import json, base64, time, hashlib
import urllib.request as ur
import urllib.parse as up
import urllib.error as ue

class Spider:
    def __init__(self):
        self.api_bases = [
            "https://hgxml.00api-agy5u.com/api",
            "https://rules.googlexml.com/api",
            "https://awsapi.ipa001-7hzktt.com/api",
        ]
        self.img_base = "https://haguapi.huangguo.top"
        self.domain_key = "HgApiCache#e0ae36"
        self.token = None
        self.token_expire = 0
        self.cache = {}
        self.cache_ttl = 300
        self.ua = "Mozilla/5.0 (Linux; Android 12; Pixel 6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        self.classical_map = {
            "成人": "风月", "淫乱": "荒淫", "婊": "贱", "强奸": "强占",
            "无码": "素纱", "有码": "遮面", "熟女": "徐娘", "人妻": "罗敷",
            "护士": "药女", "教师": "先生", "丝袜": "丝履", "巨乳": "丰盈",
            "偷拍": "窥帘", "乱伦": "禁脔", "激情": "云雨", "色情": "春宫",
            "淫秽": "秽乱", "赌博": "孤注", "广告": "告示", "荡妇": "淫娃",
            "出轨": "逾墙", "偷情": "私会", "绿帽": "翠冠", "娇妻": "美眷",
            "嫩": "稚", "骚": "浪", "欲": "念", "肉": "身", "穴": "谷",
        }
        self.minor_map = {
            "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
            "童": "稚子", "未成年": "未及笄", "teen": "豆蔻", "loli": "豆蔻",
            "schoolgirl": "书生",
        }

    def getDependence(self):
        return ""

    def init(self, extend):
        try:
            if isinstance(extend, str):
                cfg = json.loads(extend)
            elif isinstance(extend, dict):
                cfg = extend
            else:
                cfg = {}
            if cfg.get("api_bases"):
                self.api_bases = cfg["api_bases"]
            if cfg.get("img_base"):
                self.img_base = cfg["img_base"]
        except Exception:
            pass

    def _xor_decrypt(self, text):
        if not text or not text.startswith("h1."):
            return text
        try:
            raw = base64.b64decode(text[3:])
            key = self.domain_key.encode("utf-8")
            result = bytearray()
            for i, b in enumerate(raw):
                result.append(b ^ key[i % len(key)])
            return result.decode("utf-8", errors="ignore")
        except Exception:
            return text

    def _fetch_domains(self):
        for base in self.api_bases:
            try:
                data = self._request(base + "/app/config", auth=False)
                if data and data.get("domains"):
                    domains = data["domains"]
                    apis = [self._xor_decrypt(d) for d in domains.get("api", [])]
                    apis = [d.rstrip("/") + "/api" for d in apis if d]
                    if apis:
                        self.api_bases = apis
                    return
            except Exception:
                continue

    def _ensure_token(self):
        if self.token and time.time() < self.token_expire:
            return
        for base in self.api_bases:
            try:
                body = json.dumps({"device_id": "web_tvbox_" + hashlib.md5(str(time.time()).encode()).hexdigest()[:16]}).encode("utf-8")
                req = ur.Request(base + "/app/auth/device", data=body, method="POST")
                req.add_header("User-Agent", self.ua)
                req.add_header("Content-Type", "application/json")
                req.add_header("Accept", "application/json")
                resp = ur.urlopen(req, timeout=10)
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("token"):
                    self.token = data["token"]
                    self.token_expire = time.time() + 86400
                    return
            except Exception:
                continue

    def _request(self, url, auth=True, method="GET", body=None):
        cache_key = url + "|" + method + "|" + (body or "")
        if cache_key in self.cache and time.time() - self.cache[cache_key]["ts"] < self.cache_ttl:
            return self.cache[cache_key]["data"]
        if auth:
            self._ensure_token()
        last_err = None
        for base in self.api_bases:
            full_url = url
            if url.startswith("/app/"):
                full_url = base + url
            try:
                data = body.encode("utf-8") if body else None
                req = ur.Request(full_url, data=data, method=method)
                req.add_header("User-Agent", self.ua)
                req.add_header("Accept", "application/json")
                req.add_header("Referer", "https://google.huge1-7wnjsk.com/")
                if auth and self.token:
                    req.add_header("Authorization", "Bearer " + self.token)
                if body:
                    req.add_header("Content-Type", "application/json")
                resp = ur.urlopen(req, timeout=15)
                raw = resp.read().decode("utf-8")
                result = json.loads(raw)
                self.cache[cache_key] = {"ts": time.time(), "data": result}
                return result
            except ue.HTTPError as e:
                if e.code == 401 and auth:
                    self.token = None
                    self.token_expire = 0
                    self._ensure_token()
                    if self.token:
                        try:
                            data2 = body.encode("utf-8") if body else None
                            req2 = ur.Request(full_url, data=data2, method=method)
                            req2.add_header("User-Agent", self.ua)
                            req2.add_header("Accept", "application/json")
                            req2.add_header("Referer", "https://google.huge1-7wnjsk.com/")
                            req2.add_header("Authorization", "Bearer " + self.token)
                            if body:
                                req2.add_header("Content-Type", "application/json")
                            resp2 = ur.urlopen(req2, timeout=15)
                            result2 = json.loads(resp2.read().decode("utf-8"))
                            self.cache[cache_key] = {"ts": time.time(), "data": result2}
                            return result2
                        except Exception:
                            pass
                last_err = e
            except Exception as e:
                last_err = e
        if last_err:
            raise last_err
        return None

    def _fix_cover(self, cover):
        if not cover:
            return ""
        if cover.startswith("http"):
            return cover
        if cover.startswith("//"):
            return "https:" + cover
        return self.img_base + "/" + cover.lstrip("/")

    def _is_minor(self, text):
        if not text:
            return False
        for k in self.minor_map:
            if k.lower() in text.lower():
                return True
        return False

    def desensitize(self, text):
        if not text:
            return text
        has_sensitive = any(k in text for k in self.classical_map)
        if not has_sensitive:
            return text
        result = text
        for k, v in self.classical_map.items():
            result = result.replace(k, v)
        return result

    def _vod_from_item(self, item):
        if not item:
            return None
        title = item.get("title", "")
        if self._is_minor(title):
            return None
        return {
            "vod_id": str(item.get("id", "")),
            "vod_name": self.desensitize(title),
            "vod_pic": self._fix_cover(item.get("cover", "")),
            "vod_remarks": str(item.get("episode_count", "1")) + "集",
            "vod_year": item.get("year", ""),
            "vod_area": "",
            "vod_author": "",
            "vod_content": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

    def homeContent(self, filter=False):
        classes = []
        filters = {}
        try:
            cat_data = self._request("/app/categories")
            if cat_data and cat_data.get("list"):
                for c in cat_data["list"]:
                    cid = str(c["id"])
                    cname = self.desensitize(c.get("name", ""))
                    if self._is_minor(cname):
                        continue
                    classes.append({"type_id": cid, "type_name": cname})
                    filters[cid] = [
                        {"key": "badge", "name": "标签", "init": "", "value": [
                            {"n": "全部", "v": ""},
                            {"n": "18+", "v": "18+"},
                            {"n": "漫剧", "v": "漫剧"},
                            {"n": "擦边", "v": "擦边"},
                        ]},
                        {"key": "status", "name": "状态", "init": "", "value": [
                            {"n": "全部", "v": ""},
                            {"n": "完结", "v": "ended"},
                            {"n": "连载", "v": "ongoing"},
                        ]},
                    ]
        except Exception:
            pass
        if not classes:
            classes = [{"type_id": "1", "type_name": "首页推荐"}]
            filters["1"] = []
        videos = []
        try:
            home_data = self._request("/app/home?page=1&pageSize=20")
            if home_data:
                for item in home_data.get("latest", []) or []:
                    v = self._vod_from_item(item)
                    if v:
                        videos.append(v)
        except Exception:
            pass
        return {"class": classes, "filters": filters, "list": videos}

    def homeVideoContent(self):
        videos = []
        try:
            home_data = self._request("/app/home?page=1&pageSize=20")
            if home_data:
                for item in home_data.get("latest", []) or []:
                    v = self._vod_from_item(item)
                    if v:
                        videos.append(v)
        except Exception:
            pass
        return {"page": 1, "pagecount": 1, "limit": 20, "total": len(videos), "list": videos}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg) if pg else 1
        params = [("category_id", tid), ("page", str(page)), ("pageSize", "20")]
        if extend:
            if isinstance(extend, dict):
                for k, v in extend.items():
                    if v:
                        params.append((k, v))
        url = "/app/filter?" + up.urlencode(params)
        videos = []
        total = 0
        pagecount = 1
        try:
            data = self._request(url)
            if data:
                for item in data.get("list", []) or []:
                    v = self._vod_from_item(item)
                    if v:
                        videos.append(v)
                total = len(videos) + (page - 1) * 20
                pagecount = page + 1 if len(videos) >= 20 else page
        except Exception:
            pass
        return {"page": page, "pagecount": pagecount, "limit": 20, "total": total, "list": videos}

    def detailContent(self, ids):
        if isinstance(ids, str):
            ids = [ids]
        elif isinstance(ids, (list, tuple)):
            pass
        else:
            ids = [str(ids)]
        results = []
        for vid in ids:
            try:
                detail = self._request("/app/dramas/" + str(vid))
                if not detail:
                    continue
                title = self.desensitize(detail.get("title", ""))
                if self._is_minor(title):
                    continue
                eps_data = self._request("/app/dramas/" + str(vid) + "/episodes")
                play_list = []
                if eps_data and eps_data.get("list"):
                    for ep in eps_data["list"]:
                        ep_title = self.desensitize(ep.get("title", "第" + str(ep.get("ep", "")) + "集"))
                        play_list.append(ep_title + "$" + str(ep["id"]))
                play_url = "#".join(play_list)
                cat_name = ""
                if detail.get("category"):
                    cat_name = self.desensitize(detail["category"].get("name", ""))
                results.append({
                    "vod_id": str(detail.get("id", "")),
                    "vod_name": title,
                    "vod_pic": self._fix_cover(detail.get("cover", "")),
                    "vod_remarks": detail.get("remarks", "") or detail.get("status_text", ""),
                    "vod_year": detail.get("year", ""),
                    "vod_area": "",
                    "vod_author": "",
                    "vod_content": self.desensitize(detail.get("description", "") or title),
                    "vod_play_from": "黄果漫剧",
                    "vod_play_url": play_url,
                    "type_name": cat_name,
                })
            except Exception:
                continue
        return {"list": results}

    def searchContent(self, key, pg=False):
        videos = []
        try:
            page = pg if isinstance(pg, int) and pg > 0 else 1
            url = "/app/search?" + up.urlencode([("q", key), ("page", str(page)), ("pageSize", "20")])
            data = self._request(url)
            if data and data.get("list"):
                for item in data["list"]:
                    v = self._vod_from_item(item)
                    if v:
                        videos.append(v)
        except Exception:
            pass
        return {"page": 1, "pagecount": 1, "limit": 20, "total": len(videos), "list": videos}

    def playerContent(self, flag, id, vipFlags):
        try:
            data = self._request("/app/play/" + str(id))
            if data and data.get("can_play") and data.get("play_url"):
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": data["play_url"],
                    "header": {
                        "User-Agent": self.ua,
                        "Referer": "https://google.huge1-7wnjsk.com/",
                    },
                    "format": "application/x-mpegURL",
                }
        except Exception:
            pass
        return {"parse": 0, "jx": 0, "url": "", "header": {}}

    def localProxy(self, param):
        try:
            if not param:
                return [404, "text/plain", ""]
            url = param
            if param.startswith("cover/"):
                slug = param[6:]
                url = self.img_base + "/storage/series/" + slug
            elif param.startswith("http"):
                url = param
            req = ur.Request(url)
            req.add_header("User-Agent", self.ua)
            req.add_header("Referer", "https://google.huge1-7wnjsk.com/")
            resp = ur.urlopen(req, timeout=15)
            content = resp.read()
            ctype = resp.headers.get("Content-Type", "image/jpeg")
            return {"code": 200, "content": content, "headers": {"Content-Type": ctype}}
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return url.endswith(".m3u8") or ".m3u8" in url

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        self.token = None
        self.cache.clear()
