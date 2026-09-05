# -*- coding: utf-8 -*-
import gzip
import hashlib
import hmac
import json
import os
import time
import uuid
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

class _AESCBC:
    @staticmethod
    def encrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            return AES.new(key, AES.MODE_CBC, iv).encrypt(_AESCBC.pad(data))
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            enc = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).encryptor()
            return enc.update(_AESCBC.pad(data)) + enc.finalize()

    @staticmethod
    def decrypt(data, key, iv):
        try:
            from Crypto.Cipher import AES
            plain = AES.new(key, AES.MODE_CBC, iv).decrypt(data)
        except Exception:
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            dec = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend()).decryptor()
            plain = dec.update(data) + dec.finalize()
        return _AESCBC.unpad(plain)

    @staticmethod
    def pad(data):
        n = 16 - len(data) % 16
        return data + bytes([n]) * n

    @staticmethod
    def unpad(data):
        n = data[-1] if data else 0
        return data[:-n] if 1 <= n <= 16 else data

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://tideember.cc"
        self.api = self.host + "/api"
        self.name = "黄豆短剧"
        # -------- 可配置参数（可从extend中覆盖） --------
        self.platform_key = "7961beb44246e3012ce228d6b5ced05a"
        self.version = "2.0.0"
        self.device_type = "web"          # 可改为 "flutter_web"
        # ---------------------------------------------
        self.session_id = uuid.uuid4().hex
        self.device_id = self.session_id   # 通常与session_id一致
        self.token = ""                    # 若需要登录后可设置
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Origin": self.host,
            "Referer": self.host + "/home",
            "Content-Type": "application/octet-stream",
            "Accept-Encoding": "gzip, deflate, br",   # 增加
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        # 添加重试策略
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.class_cache = None
        self.filter_cache = {}

    def init(self, extend=""):
        if extend:
            try:
                cfg = json.loads(extend)
                if cfg.get("site") or cfg.get("base_url"):
                    self.host = (cfg.get("site") or cfg.get("base_url")).rstrip("/")
                    self.api = self.host + "/api"
                self.token = cfg.get("token", self.token)
                self.platform_key = cfg.get("platform_key", self.platform_key)
                self.version = cfg.get("version", self.version)
                self.device_type = cfg.get("device_type", self.device_type)
                # 更新headers
                self.headers["Origin"] = self.host
                self.headers["Referer"] = self.host + "/home"
                self.session.headers.update(self.headers)
            except Exception:
                pass

    def getName(self):
        return self.name

    def homeContent(self, filter):
        data = self._api("/drama/list", {"page": "1", "page_size": "18"})
        classes = self._classes()
        return {
            "class": classes,
            "filters": self._filters(classes),
            "list": [self._vod(x) for x in self._list(data)],
            "parse": 0,
            "jx": 0
        }

    def categoryContent(self, tid, pg, filter, extend):
        extend = extend or {}
        if tid == "yuandou":
            data = self._api("/drama/navBlock", {"code": "yuandou", "tab": "recommend", "page": str(pg)})
            items = self._nav_items(data)
        else:
            req = {"page": str(pg), "page_size": "18"}
            if tid and tid not in ("all", "recommend"):
                tabs = self._nav_filter(tid)
                idx = self._int(extend.get("sub"), 0)
                sub = tabs[idx] if tabs and 0 <= idx < len(tabs) else {}
                flt = sub.get("filter", {}) if isinstance(sub, dict) else {}
                req["cat_id"] = flt.get("cat_id", "")
                if flt.get("tag_id"):
                    req["tag_id"] = flt.get("tag_id", "")
                req["order"] = flt.get("order", "") or extend.get("order", "")
            elif extend.get("order"):
                req["order"] = extend.get("order")
            if extend.get("update_status"):
                req["update_status"] = extend.get("update_status")
            data = self._api("/drama/list", req)
            items = self._list(data)
        return {
            "page": int(pg),
            "pagecount": int(pg) if len(items) < 18 else int(pg) + 1,
            "limit": 18,
            "total": 99999,
            "list": [self._vod(x) for x in items],
            "parse": 0,
            "jx": 0
        }

    def detailContent(self, ids):
        vid = str(ids[0]).replace("rp_", "")
        obj = self._api("/drama/detail", {"id": vid})
        data = obj.get("data", obj) if isinstance(obj, dict) else {}
        if not isinstance(data, dict):
            return {"list": []}
        data = self._unlock(data)
        vod_id = self._sid(data.get("id") or data.get("drama_id") or vid)
        name = data.get("name") or data.get("title") or data.get("t") or vod_id
        eps = data.get("episodes") if isinstance(data.get("episodes"), list) else []
        count = self._int(data.get("episode_count") or data.get("free_episodes"), len(eps) or 1)
        play = []
        if eps:
            for i, ep in enumerate(eps, 1):
                seq = ep.get("seq") or ep.get("episode") or ep.get("ep") or i
                play.append("%s$%s|%s" % (ep.get("name") or ep.get("title") or "第%s集" % seq, vod_id, seq))
        else:
            play = ["第%s集$%s|%s" % (i, vod_id, i) for i in range(1, count + 1)]
        vod = {
            "vod_id": vod_id,
            "vod_name": name,
            "vod_pic": self._pic(data),
            "type_name": data.get("category") or data.get("type") or "",
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": data.get("update_label") or "全%s集" % count,
            "vod_actor": "",
            "vod_director": "",
            "vod_content": data.get("description") or data.get("summary") or name,
            "vod_play_from": self.name,
            "vod_play_url": "#".join(play)
        }
        return {"list": [vod], "parse": 0, "jx": 0}

    def searchContent(self, key, quick, pg="1"):
        data = self._api("/drama/list", {"page": str(pg), "page_size": "18", "keywords": str(key)})
        items = self._list(data)
        return {
            "page": int(pg),
            "pagecount": int(pg) if len(items) < 18 else int(pg) + 1,
            "limit": 18,
            "total": 99999,
            "list": [self._vod(x) for x in items],
            "parse": 0,
            "jx": 0
        }

    def playerContent(self, flag, id, vipFlags):
        vid, seq = self._split(id)
        obj = self._api("/drama/play", {"id": vid, "seq": str(seq)}, True)
        data = obj.get("data", {}) if isinstance(obj, dict) else {}
        url = data.get("m3u8") or data.get("url") or self._hls(vid, seq)
        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "jx": 0,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": self.host + "/home",
                "Origin": self.host
            }
        }

    # ==================== 核心请求方法（修复增强） ====================
    def _api(self, path, data=None, silent=False):
        path = "/" + path.lstrip("/")
        rid = str(uuid.uuid4())
        key = self._key(rid)
        iv = os.urandom(16)
        raw = json.dumps({
            "token": self.token or "",
            "deviceId": self.device_id,
            "data": data or {}
        }, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        body = iv + _AESCBC.encrypt(gzip.compress(raw), key, iv)
        ts = int(time.time())
        # 签名（注意顺序）
        sign_raw = "Dart|%s|%s|%s|%s" % (self.session_id, rid, ts, path)
        sign = hashlib.sha256(sign_raw.encode("utf-8")).hexdigest() + "-" + str(ts)
        # 构造请求头
        h = dict(self.headers)
        h.update({
            "version": self.version,
            "deviceType": self.device_type,
            "time": str(ts),
            "sign": sign,
            "requestId": rid,
            "sessionId": self.session_id,
            "deviceBrand": "",
            "deviceModel": "",
            "systemName": "",
            "systemVersion": ""
        })
        try:
            r = self.session.post(self.api + path, data=body, headers=h, timeout=20, verify=False)
            r.raise_for_status()
            return self._decode(r.content, rid)
        except requests.exceptions.RequestException as e:
            if not silent:
                print(f"Request error: {e}")
            return {}
        except Exception as e:
            if not silent:
                print(f"Unexpected error: {e}")
            return {}

    def _key(self, rid):
        # 使用 platform_key 作为 HMAC 密钥，对请求ID（去连字符）进行SHA256
        return hmac.new(
            self.platform_key.encode("utf-8"),
            bytes.fromhex(str(rid).replace("-", "")),
            hashlib.sha256
        ).digest()

    def _decode(self, blob, rid):
        """
        修复：优先尝试解密，如果失败则尝试直接解析JSON（可能返回明文错误信息）。
        增加对压缩数据的判断。
        """
        # 如果数据为空或太短，尝试直接解析
        if not blob or len(blob) < 32:
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                return {}
        # 尝试解密
        try:
            plain = _AESCBC.decrypt(blob[16:], self._key(rid), blob[:16])
            # 检查是否gzip压缩
            if plain[:2] == b"\x1f\x8b":
                plain = gzip.decompress(plain)
            return json.loads(plain.decode("utf-8"))
        except Exception:
            # 解密失败，尝试直接解析（可能服务器返回未加密的JSON）
            try:
                return json.loads(blob.decode("utf-8"))
            except Exception:
                return {}

    # ==================== 辅助方法 ====================
    def _classes(self):
        if self.class_cache:
            return self.class_cache
        arr = [{"type_id": "all", "type_name": "全部短剧"}]
        data = self._api("/drama/navList", {})
        # 兼容多种数据结构
        items = self._list(data.get("data", data) if isinstance(data, dict) else data)
        for item in items:
            tid = str(item.get("code") or item.get("id") or item.get("cat_id") or "")
            name = item.get("name") or item.get("title") or tid
            if tid and name:
                arr.append({"type_id": tid, "type_name": name})
        self.class_cache = arr
        return arr

    def _filters(self, classes):
        common = [
            {"key": "order", "name": "排序", "value": [{"n": "默认", "v": ""}, {"n": "最新", "v": "new"}, {"n": "最热", "v": "hot"}]},
            {"key": "update_status", "name": "状态", "value": [{"n": "全部", "v": ""}, {"n": "连载", "v": "0"}, {"n": "完结", "v": "1"}]}
        ]
        fs = {}
        for c in classes:
            tid = c["type_id"]
            tabs = self._nav_filter(tid) if tid not in ("all", "yuandou") else []
            fs[tid] = ([{"key": "sub", "name": "子分类", "value": [{"n": t.get("name", "默认"), "v": str(i)} for i, t in enumerate(tabs)]}] if tabs else []) + common
        return fs

    def _nav_filter(self, code):
        if code not in self.filter_cache:
            data = self._api("/drama/navFilter", {"code": str(code)})
            self.filter_cache[code] = self._list(data.get("data", data) if isinstance(data, dict) else data)
        return self.filter_cache.get(code, [])

    def _list(self, data):
        """递归提取列表，兼容多种返回格式"""
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ["list", "items", "data"]:
            val = data.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                return self._list(val)  # 递归
        return []

    def _nav_items(self, data):
        blocks = self._list(data.get("data", data) if isinstance(data, dict) else data)
        items = []
        for b in blocks:
            if isinstance(b, dict) and isinstance(b.get("items"), list):
                items += b.get("items")
            elif isinstance(b, dict) and (b.get("id") or b.get("drama_id")):
                items.append(b)
        return items

    def _vod(self, item):
        item = item or {}
        vid = self._sid(item.get("id") or item.get("drama_id") or "")
        remarks = item.get("update_label") or item.get("corner") or ("全%s集" % item.get("episode_count") if item.get("episode_count") else "")
        return {
            "vod_id": vid,
            "vod_name": item.get("name") or item.get("title") or item.get("t") or vid,
            "vod_pic": self._pic(item),
            "vod_remarks": remarks
        }

    def _pic(self, item):
        return item.get("img_y") or item.get("img_x") or item.get("img") or item.get("cover") or item.get("pic") or ""

    def _unlock(self, d):
        """强制解锁付费内容（模拟VIP）"""
        eps = d.get("episodes")
        if isinstance(eps, list):
            for ep in eps:
                if isinstance(ep, dict):
                    ep["is_buy"] = True
                    ep["type"] = "free"
                    ep["price"] = 0
                    ep["methods"] = []
        d.update({
            "pay_type": "free",
            "money": 0,
            "episode_price": 0,
            "points_price": 0,
            "can_vip_watch": True,
            "is_buy_whole": True,
            "vip_episodes": [],
            "coin_episodes": [],
            "points_episodes": []
        })
        return d

    def _sid(self, x):
        return str(x or "").replace("rp_", "")

    def _split(self, x):
        p = str(x).split("|", 1)
        return self._sid(p[0]), p[1] if len(p) > 1 and p[1] else "1"

    def _hls(self, vid, seq):
        # 播放地址可能需动态拼接，保留原逻辑
        return "%s/api/drama/hls/%s/%s/play.m3u8?line=free" % (self.host, self._sid(vid), seq)

    def _int(self, x, d=0):
        try:
            return int(x)
        except Exception:
            return d