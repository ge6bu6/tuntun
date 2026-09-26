# -*- coding: utf-8 -*-
import re
import sys
import json
import base64
import html as html_lib
import urllib.parse
import urllib.request
import http.cookiejar
import ssl

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    host = "https://blue.xdrgcewe.cc"
    UA = (
        "Mozilla/5.0 (Linux; Android 13; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    )
    categories = [
        {"type_name": "首页推荐", "type_id": "home"},
        {"type_name": "排行榜", "type_id": "rank"},
        {"type_name": "剧场", "type_id": "theater"},
        {"type_name": "最新", "type_id": "new"},
    ]

    def init(self, extend=""):
        self.host = "https://blue.xdrgcewe.cc"
        ext = (extend or "").strip()
        if ext.startswith("http"):
            self.host = ext.rstrip("/")
        elif ext.startswith("{"):
            try:
                cfg = json.loads(ext)
                if cfg.get("host"):
                    self.host = str(cfg["host"]).rstrip("/")
            except Exception:
                pass
        self.headers = {
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "Cache-Control": "no-cache",
        }
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._cj = http.cookiejar.CookieJar()

    def getName(self):
        return "51短剧"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        return bool(re.search(r"\.(?:m3u8|mp4|flv)(?:$|[?#])", str(url or ""), re.I))

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return

    def destroy(self):
        return

    def homeContent(self, filter):
        html = self._get("/")
        videos = self._merge_list(html)
        return {
            "class": list(self.categories),
            "filters": {},
            "list": videos[:30],
        }

    def homeVideoContent(self):
        html = self._get("/")
        return {"list": self._merge_list(html)[:30]}
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        tid = str(tid or "home")
        if tid == "home":
            if page != 1:
                return {"list": [], "page": page, "pagecount": 0, "limit": 30, "total": 0}
            path = "/"
        elif tid == "rank":
            path = "/rank/" if page == 1 else "/rank/page/%d/" % page
        elif tid == "new":
            path = "/new-theater-category/0-0-0-0-0-1/" if page == 1 else "/new-theater-category/0-0-0-0-0-1/page/%d/" % page
        elif tid == "theater":
            path = "/new-theater-category/" if page == 1 else "/new-theater-category/page/%d/" % page
        else:
            filter_id = urllib.parse.quote(str(tid), safe="")
            path = "/new-theater-category/%s/" % filter_id
            if page > 1:
                path = "/new-theater-category/%s/page/%d/" % (filter_id, page)
        html = self._get(path)
        videos = self._merge_list(html)
        if tid == "home":
            videos = videos[:30]
            return {
                "list": videos,
                "page": 1,
                "pagecount": 1 if videos else 0,
                "limit": 30,
                "total": len(videos),
            }
        meta = self._page_meta(html)
        try:
            total = int(meta.get("total") or 0)
        except Exception:
            total = 0
        try:
            limit = int(meta.get("limit") or len(videos) or 20)
        except Exception:
            limit = len(videos) or 20
        pagecount = (total + limit - 1) // limit if total else (page + 1 if videos else page)
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": limit,
            "total": total or pagecount * limit,
        }


    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        kw = urllib.parse.quote(str(key or "").strip(), safe="")
        path = "/search/%s/" % kw if page == 1 else "/search/%s/page/%d/" % (kw, page)
        html = self._get(path)
        videos = self._merge_list(html)
        meta = self._page_meta(html)
        try:
            total = int(meta.get("total") or len(videos))
        except Exception:
            total = len(videos)
        limit = len(videos) or 30
        pagecount = (total + limit - 1) // limit if total else (1 if videos else 0)
        return {
            "list": videos,
            "page": page,
            "pagecount": max(pagecount, page),
            "limit": limit,
            "total": total,
        }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        raw = str(ids[0]).strip()
        m = re.search(r"(?:/play/)?(\d+)(?:/(\d+))?", raw)
        vid = m.group(1) if m else raw
        html = self._get("/play/%s/1/" % vid)
        if not html:
            return {"list": []}
        nuxt = self._parse_nuxt_detail(html, vid)
        if nuxt:
            meta = self._parse_detail_meta(html, vid)
            meta["vod_name"] = nuxt.get("vod_name") or meta["vod_name"]
            meta["vod_content"] = nuxt.get("vod_content") or meta["vod_content"]
            meta["vod_pic"] = nuxt.get("vod_pic") or meta["vod_pic"]
            episodes = nuxt.get("episodes") or []
        else:
            meta = self._parse_detail_meta(html, vid)
            ep_count = meta["episodes"]
            if ep_count <= 1:
                nums = [int(x) for x in re.findall(r"/play/%s/(\d+)/" % re.escape(vid), html)]
                if nums:
                    ep_count = max(max(nums), ep_count)
            if ep_count < 1:
                ep_count = 1
            episodes = [
                {"id": i, "name": "第%d集" % i}
                for i in range(1, ep_count + 1)
            ]
        play_items = []
        for ep in episodes:
            name = str(ep.get("name") or ep.get("episode_title") or "").strip()
            episode_no = ep.get("index") or ep.get("episode_no")
            if not isinstance(episode_no, (int, str)) or str(episode_no).strip() in ("", "0", "None"):
                episode_no = ep.get("sort")
            if not isinstance(episode_no, (int, str)) or str(episode_no).strip() in ("", "0", "None"):
                episode_no = ep.get("id") or ep.get("episode_id")
            if not episode_no:
                continue
            episode_no = str(episode_no).strip()
            if not name:
                name = "第%s集" % episode_no
            play_items.append("%s$%s/%s" % (name, vid, episode_no))
        if not play_items:
            return {"list": []}
        return {
            "list": [{
                "vod_id": vid,
                "vod_name": meta["vod_name"],
                "vod_pic": meta["vod_pic"],
                "vod_content": meta["vod_content"] or meta["vod_name"],
                "vod_play_from": "51短剧",
                "vod_play_url": "#".join(play_items),
                "vod_remarks": meta.get("remarks") or ("全%d集" % len(play_items)),
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        val = str(id or "").strip()
        if "$" in val:
            val = val.split("$")[-1].strip()
        if self.isVideoFormat(val) and val.startswith("http"):
            if self._probe_media(val):
                return {
                    "parse": 0,
                    "url": val,
                    "header": self._play_headers(),
                }
            return {"parse": 1, "url": val, "header": self._play_headers()}
        vid, ep = "", "1"
        m = re.search(r"(?:/play/)?(\d+)/(\d+)", val)
        if m:
            vid, ep = m.group(1), m.group(2)
        else:
            m2 = re.search(r"(\d+)", val)
            if m2:
                vid = m2.group(1)
        if not vid:
            return {"parse": 0, "url": "", "msg": "invalid id"}
        page = "/play/%s/%s/" % (vid, ep)
        html = self._get(page)
        m3u8 = self._extract_m3u8(html)
        if m3u8 and self._probe_media(m3u8):
            return {
                "parse": 0,
                "url": m3u8,
                "header": self._play_headers(),
            }
        return {
            "parse": 1,
            "url": self._full_url(page),
            "header": self._play_headers(),
        }

    def localProxy(self, param):
        return None

    # -------------------- helpers --------------------
    def _play_headers(self):
        return {
            "User-Agent": self.UA,
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "*/*",
        }

    def _raw_get(self, url, timeout=25):
        try:
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self._cj),
                urllib.request.HTTPSHandler(context=self._ssl_ctx),
            )
            req = urllib.request.Request(url, headers=self.headers)
            with opener.open(req, timeout=timeout) as resp:
                data = resp.read()
                enc = resp.headers.get_content_charset() or "utf-8"
                return data.decode(enc, errors="ignore")
        except Exception:
            return ""

    def _get(self, path_or_url, timeout=25):
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            url = self.host.rstrip("/") + (
                path_or_url if path_or_url.startswith("/") else "/" + path_or_url
            )
        try:
            if hasattr(self, "fetch"):
                rsp = self.fetch(url, headers=self.headers)
                if rsp is not None:
                    if isinstance(rsp, str) and len(rsp) > 100:
                        return rsp
                    if hasattr(rsp, "text") and rsp.text and len(rsp.text) > 100:
                        return rsp.text
                    if hasattr(rsp, "content"):
                        return rsp.content.decode("utf-8", errors="ignore")
        except Exception:
            pass
        return self._raw_get(url, timeout=timeout)

    def _full_url(self, u):
        if not u:
            return ""
        u = u.strip().replace("\\u002F", "/").replace("\\/", "/")
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        return self.host.rstrip("/") + (u if u.startswith("/") else "/" + u)

    def _image_url(self, src):
        if not src:
            return ""
        src = str(src).strip()
        if src.startswith("data:"):
            return ""
        real = self._decode_img_path(src)
        real = self._full_url(real)
        if not real.startswith(("http://", "https://")):
            return ""
        token = base64.b64encode(real.encode("utf-8")).decode("ascii")
        return self.host.rstrip("/") + "/_img/" + token

    def _decode_img_path(self, src):
        if not src:
            return ""
        src = src.strip()
        m = re.search(r"/_img/([A-Za-z0-9_\-+/=]+)", src)
        if m:
            b64 = m.group(1).replace("-", "+").replace("_", "/")
            pad = "=" * (-len(b64) % 4)
            try:
                real = base64.b64decode(b64 + pad).decode("utf-8", "ignore")
                if real.startswith("http"):
                    return real
            except Exception:
                pass
        return src
    def _nuxt_data(self, html):
        if not html:
            return {}
        m = re.search(
            r'<script[^>]+id=["\']__NUXT_DATA__["\'][^>]*>(.*?)</script>',
            html,
            re.I | re.S,
        )
        if not m:
            return {}
        try:
            return self._decode_devalue(json.loads(html_lib.unescape(m.group(1))))
        except Exception:
            return {}

    def _decode_devalue(self, data):
        if not isinstance(data, list):
            return data
        memo = {}
        active = set()
        special = {
            "ShallowReactive", "Reactive", "Ref", "ShallowRef", "ToRaw",
            "Readonly", "ShallowReadonly", "Set", "Map", "Date", "RegExp",
        }
        def resolve(index):
            if isinstance(index, bool) or not isinstance(index, int):
                return index
            if index < 0:
                return index
            if index in memo:
                return memo[index]
            if index >= len(data):
                return index
            if index in active:
                return None
            active.add(index)
            value = data[index]
            if isinstance(value, list):
                if len(value) == 2 and isinstance(value[0], str) and value[0] in special and isinstance(value[1], int):
                    result = resolve(value[1])
                elif len(value) >= 3 and value[0] == "Set":
                    result = [read(v) for v in value[1:]]
                elif len(value) >= 3 and value[0] == "Map":
                    result = {}
                    for i in range(1, len(value) - 1, 2):
                        result[str(read(value[i]))] = read(value[i + 1])
                else:
                    result = [read(v) for v in value]
            elif isinstance(value, dict):
                result = {k: read(v) for k, v in value.items()}
            else:
                result = value
            active.remove(index)
            memo[index] = result
            return result
        def read(value):
            if isinstance(value, list):
                return [read(v) for v in value]
            if isinstance(value, dict):
                return {k: read(v) for k, v in value.items()}
            if isinstance(value, int) and not isinstance(value, bool):
                return resolve(value)
            return value
        return resolve(0)

    def _nuxt_objects(self, root):
        seen = set()
        def walk(value):
            if isinstance(value, (dict, list)):
                marker = id(value)
                if marker in seen:
                    return
                seen.add(marker)
            if isinstance(value, dict):
                yield value
                for child in value.values():
                    for item in walk(child):
                        yield item
            elif isinstance(value, list):
                for child in value:
                    for item in walk(child):
                        yield item
        return walk(root)

    def _is_video_object(self, value):
        if not isinstance(value, dict):
            return False
        title = value.get("title") or value.get("video_title") or value.get("drama_name")
        cover = value.get("cover") or value.get("cover_img")
        vid = value.get("video_id")
        return bool(vid and title and cover)

    def _page_meta(self, html):
        root = self._nuxt_data(html)
        for value in self._nuxt_objects(root):
            if not isinstance(value, dict):
                continue
            items = value.get("list")
            if not isinstance(items, list) or not any(self._is_video_object(x) for x in items):
                continue
            result = {}
            for key in ("total", "page", "limit"):
                try:
                    if value.get(key) is not None:
                        result[key] = int(value.get(key))
                except Exception:
                    pass
            return result
        return {}

    def _parse_nuxt_videos(self, html):
        items = []
        seen = set()
        root = self._nuxt_data(html)
        for value in self._nuxt_objects(root):
            if not self._is_video_object(value):
                continue
            vid = value.get("video_id")
            if vid is None:
                vid = value.get("id")
            vid = str(vid)
            if vid in seen:
                continue
            seen.add(vid)
            title = str(value.get("title") or value.get("video_title") or value.get("drama_name") or "").strip()
            cover = str(value.get("cover") or value.get("cover_img") or "").replace("\\u002F", "/").replace("\\/", "/")
            remark = str(value.get("play_count_text") or value.get("remark") or value.get("remark_text") or "").strip()
            if not remark and value.get("play_count") not in (None, ""):
                try:
                    remark = "%d播放" % int(value.get("play_count"))
                except Exception:
                    pass
            items.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": self._image_url(cover),
                "vod_remarks": remark,
            })
        return items

    def _parse_cards(self, html):
        items = []
        if not html:
            return items
        markers = [m.start() for m in re.finditer(r'data-xpch="(?:drama-card|card)"|class="[^"]*van-swipe-item[^"]*"', html, re.I)]
        seen = set()
        links = list(re.finditer(r'href=["\']/play/(\d+)/(\d+)/["\']', html, re.I))
        for link in links:
            vid = link.group(1)
            if vid in seen:
                continue
            lefts = [p for p in markers if p <= link.start()]
            rights = [p for p in markers if p > link.start()]
            left = lefts[-1] if lefts else max(0, link.start() - 1800)
            right = rights[0] if rights else min(len(html), link.end() + 1800)
            block = html[left:right]
            title_match = re.search(r'<img[^>]+alt=["\']([^"\']*)["\']', block, re.I)
            label_match = re.search(r'<a[^>]+aria-label=["\']([^"\']*)["\']', block, re.I)
            title = html_lib.unescape((title_match or label_match).group(1) if (title_match or label_match) else "").strip()
            if not title or title == "广告":
                continue
            pic_match = re.search(r'(?:data-src|src|poster)=["\']([^"\']+)["\']', block, re.I)
            pic = self._image_url(html_lib.unescape(pic_match.group(1))) if pic_match else ""
            remark_match = re.search(r"(\d+(?:\.\d+)?[Ww万]?播放|全\d+集|共\d+集|\d+集)", block)
            remark = remark_match.group(1) if remark_match else ""
            seen.add(vid)
            items.append({"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_remarks": remark})
        return items

    def _parse_nuxt_detail(self, html, vid):
        root = self._nuxt_data(html)
        for value in self._nuxt_objects(root):
            if not isinstance(value, dict):
                continue
            if str(value.get("playlet_id") or "") != str(vid) or not isinstance(value.get("episodeAll"), list):
                continue
            episodes = []
            for pos, ep in enumerate(value.get("episodeAll") or [], 1):
                if not isinstance(ep, dict):
                    continue
                index = ep.get("index")
                if not isinstance(index, (int, str)) or str(index).strip() in ("", "0", "None"):
                    index = ep.get("sort")
                if not isinstance(index, (int, str)) or str(index).strip() in ("", "0", "None"):
                    index = pos
                title = str(ep.get("episode_title") or ep.get("title") or "").strip()
                episodes.append({
                    "index": str(index),
                    "name": title or ("第%s集" % index),
                    "url": str(ep.get("video_url") or "").replace("\\u002F", "/").replace("\\/", "/"),
                })
            return {
                "vod_name": str(value.get("drama_name") or value.get("video_title") or "").strip(),
                "vod_content": str(value.get("description") or "").strip(),
                "vod_pic": self._image_url(str(value.get("cover_img") or "").replace("\\u002F", "/").replace("\\/", "/")),
                "remarks": str(value.get("update_status") or "").strip(),
                "episodes": episodes,
            }
        return {}


    def _merge_list(self, html):
        a = self._parse_cards(html)
        b = self._parse_nuxt_videos(html)
        if b:
            return b
        return a

    def _parse_detail_meta(self, html, vid):
        info = {
            "vod_name": "",
            "vod_content": "",
            "vod_pic": "",
            "episodes": 1,
        }
        if not html:
            return info
        for m in re.finditer(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>([\s\S]*?)</script>',
            html,
            re.I,
        ):
            try:
                data = json.loads(m.group(1))
            except Exception:
                continue
            if isinstance(data, dict) and data.get("@type") == "VideoObject":
                name = data.get("name") or ""
                name = re.sub(r"第\d+集\s*$", "", name).strip()
                info["vod_name"] = name or info["vod_name"]
                info["vod_content"] = data.get("description") or info["vod_content"]
                thumb = data.get("thumbnailUrl") or ""
                if thumb and "social-default" not in thumb:
                    info["vod_pic"] = self._image_url(thumb)
                try:
                    info["episodes"] = int(data.get("numEpisodes") or 1)
                except Exception:
                    pass
        if not info["vod_name"]:
            tm = re.search(r"<title>([^<]+)</title>", html, re.I)
            if tm:
                t = tm.group(1).split("-")[0].strip()
                t = re.sub(r"第\d+集\s*$", "", t).strip()
                info["vod_name"] = t
        if not info["vod_pic"]:
            pm = re.search(
                r'(https://pic\.[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)',
                html,
                re.I,
            )
            if pm:
                info["vod_pic"] = self._image_url(pm.group(1))
        if not info["vod_name"]:
            info["vod_name"] = "短剧%s" % vid
        if info["episodes"] < 1:
            info["episodes"] = 1
        return info

    def _probe_media(self, url):
        if not url or not str(url).lower().startswith(("http://", "https://")):
            return False
        try:
            req = urllib.request.Request(url, headers=self._play_headers(), method="GET")
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self._cj),
                urllib.request.HTTPSHandler(context=self._ssl_ctx),
            )
            with opener.open(req, timeout=15) as resp:
                data = resp.read(65536)
            body = data.decode("utf-8", errors="ignore").lstrip("\ufeff\r\n\t ")
            return bool(resp.status == 200 and (
                body.startswith("#EXTM3U")
                or (self.isVideoFormat(url) and len(data) > 0)
            ))
        except Exception:
            return False

    def _extract_m3u8(self, html):
        if not html:
            return ""
        ms = re.findall(r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)', html)
        for u in ms:
            if "auth_key=" in u or "hls." in u:
                return html_lib.unescape(u).replace("\\u002F", "/").replace("\\/", "/")
        if ms:
            return html_lib.unescape(ms[0]).replace("\\u002F", "/").replace("\\/", "/")
        return ""