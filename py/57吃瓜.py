# -*- coding: utf-8 -*-
"""
57吃瓜 (57chigua.co) - 蜂蜜影视原生 Python 蜘蛛
风格对齐 大师兄影视.py，内容结构对齐 57短剧（events + data-hls-src）
镜像: cigwan.cc / 57cg4.com
"""

import base64
import html as html_module
import json
import re
import time
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse

import requests

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def __init__(self):
            pass
        def getProxyUrl(self):
            return ""


class Spider(BaseSpider):
    DEFAULT_HOST = "https://57chigua.co"
    MIRRORS = [
        "https://57chigua.co",
        "https://cigwan.cc",
        "https://57cg4.com",
    ]
    DEFAULT_UA = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    IMG_REFERER = "https://57cg4.com/"

    CLASSES = [
        {"type_name": "全部", "type_id": "all"},
        {"type_name": "热门", "type_id": "hot"},
        {"type_name": "成人AI短剧", "type_id": "aichengduanju"},
        {"type_name": "今日吃瓜", "type_id": "jrcg"},
        {"type_name": "每日大赛", "type_id": "mrds"},
        {"type_name": "网红黑料", "type_id": "wanghong"},
        {"type_name": "网黄合集", "type_id": "video"},
        {"type_name": "出轨劈腿", "type_id": "cheating"},
        {"type_name": "直播擦边", "type_id": "live"},
        {"type_name": "社会事件", "type_id": "society"},
        {"type_name": "明星八卦", "type_id": "star"},
    ]

    FILTERS = {
        tid: [{
            "key": "sort",
            "name": "排序",
            "value": [
                {"n": "最新发布", "v": ""},
                {"n": "全站最热", "v": "hot"},
                {"n": "飙升热榜", "v": "trending"},
            ],
        }]
        for tid in (
            "all", "hot", "aichengduanju", "jrcg", "mrds",
            "wanghong", "video", "cheating", "live", "society", "star",
        )
    }

    MEDIA_EXTENSIONS = (".m3u8", ".mp4", ".mkv", ".flv", ".ts", ".webm")
    CF_SIGNS = ("just a moment", "checking your browser", "attention required")

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = self.DEFAULT_HOST
        self.ua = self.DEFAULT_UA
        self.cookie = ""
        self.timeout = 15
        self.use_cffi = False
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self.session = requests.Session()
        self.headers = {}
        self._refresh_headers()

    def init(self, extend=""):
        config = self._parse_extend(extend)
        raw_host = str(config.get("host") or self.DEFAULT_HOST).strip().rstrip("/")
        if raw_host.startswith("http"):
            self.host = raw_host
        self.ua = str(config.get("ua") or self.DEFAULT_UA).strip()
        self.cookie = str(config.get("cookie") or "").strip()
        self.timeout = self._safe_int(config.get("timeout"), 15, 5, 60)
        self.use_cffi = self._as_bool(config.get("use_cffi"), False)
        self.session = requests.Session()
        self._refresh_headers()
        return True

    def getName(self):
        return "57吃瓜"

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    @staticmethod
    def _safe_int(value, default, minimum=None, maximum=None):
        try:
            number = int(value)
        except (TypeError, ValueError):
            number = default
        if minimum is not None:
            number = max(minimum, number)
        if maximum is not None:
            number = min(maximum, number)
        return number

    @staticmethod
    def _as_bool(value, default=False):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on", "y", "是", "开启"}

    @staticmethod
    def _parse_extend(extend):
        if isinstance(extend, dict):
            return dict(extend)
        if not extend:
            return {}
        text = str(extend).strip()
        try:
            value = json.loads(text)
            return value if isinstance(value, dict) else {}
        except Exception:
            pass
        try:
            parsed = parse_qs(text, keep_blank_values=True)
            return {key: values[-1] for key, values in parsed.items()}
        except Exception:
            return {}

    def _refresh_headers(self):
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if self.cookie:
            self.headers["Cookie"] = self.cookie
        try:
            self.session.headers.clear()
            self.session.headers.update(self.headers)
        except Exception:
            pass

    def _request_raw(self, url, referer="", binary=False):
        if not url:
            return None
        target = self._absolute(url, referer or self.host)
        headers = dict(self.headers)
        if referer:
            headers["Referer"] = referer
        if binary:
            headers["Accept"] = "*/*"

        if self.use_cffi and cffi_requests is not None:
            try:
                response = cffi_requests.get(
                    target,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True,
                    impersonate="chrome131",
                )
                if getattr(response, "status_code", 200) < 400:
                    if not binary:
                        response.encoding = getattr(response, "apparent_encoding", None) or "utf-8"
                        if not self._is_cloudflare_text(response.text):
                            return response
                    else:
                        return response
            except Exception:
                pass

        for attempt in range(2):
            try:
                response = self.session.get(
                    target, headers=headers, timeout=self.timeout, allow_redirects=True
                )
                if getattr(response, "status_code", 200) >= 400:
                    raise RuntimeError("HTTP %s" % getattr(response, "status_code", 0))
                if not binary:
                    response.encoding = getattr(response, "apparent_encoding", None) or "utf-8"
                    if self._is_cloudflare_text(response.text):
                        raise RuntimeError("Cloudflare challenge")
                return response
            except Exception:
                if attempt == 0:
                    time.sleep(0.3)
        return None

    def _get_text(self, url, referer=""):
        response = self._request_raw(url, referer=referer, binary=False)
        if response is None:
            return ""
        try:
            text = response.text or ""
            return "" if self._is_cloudflare_text(text) else text
        except Exception:
            return ""

    def _get_text_multi(self, path, referer=""):
        """主域失败时轮询镜像"""
        path = path if path.startswith("/") else ("/" + path)
        hosts = [self.host] + [h for h in self.MIRRORS if h != self.host]
        for h in hosts:
            text = self._get_text(h + path, referer=referer or (h + "/"))
            if text and len(text) > 500:
                return text, h
        return "", self.host

    @classmethod
    def _is_cloudflare_text(cls, text):
        lower = (text or "")[:100000].lower()
        return any(sign in lower for sign in cls.CF_SIGNS)

    def _absolute(self, url, base):
        if not url:
            return ""
        value = html_module.unescape(str(url).strip()).replace("\\/", "/")
        if value.startswith("//"):
            return "https:" + value
        return urljoin(base, value)

    @staticmethod
    def _clean_text(value):
        if value is None:
            return ""
        text = html_module.unescape(str(value)).replace("\xa0", " ")
        text = re.sub(r"<script\b[^>]*>.*?</script>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip(" \t\r\n/|")

    def _wrap_pic(self, pic_url):
        if not pic_url:
            return ""
        pic = self._absolute(pic_url, self.host)
        if "s.chigua.media" in pic and "@" not in pic:
            return "%s@Referer=%s@User-Agent=%s" % (
                pic, self.IMG_REFERER, quote(self.ua)
            )
        return pic

    def _parse_card_list(self, html_text):
        vod_list = []
        seen = set()
        pattern = re.compile(
            r'<a[^>]+href=["\'](?:https?://[^/]+)?/events/(\d+)/?["\'][^>]*>([\s\S]*?)</a>',
            re.I,
        )
        matches = pattern.findall(html_text or "")
        if not matches:
            pattern2 = re.compile(
                r'<a[^>]+href=["\'](?:https?://[^/]+)?/(?:events/)?(\d+)/?["\'][^>]*>([\s\S]*?)</a>',
                re.I,
            )
            matches = pattern2.findall(html_text or "")

        for event_id, inner in matches:
            if event_id in seen or len(event_id) < 2:
                continue
            seen.add(event_id)
            m_t = re.search(r"<h[23][^>]*>([\s\S]*?)</h[23]>", inner, re.I)
            if m_t:
                name = self._clean_text(m_t.group(1))
            else:
                name = self._clean_text(inner)[:60] or ("吃瓜 %s" % event_id)
            pic = ""
            for src in re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', inner, re.I):
                if not src.endswith(".svg") and "logo" not in src and "favicon" not in src:
                    pic = src.strip()
                    break
            vod_list.append({
                "vod_id": event_id,
                "vod_name": name[:90],
                "vod_pic": self._wrap_pic(pic),
                "vod_remarks": "蝴蝶影视",
                "style": {"type": "rect", "ratio": 1.78},
            })
        return vod_list

    def homeContent(self, filter=False):
        result = {"class": list(self.CLASSES)}
        if filter:
            result["filters"] = self.FILTERS
        return result

    def homeVideoContent(self):
        res = self.categoryContent("aichengduanju", 1, False, {})
        return {"list": res.get("list", [])[:24]}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = self._safe_int(pg, 1, 1)
        slug = str(tid or "all").strip().replace("cat_", "")
        ext = extend or {}
        if isinstance(ext, str):
            try:
                ext = json.loads(ext)
            except Exception:
                ext = {}
        sort_val = str(ext.get("sort") or "").strip()

        if slug in ("all", "", "home"):
            path = "/" if page <= 1 else ("/page/%d/" % page)
        elif slug == "hot":
            path = "/hot/" if page <= 1 else ("/hot/%d/" % page)
        else:
            path = "/%s/" % slug if page <= 1 else ("/%s/%d/" % (slug, page))

        if sort_val:
            path += ("&sort=%s" if "?" in path else "?sort=%s") % quote(sort_val)

        html, used = self._get_text_multi(path, referer=self.host + "/")
        videos = self._parse_card_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page,
            "limit": len(videos) or 24,
            "total": 9999,
        }

    def searchContent(self, key, quick, pg="1"):
        page = self._safe_int(pg, 1, 1)
        keyword = quote(unquote(str(key or "").strip()), safe="")
        if not keyword:
            return {"list": [], "page": page, "pagecount": page, "limit": 0, "total": 0}
        path = "/search/?q=%s" % keyword
        if page > 1:
            path += "&page=%d" % page
        html, _ = self._get_text_multi(path)
        videos = self._parse_card_list(html)
        return {
            "list": videos,
            "page": page,
            "pagecount": page + 1 if len(videos) >= 10 else page,
            "limit": len(videos),
            "total": 9999,
        }

    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        event_id = str(raw_id or "").strip().strip("/")
        if not event_id:
            return {"list": []}

        path = "/events/%s/" % event_id
        html, used = self._get_text_multi(path, referer=self.host + "/")
        if not html or len(html) < 500:
            html = self._get_text(self.host + path, referer=self.host + "/")

        title = "吃瓜 %s" % event_id
        cover = ""
        desc = ""
        m = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", html or "", re.I)
        if m:
            title = self._clean_text(m.group(1)) or title
        m = re.search(
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)["\']',
            html or "",
            re.I,
        )
        if m:
            desc = m.group(1).strip()

        episodes = []
        # 1) video data-hls-src / src
        for attr in re.findall(r"<video([^>]+)>", html or "", re.I):
            m_hls = re.search(r'data-hls-src=["\']([^"\']+)["\']', attr, re.I)
            m_src = re.search(r'(?:data-fallback-src|src)=["\']([^"\']+)["\']', attr, re.I)
            stream = (m_hls.group(1) if m_hls else (m_src.group(1) if m_src else "")).strip()
            if not cover:
                m_post = re.search(r'poster=["\']([^"\']+)["\']', attr, re.I)
                if m_post:
                    cover = m_post.group(1).strip()
            if stream:
                episodes.append("片段 %02d$%s" % (len(episodes) + 1, stream))

        # 2) JSON-LD VideoObject
        if not episodes:
            for block in re.findall(
                r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
                html or "",
                re.I,
            ):
                if "VideoObject" not in block:
                    continue
                try:
                    data = json.loads(block)
                    v_list = data.get("video", [])
                    if isinstance(v_list, dict):
                        v_list = [v_list]
                    for v in v_list:
                        c_url = v.get("contentUrl") or ""
                        if c_url:
                            episodes.append("第 %02d 集$%s" % (len(episodes) + 1, c_url))
                            if not cover:
                                cover = v.get("thumbnailUrl") or cover
                except Exception:
                    pass

        # 3) 正则兜底
        if not episodes:
            seen = set()
            for m_url in re.findall(
                r'["\'](https?://[^"\'\s]+\.(?:m3u8|mp4)[^"\'\s]*)["\']', html or ""
            ):
                if m_url in seen:
                    continue
                seen.add(m_url)
                episodes.append("播放 %02d$%s" % (len(episodes) + 1, m_url))

        if not cover:
            m = re.search(
                r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
                html or "",
                re.I,
            )
            if m:
                cover = m.group(1).strip()

        full_desc = (
            "【🔥 官方交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "本贴解析到【%d】个视频片段\n\n%s"
        ) % (self.tgGroup, len(episodes), desc)

        play_url = "#".join(episodes) if episodes else ("无可用视频流$http://127.0.0.1")

        return {
            "list": [{
                "vod_id": event_id,
                "vod_name": title,
                "vod_pic": self._wrap_pic(cover),
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "共 %d 个片段" % len(episodes) if len(episodes) > 1 else "蝴蝶影视",
                "vod_content": full_desc,
                "vod_play_from": "57吃瓜在线",
                "vod_play_url": play_url,
            }]
        }

    def playerContent(self, flag, id, vipFlags=None):
        raw_url = str(id or "").strip()
        headers = {
            "User-Agent": self.ua,
            "Referer": self.IMG_REFERER,
            "Origin": self.IMG_REFERER.rstrip("/"),
        }
        if self.cookie:
            headers["Cookie"] = self.cookie
        return {
            "parse": 0,
            "jx": 0,
            "url": raw_url,
            "header": headers,
        }

    @classmethod
    def _is_media_url(cls, url):
        lower = html_module.unescape(str(url or "")).lower()
        return lower.startswith(("http://", "https://")) and any(
            ext in lower for ext in cls.MEDIA_EXTENSIONS
        )

    def isVideoFormat(self, url):
        return self._is_media_url(url)

    def manualVideoCheck(self):
        return False
