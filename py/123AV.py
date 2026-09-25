#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
123AV 插件(加固版) · 站点 123av.app
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
· 分类 / 搜索 / 演员·类型·制作商索引 / 详情 / 播放 全链路
· 列表解析:先定位每张卡片再取值,字段顺序变了也不会空
· 网络:强制 IPv4(防真机 IPv6 干等) + 自动重试 + 域名自动探活 + 可选代理
· 自检:壳里搜关键词  diag  就能看到实时诊断结果
· 纯标准库 · 无推广 · 无密码 · 无账号
配置(写进源的 extend 里即可):
    {"host": "https://123av.app", "proxy": "http://127.0.0.1:7890"}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
import re
import json
import time
import base64
import gzip
import zlib
import ssl
import socket
import html as html_lib
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        def getCache(self, key):
            return None

        def setCache(self, key, value):
            return "fail"

        def delCache(self, key):
            return "fail"


# ── 强制走 IPv4:真机上 IPv6 常常连不上还傻等,超时后分类就空了 ──
try:
    if not getattr(socket, "_zaka_v4only", False):
        _orig_gai = socket.getaddrinfo

        def _gai_v4(host, port, family=0, type=0, proto=0, flags=0):
            try:
                return _orig_gai(host, port, socket.AF_INET, type, proto, flags)
            except Exception:
                return _orig_gai(host, port, family, type, proto, flags)

        socket.getaddrinfo = _gai_v4
        socket._zaka_v4only = True
except Exception:
    pass


DEFAULT_HOST = "https://123av.app"
DEFAULT_EMBED = "https://emb2.sin-suckol-o5.asia"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")

# 卡片定位:兼容 RSC 转义形(\"videoCode\":\"x\") 与普通形("videoCode":"x")
RE_CODE = re.compile(r'\\?"videoCode\\?"\s*:\s*\\?"([A-Za-z0-9\-_]{2,48})')
RE_EMBED = re.compile(r'\\?"embedUrl\\?"\s*:\s*\\?"(https?://[^"\\]{6,300})')
RE_OGIMG = re.compile(r'<meta[^>]+property="og:image"[^>]+content="([^"]{6,400})"', re.I)
RE_OGTITLE = re.compile(r'<meta[^>]+property="og:title"[^>]+content="([^"]{1,200})"', re.I)
RE_TITLE = re.compile(r"<title>([^<]{1,200})</title>", re.I)
RE_ANCHOR = re.compile(r'<a[^>]+href="([^"]{1,300})"[^>]*>(.{0,1200}?)</a>', re.S)
RE_IDX_NAME = re.compile(r'<p[^>]*class="[^"]*text-amber-200[^"]*"[^>]*>([^<]{1,80})</p>')
RE_IDX_CNT = re.compile(r'<p[^>]*class="[^"]*text-blue-300[^"]*"[^>]*>([^<]{1,80})</p>')
RE_PAGES = re.compile(r'\\?"pages\\?"\s*:\s*\[(.{0,8000}?)\]')
RE_PAGENUM = re.compile(r'\\?"page\\?"\s*:\s*\\?"(\d{1,5})')
# 第三方播放页:聚合站自己不给流时,真实直链藏在这一页的播放配置里
RE_PLAYERCFG = re.compile(r'window\.PLAYER_CONFIG\s*=\s*(\{.{0,30000}?\})\s*;', re.S)
RE_ANY_M3U8 = re.compile(r'(https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*)')
# 聚合站拼播放地址时会把分类后缀一起带进去,源站上的片名往往不带,得逐层剥了再试
SLUG_SUFFIXES = ("-chinese-subtitle", "-english-subtitle", "-uncensored-leak",
                 "-uncensored", "-chinese", "-subtitle", "-leak", "-c")
RE_STREAM = re.compile(r'(https?://[^"\'\s\\]+\.(?:m3u8|mp4)[^"\'\s\\]*)')

INDEX_SLUGS = ("cn/actresses", "cn/genres", "cn/makers", "cn/series")

CLASSES = [
    {"type_name": "🔥 最近更新", "type_id": "cn/new"},
    {"type_name": "🆕 新发布", "type_id": "cn/release"},
    {"type_name": "🔥 最热", "type_id": "cn/hot"},
    {"type_name": "📈 今日热门", "type_id": "cn/today-hot"},
    {"type_name": "📉 本月热门", "type_id": "cn/monthly-hot"},
    {"type_name": "📊 本周趋势", "type_id": "cn/all?sort=week"},
    {"type_name": "💎 无码", "type_id": "cn/uncensored"},
    {"type_name": "🕵️ 无码泄露", "type_id": "cn/uncensored-leak"},
    {"type_name": "🇨🇳 中文字幕", "type_id": "cn/chinese-subtitle"},
    {"type_name": "🥽 VR", "type_id": "cn/VR"},
    {"type_name": "💃 女演员", "type_id": "folder/cn/actresses"},
    {"type_name": "🏷️ 类型", "type_id": "folder/cn/genres"},
    {"type_name": "🏢 制作商", "type_id": "folder/cn/makers"},
    {"type_name": "🔗 MissAV 站", "type_id": "cn/site/missav"},
    {"type_name": "🔗 nJAV 站", "type_id": "cn/site/njav"},
    {"type_name": "🔗 ThisAV 站", "type_id": "cn/site/thisav"},
    {"type_name": "🔗 Supjav 站", "type_id": "cn/site/supjav"},
    {"type_name": "SIRO", "type_id": "cn/siro"},
    {"type_name": "LUXU", "type_id": "cn/luxu"},
    {"type_name": "GANA", "type_id": "cn/gana"},
    {"type_name": "FC2", "type_id": "cn/fc2"},
    {"type_name": "FC2-PPV", "type_id": "cn/fc2-ppv"},
    {"type_name": "HEYZO", "type_id": "cn/heyzo"},
    {"type_name": "1Pondo", "type_id": "cn/1pondo"},
    {"type_name": "Caribbeancom", "type_id": "cn/caribbeancom"},
    {"type_name": "10musume", "type_id": "cn/10musume"},
    {"type_name": "Pacopacomama", "type_id": "cn/pacopacomama"},
    {"type_name": "XXX-AV", "type_id": "cn/xxx-av"},
]


class Spider(SpiderBase):
    def __init__(self):
        try:
            super(Spider, self).__init__()
        except Exception:
            pass
        self.host = DEFAULT_HOST
        self.embed = DEFAULT_EMBED
        self.ua = UA
        self.timeout = 10
        self.host_ok = False
        self.diag = []
        self._play_cache = {}
        self.cj = http.cookiejar.CookieJar()
        self.ctx = ssl.create_default_context()
        try:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE
        except Exception:
            pass
        self.handlers = [urllib.request.HTTPCookieProcessor(self.cj)]
        try:
            self.handlers.append(urllib.request.HTTPSHandler(context=self.ctx))
        except Exception:
            pass
        self._build_opener()

    def _build_opener(self, proxy=""):
        hs = list(self.handlers)
        if proxy:
            hs.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
        try:
            self.opener = urllib.request.build_opener(*hs)
        except Exception:
            self.opener = urllib.request.build_opener(*self.handlers)

    # ───────────────────────── 入口 / 配置 ─────────────────────────

    def init(self, extend=""):
        opts = {}
        if isinstance(extend, dict):
            opts = extend
        elif isinstance(extend, str) and extend.strip():
            try:
                opts = json.loads(extend)
            except Exception:
                opts = {}
        if opts.get("host"):
            self.host = str(opts["host"]).rstrip("/")
            self.host_ok = False
        if opts.get("embed"):
            self.embed = str(opts["embed"]).rstrip("/")
        if opts.get("proxy"):
            self._build_opener(str(opts["proxy"]).strip())
        if opts.get("timeout"):
            try:
                self.timeout = max(4, min(30, int(opts["timeout"])))
            except Exception:
                pass
        return True

    def setExtendInfo(self, extend=""):
        return self.init(extend)

    def getName(self):
        return "123AV"

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".mpd", ".ts"))

    def manualVideoCheck(self):
        return False

    # ───────────────────────── 网络 ─────────────────────────

    def _note(self, msg):
        try:
            self.diag.append(str(msg)[:220])
            if len(self.diag) > 40:
                self.diag = self.diag[-40:]
        except Exception:
            pass

    def _fetch(self, url, referer="", timeout=None):
        if not url:
            return 0, ""
        if url.startswith("//"):
            url = "https:" + url
        headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        if referer:
            headers["Referer"] = referer
        last_err = ""
        for attempt in range(2):
            t0 = time.time()
            try:
                req = urllib.request.Request(url, headers=headers)
                with self.opener.open(req, timeout=timeout or self.timeout) as resp:
                    code = resp.getcode()
                    raw = resp.read()
                    enc = ""
                    try:
                        enc = (resp.headers.get("Content-Encoding", "") or "").lower()
                    except Exception:
                        pass
                    if raw[:2] == b"\x1f\x8b" or enc == "gzip":
                        try:
                            raw = gzip.decompress(raw)
                        except Exception:
                            pass
                    elif enc == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            try:
                                raw = zlib.decompress(raw, -zlib.MAX_WBITS)
                            except Exception:
                                pass
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        text = raw.decode("latin1", errors="ignore")
                    if code in (403, 429) or ("Just a moment" in text[:4000]) or ("cf-chl" in text[:4000]):
                        self._note("被站点防护拦截 HTTP %s" % code)
                    self._note("GET %s -> %s %dB %.1fs" % (url[:110], code, len(text), time.time() - t0))
                    return code, text
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    body = ""
                self._note("HTTP %s %s %dB" % (e.code, url[:100], len(body)))
                if e.code in (429, 503) and attempt < 1:
                    time.sleep(0.8)
                    continue
                return e.code, body
            except Exception as e:
                last_err = "%s: %s" % (type(e).__name__, str(e)[:110])
                self._note("失败 %s | %s" % (url[:100], last_err))
                if attempt < 1:
                    time.sleep(0.5)
        return -1, ""

    def _plain(self, html):
        if not html:
            return ""
        t = html.replace('\\"', '"').replace("\\/", "/")
        t = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)
        return t

    def _ensure_host(self):
        """首次调用时探一遍可用域名,避免写死的域名一挂整条源就废"""
        if self.host_ok:
            return
        pool = []
        for h in (self.host, DEFAULT_HOST, "https://www.123av.app"):
            h = (h or "").rstrip("/")
            if h and h not in pool:
                pool.append(h)
        for h in pool:
            try:
                code, html = self._fetch(h + "/cn/new", referer=h + "/cn", timeout=8)
            except Exception:
                code, html = -1, ""
            if code == 200 and ("videoCode" in html or "video_code" in html):
                self.host = h
                self.host_ok = True
                self._note("域名可用: %s" % h)
                return
            self._note("域名探测失败: %s (HTTP %s)" % (h, code))

    # ───────────────────────── 解析 ─────────────────────────

    def _field(self, win, key):
        m = re.search(r'\\?"%s\\?"\s*:\s*\\?"((?:[^"\\]|\\.){0,500}?)\\?"' % key, win)
        if not m:
            return ""
        v = m.group(1)
        v = v.replace("\\n", " ").replace("\\t", " ").replace("\\/", "/")
        v = v.replace('\\"', '"').replace("\\\\", "\\")
        try:
            v = re.sub(r"\\u([0-9a-fA-F]{4})", lambda x: chr(int(x.group(1), 16)), v)
        except Exception:
            pass
        v = html_lib.unescape(v)
        return re.sub(r"\s+", " ", v).strip()

    def _cards(self, text):
        """定位每张卡片的位置,再在它自己的区间里取字段 —— 不怕字段顺序/相邻字段变化"""
        if not text:
            return []
        marks = [(m.start(), m.group(1)) for m in RE_CODE.finditer(text)]
        if not marks:
            return []
        items = []
        seen = set()
        for i, (pos, code) in enumerate(marks):
            if code in seen:
                continue
            end = marks[i + 1][0] if i + 1 < len(marks) else pos + 3000
            win = text[pos:max(end, pos + 300)]
            title = self._field(win, "videoTitle")
            if not title:
                title = self._field(win, "title")
            if not title:
                continue
            pic = self._field(win, "imageUrl") or self._field(win, "image") or self._field(win, "thumbnail")
            dur = self._field(win, "duration")
            seen.add(code)
            items.append(self._vod(code, title, pic, dur))
        return items

    def _video_list(self, html):
        if not html:
            return []
        items = []
        for blob in (html, self._plain(html)):
            got = self._cards(blob)
            if got:
                have = set(x["vod_id"] for x in items)
                for it in got:
                    if it["vod_id"] not in have:
                        items.append(it)
                        have.add(it["vod_id"])
                if len(items) >= 10:
                    break
        return items

    def _fetch_items(self, url, referer=""):
        """列表请求:偶发空响应(限流/骨架页)自动补一次,别让用户看到空列表"""
        html = ""
        for attempt in range(2):
            code, html = self._fetch(url, referer=referer)
            items = self._video_list(html) if code == 200 else []
            if items:
                return items, html
            if attempt == 0:
                time.sleep(0.6)
        return [], html

    def _pagecount(self, text, page):
        for blob in (text, self._plain(text)):
            m = RE_PAGES.search(blob)
            if m:
                nums = [int(x) for x in RE_PAGENUM.findall(m.group(1))]
                nums = [n for n in nums if n > 0]
                if nums:
                    return max(nums)
        return 999

    def _vod(self, code, title, image, dur):
        name = re.sub(r"\s+", " ", (title or "").strip())
        d = re.sub(r"\s+", " ", (dur or "").strip())
        if image:
            image = image.replace("\\/", "/")
            if image.startswith("//"):
                image = "https:" + image
            elif image.startswith("/"):
                image = self.host + image
        return {
            "vod_id": code,
            "vod_name": name or code.upper(),
            "vod_pic": image or "",
            "vod_remarks": d if d and d not in ("0:00", "0") else "HD",
            "style": {"type": "rect", "ratio": 1.78},
        }

    def _card(self, text):
        ch = (text or "A").strip()[:1]
        pal = ["19bcd4", "5b6ac8", "26a69a", "9b59b6", "ff3b6f", "8ec051", "ffbe1a", "3498db", "e91e63"]
        idx = sum(ord(c) for c in (text or "A")) % len(pal)
        return "https://dummyimage.com/640x360/%s/ffffff.png&text=%s" % (pal[idx], urllib.parse.quote(ch))

    # ───────────────────────── 首页 / 分类 ─────────────────────────

    def homeContent(self, filter):
        if not self.diag:
            try:
                self._ensure_host()
            except Exception:
                pass
        return {"class": list(CLASSES)}

    def homeVideoContent(self):
        try:
            self._ensure_host()
            code, html = self._fetch(self.host + "/cn/new", referer=self.host + "/cn")
            if code == 200:
                return {"list": self._video_list(html)}
        except Exception:
            pass
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        raw = str(tid or "").strip()
        is_folder = raw.startswith("folder/")
        slug = raw[7:].strip("/") if is_folder else raw.strip("/")
        if not slug:
            return self._empty(page)
        # 去掉可能的协议头/域名残留
        slug = re.sub(r"^https?://[^/]+/", "", slug)
        slug = urllib.parse.quote(slug, safe="/%:?=&+")
        try:
            self._ensure_host()
            if is_folder or slug.split("?", 1)[0] in INDEX_SLUGS:
                return self._index_content(slug, page)
            url = self.host + "/" + slug
            if page > 1:
                url = url + ("&page=%d" % page if "?" in url else "?page=%d" % page)
            items, html = self._fetch_items(url, referer=self.host + "/cn")
            pc = self._pagecount(html, page) if items else page
            self._note("分类 %s p%s -> %s 条" % (slug[:40], page, len(items)))
            return {
                "page": page,
                "pagecount": pc if pc > 0 else 1,
                "limit": len(items) or 24,
                "total": 999999,
                "list": items,
            }
        except Exception as e:
            self._note("分类异常 %s" % (str(e)[:120]))
            return self._empty(page)

    def _empty(self, page):
        return {"page": page, "pagecount": 1, "limit": 24, "total": 0, "list": []}

    def _index_content(self, slug, page):
        url = "%s/%s" % (self.host, slug.strip("/"))
        if page > 1:
            url = url + "?page=%d" % page
        items = []
        pc = page
        plain = ""
        for attempt in range(2):
            code, html = self._fetch(url, referer=self.host + "/cn")
            if code == 200:
                plain = self._plain(html)
                items = self._cards(plain) or self._cards(html) or self._index_items(html)
                if items:
                    pc = self._pagecount(plain, page)
                    break
            if attempt == 0:
                time.sleep(0.6)
        self._note("索引 %s p%s -> %s 条" % (slug[:40], page, len(items)))
        return {
            "page": page,
            "pagecount": pc if pc > 0 else 1,
            "limit": len(items) or 24,
            "total": 999999,
            "list": items,
        }

    def _index_items(self, html):
        items = []
        seen = set()
        for href, inner in RE_ANCHOR.findall(html or ""):
            if "text-amber-200" not in inner:
                continue
            path = html_lib.unescape(href.split("#")[0]).strip()
            path = path.split("?")[0].replace("\\/", "/")
            if path.startswith("http"):
                path = re.sub(r"^https?://[^/]+/", "", path)
            if path.startswith("/"):
                path = path[1:]
            if not path.startswith("cn/"):
                path = "cn/" + path.lstrip("./")
            if not re.match(r"^cn/(actresses|genres|makers|series)/", path):
                continue
            if path.rstrip("/").endswith("/ranking") or path in seen:
                continue
            nm = RE_IDX_NAME.search(inner)
            if not nm:
                continue
            name = re.sub(r"\s+", " ", html_lib.unescape(nm.group(1))).strip()
            if not name:
                continue
            cn = RE_IDX_CNT.search(inner)
            badge = re.sub(r"\s+", " ", html_lib.unescape(cn.group(1))).strip() if cn else "点开查看"
            seen.add(path)
            items.append({
                "vod_id": "folder/" + path,
                "vod_name": name,
                "vod_pic": self._card(name),
                "vod_remarks": badge,
                "vod_tag": "folder",
                "style": {"type": "oval", "ratio": 1.0} if "actresses" in path
                         else {"type": "rect", "ratio": 1.78},
            })
        return items

    # ───────────────────────── 详情 / 播放 ─────────────────────────

    def _detail_page(self, code_id):
        c, html = self._fetch("%s/cn/%s" % (self.host, code_id), referer=self.host + "/cn")
        return (html if c == 200 else "")

    def _embed_of(self, code_id):
        html = self._detail_page(code_id)
        if not html:
            return ""
        for blob in (self._plain(html), html):
            m = RE_EMBED.search(blob)
            if m:
                return m.group(1).replace("\\/", "/")
        return ""

    def _resolve(self, embed_url):
        m = re.match(r"^(https?://[^/]+)/video/(.+?)/?$", embed_url or "")
        if not m:
            return {}
        origin, vid = m.group(1), m.group(2)
        code, text = self._fetch("%s/video/%s/resolve" % (origin, vid), referer=embed_url, timeout=10)
        if code != 200 or not text.strip().startswith("{"):
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _decode_stream(self, data, embed_url):
        if not data:
            return ""
        stream = ""
        obf = data.get("obfuscatedUrl")
        key = data.get("xorKey")
        if obf and key:
            try:
                e = str(obf).replace("-", "+").replace("_", "/")
                e += "=" * (-len(e) % 4)
                b = base64.b64decode(e)
                k = str(key)
                stream = "".join(chr(b[i] ^ ord(k[i % len(k)])) for i in range(len(b)))
            except Exception:
                stream = ""
        if not stream:
            stream = str(data.get("hlsUrl") or data.get("url") or "")
        if not stream:
            return ""
        if not stream.startswith("http"):
            root = re.match(r"^(https?://[^/]+)", embed_url or "")
            stream = (root.group(1) if root else self.embed) + ("" if stream.startswith("/") else "/") + stream
        token = str(data.get("token") or "")
        if token and "token=" not in stream:
            stream += ("&" if "?" in stream else "?") + "token=" + token
        return stream

    def _cache_play(self, key, payload):
        """播放结果短时缓存(链接跟设备网络绑定且带时效,不适合长存)"""
        try:
            if len(self._play_cache) > 40:
                self._play_cache.clear()
            self._play_cache[key] = (time.time() + 90, payload)
        except Exception:
            pass

    def _slug_cands(self, slug):
        """聚合站给的播放页名常带分类后缀(-chinese-subtitle / -uncensored-leak),
        源站上真正存在的片名多半不带,逐层剥掉做候选,原样优先。"""
        slug = (slug or "").strip().strip("/")
        out = [slug] if slug else []
        cur = slug
        for _ in range(3):
            low = cur.lower()
            hit = ""
            for x in SLUG_SUFFIXES:
                if low.endswith(x):
                    hit = x
                    break
            if not hit:
                break
            cur = cur[: -len(hit)]
            if cur and cur not in out:
                out.append(cur)
        return out

    def _verify_stream(self, stream, referer=""):
        """确认这条流真能读(能读到播放列表头才算数)"""
        if not stream:
            return False
        try:
            h = {"User-Agent": self.ua, "Accept": "*/*"}
            if referer:
                h["Referer"] = referer
            req = urllib.request.Request(stream, headers=h)
            with self.opener.open(req, timeout=12) as resp:
                head = resp.read(400).decode("utf-8", "ignore")
                return ("#EXTM3U" in head) or (resp.getcode() == 200 and "mpegurl" in
                                               (resp.headers.get("Content-Type") or "").lower())
        except Exception as e:
            self._note("流校验未通过 %s" % str(e)[:100])
            return False

    def _third_party_stream(self, page_url):
        """第三方播放页 -> 真实 m3u8 直链。
        这类链接跟"请求它的人"绑在一起(令牌里带出口 IP 段和时效),
        所以必须用播放设备自己的网络在播放那一刻实时解,不能预先解好再塞给用户。"""
        if not page_url or not page_url.startswith("http"):
            return "", ""
        mm = re.match(r"^(https?://[^/]+)", page_url)
        origin = mm.group(1) if mm else ""
        # 注意:带着聚合站的 Referer 去打源站会被风控直接挡,这里只带它自己的域
        ref = origin + "/"
        pm = re.match(r"^(https?://[^/]+/play/index/)(.+?)/?$", page_url)
        targets = []
        if pm:
            for cs in self._slug_cands(pm.group(2)):
                targets.append(pm.group(1) + cs)
        else:
            targets.append(page_url)
        for u in targets:
            for attempt in range(2):
                code, text = self._fetch(u, referer=ref, timeout=15)
                if code != 200 or not text:
                    time.sleep(0.3)
                    continue
                stream = ""
                for blob in (text, self._plain(text)):
                    cfg = None
                    cm = RE_PLAYERCFG.search(blob)
                    if cm:
                        try:
                            cfg = json.loads(cm.group(1))
                        except Exception:
                            cfg = None
                    if isinstance(cfg, dict):
                        for k in ("m3u8", "hls", "playUrl", "url", "src", "file"):
                            v = cfg.get(k)
                            if isinstance(v, str) and v.startswith("http"):
                                stream = v.replace("\\/", "/")
                                break
                    if not stream:
                        sm = RE_ANY_M3U8.search(blob)
                        if sm:
                            stream = sm.group(1).replace("\\/", "/")
                    if stream:
                        break
                if stream and self._verify_stream(stream, referer=u):
                    return stream, u
                break
            time.sleep(0.2)
        return "", ""

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else str(ids)
        raw = str(raw or "").strip()
        if raw.startswith("folder/"):
            return {"list": []}
        code_id = raw.rsplit("/", 1)[-1]
        if not code_id:
            return {"list": []}
        try:
            self._ensure_host()
            html = self._detail_page(code_id)
            title = ""
            pic = ""
            embed_url = ""
            if html:
                for blob in (self._plain(html), html):
                    m = RE_OGIMG.search(html) or RE_OGIMG.search(blob)
                    if m and not pic:
                        pic = html_lib.unescape(m.group(1))
                    m = RE_OGTITLE.search(html) or RE_OGTITLE.search(blob)
                    if m and not title:
                        title = html_lib.unescape(m.group(1))
                    m = RE_EMBED.search(blob)
                    if m and not embed_url:
                        embed_url = m.group(1).replace("\\/", "/")
                if not title:
                    m = RE_TITLE.search(html)
                    if m:
                        title = m.group(1).split("|")[0].strip()
                if not pic:
                    m = re.search(r'"(https?://[^"]*/n/[^"]*)"', self._plain(html))
                    if m:
                        pic = m.group(1)
            if not embed_url:
                embed_url = "%s/video/%s" % (self.embed, code_id)
            data = self._resolve(embed_url)
            if data:
                if not title:
                    title = re.sub(r"\s+", " ", str(data.get("title") or "")).strip()
                if not pic:
                    pic = str(data.get("thumbnail") or "").strip()
            title = re.sub(r"\s+", " ", (title or "").replace(" - 123AV", "")).strip()
            return {
                "list": [{
                    "vod_id": raw,
                    "vod_name": title or code_id.upper(),
                    "vod_pic": pic or self._card(code_id.upper()),
                    "vod_remarks": "HD",
                    "vod_content": "编号: %s" % code_id.upper(),
                    "vod_play_from": "123AV",
                    "vod_play_url": "正片$%s" % embed_url,
                }]
            }
        except Exception as e:
            self._note("详情异常 %s" % str(e)[:120])
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or "").strip()
        if not raw:
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}
        try:
            # 同一片子短时间内被反复要,直接给上次解出来的
            now = time.time()
            hit = self._play_cache.get(raw)
            if hit and hit[0] > now:
                return dict(hit[1])
            self._ensure_host()

            embed_url = ""
            if raw.startswith("http") and (".m3u8" in raw):
                return {"parse": 0, "playUrl": "", "url": raw,
                        "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}
            if raw.startswith("http") and "/video/" in raw:
                embed_url = raw
            elif raw.startswith("http"):
                embed_url = raw
            else:
                code_id = raw.rsplit("/", 1)[-1]
                embed_url = self._embed_of(code_id) or ("%s/video/%s" % (self.embed, code_id))

            header = {"User-Agent": self.ua, "Referer": embed_url}
            data = self._resolve(embed_url) or {}

            # ① 站点自己直接给原生 HLS
            stream = self._decode_stream(data, embed_url)
            if stream:
                out = {"parse": 0, "playUrl": "", "url": stream, "header": header}
                self._cache_play(raw, out)
                return out

            # ② 站点把流甩给了第三方播放页:从那一页的播放配置里把直链抠出来
            page = str(data.get("embedUrl") or "").strip()
            for target in (page, embed_url):
                if not target:
                    continue
                s2, page_used = self._third_party_stream(target)
                if s2:
                    out = {"parse": 0, "playUrl": "", "url": s2,
                           "header": {"User-Agent": self.ua, "Referer": page_used}}
                    self._cache_play(raw, out)
                    return out

            # ③ 实在拿不到直链:把站点自己的播放页交给壳去嗅探
            if page:
                return {"parse": 1, "playUrl": "", "url": page,
                        "header": {"User-Agent": self.ua, "Referer": embed_url}}
            return {"parse": 1, "playUrl": "", "url": embed_url, "header": header}
        except Exception as e:
            self._note("播放异常 %s" % str(e)[:120])
            return {"parse": 1, "playUrl": "", "url": raw,
                    "header": {"User-Agent": self.ua, "Referer": self.host + "/"}}

    # ───────────────────────── 搜索 / 自检 ─────────────────────────

    def _diag_list(self):
        items = []
        try:
            ok = self._fetch(self.host + "/cn/new", referer=self.host + "/cn", timeout=8)
        except Exception as e:
            ok = (-1, str(e))
        rows = [
            "主机: %s" % self.host,
            "首页响应: HTTP %s / %s 字节" % (ok[0], len(ok[1] or "")),
            "解析出卡片: %s 条" % len(self._cards(self._plain(ok[1] or "")) if ok[0] == 200 else []),
            "网络: 已强制 IPv4",
            "版本: 加固版 v3",
        ]
        rows += ["最近请求: " + d for d in self.diag[-12:]]
        for i, r in enumerate(rows):
            items.append({
                "vod_id": "diag-%d" % i,
                "vod_name": r,
                "vod_pic": self._card("D"),
                "vod_remarks": "自检",
                "style": {"type": "rect", "ratio": 1.78},
            })
        return {"page": 1, "pagecount": 1, "limit": len(items), "total": len(items), "list": items}

    def searchContent(self, key, quick, pg="1"):
        k = (key or "").strip()
        if k.lower() in ("diag", "debug", "自检", "诊断"):
            return self._diag_list()
        try:
            page = int(pg) if pg else 1
        except Exception:
            page = 1
        try:
            self._ensure_host()
            url = "%s/cn/search/%s" % (self.host, urllib.parse.quote(k))
            if page > 1:
                url = url + "?page=%d" % page
            items, html = self._fetch_items(url, referer=self.host + "/cn")
            pc = self._pagecount(html, page) if items else page
            self._note("搜索 %s p%s -> %s 条" % (k[:20], page, len(items)))
            return {
                "page": page,
                "pagecount": pc if pc > 0 else 1,
                "limit": len(items) or 24,
                "total": 999999,
                "list": items,
            }
        except Exception as e:
            self._note("搜索异常 %s" % str(e)[:120])
            return self._empty(page)

    # ───────────────────────── 其它 ─────────────────────────

    def action(self, action):
        return {"msg": "OK"}

    def liveContent(self):
        return ""

    def localProxy(self, params):
        url = params.get("url", "")
        if not url:
            return [404, "text/plain; charset=utf-8", "Missing url parameter"]
        headers = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        }
        try:
            req = urllib.request.Request(url, headers=headers)
            with self.opener.open(req, timeout=self.timeout) as resp:
                return [resp.getcode(), "image/jpeg", resp.read()]
        except Exception:
            return [404, "text/plain; charset=utf-8", b""]

    def destroy(self):
        try:
            self.cj.clear()
        except Exception:
            pass
