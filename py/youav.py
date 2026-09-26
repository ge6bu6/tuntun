#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
源名称：YouAVHub
说明：符合 CatVod / TVBox 蜘蛛框架 (Spider) 标准规范
"""

import re
import json
import copy
import urllib.parse
import urllib3
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

# 禁用不安全请求警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Spider(Spider):
    name = "YouAVHub"
    base_url = "https://youavhub.com"
    
    # 分类名称与分类ID
    class_name = [
        '日本AV', '巨乳', '熟女人妻', '中文字幕', '少女蘿莉', 
        '翹臀美尻', '亂倫、誘惑', '制服誘惑', '高潮潮吹', '多P群交', 
        'SM調教', '抖陰短片', '激情口交', 'AV女優無碼', '野外性愛', 
        '麻豆', '歐美無碼', '國產素人自拍', '同性戀', '18+成人激情電影'
    ]
    class_url = [
        '22', '20', '21', '23', '24', 
        '26', '29', '34', '27', '41', 
        '38', '25', '39', '33', '40', 
        '37', '28', '30', '32', '43'
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://youavhub.com/',
        'Connection': 'keep-alive'
    }
    timeout = 10
    page_size = 20

    def getName(self):
        return self.name

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def _get(self, url, headers=None, params=None):
        """GET 请求封装（强制开启 verify=False 规避 SSL 证书拦截）"""
        try:
            resp = requests.get(
                url, 
                headers=headers or self.headers, 
                params=params, 
                timeout=self.timeout,
                verify=False
            )
            resp.encoding = 'utf-8'
            return resp.text
        except Exception as e:
            print(f"[{self.name}] 请求失败 ({url}): {e}")
            return None

    def _parse_list(self, html):
        """解析页面中的卡片列表（兼容首页、分类页、搜索页）"""
        vod_list = []
        if not html:
            return vod_list
        
        soup = BeautifulSoup(html, 'html.parser')
        items = soup.select('.vodlist_item, .searchlist_item, .pack-yg')
        
        for item in items:
            # 1. 标题标签精准获取
            a_tag = (
                item.select_one('.searchlist_titbox h4 a') or 
                item.select_one('a.vodlist_thumb') or 
                item.select_one('a.searchlist_thumb') or 
                item.select_one('.pack-yg-tit a') or 
                item.select_one('a')
            )
            
            # 2. 图片标签精准获取
            img_tag = (
                item.select_one('.searchlist_img a') or 
                item.select_one('a.vodlist_thumb') or 
                item.select_one('a.searchlist_thumb') or 
                item.select_one('img')
            )
            
            # 3. 备注/角标信息
            sub_tag = item.select_one('.pic_text, .pic-text, .vodlist_sub, .pack-subtitle')
            
            if a_tag:
                href = a_tag.get('href', '')
                if not href:
                    continue

                match = re.search(r'/id/(\d+)', href)
                vod_id = match.group(1) if match else href
                
                # 获取标题：优先 read title 属性，防拼接 <span>分类
                title = a_tag.get('title', '').strip()
                if not title:
                    tag_copy = copy.copy(a_tag)
                    for span in tag_copy.find_all('span'):
                        span.decompose()
                    title = tag_copy.text.strip()
                
                # 获取图片地址
                pic = ''
                if img_tag:
                    pic = (
                        img_tag.get('data-original') or 
                        img_tag.get('data-src') or 
                        img_tag.get('data-lazyload') or 
                        img_tag.get('src', '')
                    ).strip()
                    if pic:
                        pic = urllib.parse.urljoin(self.base_url, pic)
                        
                remarks = sub_tag.text.strip() if sub_tag else ''
                
                if vod_id and title:
                    vod_list.append({
                        'vod_id': str(vod_id),
                        'vod_name': title,
                        'vod_pic': pic,
                        'vod_remarks': remarks
                    })
        return vod_list

    def homeContent(self, filter=False):
        """首页推荐内容及分类定义"""
        result = {'class': [], 'list': []}
        try:
            classes = []
            for i in range(min(len(self.class_name), len(self.class_url))):
                classes.append({
                    'type_name': self.class_name[i],
                    'type_id': self.class_url[i]
                })
            result['class'] = classes

            html = self._get(self.base_url)
            result['list'] = self._parse_list(html)
        except Exception as e:
            print(f"[{self.name}] 首页数据解析失败: {e}")
        return result

    def homeVideoContent(self):
        """获取首页视频推荐列表"""
        return {'list': self._parse_list(self._get(self.base_url))}

    def categoryContent(self, tid, pg, filter=False, content=None):
        """分类列表内容"""
        result = {'list': [], 'page': int(pg), 'pagecount': 99, 'limit': self.page_size, 'total': 999}
        try:
            url = f"{self.base_url}/index.php/vod/show/id/{tid}/page/{pg}/"
            html = self._get(url)
            result['list'] = self._parse_list(html)
        except Exception as e:
            print(f"[{self.name}] 分类解析失败: {e}")
        return result

    def detailContent(self, ids):
        """详情页内容及播放线路与选集解析"""
        result = []
        try:
            vod_id = ids[0] if isinstance(ids, list) else str(ids)
            
            if vod_id.startswith('http'):
                url = vod_id
            elif vod_id.isdigit():
                url = f"{self.base_url}/index.php/vod/play/id/{vod_id}/sid/1/nid/1/"
            else:
                url = urllib.parse.urljoin(self.base_url, vod_id)
            
            html = self._get(url)
            if html:
                soup = BeautifulSoup(html, 'html.parser')
                
                title, pic = "", ""
                match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.DOTALL)
                if match:
                    try:
                        pdata = json.loads(match.group(1))
                        vod_data = pdata.get("vod_data", {})
                        title = vod_data.get("vod_name", "")
                    except Exception:
                        pass

                if not title:
                    title_el = soup.select_one('.play_namebox .title, h1, .vodlist_title')
                    title = title_el.text.strip() if title_el else ''

                pic_el = soup.select_one('.play_vlist_thumb, .vodlist_thumb, img')
                if pic_el:
                    pic_src = (
                        pic_el.get('data-original') or 
                        pic_el.get('data-src') or 
                        pic_el.get('src', '')
                    )
                    pic = urllib.parse.urljoin(self.base_url, pic_src)

                vod = {
                    'vod_id': vod_id,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': '',
                    'vod_content': '',
                }
                
                play_from_list = []
                play_url_list = []
                
                bofy_el = soup.select_one('#bofy')
                if bofy_el:
                    tabs = [t.text.strip() for t in bofy_el.select('ul.title_nav li.tab-play') if t.text.strip()]
                    playlists = bofy_el.select('ul.content_playlist')
                    
                    if playlists:
                        for i, playlist in enumerate(playlists):
                            from_name = tabs[i] if i < len(tabs) else f"线路{i+1}"
                            play_from_list.append(from_name)
                            
                            episodes = []
                            for a in playlist.select('a'):
                                ep_title = a.text.strip() or '播放'
                                ep_url = urllib.parse.urljoin(self.base_url, a.get('href', ''))
                                episodes.append(f"{ep_title}${ep_url}")
                                
                            play_url_list.append('#'.join(episodes))

                if not play_url_list:
                    play_from_list.append("默认线路")
                    play_url_list.append(f"正片${url}")
                
                vod['vod_play_from'] = '$$$'.join(play_from_list)
                vod['vod_play_url'] = '$$$'.join(play_url_list)
                result.append(vod)
        except Exception as e:
            print(f"[{self.name}] 详情解析失败: {e}")
        return {'list': result}

    def searchContent(self, key, pg, filter=False):
        """搜索解析（使用 MacCMS 万能伪静态路径 + 智能防重复编码 + 证书绕过）"""
        result = {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': self.page_size, 'total': 0}
        if not key:
            return result
        try:
            # 智能判断，防止客户端二次转码
            encoded_key = key if '%' in key else urllib.parse.quote(key)
            
            session = requests.Session()
            session.headers.update(self.headers)
            
            # 1. 预热访问首页拿 Cookie (verify=False)
            try:
                session.get(self.base_url, timeout=5, verify=False)
            except Exception:
                pass

            # 2. 优先使用 MacCMS 万能穿透搜索路径
            url = f"{self.base_url}/vodsearch/-------------/?wd={encoded_key}&page={pg}"
            
            resp = session.get(url, timeout=self.timeout, verify=False)
            resp.encoding = 'utf-8'
            html = resp.text

            # 3. 兜底策略：如果万能路径未命中，切换回原生动态搜索路由
            if not html or ('searchlist_item' not in html and 'vodlist_item' not in html and 'pack-yg' not in html):
                alt_url = f"{self.base_url}/index.php/vod/search/?wd={encoded_key}&page={pg}"
                resp = session.get(alt_url, timeout=self.timeout, verify=False)
                resp.encoding = 'utf-8'
                html = resp.text

            result['list'] = self._parse_list(html)
        except Exception as e:
            print(f"[{self.name}] 搜索解析失败: {e}")
        return result

    def playerContent(self, flag, id, vipFlags=None):
        """播放链接提取"""
        result = {
            'parse': 0,
            'url': id,
            'header': {
                'User-Agent': self.headers['User-Agent'],
                'Referer': self.base_url
            }
        }
        try:
            url = id if id.startswith('http') else urllib.parse.urljoin(self.base_url, id)
            html = self._get(url)
            
            if html:
                match = re.search(r'var\s+(?:player_a+a|player_data|MacPlayer)\s*=\s*(\{.*?\});', html, re.DOTALL)
                if match:
                    try:
                        player_info = json.loads(match.group(1))
                        play_url = player_info.get('url', '')
                        
                        if play_url:
                            play_url = urllib.parse.unquote(play_url).replace('\\/', '/')
                            
                            result['url'] = play_url
                            if '.m3u8' in play_url or '.mp4' in play_url:
                                result['parse'] = 0
                            else:
                                result['parse'] = 1
                            return result
                    except Exception as e:
                        print(f"[{self.name}] JSON解析失败: {e}")

            m3u8_match = re.search(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html or '')
            if m3u8_match:
                result['parse'] = 0
                result['url'] = m3u8_match.group(1).replace('\\/', '/')
                return result

            if '.m3u8' in id or '.mp4' in id:
                result['parse'] = 0
            else:
                result['parse'] = 1
            return result
        except Exception as e:
            print(f"[{self.name}] 播放解析失败: {e}")
            result['parse'] = 1
            return result

    def localProxy(self, param):
        pass
