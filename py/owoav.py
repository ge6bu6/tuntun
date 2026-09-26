# coding: utf-8
import sys
import re
import json
import requests
import urllib3
import html
from urllib.parse import urljoin, urlparse, quote
from bs4 import BeautifulSoup

# 禁用 SSL 警告
urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider as BaseSpider

PROTECTED_LINE_NAME = "".join([chr(0x98de), chr(0x9c7c), chr(0x9ad8), chr(0x6e05)])

class Spider(BaseSpider):
    def getName(self):
        return "owoav高清"

    def __init__(self):
        super().__init__()
        self.session = requests.Session()
        
        self.preset_urls = [
            "https://600kk.net",
            "https://owo1.cc",
            "https://owo2.cc",
            "https://owo3.cc",
            "https://owo4.cc",
            "https://ozzez.com",
            "https://owoav.com"
        ]
        
        self.publish_url = "https://www.owodz.com"
        self.site_url = self.preset_urls[0]
        
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.site_url,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

    def _verify_line_integrity(self, line_str):
        target = "".join([chr(0x98de), chr(0x9c7c), chr(0x9ad8), chr(0x6e05)])
        return str(line_str).strip() == target

    def _fetch(self, url, timeout=8):
        try:
            r = self.session.get(url, headers=self.headers, timeout=timeout, verify=False)
            r.encoding = 'utf-8'
            if r.status_code == 200:
                return r.text
        except Exception:
            pass
        return ''

    def update_site_url(self):
        if getattr(self, '_url_checked', False):
            return

        for url in self.preset_urls:
            html_text = self._fetch(f"{url}/", timeout=3)
            if html_text:
                self.site_url = url.rstrip('/')
                self.headers["Referer"] = self.site_url
                self._url_checked = True
                return

        html_text = self._fetch(self.publish_url, timeout=5)
        if html_text:
            soup = BeautifulSoup(html_text, 'html.parser')
            links = soup.select('.m-listD-item.type3 a') or soup.select('a')
            for a in links:
                href = str(a.get('href', '')).strip()
                if href.startswith('http') and not any(k in href for k in ['github', 't.me', 'ymd168', 'mailto', 'owodz']):
                    if 'owo' in href:
                        parsed = urlparse(href)
                        self.site_url = f"{parsed.scheme}://{parsed.netloc}"
                        break
                    elif self.site_url == self.preset_urls[0]:
                        parsed = urlparse(href)
                        self.site_url = f"{parsed.scheme}://{parsed.netloc}"

        self.headers["Referer"] = self.site_url
        self._url_checked = True

    def init(self, extend=""):
        self.update_site_url()

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def action(self, action):
        pass

    # 1. 首页分类与精细化筛选配置
    def homeContent(self, filter):
        self.update_site_url()
        result = {}
        
        # 隔离根分类 ID，确保绝不与网络层二级 URL 重叠
        cate_list = [
            {"type_name": "视频", "type_id": "videos"},
            {"type_name": "女优", "type_id": "cate_models_root"}, # 一级分类独占 ID
            {"type_name": "分类", "type_id": "folder_categories"},
            {"type_name": "频道", "type_id": "folder_channels"},
            {"type_name": "标签", "type_id": "folder_tags"}
        ]
        result['class'] = cate_list

        if filter:
            result['filters'] = {
                "videos": [
                    {
                        "key": "by",
                        "name": "排序",
                        "value": [
                            {"n": "最新", "v": "post_date"},
                            {"n": "热门", "v": "video_viewed"},
                            {"n": "最受欢迎", "v": "rating"},
                            {"n": "最长", "v": "duration"}
                        ]
                    }
                ],
                # 仅第一层【女优】根目录生效
                "cate_models_root": [
                    {
                        "key": "by",
                        "name": "排序",
                        "value": [
                            {"n": "默认", "v": "model_viewed"},
                            {"n": "按字母排序", "v": "title"},
                            {"n": "评分最高", "v": "rating"},
                            {"n": "观看最多", "v": "model_viewed"},
                            {"n": "评论最多", "v": "comments_count"},
                            {"n": "收藏最多", "v": "subscribers_count"}
                        ]
                    }
                ]
            }

        return result

    def homeVideoContent(self):
        return self.categoryContent('videos', '1', False, {})

    def _format_square_pic(self, img_src):
        if not img_src:
            return ""
        img_src = re.sub(r'size=\d+x\d+', 'size=max', img_src)
        if '?' in img_src:
            return img_src + "&style=fit&aspect=contain"
        return img_src + "?style=fit&aspect=contain"

    def _extract_count_only(self, item_node):
        # 1. 优先精准定位：针对包含 icon-camera 图标的 li 节点提取视频数量
        camera_li = item_node.select_one('.thumb-spot__data li i[class*="icon-camera"]')
        if camera_li and camera_li.parent:
            txt = camera_li.parent.get_text(strip=True)
            m = re.search(r'(\d+)', txt)
            if m:
                return f"{m.group(1)}个视频"

        # 2. 备用定位：针对常规数量节点
        count_node = (
            item_node.select_one('.videos-count') or 
            item_node.select_one('.video-count') or 
            item_node.select_one('.videos') or 
            item_node.select_one('.count') or 
            item_node.select_one('.v-count') or 
            item_node.select_one('.item-videos') or
            item_node.select_one('.badge') or
            item_node.select_one('.num') or
            item_node.select_one('.info') or
            item_node.select_one('.sub-title')
        )
        if count_node:
            txt = str(count_node.text).strip()
            txt = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?', '', txt)
            m = re.search(r'(\d+)', txt)
            if m:
                return f"{m.group(1)}个视频"

        # 3. 属性提取
        for attr in ['data-videos', 'data-count', 'data-total', 'videos']:
            val = item_node.get(attr)
            if val and str(val).isdigit():
                return f"{val}个视频"

        # 4. 针对 .thumb-spot__data 下的第一个 li 节点（常见于分类列表卡片）
        first_data_li = item_node.select_one('.thumb-spot__data li')
        if first_data_li:
            txt = first_data_li.get_text(strip=True)
            m = re.search(r'(\d+)', txt)
            if m:
                return f"{m.group(1)}个视频"

        # 5. HTML正则关键词匹配
        item_html = str(item_node)
        m_html_kw = re.search(r'(\d+)\s*(?:个视频|videos|视频)', item_html, re.IGNORECASE)
        if m_html_kw:
            return f"{m_html_kw.group(1)}个视频"

        # 6. 保底提取：括号匹配
        node_txt = item_node.get_text(separator=' ')
        node_txt = re.sub(r'\d{1,2}:\d{2}(?::\d{2})?', '', node_txt)

        m_bracket = re.search(r'[\(\（]\s*(\d+)\s*[\)\）]', node_txt)
        if m_bracket:
            return f"{m_bracket.group(1)}个视频"

        return ""

    def _extract_duration_only(self, item_node):
        time_node = (
            item_node.select_one('.duration') or 
            item_node.select_one('.time') or 
            item_node.select_one('.thumb-spot__data li') or
            item_node.select_one('.label-duration')
        )
        if time_node:
            txt = str(time_node.text).strip()
            m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', txt)
            if m:
                return m.group(1)

        node_txt = item_node.get_text(separator=' ')
        m = re.search(r'(\d{1,2}:\d{2}(?::\d{2})?)', node_txt)
        if m:
            return m.group(1)

        return ""

    # 2. 分类/子列表解析与动态筛选擦除
    def categoryContent(self, tid, pg, filter, extend):
        self.update_site_url()
        result = {}
        page = int(pg) if pg else 1

        pure_tid = str(tid).strip()
        while pure_tid.startswith("folder_"):
            pure_tid = pure_tid[7:]

        clean_tid_path = pure_tid.strip('/')
        
        # 判断是否进入了二级详情列表页面（如：http://site.com/models/xxx/）
        is_second_layer = pure_tid.startswith('http')

        # 如果是二级页面，强行清除传入的 extend 数据
        if is_second_layer:
            extend = {}

        # 匹配一级分类
        is_categories = clean_tid_path == 'categories' or clean_tid_path.endswith('/categories')
        is_videos_cat = clean_tid_path == 'videos'
        is_models_first_layer = (pure_tid == 'cate_models_root' or pure_tid == 'models')

        if page > 1 and is_categories:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 0, 'total': 0}

        # 组装请求 URL
        if is_second_layer:
            # 二级列表页面：直接拼接页码，绝不附带任何 ?by= 筛选参数
            base_url = pure_tid.rstrip('/')
            url = f"{base_url}/{page}/" if page > 1 else f"{base_url}/"
        else:
            if is_videos_cat:
                extend_dict = extend if isinstance(extend, dict) else {}
                by_param = extend_dict.get('by', 'post_date').strip()
                param_str = f"?by={by_param}" if by_param else ""
                url = f"{self.site_url}/{clean_tid_path}/{page}/{param_str}" if page > 1 else f"{self.site_url}/{clean_tid_path}/{param_str}"
            elif is_models_first_layer:
                # 一级【女优】列表页：响应分类筛选参数
                extend_dict = extend if isinstance(extend, dict) else {}
                by_param = extend_dict.get('by', '').strip()
                param_str = f"?by={by_param}" if by_param else ""
                url = f"{self.site_url}/models/{page}/{param_str}" if page > 1 else f"{self.site_url}/models/{param_str}"
            else:
                base_url = f"{self.site_url}/{clean_tid_path}"
                if page == 1:
                    url = f"{base_url}/"
                else:
                    parts = base_url.split('/')
                    root_types = ['tags', 'models', 'categories', 'channels', 'videos']
                    if parts[-1].isdigit() and len(parts) > 4 and parts[-2] not in root_types:
                        parts.pop()
                        base_url = "/".join(parts)
                    url = f"{base_url}/{page}/"

        html_text = self._fetch(url)
        if not html_text:
            return {'list': [], 'page': page, 'pagecount': 1, 'limit': 0, 'total': 0}

        soup = BeautifulSoup(html_text, 'html.parser')
        videos = []

        tags_container = soup.select_one('.list-tags') or soup.select_one('.models-list') or soup.select_one('.categories-list') or soup.select_one('.thumbs-models')
        items = (
            soup.select('.thumbs__list .item') or 
            soup.select('.thumbs__list .thumb') or 
            soup.select('.thumbs-models .item') or
            soup.select('.thumbs-categories .item') or
            soup.select('.thumbs-categories .thumb') or
            soup.select('.list-categories .item') or
            soup.select('.categories-list .item')
        )

        if tags_container and not items:
            tag_a_nodes = tags_container.select('a')
            for a_tag in tag_a_nodes:
                href = str(a_tag.get('href', '')).strip()
                if not href:
                    continue

                raw_url = href if href.startswith('http') else urljoin(self.site_url, href)
                full_text = str(a_tag.get_text(strip=True))
                
                num_match = re.search(r'[\(\（\s]*(\d+)[\)\）\s]*$', full_text)
                if num_match:
                    num_val = num_match.group(1)
                    title = re.sub(r'[\(\（\s]*\d+[\)\）\s]*$', '', full_text).strip()
                    remarks = f"{num_val}个视频"
                else:
                    title = full_text
                    remarks = "进入查看"

                if not title:
                    continue

                v_item = {
                    "vod_id": str(f"folder_{raw_url}"),
                    "vod_name": str(title),
                    "vod_pic": "",
                    "vod_remarks": str(remarks),
                    "vod_tag": "folder"
                }

                if any(k in raw_url for k in ['/models/', '/categories/', '/channels/', '/tags/']):
                    v_item["style"] = {"type": "rect", "ratio": 1.0, "crop": False}
                    v_item["pic_style"] = {"type": "rect", "ratio": 1.0, "fill": "fit"}

                videos.append(v_item)

            result['list'] = videos
            result['page'] = page
            
            if is_categories:
                result['pagecount'] = 1
                result['total'] = len(videos)
            else:
                result['pagecount'] = page + 1 if len(videos) >= 12 else page
                result['total'] = 9999

            result['limit'] = len(videos)
            
            # 【关键补丁】如果请求的是二级页面，显式返回空的 filter 声明，强行卸载客户端继承的筛选 UI
            if is_second_layer:
                result['filter'] = False
                result['filters'] = {}

            return result

        for item in items:
            a_tag = item.find('a')
            if not a_tag:
                continue

            href = str(a_tag.get('href', '')).strip()
            if not href:
                continue

            raw_url = href if href.startswith('http') else urljoin(self.site_url, href)

            title = str(a_tag.get('title', '')).strip()
            if not title:
                title_node = item.select_one('.thumb-spot__title') or item.select_one('.title') or item.select_one('.name')
                if title_node:
                    title = str(title_node.text).strip()
            
            if title:
                title = re.sub(r'[\(\（\s]*\d+[\)\）\s]*$', '', title).strip()

            img_tag = item.find('img')
            img_src = ""
            if img_tag:
                img_src = str(img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src', ''))
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src

            is_folder = ('/video/' not in raw_url and '/v/' not in raw_url and 
                         any(k in raw_url for k in ['/models/', '/categories/', '/channels/', '/tags/']) and 
                         raw_url.count('/') <= 5)

            is_square_item = any(k in raw_url for k in ['/models/', '/categories/', '/channels/', '/tags/'])

            if is_folder:
                remarks = self._extract_count_only(item) or "进入查看"

                vod_dict = {
                    "vod_id": str(f"folder_{raw_url}"),
                    "vod_name": str(title if title else "目录"),
                    "vod_pic": str(self._format_square_pic(img_src) if is_square_item else img_src),
                    "vod_remarks": str(remarks),
                    "vod_tag": "folder"
                }

                if is_square_item:
                    vod_dict["style"] = {"type": "rect", "ratio": 1.0, "crop": False}
                    vod_dict["pic_style"] = {"type": "rect", "ratio": 1.0, "fill": "fit"}

                videos.append(vod_dict)
            else:
                duration_str = self._extract_duration_only(item)
                videos.append({
                    "vod_id": str(raw_url),
                    "vod_name": str(title if title else "视频"),
                    "vod_pic": str(img_src),
                    "vod_remarks": str(duration_str)
                })

        result['list'] = videos
        result['page'] = page
        
        if is_categories:
            result['pagecount'] = 1
            result['total'] = len(videos)
        else:
            result['pagecount'] = page + 1 if len(videos) >= 12 else page
            result['total'] = 9999

        result['limit'] = len(videos)

        # 【关键补丁】二级列表显式告诉播放器：“此页面禁用筛选”
        if is_second_layer:
            result['filter'] = False
            result['filters'] = {}

        return result

    def detailContent(self, array):
        self.update_site_url()
        
        if not self._verify_line_integrity(PROTECTED_LINE_NAME):
            return {"list": []}

        raw_vod_id = array[0] if isinstance(array, list) else array
        clean_url = str(raw_vod_id).strip()
        while clean_url.startswith("folder_"):
            clean_url = clean_url[7:]
            
        url = clean_url if clean_url.startswith('http') else urljoin(self.site_url, clean_url)

        html_text = self._fetch(url)
        if not html_text:
            return {"list": []}

        soup = BeautifulSoup(html_text, 'html.parser')

        title_node = soup.select_one('h1.title') or soup.select_one('h1')
        title = str(title_node.text).strip() if title_node else "视频详情"

        pic = ""
        match_pic = re.search(r"preview_url\s*:\s*'([^']+)'", html_text)
        if match_pic:
            pic = match_pic.group(1).replace(r'\/', '/')
        else:
            img_node = soup.select_one('.player-holder img') or soup.select_one('meta[property="og:image"]')
            if img_node:
                pic = str(img_node.get('content') or img_node.get('src', ''))

        desc = ""
        desc_node = soup.select_one('.media-desc .media-info__desc') or soup.select_one('.description') or soup.select_one('meta[name="description"]')
        if desc_node:
            desc = str(desc_node.get('content', '') if desc_node.name == 'meta' else desc_node.text).strip()

        actor_list = []
        match_models = re.search(r"video_models\s*:\s*'([^']+)'", html_text)
        if match_models and match_models.group(1).strip():
            actor_list.extend([m.strip() for m in match_models.group(1).split(',') if m.strip()])
        
        if not actor_list:
            model_nodes = soup.select('.media-model .media-box__title') or soup.select('.media-models a[href*="/models/"]')
            for node in model_nodes:
                name = str(node.text).strip()
                if name and name != "查看资料" and name not in actor_list:
                    actor_list.append(name)
        
        vod_actor = " ".join(actor_list) if actor_list else ""

        type_list = []
        match_cate = re.search(r"video_categories\s*:\s*'([^']+)'", html_text)
        if match_cate and match_cate.group(1).strip():
            type_list.extend([c.strip() for c in match_cate.group(1).split(',') if c.strip()])

        if not type_list:
            for row in soup.select('.media-info__lists-row'):
                label = row.select_one('.media-info__label')
                if label and "分类" in label.text:
                    for a in row.select('.media-info__buttons a'):
                        cat_text = str(a.text).strip()
                        if cat_text and cat_text not in type_list:
                            type_list.append(cat_text)

        raw_type_str = " ".join(type_list) if type_list else ""

        tag_list = []
        match_tags = re.search(r"video_tags\s*:\s*'([^']+)'", html_text)
        if match_tags and match_tags.group(1).strip():
            tag_list.extend([t.strip() for t in match_tags.group(1).split(',') if t.strip()])

        if not tag_list:
            for row in soup.select('.media-info__lists-row'):
                label = row.select_one('.media-info__label')
                if label and "标签" in label.text:
                    for a in row.select('.media-info__buttons a'):
                        tag_text = str(a.text).strip()
                        if tag_text and tag_text not in tag_list:
                            tag_list.append(tag_text)

        if not tag_list:
            meta_tags = soup.select('meta[property="video:tag"]')
            for meta in meta_tags:
                tag_content = str(meta.get('content', '')).strip()
                if tag_content and tag_content not in tag_list:
                    tag_list.append(tag_content)

        raw_tag_str = " ".join(tag_list) if tag_list else ""

        if raw_type_str and raw_tag_str:
            combined_type = f"{raw_type_str} / {raw_tag_str}"
        elif raw_tag_str:
            combined_type = raw_tag_str
        elif raw_type_str:
            combined_type = raw_type_str
        else:
            combined_type = "未知"

        vod = {
            "vod_id": str(url),
            "vod_name": str(title),
            "vod_pic": str(pic),
            "type_name": str(combined_type),
            "vod_class": str(combined_type),
            "vod_actor": str(vod_actor),
            "vod_content": str(desc),
            "vod_play_from": str(PROTECTED_LINE_NAME),
            "vod_play_url": f"正片${str(url)}"
        }

        return {"list": [vod]}

    def searchContent(self, key, quick, pg='1'):
        self.update_site_url()
        page = int(pg) if pg else 1

        clean_key = str(key).strip()
        encoded_key = quote(clean_key)
        
        url = f"{self.site_url}/search/{encoded_key}/{page}/" if page > 1 else f"{self.site_url}/search/{encoded_key}/"

        html_text = self._fetch(url)
        if not html_text:
            return {"list": [], 'page': page, 'pagecount': 1}

        soup = BeautifulSoup(html_text, 'html.parser')
        videos = []
        items = (
            soup.select('.thumbs__list .item') or 
            soup.select('.thumbs__list .thumb') or 
            soup.select('.thumbs-models .item') or
            soup.select('.thumbs-categories .item')
        )

        for item in items:
            a_tag = item.find('a')
            if not a_tag:
                continue

            href = str(a_tag.get('href', '')).strip()
            if not href:
                continue

            vod_id = href if href.startswith('http') else urljoin(self.site_url, href)

            title = str(a_tag.get('title', '')).strip()
            if not title:
                title_node = item.select_one('.thumb-spot__title') or item.select_one('.title') or item.select_one('.name')
                title = str(title_node.text).strip() if title_node else str(a_tag.text).strip()

            img_tag = item.find('img')
            img_src = ""
            if img_tag:
                img_src = str(img_tag.get('data-original') or img_tag.get('data-src') or img_tag.get('src', ''))
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src

            is_folder = ('/video/' not in vod_id and '/v/' not in vod_id and 
                         any(k in vod_id for k in ['/models/', '/categories/', '/channels/', '/tags/']))

            is_square_item = any(k in vod_id for k in ['/models/', '/categories/', '/channels/', '/tags/'])

            if is_folder:
                remarks = self._extract_count_only(item) or "进入查看"
            else:
                remarks = self._extract_duration_only(item)

            item_dict = {
                "vod_id": str(f"folder_{vod_id}" if is_folder else vod_id),
                "vod_name": str(title if title else clean_key),
                "vod_pic": str(self._format_square_pic(img_src) if is_square_item else img_src),
                "vod_remarks": str(remarks)
            }
            if is_folder:
                item_dict["vod_tag"] = "folder"
                if is_square_item:
                    item_dict["style"] = {"type": "rect", "ratio": 1.0, "crop": False}
                    item_dict["pic_style"] = {"type": "rect", "ratio": 1.0, "fill": "fit"}

            videos.append(item_dict)

        if not videos:
            blocks = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_text, re.S)
            for href, inner in blocks:
                if any(k in href for k in ['/video/', '/models/', '/categories/', '/channels/', '/tags/']):
                    full_url = href if href.startswith('http') else urljoin(self.site_url, href)
                    clean_inner = re.sub(r'<[^>]+>', '', inner).strip()
                    if clean_inner:
                        is_folder = '/video/' not in full_url
                        is_square_item = any(k in full_url for k in ['/models/', '/categories/', '/channels/', '/tags/'])
                        item_dict = {
                            "vod_id": str(f"folder_{full_url}" if is_folder else full_url),
                            "vod_name": str(clean_inner),
                            "vod_pic": "",
                            "vod_remarks": str("进入查看" if is_folder else "")
                        }
                        if is_folder and is_square_item:
                            item_dict["style"] = {"type": "rect", "ratio": 1.0, "crop": False}
                            item_dict["pic_style"] = {"type": "rect", "ratio": 1.0, "fill": "fit"}
                        videos.append(item_dict)

        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page
        }

    def playerContent(self, flag, id, vipFlags=None):
        self.update_site_url()
        clean_id = str(id).strip()
        while clean_id.startswith("folder_"):
            clean_id = clean_id[7:]
            
        play_url = ""

        page_url = clean_id if clean_id.startswith("http") else urljoin(self.site_url, clean_id)

        if "/video/" in page_url:
            try:
                rsp = self.session.get(page_url, headers=self.headers, timeout=8, verify=False)
                if rsp.status_code == 200:
                    html_text = rsp.text

                    match_url = re.search(r"video_url\s*:\s*['\"]([^'\"]+)['\"]", html_text)
                    if match_url:
                        play_url = match_url.group(1)
                    else:
                        soup = BeautifulSoup(html_text, 'html.parser')
                        source_tag = soup.select_one('video source') or soup.select_one('#download_list a[href*="get_file"]')
                        if source_tag and source_tag.get('src'):
                            play_url = str(source_tag['src'])
                        elif source_tag and source_tag.get('href'):
                            play_url = str(source_tag['href'])
            except Exception:
                pass
        elif ".mp4" in page_url or ".m3u8" in page_url:
            play_url = page_url

        if play_url:
            play_url = play_url.replace(r'\/', '/').replace('\\', '').strip()
            if play_url.startswith('//'):
                play_url = 'https:' + play_url
            elif not play_url.startswith('http'):
                play_url = urljoin(self.site_url, play_url)

        parsed_page_url = urlparse(page_url)
        referer_domain = f"{parsed_page_url.scheme}://{parsed_page_url.netloc}" if parsed_page_url.netloc else self.site_url

        play_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": str(referer_domain)
        }

        final_url = str(play_url if play_url else page_url)

        return {
            "parse": 0,
            "url": final_url,
            "header": play_headers
        }
