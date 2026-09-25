#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2AV (home.2av.com) TVBox Spider
--------------------------------
核心突破：站点未登录只在 /web/video/player/{id}/{hd}/index.m3u8 里返回 33 片试看，
但分片指向的 CDN 目录下放着完整版 index.m3u8（含 #EXT-X-ENDLIST，长度可到 3 小时）。
流程：站上试看列表 -> 推出 CDN base -> 取 {base}/index.m3u8 完整分片表 -> 本地代理输出。
分片文件是「181 字节假 PNG 头 + 标准 MPEG-TS」，本地代理负责剥掉包头再吐给播放器。

零第三方依赖，兼容 Python 2.7 / 3.x 与 Jython。
"""

import base64
import hashlib
import json
import re
import socket
import sys
import threading
import time

try:  # Python 3
    from urllib.request import Request as _Request, urlopen as _urlopen
    from urllib.parse import urlencode as _urlencode, urljoin as _urljoin
    from urllib.parse import quote as _quote, unquote as _unquote
except ImportError:  # Python 2 / Jython 2.7
    from urllib2 import Request as _Request, urlopen as _urlopen
    from urllib import urlencode as _urlencode, quote as _quote, unquote as _unquote
    from urlparse import urljoin as _urljoin

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from socketserver import ThreadingMixIn
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
    from SocketServer import ThreadingMixIn


# ============================================================
# 基础工具
# ============================================================

PY2 = sys.version_info[0] < 3

if PY2:
    _TEXT_TYPES = (str, unicode)  # noqa: F821
else:
    _TEXT_TYPES = (str,)


def _us(v):
    """任何值转成安全文本"""
    if v is None:
        return ""
    if isinstance(v, bytes if not PY2 else str):
        try:
            return v.decode("utf-8", "ignore")
        except Exception:
            return ""
    if not isinstance(v, _TEXT_TYPES):
        try:
            return str(v)
        except Exception:
            return ""
    return v


def _bs(v):
    """文本转 bytes"""
    if isinstance(v, bytes):
        return v
    try:
        return _us(v).encode("utf-8")
    except Exception:
        return b""


def _unescape(s):
    """HTML 反转义（不依赖 html 模块，Jython 兼容）"""
    s = _us(s)
    pairs = (
        ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'),
        ("&#039;", "'"), ("&#39;", "'"), ("&apos;", "'"), ("&nbsp;", " "),
        ("&#x27;", "'"), ("&hellip;", "…"),
    )
    for a, b in pairs:
        s = s.replace(a, b)
    try:
        def _num(m):
            try:
                return chr(int(m.group(1)))
            except Exception:
                return m.group(0)
        s = re.sub(r"&#(\d+);", _num, s)
    except Exception:
        pass
    return s


def _strip_tags(s):
    return re.sub(r"<[^>]*>", "", _us(s)).strip()


def _clean_title(s):
    """清理标题：反转义 + 去标签 + 压缩空白 + 去站点后缀"""
    s = _strip_tags(_unescape(s))
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s*[-—|]\s*2AV\.IS\s*$", "", s, flags=re.I).strip()
    return s


def _abs(url, host):
    url = _us(url).strip()
    if not url:
        return ""
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return _urljoin(host.rstrip("/") + "/", url.lstrip("/"))


# 标题里出现这些词的内容直接跳过（用户既定的过滤规范）
_BLOCK_WORDS = (
    "幼女", "幼齿", "萝莉", "蘿莉", "loli", "小学生", "中学生", "初中", "高中",
    "未成年", "儿童", "女童", "中学", "小学", "jk制服少女", "teen",
)


def _blocked(text):
    t = _us(text).lower()
    for w in _BLOCK_WORDS:
        if w in t:
            return True
    return False


# ============================================================
# 网络层（urllib 直连，零依赖）
# ============================================================

_UA_PC = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
_UA_M = ("Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/131.0.0.0 Mobile Safari/537.36")


_THROTTLE_LOCK = threading.Lock()
_THROTTLE_LAST = [0.0]
_MIN_GAP = 0.08          # 同域最小请求间隔，防站点限流


def _throttle():
    with _THROTTLE_LOCK:
        now = time.time()
        wait = _MIN_GAP - (now - _THROTTLE_LAST[0])
        if wait > 0:
            time.sleep(wait)
        _THROTTLE_LAST[0] = time.time()


def _http(url, referer=None, data=None, timeout=20, headers=None, ua=None, retry=2):
    """返回 (bytes, err)；对限流/断连做短退避重试"""
    if not url:
        return None, "empty url"
    hdrs = {
        "User-Agent": ua or _UA_PC,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        hdrs["Referer"] = referer
    if headers:
        for k, v in headers.items():
            hdrs[k] = v
    body = None
    if data is not None:
        if isinstance(data, dict):
            body = _bs(_urlencode(data))
            hdrs["Content-Type"] = "application/x-www-form-urlencoded; charset=UTF-8"
        else:
            body = _bs(data)
    err = ""
    for attempt in range(retry + 1):
        _throttle()
        try:
            req = _Request(url, data=body, headers=hdrs)
            resp = _urlopen(req, timeout=timeout)
            try:
                return resp.read(), None
            finally:
                try:
                    resp.close()
                except Exception:
                    pass
        except Exception as e:
            err = "%s: %s" % (type(e).__name__, e)
            if attempt < retry:
                time.sleep(0.6 * (attempt + 1))
    return None, err


def _http_text(url, referer=None, data=None, timeout=20, headers=None, ua=None):
    raw, err = _http(url, referer, data, timeout, headers, ua)
    if raw is None:
        return "", err
    for enc in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(enc), None
        except Exception:
            continue
    return raw.decode("utf-8", "ignore"), None


# ============================================================
# 站点解析
# ============================================================

HOST = "https://home.2av.com"
CDN_HINT = "runcoin.store"

_RE_CARD = re.compile(r'<div class="videoCard">(.*?)</div>\s*</div>\s*</div>', re.S)
_RE_HREF_VIDEO = re.compile(r'href="/video/(\d+)\.html"')
_RE_IMG = re.compile(r'<img[^>]*(?:src|data-src|data-original)=["\']([^"\']+)["\'][^>]*?(?:alt=["\']([^"\']*)["\'])?', re.S)
_RE_ALT = re.compile(r'alt=["\']([^"\']*)["\']')
_RE_DUR = re.compile(r'font-size: 13px"?>\s*([\d]{1,2}:[\d]{2}(?::[\d]{2})?)\s*<')
_RE_H3 = re.compile(r'<h3[^>]*class="[^"]*index-h[^"]*"[^>]*>([^<]{1,60})</h3>', re.I)


def _parse_cards(html):
    """从列表 HTML 解析卡片列表"""
    items = []
    seen = set()
    if not html:
        return items
    blocks = re.split(r'<div class="videoCard">', html)
    for blk in blocks[1:]:
        try:
            m = _RE_HREF_VIDEO.search(blk)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            title = ""
            am = _RE_ALT.search(blk)
            if am:
                title = _clean_title(am.group(1))
            if not title:
                continue
            if _blocked(title):
                seen.add(vid)
                continue
            pic = ""
            im = _RE_IMG.search(blk)
            if im:
                pic = _unescape(im.group(1))
            pic = _fix_cover(pic)
            dur = ""
            dm = _RE_DUR.search(blk)
            if dm:
                dur = dm.group(1)
            remark = dur
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
            seen.add(vid)
        except Exception:
            continue
    return items


def _fix_cover(url):
    """封面：站点用 webp 代理，剥出原图直链"""
    url = _us(url)
    if not url:
        return ""
    mm = re.search(r"[?&]url=([^&]+)", url)
    if mm:
        try:
            inner = _unquote(_unescape(mm.group(1)))
            if inner.startswith("http"):
                return _unescape(inner)
        except Exception:
            pass
    return _unescape(url)


def _parse_sections(html):
    """首页板块：{板块名: [卡片]}"""
    out = {}
    if not html:
        return out
    marks = [(m.start(), _strip_tags(m.group(1))) for m in _RE_H3.finditer(html)]
    marks.append((len(html), "__END__"))
    for i in range(len(marks) - 1):
        name = marks[i][1]
        seg = html[marks[i][0]:marks[i + 1][0]]
        cards = _parse_cards(seg)
        if cards:
            out[name] = cards
    return out


def _find_section(sections, *keys):
    for name, cards in sections.items():
        low = name.lower()
        for k in keys:
            if k in low:
                return cards
    return []


_CDN_SEG_RE = re.compile(r'^(https?://[^/\s]+/[^\s]*?)/([^/\s]+\.(?:png|ts|jpg|jpeg))$')


def _cdn_base_from_playlist(text):
    """从试看播放列表的首个分片推出 CDN 目录"""
    if not text:
        return ""
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _CDN_SEG_RE.match(line)
        if m:
            return m.group(1)
    return ""


def _parse_playlist(text):
    """解析 m3u8：返回 (控制标签, [(时长, 地址)])"""
    tags = []
    segs = []
    last_dur = ""
    for raw in _us(text).split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            last_dur = line.split(":", 1)[1].split(",")[0].strip() if ":" in line else ""
            continue
        if line.startswith("#"):
            tags.append(line)
            continue
        segs.append((last_dur, line))
        last_dur = ""
    return tags, segs


_TAG_CHECK = {}


def _tag_has_content(tid, ttl=86400):
    """站点空标签过滤：列表页无卡片且增量接口也无数据 -> 判为空标签"""
    sid = _us(tid).split("_", 1)[-1]
    now = time.time()
    hit = _TAG_CHECK.get(tid)
    if hit and hit[0] > now:
        return hit[1]
    ok = False
    try:
        html, _ = _http_text("%s/tag/%s.html" % (HOST, sid), HOST + "/")
        if html and 'id="empty"' not in html:
            ok = bool(_parse_cards(html))
        if not ok:
            raw, _ = _http_text(
                "%s/index/index/tagView_more?id=%s&offset=0" % (HOST, _quote(sid)),
                "%s/tag/%s.html" % (HOST, sid))
            ok = bool(_parse_cards(raw or ""))
    except Exception:
        ok = True          # 探测本身失败时不误删分类
    _TAG_CHECK[tid] = (now + ttl, ok)
    return ok


# ============================================================
# 播放链路：站上试看 -> CDN 完整片源
# ============================================================

_CACHE = {}          # key -> (到期时间, 数据)
_CACHE_LOCK = threading.Lock()


def _cache_get(key):
    with _CACHE_LOCK:
        v = _CACHE.get(key)
        if not v:
            return None
        if v[0] < time.time():
            try:
                del _CACHE[key]
            except Exception:
                pass
            return None
        return v[1]


def _cache_put(key, val, ttl=3600):
    with _CACHE_LOCK:
        if len(_CACHE) > 300:
            for k in list(_CACHE.keys())[:100]:
                _CACHE.pop(k, None)
        _CACHE[key] = (time.time() + ttl, val)


def resolve_stream(vid, hd="", ref=None):
    """
    解析一部片子的完整播放数据。
    返回 dict: {ok, hds, segs:[(dur,url)], cdn_base, error}
    """
    vid = _us(vid).split("|")[0].strip()
    if not vid:
        return {"ok": False, "error": "no id"}
    ref = ref or ("%s/video/%s.html" % (HOST, vid))
    ck = "hds:%s" % vid
    hds = _cache_get(ck)
    if hds is None:
        txt, err = _http_text("%s/web/video/player/%s/1/index.m3u8" % (HOST, vid), ref)
        if not txt or "#EXTM3U" not in txt:
            return {"ok": False, "error": err or "master 取不到"}
        hds = re.findall(r"/web/video/player/%s/(\d+)/index\.m3u8" % vid, txt)
        if not hds:
            hds = []
        _cache_put(ck, hds, 7200)

    if not hds:
        # 无分档：直接把 master 当播放表（少数片是这样）
        return {"ok": False, "error": "无清晰度档位"}

    want = _us(hd).strip()
    if want not in hds:
        want = "720" if "720" in hds else hds[0]

    sk = "pl:%s:%s" % (vid, want)
    cached = _cache_get(sk)
    if cached:
        return cached

    prev_url = "%s/web/video/player/%s/%s/index.m3u8?resource=" % (HOST, vid, want)
    ptxt, err = _http_text(prev_url, ref)
    if not ptxt or "#EXTM3U" not in ptxt:
        return {"ok": False, "error": err or "档位播放表取不到"}

    cdn_base = _cdn_base_from_playlist(ptxt)
    result = None
    if cdn_base:
        full, e2 = _http_text(cdn_base + "/index.m3u8", HOST + "/")
        if full and "#EXTM3U" in full:
            tags, segs = _parse_playlist(full)
            abs_segs = []
            for dur, s in segs:
                abs_segs.append((dur, _abs(s, cdn_base + "/")))
            if abs_segs:
                result = {
                    "ok": True, "vid": vid, "hd": want, "hds": hds,
                    "cdn_base": cdn_base, "segs": abs_segs,
                    "tags": [t for t in tags if not t.startswith("#EXT-X-ENDLIST")
                             and not t.startswith("#EXT-X-STREAM-INF")],
                    "full": True, "error": "",
                }
    if result is None:
        # 兜底：CDN 完整表拿不到，用站上的（试看）
        tags, segs = _parse_playlist(ptxt)
        abs_segs = [(d, _abs(s, HOST + "/")) for d, s in segs]
        if not abs_segs:
            return {"ok": False, "error": "站上播放表为空"}
        result = {
            "ok": True, "vid": vid, "hd": want, "hds": hds,
            "cdn_base": cdn_base, "segs": abs_segs,
            "tags": [t for t in tags if not t.startswith("#EXT-X-STREAM-INF")],
            "full": False, "error": "",
        }
    _cache_put(sk, result, 3600 if result.get("full") else 120)
    return result


# ============================================================
# 分片处理：剥掉 181 字节假 PNG 头
# ============================================================

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_IEND = b"IEND"


def strip_shell(data):
    """把站点分片还原成纯 MPEG-TS"""
    if not data:
        return data
    if data[:1] == b"\x47":
        return data
    if data[:8] == _PNG_MAGIC:
        i = data.find(_IEND)
        if i > 0 and i < 8192:
            start = i + 8
            if start < len(data) and data[start] == 0x47:
                return data[start:]
    # 兜底：全文件找 TS 同步点
    for off in range(0, min(4096, max(0, len(data) - 376))):
        if data[off] == 0x47 and data[off + 188] == 0x47 and data[off + 376] == 0x47:
            return data[off:]
    return data


# 分片内存缓存（顺序播放命中率高）
_SEG_CACHE = {}
_SEG_ORDER = []
_SEG_LOCK = threading.Lock()
_SEG_MAX = 96


def _seg_cache_get(key):
    with _SEG_LOCK:
        return _SEG_CACHE.get(key)


def _seg_cache_put(key, val):
    with _SEG_LOCK:
        if key not in _SEG_CACHE:
            _SEG_ORDER.append(key)
        _SEG_CACHE[key] = val
        while len(_SEG_ORDER) > _SEG_MAX:
            k = _SEG_ORDER.pop(0)
            _SEG_CACHE.pop(k, None)


def fetch_segment(url, ref=None):
    key = hashlib.md5(_bs(url)).hexdigest()
    hit = _seg_cache_get(key)
    if hit is not None:
        return hit, None
    raw, err = _http(url, ref or (HOST + "/"), timeout=25)
    if raw is None:
        return None, err
    data = strip_shell(raw)
    _seg_cache_put(key, data)
    return data, None


# ============================================================
# 本地代理服务（给播放器吐完整播放表 + 剥壳分片）
# ============================================================

_STREAMS = {}        # sid -> {"segs": [...], "tags": [...], ...}
_STREAM_ORDER = []
_STREAM_LOCK = threading.Lock()
_SERVER = {"httpd": None, "port": 0}
_SERVER_LOCK = threading.Lock()
_STREAM_MAX = 24


def _register_stream(info):
    sid = hashlib.md5(_bs("%s|%s|%s" % (info.get("vid"), info.get("hd"),
                                        info.get("cdn_base")))).hexdigest()[:12]
    with _STREAM_LOCK:
        _STREAMS[sid] = info
        if sid in _STREAM_ORDER:
            _STREAM_ORDER.remove(sid)
        _STREAM_ORDER.append(sid)
        while len(_STREAM_ORDER) > _STREAM_MAX:
            k = _STREAM_ORDER.pop(0)
            _STREAMS.pop(k, None)
    return sid


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ZakaProxy/1.0"

    def log_message(self, fmt, *args):
        return

    def _send(self, code, ctype, body, extra=None):
        try:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Accept-Ranges", "bytes")
            if extra:
                for k, v in extra.items():
                    self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD" and body:
                self.wfile.write(body)
        except Exception:
            pass

    def _query(self):
        q = {}
        if "?" in self.path:
            raw = self.path.split("?", 1)[1]
            for part in raw.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    q[_unquote(k)] = _unquote(v)
                elif part:
                    q[_unquote(part)] = ""
        return q

    def do_GET(self):
        self._handle()

    def do_HEAD(self):
        self._handle()

    def _handle(self):
        path = self.path.split("?", 1)[0]
        q = self._query()
        try:
            if path.startswith("/p"):
                return self._playlist(q)
            if path.startswith("/s"):
                return self._segment(q)
        except Exception as e:
            return self._send(500, "text/plain", _bs("err %s" % e))
        return self._send(404, "text/plain", b"Not Found")

    def _playlist(self, q):
        sid = _us(q.get("id"))
        with _STREAM_LOCK:
            info = _STREAMS.get(sid)
        if not info:
            return self._send(404, "text/plain", b"stream gone")
        port = _SERVER.get("port") or 0
        lines = ["#EXTM3U", "#EXT-X-VERSION:3",
                 "#EXT-X-TARGETDURATION:%s" % (info.get("target") or 4),
                 "#EXT-X-MEDIA-SEQUENCE:0"]
        for t in info.get("tags") or []:
            if t.startswith("#EXT-X-TARGETDURATION") or t.startswith("#EXT-X-MEDIA-SEQUENCE"):
                continue
            lines.append(t)
        base = "http://127.0.0.1:%d/s?id=%s&n=" % (port, sid)
        for idx, (dur, _u) in enumerate(info.get("segs") or []):
            lines.append("#EXTINF:%s," % (dur or "4.000000"))
            lines.append(base + str(idx))
        lines.append("#EXT-X-ENDLIST")
        body = _bs("\n".join(lines) + "\n")
        return self._send(200, "application/vnd.apple.mpegurl", body,
                          {"Cache-Control": "no-cache"})

    def _segment(self, q):
        sid = _us(q.get("id"))
        try:
            n = int(_us(q.get("n")) or -1)
        except Exception:
            n = -1
        with _STREAM_LOCK:
            info = _STREAMS.get(sid)
        if not info:
            return self._send(404, "text/plain", b"stream gone")
        segs = info.get("segs") or []
        if n < 0 or n >= len(segs):
            return self._send(404, "text/plain", b"bad index")
        url = segs[n][1]
        data, err = fetch_segment(url, info.get("referer"))
        if data is None:
            return self._send(502, "text/plain", _bs("fetch fail %s" % err))
        rng = self.headers.get("Range") if hasattr(self, "headers") else None
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", _us(rng))
            if m:
                total = len(data)
                a = int(m.group(1)) if m.group(1) else 0
                b = int(m.group(2)) if m.group(2) else total - 1
                if a >= total:
                    return self._send(416, "text/plain", b"", {"Content-Range": "bytes */%d" % total})
                b = min(b, total - 1)
                chunk = data[a:b + 1]
                return self._send(206, "video/mp2t", chunk,
                                  {"Content-Range": "bytes %d-%d/%d" % (a, b, total)})
        return self._send(200, "video/mp2t", data)


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # 播放器拉完即断连属常态，不刷栈
        try:
            t = sys.exc_info()[0]
            if t is not None and issubclass(t, (socket.error, IOError, OSError)):
                return
        except Exception:
            pass
        return


def ensure_server():
    """起本地代理服务，返回端口"""
    with _SERVER_LOCK:
        if _SERVER["httpd"] is not None and _SERVER["port"]:
            return _SERVER["port"]
        httpd = _ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        port = httpd.server_address[1]
        _SERVER["httpd"] = httpd
        _SERVER["port"] = port
        t = threading.Thread(target=httpd.serve_forever)
        t.setDaemon(True)
        t.start()
        return port


# ============================================================
# Spider
# ============================================================

_EXT_DEFAULT = ""


class Spider(object):

    def __init__(self):
        self.host = HOST
        self.ua = _UA_PC
        self.s = None
        self.session = None
        self.sess = None
        self.opt = {}
        self._classes = None

    # ---------- 契约 ----------
    def getDependence(self):
        return []

    def init(self, extend=""):
        if isinstance(extend, dict):
            self.opt = extend
        elif isinstance(extend, str) and extend.strip().startswith("{"):
            try:
                d = json.loads(extend)
                if isinstance(d, dict):
                    self.opt = d
            except Exception:
                self.opt = {}
        else:
            self.opt = {}
        return None

    def isVideoFormat(self, url):
        u = _us(url).lower()
        return (".m3u8" in u) or (".mp4" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return None

    def action(self, action):
        return {}

    # ---------- 分类 ----------
    def _load_classes(self):
        if self._classes is not None:
            return self._classes
        cls = [
            {"type_id": "home", "type_name": "热门"},
            {"type_id": "free", "type_name": "免费"},
            {"type_id": "rec", "type_name": "推荐"},
            {"type_id": "new", "type_name": "最新"},
        ]
        try:
            html, _ = _http_text(self.host + "/", self.host + "/")
            for m in re.finditer(r'href="(/space/(\d+)\.html)"[^>]*>\s*(?:<img[^>]*alt="([^"]*)")?',
                                 html or ""):
                pid = m.group(2)
                name = _clean_title(m.group(3) or "")
                tid = "space_" + pid
                if not name:
                    continue
                if any(c["type_id"] == tid for c in cls):
                    continue
                cls.append({"type_id": tid, "type_name": name})
            for m in re.finditer(r'href="(/tag/(\d+)\.html)"[^>]*>\s*([^<]{1,20})', html or ""):
                tid = "tag_" + m.group(2)
                name = _clean_title(m.group(3) or "")
                if not name or any(c["type_id"] == tid for c in cls):
                    continue
                if not _tag_has_content(tid):
                    continue          # 站点上的空标签，不放进分类
                cls.append({"type_id": tid, "type_name": name})
        except Exception:
            pass
        self._classes = cls
        return cls

    def homeContent(self, filter=None):
        try:
            return {"class": self._load_classes(), "filters": {}}
        except Exception:
            return {"class": [], "filters": {}}

    def homeVideoContent(self):
        try:
            html, _ = _http_text(self.host + "/", self.host + "/")
            secs = _parse_sections(html or "")
            items = _find_section(secs, "popular", "热门")
            if not items:
                items = _find_section(secs, "recommend", "推荐")
            if not items:
                items = _parse_cards(html or "")
            return {"list": items[:40]}
        except Exception:
            return {"list": []}

    # ---------- 分类列表 ----------
    def _more_api(self, tid, offset):
        """增量接口：返回 (html片段, 是否还有更多)"""
        ref = self.host + "/"
        if tid == "new":
            url = "%s/index/index/index_more?offset=%d" % (self.host, offset)
            txt, _ = _http_text(url, ref)
            return txt or ""
        if tid.startswith("space_"):
            sid = tid.split("_", 1)[1]
            url = "%s/index/index/space_more?id=%s&offset=%d" % (self.host, _quote(sid), offset)
            txt, _ = _http_text(url, self.host + "/space/%s.html" % sid)
            return txt or ""
        if tid.startswith("tag_"):
            sid = tid.split("_", 1)[1]
            url = "%s/index/index/tagView_more?id=%s&offset=%d" % (self.host, _quote(sid), offset)
            txt, _ = _http_text(url, self.host + "/tag/%s.html" % sid)
            return txt or ""
        return ""

    def _first_page(self, tid):
        """第一屏：优先吃站点 SSR 页面"""
        if tid in ("home", "free", "rec"):
            html, _ = _http_text(self.host + "/", self.host + "/")
            secs = _parse_sections(html or "")
            if tid == "home":
                items = _find_section(secs, "popular", "热门")
            elif tid == "free":
                items = _find_section(secs, "free", "免费")
            else:
                items = _find_section(secs, "recommend", "推荐")
            return items, []
        if tid == "new":
            raw = self._more_api(tid, 0)
            return _parse_cards(raw), _parse_cards(raw)
        if tid.startswith("space_"):
            sid = tid.split("_", 1)[1]
            html, _ = _http_text(self.host + "/space/%s.html" % sid, self.host + "/")
            items = _parse_cards(html or "")
            if not items:
                items = _parse_cards(self._more_api(tid, 0))
            return items, []
        if tid.startswith("tag_"):
            sid = tid.split("_", 1)[1]
            html, _ = _http_text(self.host + "/tag/%s.html" % sid, self.host + "/")
            items = _parse_cards(html or "")
            if not items:
                items = _parse_cards(self._more_api(tid, 0))
            return items, []
        return [], []

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            tid = _us(tid) or "home"
            try:
                pg = int(pg)
            except Exception:
                pg = 1
            if pg < 1:
                pg = 1

            if pg == 1:
                items, extra = self._first_page(tid)
                more = _parse_cards(self._more_api(tid, len(items))) if tid == "new" else []
                if tid == "new":
                    more = extra
                try:
                    self._pg1_count = getattr(self, "_pg1_count", {})
                    self._pg1_count[tid] = len(items)
                except Exception:
                    pass
            else:
                if tid in ("home", "free", "rec"):
                    # 首页三大板块为固定精选，只有一屏
                    return {"list": [], "page": pg, "pagecount": pg}
                base = 16 if tid.startswith("space_") else 12
                try:
                    base = (getattr(self, "_pg1_count", {}) or {}).get(tid, base) or base
                except Exception:
                    base = 16 if tid.startswith("space_") else 12
                offset = base + (pg - 2) * 16
                raw = self._more_api(tid, offset)
                items = _parse_cards(raw)
                more = items

            uniq = []
            vis = set()
            for it in items:
                if it["vod_id"] in vis:
                    continue
                vis.add(it["vod_id"])
                uniq.append(it)
            if tid in ("home", "free", "rec"):
                pagecount = 1
            else:
                pagecount = pg + 1 if (len(uniq) >= 12 or len(more) > 0) else pg
            return {"list": uniq, "page": pg, "pagecount": pagecount,
                    "limit": len(uniq), "total": len(uniq)}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1}

    # ---------- 详情 ----------
    def detailContent(self, ids):
        try:
            vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            vid = _us(vid).split("|")[0].strip()
            if not vid:
                return {"list": []}
            ref = "%s/video/%s.html" % (self.host, vid)
            html, _ = _http_text(ref, self.host + "/")
            if not html:
                return {"list": []}

            title = ""
            m = re.search(r'<meta property="og:title" content="([^"]*)"', html)
            if m:
                title = _clean_title(m.group(1))
            if not title:
                m = re.search(r'<title>([^<]*)</title>', html)
                if m:
                    title = _clean_title(m.group(1))
            if _blocked(title):
                return {"list": []}

            pic = ""
            m = re.search(r'<meta content="([^"]*)" property="og:image"', html)
            if m:
                pic = _fix_cover(m.group(1))

            content = ""
            m = re.search(r'<div[^>]*class="[^"]*(?:des|content|intro)[^"]*"[^>]*>(.*?)</div>', html, re.S)
            if m:
                content = _strip_tags(m.group(1))[:500]
            try:
                durs = re.findall(r'font-size: 13px"?>\s*([\d]{1,2}:[\d]{2}(?::[\d]{2})?)\s*<', html)
                pub = re.findall(r'videoPlayNum[^>]*>\s*<span>\s*([^<]{1,20})', html)
                tags = [_strip_tags(t) for t in re.findall(r'class="[^"]*tag[^"]*"[^>]*>\s*([^<>]{1,20})\s*<', html)]
                meta = []
                if durs:
                    meta.append("时长 " + durs[0])
                if pub:
                    meta.append("播放 " + _clean_title(pub[0]))
                if tags:
                    meta.append("标签 " + "/".join([t for t in tags[:6] if t]))
                head = " ".join(meta)
                if head:
                    content = (head + "\n" + content).strip()
            except Exception:
                pass

            info = resolve_stream(vid, "", ref)
            hds = info.get("hds") or []
            if not hds:
                hds = ["720"]

            order = [h for h in ("1080", "720", "540", "480", "360") if h in hds]
            for h in hds:
                if h not in order:
                    order.append(h)

            froms = []
            urls = []
            for h in order:
                froms.append("%sP" % h)
                urls.append("正片$%s|%s" % (vid, h))

            item = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "$$$".join(froms) if froms else "默认",
                "vod_play_url": "$$$".join(urls) if urls else "正片$%s" % vid,
                "vod_remarks": "完整版" if info.get("full") else "",
            }
            return {"list": [item]}
        except Exception:
            return {"list": []}

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            key = _us(key).strip()
            if not key:
                return {"list": [], "page": 1, "pagecount": 1}
            txt, err = _http_text("%s/web/index/search" % self.host, self.host + "/",
                                  data={"q": key})
            items = []
            seen = set()
            data = None
            if txt:
                try:
                    data = json.loads(txt)
                except Exception:
                    data = None
            arr = []
            if isinstance(data, dict):
                arr = data.get("data") or []
            elif isinstance(data, list):
                arr = data
            for d in arr:
                if not isinstance(d, dict):
                    continue
                raw_id = _us(d.get("id") or "")
                m = re.search(r"(\d+)", raw_id)
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen:
                    continue
                name = _clean_title(d.get("name") or "")
                if not name or _blocked(name):
                    continue
                items.append({"vod_id": vid, "vod_name": name,
                              "vod_pic": _fix_cover(d.get("pic") or d.get("img") or ""),
                              "vod_remarks": ""})
                seen.add(vid)
            if not items:
                # 兜底：走站内搜索页
                html, _ = _http_text("%s/index/search?q=%s" % (self.host, _quote(key)),
                                     self.host + "/")
                items = _parse_cards(html or "")
            return {"list": items, "page": 1, "pagecount": 1}
        except Exception:
            return {"list": [], "page": 1, "pagecount": 1}

    # ---------- 播放 ----------
    def playerContent(self, flag, ids, vipFlags=None):
        empty = {"parse": 1, "jx": 0, "playUrl": "", "url": "", "header": {}}
        try:
            raw = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
            raw = _us(raw)
            parts = raw.split("|")
            vid = parts[0].strip()
            hd = parts[1].strip() if len(parts) > 1 else ""
            if not vid:
                return empty
            ref = "%s/video/%s.html" % (self.host, vid)
            info = resolve_stream(vid, hd, ref)
            if not info.get("ok"):
                return empty
            info["referer"] = self.host + "/"
            info["target"] = 4
            try:
                info["target"] = int(float(info.get("segs")[0][0] or 4)) or 4
                if info["target"] < 1:
                    info["target"] = 4
            except Exception:
                info["target"] = 4
            sid = _register_stream(info)
            port = ensure_server()
            url = "http://127.0.0.1:%d/p?id=%s" % (port, sid)
            return {
                "parse": 0,
                "jx": 0,
                "playUrl": "",
                "url": url,
                "header": {"User-Agent": self.ua, "Referer": ref},
                "format": "application/x-mpegURL",
            }
        except Exception:
            return empty

    # ---------- 壳回调本地代理 ----------
    def localProxy(self, param):
        if not isinstance(param, dict):
            txt = _us(param)
            if txt.strip().startswith("{"):
                try:
                    param = json.loads(txt)
                except Exception:
                    param = {}
        if not isinstance(param, dict):
            param = {}
        q = {}
        for k, v in param.items():
            q[_us(k)] = _us(v)

        # 壳把 /p? /s? 的 query 透传过来
        sid = q.get("id", "")
        if "n" in q:
            try:
                n = int(q.get("n") or -1)
            except Exception:
                n = -1
            with _STREAM_LOCK:
                info = _STREAMS.get(sid)
            if not info:
                return [404, "text/plain", b"stream gone", {}]
            segs = info.get("segs") or []
            if n < 0 or n >= len(segs):
                return [404, "text/plain", b"bad index", {}]
            data, err = fetch_segment(segs[n][1], info.get("referer"))
            if data is None:
                return [502, "text/plain", _bs("fetch fail %s" % err), {}]
            return [200, "video/mp2t", data, {"Access-Control-Allow-Origin": "*"}]

        if sid:
            with _STREAM_LOCK:
                info = _STREAMS.get(sid)
            if not info:
                return [404, "text/plain", b"stream gone", {}]
            port = _SERVER.get("port") or 0
            lines = ["#EXTM3U", "#EXT-X-VERSION:3",
                     "#EXT-X-TARGETDURATION:%s" % (info.get("target") or 4),
                     "#EXT-X-MEDIA-SEQUENCE:0"]
            base = "http://127.0.0.1:%d/s?id=%s&n=" % (port, sid)
            for idx, (dur, _u) in enumerate(info.get("segs") or []):
                lines.append("#EXTINF:%s," % (dur or "4.000000"))
                lines.append(base + str(idx))
            lines.append("#EXT-X-ENDLIST")
            return [200, "application/vnd.apple.mpegurl", _bs("\n".join(lines) + "\n"),
                    {"Access-Control-Allow-Origin": "*"}]

        # 兼容直接透传 URL 的调用方式
        u = q.get("url", "")
        if u:
            data, err = fetch_segment(u, q.get("referer") or (self.host + "/"))
            if data is None:
                return [502, "text/plain", _bs("fetch fail %s" % err), {}]
            return [200, "video/mp2t", data, {"Access-Control-Allow-Origin": "*"}]

        return [404, "text/plain", b"Not Found", {}]
