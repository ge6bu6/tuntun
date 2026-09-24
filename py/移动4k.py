# -*- coding: utf-8 -*-
# 移动4K (Yidong4K) TVBox/Drpy 源 (type 3)
# 站点: https://vidsite.cloudseekr.com/vid/app/  —— 网盘资源型 4K 源
# 详情的 resUrl 是中国移动云盘(139)分享链接, 播放需走 139 分享接口解密解析。
import base64, hashlib, json, os, re, time
import urllib.request

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

try:
    from Crypto.Cipher import AES as _AES
except Exception:
    _AES = None

BASE = "https://vidsite.cloudseekr.com"
HDR = {
    "Origin": BASE,
    "Accept": "application/json, text/plain, */*",
    "Cache-Control": "no-cache",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"),
    "Referer": BASE + "/vid/app/",
    "Pragma": "no-cache",
    "Content-Type": "application/json; charset=utf-8",
}
# 139 云盘分享接口 AES 密钥 (Java: g()/k() 同密钥, CBC, 前置 16 字节 IV)
YN_KEY = b"PVGDwmcvfs1uV3d1"
YN_HDR = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
    "Content-Type": "application/json;charset=UTF-8",
    "Referer": "https://yun.139.com/",
    "x-deviceinfo": "||3|12.27.0|chrome|131.0.0.0|1||windows 10|546X902|zh-CN|||",
    "hcy-cool-flag": "1",
    "authorization": "",
}
YN_INFO = ("https://share-kd-njs.yun.139.com/yun-share/richlifeApp/devapp/"
           "IOutLink/getOutLinkInfoV6")
YN_CONTENT = ("https://share-kd-njs.yun.139.com/yun-share/richlifeApp/devapp/"
              "IOutLink/getContentInfoFromOutLink")

COLS = [("1", "电影"), ("2", "电视剧"), ("3", "动漫")]

# 139 目录缓存: walk 结果按分享链接缓存 10 分钟, 避免重复展开
_YNCACHE = {}


def _yn_enc(text):
    if not _AES:
        return None
    iv = os.urandom(16)
    b = text.encode()
    b += bytes([16 - len(b) % 16]) * (16 - len(b) % 16)
    return base64.b64encode(
        iv + _AES.new(YN_KEY, _AES.MODE_CBC, iv).encrypt(b)).decode()


def _yn_dec(text):
    if not _AES:
        return ""
    try:
        b = base64.b64decode(text)
        c = _AES.new(YN_KEY, _AES.MODE_CBC, b[:16]).decrypt(b[16:])
        return c[:-c[-1]].decode("utf-8", "ignore")
    except Exception:
        return ""


def _ep_longname(name):
    base = re.sub(r"\.\w+$", "", name)
    m = re.search(r"[Ee](\d{1,3})(?!\d)", name)
    if not m:
        m = re.search(r"(?<!\d)(\d{1,3})(?!\d)\s*(?:集)?", base)
    return ("第%d集" % int(m.group(1))) if m else base


def _walk(link, caID, dirName, out, depth=0):
    """递归展开 139 分享目录, 收集所有视频文件。
    返回 dict 列表: {name, coID, url, parent(目录显示名)} —— 顺序即播放顺序。"""
    d = {}
    try:
        req = urllib.request.Request(
            YN_INFO, data=_yn_enc(json.dumps({"getOutLinkInfoReq": {
                "account": "", "linkID": link, "passwd": "", "caSrt": 1,
                "coSrt": 1, "srtDr": 0, "bNum": 1, "pCaID": caID, "eNum": 200}})).encode(),
            headers=YN_HDR, method="POST")
        d = (json.loads(_yn_dec(urllib.request.urlopen(req, timeout=60).read().decode()))
             .get("data") or {})
    except Exception:
        pass
    for co in (d.get("coLst") or []):
        nm = co.get("coName") or ""
        if not re.search(r"\.(mkv|mp4|ts|avi|rmvb|wmv|mov|webm|m3u8)$", nm, re.I):
            continue
        out.append({"name": nm, "coID": co.get("coID") or "",
                    "url": co.get("presentURL") or "", "parent": dirName})
    if depth >= 5:
        return
    for ca in (d.get("caLst") or []):
        _walk(link, ca.get("caID") or "", ca.get("caName") or "", out, depth + 1)


class Spider(BaseSpider):
    def init(self, extend=""):
        self.fp = hashlib.md5(
            ("AiNewYiDong4K_%d_%d" % (int(time.time() * 1000), time.time_ns()))
            .encode()).hexdigest()

    def getName(self):
        return "移动4K"

    # ── 站点 POST ─────────────────────────────
    def _post(self, path, data):
        try:
            req = urllib.request.Request(BASE + path,
                                         data=json.dumps(data).encode(),
                                         headers=HDR, method="POST")
            return json.load(urllib.request.urlopen(req, timeout=20))
        except Exception:
            return {}

    @staticmethod
    def _card(x):
        return {"vod_id": str(x.get("id", "")),
                "vod_name": x.get("title", ""),
                "vod_pic": x.get("appCoverUrl", ""),
                "vod_remarks": ""}

    # ── 139 云盘解密 ─────────────────────────
    @staticmethod
    def _yn_enc(text):
        if not _AES:
            return None
        iv = os.urandom(16)
        b = text.encode()
        b += bytes([16 - len(b) % 16]) * (16 - len(b) % 16)
        return base64.b64encode(
            iv + _AES.new(YN_KEY, _AES.MODE_CBC, iv).encrypt(b)).decode()

    @staticmethod
    def _yn_dec(text):
        if not _AES:
            return ""
        try:
            b = base64.b64decode(text)
            c = _AES.new(YN_KEY, _AES.MODE_CBC, b[:16]).decrypt(b[16:])
            return c[:-c[-1]].decode("utf-8", "ignore")
        except Exception:
            return ""

    def _yn_call(self, url, payload):
        enc = self._yn_enc(payload)
        if not enc:
            return {}
        try:
            req = urllib.request.Request(url, data=enc.encode(),
                                         headers=YN_HDR, method="POST")
            return json.loads(self._yn_dec(
                urllib.request.urlopen(req, timeout=60).read().decode()))
        except Exception:
            return {}

    def _yn_play(self, share_url, depth=0):
        """139 分享链接 -> 可播 m3u8 (递归进入子目录取第一个视频文件)。"""
        m = re.search(r"/i/([A-Za-z0-9]+)", share_url or "")
        if not m or depth > 3:
            return ""
        link = m.group(1)
        r = self._yn_call(YN_INFO, json.dumps({"getOutLinkInfoReq": {
            "account": "", "linkID": link, "passwd": "", "caSrt": 0,
            "coSrt": 0, "srtDr": 1, "bNum": 1, "pCaID": "root", "eNum": 200}}))
        d = r.get("data") or {}
        for co in (d.get("coLst") or []):
            u = co.get("presentURL") or ""
            if u.startswith("http"):
                return u
        for ca in (d.get("caLst") or []):
            caid = ca.get("caID")
            if not caid:
                continue
            r2 = self._yn_call(YN_INFO, json.dumps({"getOutLinkInfoReq": {
                "account": "", "linkID": link, "passwd": "", "caSrt": 1,
                "coSrt": 1, "srtDr": 0, "bNum": 1, "pCaID": caid, "eNum": 200}}))
            d2 = r2.get("data") or {}
            for co in (d2.get("coLst") or []):
                u = co.get("presentURL") or ""
                if u.startswith("http"):
                    return u
            for co in (d2.get("coLst") or []):
                cid = co.get("coID")
                if not cid:
                    continue
                r3 = self._yn_call(YN_CONTENT, json.dumps({
                    "getContentInfoFromOutLinkReq": {
                        "contentId": cid, "linkID": link, "account": ""},
                    "commonAccountInfo": {"account": "", "accountType": 1}}))
                u = (((r3.get("data") or {}).get("contentInfo") or {})
                     .get("presentURL")) or ""
                if u.startswith("http"):
                    return u
        return ""

    # ── 接口 ──────────────────────────────────
    def homeContent(self, filter):
        return {"class": [{"type_id": a, "type_name": b} for a, b in COLS],
                "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg or 1)
        d = self._post("/vidsite/vs/qryPageColumnVideo", {
            "columnId": int(tid), "cateIdList": [0, 0, 0],
            "pageIndex": page, "pageSize": 9}).get("data") or {}
        out = [self._card(x) for x in (d.get("list") or [])]
        return {"list": out, "page": page,
                "pagecount": max(1, int(d.get("pages") or 1)),
                "limit": 9, "total": int(d.get("total") or len(out))}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids).split(",")[0]
        self._post("/vidsite/vs/addAccessRecord",
                   {"fprint": self.fp, "deviceType": 1})
        d = self._post("/vidsite/vs/qryVideoDetail",
                       {"videoId": int(vid), "fprint": self.fp}).get("data") or {}
        if not d:
            return {"list": []}
        res_url = d.get("resUrl") or ""
        m = re.search(r"/i/([A-Za-z0-9]+)", res_url)
        episodes = ""
        cache_key = res_url
        if m:
            now = time.time()
            cached = _YNCACHE.get(cache_key)
            if cached and now - cached[0] < 600:
                episodes = cached[1]
            else:
                fl = []
                try:
                    _walk(m.group(1), "root", "", fl)  # 顶层用 root 作为 pCaID
                except Exception:
                    fl = []
                # 收集文件所在父目录, 判断是否有多个分组(多季)需要前缀
                parents = set(f.get("parent", "") for f in fl)
                need_pre = len(parents) > 1
                lines = []
                for f in fl:
                    nm = _ep_longname(f.get("name", ""))
                    if need_pre and f.get("parent"):
                        pm = re.search(r"^.*?([\u4e00-\u9fa5\w·\s]{2,20})$",
                                       f["parent"] or "")
                        pre = pm.group(1).strip() if pm else (f["parent"] or "")
                        nm = "%s·%s" % (pre, nm)
                    u = f.get("url") or ""
                    if u:
                        lines.append("%s$%s" % (nm, u))
                    else:
                        lines.append("%s$url:%s" % (nm, res_url))
                episodes = "#".join(lines)
                _YNCACHE[cache_key] = (now, episodes)
        return {"list": [{
            "vod_id": vid,
            "vod_name": d.get("title", vid),
            "vod_pic": d.get("appCoverUrl", ""),
            "vod_year": "",
            "vod_actor": d.get("actor", "") or "",
            "vod_director": d.get("director", "") or "",
            "vod_content": d.get("remark", ""),
            "vod_play_from": "移动云盘",
            "vod_play_url": episodes or ("正片$url:" + res_url),
        }]}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id)
        if raw.startswith("url:"):
            # 走分享链接兜底解析
            real = self._yn_play(raw[4:]) or raw[4:]
            u = real
        else:
            u = raw  # 已是直链 m3u8
        return {"parse": 0, "playUrl": "", "url": u, "jx": 0,
                "header": {"User-Agent": YN_HDR["User-Agent"],
                           "Referer": "https://yun.139.com/"}}

    def searchContent(self, key, quick, pg):
        d = self._post("/vidsite/vs/qryPageColumnVideo",
                       {"columnId": 0, "cateIdList": [0, 0, 0], "pageIndex": 1,
                        "pageSize": 9, "searchKey": key}).get("data") or {}
        out = [self._card(x) for x in (d.get("list") or [])]
        return {"list": out, "page": 1, "pagecount": 1, "limit": 9,
                "total": int(d.get("total") or len(out))}

    def isVideoFormat(self, url):
        return any(s in str(url).lower() for s in (".m3u8", ".mp4"))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return ""
