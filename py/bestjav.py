#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
from urllib.parse import urlparse, quote, unquote
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key): return None
        def setCache(self, key, value): return "fail"
        def delCache(self, key): return "fail"

def format_remarks(brand="蝴蝶影视", meta=""):
    clean_meta = str(meta or "").strip()
    clean_meta = re.sub(r"[\r\n\t]+", " ", clean_meta).strip()
    if clean_meta:
        return "%s | %s" % (brand, clean_meta)
    return brand

class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://www.bestjavporn.com"
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        self.RC4_KEY_FALLBACK = b"1ETZmhTN4BzX5czN1gjN"
        self.options = {}

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.options = extend
        elif extend:
            try:
                self.options = json.loads(extend)
            except Exception:
                self.options = {}
        return True

    def getName(self):
        return "蝴蝶·BestJavPorn"

    # ================= 动态嗅探过滤器配置 =================
    def isVideoFormat(self, url):
        if not url:
            return False
        low = url.lower()
        # 严格过滤广告、统计与 5 秒预览样片
        if any(bad in low for bad in ("preview.mp4", "sample.mp4", "trailer.mp4", "top_banner", "55287.mp4", "native-ad", "stat.php")):
            return False
        return any(k in low for k in (".m3u8", ".mp4", "streamhls", "master.m3u8", ".flv", ".ts"))

    def manualVideoCheck(self):
        return False

    # ================= 核心双层 RC4 解密引擎 =================
    def _rc4(self, key, data):
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) & 255
            S[i], S[j] = S[j], S[i]
        i = j = 0
        out = bytearray()
        for ch in data:
            i = (i + 1) & 255
            j = (j + S[i]) & 255
            S[i], S[j] = S[j], S[i]
            out.append(ch ^ S[(S[i] + S[j]) & 255])
        return bytes(out)

    def _b64d(self, s):
        if isinstance(s, str):
            s = s.encode("utf-8")
        s = s.strip()
        pad = (-len(s)) % 4
        return base64.b64decode(s + (b"=" * pad))

    def _dec(self, b, key=None):
        try:
            k = key if key is not None else self.RC4_KEY_FALLBACK
            step1 = self._rc4(k, self._b64d(b))
            return self._b64d(step1).decode("utf-8", "replace")
        except Exception:
            return ""

    def _derive_key(self, postid):
        try:
            raw = ("%s_0x58fe15" % postid).encode("utf-8")
            return base64.b64encode(raw).decode("ascii")[::-1].encode("ascii")
        except Exception:
            return None

    def _postid(self, html):
        if not html:
            return None
        m = re.search(r'postid-(\d+)', html)
        if m:
            return m.group(1)
        m = re.search(r'<article[^>]*id="post-(\d+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<body[^>]*\bid="post-(\d+)"', html)
        if m:
            return m.group(1)
        return None

    # ================= 网络请求引擎 =================
    def _fetch(self, target_url, data=None, referer="", headers_custom=None):
        if not target_url:
            return {"code": 0, "text": "", "bytes": b"", "err": "", "final_url": ""}
        if target_url.startswith("//"):
            target_url = "https:" + target_url
        elif target_url.startswith("/"):
            target_url = self.siteUrl + target_url

        headers = {
            "User-Agent": self._ua,
            "Referer": referer if referer else (self.siteUrl + "/"),
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive"
        }
        if headers_custom:
            headers.update(headers_custom)

        req_data = None
        if data is not None:
            if isinstance(data, dict):
                req_data = urllib.parse.urlencode(data).encode("utf-8")
                headers["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
                headers["X-Requested-With"] = "XMLHttpRequest"
            elif isinstance(data, (bytes, str)):
                req_data = data.encode("utf-8") if isinstance(data, str) else data

        last_err = ""
        for attempt in range(2):
            try:
                req = urllib.request.Request(target_url, data=req_data, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    final_url = resp.geturl()
                    raw = resp.read()
                    enc = getattr(resp, "headers", {}).get("Content-Encoding", "")
                    if raw.startswith(b"\x1f\x8b") or enc == "gzip":
                        raw = gzip.decompress(raw)
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    return {"code": code, "text": text, "bytes": raw, "err": "", "final_url": final_url}
            except urllib.error.HTTPError as e:
                last_err = "HTTP %s" % e.code
                if e.code in (451, 403, 429) and attempt == 0:
                    continue
                err_raw = ""
                try:
                    err_raw = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass
                return {"code": e.code, "text": err_raw, "bytes": b"", "err": str(e), "final_url": target_url}
            except Exception as e:
                last_err = str(e)
                if attempt == 0:
                    continue
                return {"code": -1, "text": "", "bytes": b"", "err": str(e), "final_url": target_url}

        return {"code": -1, "text": "", "bytes": b"", "err": last_err, "final_url": target_url}

    def _clean_text(self, raw):
        t = re.sub(r'<[^>]+>', '', raw or '')
        try:
            t = html_lib.unescape(t)
        except Exception:
            pass
        return re.sub(r'[\r\n\t\s]+', ' ', t).strip()

    def homeContent(self, filter):
        result = {
            "class": [
                {"type_name": "有码专区", "type_id": "censored"},
                {"type_name": "无码专区", "type_id": "uncensored"},
                {"type_name": "中英字幕", "type_id": "subbed"},
                {"type_name": "素人专区", "type_id": "amateur"},
                {"type_name": "去码无码", "type_id": "decensored"},
                {"type_name": "分类大全", "type_id": "folder_categories"},
                {"type_name": "女优演员", "type_id": "folder_pornstars"},
                {"type_name": "制片厂商", "type_id": "folder_studios"}
            ]
        }
        if filter:
            result["filters"] = {
                "subbed": [
                    {
                        "key": "sub_lang",
                        "name": "字幕语言",
                        "init": "chinese",
                        "value": [
                            {"n": "中文字幕", "v": "chinese"},
                            {"n": "英文字幕", "v": "english"},
                            {"n": "印尼字幕", "v": "indo"}
                        ]
                    }
                ]
            }
        return result

    def homeVideoContent(self):
        return self.categoryContent("censored", 1, None, {})

    def _extract_real_img(self, chunk):
        for attr in ("data-lazy-src", "data-wpsrc", "data-original", "data-src"):
            m = re.search(r'\b%s=["\']([^"\']+)["\']' % attr, chunk, re.I)
            if m:
                val = m.group(1).strip()
                if val and not val.startswith("data:image/svg") and not val.endswith("/404.png"):
                    return val

        noscript_m = re.search(r'<noscript[^>]*>([\s\S]*?)</noscript>', chunk, re.I)
        if noscript_m:
            src_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', noscript_m.group(1), re.I)
            if src_m:
                val = src_m.group(1).strip()
                if val and not val.startswith("data:image/svg") and not val.endswith("/404.png"):
                    return val

        src_m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', chunk, re.I)
        if src_m:
            val = src_m.group(1).strip()
            if val and not val.startswith("data:image/svg") and not val.endswith("/404.png"):
                return val

        return ""

    def _wrap_img(self, img_url):
        if not img_url:
            return ""
        if not img_url.startswith("http"):
            img_url = urllib.parse.urljoin(self.siteUrl, img_url)
        return "%s@Referer=%s@User-Agent=%s" % (img_url, self.siteUrl + "/", quote(self._ua))

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        raw_target = str(tid).strip()

        is_sub_flow = False
        if raw_target.startswith("folder@@"):
            is_sub_flow = True
            base_url = raw_target.replace("folder@@", "")
            if page > 1:
                req_url = base_url.rstrip("/") + ("/page/%d/" % page)
            else:
                req_url = base_url
        else:
            route_map = {
                "censored": "/category/censored/",
                "uncensored": "/category/uncensored/",
                "amateur": "/category/amateur/",
                "decensored": "/category/decensored/",
                "folder_categories": "/categories/",
                "folder_pornstars": "/pornstars/",
                "folder_studios": "/studios/"
            }

            if raw_target == "subbed":
                lang = (extend or {}).get("sub_lang", "chinese")
                if lang == "chinese":
                    base_path = "/category/chinese-subtitle/"
                elif lang == "indo":
                    base_path = "/category/subtitle-indonesia/"
                else:
                    base_path = "/category/censored/english-subtitle/"
            elif raw_target in route_map:
                base_path = route_map[raw_target]
            else:
                base_path = raw_target if raw_target.startswith("/") else ("/" + raw_target)
                if not base_path.endswith("/"):
                    base_path += "/"

            if page > 1:
                req_url = self.siteUrl + ("%spage/%d/" % (base_path.rstrip("/") + "/", page))
            else:
                req_url = self.siteUrl + base_path

        res = self._fetch(req_url)
        html = res.get("text", "")
        if not html:
            return {"page": page, "pagecount": 1, "limit": 0, "total": 0, "list": []}

        scoped_html = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', html, flags=re.I)
        scoped_html = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', scoped_html, flags=re.I)
        scoped_html = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', scoped_html, flags=re.I)

        is_first_level_folder = (not is_sub_flow) and (raw_target in ("folder_categories", "folder_pornstars", "folder_studios") or any(k in req_url for k in ("/categories/", "/pornstars/", "/studios/")))

        chunks = []
        for split_key in ('class="thumb', 'class="post-', 'class="video-block', 'class="item'):
            parts = scoped_html.split(split_key)
            if len(parts) > 2:
                chunks = parts[1:]
                break

        if not chunks:
            chunks = re.findall(r'(<(?:div|article|li)[^>]*(?:item|video|thumb|post)[^>]*>[\s\S]*?</(?:div|article|li)>)', scoped_html, re.I)

        video_list = []
        for chunk in chunks:
            link_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']+)["\']', chunk, re.I)
            if not link_m:
                link_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', chunk, re.I)
            if not link_m:
                continue

            href = link_m.group(1).strip()
            title = self._clean_text(link_m.group(2))
            if not href or href.startswith("javascript:") or href in ("#", "/"):
                continue

            full_href = href if href.startswith("http") else urllib.parse.urljoin(self.siteUrl, href)
            raw_pic = self._extract_real_img(chunk)
            wrapped_pic = self._wrap_img(raw_pic)

            dur_m = re.search(r'class="duration"[^>]*>[\s\S]*?</i>\s*([0-9:]+)', chunk, re.I)
            if not dur_m:
                dur_m = re.search(r'(?:duration|time|badge)[^>]*>([\s\S]*?)</', chunk, re.I)
            duration = self._clean_text(dur_m.group(1)) if dur_m else ""

            if is_first_level_folder:
                is_actor = "pornstar" in req_url
                card = {
                    "vod_id": "folder@@" + full_href,
                    "vod_name": title or "未知目录",
                    "vod_pic": wrapped_pic,
                    "vod_remarks": format_remarks("蝴蝶影视", "作品集"),
                    "vod_tag": "folder",
                    "style": {"type": "oval" if is_actor else "rect", "ratio": 1.0 if is_actor else 1.78}
                }
            else:
                card = {
                    "vod_id": full_href,
                    "vod_name": title or "未知片目",
                    "vod_pic": wrapped_pic,
                    "vod_remarks": format_remarks("蝴蝶影视", duration),
                    "style": {"type": "rect", "ratio": 1.78}
                }
            video_list.append(card)

        has_next = ('page/%d/' % (page + 1)) in scoped_html
        pagecount = (page + 1) if has_next else page

        return {
            "page": page,
            "pagecount": max(pagecount, 1),
            "limit": len(video_list),
            "total": 9999 if has_next else len(video_list),
            "list": video_list
        }

    def _line_label(self, lo):
        m = {"mp": "MP专线", "us": "US专线", "fr": "FR专线", "my": "MY专线",
             "nl3": "NL专线", "de3": "DE专线", "de": "DE专线", "nl": "NL专线"}
        return "蝴蝶·" + m.get(lo, str(lo).upper())

    # ================= 详情页：逆向推导并列出完整线路 =================
    def detailContent(self, ids):
        raw_id = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        target_url = str(raw_id)

        if target_url.startswith("folder@@"):
            return self.categoryContent(target_url, 1, None, {})

        res = self._fetch(target_url)
        html = res.get("text", "")

        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        title = self._clean_text(title_m.group(1)) if title_m else "正片详情"

        raw_cover = self._extract_real_img(html)
        cover = self._wrap_img(raw_cover)

        dur_m = re.search(r'itemprop="duration"\s+content="P0DT([^"]+)"', html)
        dur_str = dur_m.group(1).lower() if dur_m else "完整正片"

        from_list = ["蝴蝶·主专线"]
        url_list = ["正片$" + target_url + "@@main"]

        # 🌟 核心逆向：解出 data-mpu 换取全部备用正片线路
        mpu_m = re.search(r'data-mpu=["\']([^"\']+)["\']', html)
        if mpu_m:
            postid = self._postid(html)
            key = self._derive_key(postid)
            token = self._dec(mpu_m.group(1), key)
            if token:
                api_url = self.siteUrl + "/api/play/"
                api_res = self._fetch(api_url, data={"sources": token, "ver": "2"}, referer=target_url)
                api_text = api_res.get("text", "")
                try:
                    j = json.loads(api_text)
                    if j.get("status"):
                        reserve_str = self._dec(j.get("reserve", ""), key)
                        if reserve_str:
                            arr = json.loads(reserve_str)
                            for e in arr:
                                lo = e.get("lo")
                                if lo:
                                    from_list.append(self._line_label(lo))
                                    url_list.append("正片$" + target_url + "@@" + str(lo))
                except Exception:
                    pass

        intro = (
            "【🔥 蝴蝶影视交流群: %s】\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "• 影片标题: %s\n"
            "• 官方正片时长: %s\n"
            "• 播放通道: 蝴蝶多线路专线 (已彻底穿透样片鉴权，支持原生极速硬解)"
        ) % (self.tgGroup, title, dur_str)

        return {
            "list": [{
                "vod_id": target_url,
                "vod_name": title,
                "vod_pic": cover,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "蝴蝶影视",
                "vod_content": intro.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                "vod_play_from": "$$$".join(from_list),
                "vod_play_url": "$$$".join(url_list)
            }]
        }

    # ================= 播放解析：解密嵌入页并移交 TVBox 原生嗅探 =================
    def playerContent(self, flag, id, vipFlags):
        raw_target = str(id).strip()
        target_page = raw_target
        linekey = "main"

        if "@@" in raw_target:
            parts = raw_target.split("@@", 1)
            target_page = parts[0]
            linekey = parts[1] if len(parts) > 1 else "main"

        play_page_url = ""
        # 1. 现场从详情页动态拉取 Token（保证请求时效性）
        res = self._fetch(target_page)
        html = res.get("text", "")
        mpu_m = re.search(r'data-mpu=["\']([^"\']+)["\']', html)

        if mpu_m:
            postid = self._postid(html)
            key = self._derive_key(postid)
            token = self._dec(mpu_m.group(1), key)
            if token:
                api_url = self.siteUrl + "/api/play/"
                api_res = self._fetch(api_url, data={"sources": token, "ver": "2"}, referer=target_page)
                try:
                    j = json.loads(api_res.get("text", ""))
                    if j.get("status"):
                        if linekey == "main":
                            play_page_url = self._dec(j.get("data", ""), key)
                        else:
                            reserve_str = self._dec(j.get("reserve", ""), key)
                            if reserve_str:
                                arr = json.loads(reserve_str)
                                for e in arr:
                                    if str(e.get("lo")) == linekey:
                                        play_page_url = self._dec(e.get("data", ""), key)
                                        break
                            if not play_page_url:
                                play_page_url = self._dec(j.get("data", ""), key)
                except Exception:
                    pass

        # 2. 格式化嵌入页面地址
        if play_page_url:
            play_page_url = play_page_url.strip()
            if play_page_url.startswith("//"):
                play_page_url = "https:" + play_page_url
        else:
            play_page_url = target_page

        # 3. 构造防盗链头，通知 TVBox 嗅探器启动
        headers = {
            "User-Agent": self._ua,
            "Referer": self.siteUrl + "/"
        }

        return {
            "parse": 1,          # 🌟 方案 B 核心：1 代表移交客户端底层 WebView 自动嗅探
            "playUrl": "",
            "url": play_page_url,
            "header": headers
        }

    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        query_kw = quote(str(key).strip())
        search_path = "/page/%d/?s=%s" % (page, query_kw) if page > 1 else "/?s=%s" % query_kw
        return self.categoryContent(search_path, page, None, {})

    def localProxy(self, params):
        url = params.get("url", "")
        if not url:
            return [404, "text/plain; charset=utf-8", "Missing url parameter"]
        res = self._fetch(url, referer=self.siteUrl + "/")
        raw_b = res.get("bytes", b"")
        mime = "image/jpeg"
        if raw_b.startswith(b"\x89PNG"):
            mime = "image/png"
        elif raw_b.startswith(b"GIF8"):
            mime = "image/gif"
        elif raw_b.startswith(b"RIFF"):
            mime = "image/webp"
        return [res.get("code", 200), mime, raw_b]

    def action(self, action):
        return {"msg": "ok"}

    def liveContent(self):
        return ""

    def destroy(self):
        self.options = {}