# -*- coding: utf-8 -*-
"""
TVBox Spider - 禁忌短剧 / jinji.video 剧场板块
================================================================
目标页: https://jinji.video/theater-adults-shortdrama  (剧场 → 成人短剧)

站点是 Next.js(App Router)前端 + 私有加密 API:
    POST https://<host>/api/<path>
    Header: content-type: application/octet-stream
            version: 1.0.0
            deviceType: web
            time:     <unix 秒>
            requestId: <uuid4 去掉横线,32 位 hex>
    Body:   iv(16B) || AES-256-CBC( gzip( utf8(JSON) ) )

    AES key = HMAC-SHA256(key=API_WEB_KEY, msg=unhexlify(requestId))   32 字节
    明文 JSON = {deviceId, token, domain, shareCode, channel, ip, data}
    响应: 若首字节是 { 或 [ 则为明文 JSON;否则同样是 iv||密文,用同一把 key 解

本文件为**单文件、零第三方依赖**实现(自带纯 Python AES-256-CBC),
py3 可直接跑,亦兼容 py2/Jython(不使用 f-string / 仅用 % 格式化)。

------------------------------------------------------------------
CLI 用法(不进 TVBox 也能直接跑):
    python3 jinji_theater.py nav                      # 列出剧场全部分类
    python3 jinji_theater.py list --tid 14 --page 1   # 拉列表
    python3 jinji_theater.py search 护士 --page 1     # 搜索
    python3 jinji_theater.py detail f525cb2f0866807f  # 详情 + 剧集
    python3 jinji_theater.py play f525cb2f0866807f 1  # 取第 1 集播放地址
    python3 jinji_theater.py probe                    # 自检(协议/接口)

extend 参数(源配置 ext 字段,用 | 分隔,用不到哪段就删):
    https://jinji.video|token=你的会话|device=自定义设备号|interval=1.2|img=source|proxy=0

    token    : 你自己账号的会话(token_userid),填了就用你的权限拉数据(可选)
    device   : 自定义设备号(可选,不填自动生成)
    interval : 请求间隔秒,默认 1.2(站点有频控,别调太小)
    img      : 封面图取值 source(默认,真图 jpg) / raw(站点原始 bnc 地址)
    proxy    : 1 = 播放地址走本机 localProxy(m3u8 重写);默认 0 直连
"""

import base64
import binascii
import gzip
import hashlib
import hmac
import io
import json
import os
import random
import re
import socket
import struct
import sys
import threading
import time
import uuid

try:
    from urllib.parse import urljoin, quote, unquote, urlencode
except ImportError:  # py2 / Jython
    from urlparse import urljoin
    from urllib import quote, unquote, urlencode

try:
    import requests
except ImportError:
    requests = None

try:
    from urllib.request import Request as _URLRequest, build_opener as _build_opener, HTTPRedirectHandler as _RedirHandler
    from urllib.error import HTTPError as _HTTPError, URLError as _URLError
except ImportError:  # py2
    from urllib2 import Request as _URLRequest, build_opener as _build_opener
    from urllib2 import HTTPRedirectHandler as _RedirHandler
    from urllib2 import HTTPError as _HTTPError, URLError as _URLError

try:
    import ssl as _ssl
except ImportError:
    _ssl = None


# ==================================================================
# 站点常量
# ==================================================================
DEFAULT_HOST = "https://jinji.video"
API_WEB_KEY = "7961beb44246e3012ce228d6b5ced05a"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

THEATER_BOARD = "theater"          # 剧场板块的 board_id
PAGE_SIZE = 24

# 未成年相关条目剔除(命中即丢;成年年龄如 18/19 岁不误杀)
_UNDERAGE_RE = re.compile(
    u"(1[0-7]\\s*岁|未成年|初中生|小学生|幼女|幼齿|萝莉|正太|男童|女童|童颜巨乳)"
)


# ==================================================================
# 纯 Python AES-256-CBC(无第三方依赖)
# 表结构照 rijndael-alg-fst 的 T-table 写法,自检见 _aes_selftest()
# ==================================================================
def _build_aes_tables():
    exp = [0] * 512
    log = [0] * 256
    x = 1
    for i in range(255):
        exp[i] = x
        log[x] = i
        x ^= ((x << 1) ^ (0x11B if (x & 0x80) else 0)) & 0xFF
    for i in range(255, 512):
        exp[i] = exp[i - 255]

    def _rotl8(b, n):
        return ((b << n) | (b >> (8 - n))) & 0xFF

    sbox = [0] * 256
    inv_sbox = [0] * 256
    for a in range(256):
        b = 0 if a == 0 else exp[255 - log[a]]
        s = b ^ _rotl8(b, 1) ^ _rotl8(b, 2) ^ _rotl8(b, 3) ^ _rotl8(b, 4) ^ 0x63
        sbox[a] = s
        inv_sbox[s] = a

    def mul(a, b):
        if a == 0 or b == 0:
            return 0
        return exp[(log[a] + log[b]) % 255]

    te0 = [0] * 256
    te1 = [0] * 256
    te2 = [0] * 256
    te3 = [0] * 256
    td0 = [0] * 256
    td1 = [0] * 256
    td2 = [0] * 256
    td3 = [0] * 256
    for i in range(256):
        s = sbox[i]
        si = inv_sbox[i]
        te0[i] = (mul(s, 2) << 24) | (s << 16) | (s << 8) | mul(s, 3)
        te1[i] = (mul(s, 3) << 24) | (mul(s, 2) << 16) | (s << 8) | s
        te2[i] = (s << 24) | (mul(s, 3) << 16) | (mul(s, 2) << 8) | s
        te3[i] = (s << 24) | (s << 16) | (mul(s, 3) << 8) | mul(s, 2)
        td0[i] = (mul(si, 14) << 24) | (mul(si, 9) << 16) | (mul(si, 13) << 8) | mul(si, 11)
        td1[i] = (mul(si, 11) << 24) | (mul(si, 14) << 16) | (mul(si, 9) << 8) | mul(si, 13)
        td2[i] = (mul(si, 13) << 24) | (mul(si, 11) << 16) | (mul(si, 14) << 8) | mul(si, 9)
        td3[i] = (mul(si, 9) << 24) | (mul(si, 13) << 16) | (mul(si, 11) << 8) | mul(si, 14)
    return sbox, inv_sbox, (te0, te1, te2, te3), (td0, td1, td2, td3)


SBOX, INV_SBOX, _TE, _TD = _build_aes_tables()
TE0, TE1, TE2, TE3 = _TE
TD0, TD1, TD2, TD3 = _TD
RCON = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36, 0x6C, 0xD8, 0xAB, 0x4D]


def _pack4(b):
    return (b[0] << 24) | (b[1] << 16) | (b[2] << 8) | b[3]


def _unpack4(w):
    return [(w >> 24) & 0xFF, (w >> 16) & 0xFF, (w >> 8) & 0xFF, w & 0xFF]


def _sub_word(w):
    return ((SBOX[(w >> 24) & 0xFF] << 24) | (SBOX[(w >> 16) & 0xFF] << 16) |
            (SBOX[(w >> 8) & 0xFF] << 8) | SBOX[w & 0xFF])


def _expand_key(key):
    nk = len(key) // 4
    nr = nk + 6
    total = 4 * (nr + 1)
    w = [0] * total
    for i in range(nk):
        w[i] = _pack4(key[4 * i:4 * i + 4])
    for i in range(nk, total):
        t = w[i - 1]
        if i % nk == 0:
            t = (((t << 8) | (t >> 24)) & 0xFFFFFFFF)
            t = _sub_word(t) ^ (RCON[i // nk - 1] << 24)
        elif nk > 6 and i % nk == 4:
            t = _sub_word(t)
        w[i] = w[i - nk] ^ t
    return w, nr


def _inv_mix_word(w):
    """对一个轮密钥字做 InvMixColumns(Td 表 + S 盒,等价于 OpenSSL 的 Te4 查表)"""
    return (TD0[SBOX[(w >> 24) & 0xFF]] ^ TD1[SBOX[(w >> 16) & 0xFF]] ^
            TD2[SBOX[(w >> 8) & 0xFF]] ^ TD3[SBOX[w & 0xFF]]) & 0xFFFFFFFF


def _expand_key_dec(key):
    """解密专用轮密钥:轮密钥逆序 + 中间轮做 InvMixColumns(等价逆密码)"""
    w, nr = _expand_key(key)
    total = 4 * (nr + 1)
    r = [0] * total
    for i in range(0, total, 4):
        j = total - 4 - i
        r[i] = w[j]
        r[i + 1] = w[j + 1]
        r[i + 2] = w[j + 2]
        r[i + 3] = w[j + 3]
    for i in range(4, 4 * nr):
        r[i] = _inv_mix_word(r[i])
    return r, nr


def _encrypt_block(block, w, nr):
    s0 = _pack4(block[0:4]) ^ w[0]
    s1 = _pack4(block[4:8]) ^ w[1]
    s2 = _pack4(block[8:12]) ^ w[2]
    s3 = _pack4(block[12:16]) ^ w[3]
    for r in range(1, nr):
        k = 4 * r
        t0 = (TE0[s0 >> 24] ^ TE1[(s1 >> 16) & 0xFF] ^ TE2[(s2 >> 8) & 0xFF] ^ TE3[s3 & 0xFF]) ^ w[k]
        t1 = (TE0[s1 >> 24] ^ TE1[(s2 >> 16) & 0xFF] ^ TE2[(s3 >> 8) & 0xFF] ^ TE3[s0 & 0xFF]) ^ w[k + 1]
        t2 = (TE0[s2 >> 24] ^ TE1[(s3 >> 16) & 0xFF] ^ TE2[(s0 >> 8) & 0xFF] ^ TE3[s1 & 0xFF]) ^ w[k + 2]
        t3 = (TE0[s3 >> 24] ^ TE1[(s0 >> 16) & 0xFF] ^ TE2[(s1 >> 8) & 0xFF] ^ TE3[s2 & 0xFF]) ^ w[k + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
    k = 4 * nr
    o0 = (((SBOX[s0 >> 24] << 24) | (SBOX[(s1 >> 16) & 0xFF] << 16) |
           (SBOX[(s2 >> 8) & 0xFF] << 8) | SBOX[s3 & 0xFF]) ^ w[k]) & 0xFFFFFFFF
    o1 = (((SBOX[s1 >> 24] << 24) | (SBOX[(s2 >> 16) & 0xFF] << 16) |
           (SBOX[(s3 >> 8) & 0xFF] << 8) | SBOX[s0 & 0xFF]) ^ w[k + 1]) & 0xFFFFFFFF
    o2 = (((SBOX[s2 >> 24] << 24) | (SBOX[(s3 >> 16) & 0xFF] << 16) |
           (SBOX[(s0 >> 8) & 0xFF] << 8) | SBOX[s1 & 0xFF]) ^ w[k + 2]) & 0xFFFFFFFF
    o3 = (((SBOX[s3 >> 24] << 24) | (SBOX[(s0 >> 16) & 0xFF] << 16) |
           (SBOX[(s1 >> 8) & 0xFF] << 8) | SBOX[s2 & 0xFF]) ^ w[k + 3]) & 0xFFFFFFFF
    return _unpack4(o0) + _unpack4(o1) + _unpack4(o2) + _unpack4(o3)


def _decrypt_block(block, w, nr):
    s0 = _pack4(block[0:4]) ^ w[0]
    s1 = _pack4(block[4:8]) ^ w[1]
    s2 = _pack4(block[8:12]) ^ w[2]
    s3 = _pack4(block[12:16]) ^ w[3]
    for k in range(4, 4 * nr, 4):
        t0 = (TD0[s0 >> 24] ^ TD1[(s3 >> 16) & 0xFF] ^ TD2[(s2 >> 8) & 0xFF] ^ TD3[s1 & 0xFF]) ^ w[k]
        t1 = (TD0[s1 >> 24] ^ TD1[(s0 >> 16) & 0xFF] ^ TD2[(s3 >> 8) & 0xFF] ^ TD3[s2 & 0xFF]) ^ w[k + 1]
        t2 = (TD0[s2 >> 24] ^ TD1[(s1 >> 16) & 0xFF] ^ TD2[(s0 >> 8) & 0xFF] ^ TD3[s3 & 0xFF]) ^ w[k + 2]
        t3 = (TD0[s3 >> 24] ^ TD1[(s2 >> 16) & 0xFF] ^ TD2[(s1 >> 8) & 0xFF] ^ TD3[s0 & 0xFF]) ^ w[k + 3]
        s0, s1, s2, s3 = t0, t1, t2, t3
    o0 = (((INV_SBOX[s0 >> 24] << 24) | (INV_SBOX[(s3 >> 16) & 0xFF] << 16) |
           (INV_SBOX[(s2 >> 8) & 0xFF] << 8) | INV_SBOX[s1 & 0xFF]) ^ w[4 * nr]) & 0xFFFFFFFF
    o1 = (((INV_SBOX[s1 >> 24] << 24) | (INV_SBOX[(s0 >> 16) & 0xFF] << 16) |
           (INV_SBOX[(s3 >> 8) & 0xFF] << 8) | INV_SBOX[s2 & 0xFF]) ^ w[4 * nr + 1]) & 0xFFFFFFFF
    o2 = (((INV_SBOX[s2 >> 24] << 24) | (INV_SBOX[(s1 >> 16) & 0xFF] << 16) |
           (INV_SBOX[(s0 >> 8) & 0xFF] << 8) | INV_SBOX[s3 & 0xFF]) ^ w[4 * nr + 2]) & 0xFFFFFFFF
    o3 = (((INV_SBOX[s3 >> 24] << 24) | (INV_SBOX[(s2 >> 16) & 0xFF] << 16) |
           (INV_SBOX[(s1 >> 8) & 0xFF] << 8) | INV_SBOX[s0 & 0xFF]) ^ w[4 * nr + 3]) & 0xFFFFFFFF
    return _unpack4(o0) + _unpack4(o1) + _unpack4(o2) + _unpack4(o3)


def aes_cbc_encrypt(data, key, iv):
    """严格 PKCS7 填充的 AES-CBC 加密,返回 bytes"""
    w, nr = _expand_key(key)
    pad = 16 - (len(data) % 16)
    data = data + bytes(bytearray([pad]) * pad) if not isinstance(data, str) else \
        data + bytes(bytearray([pad]) * pad)
    out = bytearray()
    prev = list(iv)
    for off in range(0, len(data), 16):
        blk = list(bytearray(data[off:off + 16]))
        blk = [blk[i] ^ prev[i] for i in range(16)]
        prev = _encrypt_block(blk, w, nr)
        out.extend(bytearray(prev))
    return bytes(out)


def aes_cbc_decrypt(data, key, iv):
    """AES-CBC 解密 + 严格 PKCS7 校验,返回 bytes"""
    if len(data) == 0 or len(data) % 16 != 0:
        raise ValueError("aes: 密文长度非法")
    w, nr = _expand_key_dec(key)
    out = bytearray()
    prev = list(iv)
    for off in range(0, len(data), 16):
        blk = list(bytearray(data[off:off + 16]))
        plain = _decrypt_block(blk, w, nr)
        plain = [plain[i] ^ prev[i] for i in range(16)]
        prev = blk
        out.extend(bytearray(plain))
    pad = out[-1]
    if pad < 1 or pad > 16:
        raise ValueError("aes: PKCS7 填充非法")
    for i in range(len(out) - pad, len(out)):
        if out[i] != pad:
            raise ValueError("aes: PKCS7 填充非法")
    return bytes(out[:len(out) - pad])


def _aes_selftest():
    """用 FIPS-197 官方向量自检 AES-128/256"""
    ok = True
    k128 = binascii.unhexlify("000102030405060708090a0b0c0d0e0f")
    p = binascii.unhexlify("00112233445566778899aabbccddeeff")
    c = aes_cbc_encrypt(p, k128, bytes(bytearray(16)))
    ok = ok and c[:16] == binascii.unhexlify("69c4e0d86a7b0430d8cdb78070b4c55a")
    k256 = binascii.unhexlify("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f")
    c2 = aes_cbc_encrypt(p, k256, bytes(bytearray(16)))
    ok = ok and c2[:16] == binascii.unhexlify("8ea2b7ca516745bfeafc49904b496089")
    back = aes_cbc_decrypt(c2, k256, bytes(bytearray(16)))
    ok = ok and back == p
    return ok


# ==================================================================
# HTTP 层(requests 优先,否则 urllib 降级)
# ==================================================================
_SSL_CTX = None
if _ssl is not None:
    try:
        _SSL_CTX = _ssl.create_default_context()
        _SSL_CTX.check_hostname = False
        _SSL_CTX.verify_mode = _ssl.CERT_NONE
    except Exception:
        _SSL_CTX = None


def _http(method, url, headers=None, body=None, timeout=25):
    """返回 (status, headers_dict, bytes) —— 失败返回 (0, {}, b'')"""
    headers = headers or {}
    if requests is not None:
        try:
            requests.packages.urllib3.disable_warnings()
        except Exception:
            pass
        try:
            r = requests.request(method, url, headers=headers, data=body,
                                 timeout=timeout, verify=False)
            return r.status_code, dict(r.headers), r.content
        except Exception:
            return 0, {}, b""
    try:
        req = _URLRequest(url, data=body, headers=headers, method=method)
        opener = _build_opener()
        if _SSL_CTX is not None:
            import urllib.request as _ur
            handler = _ur.HTTPSHandler(context=_SSL_CTX)
            opener = _build_opener(handler)
        resp = opener.open(req, timeout=timeout)
        return getattr(resp, "code", 200), dict(resp.headers), resp.read()
    except _HTTPError as e:
        try:
            return e.code, dict(e.headers), e.read()
        except Exception:
            return e.code, {}, b""
    except Exception:
        return 0, {}, b""


# ==================================================================
# Spider
# ==================================================================
_GLOBAL = {
    "device_id": "",
    "session": "",
    "ts": 0,
}


def _now():
    return int(time.time())


def _gzip_bytes(raw):
    buf = io.BytesIO()
    f = gzip.GzipFile(fileobj=buf, mode="wb")
    f.write(raw)
    f.close()
    return buf.getvalue()


def _gunzip_bytes(raw):
    return gzip.GzipFile(fileobj=io.BytesIO(raw)).read()


def _b(x):
    """py2/py3 统一的 bytes 化"""
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    return x.encode("utf-8")


def _s(x):
    """py2/py3 统一的 str 化"""
    if isinstance(x, bytes):
        return x.decode("utf-8", "ignore")
    return x


def _is_underage(text):
    try:
        return bool(_UNDERAGE_RE.search(_s(text or u"")))
    except Exception:
        return False


class Spider(object):

    # ---------------- 生命周期 ----------------
    def __init__(self):
        self.host = DEFAULT_HOST
        self.hostname = "jinji.video"
        self.device_id = ""
        self.session = ""          # token_userid
        self.interval = 1.2
        self.img_mode = "source"
        self.use_proxy = False
        self._lock = threading.Lock()
        self._last_req = 0.0
        self._nav_cache = None
        self._detail_cache = {}
        self._ua = UA
        # 三个会话别名(契约要求)
        self.s = None
        self.session_obj = None
        self.sess = None

    def getDependence(self):
        return []

    def init(self, extend=""):
        ext = {}
        try:
            if isinstance(extend, dict):
                ext = extend
            elif isinstance(extend, str) and extend.strip():
                raw = extend.strip()
                if raw.startswith("{"):
                    ext = json.loads(raw)
                else:
                    parts = raw.split("|")
                    if parts and parts[0].startswith("http"):
                        self.host = parts[0].rstrip("/")
                        parts = parts[1:]
                    for p in parts:
                        if not p:
                            continue
                        if "=" in p:
                            k, v = p.split("=", 1)
                            ext[k.strip()] = v.strip()
        except Exception:
            ext = {}

        if ext.get("host"):
            self.host = str(ext["host"]).rstrip("/")
        try:
            self.hostname = self.host.split("//", 1)[1].split("/", 1)[0]
        except Exception:
            self.hostname = "jinji.video"

        try:
            self.interval = float(ext.get("interval", 1.2))
        except Exception:
            self.interval = 1.2
        if self.interval < 0.3:
            self.interval = 0.3

        self.img_mode = str(ext.get("img", "source") or "source").lower()
        self.use_proxy = str(ext.get("proxy", "0")) in ("1", "true", "yes", "y", "on")

        if ext.get("device"):
            self.device_id = str(ext["device"])
        elif _GLOBAL.get("device_id"):
            self.device_id = _GLOBAL["device_id"]
        else:
            self.device_id = "web_" + uuid.uuid4().hex
            _GLOBAL["device_id"] = self.device_id

        if ext.get("token"):
            self.session = str(ext["token"]).strip()
            _GLOBAL["session"] = self.session
            _GLOBAL["ts"] = _now()
        else:
            self.session = _GLOBAL.get("session") or ""

        self.s = self.session_obj = self.sess = self
        try:
            self.ensure_session()
        except Exception:
            pass
        return None

    def destroy(self):
        return None

    # ---------------- 会话 ----------------
    def ensure_session(self, force=False):
        if self.session and not force:
            return self.session
        with self._lock:
            if self.session and not force:
                return self.session
            data = self._api("/login/device", {}, retry=2, no_auth=True)
            d = (data or {}).get("data") or {}
            tok = d.get("token")
            uid = d.get("user_id")
            if tok and uid:
                self.session = "%s_%s" % (tok, uid)
                _GLOBAL["session"] = self.session
                _GLOBAL["ts"] = _now()
            return self.session

    # ---------------- 网络 ----------------
    def _throttle(self):
        gap = time.time() - self._last_req
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self._last_req = time.time()

    def _api(self, path, data=None, retry=3, timeout=20, no_auth=False):
        """加密 API 调用;返回解析后的 dict,失败返回 None"""
        for attempt in range(max(1, retry)):
            try:
                self._throttle()
                rid = uuid.uuid4().hex
                key = hmac.new(_b(API_WEB_KEY), binascii.unhexlify(rid), hashlib.sha256).digest()
                payload = {
                    "deviceId": self.device_id,
                    "token": "" if no_auth else (self.session or ""),
                    "domain": self.hostname,
                    "shareCode": "",
                    "channel": "web",
                    "ip": "",
                    "data": data if data is not None else {},
                }
                raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                plain = _gzip_bytes(_b(raw))
                iv = bytes(bytearray([random.randint(0, 255) for _ in range(16)]))
                body = iv + aes_cbc_encrypt(plain, key, iv)

                headers = {
                    "User-Agent": self._ua,
                    "content-type": "application/octet-stream",
                    "version": "1.0.0",
                    "deviceType": "web",
                    "time": str(_now()),
                    "requestId": rid,
                    "Origin": self.host,
                    "Referer": self.host + "/",
                    "Accept": "*/*",
                }
                if not no_auth and self.session:
                    headers["sessionid"] = self.session
                    headers["token"] = self.session

                status, _, raw_resp = _http("POST", self.host + "/api" + path,
                                            headers=headers, body=body, timeout=timeout)
                if status != 200 or not raw_resp:
                    time.sleep(0.8 * (attempt + 1))
                    continue

                if raw_resp[0:1] in (b"{", b"["):
                    out = json.loads(_s(raw_resp))
                else:
                    if len(raw_resp) < 32:
                        time.sleep(0.6)
                        continue
                    dec = aes_cbc_decrypt(raw_resp[16:], key, raw_resp[:16])
                    out = json.loads(_s(_gunzip_bytes(dec)))

                err = out.get("errorCode")
                if err in (2002, 2003) and not no_auth:
                    self.session = ""
                    self.ensure_session()
                    continue
                return out
            except Exception:
                time.sleep(0.6 * (attempt + 1))
        return None

    def _get(self, url, headers=None, timeout=25):
        h = {"User-Agent": self._ua, "Referer": self.host + "/"}
        if headers:
            h.update(headers)
        status, hdr, body = _http("GET", url, headers=h, timeout=timeout)
        return status, hdr, body

    # ---------------- 字段工具 ----------------
    def _abs(self, u):
        u = _s(u or "")
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if not u.startswith("/"):
            u = "/" + u
        return self.host + u

    def _pic(self, it):
        it = it or {}
        keys = ("img_x_source", "img_y_source", "img_x", "img_y", "img", "seo_image_url")
        if self.img_mode == "raw":
            keys = ("img_x", "img_y", "img", "img_x_source", "img_y_source")
        first = ""
        for k in keys:
            v = it.get(k) or ""
            if not v:
                continue
            if not first:
                first = v
            if not v.endswith(".bnc"):
                return v
        return first

    @staticmethod
    def _num(v, default=0):
        try:
            return int(str(v).strip())
        except Exception:
            return default

    def _item(self, it):
        """列表项 -> TVBox 卡片"""
        vid = _s(it.get("drama_id") or it.get("id") or "")
        name = _s(it.get("name") or "")
        if not vid or not name or _is_underage(name):
            return None
        if it.get("type") in ("ad", "app"):
            return None
        remark_bits = []
        ep_total = _s(it.get("episode_total") or it.get("episode_count") or "")
        if ep_total:
            remark_bits.append(u"全%s集" % ep_total)
        pay = _s(it.get("pay_type") or "")
        locked = (it.get("is_locked") == "y") or (it.get("can_watch") is False)
        if pay == "free" and not locked:
            remark_bits.append(u"✅免费")
        elif locked:
            remark_bits.append(u"🔒VIP试看")
        else:
            remark_bits.append(u"✅可播")
        if it.get("duration") and re.match(r"^\d{1,3}:\d{2}", _s(it.get("duration"))):
            remark_bits.append(_s(it.get("duration")))
        tags = it.get("tags") or []
        if isinstance(tags, list) and tags:
            t = _s((tags[0] or {}).get("name") or "")
            if t:
                remark_bits.append(t)
        return {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._pic(it),
            "vod_remarks": u" · ".join([x for x in remark_bits if x]),
        }

    # ---------------- 分类 ----------------
    def _navs(self, force=False):
        if self._nav_cache is not None and not force:
            return self._nav_cache
        out = []
        res = self._api("/movie/boardNav", {"id": THEATER_BOARD}, retry=3)
        if res and res.get("status") == "y":
            data = res.get("data") or {}
            for it in (data.get("items") or []):
                tid = _s(it.get("id"))
                name = _s(it.get("name"))
                if not tid or not name:
                    continue
                out.append({"tid": tid, "name": name, "code": _s(it.get("code")),
                            "mode": _s(it.get("module_mode"))})
        self._nav_cache = out
        return out

    def homeContent(self, filter=None):
        cls = [{"type_id": "all", "type_name": u"🔥 剧场全部"}]
        for n in self._navs():
            cls.append({"type_id": n["tid"], "type_name": n["name"]})
        filters = {}
        sort_vals = [
            {"n": u"默认", "v": ""},
            {"n": u"最热", "v": "hot"},
            {"n": u"最新", "v": "new"},
            {"n": u"最多观看", "v": "click"},
            {"n": u"收藏最多", "v": "favorite"},
        ]
        for c in cls:
            filters[c["type_id"]] = [{"key": "order", "name": u"排序", "value": sort_vals}]
        return {"class": cls, "filters": filters}

    def homeVideoContent(self):
        items = self._list("14", 1, 12, "")
        return {"list": items}

    def _list(self, tid, pg, size, order):
        return self._list_page(tid, pg, size, order)[0]

    def _list_page(self, tid, pg, size, order):
        """返回 (TVBox 条目, 原始 data)。站点 total/last_page 是自增假字段,判尾只认实测。"""
        body = {"page": pg, "page_size": size}
        if tid and tid != "all":
            body["board_id"] = THEATER_BOARD
            body["nav_id"] = self._num(tid)
        if order:
            body["order"] = order
        res = self._api("/search/movie", body, retry=3, timeout=25)
        if not res or res.get("status") != "y":
            return [], {}
        data = res.get("data") or {}
        # 越界时站点会回卷到第 1 页,按请求页号对不上处理
        rp = _s(data.get("current_page") or data.get("page") or "")
        if rp and self._num(rp, 0) and self._num(rp, 0) != pg and pg > 1:
            return [], data
        raw = data.get("items") or data.get("data") or []
        out = []
        seen = set()
        for it in raw:
            v = self._item(it)
            if not v or v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return out, data

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        tid = _s(tid)
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        order = ""
        if isinstance(filter, dict):
            order = _s(filter.get("order") or "")
        if not order and isinstance(extend, dict):
            order = _s(extend.get("order") or "")
        items, data = self._list_page(tid, pg, PAGE_SIZE, order)
        pagecount = pg
        if items and data.get("has_more"):
            pagecount = pg + 1
        return {"list": items, "page": pg, "pagecount": pagecount,
                "limit": PAGE_SIZE, "total": PAGE_SIZE * pagecount}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        size = 12 if quick else PAGE_SIZE
        res = self._api("/search/movie", {"keyword": _s(key), "page": pg, "page_size": size},
                        retry=3, timeout=25)
        items = []
        if res and res.get("status") == "y":
            seen = set()
            for it in ((res.get("data") or {}).get("items") or []):
                v = self._item(it)
                if not v or v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                items.append(v)
        return {"list": items, "page": pg, "pagecount": 9999,
                "limit": size, "total": size * 9999}

    # ---------------- 详情 ----------------
    def _detail(self, vid, lid=""):
        ck = "%s|%s" % (vid, lid or "")
        if ck in self._detail_cache:
            return self._detail_cache[ck]
        body = {"id": _s(vid)}
        if lid:
            body["lid"] = _s(lid)
        res = self._api("/movie/detail", body, retry=3, timeout=25)
        data = None
        if res and res.get("status") == "y":
            data = res.get("data") or None
        if data is not None and len(self._detail_cache) < 60:
            self._detail_cache[ck] = data
        return data

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = _s(ids[0]) if ids else ""
        else:
            vid = _s(ids or "")
        if vid.startswith("d:"):
            vid = vid[2:]
        data = self._detail(vid)
        if not data:
            return {"list": []}

        name = _s(data.get("name") or "")
        play_from = []
        play_lists = []

        groups = data.get("links") or []
        eps = []
        for g in groups:
            for it in (g.get("items") or []):
                eps.append(it)
        eps = [e for e in eps if e.get("episode_id")]
        eps.sort(key=lambda e: self._num(e.get("episode_no"), 0))

        free_pairs = []
        lock_pairs = []
        for e in eps:
            ep_name = _s(e.get("name") or (u"第%s集" % _s(e.get("episode_no"))))
            url = _s(e.get("m3u8_url") or "")
            locked = (e.get("is_locked") == "y") or (e.get("can_watch") is False)
            if url and not locked:
                free_pairs.append("%s$%s" % (ep_name, self._abs(url)))
            else:
                lock_pairs.append("%s$L|%s|%s" % (ep_name, vid, _s(e.get("episode_id"))))

        if free_pairs:
            play_from.append(u"正片(可播)")
            play_lists.append("#".join(free_pairs))
        if lock_pairs:
            play_from.append(u"试看片段(VIP锁)")
            play_lists.append("#".join(lock_pairs))
        if not eps:
            # 只有单片(无分集列表),退回 playback_v2 的首条地址
            single = self._single_url(data)
            if single:
                play_from.append(u"默认线路")
                play_lists.append("%s$%s" % (name or u"正片", single))

        pic = self._pic(data)
        content = _s(data.get("description") or "")
        bits = []
        if data.get("episode_total"):
            bits.append(u"共%s集" % _s(data.get("episode_total")))
        if data.get("duration"):
            bits.append(u"单片时长 %s" % _s(data.get("duration")))
        if data.get("publisher"):
            bits.append(u"出品:%s" % _s(data.get("publisher")))
        if data.get("pay_type"):
            bits.append(u"付费类型:%s" % _s(data.get("pay_type")))
        tags = data.get("tags") or []
        if isinstance(tags, list) and tags:
            bits.append(u"标签:" + u"/".join([_s((t or {}).get("name")) for t in tags if (t or {}).get("name")]))
        if data.get("is_locked") == "y" or data.get("can_watch") is False:
            bits.append(u"⚠ 该剧服务端为 VIP 锁,未登录付费账号只能看试看片段")
        head = u" · ".join([b for b in bits if b])
        vod_content = (head + u"\n" + content).strip() if (head or content) else ""

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_year": _s(data.get("issue_date") or ""),
            "vod_area": u"短剧",
            "vod_remarks": (u"共%s集" % _s(data.get("episode_total"))) if data.get("episode_total") else "",
            "vod_actor": u"/".join([_s((a or {}).get("nickname") or (a or {}).get("username") or "")
                                    for a in (data.get("actors") or []) if a]),
            "vod_director": _s(data.get("publisher") or ""),
            "vod_content": vod_content,
            "vod_play_from": "$$$".join(play_from),
            "vod_play_url": "$$$".join(play_lists),
        }
        return {"list": [vod]}

    def _single_url(self, data):
        pb = data.get("playback_v2") or {}
        lines = pb.get("video_lines") or []
        for l in lines:
            h = (l.get("h264") or {}).get("url")
            if h:
                return self._abs(h)
        if pb.get("play_url"):
            return self._abs(pb.get("play_url"))
        for pl in (data.get("play_links") or []):
            for k in ("m3u8_url", "preview_m3u8_url"):
                if pl.get(k):
                    return self._abs(pl.get(k))
        return ""

    # ---------------- 播放 ----------------
    def playerContent(self, flag, ids, vipFlags=None):
        raw = ""
        if isinstance(ids, (list, tuple)):
            raw = _s(ids[0]) if ids else ""
        else:
            raw = _s(ids or "")

        url = ""
        if raw.startswith("L|"):
            _, vid, lid = (raw.split("|") + ["", ""])[:3]
            data = self._detail(vid, lid)
            if data:
                for pl in (data.get("play_links") or []):
                    for k in ("m3u8_url", "preview_m3u8_url"):
                        if pl.get(k):
                            url = self._abs(pl[k])
                            break
                    if url:
                        break
                if not url:
                    url = self._single_url(data)
        elif raw.startswith("/"):
            url = self._abs(raw)
        elif raw.startswith("http"):
            url = raw

        if not url:
            return {"parse": 0, "jx": 0, "playUrl": "", "url": "",
                    "header": self._headers(), "format": "application/x-mpegURL"}

        if self.use_proxy:
            url = "proxy://do=spider&url=" + quote(url, safe="")

        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": url,
            "header": self._headers(),
            "format": "application/x-mpegURL",
        }

    def _headers(self):
        return {
            "User-Agent": self._ua,
            "Referer": self.host + "/",
            "Origin": self.host,
        }

    # ---------------- 本地代理(m3u8 清洗) ----------------
    def localProxy(self, param):
        try:
            if isinstance(param, str):
                try:
                    param = json.loads(param)
                except Exception:
                    param = {}
            if not isinstance(param, dict):
                param = {}
            url = param.get("url") or param.get("u") or ""
            if isinstance(url, list):
                url = url[0] if url else ""
            url = _s(url)
            if not url:
                return [400, "text/plain", _b("bad request"), {"Access-Control-Allow-Origin": "*"}]
            try:
                url = unquote(url)
            except Exception:
                pass
            if url.startswith("proxy://"):
                url = url[8:]
            if not url.startswith("http"):
                url = self._abs(url)

            status, hdr, body = self._get(url, timeout=25)
            if status != 200 or not body:
                return [502, "text/plain", _b("upstream error"), {"Access-Control-Allow-Origin": "*"}]

            ctype = (hdr.get("Content-Type") or hdr.get("content-type") or "").lower()
            low = url.split("?")[0].lower()
            is_m3u8 = ("mpegurl" in ctype) or low.endswith(".m3u8") or low.endswith(".m3u")
            out_headers = {
                "Access-Control-Allow-Origin": "*",
                "User-Agent": self._ua,
            }
            if not is_m3u8:
                return [200, ctype or "application/octet-stream", body, out_headers]

            text = _s(body)
            if not text.lstrip().startswith("#EXTM3U"):
                return [200, "application/vnd.apple.mpegurl", body, out_headers]

            base = url.rsplit("/", 1)[0] + "/"
            lines = text.split("\n")
            out = []
            for line in lines:
                s = line.strip()
                if s and not s.startswith("#"):
                    out.append(urljoin(base, s))
                    continue
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP") or \
                        s.startswith("#EXT-X-MEDIA") or s.startswith("#EXT-X-STREAM-INF"):
                    def _fix(m):
                        return '%s="%s"' % (m.group(1), urljoin(base, m.group(2)))
                    s = re.sub(r'(URI)="([^"]+)"', _fix, s)
                    out.append(s)
                    continue
                out.append(line)
            return [200, "application/vnd.apple.mpegurl", _b("\n".join(out)), out_headers]
        except Exception:
            return [500, "text/plain", _b("proxy error"), {"Access-Control-Allow-Origin": "*"}]

    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        u = _s(url).lower()
        for k in (".m3u8", ".m3u", ".mp4", ".flv", ".ts"):
            if k in u:
                return True
        return False

    def action(self, action):
        return {}


# ==================================================================
# CLI(不进 TVBox 也能用)
# ==================================================================
def _cli(argv):
    sp = Spider()
    ext = ""
    for i, a in enumerate(argv):
        if a == "--ext" and i + 1 < len(argv):
            ext = argv[i + 1]
    sp.init(ext)

    def _arg(name, default=""):
        for i, a in enumerate(argv):
            if a == name and i + 1 < len(argv):
                return argv[i + 1]
        return default

    cmd = argv[1] if len(argv) > 1 else "probe"

    if cmd == "probe":
        print("AES 自检:", "PASS" if _aes_selftest() else "FAIL")
        print("会话:", sp.session or "(设备登录失败)")
        navs = sp._navs()
        print("剧场分类:", ", ".join(["%s=%s" % (n["tid"], n["name"]) for n in navs]))
        items = sp._list(_arg("--tid", "14"), 1, 5, "")
        print("列表样本(%d 条):" % len(items))
        for it in items:
            print("   ", it["vod_name"][:30], "|", it["vod_remarks"], "|", it["vod_pic"][:60])
        if items:
            d = sp.detailContent([items[0]["vod_id"]])
            v = (d.get("list") or [{}])[0]
            print("详情:", v.get("vod_name"), "| 线路:", v.get("vod_play_from"))
            urls = (v.get("vod_play_url") or "").split("#")
            print("   集数:", len(urls), "| 首个:", urls[0][:120] if urls else "")
            if urls:
                pid = urls[0].split("$", 1)[-1]
                p = sp.playerContent("", pid, None)
                print("   播放:", p.get("url")[:120])
        return 0

    if cmd == "nav":
        for n in sp._navs():
            print("%-4s %-14s %s" % (n["tid"], n["name"], n["code"]))
        return 0

    if cmd == "list":
        for it in sp._list(_arg("--tid", "14"), int(_arg("--page", "1")), PAGE_SIZE, _arg("--sort", "")):
            print("%-14s %-40s %s" % (it["vod_id"], it["vod_name"][:38], it["vod_remarks"]))
        return 0

    if cmd == "search":
        key = argv[2] if len(argv) > 2 else ""
        for it in sp.searchContent(key, False, _arg("--page", "1"))["list"]:
            print("%-14s %-40s %s" % (it["vod_id"], it["vod_name"][:38], it["vod_remarks"]))
        return 0

    if cmd == "detail":
        vid = argv[2] if len(argv) > 2 else ""
        v = (sp.detailContent([vid]).get("list") or [{}])[0]
        print("片名:", v.get("vod_name"))
        print("封面:", v.get("vod_pic"))
        print("简介:", (v.get("vod_content") or "")[:300])
        print("线路:", v.get("vod_play_from"))
        for i, block in enumerate((v.get("vod_play_url") or "").split("$$$")):
            eps = block.split("#")
            print("  [%d] %d 集, 前 2 集:" % (i, len(eps)))
            for e in eps[:2]:
                print("     ", e[:130])
        return 0

    if cmd == "play":
        vid = argv[2] if len(argv) > 2 else ""
        no = _arg("--ep", "1")
        v = (sp.detailContent([vid]).get("list") or [{}])[0]
        blocks = (v.get("vod_play_url") or "").split("$$$")
        target = blocks[0].split("#")[max(0, int(no) - 1)]
        pid = target.split("$", 1)[-1]
        p = sp.playerContent("", pid, None)
        print("集:", target.split("$", 1)[0])
        print("地址:", p.get("url"))
        return 0

    print("用法: nav | list | search <词> | detail <id> | play <id> --ep N | probe")
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
