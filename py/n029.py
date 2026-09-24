# -*- coding: utf-8 -*-
import requests
import time
import re

class Spider:
    def __init__(self):
        self.baseurl = "https://m.xgshort.com"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Referer": self.baseurl + "/movie",
            "Origin": self.baseurl,
        })
        self.token = None
        self.token_expire = 0
        self.categories = []
        self.CLASSICAL_MAP = {
            "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫", "淫秽": "猥亵",
            "激情": "云雨", "做爱": "云雨", "性交": "交欢", "欲": "情思", "高潮": "云端",
            "偷拍": "窥帘", "偷窥": "窥帘", "乱伦": "禁脔", "强奸": "强占", "无码": "素纱",
            "有码": "遮面", "熟女": "徐娘", "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉",
            "学生": "书生", "人妻": "罗敷", "护士": "药女", "教师": "先生", "丝袜": "丝履",
            "巨乳": "丰盈", "臀": "玉臀", "脚": "莲步", "赌博": "孤注", "毒品": "药石",
            "广告": "告示", "暴力": "杀伐", "恐怖": "幽冥", "裸体": "玉体", "自慰": "弄玉",
            "口交": "含朱", "肛交": "后庭", "群交": "合卺", "车震": "车行", "野战": "郊合",
        }
        self.MINOR_KEYWORDS = ["萝莉", "幼女", "少女", "学生", "童", "未成年", "teen", "loli", "schoolgirl", "豆蔻", "玉蕊", "碧玉", "书生", "稚子"]

    def desensitize(self, text):
        if not text:
            return text
        if isinstance(text, (int, float)):
            return text
        result = str(text)
        for k, v in self.CLASSICAL_MAP.items():
            result = result.replace(k, v)
        return result

    def is_minor(self, text):
        if not text:
            return False
        t = str(text).lower()
        for kw in self.MINOR_KEYWORDS:
            if kw.lower() in t:
                return True
        return False

    def getDependence(self):
        return ""

    def init(self, extend):
        try:
            cfg = extend
            if isinstance(extend, str):
                import json as _json
                cfg = _json.loads(extend)
            if isinstance(cfg, dict):
                if cfg.get("baseurl"):
                    self.baseurl = cfg["baseurl"]
        except:
            pass
        self._ensure_token()

    def _ensure_token(self):
        now = time.time()
        if self.token and now < self.token_expire:
            return True
        return self._guest_login()

    def _guest_login(self):
        for i in range(10):
            try:
                self.session.get(self.baseurl + "/movie", timeout=10)
                time.sleep(0.3)
                r = self.session.post(
                    self.baseurl + "/api/auth/guest-login",
                    json={"guestToken": ""},
                    timeout=10,
                )
                if r.status_code == 200:
                    data = r.json()
                    token = data.get("access_token", "")
                    if token:
                        self.token = token
                        self.token_expire = time.time() + data.get("expires_in", 604800) - 300
                        self.session.headers["Authorization"] = "Bearer " + token
                        return True
            except:
                pass
            time.sleep(1)
        return False

    def _get(self, path, params=None, need_token=False):
        if need_token:
            self._ensure_token()
        for _ in range(3):
            try:
                r = self.session.get(self.baseurl + path, params=params, timeout=15)
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 401 and need_token:
                    self.token = None
                    self._ensure_token()
                    continue
            except:
                time.sleep(0.5)
        return None

    def _post(self, path, data, need_token=False):
        if need_token:
            self._ensure_token()
        for _ in range(3):
            try:
                r = self.session.post(self.baseurl + path, json=data, timeout=15)
                if r.status_code in (200, 201):
                    return r.json()
                if r.status_code == 401 and need_token:
                    self.token = None
                    self._ensure_token()
                    continue
            except:
                time.sleep(0.5)
        return None

    def _load_categories(self):
        if self.categories:
            return self.categories
        data = self._get("/api/home/categories")
        if data and isinstance(data, list):
            self.categories = data
        return self.categories

    def _parse_vod(self, item, category_name=""):
        title = item.get("seriesTitle", item.get("title", ""))
        if self.is_minor(title):
            return None
        vod_id = item.get("seriesShortId", item.get("shortId", ""))
        if not vod_id:
            return None
        cover = item.get("seriesCoverUrl", item.get("coverUrl", ""))
        desc = item.get("seriesDescription", item.get("description", ""))
        remarks = item.get("updateStatus", "")
        if item.get("isSerial"):
            remarks = remarks or "连载"
        else:
            remarks = remarks or "全一集"
        score = item.get("seriesScore", item.get("score", 0))
        if score:
            remarks = str(score) + "分 " + remarks
        return {
            "vod_id": str(vod_id),
            "vod_name": self.desensitize(title),
            "vod_pic": cover,
            "vod_remarks": self.desensitize(remarks),
            "vod_content": self.desensitize(desc),
            "vod_actor": self.desensitize(item.get("seriesStarring", item.get("seriesActor", ""))),
            "vod_year": "",
            "vod_area": "",
            "vod_director": "",
        }

    def homeContent(self, filter=True):
        cats = self._load_categories()
        class_list = []
        filters = {}
        for c in cats:
            if c.get("isEnabled", True):
                cid = str(c.get("id", ""))
                cname = self.desensitize(c.get("name", ""))
                if self.is_minor(cname):
                    continue
                class_list.append({"type_id": cid, "type_name": cname})
                filters[cid] = []
        video_list = []
        data = self._get("/api/home/gethomemodules", params={"channeid": 1})
        if data and isinstance(data, dict):
            modules = data.get("data", {}).get("list", [])
            for mod in modules:
                if mod.get("type") == 3:
                    for item in mod.get("list", []):
                        vod = self._parse_vod(item)
                        if vod:
                            video_list.append(vod)
                elif mod.get("type") == 0:
                    for b in mod.get("banners", []):
                        item = dict(b)
                        item["seriesShortId"] = b.get("shortId", "")
                        vod = self._parse_vod(item)
                        if vod:
                            video_list.append(vod)
        return {"class": class_list, "filters": filters, "list": video_list}

    def homeVideoContent(self):
        data = self._get("/api/home/gethomemodules", params={"channeid": 1})
        video_list = []
        if data and isinstance(data, dict):
            modules = data.get("data", {}).get("list", [])
            for mod in modules:
                if mod.get("type") == 3:
                    for item in mod.get("list", []):
                        vod = self._parse_vod(item)
                        if vod:
                            video_list.append(vod)
        return {"page": 1, "pagecount": 1, "limit": 20, "total": len(video_list), "list": video_list}

    def categoryContent(self, tid, pg, filter, extend):
        video_list = []
        try:
            chid = int(tid)
        except:
            chid = tid
        data = self._get("/api/home/gethomemodules", params={"channeid": chid})
        total = 0
        if data and isinstance(data, dict):
            modules = data.get("data", {}).get("list", [])
            for mod in modules:
                if mod.get("type") == 3:
                    items = mod.get("list", [])
                    total = len(items)
                    for item in items:
                        vod = self._parse_vod(item)
                        if vod:
                            video_list.append(vod)
        pagecount = 1 if total > 0 else 0
        return {"page": pg, "pagecount": pagecount, "limit": 20, "total": total, "list": video_list}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if isinstance(ids, str):
            ids = [ids]
        result_list = []
        for vod_id in ids:
            vid = str(vod_id)
            data = self._get("/api/video/episodes", params={"seriesShortId": vid, "size": 500}, need_token=True)
            episodes = []
            vod_name = ""
            vod_pic = ""
            vod_content = ""
            vod_remarks = ""
            vod_actor = ""
            if data and isinstance(data, dict):
                eps = data.get("data", {}).get("list", [])
                if isinstance(eps, list):
                    for ep in eps:
                        ep_title = ep.get("episodeTitle", str(ep.get("episodeNumber", "")))
                        if self.is_minor(ep_title):
                            continue
                        ep_key = ep.get("episodeAccessKey", "")
                        if not ep_key:
                            continue
                        episodes.append((ep_title, ep_key))
                        if not vod_name:
                            vod_name = ep.get("seriesTitle", "")
                            vod_pic = ""
                            vod_actor = ep.get("seriesActor", "")
            if not vod_name:
                rec = self._get("/api/video/recommend")
                if rec and isinstance(rec, dict):
                    for item in rec.get("data", {}).get("list", []):
                        if str(item.get("seriesShortId", "")) == vid:
                            vod_name = item.get("seriesTitle", "")
                            vod_pic = item.get("seriesCoverUrl", "")
                            vod_content = item.get("seriesDescription", "")
                            vod_remarks = item.get("updateStatus", "")
                            vod_actor = item.get("seriesStarring", "")
                            break
            if self.is_minor(vod_name):
                continue
            play_from = "全集"
            play_urls = []
            for ep_title, ep_key in episodes:
                play_urls.append(self.desensitize(ep_title) + "$" + ep_key)
            vod = {
                "vod_id": vid,
                "vod_name": self.desensitize(vod_name),
                "vod_pic": vod_pic,
                "vod_remarks": self.desensitize(vod_remarks),
                "vod_content": self.desensitize(vod_content),
                "vod_actor": self.desensitize(vod_actor),
                "vod_director": "",
                "vod_year": "",
                "vod_area": "",
                "vod_play_from": play_from,
                "vod_play_url": "$$$".join(play_urls) if play_urls else "",
            }
            result_list.append(vod)
        return {"list": result_list}

    def searchContent(self, key, quick):
        video_list = []
        data = self._get("/api/list/fuzzysearch", params={"keyword": key, "page": 1, "size": 20})
        if data and isinstance(data, dict):
            items = data.get("data", {}).get("list", [])
            if isinstance(items, list):
                for item in items:
                    title = item.get("seriesTitle", item.get("title", ""))
                    if self.is_minor(title):
                        continue
                    sid = item.get("seriesShortId", item.get("shortId", ""))
                    if not sid:
                        continue
                    video_list.append({
                        "vod_id": str(sid),
                        "vod_name": self.desensitize(title),
                        "vod_pic": item.get("seriesCoverUrl", item.get("coverUrl", "")),
                        "vod_remarks": self.desensitize(item.get("updateStatus", "")),
                        "vod_content": "",
                        "vod_actor": "",
                    })
        return {"page": 1, "pagecount": 1, "limit": 20, "total": len(video_list), "list": video_list}

    def playerContent(self, flag, id, vipFlags):
        ep_key = str(id)
        data = self._post(
            "/api/video/episode-url/query",
            {"type": "episode", "accessKey": ep_key},
            need_token=True,
        )
        play_url = ""
        if data and isinstance(data, dict):
            urls = data.get("data", {}).get("urls", [])
            if isinstance(urls, list) and urls:
                play_url = urls[0].get("cdnUrl", "")
        fmt = "application/x-mpegURL" if ".m3u8" in play_url else "video/mp4"
        return {
            "parse": 0,
            "jx": 0,
            "url": play_url,
            "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.baseurl + "/"},
            "format": fmt,
        }

    def localProxy(self, param):
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def action(self, action):
        pass

    def destroy(self):
        self.session.close()
