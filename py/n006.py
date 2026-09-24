#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
══════════════════════════════════════════════════════════════════
TVBox 官方适配爬虫：XSZAV 全功能影视源 (直连防盗链穿透版)
══════════════════════════════════════════════════════════════════
"""

import sys
import os
import re
import json
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
        def __init__(self):
            pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.siteUrl = "https://xsz-shared-proxy.97471201.workers.dev"
        self.rawSite = "https://tw.xszav2.com"
        self.tgGroup = "https://t.me/+3t5XRPPo9mlkZDRl"

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
        return True

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def _fetch(self, target_url):
        if not target_url:
            return ""

        if target_url.startswith(self.rawSite):
            target_url = target_url.replace(self.rawSite, self.siteUrl)

        parsed = urllib.parse.urlparse(target_url)
        headers = {
            "Host": parsed.netloc,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close"
        }

        def decode_stream(raw_bytes, enc):
            if not raw_bytes:
                return b""
            if raw_bytes.startswith(b"\x1f\x8b"):
                try:
                    return gzip.decompress(raw_bytes)
                except Exception:
                    return zlib.decompress(raw_bytes, 16 + zlib.MAX_WBITS)
            elif enc == "deflate":
                try:
                    return zlib.decompress(raw_bytes)
                except Exception:
                    pass
            return raw_bytes

        try:
            req = urllib.request.Request(target_url, headers=headers)
            with self.opener.open(req, timeout=15) as resp:
                data = decode_stream(resp.read(), resp.headers.get("Content-Encoding"))
                try:
                    return data.decode("utf-8")
                except Exception:
                    return data.decode("gbk", errors="ignore")
        except Exception:
            return ""

    def _fix_url(self, path):
        if not path:
            return ""
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if path.startswith("//"):
            return "https:" + path
        return self.siteUrl.rstrip("/") + "/" + path.lstrip("/")

    def homeContent(self, *args, **kwargs):
        classes = [
            {"type_name": "日本AV", "type_id": "/c/japanese"},
            {"type_name": "無碼流出", "type_id": "/c/uncensored-leak"},
            {"type_name": "素人影片", "type_id": "/c/amateur"},
            {"type_name": "無碼專區", "type_id": "/c/uncensored"},
            {"type_name": "XXX-AV", "type_id": "/tags/xxx-av"},
            {"type_name": "頑皮4610", "type_id": "/tags/naughty4610"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("/c/japanese", "1", None, {})

    def categoryContent(self, tid, pg, filter, extend):
        page_num = str(pg) if pg else "1"
        page_url = self._fix_url(tid)
        if page_num != "1":
            page_url = "%s?page=%s" % (page_url, page_num)

        html = self._fetch(page_url)
        cards = []

        pattern = r'<a[^>]+href=["\']([^"\']*/video/\d+)["\'][^>]*>([\s\S]*?)</a>'
        matches = re.findall(pattern, html, re.I)

        for href, inner in matches:
            img_m = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                continue
            pic_url = img_m.group(1).strip()
            if pic_url.startswith("data:image"):
                real_img_m = re.search(r'data-src=["\']([^"\']+)["\']', inner, re.I)
                if real_img_m:
                    pic_url = real_img_m.group(1).strip()
                else:
                    continue

            title = ""
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner, re.I)
            if alt_m and alt_m.group(1).strip():
                title = alt_m.group(1).strip()
            else:
                title_clean = re.sub(r'<[^>]+>', '', inner).strip()
                title = title_clean if title_clean else "XSZAV 影片"

            cards.append({
                "vod_id": self._fix_url(href),
                "vod_name": title,
                "vod_pic": pic_url,
                "vod_remarks": "高清原版"
            })

        return {
            "list": cards,
            "page": int(page_num) if page_num.isdigit() else 1,
            "pagecount": 999,
            "limit": len(cards),
            "total": 9999
        }

    def detailContent(self, ids):
        video_url = ids[0]
        html = self._fetch(video_url)

        title = "XSZAV 高清影片"
        title_m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I)
        if title_m:
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()

        pic = ""
        poster_m = re.search(r'poster=["\']([^"\']+)["\']', html, re.I)
        if poster_m:
            pic = poster_m.group(1).strip()

        # 直接提取 m3u8 真实地址
        m3u8_url = ""
        video_src_m = re.search(r'<video[^>]+src=["\']([^"\']+\.m3u8[^"\']*)["\']', html, re.I)
        if video_src_m:
            m3u8_url = video_src_m.group(1).strip()
        else:
            all_m3u8 = re.findall(r'["\'](https?://[^"\']+\.m3u8[^"\']*)["\']', html, re.I)
            if all_m3u8:
                m3u8_url = all_m3u8[0].strip()
            else:
                rel_m3u8 = re.findall(r'["\'](/media/videos/[^"\']+\.m3u8[^"\']*)["\']', html, re.I)
                if rel_m3u8:
                    m3u8_url = rel_m3u8[0].strip()

        final_play_url = self._fix_url(m3u8_url) if m3u8_url else ""

        play_list = []
        if final_play_url:
            play_list.append("默认原画$" + final_play_url)
            v_match = re.search(r'/media/videos/(v_[a-zA-Z0-9]+)\.m3u8', final_play_url)
            if v_match:
                v_id = v_match.group(1).replace("v_", "")
                play_list.append("1080p超清$https://v1.xsz2-cdn.com/v4/" + v_id + "_1080p/v.m3u8")
                play_list.append("720p高清$https://v1.xsz2-cdn.com/v4/" + v_id + "_720p/v.m3u8")

        play_url_str = "#".join(play_list) if play_list else "无播放源$http://127.0.0.1"
        brand_content = "【🔥官方交流群: %s】\nXSZAV 影视专线已稳定联通。" % self.tgGroup

        return {
            "list": [{
                "vod_id": video_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_actor": "📢 TG群: t.me/+3t5XRPPo9mlkZDRl",
                "vod_director": "ZakaTV",
                "vod_remarks": "直连播放",
                "vod_content": brand_content,
                "vod_play_from": "XSZAV-Direct",
                "vod_play_url": play_url_str
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        # 针对直连 CDN 播放时强制注入标准防盗链头
        return {
            "parse": 0,
            "url": id,
            "header": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Referer": "https://tw.xszav2.com/",
                "Origin": "https://tw.xszav2.com"
            }
        }

    def searchContent(self, key, quick, pg="1"):
        if not key:
            return {"list": []}
        page_num = str(pg) if pg else "1"
        encoded_key = urllib.parse.quote(key)
        search_url = "%s/search?q=%s&page=%s" % (self.siteUrl, encoded_key, page_num)

        html = self._fetch(search_url)
        cards = []

        pattern = r'<a[^>]+href=["\']([^"\']*/video/\d+)["\'][^>]*>([\s\S]*?)</a>'
        matches = re.findall(pattern, html, re.I)

        for href, inner in matches:
            img_m = re.search(r'<img[^>]+(?:data-src|src)=["\']([^"\']+)["\']', inner, re.I)
            if not img_m:
                continue
            pic_url = img_m.group(1).strip()
            if pic_url.startswith("data:image"):
                real_img_m = re.search(r'data-src=["\']([^"\']+)["\']', inner, re.I)
                if real_img_m:
                    pic_url = real_img_m.group(1).strip()
                else:
                    continue

            title = ""
            alt_m = re.search(r'alt=["\']([^"\']+)["\']', inner, re.I)
            if alt_m and alt_m.group(1).strip():
                title = alt_m.group(1).strip()
            else:
                title_clean = re.sub(r'<[^>]+>', '', inner).strip()
                title = title_clean if title_clean else key

            cards.append({
                "vod_id": self._fix_url(href),
                "vod_name": title,
                "vod_pic": pic_url,
                "vod_remarks": "搜索结果"
            })

        return {
            "list": cards,
            "page": int(page_num) if page_num.isdigit() else 1,
            "pagecount": 999,
            "limit": len(cards),
            "total": 9999
        }