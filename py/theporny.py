# -*- coding: utf-8 -*-
"""
theporny.py  --  TVBox Spider (FongMi / 影视仓 / OK影视 / PeekPro 兼容)

站点     : https://theporny.com
协议     : 站点前端是 Angular 壳, 所有业务请求统一走
           POST {网关}/js   体: {"url":"<接口>","app":"theporny.com", ...}
           响应体 {"r":"<base64>"}, base64 里是 OpenSSL "Salted__" 容器,
           口令取自站点前端常量. 本文件用纯 Python 复现该算法:
             key||iv = EVP_BytesToKey(MD5 迭代)  ->  AES-256-CBC  ->  PKCS7  ->  JSON
           网关域名有多个镜像, 脚本自动轮换.
播放     : 详情接口下发带时效签名的 m3u8, 播放时必须重新取一次拿新签名.
           清单里分片是相对路径, 由本脚本自带的 127.0.0.1 中转绝对化后再吐给播放器.
依赖     : 零第三方依赖 (requests 有则用, 无则 urllib 兜底)
兼容     : CPython 2.7 / 3.x / Jython 2.7

ext 用法:
    "https://theporny.com|interval=1.2|img=direct|proxy=1"
    可选项全部可省:
      base=        网关主域名, 默认 v2.cdn199.com
      interval=    请求间隔秒, 默认 1.0 (站点有频控, 别低于 0.5)
      img=         direct(默认) | relay  图片是否走本地中转
      proxy=       1(默认) 播放清单走本地中转  | 0 直接给原始 m3u8
"""

import base64
import binascii
import json
import re
import socket
import threading
import time

try:
    import hashlib
except ImportError:
    hashlib = None

try:
    import requests
except ImportError:
    requests = None

try:
    from urllib.parse import quote, urljoin, unquote
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:  # py2
    from urllib import quote, unquote
    from urllib2 import Request, urlopen, URLError
    from urlparse import urljoin

try:
    text_type = unicode  # noqa  py2
except NameError:
    text_type = str


# ---------------------------------------------------------------- 基础工具

def _to_bytes(v):
    if isinstance(v, bytes):
        return v
    if isinstance(v, bytearray):
        return bytes(v)
    if text_type is not str and isinstance(v, text_type):
        return v.encode("utf-8")
    return str(v).encode("utf-8")


def _to_text(v):
    if isinstance(v, text_type):
        return v
    if isinstance(v, (bytes, bytearray)):
        try:
            return v.decode("utf-8")
        except Exception:
            return v.decode("latin-1", "ignore")
    return text_type(v)


# ---------------------------------------------------------------- MD5

def _md5(data):
    if hashlib is not None:
        return hashlib.md5(data).digest()
    return _md5_pure(data)


def _md5_pure(data):
    """纯 Python MD5 (环境无 hashlib 时兜底)。"""
    import struct

    msg = bytearray(data)
    ml = len(msg) * 8
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack("<Q", ml)

    s = [7, 12, 17, 22] * 4 + [5, 9, 14, 20] * 4 + [4, 11, 16, 23] * 4 + [6, 10, 15, 21] * 4
    k = [int(abs(__import__("math").sin(i + 1)) * 4294967296) & 0xFFFFFFFF for i in range(64)]

    a0, b0, c0, d0 = 0x67452301, 0xEFCDAB89, 0x98BADCFE, 0x10325476
    for off in range(0, len(msg), 64):
        m = struct.unpack("<16I", bytes(msg[off:off + 64]))
        a, b, c, d = a0, b0, c0, d0
        for i in range(64):
            if i < 16:
                f = (b & c) | (~b & d)
                g = i
            elif i < 32:
                f = (d & b) | (~d & c)
                g = (5 * i + 1) % 16
            elif i < 48:
                f = b ^ c ^ d
                g = (3 * i + 5) % 16
            else:
                f = c ^ (b | (~d & 0xFFFFFFFF))
                g = (7 * i) % 16
            f = (f + a + k[i] + m[g]) & 0xFFFFFFFF
            a, d, c, b = d, c, b, (b + ((f << s[i]) | (f >> (32 - s[i])))) & 0xFFFFFFFF
        a0 = (a0 + a) & 0xFFFFFFFF
        b0 = (b0 + b) & 0xFFFFFFFF
        c0 = (c0 + c) & 0xFFFFFFFF
        d0 = (d0 + d) & 0xFFFFFFFF
    return struct.pack("<4I", a0, b0, c0, d0)


# ---------------------------------------------------------------- AES-256 解密

_SBOX_HEX = (
    "637c777bf26b6fc53001672bfed7ab76ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d8311504c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f8453d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa851a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d197360814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df8ca1890dbfe6426841992d0fb054bb16"
)

_SBOX = [int(_SBOX_HEX[i:i + 2], 16) for i in range(0, 512, 2)]
_INV = [0] * 256
for _i, _v in enumerate(_SBOX):
    _INV[_v] = _i


def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1:
            p ^= a
        hi = a & 0x80
        a = (a << 1) & 0xFF
        if hi:
            a ^= 0x1B
        b >>= 1
    return p


_M9 = [_gmul(x, 9) for x in range(256)]
_M11 = [_gmul(x, 11) for x in range(256)]
_M13 = [_gmul(x, 13) for x in range(256)]
_M14 = [_gmul(x, 14) for x in range(256)]


def _round_keys(key):
    """AES-256 密钥扩展, 返回 15 组 16 字节轮密钥。"""
    nk, nr = 8, 14
    w = [[key[4 * i + j] for j in range(4)] for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (nr + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [_SBOX[x] for x in t]
            t[0] ^= rcon
            rcon = (rcon << 1) ^ 0x1B if rcon & 0x80 else rcon << 1
        elif i % nk == 4:
            t = [_SBOX[x] for x in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    rks = []
    for r in range(nr + 1):
        k = []
        for c in range(4):
            k.extend(w[4 * r + c])
        rks.append(k)
    return rks


_RS = (0, 13, 10, 7, 4, 1, 14, 11, 8, 5, 2, 15, 12, 9, 6, 3)


def _decrypt_block(blk, rks):
    s = [blk[i] ^ rks[14][i] for i in range(16)]
    for rnd in range(13, 0, -1):
        t = [_INV[s[i]] for i in _RS]
        t = [t[i] ^ rks[rnd][i] for i in range(16)]
        o = [0] * 16
        for c in range(4):
            a0, a1, a2, a3 = t[4 * c], t[4 * c + 1], t[4 * c + 2], t[4 * c + 3]
            o[4 * c] = _M14[a0] ^ _M11[a1] ^ _M13[a2] ^ _M9[a3]
            o[4 * c + 1] = _M9[a0] ^ _M14[a1] ^ _M11[a2] ^ _M13[a3]
            o[4 * c + 2] = _M13[a0] ^ _M9[a1] ^ _M14[a2] ^ _M11[a3]
            o[4 * c + 3] = _M11[a0] ^ _M13[a1] ^ _M9[a2] ^ _M14[a3]
        s = o
    t = [_INV[s[i]] for i in _RS]
    return [t[i] ^ rks[0][i] for i in range(16)]


def aes_cbc_decrypt(key, iv, data):
    rks = _round_keys(list(key))
    out = []
    prev = list(iv)
    for off in range(0, len(data) - 15, 16):
        blk = list(data[off:off + 16])
        dec = _decrypt_block(blk, rks)
        out.extend([dec[j] ^ prev[j] for j in range(16)])
        prev = blk
    if out:
        pad = out[-1]
        if 1 <= pad <= 16:
            out = out[:-pad]
    try:
        return bytes(bytearray(out))
    except Exception:
        return b"".join([chr(x) for x in out])


def evp_bytes_to_key(pw, salt, need=48):
    """EVP_BytesToKey(MD5, 1 round) -- 与 CryptoJS 口令模式一致。"""
    d = b""
    prev = b""
    while len(d) < need:
        prev = _md5(prev + pw + salt)
        d += prev
    return d[:need]


# ---------------------------------------------------------------- 本地中转

class _Relay(object):
    """极简本地 HTTP 服务, 用于把 m3u8 里的相对分片绝对化。"""

    def __init__(self, spider):
        self.spider = spider
        self.sock = None
        self.port = 0
        self._lock = threading.Lock()

    def ensure(self):
        if self.port:
            return self.port
        with self._lock:
            if self.port:
                return self.port
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(("127.0.0.1", 0))
            s.listen(32)
            self.sock = s
            self.port = s.getsockname()[1]
            t = threading.Thread(target=self._loop)
            t.setDaemon(True)
            t.start()
            return self.port

    def _loop(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except Exception:
                return
            try:
                th = threading.Thread(target=self._handle, args=(conn,))
                th.setDaemon(True)
                th.start()
            except Exception:
                try:
                    conn.close()
                except Exception:
                    pass

    def _handle(self, conn):
        try:
            conn.settimeout(20)
            raw = b""
            while b"\r\n\r\n" not in raw and len(raw) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                raw += chunk
            first = raw.split(b"\r\n")[0].decode("latin-1")
            parts = first.split(" ")
            target = parts[1] if len(parts) > 1 else "/"
            body, mime, code = self.spider._relay_dispatch(target)
            head = "HTTP/1.1 %d OK\r\nContent-Type: %s\r\n" \
                   "Content-Length: %d\r\nAccess-Control-Allow-Origin: *\r\n" \
                   "Connection: close\r\n\r\n" % (code, mime, len(body))
            conn.sendall(_to_bytes(head) + body)
        except Exception:
            pass
        finally:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------- Spider

class Spider(object):

    HOST = "https://theporny.com"
    APP = "theporny.com"
    VER = "260901"
    PASS = b"xxx"

    GATES = [
        "https://v2.cdn199.com",
        "https://v2.kekecdn.net",
        "https://v2.luchu.org",
        "https://v2.madou.ws",
        "https://v2.papapa.biz",
        "https://v2.tianmtv.com",
    ]

    UA = ("Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36")

    # 实测有独立数据返回的分类 (type 值由站点前端硬编码, 已逐个核对)
    CATS = [
        ("hot", u"热门"),
        ("recent", u"最近更新"),
        ("high", u"高清"),
        ("japan", u"日本AV"),
        ("west", u"欧美风尚"),
        ("torture", u"重口味"),
        ("swag", u"台湾SWAG"),
        ("banana", u"汝工作室"),
        ("pissvids", u"欧美VIP"),
        ("home_91_8", u"91精选"),
        ("home_vip_8", u"国产制片厂"),
        ("home_hot_8", u"国产自拍"),
        ("home_japan_8", u"日本精选"),
        ("home_west_8", u"欧美精选"),
        ("home_torture_8", u"重口精选"),
        ("home_high_8", u"站长推荐"),
        ("home_swag_8", u"SWAG全辑"),
        ("home_banana_8", u"汝工作室精选"),
        ("home_pissvids_8", u"欧美VIP精选"),
    ]

    def __init__(self):
        self.s = None
        self.session = None
        self.sess = None
        self.extend = {}
        self.base = self.GATES[0]
        self.gate_idx = 0
        self.interval = 1.0
        self.img_relay = False
        self.use_proxy = True
        self._last_req = 0.0
        self._relay = _Relay(self)
        self._cache = {}
        self._req_lock = threading.Lock()

    # -------------------------------------------------- 生命周期

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = self._parse_ext(extend)
        if self.extend.get("base"):
            b = str(self.extend["base"]).strip().rstrip("/")
            if not b.startswith("http"):
                b = "https://" + b
            self.base = b
        try:
            self.interval = float(self.extend.get("interval", 1.0))
        except Exception:
            self.interval = 1.0
        if self.interval < 0:
            self.interval = 0.0
        self.img_relay = str(self.extend.get("img", "direct")).lower() == "relay"
        self.use_proxy = str(self.extend.get("proxy", "1")).lower() not in ("0", "false", "no")
        self._build_session()

    def _parse_ext(self, extend):
        if isinstance(extend, dict):
            return dict(extend)
        d = {}
        if isinstance(extend, (list, tuple)) and extend:
            extend = extend[0]
        if not isinstance(extend, text_type):
            return d
        s = extend.strip()
        if not s:
            return d
        if s.startswith("{"):
            try:
                v = json.loads(s)
                if isinstance(v, dict):
                    return v
            except Exception:
                return d
        for part in s.split("|"):
            part = part.strip()
            if not part:
                continue
            if part.startswith("http") and "base" not in d:
                d["base"] = part
            elif "=" in part:
                k, v = part.split("=", 1)
                d[k.strip()] = v.strip()
        return d

    def _build_session(self):
        if requests is None:
            self.s = self.session = self.sess = None
            return
        try:
            s = requests.Session()
            s.headers.update(self._headers())
            self.s = self.session = self.sess = s
        except Exception:
            self.s = self.session = self.sess = None

    def _headers(self):
        return {
            "User-Agent": self.UA,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": self.HOST,
            "Referer": self.HOST + "/",
        }

    def destroy(self):
        self._cache = {}
        return None

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return {}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = str(url).lower()
        for k in (".m3u8", ".mp4", ".flv", ".avi", ".mkv", ".ts"):
            if k in u:
                return True
        return False

    # -------------------------------------------------- 网络

    def _throttle(self):
        if self.interval <= 0:
            return
        with self._req_lock:
            gap = time.time() - self._last_req
            if gap < self.interval:
                time.sleep(self.interval - gap)
            self._last_req = time.time()

    def _post(self, path, tries=3):
        body = {
            "url": path,
            "app": self.APP,
            "version": self.VER,
            "deviceInfo": {},
            "uuid": "novalue",
            "theLink": "novaluenull",
            "isStandalone": False,
        }
        payload = json.dumps(body)
        last = None
        for i in range(tries):
            base = self.GATES[(self.gate_idx + i) % len(self.GATES)]
            try:
                self._throttle()
                txt = self._http_post(base + "/js", payload)
                if not txt:
                    continue
                try:
                    obj = json.loads(txt)
                except Exception:
                    continue
                if isinstance(obj, dict) and "r" in obj:
                    self.gate_idx = (self.gate_idx + i) % len(self.GATES)
                    return self._decrypt(obj["r"])
                if isinstance(obj, dict) and obj.get("blocked"):
                    last = "blocked"
                    continue
                return obj
            except Exception as e:
                last = e
                continue
        if last is not None:
            return None
        return None

    def _http_post(self, url, payload):
        data = _to_bytes(payload)
        if self.s is not None:
            r = self.s.post(url, data=data, timeout=25)
            if r.status_code != 200:
                raise IOError("http %s" % r.status_code)
            return _to_text(r.content)
        req = Request(url, data=data, headers=self._headers())
        resp = urlopen(req, timeout=25)
        return _to_text(resp.read())

    def _get(self, url, referer=None, tries=2):
        """取原始文件 (m3u8 / 图片)。"""
        for i in range(tries):
            try:
                self._throttle()
                hdr = {"User-Agent": self.UA}
                if referer:
                    hdr["Referer"] = referer
                if self.s is not None:
                    r = self.s.get(url, headers=hdr, timeout=25)
                    if r.status_code != 200:
                        raise IOError("http %s" % r.status_code)
                    return r.content
                req = Request(url, headers=hdr)
                return urlopen(req, timeout=25).read()
            except Exception as e:
                # 有些 CDN 会给出偏大的 Content-Length, 读半截报错但数据已到手
                part = getattr(e, "partial", None)
                if part:
                    return part
                if i == tries - 1:
                    return None
        return None

    def _decrypt(self, raw):
        try:
            b = base64.b64decode(_to_bytes(raw))
        except (binascii.Error, ValueError):
            return None
        if not b.startswith(b"Salted__") or len(b) < 32:
            try:
                return json.loads(_to_text(b))
            except Exception:
                return None
        salt = b[8:16]
        ct = b[16:]
        material = evp_bytes_to_key(self.PASS, salt, 48)
        pt = aes_cbc_decrypt(material[:32], material[32:48], ct)
        try:
            return json.loads(_to_text(pt))
        except Exception:
            return None

    # -------------------------------------------------- 数据整形

    def _pic(self, vid, item=None):
        thumbs = []
        if isinstance(item, dict):
            thumbs = item.get("thumbnails") or item.get("thumbNails") or []
        if thumbs:
            pic = self._fix_url(thumbs[0])
        else:
            pic = "https://tp.helloye.com/%s.jpg" % vid
        if self.img_relay:
            return self._relay_url("img", pic)
        return pic

    def _fix_url(self, u):
        if not u:
            return ""
        u = _to_text(u).strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        return urljoin(self.HOST + "/", u)

    # 未成年条目一律不进列表 (年龄 <18 的直接丢; 明确写 18/19 岁的不误杀)
    _AGE_RE = re.compile(r"(\d{1,2})\s*岁")

    _MINOR_WORDS = (u"未成年", u"幼女", u"女童", u"小学生", u"初中生", u"初一", u"初二",
                    u"初三", u"儿童色情", u"萝莉幼", u"萝莉妹")

    def _is_minor(self, title):
        t = _to_text(title or "")
        if not t:
            return False
        for m in self._AGE_RE.finditer(t):
            try:
                if int(m.group(1)) < 18:
                    return True
            except Exception:
                pass
        for w in self._MINOR_WORDS:
            if w in t:
                return True
        return False

    def _video_item(self, v):
        try:
            vid = _to_text(v.get("id") or v.get("vId") or "")
            name = _to_text(v.get("title") or "")
            if not name:
                name = _to_text(v.get("title_en") or vid)
            if self._is_minor(name) or self._is_minor(_to_text(v.get("title_en") or "")):
                return None
            return {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": self._pic(vid, v),
                "vod_remarks": _to_text(v.get("size") or v.get("durationStr") or ""),
            }
        except Exception:
            return None

    def _unwrap(self, data):
        """兼容 服务端可能返回 {list:[...]} 或 裸数组。"""
        if isinstance(data, dict):
            for k in ("list", "videos", "data", "sevenVideos", "result"):
                if isinstance(data.get(k), list):
                    return data[k]
            return []
        if isinstance(data, list):
            return data
        return []

    # -------------------------------------------------- 13 接口

    def homeContent(self, filter=None):
        cats = [{"type_id": t, "type_name": n} for t, n in self.CATS]
        return {"class": cats, "filters": {}}

    def homeVideoContent(self):
        lst = []
        for t, _n in self.CATS[:4]:
            for it in self._list(t, 1):
                lst.append(it)
        return {"list": lst}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        tid = _to_text(tid or self.CATS[0][0])
        try:
            pg = int(str(pg))
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        lst = self._list(tid, pg)
        return {"list": lst, "page": pg, "pagecount": pg + 1 if lst else pg,
                "limit": 24, "total": len(lst)}

    def _list(self, tid, pg):
        data = self._post("/sevenVideos?page=%d&type=%s" % (pg, tid))
        raw = self._unwrap(data)
        out = []
        seen = set()
        for v in raw:
            if not isinstance(v, dict):
                continue
            it = self._video_item(v)
            if not it or not it["vod_id"]:
                continue
            if it["vod_id"] in seen:
                continue
            seen.add(it["vod_id"])
            out.append(it)
        return out

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = _to_text(vid or "")
        vid = vid.split("|")[0].split("$")[0]
        if not vid:
            return {"list": []}
        d = self._detail(vid)
        if not d:
            return {"list": []}
        name = _to_text(d.get("title") or d.get("title_en") or vid)
        if self._is_minor(name) or self._is_minor(_to_text(d.get("title_en") or "")):
            return {"list": []}
        pics = d.get("thumbnails") or []
        pic = self._pic(vid, d) if pics else "https://tp.helloye.com/%s.jpg" % vid
        lines = d.get("m3u8s") or []
        if not lines and d.get("m3u8"):
            lines = [d["m3u8"]]
        froms = []
        urls = []
        if len(lines) > 1:
            for i, u in enumerate(lines):
                froms.append(u"线路%d" % (i + 1))
                urls.append(u"正片$%s" % vid)
        else:
            froms.append(u"theporny")
            urls.append(u"正片$%s" % vid)
        cont = u"片名: %s\n主演/来源: %s\n时长: %s\n大小: %s\n播放: %s\n时间: %s" % (
            name,
            _to_text(d.get("user") or ""),
            _to_text(d.get("durationStr") or ""),
            _to_text(d.get("size") or ""),
            _to_text(d.get("views") or ""),
            _to_text(d.get("time") or ""),
        )
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_content": cont,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }]}

    def _detail(self, vid, ttl=120):
        now = time.time()
        c = self._cache.get(vid)
        if c and now - c[0] < ttl:
            return c[1]
        d = self._post("/sevenVideos/" + quote(vid))
        if isinstance(d, dict) and (d.get("m3u8s") or d.get("title")):
            self._cache[vid] = (now, d)
            return d
        return d if isinstance(d, dict) else None

    def searchContent(self, key, quick=False, pg="1"):
        key = _to_text(key or "").strip()
        try:
            pg = int(str(pg))
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        if not key:
            return {"list": [], "page": pg, "pagecount": pg}
        # 实测: /sevenVideos/s 才认页码; /searchSevenVideos 只回最新一批, 翻页无效
        data = self._post("/sevenVideos/s?page=%d&q=%s&sortBy=time" % (pg, quote(key)))
        raw = self._unwrap(data)
        if not raw:
            data = self._post("/searchSevenVideos?page=%d&keywords=%s" % (pg, quote(key)))
            raw = self._unwrap(data)
        out = []
        seen = set()
        for v in raw:
            if not isinstance(v, dict):
                continue
            it = self._video_item(v)
            if not it or not it["vod_id"] or it["vod_id"] in seen:
                continue
            seen.add(it["vod_id"])
            out.append(it)
        return {"list": out, "page": pg, "pagecount": pg + 1 if out else pg, "limit": 24,
                "total": len(out)}

    def playerContent(self, flag, ids, vipFlags=None):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = _to_text(vid or "").split("$")[-1].split("|")[0]
        url = self._play_url(vid)
        header = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
        }
        if not url:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": header}
        if self.use_proxy:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": self._relay_url("m3u8", url),
                    "header": header, "format": "application/x-mpegURL"}
        return {"parse": 0, "jx": 0, "playUrl": "", "url": url,
                "header": header, "format": "application/x-mpegURL"}

    def _play_url(self, vid):
        d = self._detail(vid, ttl=60)
        if not d:
            return ""
        lines = d.get("m3u8s") or []
        if not lines and d.get("m3u8"):
            lines = [d["m3u8"]]
        for u in lines:
            u = self._fix_url(u)
            if u:
                return u
        return ""

    # -------------------------------------------------- 本地中转

    def _relay_url(self, kind, target):
        try:
            port = self._relay.ensure()
        except Exception:
            return target
        raw = base64.b64encode(_to_bytes(target))
        raw = raw.replace(b"+", b"-").replace(b"/", b"_").rstrip(b"=")
        return "http://127.0.0.1:%d/%s?u=%s" % (port, kind, _to_text(raw))

    def _relay_dispatch(self, target):
        try:
            q = target.split("?", 1)[1] if "?" in target else ""
            kind = "m3u8"
            if target.startswith("/img"):
                kind = "img"
            val = ""
            for kv in q.split("&"):
                if kv.startswith("u="):
                    val = unquote(kv[2:])
                    break
            if not val:
                return b"no url", "text/plain", 400
            pad = "=" * (-len(val) % 4)
            real = _to_text(base64.b64decode(_to_bytes(val.replace("-", "+").replace("_", "/") + pad)))
            if kind == "img":
                data = self._get(real, referer=self.HOST + "/")
                if not data:
                    return b"", "image/jpeg", 404
                mime = "image/jpeg"
                if data[:8].startswith(b"\x89PNG"):
                    mime = "image/png"
                elif data[:4] == b"RIFF":
                    mime = "image/webp"
                return data, mime, 200
            raw = self._get(real, referer=self.HOST + "/")
            if not raw:
                return b"", "application/vnd.apple.mpegurl", 502
            clean = self._clean_m3u8(_to_text(raw), real)
            return _to_bytes(clean), "application/vnd.apple.mpegurl", 200
        except Exception:
            return b"", "application/vnd.apple.mpegurl", 500

    def _clean_m3u8(self, text, base):
        out = []
        for line in text.splitlines():
            s = line.strip()
            if not s:
                out.append(line)
                continue
            if s.startswith("#"):
                # 只动 #EXT-X-KEY / #EXT-X-MAP 里的 URI, 其余控制标签一律原样保留
                if "URI=" in s:
                    s = re.sub(r'URI="([^"]+)"',
                               lambda m: 'URI="%s"' % urljoin(base, m.group(1)), s)
                out.append(s)
                continue
            out.append(urljoin(base, s))
        return "\n".join(out)

    def localProxy(self, param):
        try:
            if isinstance(param, text_type):
                try:
                    param = json.loads(param)
                except Exception:
                    param = {}
            if not isinstance(param, dict):
                param = {}
            target = param.get("url") or param.get("path") or ""
            if not target:
                return [404, "text/plain", b"Not Found", {}]
            body, mime, code = self._relay_dispatch(_to_text(target))
            return [code, mime, body, {"Access-Control-Allow-Origin": "*"}]
        except Exception:
            return [500, "text/plain", b"error", {}]


# ---------------------------------------------------------------- CLI 自测

def _main(argv):
    import sys

    sp = Spider()
    sp.init("")
    cmd = argv[1] if len(argv) > 1 else "nav"
    if cmd == "nav":
        for c in sp.homeContent().get("class", []):
            print("%-18s %s" % (c["type_id"], c["type_name"]))
    elif cmd == "list":
        tid = argv[2] if len(argv) > 2 else "hot"
        pg = argv[3] if len(argv) > 3 else "1"
        r = sp.categoryContent(tid, pg)
        print("page=%s n=%d" % (r["page"], len(r["list"])))
        for v in r["list"][:6]:
            print("  %-14s %s" % (v["vod_id"], v["vod_name"][:44]))
    elif cmd == "detail":
        r = sp.detailContent([argv[2]])
        if r["list"]:
            d = r["list"][0]
            print(d["vod_name"])
            print(d["vod_content"])
            print("play_url:", d["vod_play_url"])
    elif cmd == "play":
        vid = argv[2]
        r = sp.playerContent("", vid, [])
        print("url:", r["url"])
        if not r["url"].startswith("http://127.0.0.1"):
            print("header:", r["header"])
    elif cmd == "search":
        r = sp.searchContent(argv[2] if len(argv) > 2 else u"麻豆", False, "1")
        print("n=%d" % len(r["list"]))
        for v in r["list"][:6]:
            print("  %-14s %s" % (v["vod_id"], v["vod_name"][:44]))
    else:
        print(__doc__)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv))
