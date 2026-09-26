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
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.domains = [
            "https://chinaxmovie.com",
            "http://chinaxmovie.com"
        ]
        self.currentDomain = self.domains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

    def init(self, extend=""):
        return {}

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def _dict(self, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        return {}

    def _list(self, v):
        if isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                if isinstance(d, (list, tuple)):
                    return [str(i) for i in d]
            except Exception:
                pass
            return [str(v)]
        return []

    def _is_valid_html(self, html_text):
        if not html_text or len(html_text) < 300:
            return False
        block_keywords = ("发布页", "enter-link", "enter-maomi", "点击进入", "Just a moment...", "Attention Required")
        for kw in block_keywords:
            if kw in html_text:
                return False
        return True

    def _fetch_safe(self, path, referer="", headers_extra=None, raw_bytes=False):
        candidates = [self.currentDomain] + [d for d in self.domains if d != self.currentDomain]

        for domain in candidates:
            if path.startswith("http://") or path.startswith("https://"):
                target_url = path
            else:
                target_url = domain + path if path.startswith("/") else (domain + "/" + path)

            headers = {
                "User-Agent": self._ua,
                "Referer": referer if referer else (domain + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "close"
            }
            if headers_extra:
                headers.update(headers_extra)

            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    if code != 200:
                        continue

                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)

                    if raw_bytes:
                        return {"code": code, "bytes": raw, "text": "", "err": ""}

                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        try:
                            text = raw.decode("gbk")
                        except Exception:
                            text = raw.decode("latin1", errors="ignore")

                    if not (path.startswith("http://") or path.startswith("https://")):
                        if not self._is_valid_html(text):
                            continue

                    if not (path.startswith("http://") or path.startswith("https://")):
                        if domain != self.currentDomain:
                            self.currentDomain = domain

                    return {"code": code, "text": text, "bytes": raw, "err": ""}
            except Exception:
                continue

        return {"code": -1, "text": "", "bytes": b"", "err": "请求失败"}

    def _parse_cards(self, html_text):
        card_blocks = re.findall(r'(<div[^>]*class=["\'][^"\']*thumbnail\s+group[^"\']*["\'][^>]*>[\s\S]*?</div>\s*</div>\s*</div>)', html_text, re.I)
        if not card_blocks:
            card_blocks = re.findall(r'(<div[^>]*class=["\'][^"\']*thumbnail[^"\']*["\'][^>]*>[\s\S]*?</div>\s*</div>)', html_text, re.I)

        video_list = []
        seen_ids = set()

        for block in card_blocks:
            href_m = re.search(r'href=["\'](/vodplay/[a-zA-Z0-9_-]+)["\']', block, re.I)
            if not href_m:
                continue
            v_href = href_m.group(1).strip()
            if v_href in seen_ids:
                continue

            pic_url = ""
            pic_m = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', block, re.I)
            if pic_m:
                pic_url = pic_m.group(1).strip()
                if pic_url.startswith("//"):
                    pic_url = "https:" + pic_url
                elif pic_url.startswith("/"):
                    pic_url = self.currentDomain + pic_url

            clean_title = ""
            alt_m = re.search(r'<img[^>]+alt=["\']([^"\']+)["\']', block, re.I)
            if alt_m:
                clean_title = alt_m.group(1).strip()
            if not clean_title:
                text_m = re.search(r'<a[^>]*class=["\'][^"\']*text-secondary[^"\']*["\'][^>]*>([\s\S]*?)</a>', block, re.I)
                if text_m:
                    clean_title = re.sub(r'<[^>]+>', '', text_m.group(1)).strip()

            clean_title = re.sub(r'\s+', ' ', clean_title)
            if not clean_title or len(clean_title) <= 1:
                continue

            seen_ids.add(v_href)

            rem_m = re.search(r'<span[^>]*class=["\'][^"\']*(?:bottom-1|text-nord5|remarks|pic-text)[^"\']*["\'][^>]*>([\s\S]*?)</span>', block, re.I)
            remarks = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip() if rem_m else "高清"

            safe_id = "v_" + base64.urlsafe_b64encode(v_href.encode("utf-8")).decode("utf-8").rstrip("=")

            video_list.append({
                "vod_id": safe_id,
                "vod_name": clean_title,
                "vod_pic": pic_url,
                "vod_remarks": remarks
            })

        return video_list

    def homeContent(self, filter=False):
        classes = [
            {"type_name": "国产传媒", "type_id": "domestic-media"},
            {"type_name": "日本AV", "type_id": "japanese-av"},
            {"type_name": "无码视频", "type_id": "uncensored-videos"},
            {"type_name": "中文字幕", "type_id": "chinese-subtitles"}
        ]

        res = self._fetch_safe("/")
        rec_list = self._parse_cards(res.get("text", ""))

        return {
            "class": classes,
            "list": rec_list
        }

    def homeVideoContent(self):
        res = self._fetch_safe("/")
        return {"list": self._parse_cards(res.get("text", ""))}

    def categoryContent(self, tid, pg, filter=False, extend=None, *args, **kwargs):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        clean_slug = str(tid).strip("/").replace("vodtype/", "")

        if page_num == 1:
            target_path = "/vodtype/%s" % clean_slug
        else:
            target_path = "/vodtype/%s/page/%d/" % (clean_slug, page_num)

        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")
        vods = self._parse_cards(html_text)

        if not vods and page_num > 1:
            target_path_alt = "/vodtype/%s-%d.html" % (clean_slug, page_num)
            res_alt = self._fetch_safe(target_path_alt)
            vods = self._parse_cards(res_alt.get("text", ""))

        return {
            "page": page_num,
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": vods
        }

    def detailContent(self, ids):
        raw_id = self._list(ids)[0] if self._list(ids) else ""
        if not raw_id:
            return {"list": []}

        detail_path = ""
        if str(raw_id).startswith("v_"):
            try:
                b64_str = raw_id[2:]
                pad = len(b64_str) % 4
                if pad:
                    b64_str += "=" * (4 - pad)
                detail_path = base64.urlsafe_b64decode(b64_str.encode("utf-8")).decode("utf-8")
            except Exception:
                detail_path = str(raw_id)
        else:
            detail_path = str(raw_id)

        res = self._fetch_safe(detail_path)
        html_text = res.get("text", "")

        t_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html_text, re.I)
        vod_title = re.sub(r'<[^>]+>', '', t_m.group(1)).strip() if t_m else "精彩视频"

        final_stream = ""
        m = re.search(r'player_aaaa\s*=\s*\{.*?"url"\s*:\s*"([^"]+)".*?\}', html_text)
        if m:
            final_stream = m.group(1).replace("\\/", "/")

        if not final_stream or not (".m3u8" in final_stream or ".mp4" in final_stream):
            m2 = re.search(r'"url"\s*:\s*"(https?:\\/\\/[^"]+\.m3u8[^"]*)"', html_text)
            if m2:
                final_stream = m2.group(1).replace("\\/", "/")

        if not final_stream:
            box_m = re.search(r'<div[^>]*class=["\'][^"\']*stui-player__video[^"\']*["\'][^>]*>([\s\S]*?)</div>', html_text, re.I)
            if box_m:
                m3 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', box_m.group(1))
                if m3:
                    final_stream = m3.group(1)

        play_url_target = final_stream if final_stream else detail_path

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        vod_content = "%s\n\n%s\n\n【说明：本站持续为您搜集全网高清精彩视频，欢迎加入TG群获取最新资源！】" % (group_info, custom_notice)

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": vod_title,
                "vod_pic": "",
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清",
                "vod_content": vod_content,
                "vod_play_from": "官方专线",
                "vod_play_url": "正片$%s" % play_url_target
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()

        if not self.isVideoFormat(url):
            res = self._fetch_safe(url)
            html = res.get("text", "")
            m = re.search(r'"url"\s*:\s*"([^"]+)"', html)
            if m:
                clean_u = m.group(1).replace("\\/", "/")
                if ".m3u8" in clean_u or ".mp4" in clean_u:
                    url = clean_u

        play_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(play_headers)
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        if not key:
            return {"list": []}

        encoded_key = urllib.parse.quote(str(key))
        if page_num == 1:
            search_path = "/vodsearch/-------------.html?wd=%s" % encoded_key
        else:
            search_path = "/vodsearch/%s----------%d---.html" % (encoded_key, page_num)

        res = self._fetch_safe(search_path)
        vods = self._parse_cards(res.get("text", ""))

        return {
            "page": page_num,
            "pagecount": 99,
            "limit": 20,
            "total": 999,
            "list": vods
        }