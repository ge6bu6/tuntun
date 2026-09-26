# -*- coding: utf-8 -*-
import re
import sys
import json
import time
from base64 import b64encode, b64decode
from urllib.parse import quote, unquote

try:
    import requests
except Exception:
    requests = None
import urllib.request

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass
try:
    from Crypto.Cipher import AES as _AES
except Exception:
    try:
        from Cryptodome.Cipher import AES as _AES
    except Exception:
        _AES = None
try:
    from lxml import etree
except Exception:
    etree = None


class Spider:
    """黄果短剧五壳通用独立 Spider"""

    _IMG_KEY = bytes([102, 53, 100, 57, 54, 53, 100, 102, 55, 53, 51, 51, 54, 50, 55, 48])
    _IMG_IV = bytes([57, 55, 98, 54, 48, 51, 57, 52, 97, 98, 99, 50, 102, 98, 101, 49])
    _TIMEOUT = 20

    def __init__(self):
        self.host = "https://huangguoai.com"
        self.ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/120.0.0.0 Safari/537.36")
        self.pics_direct = False
        self._proxy_url = ""
        self._session = None
        self.img_key = b'f5d965df75336270'
        self.img_iv = b'97b60394abc2fbe1'
        self.img_hosts = {'pic.eanfog.cn', 'pic.zdmhyg.cn', 'pic.tuafjz.cn'}
        self.base_cates = [
            {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
            {"type_id": "ai-huanlian", "type_name": "AI换脸"},
            {"type_id": "ai-mogai", "type_name": "AI魔改"},
        ]
        self._recommend_cache = None

    def getName(self):
        return "黄果短剧"

    def getDependence(self):
        return []

    def init(self, extend=""):
        if isinstance(extend, str) and extend.strip()[:1] == "{":
            try:
                extend = json.loads(extend)
            except Exception:
                extend = dict()
        if not isinstance(extend, dict):
            extend = dict()
        if extend.get("host"):
            self.host = str(extend["host"]).rstrip("/")
        ext = json.dumps(extend, ensure_ascii=False) if extend else str(extend)
        self.pics_direct = "direct=1" in ext
        self.categories = [
            {"type_id": "recommend", "type_name": "精选推荐"},
            {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
            {"type_id": "ai-huanlian", "type_name": "AI换脸"},
            {"type_id": "ai-mogai", "type_name": "AI魔改"},
            {"type_id": "ranks", "type_name": "排行榜"},
            {"type_id": "chigua", "type_name": "黄果吃瓜"},
            {"type_id": "topics", "type_name": "话题精选"},
        ]
        self.filters = {
            "ai-duanju": [{"key": "sort", "name": "排序", "value": [
                {"n": "最新更新", "v": "latest"}, {"n": "当前热播", "v": "hot"},
                {"n": "独家原创", "v": "original"}, {"n": "随机推荐", "v": "random"}]}],
            "ai-manju": [{"key": "sort", "name": "排序", "value": [
                {"n": "最新更新", "v": "latest"}, {"n": "当前热播", "v": "hot"},
                {"n": "独家原创", "v": "original"}, {"n": "随机推荐", "v": "random"}]}],
            "ai-huanlian": [{"key": "sort", "name": "排序", "value": [
                {"n": "最新更新", "v": "latest"}, {"n": "当前热播", "v": "hot"},
                {"n": "独家原创", "v": "original"}, {"n": "随机推荐", "v": "random"}]}],
            "ai-mogai": [{"key": "sort", "name": "排序", "value": [
                {"n": "最新更新", "v": "latest"}, {"n": "当前热播", "v": "hot"},
                {"n": "独家原创", "v": "original"}, {"n": "随机推荐", "v": "random"}]}],
            "ranks": [{"key": "rank_type", "name": "榜单", "value": [
                {"n": "热播榜", "v": "hot"}, {"n": "推荐榜", "v": "recommend"},
                {"n": "潜力榜", "v": "potential"}]}],
            "chigua": [{"key": "cate", "name": "分类", "value": [
                {"n": "全部", "v": "all"}, {"n": "热门吃瓜", "v": "remen"},
                {"n": "AI原创", "v": "yuanchuang"}]}],
            "topics": [{"key": "tid", "name": "话题", "value": [
                {"n": "热门AI短剧", "v": "hot-aiduanju"}, {"n": "欧美短剧", "v": "oumei-duanju"},
                {"n": "天才男友", "v": "tiancai-nantong"}, {"n": "明星换脸", "v": "mingxing-huanlian"}]}],
        }

    def _headers(self, referer=None):
        return {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": (referer or self.host) + "/",
        }

    def _session_obj(self):
        """复用 Session，行为接近真实浏览器持续访问"""
        if self._session is not None:
            return self._session
        if requests is None:
            return None
        try:
            s = requests.Session()
            s.verify = False
            s.headers.update(self._headers())
            self._session = s
            return s
        except Exception:
            return None

    def _ensure_str(self, data, asjson=False):
        """把响应统一为干净字符串；处理 gzip 与宽字符编码，避免 lxml 编码探测报错"""
        if isinstance(data, str):
            return data
        if data is None:
            return ""
        if isinstance(data, bytes):
            if len(data) >= 2 and data[:2] == b"\x1f\x8b":
                import gzip
                try:
                    data = gzip.decompress(data)
                except Exception:
                    pass
            # 去掉 UTF-32/UTF-16 BOM，避免 lxml "encoding not supported" 报错
            for bom, enc in ((b"\xff\xfe\x00\x00", "utf-32"), (b"\x00\x00\xfe\xff", "utf-32"),
                             (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")):
                if data[:len(bom)] == bom:
                    try:
                        return data.decode(enc)
                    except Exception:
                        break
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return data.decode("gbk", errors="ignore")
        return str(data)

    def _get(self, url, referer=None, asjson=False, raw=False):
        fail = dict() if asjson else (b"" if raw else "")
        if not url:
            return fail
        headers = self._headers(referer)
        sess = self._session_obj()
        if sess is not None:
            for _ in range(3):
                try:
                    r = sess.get(url, headers=headers, timeout=self._TIMEOUT)
                    if asjson:
                        try:
                            return r.json()
                        except Exception:
                            return dict()
                    if raw:
                        return r.content
                    return self._ensure_str(r.content)
                except Exception:
                    time.sleep(1)
            return fail
        if requests is not None:
            for _ in range(3):
                try:
                    r = requests.get(url, headers=headers, timeout=self._TIMEOUT, verify=False)
                    if asjson:
                        try:
                            return r.json()
                        except Exception:
                            return dict()
                    if raw:
                        return r.content
                    return self._ensure_str(r.content)
                except Exception:
                    time.sleep(1)
            return fail
        import gzip
        for _ in range(3):
            try:
                req = urllib.request.Request(url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=self._TIMEOUT)
                data = resp.read()
                if asjson:
                    try:
                        return json.loads(self._ensure_str(data))
                    except Exception:
                        return dict()
                if raw:
                    return data
                return self._ensure_str(data)
            except Exception:
                time.sleep(1)
        return fail

    def _get_bin(self, url):
        return self._get(url, raw=True)

    def _fix(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _img_src(self, u):
        """剔除 CDN 防盗链的 auth_key 等查询参数，得到不过期的稳定直链"""
        u = self._fix(u or "")
        if u.startswith("http") and "?" in u:
            u = re.sub(r"\?.*", "", u)
        return u

    def getProxyUrl(self, local=True):
        if self._proxy_url:
            return self._proxy_url
        try:
            from com.github.catvod import Proxy as _CatProxy
            return str(_CatProxy.getUrl(local)) + "?do=py"
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def _proxy_pic(self, u):
        """图片走壳本地代理，由 localProxy 解密后返回真实图片"""
        u = self._img_src(u)
        if not u:
            return ""
        if self.pics_direct:
            return u
        enc = quote(b64encode(u.encode("utf-8")).decode("utf-8"), safe="")
        return self.getProxyUrl() + "&url=" + enc + "&type=img"

    def _decrypt_img(self, raw):
        """AES-128-CBC 解密站点封面字节；无加密或解密失败时原样返回"""
        if not raw or len(raw) % 16 != 0 or _AES is None:
            return raw
        try:
            pt = _AES.new(self._IMG_KEY, _AES.MODE_CBC, self._IMG_IV).decrypt(raw)
        except Exception:
            return raw
        if not (pt[:2] == b"\xff\xd8" or pt[:8] == b"\x89PNG\r\n\x1a\n"
                or pt[:4] == b"RIFF" or pt[:6] in (b"GIF87a", b"GIF89a")):
            return raw
        pad = pt[-1]
        if 0 < pad <= 16 and pt[-pad:] == bytes([pad]) * pad:
            pt = pt[:-pad]
        if pt[:2] == b"\xff\xd8":
            i = pt.rfind(b"\xff\xd9")
            if i >= 0:
                pt = pt[:i + 2]
        elif pt[:8] == b"\x89PNG\r\n\x1a\n":
            i = pt.rfind(b"IEND")
            if i >= 0:
                pt = pt[:i + 8]
        return pt

    def _img_ct(self, data):
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        return "image/jpeg"

    def _card(self, card):
        a = card.xpath('.//a[contains(@href,"/detail/")]')
        if not a:
            return None
        a = a[0]
        m = re.search(r"/detail/(\d+)/", a.get("href", ""))
        if not m:
            return None
        img = (card.xpath('.//img/@data-src') or card.xpath('.//img/@src') or ["", ""])[0]
        title = "".join(card.xpath('.//*[contains(@class,"hg-drama-card__title")]//text()')).strip()
        if not title:
            title = a.get("title", "").strip()
        if not title:
            return None
        rem = "".join(card.xpath('.//*[contains(@class,"hg-drama-card__episode")]//text()')).strip()
        score = "".join(card.xpath('.//*[contains(@class,"hg-drama-card__score")]//text()')).strip()
        if rem and score:
            rem = rem + " · " + score
        elif not rem:
            rem = score
        return {
            "vod_id": m.group(1),
            "vod_name": title,
            "vod_pic": self._proxy_pic(img),
            "vod_remarks": rem,
        }

    def _cards(self, html, all_grids=False):
        if not html or etree is None:
            return []
        if not isinstance(html, str):
            html = self._ensure_str(html)
        try:
            tree = etree.HTML(html)
        except Exception:
            return []
        if all_grids:
            nodes = []
            for g in tree.xpath('//*[contains(@class,"hg-card-grid")]'):
                nodes.extend(g.xpath('.//*[contains(@class,"hg-drama-card")]'))
        else:
            grids = tree.xpath('//*[contains(@class,"hg-card-grid")]')
            nodes = grids[0].xpath('.//*[contains(@class,"hg-drama-card")]') if grids else []
        out, seen = [], set()
        for card in nodes:
            try:
                item = self._card(card)
                if not item or item["vod_id"] in seen:
                    continue
                seen.add(item["vod_id"])
                out.append(item)
            except Exception:
                continue
        return out

    def _rank_items(self, html):
        if not html or etree is None:
            return []
        if not isinstance(html, str):
            html = self._ensure_str(html)
        try:
            tree = etree.HTML(html)
        except Exception:
            return []
        lists = tree.xpath('//*[contains(@class,"hg-rank-list")]')
        nodes = lists[0].xpath('.//*[contains(@class,"hg-rank-item")]') if lists else tree.xpath('//*[contains(@class,"hg-rank-item")]')
        out, seen = [], set()
        for item in nodes:
            try:
                a = item.xpath('.//a[contains(@href,"/detail/")]')
                if not a:
                    continue
                m = re.search(r"/detail/(\d+)/", a[0].get("href", ""))
                if not m or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                img = (item.xpath('.//img/@data-src') or item.xpath('.//img/@src') or ["", ""])[0]
                title = "".join(item.xpath('.//*[contains(@class,"hg-rank-item__title")]//text()')).strip()
                if not title:
                    title = a[0].get("title", "").strip()
                if not title:
                    continue
                out.append({
                    "vod_id": m.group(1),
                    "vod_name": title,
                    "vod_pic": self._proxy_pic(img),
                    "vod_remarks": "".join(item.xpath('.//*[contains(@class,"hg-rank-item__tags")]//text()')).strip(),
                })
            except Exception:
                continue
        return out

    def _panel_total(self, html):
        m = re.search(r'data-panel-total="(\d+)"', html or "")
        return int(m.group(1)) if m else 0

    def _api_items(self, path, params=None):
        """站点 JSON 接口优先，行为接近真实浏览器持续访问"""
        try:
            data = self._get(self.host + path, asjson=True)
        except Exception:
            return None, None
        if not isinstance(data, dict):
            return None, None
        body = data.get("data")
        if not isinstance(body, dict):
            return None, None
        items = body.get("items")
        if not isinstance(items, list):
            return None, None
        return items, body.get("pagination") if isinstance(body.get("pagination"), dict) else None

    @staticmethod
    def _api_remarks(item):
        if not isinstance(item, dict):
            return ""
        if item.get("is_finished"):
            try:
                total = int(item.get("episode_count") or item.get("total_episodes") or 0)
            except Exception:
                total = 0
            return ("全%d集" % total) if total else "已完结"
        try:
            ep = int(item.get("episode_count") or 0)
        except Exception:
            ep = 0
        if ep:
            return "更新至%d集" % ep
        score = item.get("score")
        try:
            if score not in (None, ""):
                return str(score) + "分"
        except Exception:
            pass
        return ""

    def _api_video_item(self, item):
        vid = str(item.get("id") or item.get("video_id") or "")
        if not vid:
            return None
        tags = item.get("tags")
        remarks = self._api_remarks(item)
        if isinstance(tags, list) and tags:
            tag_str = "·".join([str(t) for t in tags[:3] if t])
            if tag_str:
                remarks = (remarks + " " + tag_str).strip() if remarks else tag_str
        return {
            "vod_id": vid,
            "vod_name": item.get("title") or "",
            "vod_pic": self._proxy_pic(item.get("cover") or ""),
            "vod_remarks": remarks,
        }

    def _api_rank_item(self, item):
        vid = str(item.get("video_id") or item.get("id") or "")
        if not vid:
            return None
        try:
            rank = item.get("rank")
            label = item.get("metric_label") or ""
            value = item.get("metric_value")
            remarks = ("#%s %s%s" % (rank, label, value)).strip() if rank else ""
        except Exception:
            remarks = ""
        tags = item.get("tags")
        if isinstance(tags, list) and tags:
            tag_str = "·".join([str(t) for t in tags[:3] if t])
            if tag_str:
                remarks = (remarks + " " + tag_str).strip() if remarks else tag_str
        if not remarks:
            remarks = self._api_remarks(item)
        return {
            "vod_id": vid,
            "vod_name": item.get("title") or "",
            "vod_pic": self._proxy_pic(item.get("cover") or ""),
            "vod_remarks": remarks,
        }

    def _api_category(self, tid, sort, pg, per=24):
        items, pagination = self._api_items(
            "/api/videos/category/" + tid,
            params={"page": pg, "size": per, "sort": sort} if False else None,
        )
        return items, pagination

    def _ensure_cates(self):
        if getattr(self, "categories", None):
            if not getattr(self, "filters", None):
                self.filters = dict()
            return
        self.categories = [
            {"type_id": "recommend", "type_name": "精选推荐"},
            {"type_id": "ai-duanju", "type_name": "AI成人短剧"},
            {"type_id": "ai-manju", "type_name": "AI成人漫剧"},
            {"type_id": "ai-huanlian", "type_name": "AI换脸"},
            {"type_id": "ai-mogai", "type_name": "AI魔改"},
            {"type_id": "ranks", "type_name": "排行榜"},
            {"type_id": "chigua", "type_name": "黄果吃瓜"},
            {"type_id": "topics", "type_name": "话题精选"},
        ]
        self.filters = dict()

    def _is_encrypted(self, url):
        if not url:
            return False
        try:
            from urllib.parse import urlparse as _up
            return _up(url).hostname in self.img_hosts
        except Exception:
            return False

    def _wrap_pic(self, pic):
        return self._proxy_pic(pic)

    @staticmethod
    def _remarks(item):
        if not isinstance(item, dict):
            return ""
        if item.get("is_finished"):
            try:
                total = int(item.get("episode_count") or item.get("total_episodes") or 0)
            except Exception:
                total = 0
            return ("全%d集" % total) if total else "已完结"
        try:
            ep = int(item.get("episode_count") or 0)
        except Exception:
            ep = 0
        return ("更新至%d集" % ep) if ep else ""

    def _category_api(self, base_id, sort, page, per=20):
        result = {"list": [], "page": page, "pagecount": 1, "limit": per, "total": 0}
        items, _ = self._api_items("/api/videos/category/%s?page=%d&size=%d&sort=%s" % (base_id, page, per, sort))
        if not items:
            return result
        for it in items:
            v = self._api_video_item(it)
            if v:
                result["list"].append(v)
        result["pagecount"] = page + 1
        result["total"] = len(result["list"]) * page
        return result

    def _category_ranks(self, rank_type, page, per=20):
        result = {"list": [], "page": page, "pagecount": 1, "limit": per, "total": 0}
        items, _ = self._api_items("/api/ranks/%s?page=%d&size=%d" % (rank_type or "hot", page, per))
        if not items:
            return result
        for it in items:
            v = self._api_rank_item(it)
            if v:
                result["list"].append(v)
        result["pagecount"] = page + 1
        result["total"] = len(result["list"]) * page
        return result

    def _category_random(self, base_id):
        return self._category_api(base_id, "random", 1)

    def _category_chigua(self, cate, page):
        per = 12
        result = {"list": [], "page": page, "pagecount": 1, "limit": per, "total": 0}
        try:
            if cate == "remen":
                path = "/chigua/remen/page/%d/" % page if page > 1 else "/chigua/remen/"
            elif cate == "yuanchuang":
                path = "/chigua/yuanchuang/page/%d/" % page if page > 1 else "/chigua/yuanchuang/"
            else:
                path = "/chigua/page/%d/" % page if page > 1 else "/chigua/"
            html = self._get(self.host + path)
            if not html:
                return result
            posts = re.findall(r'<a[^>]*class="hg-post-card"[^>]*href="(/archives/(\d+)/)"[^>]*>.*?<h3>(.*?)</h3>', html, re.DOTALL)
            for href, pid, title in posts:
                pos = html.find('href="%s"' % href)
                chunk = html[pos:pos + 600] if pos >= 0 else ""
                pm = re.search(r'data-src="(https?://[^"]+)"', chunk) or re.search(r'src="(https?://[^"]+)"', chunk)
                result["list"].append({"vod_id": "archives_%s" % pid, "vod_name": title.strip(), "vod_pic": self._proxy_pic(pm.group(1)) if pm else "", "vod_remarks": "吃瓜"})
            pm2 = re.search(r'data-pages="(\d+)"', html)
            result["pagecount"] = int(pm2.group(1)) if pm2 else (page if len(result["list"]) < per else page + 1)
            result["total"] = len(result["list"])
        except Exception:
            pass
        return result

    def _category_topics(self, topic, page):
        per = 20
        result = {"list": [], "page": page, "pagecount": 1, "limit": per, "total": 0}
        try:
            path = "/topics/%s/?page=%d" % (topic, page) if topic and page > 1 else ("/topics/%s/" % topic if topic else "/topics/")
            html = self._get(self.host + path)
            if not html:
                return result
            cards = re.findall(r'<div[^>]*class="hg-drama-card"[^>]*>.*?</div>\s*</div>\s*</div>', html, re.DOTALL)
            for c in cards:
                lm = re.search(r'href="(/detail/(\d+)/)"', c)
                if not lm:
                    continue
                tm = re.search(r'hg-drama-card__title[^>]*><a[^>]*>([^<]+)</a>', c)
                pm = re.search(r'data-src="(https?://[^"]+)"', c) or re.search(r'src="(https?://[^"]+)"', c)
                em = re.search(r'hg-drama-card__episode[^>]*>([^<]+)', c)
                result["list"].append({"vod_id": lm.group(2), "vod_name": tm.group(1).strip() if tm else ("视频%s" % lm.group(2)), "vod_pic": self._proxy_pic(pm.group(1)) if pm else "", "vod_remarks": em.group(1).strip() if em else ""})
            pm2 = re.search(r'data-pages="(\d+)"', html)
            result["pagecount"] = int(pm2.group(1)) if pm2 else (page if len(result["list"]) < per else page + 1)
            result["total"] = len(result["list"])
        except Exception:
            pass
        return result

    def homeContent(self, filter=None):
        self._ensure_cates()
        result = {"class": self.categories, "filters": getattr(self, "filters", dict())}
        return result

    def homeVideoContent(self):
        if self._recommend_cache:
            return {"list": self._recommend_cache}
        try:
            items, _ = self._api_items("/api/videos/category/ai-duanju?page=1&size=20&sort=latest")
            vids, seen = [], set()
            for it in items or []:
                v = self._api_video_item(it)
                if not v or v["vod_id"] in seen:
                    continue
                seen.add(v["vod_id"])
                vids.append(v)
            if vids:
                self._recommend_cache = vids
                return {"list": vids}
        except Exception:
            pass
        return {"list": self._cards(self._get(self.host), all_grids=True)}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = max(int(pg or 1), 1)
        tid = str(tid or "").strip("/")
        ext = extend if isinstance(extend, dict) else dict()
        if tid == "recommend":
            return self.homeVideoContent()
        if tid in ("ranks", "ranks/hot", "rank"):
            return self._category_ranks(ext.get("rank_type", "hot"), pg)
        if tid == "chigua":
            return self._category_chigua(ext.get("cate", "all"), pg)
        if tid == "topics":
            return self._category_topics(ext.get("tid", ""), pg)
        sort = ext.get("sort", "latest")
        if sort == "original":
            sort = "hot"
        if sort == "random":
            return self._category_random(tid)
        ret = self._category_api(tid, sort, pg)
        if ret.get("list"):
            return ret
        html = self._get(self.host + "/" + tid + ("/" if pg == 1 else "/%d/" % pg))
        cards = self._cards(html) or self._cards(html, all_grids=True) or self._rank_items(html)
        total = self._panel_total(html)
        pagecount = max(1, (total + 23) // 24) if total else 9999
        return {"page": pg, "pagecount": pagecount, "limit": 24, "total": total or 99999, "list": cards}

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids or "")
        vid = vid.strip()
        if not vid:
            return {"list": []}
        if vid.startswith("archives_"):
            return self._detail_archives(vid.replace("archives_", ""))
        return self._detail_video(vid)

    def _detail_video(self, vid):
        result = {"list": []}
        try:
            title, cover, desc = "", "", ""
            data = self._get(self.host + "/api/videos/detail/" + vid, asjson=True)
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                item = data["data"]
                title = item.get("title", "") or ""
                cover = self._proxy_pic(item.get("cover", "") or "")
                desc = item.get("description", "") or ""
            if not title or not cover:
                html = ""
                for path in ("/video/%s/" % vid, "/detail/%s/" % vid):
                    html = self._get(self.host + path) or ""
                    if html and "<h1" in html:
                        break
                if html and etree is not None:
                    if not isinstance(html, str):
                        html = self._ensure_str(html)
                    try:
                        tree = etree.HTML(html)
                    except Exception:
                        tree = None
                    if tree is not None:
                        if not title:
                            tm = "".join(tree.xpath('//h1/text()')).strip()
                            title = re.sub(r'\s*第\s*\d+\s*集\s*$', '', tm).strip() if tm else vid
                        if not cover:
                            pic_l = tree.xpath('//*[contains(@class,"hg-web-detail__poster")]//img/@data-src') or tree.xpath('//*[contains(@class,"hg-web-detail__poster")]//img/@src') or tree.xpath('//img/@data-src') or tree.xpath('//img/@src')
                            cover = self._proxy_pic(pic_l[0].strip()) if pic_l else ""
                        if not desc:
                            desc = "".join(tree.xpath('//*[contains(@class,"hg-web-detail__desc")]/text()')).strip()
                        remarks_l = "".join(tree.xpath('//*[contains(@class,"hg-web-detail__poster")]//*[contains(@class,"hg-web-detail__episode")]//text()')).strip()
                        score_l = "".join(tree.xpath('//*[contains(@class,"hg-web-detail__score")]//text()')).strip()
                        tags = [t.strip() for t in tree.xpath('//*[contains(@class,"hg-web-detail__tags")]//*[contains(@class,"hg-tag")]//text()') if t.strip()]
                        meta = "".join(tree.xpath('//*[contains(@class,"hg-web-detail__meta")]//text()')).strip()
                        eps = []
                        for a in tree.xpath('//*[contains(@class,"hg-web-detail__ep-grid")]//a'):
                            href = a.get("href", "") or ""
                            if not href:
                                continue
                            eid = a.get("data-ep-id", "") or ""
                            name_ep = "第" + eid + "集" if eid else "".join(a.xpath('.//text()')).strip()
                            eps.append(name_ep + "$" + self._fix(href))
                        if not eps:
                            play = tree.xpath('//*[contains(@class,"hg-web-detail__play")]/@href')
                            if play:
                                eps = ["第1集$" + self._fix(play[0])]
                        if eps:
                            info = {"vod_id": vid, "vod_name": title, "vod_pic": cover, "vod_play_from": "黄果短剧", "vod_play_url": "#".join(eps), "vod_content": desc}
                            if remarks_l:
                                info["vod_remarks"] = remarks_l
                            elif score_l:
                                info["vod_remarks"] = score_l + "分"
                            if tags:
                                info["vod_class"] = ",".join(tags)
                            ym = re.search(r"(20\d{2})-(\d{2})-(\d{2})", meta or "")
                            if ym:
                                info["vod_year"] = ym.group(1)
                            result["list"].append(info)
                            return result
            ep_srcs = self._extract_sources(vid)
            if ep_srcs:
                segs = ["第%s集$%s" % (ep, src) for ep, src in sorted(ep_srcs.items(), key=lambda x: int(x[0]))]
                play_url = "#".join(segs)
            else:
                play_url = "第1集$%s" % vid
            if not title:
                title = vid
            result["list"].append({"vod_id": vid, "vod_name": title, "vod_pic": cover, "vod_content": desc, "vod_play_from": "黄果短剧", "vod_play_url": play_url})
        except Exception:
            pass
        return result

    def _extract_sources(self, vid):
        ep_srcs = {}
        check_ep = 1
        max_check = 100
        while check_ep <= max_check:
            url = "/video/%s/ep-%d/" % (vid, check_ep) if check_ep > 1 else "/video/%s/" % vid
            html = self._get(self.host + url)
            if not html:
                break
            new_eps = False
            for m in re.finditer(r'<script[^>]*>(.*?)</script>', html, re.DOTALL):
                block = m.group(1)
                if 'epPlaySrcs' not in block and 'videoSrc' not in block:
                    continue
                vs_m = re.search(r'"videoSrc"\s*:\s*"((?:https?://)?[^"]+)"', block)
                if vs_m:
                    src = vs_m.group(1).replace('\\u0026', '&')
                    if src.startswith("//"):
                        src = "https:" + src
                    if str(check_ep) not in ep_srcs:
                        ep_srcs[str(check_ep)] = src
                        new_eps = True
                eps_m = re.search(r'"epPlaySrcs"\s*:\s*(\{[^}]+\})', block)
                if eps_m:
                    try:
                        raw = eps_m.group(1).replace('\\u0026', '&')
                        eps = json.loads(raw)
                        for ep, src in eps.items():
                            if src and ep not in ep_srcs:
                                if src.startswith("//"):
                                    src = "https:" + src
                                ep_srcs[ep] = src
                                new_eps = True
                    except Exception:
                        pass
                if new_eps:
                    break
            if not new_eps and check_ep > 1:
                break
            check_ep += 1
            time.sleep(0.15)
        if not ep_srcs:
            html = self._get(self.host + "/video/%s/" % vid)
            if html:
                for m in re.finditer(r'(?:data-src|src)="([^"]*\.m3u8[^"]*)"', html):
                    src = m.group(1).replace('\\u0026', '&')
                    if src.startswith("//"):
                        src = "https:" + src
                    if "1" not in ep_srcs:
                        ep_srcs["1"] = src
        return ep_srcs

    def _detail_archives(self, post_id):
        result = {"list": []}
        try:
            html = self._get(self.host + "/archives/%s/" % post_id)
            if not html:
                return result
            tm = re.search(r'<title>(.*?)</title>', html)
            title = (tm.group(1).replace(" - 黄果短剧", "").strip()) if tm else ("吃瓜%s" % post_id)
            pm = re.search(r'data-src="(https?://[^"]+)"', html) or re.search(r'src="(https?://[^"]+)"', html)
            pic = self._proxy_pic(pm.group(1)) if pm else ""
            video_url = ""
            m = re.search(r'<video[^>]+src="(https?://[^"]+)"', html)
            if m:
                video_url = m.group(1)
            if not video_url:
                m = re.search(r'<iframe[^>]+src="(https?://[^"]+)"', html)
                if m:
                    video_url = m.group(1)
            if not video_url:
                m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html)
                if m:
                    video_url = m.group(1)
            play_url = "第1集$%s" % video_url if video_url else "第1集$%s" % post_id
            result["list"].append({"vod_id": "archives_%s" % post_id, "vod_name": title, "vod_pic": pic, "vod_content": "吃瓜内容", "vod_play_from": "黄果短剧", "vod_play_url": play_url})
        except Exception:
            pass
        return result

    def searchContent(self, key, quick=False, pg="1"):
        result = {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
        try:
            page = max(int(pg or 1), 1)
            url = self.host + "/search/?keyword=%s" % quote(key)
            if page > 1:
                url += "&page=%d" % page
            html = self._get(url)
            if not html:
                return result
            videos, seen = [], set()
            for m in re.finditer(r'data-track-id="(\d+)"', html):
                vid = m.group(1)
                if vid in seen:
                    continue
                chunk = html[m.start():m.start() + 800]
                tm = re.search(r'data-track-title="([^"]*)"', chunk)
                pm = re.search(r'data-src="(https?://[^"]*)"', chunk) or re.search(r'src="(https?://[^"]*)"', chunk)
                videos.append({"vod_id": vid, "vod_name": tm.group(1) if tm else "", "vod_pic": self._proxy_pic(pm.group(1)) if pm else "", "vod_remarks": ""})
                seen.add(vid)
            result["list"] = videos
            tm2 = re.search(r'data-track-search-total="(\d+)"', html)
            pm2 = re.search(r'data-pages="(\d+)"', html)
            if tm2:
                result["total"] = int(tm2.group(1))
            result["pagecount"] = int(pm2.group(1)) if pm2 else (page + 1 if len(videos) >= 20 else page)
            result["page"] = page
        except Exception:
            pass
        return result

    def searchContentPage(self, key, quick=False, pg="1", size="20"):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags=None):
        header = {
            "User-Agent": self.ua,
            "Referer": self.host + "/",
        }
        result = {"parse": 0, "jx": 0, "playUrl": "", "url": "", "header": header, "format": "application/x-mpegURL"}
        if not id:
            return result
        raw = str(id).strip()
        if raw.startswith("http") and (".m3u8" in raw or ".mp4" in raw):
            if ".mp4" in raw.lower():
                result["format"] = "video/mp4"
            result["url"] = raw
            return result
        if raw.startswith("archives_"):
            d = self._detail_archives(raw.replace("archives_", ""))
            pu = (d.get("list") or [{}])[0].get("vod_play_url", "")
            parts = pu.split("$", 1)
            if len(parts) == 2 and parts[1].startswith("http"):
                if ".mp4" in parts[1].lower():
                    result["format"] = "video/mp4"
                result["url"] = parts[1]
                return result
            result["parse"] = 1
            result["url"] = "%s/archives/%s/" % (self.host, raw.replace("archives_", ""))
            return result
        if raw.startswith("http"):
            url = raw
        elif raw.startswith("/"):
            url = self._fix(raw)
        elif raw.isdigit():
            url = "%s/video/%s/" % (self.host, raw)
        else:
            url = self._fix(raw)
        html = self._get(url, referer=self.host)
        play = ""
        mime = "application/x-mpegURL"
        if html:
            mm = re.search(r'<script id="videoInitialData" type="application/json">(.*?)</script>', html, re.S)
            if mm:
                try:
                    data = json.loads(mm.group(1))
                except Exception:
                    data = dict()
                if isinstance(data, dict):
                    em = re.search(r"/ep-(\d+)/", url)
                    ep = str(em.group(1)) if em else "1"
                    srcs = data.get("epPlaySrcs") or dict()
                    play = srcs.get(ep) or data.get("videoSrc") or ""
        if play:
            play = play.replace("\\u0026", "&")
            if not play.startswith("http"):
                mm2 = re.search(r"(https?://[^\s\"']+)", play)
                play = mm2.group(1) if mm2 else ""
            if ".mp4" in play.lower():
                mime = "video/mp4"
        if not play:
            m = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', html or "")
            if m:
                play = m.group(1).replace("\\u0026", "&")
                if ".mp4" in play.lower():
                    mime = "video/mp4"
        if not play:
            data = self._get(self.host + "/api/videos/detail/" + (re.search(r"/video/(\d+)", url).group(1) if re.search(r"/video/(\d+)", url) else ""), asjson=True)
            if isinstance(data, dict):
                src = (data.get("data") or {}).get("videoSrc", "") if isinstance(data.get("data"), dict) else ""
                if src:
                    play = src
        result["url"] = play
        result["format"] = mime
        return result

    def proxy(self, param=None):
        result = self.localProxy(param)
        if isinstance(result, (list, tuple)) and len(result) >= 4:
            return [result[0], result[1], result[2]]
        return result

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = dict()
        if not isinstance(param, dict):
            param = dict()
        else:
            param = dict(param)
        def _one(v):
            if isinstance(v, (list, tuple)):
                return v[0] if v else ""
            return v
        try:
            kind = _one(param.get("type") or param.get("action") or "")
            kind = str(kind or "").strip().lower()
            if kind not in ("img",):
                kind = "img"
            if kind == "img":
                raw = _one(param.get("url", "")) or ""
                if raw:
                    url = b64decode(unquote(str(raw)).encode("utf-8")).decode("utf-8")
                    url = self._img_src(url)
                    if url:
                        raw2 = self._get_bin(url)
                        if raw2:
                            data = self._decrypt_img(raw2)
                            return [200, self._img_ct(data), data, {"Access-Control-Allow-Origin": "*"}]
        except Exception:
            pass
        return [404, "text/plain", "Not Found", dict()]

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return ".m3u8" in u or ".mp4" in u or ".flv" in u or ".ts" in u or ".m4v" in u

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return dict()

    def destroy(self):
        return None