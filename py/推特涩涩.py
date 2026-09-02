# -*- coding: utf-8 -*-
# PeKtino.com - TVBox 爬虫脚本 (全部 + 筛选器)

import sys
import re
import json
import requests
from urllib.parse import urljoin, quote, unquote

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def getName(self): return "Base"
        def homeContent(self, filter): return {"class": []}
        def categoryContent(self, tid, pg, filter, extend): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def searchContent(self, key, quick, pg="1"): return {"list": []}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def destroy(self): pass
        def localProxy(self, param): return None

class Spider(BaseSpider):
    def init(self, extend=""):
        self.host = "https://pektino.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        self.lang = "zh-CN"
        self.debug = True

    def _log(self, msg):
        if self.debug:
            print(f"[PeKtino] {msg}")

    def getName(self):
        return "PeKtino"

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("http"):
            return url
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host + url
        return self.host + "/" + url

    def _fetch(self, url):
        try:
            r = self.session.get(url, timeout=15)
            if r.status_code == 200:
                r.encoding = "utf-8"
                return r.text
            return ""
        except Exception as e:
            self._log(f"请求失败: {e}")
            return ""

    def homeContent(self, filter=False):
        # 只有一个分类：全部
        classes = [{"type_id": "all", "type_name": "全部"}]

        # 筛选器定义：时间 + 排序
        filters = {
            "all": [
                {
                    "key": "time_range",
                    "name": "时间分类",
                    "value": [
                        {"n": "每日", "v": "daily"},
                        {"n": "每周", "v": "weekly"},
                        {"n": "每月", "v": "monthly"},
                        {"n": "所有时间", "v": "all"},
                    ]
                },
                {
                    "key": "sort",
                    "name": "排序方式",
                    "value": [
                        {"n": "按点赞", "v": "favorite"},
                        {"n": "按观看数", "v": "pv"},
                        {"n": "按时长", "v": "time"},
                        {"n": "最近添加", "v": "created"},
                    ]
                }
            ]
        }
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        # 默认使用所有时间 + 按点赞
        return self.categoryContent("all", "1", False, {"time_range": "all", "sort": "favorite"})

    def _extract_videos(self, html):
        videos = []
        if not html:
            return videos

        pattern = r'<div class="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden mb-4">(.*?)</div>\s*<div class="m-2">'
        items = re.findall(pattern, html, re.DOTALL)
        if not items:
            items = re.findall(r'<div class="bg-white[^"]*rounded-lg[^"]*shadow-md[^"]*overflow-hidden mb-4">(.*?)</div>\s*<div class="m-2">', html, re.DOTALL)

        if items:
            for item in items:
                try:
                    link_match = re.search(r'href="(/zh-CN/movie/[^"]+)"', item)
                    if not link_match:
                        continue
                    link = link_match.group(1)

                    img_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*>', item)
                    pic = self._fix_url(img_match.group(1)) if img_match else ""

                    duration_match = re.search(r'<div class="absolute bottom-2 right-2 bg-black/60 text-white text-xs px-2 py-1 rounded-lg">([^<]+)</div>', item)
                    duration = duration_match.group(1).strip() if duration_match else ""

                    views_match = re.search(r'<img src="/icons/eye-black\.svg"[^>]*>([^<]+)</span>', item)
                    views = views_match.group(1).strip() if views_match else ""

                    fav_match = re.search(r'<img src="/icons/heart-black\.svg"[^>]*><span[^>]*>([^<]+)</span>', item)
                    fav = fav_match.group(1).strip() if fav_match else ""

                    title_match = re.search(r'alt="([^"]+)"', item)
                    title = title_match.group(1) if title_match else link.split("/")[-1]

                    vid_match = re.search(r'/movie/([^/]+)', link)
                    vid = vid_match.group(1) if vid_match else link

                    remarks = []
                    if duration:
                        remarks.append(f"⏱{duration}")
                    if views:
                        remarks.append(f"👁{views}")
                    if fav:
                        remarks.append(f"❤{fav}")

                    videos.append({
                        "vod_id": vid,
                        "vod_name": title,
                        "vod_pic": pic,
                        "vod_remarks": " | ".join(remarks),
                    })
                except:
                    continue

        if not videos:
            next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
            if next_data:
                try:
                    data = json.loads(next_data.group(1))
                    def find_items(obj):
                        if isinstance(obj, dict):
                            if "props" in obj and "pageProps" in obj["props"]:
                                page_props = obj["props"]["pageProps"]
                                if "initialItems" in page_props:
                                    return page_props["initialItems"]
                            for value in obj.values():
                                result = find_items(value)
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_items(item)
                                if result:
                                    return result
                        return None
                    items = find_items(data)
                    if items:
                        for item in items:
                            vid = item.get("url_cd", "")
                            if vid:
                                title = item.get("anime_title") or vid
                                pic = item.get("thumbnail", "")
                                pic = self._fix_url(pic)
                                duration = ""
                                if "time" in item:
                                    m = item["time"] // 60
                                    s = item["time"] % 60
                                    duration = f"{m:02d}:{s:02d}"
                                views = item.get("pv", "")
                                fav = item.get("favorite", "")
                                remarks = []
                                if duration:
                                    remarks.append(f"⏱{duration}")
                                if views:
                                    remarks.append(f"👁{views}")
                                if fav:
                                    remarks.append(f"❤{fav}")
                                videos.append({
                                    "vod_id": vid,
                                    "vod_name": title,
                                    "vod_pic": pic,
                                    "vod_remarks": " | ".join(remarks),
                                })
                except Exception as e:
                    self._log(f"解析 __NEXT_DATA__ 失败: {e}")

        return videos

    def _get_pagecount(self, html):
        page_links = re.findall(r'<a[^>]*href="[^"]*page=(\d+)"[^>]*>', html)
        if page_links:
            return max(int(p) for p in page_links)
        last_match = re.search(r'href="[^"]*page=(\d+)"[^>]*>最后', html)
        if last_match:
            return int(last_match.group(1))
        return 1

    def categoryContent(self, tid, pg, filter=False, extend=None):
        pg = int(pg) if pg else 1
        extend = extend or {}

        # 从筛选器获取参数
        time_range = extend.get("time_range", "all")
        sort = extend.get("sort", "favorite")

        # 构造基础 URL（根据时间范围）
        if time_range == "daily":
            url = f"{self.host}/{self.lang}/"
        elif time_range == "weekly":
            url = f"{self.host}/{self.lang}/weekly"
        elif time_range == "monthly":
            url = f"{self.host}/{self.lang}/monthly"
        else:  # all
            url = f"{self.host}/{self.lang}/all"

        # 添加排序和分页
        params = []
        if sort:
            params.append(f"sort={sort}")
        if pg > 1:
            params.append(f"page={pg}")
        if params:
            url += "?" + "&".join(params)

        self._log(f"分类请求: {url}")
        html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        videos = self._extract_videos(html)
        pagecount = self._get_pagecount(html)

        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount if pagecount >= pg else pg,
            "limit": 20,
            "total": pagecount * 20
        }

    def detailContent(self, ids):
        vid = ids[0] if ids else ""
        if not vid:
            return {"list": []}

        if vid.startswith("http"):
            url = vid
        else:
            if not vid.startswith("/"):
                url = f"{self.host}/{self.lang}/movie/{vid}"
            else:
                url = self._fix_url(vid)

        html = self._fetch(url)
        if not html:
            return {"list": []}

        title = ""
        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html)
        if title_match:
            title = title_match.group(1).strip()
        if not title:
            title_match = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', html)
            if title_match:
                title = title_match.group(1)
        if not title:
            title = vid

        pic = ""
        pic_match = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html)
        if pic_match:
            pic = pic_match.group(1)
        if not pic:
            pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*object-cover[^"]*"', html)
            if pic_match:
                pic = pic_match.group(1)
        pic = self._fix_url(pic)

        play_url = ""
        next_data = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
        if next_data:
            try:
                data = json.loads(next_data.group(1))
                def find_video_url(obj):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if key == 'url' and isinstance(value, str) and 'video.twimg.com' in value:
                                return value
                            result = find_video_url(value)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for item in obj:
                            result = find_video_url(item)
                            if result:
                                return result
                    return None
                play_url = find_video_url(data)
                if play_url:
                    self._log(f"从__NEXT_DATA__提取到视频: {play_url}")
            except Exception as e:
                pass

        if not play_url:
            mp4_match = re.search(r'(https://video\.twimg\.com/[^\s"\']+\.mp4[^\s"\']*)', html)
            if mp4_match:
                play_url = mp4_match.group(1)

        if not play_url:
            video_match = re.search(r'<video[^>]*src="([^"]+)"', html)
            if video_match:
                play_url = video_match.group(1)

        if play_url:
            play_url = f"播放${play_url}"
        else:
            play_url = f"网页播放${url}"

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": "",
                "vod_play_from": "PeKtino",
                "vod_play_url": play_url,
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        if not id:
            return {"parse": 0, "url": "", "header": {}}

        if id.startswith(("http://", "https://")):
            if ".mp4" in id or ".m3u8" in id:
                headers = {
                    "User-Agent": self.session.headers.get("User-Agent"),
                    "Accept": "video/mp4,video/webm,video/*;q=0.8,*/*;q=0.5",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                }
                if "video.twimg.com" in id:
                    headers["Referer"] = "https://x.com/"
                    headers["Origin"] = "https://x.com"
                else:
                    headers["Referer"] = self.host + "/"
                    headers["Origin"] = self.host
                return {"parse": 0, "url": id, "header": headers}
            html = self._fetch(id)
            if html:
                mp4_match = re.search(r'(https://video\.twimg\.com/[^\s"\']+\.mp4[^\s"\']*)', html)
                if mp4_match:
                    return {
                        "parse": 0,
                        "url": mp4_match.group(1),
                        "header": {
                            "User-Agent": self.session.headers.get("User-Agent"),
                            "Referer": "https://x.com/",
                            "Origin": "https://x.com",
                            "Accept": "video/mp4,video/webm,video/*;q=0.8,*/*;q=0.5",
                        }
                    }
            return {"parse": 1, "url": id, "header": {"Referer": self.host + "/"}}

        url = self._fix_url(id)
        if not url:
            return {"parse": 0, "url": "", "header": {}}

        return {
            "parse": 0,
            "url": url,
            "header": {
                "User-Agent": self.session.headers.get("User-Agent"),
                "Referer": self.host + "/",
                "Origin": self.host,
            }
        }

    def searchContent(self, key, quick=False, pg="1"):
        pg = int(pg) if pg else 1
        enc_key = quote(key)
        url = f"{self.host}/{self.lang}/search?q={enc_key}&page={pg}"
        html = self._fetch(url)
        if not html:
            url = f"{self.host}/{self.lang}/category/{enc_key}?page={pg}"
            html = self._fetch(url)
        if not html:
            return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}

        videos = self._extract_videos(html)
        pagecount = self._get_pagecount(html)
        return {
            "list": videos,
            "page": pg,
            "pagecount": pagecount if pagecount >= pg else pg,
            "limit": 20,
            "total": pagecount * 20
        }

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(ext in url.lower() for ext in ['.mp4', '.m3u8', '.ts'])

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self.session:
            self.session.close()

    def localProxy(self, param):
        return None