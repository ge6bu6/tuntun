# coding=utf-8
# TVBox / FongMi T3 (type=3) Spider —— bestjavporn.com (JAV / 成人)
# 逆向要點：
#   1) 列表卡片 <article id="post-NNNNNN" ...>，內 <a href=".../video/{slug}/">，縮圖 img.video-img@data-lazy-src
#   2) 詳情頁 /video/{slug}/ 內 data-mpu 密文 → RC4 double-atob 解出 token
#      RC4 動態金鑰 = reverse(base64(f"{postid}_0x58fe15"))，postid 從詳情頁 postid-\d+ 取得
#   3) POST /api/play/ (sources=token&ver=2) → dec(data)=主播放頁；dec(reserve)=備援線路 JSON 陣列
#   4) 播放頁 (video1.bestjavporn.com) 內 JWPlayer 動態產出 streamhls.click m3u8，僅瀏覽器可取
#      → 採方案B parse:1，交 TVBox 內建嗅探器解析（法則27：帶完整 header）
import sys, re, base64, json
sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):  # 本地冒煙測試兜底（正式環境由 T3 提供）
        def init(self, extend=""): pass


class Spider(Spider):

    # ---------------- 站點常量（換站只改這裡） ----------------
    siteName = "JAV"
    HOST = "https://www.bestjavporn.com"
    UA = "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    RC4_KEY = b"1ETZmhTN4BzX5czN1gjN"  # 固定金鑰：僅特定 postid 有效，作 _derive_key 失敗時的兜底

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self.headers = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        return

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return (".m3u8" in u) or (".mp4" in u) or ("master.m3u8" in u)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ================= RC4 double-atob 解密（已實測驗證） =================
    def _rc4(self, key, data):
        S = list(range(256)); j = 0
        for i in range(256):
            j = (j + S[i] + key[i % len(key)]) & 255
            S[i], S[j] = S[j], S[i]
        i = j = 0; out = bytearray()
        for ch in data:
            i = (i + 1) & 255; j = (j + S[i]) & 255
            S[i], S[j] = S[j], S[i]
            out.append(ch ^ S[(S[i] + S[j]) & 255])
        return bytes(out)

    def _b64d(self, s):
        if isinstance(s, str):
            s = s.encode("utf-8")
        s = s.strip()
        pad = (-len(s)) % 4
        return base64.b64decode(s + (b"=" * pad))

    def dec(self, b, key=None):
        # base64decode -> RC4(key) -> base64decode -> utf-8
        # key 為 bytes；未給則用 RC4_KEY（固定金鑰，僅特定 postid 有效，作最後兜底）
        try:
            k = key if key is not None else self.RC4_KEY
            step1 = self._rc4(k, self._b64d(b))
            return self._b64d(step1).decode("utf-8", "replace")
        except Exception:
            return ""

    def _derive_key(self, postid):
        # 動態金鑰 = reverse(base64(f"{postid}_0x58fe15"))，實測隨 postid 變動
        try:
            raw = ("%s_0x58fe15" % postid).encode("utf-8")
            return base64.b64encode(raw).decode("ascii")[::-1].encode("ascii")
        except Exception:
            return None

    def _postid(self, html):
        if not html:
            return None
        m = re.search(r'postid-(\d+)', html)
        if m:
            return m.group(1)
        m = re.search(r'<article[^>]*id="post-(\d+)"', html)
        if m:
            return m.group(1)
        m = re.search(r'<body[^>]*\bid="post-(\d+)"', html)
        if m:
            return m.group(1)
        return None

    # ================= 網路封裝（法則4：失敗回 None 須判空） =================
    def _get(self, url, headers=None):
        h = dict(self.headers)
        if headers:
            h.update(headers)
        try:
            rsp = self.fetch(url, headers=h)
            if rsp is None:
                return None
            code = getattr(rsp, "status_code", getattr(rsp, "code", 200))
            if code and int(code) >= 400:
                return None
            return rsp.text
        except Exception:
            return self._local_get(url, h)

    def _post(self, url, data, headers=None):
        h = {
            "User-Agent": self.UA,
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Referer": self.HOST + "/",
            "Origin": self.HOST,
        }
        if headers:
            h.update(headers)
        try:
            rsp = self.post(url, data=data, headers=h)
            if rsp is None:
                return None
            code = getattr(rsp, "status_code", getattr(rsp, "code", 200))
            if code and int(code) >= 400:
                return None
            return rsp.text
        except Exception:
            return self._local_post(url, data, h)

    # 本地冒煙測試兜底（正式 T3 環境不會走到）
    def _local_get(self, url, h):
        try:
            import urllib.request
            req = urllib.request.Request(url, headers=h)
            return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception:
            return None

    def _local_post(self, url, data, h):
        try:
            import urllib.request, urllib.parse
            body = urllib.parse.urlencode(data).encode()
            req = urllib.request.Request(url, data=body, headers=h)
            return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")
        except Exception:
            return None

    # ================= 列表卡片解析 =================
    def _parse_cards(self, html):
        vods = []
        if not html:
            return vods
        blocks = re.findall(r'<article[^>]*id="post-\d+"[^>]*>(.*?)</article>', html, re.S)
        seen = set()
        for b in blocks:
            m = re.search(r'href="https?://[^"]*/video/([^"/]+)/?"\s+title="([^"]*)"', b)
            if not m:
                continue
            slug, title = m.group(1), m.group(2)
            if not slug or slug in seen:
                continue
            seen.add(slug)
            # 縮圖：img.video-img@data-lazy-src，過濾 qtranslate 國旗 / 廣告 / 404 圖
            pic = ""
            for pm in re.finditer(r'data-lazy-src="([^"]+)"', b):
                cand = pm.group(1)
                if ("flags/" in cand or "githubusercontent" in cand
                        or "native-ad" in cand or "data-notsrc" in cand):
                    continue
                pic = cand
                break
            if not pic:
                pm = re.search(r'class="[^"]*video-img[^"]*"[^>]*\ssrc="(https?://[^"]+)"', b)
                pic = pm.group(1) if pm else ""
            dm = re.search(r'class="duration"[^>]*>([^<]+)<', b)
            remark = dm.group(1).strip() if dm else ""
            vods.append({
                "vod_id": slug,
                "vod_name": self._clean(title),
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return vods

    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r"<[^>]+>", "", s)
        try:
            import html as _h
            s = _h.unescape(s)
        except Exception:
            s = s.replace("&amp;", "&").replace("&#039;", "'").replace("&quot;", '"')
        return s.strip()

    def _pagecount(self, html, pg):
        try:
            nums = [int(x) for x in re.findall(r'/page/(\d+)/', html or "")]
            if nums:
                return max(max(nums), int(pg))
        except Exception:
            pass
        return 9999  # 未知總頁：保持可翻頁

    # ================= homeContent：靜態分類，零網路（法則16/17） =================
    def homeContent(self, filter):
        classes = [
            {"type_id": "latest", "type_name": "最新"},
            {"type_id": "censored", "type_name": "有碼"},
            {"type_id": "uncensored", "type_name": "無碼"},
            {"type_id": "amateur", "type_name": "素人"},
        ]
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        html = self._get(self.HOST + "/")
        return {"list": self._parse_cards(html)}

    # ================= categoryContent =================
    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        if tid in ("censored", "uncensored", "amateur"):
            base = "%s/category/%s/" % (self.HOST, tid)
            url = base if pg == 1 else "%spage/%d/" % (base, pg)
        else:  # latest / 首頁流
            url = self.HOST + "/" if pg == 1 else "%s/page/%d/" % (self.HOST, pg)
        html = self._get(url)
        vods = self._parse_cards(html)
        return {
            "list": vods,
            "page": pg,
            "pagecount": self._pagecount(html, pg) if vods else max(pg, 1),
            "limit": len(vods) if vods else 24,
            "total": 999999,
        }

    # ================= searchContent =================
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        if pg < 1:
            pg = 1
        import urllib.parse as up
        q = up.quote(key)
        if pg == 1:
            url = "%s/?s=%s" % (self.HOST, q)
        else:
            url = "%s/page/%d/?s=%s" % (self.HOST, pg, q)
        html = self._get(url)
        vods = self._parse_cards(html)
        return {"list": vods, "page": pg, "pagecount": (pg + 1) if vods else pg,
                "limit": len(vods), "total": 999999}

    # ================= detailContent（法則35） =================
    def detailContent(self, ids):
        ids = self._norm_ids(ids)
        if not ids:
            return {"list": []}
        slug = ids[0]
        url = "%s/video/%s/" % (self.HOST, slug)
        html = self._get(url)
        if not html:
            return self._skeleton(slug)

        title = self._first(html, [
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            r'<h1[^>]*>([^<]+)</h1>',
            r'<title>([^<]+)</title>',
        ]) or slug
        pic = self._first(html, [
            r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"',
        ]) or ""
        desc = self._first(html, [
            r'<meta[^>]+name="description"[^>]+content="([^"]+)"',
            r'<meta[^>]+property="og:description"[^>]+content="([^"]+)"',
        ]) or ""

        # 嘗試枚舉多線路（主線路 + 備援），失敗則單線路
        froms, urls = self._build_play_lines(html, slug)

        vod = {
            "vod_id": slug,
            "vod_name": self._clean(title),
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": self._clean(desc),
            "vod_play_from": froms,
            "vod_play_url": urls,
        }
        return {"list": [vod]}

    def _line_label(self, lo):
        m = {"mp": "MP", "us": "US", "fr": "FR", "my": "MY",
             "nl3": "NL", "de3": "DE", "de": "DE", "nl": "NL"}
        return "線路" + m.get(lo, str(lo).upper())

    def _build_play_lines(self, html, slug):
        """回傳 (vod_play_from, vod_play_url)。play id 格式 slug@@linekey（法則21：無裸 $）。"""
        default_from = self.siteName
        default_url = "正片$" + slug + "@@main"
        m = re.search(r'data-mpu="([^"]+)"', html or "")
        if not m:
            return default_from, default_url
        key = self._derive_key(self._postid(html))  # 動態金鑰（隨 postid 變）
        token = self.dec(m.group(1), key)
        if not token:
            return default_from, default_url
        resp = self._post(self.HOST + "/api/play/",
                          {"sources": token, "ver": "2"},
                          {"Referer": "%s/video/%s/" % (self.HOST, slug)})
        if not resp:
            return default_from, default_url
        try:
            j = json.loads(resp)
        except Exception:
            return default_from, default_url
        if not j.get("status"):
            return default_from, default_url

        froms = ["主線路"]
        urls = ["正片$" + slug + "@@main"]
        try:
            arr = json.loads(self.dec(j.get("reserve", ""), key) or "[]")
            for e in arr:
                lo = e.get("lo")
                if not lo:
                    continue
                froms.append(self._line_label(lo))
                urls.append("正片$" + slug + "@@" + str(lo))
        except Exception:
            pass
        return "$$$".join(froms), "$$$".join(urls)

    # ================= playerContent（方案B parse:1，法則27） =================
    def playerContent(self, flag, id, vipFlags):
        header = {"User-Agent": self.UA, "Referer": self.HOST + "/"}
        slug, linekey = self._split_playid(id)
        play_page = self._resolve_play_page(slug, linekey)
        if not play_page:
            # 兜底：回詳情頁，交嗅探器嘗試
            play_page = "%s/video/%s/" % (self.HOST, slug)
        return {"parse": 1, "playUrl": "", "url": play_page, "header": header}

    def _split_playid(self, pid):
        s = str(pid or "").strip()
        if s.startswith("http"):
            s = s.rstrip("/").split("/")[-1]
        if "@@" in s:
            slug, key = s.split("@@", 1)
            return slug, (key or "main")
        return s, "main"

    def _resolve_play_page(self, slug, linekey):
        """即時解析播放頁 URL（t/s 為時效 token，須每次重取）。"""
        html = self._get("%s/video/%s/" % (self.HOST, slug))
        if not html:
            return None
        m = re.search(r'data-mpu="([^"]+)"', html)
        if not m:
            return None
        key = self._derive_key(self._postid(html))  # 動態金鑰
        token = self.dec(m.group(1), key)
        if not token:
            return None
        resp = self._post(self.HOST + "/api/play/",
                          {"sources": token, "ver": "2"},
                          {"Referer": "%s/video/%s/" % (self.HOST, slug)})
        if not resp:
            return None
        try:
            j = json.loads(resp)
        except Exception:
            return None
        if not j.get("status"):
            return None
        page = ""
        if linekey == "main":
            page = self.dec(j.get("data", ""), key)
        else:
            try:
                arr = json.loads(self.dec(j.get("reserve", ""), key) or "[]")
                for e in arr:
                    if str(e.get("lo")) == linekey:
                        page = self.dec(e.get("data", ""), key)
                        break
            except Exception:
                page = ""
            if not page:  # 找不到對應線路則退回主線路
                page = self.dec(j.get("data", ""), key)
        return self._abs(page)

    def _abs(self, u):
        if not u:
            return None
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("http"):
            return u
        return None

    # ================= localProxy（方案B 一般不觸發，保留 m3u8 絕對化兜底） =================
    def localProxy(self, param):
        try:
            import urllib.parse as up
            url = param.get("url") if isinstance(param, dict) else None
            if not url:
                return [404, "text/plain", b""]
            url = up.unquote(url)
            text = self._get(url, {"Referer": "https://video1.bestjavporn.com/"})
            if text is None:
                return [404, "text/plain", b""]
            base = url.rsplit("/", 1)[0] + "/"
            out = []
            for ln in text.splitlines():
                s = ln.strip()
                if s and not s.startswith("#") and not s.startswith("http"):
                    s = up.urljoin(base, s)
                out.append(s)
            body = ("\n".join(out)).encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", body]
        except Exception:
            return [404, "text/plain", b""]

    # ================= 通用工具 =================
    def _first(self, html, patterns):
        for p in patterns:
            m = re.search(p, html, re.S)
            if m:
                return m.group(1).strip()
        return None

    def _norm_ids(self, ids):
        if ids is None:
            return []
        if isinstance(ids, str):
            ids = [ids]
        out = []
        for x in ids:
            if x is None:
                continue
            s = str(x).strip()
            if not s:
                continue
            if s.startswith("http"):
                s = s.rstrip("/").split("/")[-1]
            if "@@" in s:
                s = s.split("@@", 1)[0]
            out.append(s)
        return out

    def _skeleton(self, slug):
        vod = {
            "vod_id": slug,
            "vod_name": slug,
            "vod_pic": "",
            "vod_remarks": "",
            "vod_content": "詳情載入失敗，可直接嘗試播放",
            "vod_play_from": self.siteName,
            "vod_play_url": "正片$" + slug + "@@main",
        }
        return {"list": [vod]}

    # T3 其它可選接口
    def liveContent(self, url):
        return {}

    def action(self, action):
        return ""
