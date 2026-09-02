"""
==================================================
@Spider Name : MissAV
@Author      : 飞鱼
@Version     : 1.0.0
@Description : TVBox/CatVod MissAV Spider Plugin
==================================================
"""

import json
import sys
import re
import base64
from urllib.parse import urljoin, quote, unquote
from pyquery import PyQuery as pq

# 兼容 Spider 基础类导入
sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    author = "飞鱼"
    version = "1.0.0"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    # 轮询域名列表（优先使用 missav02.xyz，失败自动切换 missav.app）
    domains = [
        'https://missav02.xyz',
        'https://missav.app'
    ]

    def getDependence(self):
        return ['pyquery']

    def getName(self):
        # UI 界面直接显示作者署名
        return "MissAV (by 飞鱼)"

    def init(self, extend=""):
        # 日志控制台输出作者版权提示
        print(f"[{self.getName()}] 插件加载成功 | 作者: {self.author} | 版本: {self.version}")

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    # 核心轮询请求工具：支持多域名故障转移
    def _fetch_with_fallback(self, path):
        """
        传入相对路径（如 '/label/new/'）或包含占位符的路径，自动依次尝试各个域名。
        """
        for domain in self.domains:
            full_url = urljoin(domain, path)
            try:
                rsp = self.fetch(full_url, headers=self.headers)
                # 校验状态码以及非 CF 拦截页面
                if rsp and rsp.status_code == 200 and 'Just a moment...' not in rsp.text:
                    return rsp.text, domain
            except Exception:
                continue
        return None, self.domains[0]

    # 1. 首页推荐数据 & 分类菜单
    def homeContent(self, filter):
        result = {}
        
        # 定义分类
        classes = [
            {"type_name": "国产", "type_id": "20"},
            {"type_name": "日本有码", "type_id": "21"},
            {"type_name": "日本无码", "type_id": "22"},
            {"type_name": "中文字幕", "type_id": "28"},
            {"type_name": "欧美", "type_id": "23"},
            {"type_name": "动漫", "type_id": "24"},
            {"type_name": "伦理", "type_id": "25"}
        ]
        result['class'] = classes

        # 筛选配置
        filters = {
            "20": [{"key": "cateId", "name": "分类", "value": [{"v": "20", "n": "全部"}, {"v": "26", "n": "国产精品"}, {"v": "27", "n": "国产剧情"}, {"v": "29", "n": "国产自拍"}, {"v": "35", "n": "国产主播"}, {"v": "85", "n": "国模私拍"}, {"v": "91", "n": "网红明星"}, {"v": "105", "n": "国产SM"}, {"v": "107", "n": "台湾辣妹"}, {"v": "108", "n": "香港正妹"}]}],
            "21": [{"key": "cateId", "name": "分类", "value": [{"v": "21", "n": "全部"}, {"v": "31", "n": "人妻"}, {"v": "44", "n": "素人"}, {"v": "46", "n": "口爆颜射"}, {"v": "47", "n": "萝莉少女"}, {"v": "48", "n": "美乳巨乳"}, {"v": "52", "n": "制服诱惑"}, {"v": "57", "n": "调教"}, {"v": "58", "n": "出轨"}, {"v": "101", "n": "有码精品"}]}],
            "22": [{"key": "cateId", "name": "分类", "value": [{"v": "22", "n": "全部"}, {"v": "102", "n": "无码精品"}]}],
            "23": [{"key": "cateId", "name": "分类", "value": [{"v": "23", "n": "全部"}, {"v": "104", "n": "欧美精品"}]}],
            "24": [{"key": "cateId", "name": "分类", "value": [{"v": "24", "n": "全部"}, {"v": "103", "n": "动漫精品"}]}],
            "25": [{"key": "cateId", "name": "分类", "value": [{"v": "25", "n": "全部"}, {"v": "39", "n": "综合三级"}]}],
            "28": [{"key": "cateId", "name": "分类", "value": [{"v": "28", "n": "全部"}, {"v": "51", "n": "日本中字"}]}]
        }
        if filter:
            result['filters'] = filters

        # 轮询获取首页推荐视频
        try:
            html, base_domain = self._fetch_with_fallback("/label/new/")
            if html:
                doc = pq(html)
                videos = self._parse_cards(doc, base_domain)
                result['list'] = videos
            else:
                result['list'] = []
        except Exception:
            result['list'] = []

        return result

    def homeVideoContent(self):
        return self.homeContent(False)

    # 2. 分类列表数据处理
    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        page = int(pg)
        
        target_cate_id = extend.get('cateId', tid) if extend else tid
        path = f"/vodtype/{target_cate_id}-{page}/"
        
        try:
            html, base_domain = self._fetch_with_fallback(path)
            if html:
                doc = pq(html)
                videos = self._parse_cards(doc, base_domain)
                
                result['list'] = videos
                result['page'] = page
                result['pagecount'] = page + 1
                result['limit'] = 20
                result['total'] = 9999
            else:
                result['list'] = []
        except Exception:
            result['list'] = []

        return result

    # 3. 详情页解析
    def detailContent(self, array):
        vod_id = array[0]
        
        try:
            path = vod_id
            for d in self.domains:
                if path.startswith(d):
                    path = path.replace(d, '')
                    break
                    
            html, base_domain = self._fetch_with_fallback(path)
            if not html:
                return {'list': []}

            doc = pq(html)

            title = doc('meta[property="og:title"]').attr('content') or doc('title').text()
            pic = doc('img.w-full').attr('src') or doc('img').attr('data-src') or ''
            
            type_name = doc('.text-muted a').text()
            actor = ''
            if '</a>：' in html and '</p>' in html:
                try:
                    actor = html.split('</a>：')[1].split('</p>')[0].replace('<a>', '').replace('</a>', '').strip()
                except Exception:
                    actor = ''
                    
            remarks = ''
            if '概要：</span>' in html and '</p>' in html:
                try:
                    remarks = html.split('概要：</span>')[1].split('</p>')[0].strip()
                except Exception:
                    remarks = ''

            play_url = urljoin(base_domain, path)
            vod_play_from = f"MissAV直连 ({self.author})"
            vod_play_url = f"正片播放${play_url}"

            vod = {
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': pic,
                'type_name': type_name,
                'vod_actor': actor,
                'vod_content': remarks,
                'vod_play_from': vod_play_from,
                'vod_play_url': vod_play_url
            }

            return {'list': [vod]}
        except Exception:
            return {'list': []}

    # 4. 搜索处理
    def searchContent(self, key, quick, pg="1"):
        result = {}
        encoded_key = quote(key)
        path = f"/vodsearch/{encoded_key}-------------/"

        try:
            html, base_domain = self._fetch_with_fallback(path)
            if html:
                doc = pq(html)
                videos = self._parse_cards(doc, base_domain)
                result['list'] = videos
            else:
                result['list'] = []
        except Exception:
            result['list'] = []

        return result

    # 5. 播放接口（优先直连正则提取 .m3u8，提取失败自动切为 Web 嗅探）
    def playerContent(self, flag, id, vipFlags):
        result = {
            'parse': '1',
            'playUrl': '',
            'url': id,
            'header': json.dumps(self.headers)
        }

        try:
            rsp = self.fetch(id, headers=self.headers)
            html = rsp.text if rsp else ""

            match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html)
            if match:
                player_json = json.loads(match.group(1))
                raw_url = player_json.get('url', '')
                encrypt = player_json.get('encrypt', 0)

                if encrypt == 1:
                    raw_url = unquote(raw_url)
                elif encrypt == 2:
                    raw_url = unquote(base64.b64decode(raw_url).decode('utf-8'))

                if raw_url and ('.m3u8' in raw_url or '.mp4' in raw_url or 'http' in raw_url):
                    result['parse'] = '0'
                    result['url'] = raw_url
        except Exception:
            pass

        return result

    # 辅助工具：提取视频列表卡片
    def _parse_cards(self, doc, base_domain):
        videos = []
        items = doc('body .gap-5 .group').items()
        
        for item in items:
            link = item('a').attr('href')
            if not link:
                continue
            
            vod_id = link if link.startswith('http') else urljoin(base_domain, link)
            title = item('.text-nord4').text().strip()
            img = item('img').attr('data-src') or item('img').attr('src') or ''
            
            absolute_els = item('.absolute')
            remarks = ""
            if len(absolute_els) >= 2:
                sub1 = pq(absolute_els[1]).text().strip()
                sub0 = pq(absolute_els[0]).text().strip()
                remarks = f"{sub1} {sub0}".strip()
            elif len(absolute_els) == 1:
                remarks = pq(absolute_els[0]).text().strip()

            videos.append({
                'vod_id': vod_id,
                'vod_name': title,
                'vod_pic': img,
                'vod_remarks': remarks
            })

        return videos
