# coding=utf-8
# ============================================================================
# 88影视(88ayyc) · 影视壳 / TVBox 本地 py 源  (type 3 / drpy py 模式)
# ----------------------------------------------------------------------------
# 安装三步:
#   1) 壳子的配置目录下建一个 py 文件夹(和 api.json 放同一层)
#   2) 本文件丢进去,确保文件名是 ayyc.py  →  <配置目录>/py/ayyc.py
#   3) api.json 里对应站点已经写好了,不用改:
#      {"key":"ayyc","name":"88影视","type":3,"api":"./py/ayyc.py",
#       "searchable":1,"quickSearch":1,"filterable":1,
#       "ext":"https://88ayyc35.6p.tattoo"}
#      换域名只改 ext 就行,脚本不用动。
#
# 实现说明:
#   · 目标站所有页面都是「双层 base64」包装,本脚本内部自动解开
#   · 标准采集口 /api.php/provide/vod/ 已被站方关闭,别往那填
#   · 列表走 /index.php/ajax/data?mid=1&tid=&page= (标准 vod JSON)
#   · 播放地址走播放页里的 player_aaaa 变量,m3u8 直链明文(encrypt=0)
#   · 分类列表只给元数据(秒回),点进去才拉 m3u8,顺带后台预热下一页
# ============================================================================

import base64
import gzip
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
except Exception:
    BaseHTTPRequestHandler = ThreadingHTTPServer = None

sys.path.append('..')
try:
    from base.spider import Spider as _Base
except Exception:
    _Base = object

try:
    import requests as _rq
except Exception:
    _rq = None


# ---------------------------------------------------------------- 配置
DEFAULT_BASE = "https://88ayyc35.6p.tattoo"
SITE_NAME = "88影视"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
TIMEOUT = 12
PER_PAGE = 10          # 目标站 ajax/data 固定每页 10 条
CACHE_TTL = 300        # 缓存秒数
DETAIL_WORKERS = 8     # 详情并发数

# 首页解析失败时的兜底分类表
FALLBACK_CATS = {
    "3": "黑料吃瓜", "4": "厂牌原创", "5": "国产精选", "6": "明星换脸", "7": "AV解说",
    "8": "禁漫精选", "9": "乱伦", "10": "父女", "11": "母子", "12": "兄妹", "13": "学生",
    "14": "嫂子", "15": "姐夫", "16": "师生", "17": "全家", "28": "国产大片",
    "31": "欧美大片", "32": "网红直播", "33": "探花约炮", "34": "三级伦理", "35": "萝莉开苞",
    "66": "有声小说", "68": "cosplay", "69": "AI魔改", "70": "av综艺", "72": "嫩妹下海",
    "74": "每日甄选", "76": "ts人妖", "77": "姿势玩法", "78": "同性恋", "79": "真实缅北",
    "80": "恶心恐怖", "81": "黄金圣水", "82": "校园霸凌", "83": "战场实录", "84": "人兽乱交",
    "85": "灵异视频", "86": "N号房", "87": "日韩大片", "88": "SM调教",
}


# ---------------------------------------------------------------- 海报解密
# 站上海报挂在 aisearch.cdn.bcebos.com 的 .txt 里,内容是 base64(原图 XOR 密钥)。
# 密钥取自站点前端脚本,解密方式 = 逐字节和密钥循环异或,解出来就是原图。
# vod_pic_thumb / vod_pic_slide 那个域名(rgvgd.ebailx.com)已经解析不出来了,是死的,
# 所以海报只能走 vod_pic 解密这条路。壳子自己不会解密,本脚本起一个本地小服务
# (127.0.0.1)把解好的图直接吐给壳子。
IMG_KEY = "OzoTeoS7D>6Y^@z39JmD"
IMG_KEY_BYTES = [ord(c) for c in IMG_KEY]
ENC_DOMAINS = ("cdn.bcebos.com", "ucloudqn.unipus.cn", "vfile.meituan.net")
PIC_PORTS = (9988, 9989, 9990, 9991, 18765, 18766, 18767)
PIC_CACHE_DIR = os.path.join(tempfile.gettempdir(), "ayyc_pic_cache")
PIC_MEM_MAX = 400          # 内存里最多缓存多少张
PIC_WARM_WORKERS = 6       # 后台预热海报的并发


# ---------------------------------------------------------------- 底层工具
def _headers(base, referer=None):
    return {
        "User-Agent": UA,
        "Referer": referer or (base + "/"),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "close",
    }


def _http(url, base, referer=None):
    """抓一个 URL 返回文本,自动处理 gzip / 编码"""
    hdr = _headers(base, referer)
    if _rq is not None:
        r = _rq.get(url, headers=hdr, timeout=TIMEOUT)
        return r.content.decode("utf-8", "ignore")

    req = urllib.request.Request(url, headers=hdr)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw = resp.read()
        enc = (resp.headers.get("Content-Encoding") or "").lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except Exception:
            pass
    for codec in ("utf-8", "gbk", "latin-1"):
        try:
            return raw.decode(codec)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def _b64(text):
    s = "".join(text.split())
    pad = (-len(s)) % 4
    try:
        return base64.b64decode(s + "=" * pad).decode("utf-8")
    except Exception:
        return None


def _unwrap(text):
    """目标站把真内容套了两层 base64: var str='<b64>' -> 再 b64 -> 真内容"""
    if not text:
        return text
    m = re.search(r"var\s+str\s*=\s*'([^']+)'", text)
    if not m:
        m = re.search(r'var\s+str\s*=\s*"([^"]+)"', text)
    if not m:
        return text
    cur = m.group(1)
    for _ in range(2):
        nxt = _b64(cur)
        if not nxt or not nxt.strip():
            break
        cur = nxt
    return cur


def _is_enc_pic(url):
    """是不是「加密域名」上的图(要解密的)"""
    if not url or not url.startswith("http"):
        return False
    for d in ENC_DOMAINS:
        if d in url:
            return True
    return False


def _pic_mime(b):
    if b[:4] == b"\x89PNG":
        return "image/png"
    if b[:3] == b"GIF":
        return "image/gif"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "image/webp"
    if b[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return ""


def _pic_cache_path(url):
    return os.path.join(PIC_CACHE_DIR,
                        hashlib.md5(url.encode("utf-8")).hexdigest())


def _decode_pic(raw):
    """拿到的一坨字节 → 原始图片字节。两种形态:
       ① 直接就是图片(有些 CDN 是明文图) ② base64(原图 XOR 密钥)"""
    if not raw or len(raw) < 64:
        return b"", ""
    mime = _pic_mime(raw)
    if mime:
        return raw, mime
    txt = raw.strip()
    try:
        bin_ = base64.b64decode(txt + b"=" * ((-len(txt)) % 4))
    except Exception:
        return b"", ""
    if not bin_:
        return b"", ""
    out = bytes(b ^ IMG_KEY_BYTES[i % len(IMG_KEY_BYTES)]
                for i, b in enumerate(bin_))
    mime = _pic_mime(out)
    if not mime:
        return b"", ""
    return out, mime


def load_pic(url):
    """拿一张海报的原始图片字节,带磁盘缓存。返回 (bytes, mime)"""
    if not url or not url.startswith("http"):
        return b"", ""
    cp = _pic_cache_path(url)
    try:
        if os.path.exists(cp) and os.path.getsize(cp) > 64:
            with open(cp, "rb") as f:
                b = f.read()
            mime = _pic_mime(b)
            if mime:
                return b, mime
    except Exception:
        pass
    b, mime = b"", ""
    for _ in range(2):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA, "Referer": DEFAULT_BASE + "/"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                raw = r.read()
            b, mime = _decode_pic(raw)
            if b:
                break
        except Exception:
            time.sleep(0.3)
    if b:
        try:
            os.makedirs(PIC_CACHE_DIR, exist_ok=True)
            with open(cp, "wb") as f:
                f.write(b)
        except Exception:
            pass
    return b, mime


# ---- 本地图片小服务:壳子不会解密,这里解好直接喂给它 ----
_pic_state = {"port": 0, "mem": {}, "lock": threading.Lock(), "tried": False}


def _pic_b64(url):
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode().rstrip("=")


def _pic_unb64(tag):
    return base64.urlsafe_b64decode(tag + "=" * ((-len(tag)) % 4)).decode("utf-8")


def _pic_handler_factory():
    class _H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            try:
                path = urllib.parse.urlparse(self.path).path
                if not path.startswith("/p/"):
                    self.send_error(404)
                    return
                tag = path[3:]
                if "." in tag:
                    tag = tag.rsplit(".", 1)[0]
                url = _pic_unb64(tag)
                data, mime = b"", ""
                with _pic_state["lock"]:
                    mem = _pic_state["mem"].get(url)
                if mem:
                    data, mime = mem
                if not data:
                    data, mime = load_pic(url)
                    if data:
                        with _pic_state["lock"]:
                            if len(_pic_state["mem"]) < PIC_MEM_MAX:
                                _pic_state["mem"][url] = (data, mime)
                if not data:
                    self.send_response(302)
                    self.send_header("Location", url)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", mime or "image/jpeg")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "public, max-age=604800")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                try:
                    self.send_error(500)
                except Exception:
                    pass

    return _H


def pic_server_port():
    """起本地图片服务,返回端口;起不来返回 0"""
    if _pic_state["port"]:
        return _pic_state["port"]
    with _pic_state["lock"]:
        if _pic_state["port"] or _pic_state["tried"]:
            return _pic_state["port"]
        _pic_state["tried"] = True
        if ThreadingHTTPServer is None:
            return 0
        for port in PIC_PORTS:
            try:
                srv = ThreadingHTTPServer(("127.0.0.1", port), _pic_handler_factory())
            except Exception:
                continue
            srv.daemon_threads = True
            try:
                threading.Thread(target=srv.serve_forever, daemon=True).start()
            except Exception:
                continue
            _pic_state["port"] = port
            return port
    return 0


def _pic_url(url):
    """把海报换成「本地服务地址」;服务起不来就原样返回,不影响出片"""
    if not url or not url.startswith("http"):
        return ""
    port = pic_server_port()
    if not port:
        return url
    return "http://127.0.0.1:%d/p/%s.jpg" % (port, _pic_b64(url))


def warm_pics(urls):
    """后台把海报先解密缓存好,壳子拉的时候就是秒回"""
    todo = []
    with _pic_state["lock"]:
        for u in urls:
            if not u or not str(u).startswith("http") or u in _pic_state["mem"]:
                continue
            if "127.0.0.1" in u or "localhost" in u:
                continue
            if len(todo) < 24:
                todo.append(u)
    if not todo:
        return

    def run():
        try:
            with ThreadPoolExecutor(max_workers=PIC_WARM_WORKERS) as ex:
                list(ex.map(load_pic, todo))
        except Exception:
            pass

    try:
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        pass


def _pick(v, *keys):
    for k in keys:
        val = v.get(k)
        if val not in (None, "", "0"):
            return val
    return ""


def _fmt_play(sid):
    return "线路%s" % sid


# ---------------------------------------------------------------- 主体
class Spider(_Base):

    def __init__(self, *args, **kwargs):
        try:
            super(Spider, self).__init__(*args, **kwargs)
        except Exception:
            pass
        self.base = DEFAULT_BASE
        self._cache = {}
        self._lock = threading.Lock()
        self._warming = set()

    # ---------------- 生命周期 ----------------
    def getName(self):
        return SITE_NAME

    def init(self, extend=""):
        ext = extend
        if isinstance(ext, dict):
            ext = ext.get("ext") or ext.get("base") or ext.get("url") or ""
        if isinstance(ext, (list, tuple)):
            ext = ext[0] if ext else ""
        ext = str(ext or "").strip().strip('"').strip("'")
        if ext.startswith("http"):
            self.base = ext.rstrip("/")
        else:
            self.base = DEFAULT_BASE
        try:
            pic_server_port()
        except Exception:
            pass

    def isVideoFormat(self, url):
        return bool(url)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        self._cache.clear()

    # ---------------- 缓存 ----------------
    def _cget(self, key):
        it = self._cache.get(key)
        if it and (time.time() - it[0]) <= CACHE_TTL:
            return it[1]
        return None

    def _cset(self, key, val):
        with self._lock:
            self._cache[key] = (time.time(), val)
            if len(self._cache) > 2000:
                for k in list(self._cache.keys())[:1000]:
                    self._cache.pop(k, None)

    # ---------------- 基础请求 ----------------
    def _get(self, url, referer=None):
        return _http(url, self.base, referer)

    def _json(self, url, referer=None):
        return json.loads(_unwrap(self._get(url, referer)))

    # ---------------- 分类 ----------------
    def _cats(self):
        c = self._cget("cats")
        if c:
            return c
        cats = {}
        try:
            html = _unwrap(self._get(self.base + "/"))
            for tid, name in re.findall(
                    r'/index\.php/vod/type/id/(\d+)\.html"[^>]*>\s*([^<]{1,24}?)\s*<', html):
                name = name.strip()
                if name and tid not in cats:
                    cats[tid] = name
        except Exception:
            cats = {}
        if len(cats) < 5:
            cats = dict(FALLBACK_CATS)
        self._cset("cats", cats)
        return cats

    # ---------------- 列表 ----------------
    def _list_page(self, tid, page):
        ck = "lp:%s:%s" % (tid, page)
        c = self._cget(ck)
        if c:
            return c
        try:
            j = self._json("%s/index.php/ajax/data?mid=1&tid=%s&page=%s"
                           % (self.base, tid, page))
        except Exception:
            j = {"list": [], "pagecount": 1, "total": 0}
        self._cset(ck, j)
        return j

    # ---------------- 搜索 ----------------
    def _search(self, wd):
        ck = "sb:%s" % wd
        c = self._cget(ck)
        if c is not None:
            return c
        url = "%s/index.php/vod/search.html?wd=%s" % (self.base, urllib.parse.quote(wd))
        briefs, seen = [], set()
        try:
            html = _unwrap(self._get(url))
        except Exception:
            html = ""
        for part in re.split(r'(?=/index\.php/vod/detail/id/\d+\.html")', html):
            if not part.startswith("/index.php/vod/detail/id/"):
                continue
            head = part[:2000]
            m = re.match(r'/index\.php/vod/detail/id/(\d+)\.html"', head)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen:
                continue
            seen.add(vid)
            t = re.search(r'title="([^"]{1,140})"', head)
            img = re.search(
                r'<img[^>]+(?:data-src|data-original|src)="(https?://[^"]{10,200})"', head)
            briefs.append({
                "vod_id": vid,
                "vod_name": (t.group(1).strip() if t else vid),
                "vod_pic": (img.group(1) if img else ""),
            })
        if not briefs and html:
            try:
                j = json.loads(html)
                for it in j.get("list", []):
                    briefs.append({"vod_id": str(it.get("vod_id")),
                                   "vod_name": it.get("vod_name") or "",
                                   "vod_pic": it.get("vod_pic") or ""})
            except Exception:
                pass
        self._cset(ck, briefs)
        return briefs

    # ---------------- 播放页 ----------------
    def _play(self, vid, sid=1, nid=1):
        """返回 (vod_data, m3u8, 该片所有 sid)"""
        ck = "pp:%s:%s:%s" % (vid, sid, nid)
        c = self._cget(ck)
        if c is not None:
            return c
        url = "%s/index.php/vod/play/id/%s/sid/%s/nid/%s.html" % (self.base, vid, sid, nid)
        ref = "%s/index.php/vod/detail/id/%s.html" % (self.base, vid)
        data, m3u8, sids = {}, "", []
        try:
            htm = _unwrap(self._get(url, referer=ref))
            i = htm.find("player_aaaa")
            if i >= 0:
                b = htm.find("{", i)
                if b >= 0:
                    obj, _ = json.JSONDecoder().raw_decode(htm[b:])
                    data = dict(obj.get("vod_data") or {})
                    u = (obj.get("url") or "").strip()
                    if u.startswith("//"):
                        u = "https:" + u
                    m3u8 = u
            for s in re.findall(r'/index\.php/vod/play/id/%s/sid/(\d+)/nid/' % vid, htm):
                if s not in sids:
                    sids.append(s)
        except Exception:
            pass
        res = (data, m3u8, sids or [str(sid)])
        self._cset(ck, res)
        return res

    def _m3u8(self, vid, sid):
        return self._play(vid, sid, 1)[1]

    # ---------------- 数据整形 ----------------
    def _brief(self, v):
        vid = str(v.get("vod_id") or "")
        return {
            "vod_id": int(vid) if vid.isdigit() else vid,
            "vod_name": v.get("vod_name") or "",
            "vod_sub": "",
            "vod_en": "",
            "type_id": v.get("type_id") or 0,
            "type_name": self._cats().get(str(v.get("type_id") or ""), ""),
            "vod_pic": _pic_url(_pick(v, "vod_pic", "vod_pic_slide",
                                      "vod_pic_thumb")),
            "vod_actor": v.get("vod_actor") or "",
            "vod_director": v.get("vod_director") or "",
            "vod_year": v.get("vod_year") or "",
            "vod_area": v.get("vod_area") or "",
            "vod_lang": v.get("vod_lang") or "",
            "vod_remarks": v.get("vod_remarks") or (v.get("vod_pubdate") or ""),
            "vod_score": str(v.get("vod_score") or "0"),
            "vod_time": (v.get("vod_pubdate") or "")
                        or time.strftime("%Y-%m-%d %H:%M:%S"),
            "vod_content": v.get("vod_blurb") or v.get("vod_content") or "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

    # ---------------- 首页 ----------------
    def homeContent(self, filter=False):
        cats = self._cats()
        classes = [{"type_id": int(t), "type_name": n} for t, n in
                   sorted(cats.items(), key=lambda x: int(x[0]))]
        try:
            tid_list = [c["type_id"] for c in classes[:4]]
        except Exception:
            tid_list = [3]
        filters = {str(t): [] for t in tid_list}
        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        cats = self._cats()
        tids = [t for t in sorted(cats, key=lambda x: int(x))[:6]]
        items, seen = [], set()

        def grab(tid):
            try:
                return self._list_page(tid, 1).get("list", [])[:6]
            except Exception:
                return []

        try:
            with ThreadPoolExecutor(max_workers=6) as ex:
                for lst in ex.map(grab, tids):
                    for v in lst:
                        vid = str(v.get("vod_id"))
                        if vid in seen:
                            continue
                        seen.add(vid)
                        items.append(self._brief(v))
                        warm_pics([_pick(v, "vod_pic", "vod_pic_slide",
                                         "vod_pic_thumb")])
        except Exception:
            pass
        return {"list": items}

    # ---------------- 分类内容 ----------------
    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = 1
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        j = self._list_page(tid, page)
        raw = j.get("list", []) or []
        items = [self._brief(v) for v in raw]
        try:
            pagecount = int(j.get("pagecount") or 1)
        except Exception:
            pagecount = 1
        try:
            total = int(j.get("total") or len(items))
        except Exception:
            total = len(items)
        self._warm([v.get("vod_id") for v in raw])
        warm_pics([v.get("vod_pic") or v.get("vod_pic_thumb") or "" for v in raw])
        return {"list": items, "page": page, "pagecount": pagecount,
                "limit": PER_PAGE, "total": total}

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick=False, pg="1"):
        briefs = self._search(key)
        self._warm([b["vod_id"] for b in briefs[:30]])
        return {"list": [self._brief(b) for b in briefs]}

    # ---------------- 详情 ----------------
    def detailContent(self, array):
        vid = ""
        try:
            vid = str(array[0]).split("$")[0].strip()
        except Exception:
            vid = str(array).split("$")[0].strip()
        if vid.startswith("http"):
            return {"list": [{"vod_id": vid, "vod_name": vid,
                              "vod_play_from": "线路1",
                              "vod_play_url": "正片$%s" % vid}]}

        data, first, sids = self._play(vid, 1, 1)
        item = self._brief(dict(data))
        item["vod_id"] = int(vid) if vid.isdigit() else vid

        us = {}
        if first:
            us["1"] = first
        rest = [s for s in sids if s not in us]
        if rest:
            try:
                with ThreadPoolExecutor(max_workers=DETAIL_WORKERS) as ex:
                    futs = {ex.submit(self._m3u8, vid, s): s for s in rest}
                    for f in as_completed(futs):
                        u = f.result()
                        if u:
                            us[futs[f]] = u
            except Exception:
                pass

        froms, urls = [], []
        for sid in sorted(us, key=lambda x: int(x) if x.isdigit() else 999):
            u = us[sid]
            if not u or not u.startswith("http"):
                continue
            froms.append(_fmt_play(sid))
            urls.append("正片$%s" % u)
        item["vod_play_from"] = "$$$".join(froms) or "线路1"
        item["vod_play_url"] = "$$$".join(urls)
        return {"list": [item]}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        if "$" in url:
            url = url.split("$")[-1].strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            u = self._m3u8(url, 1)
            if u:
                url = u
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps({
                "User-Agent": UA,
                "Referer": self.base + "/",
            }),
        }

    # ---------------- 后台预热 ----------------
    def _warm(self, vids):
        todo = []
        with self._lock:
            for v in vids:
                v = str(v or "")
                if not v or v in self._warming:
                    continue
                if self._cget("pp:%s:1:1" % v):
                    continue
                self._warming.add(v)
                todo.append(v)
        if not todo:
            return

        def run():
            try:
                with ThreadPoolExecutor(max_workers=4) as ex:
                    list(ex.map(lambda x: self._play(x, 1, 1), todo[:12]))
            except Exception:
                pass
            finally:
                with self._lock:
                    for v in todo:
                        self._warming.discard(v)

        try:
            threading.Thread(target=run, daemon=True).start()
        except Exception:
            pass


# ---------------------------------------------------------------- 本地自测
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="88影视 py 源自测")
    ap.add_argument("--ext", default=DEFAULT_BASE)
    ap.add_argument("--wd", default="")
    ap.add_argument("--vid", default="")
    args = ap.parse_args()

    sp = Spider()
    sp.init(args.ext)

    t0 = time.time()
    hc = sp.homeContent(False)
    print("[homeContent] %d 个分类  用时 %.2fs" % (len(hc["class"]), time.time() - t0))
    for c in hc["class"][:8]:
        print("   ", c["type_id"], c["type_name"])

    tid = hc["class"][0]["type_id"]
    t0 = time.time()
    cc = sp.categoryContent(tid, 1, False, None)
    print("[categoryContent] tid=%s 共 %s 页 / %s 条,本页 %d 条  用时 %.2fs"
          % (tid, cc["pagecount"], cc["total"], len(cc["list"]), time.time() - t0))
    for it in cc["list"][:3]:
        print("   ", it["vod_id"], it["vod_name"], it["vod_pic"][:70])

    # ---- 海报解密链路自检:本地服务能不能吐出真图 ----
    print("[pic] 本地图片服务端口 =", pic_server_port())
    ok = 0
    sample = cc["list"][:6]
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(load_pic, _pick(v, "vod_pic", "vod_pic_slide",
                                         "vod_pic_thumb")): v for v in sample}
        for f in as_completed(futs):
            b, mime = f.result()
            name = futs[f].get("vod_name", "")[:16]
            print("   ", ("OK " if b else "FAIL"), mime or "-", len(b), name)
            if b:
                ok += 1
    print("[pic] %d/%d 张海报解密成功" % (ok, len(sample)))
    try:
        import urllib.request as _u
        with _u.urlopen(cc["list"][0]["vod_pic"], timeout=20) as r:
            got = r.read()
        print("[pic] 本地服务实测 HTTP %s,Content-Type=%s,%d 字节"
              % (r.status, r.headers.get("Content-Type"), len(got)))
    except Exception as e:
        print("[pic] 本地服务实测失败:", e)

    if args.wd:
        t0 = time.time()
        sc = sp.searchContent(args.wd, True, "1")
        print("[searchContent] '%s' 命中 %d 条  用时 %.2fs"
              % (args.wd, len(sc["list"]), time.time() - t0))
        for it in sc["list"][:3]:
            print("   ", it["vod_id"], it["vod_name"])

    vid = args.vid or str(cc["list"][0]["vod_id"])
    t0 = time.time()
    dc = sp.detailContent([vid])
    it = dc["list"][0]
    print("[detailContent] %s / %s  用时 %.2fs"
          % (it.get("vod_id"), it.get("vod_name"), time.time() - t0))
    print("   线路:", it.get("vod_play_from"))
    for line in (it.get("vod_play_url") or "").split("$$$")[:3]:
        print("   ", line[:110])

    first_url = (it.get("vod_play_url") or "").split("$$$")[0].split("$")[-1]
    pc = sp.playerContent("线路1", first_url, None)
    print("[playerContent] parse=%s url=%s" % (pc["parse"], pc["url"][:110]))
