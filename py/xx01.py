import base64
import html as htmlmod
import json
import re
import threading
import time
import urllib.parse
from urllib.parse import urljoin, urlparse

import requests
from lxml import etree

try:
    import sys
    sys.path.append('..')
    from base.spider import Spider as _Base
except Exception:
    _Base = object


class Spider(_Base):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = "https://xx01.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-User": "?1",
            "Referer": "https://xx01.com/",
        }
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self.headers)
        self.classes = [
            {"type_id": "chinese-subtitle", "type_name": "中文字幕"},
            {"type_id": "madou", "type_name": "国产AV"},
            {"type_id": "new", "type_name": "最近更新"},
            {"type_id": "release", "type_name": "新作上市"},
            {"type_id": "uncensored-leak", "type_name": "无码流出"},
            {"type_id": "anime", "type_name": "成人动漫"},
            {"type_id": "VR", "type_name": "VR"},
            {"type_id": "avtalk", "type_name": "AV解说"},
            {"type_id": "siro", "type_name": "SIRO"},
            {"type_id": "luxu", "type_name": "LUXU"},
            {"type_id": "gana", "type_name": "GANA"},
            {"type_id": "fc2", "type_name": "FC2"},
            {"type_id": "heyzo", "type_name": "HEYZO"},
            {"type_id": "tokyohot", "type_name": "东京热"},
            {"type_id": "1pondo", "type_name": "一本道"},
            {"type_id": "caribbeancom", "type_name": "Caribbeancom"},
            {"type_id": "10musume", "type_name": "10musume"},
            {"type_id": "pacopacomama", "type_name": "pacopacomama"},
            {"type_id": "klive", "type_name": "韩国直播"},
            {"type_id": "clive", "type_name": "中国直播"},
            {"type_id": "tiktok", "type_name": "抖阴视频"},
            {"type_id": "starface", "type_name": "明星换脸"},
            {"type_id": "cmedia", "type_name": "国产传媒"},
        ]

    def getDependence(self):
        return []

    def action(self, action):
        return {}

    def init(self, extend=""):
        if isinstance(extend, str):
            text = extend.strip()
            if text.startswith("{"):
                try:
                    cfg = json.loads(text)
                    if isinstance(cfg, dict) and cfg.get("site"):
                        self.host = cfg["site"].rstrip("/")
                except Exception:
                    pass
            elif text.startswith("http"):
                self.host = text.rstrip("/")
        elif isinstance(extend, dict) and extend.get("site"):
            self.host = str(extend["site"]).rstrip("/")
        self.headers["Referer"] = self.host + "/"
        self.session.headers.update(self.headers)

    def getName(self):
        return "XX01"

    def isVideoFormat(self, url):
        if not url:
            return False
        return ".m3u8" in url or ".mp4" in url or ".flv" in url or ".ts" in url

    def manualVideoCheck(self):
        return False

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

    def localProxy(self, param):
        if isinstance(param, str):
            try:
                param = json.loads(param)
            except Exception:
                param = {}
        if not isinstance(param, dict):
            param = {}
        try:
            ptype = str(param.get('type', ''))
            if 'm3u8' in ptype:
                inner = urllib.parse.unquote(str(param.get('url', '')))
                vid = str(param.get('vid', ''))
                if not inner:
                    return [500, 'text/plain', b'empty']
                data = self.req('https://pl3.vvvvvvvv.top/api/play?url=' + urllib.parse.quote(inner, safe=':/?=&'), timeout=20, headers={'User-Agent': self.headers['User-Agent'], 'Referer': self.host + '/'}).text
                base = 'https://pl3.vvvvvvvv.top/api/play?url='
                out = []
                for line in data.splitlines():
                    s = line.strip()
                    if not s:
                        continue
                    if s.startswith('#'):
                        if s.startswith('#EXT-X-STREAM-INF'):
                            out.append(s)
                        elif s.startswith('#EXT-X-TOKEN'):
                            out.append(s)
                        elif s.startswith('#EXTM3U') or s.startswith('#EXT-X-VERSION') or s.startswith('#EXT-X-TARGETDURATION') or s.startswith('#EXT-X-MEDIA-SEQUENCE') or s.startswith('#EXT-X-PLAYLIST-TYPE') or s.startswith('#EXT-X-ENDLIST'):
                            out.append(s)
                        continue
                    if s.startswith('https://pl3.vvvvvvvv.top/api/play?url='):
                        out.append(s + '&r=' + urllib.parse.quote('https://missav.ws/', safe=''))
                    elif s.startswith('http'):
                        out.append(base + urllib.parse.quote(s, safe='') + '&r=' + urllib.parse.quote('https://missav.ws/', safe=''))
                    else:
                        out.append(s)
                body = '\n'.join(out)
                try:
                    thread = threading.Thread(target=self._cache_times, args=(vid, body))
                    thread.start()
                except Exception:
                    pass
                return [200, 'application/vnd.apple.mpegurl', body]
        except Exception as e:
            try:
                print(e)
            except Exception:
                pass
            return [500, 'text/html', '']
        return [404, "text/plain", b"Not Found", {}]

    def _cache_times(self, vid, body):
        try:
            times = 0.0
            for line in body.splitlines():
                if line.startswith('#EXTINF:'):
                    try:
                        times += float(line.split(':')[1].split(',')[0])
                    except Exception:
                        pass
            time.sleep(1)
            purl = self.getProxyUrl() + '&type=xdm&vid=' + urllib.parse.quote(str(vid), safe='')
            self.fetch('http://127.0.0.1:9978/action?do=refresh&type=danmaku&path=' + urllib.parse.quote(purl, safe=''), timeout=5)
        except Exception:
            pass

    def req(self, url, timeout=15, **kw):
        kw.setdefault('timeout', timeout)
        kw.setdefault('headers', self.headers)
        kw.setdefault('verify', False)
        r = self.session.get(url, **kw)
        enc = (r.encoding or "").lower()
        if not enc or enc in ("iso-8859-1", "latin-1", "ascii", "windows-1252"):
            r.encoding = "utf-8"
        return r

    def pq(self, html):
        from lxml import html as lhtml
        return _PQ(lhtml.fromstring(html))

    def getdoc(self, path_or_url):
        url = path_or_url if path_or_url.startswith('http') else self.host + path_or_url
        return self.pq(self.req(url).text)

    def getlist(self, data):
        videos = []
        for k in data.items():
            try:
                a = k.attr('href')
                b = k.text()
                if a and b and a.startswith('/'):
                    videos.append({'vod_id': a.strip('/'), 'vod_name': b.replace('\n', ' ').strip()})
            except Exception:
                continue
        return videos

    def _fetch(self, url, timeout=30):
        try:
            r = self.req(url, timeout=timeout)
            if r.status_code == 200:
                return r.text
            return ""
        except Exception:
            return ""

    def _clean(self, text):
        if not text:
            return ""
        return htmlmod.unescape(re.sub(r"<[^>]+>", "", str(text))).strip()

    def _fix_pic(self, pic):
        if not pic:
            return ""
        if pic.startswith("//"):
            return "https:" + pic
        if pic.startswith("/"):
            return urljoin(self.host, pic)
        return pic

    def _parse_list(self, page_text):
        ret = []
        if not page_text:
            return ret
        doc = etree.HTML(page_text)
        if doc is None:
            return ret
        seen = set()
        for wrap in doc.xpath('//div[contains(@class,"item-wrapper")]'):
            try:
                alist = wrap.xpath('.//a[@href]')
                href = ""
                for a in alist:
                    h = (a.get("href") or "").strip()
                    if h and not h.startswith(("http", "#", "javascript", "/genres", "/actresses", "/new?", "/search")):
                        href = h
                        break
                if not href:
                    continue
                vid = href.strip("/")
                if not vid or vid in seen or "/" in vid.replace("-", "") and len(vid) > 60:
                    if vid in seen:
                        continue
                if "/" in vid:
                    continue
                seen.add(vid)
                name = ""
                tlist = wrap.xpath('.//div[contains(@class,"truncate")]//a/text()')
                if tlist:
                    name = tlist[0].strip()
                if not name:
                    imgs = wrap.xpath('.//img[@alt]/@alt')
                    if imgs:
                        name = imgs[0].strip()
                if not name:
                    name = vid
                pic = ""
                imgs = wrap.xpath('.//img')
                for img in imgs:
                    cand = img.get("data-src") or img.get("data-original") or img.get("src") or ""
                    if cand and "flags/" not in cand and "loading" not in cand and "data:image" not in cand:
                        pic = cand.strip()
                        break
                if pic.startswith("//"):
                    pic = "https:" + pic
                elif pic.startswith("/"):
                    pic = urljoin("https://ig2.pppppppp.top", pic)
                pic = self._fix_pic(pic)
                remarks = ""
                rlist = wrap.xpath('.//span[contains(@class,"absolute")]/text()')
                if rlist:
                    remarks = rlist[0].strip()
                ret.append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_remarks": remarks})
            except Exception:
                continue
        return ret

    def homeContent(self, filter=None):
        return {"class": self.classes, "filters": {}}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._fetch(self.host + "/new"))[:30]}

    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        tid = str(tid or "new").strip("/")
        url = self.host + "/" + tid
        if pg > 1:
            url += "?page=" + str(pg)
        items = self._parse_list(self._fetch(url))
        return {"list": items, "page": pg, "pagecount": pg + 1 if items else pg, "limit": len(items), "total": 0}

    def _decode_packer(self, page_text):
        urls = []
        if not page_text:
            return urls
        for m in re.finditer(r"eval\(function\(p,a,c,k,e,d\)(.*?)\)\)", page_text, re.S):
            try:
                chunk = m.group(0)
                args = re.search(r"\}\('(.*?)',\d+,\d+,'(.*?)'\.split\('\|'\)", chunk, re.S)
                if not args:
                    continue
                p, k = args.group(1), args.group(2).split("|")
                a = 15
                try:
                    am = re.search(r",(\d+),\d+,'", chunk)
                    if am:
                        a = int(am.group(1))
                except Exception:
                    pass
                def b36(n):
                    ch = "0123456789abcdefghijklmnopqrstuvwxyz"
                    if n == 0:
                        return "0"
                    o = ""
                    while n > 0:
                        o = ch[n % a] + o
                        n //= a
                    return o
                d = {}
                c = len(k)
                while c > 0:
                    c -= 1
                    d[b36(c)] = k[c] if c < len(k) else b36(c)
                def repl(mm):
                    w = mm.group(0)
                    return d.get(w, w)
                dec = re.sub(r"\b\w+\b", repl, p)
                for u in re.findall(r"https?://[^\s\"'<>;]+", dec):
                    u = u.replace("\\/", "/").strip("\\'\";")
                    if "surrit.com" in u and u not in urls:
                        urls.append(u)
            except Exception:
                continue
        return urls

    def _extract_video_urls(self, page_text):
        cands = []
        if not page_text:
            return cands
        text = htmlmod.unescape(page_text)
        for m in re.findall(r"https://pl3\.vvvvvvvv\.top/api/play\?url=[^\s\"'<>\[\]]+", text):
            u = m.strip()
            if u.startswith("http"):
                cands.append(u)
        for pat in [
            r"(https?://[^\s\"'<>\[\]]+\.m3u8(?:\?[^\s\"'<>\[\]]*)?)",
            r"(https?://[^\s\"'<>\[\]]+\.mp4(?:\?[^\s\"'<>\[\]]*)?)",
            r"(https?://[^\s\"'<>\[\]]*fourhoi\.com[^\s\"'<>\[\]]*)",
            r"(https?://[^\s\"'<>\[\]]*surrit\.com[^\s\"'<>\[\]]*)",
            r"(https?://[^\s\"'<>\[\]]+/api/proxy/\?url=[^\s\"'<>\[\]]+)",
        ]:
            for m in re.findall(pat, text):
                u = m[0] if isinstance(m, tuple) else m
                u = u.strip()
                if u and u.startswith("http") and "cover-" not in u and "${" not in u:
                    cands.append(u)
        for uid in re.findall(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", text, re.I):
            cands.append("https://pl3.vvvvvvvv.top/api/play?url=" + urllib.parse.quote("https://surrit.com/" + uid + "/playlist.m3u8", safe=":/?=&"))
        return cands

    def _pick_best(self, urls):
        def score(u):
            s = 0
            if "pl3.vvvvvvvv.top/api/play" in u:
                s += 200
            if ".m3u8" in u:
                s += 100
            if "playlist.m3u8" in u:
                s += 50
            if "surrit.com" in u:
                s += 40
            if "fourhoi.com" in u:
                s += 35
            if ".mp4" in u and "preview" not in u:
                s += 30
            if "preview" in u:
                s -= 50
            if u.endswith((".jpg", ".png", ".webp", ".gif")):
                s -= 1000
            return s
        seen = set()
        uniq = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                uniq.append(u)
        if not uniq:
            return ""
        uniq.sort(key=score, reverse=True)
        return uniq[0]

    def _build_lines(self, page_text, vid, page_url=""):
        raw = self._decode_packer(page_text or "")
        inner = []
        for u in raw:
            if "/720p/" in u:
                q = urllib.parse.quote(u, safe=":/?=&")
                inner.append("https://pl3.vvvvvvvv.top/api/play?url=" + q)
            else:
                inner.append(u)
        uidm = re.search(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", page_text or "", re.I)
        full = ""
        preview = ""
        if uidm:
            uid = uidm.group(1)
            inner_url = "https://surrit.com/" + uid + "/playlist.m3u8"
            full = self.getProxyUrl() + "&type=m3u8&vid=" + urllib.parse.quote(vid, safe="") + "&url=" + urllib.parse.quote(inner_url, safe="")
            preview = "https://ig2.pppppppp.top/api/proxy/?url=" + urllib.parse.quote("https://fourhoi.com/" + vid + "/preview.mp4", safe="")
        froms, urls = [], []
        if full:
            froms.append("高清")
            urls.append("播放$" + full)
        for u in inner:
            if u != full.replace("https://pl3.vvvvvvvv.top/api/play?url=", "") and u not in full:
                q = u if u.startswith("https://pl3.") else "https://pl3.vvvvvvvv.top/api/play?url=" + urllib.parse.quote(u, safe=":/?=&")
                if q != full:
                    froms.append("备用")
                    urls.append("播放$" + q)
                    break
        if preview:
            froms.append("预告")
            urls.append("播放$" + preview)
        if not froms:
            four = "https://fourhoi.com/" + vid + "/playlist.m3u8"
            froms.append("高清")
            urls.append("播放$" + "https://ig2.pppppppp.top/api/proxy/?url=" + urllib.parse.quote(four, safe=""))
        return froms, urls

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids else ""
        else:
            vid = str(ids or "")
        vid = vid.strip().strip("/")
        url = self.host + "/" + vid
        title = vid
        content = ""
        pic = ""
        play = ""
        page_text = self._fetch(url, timeout=20)
        froms, urls = [], []
        if page_text:
            doc = etree.HTML(page_text)
            if doc is not None:
                h1 = doc.xpath("//h1/text()")
                if h1 and h1[0].strip():
                    title = h1[0].strip()
                else:
                    og = doc.xpath('//meta[@property="og:title"]/@content')
                    if og:
                        title = og[0].strip()
                title = re.sub(r"\s*[-|]\s*XX01\.?COM.*$", "", title, flags=re.I).strip()
                if len(title) > 200:
                    title = title[:200].rstrip() + "..."
                desc = doc.xpath('//meta[@name="description"]/@content | //meta[@property="og:description"]/@content')
                if desc and len(desc[0]) > 10:
                    content = desc[0].strip()
                ogimg = doc.xpath('//meta[@property="og:image"]/@content')
                if ogimg:
                    pic = self._fix_pic(ogimg[0])
            froms, urls = self._build_lines(page_text, vid)
        if not froms:
            froms, urls = self._build_lines("", vid)
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": content,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick=False, pg="1"):
        try:
            pg = int(pg) if pg else 1
        except Exception:
            pg = 1
        url = self.host + "/search/" + urllib.parse.quote(str(key))
        if pg > 1:
            url += "?page=" + str(pg)
        items = self._parse_list(self._fetch(url))
        return {"list": items, "page": pg, "pagecount": pg + 1 if items else pg}

    def playerContent(self, flag, id, vipFlags=None):
        if isinstance(id, (list, tuple)):
            id = str(id[0]) if id else ""
        else:
            id = str(id or "")
        if id.startswith("嗅探$"):
            id = id[3:]
        if id.startswith(self.getProxyUrl()) or ('type=m3u8' in id and 'url=' in id):
            return {"parse": 0, "jx": 0, "playUrl": "", "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}
        if id.startswith("http"):
            if "api/play?url=" in id or "api/proxy" in id:
                return {"parse": 0, "jx": 0, "playUrl": "", "url": id, "header": {"Referer": self.host + "/", "User-Agent": self.headers["User-Agent"]}}
            if re.search(r"\.(m3u8|mp4|flv|ts)(\?|$)", id, re.I):
                return {"parse": 0, "jx": 0, "playUrl": "", "url": id, "header": dict(self.headers)}
            return {"parse": 0, "jx": 0, "playUrl": "", "url": id, "header": dict(self.headers)}
        return {"parse": 0, "jx": 0, "playUrl": "", "url": id, "header": dict(self.headers)}


class _PQ:
    def __init__(self, nodes):
        if isinstance(nodes, _PQ):
            nodes = nodes._nodes
        self._nodes = list(nodes) if isinstance(nodes, (list, tuple)) else [nodes]

    def __call__(self, selector=None):
        if not selector:
            return self
        out = []
        for el in self._nodes:
            try:
                out.extend(el.cssselect(selector))
            except Exception:
                pass
        return _PQ(out)

    def __bool__(self):
        return len(self._nodes) > 0

    def __len__(self):
        return len(self._nodes)

    def items(self):
        for el in self._nodes:
            yield _PQ(el)

    def attr(self, name):
        if not self._nodes:
            return None
        return self._nodes[0].get(name)

    def text(self):
        if not self._nodes:
            return ''
        parts = []
        for el in self._nodes:
            if isinstance(getattr(el, 'tag', None), str) and el.tag in ('script', 'style'):
                continue
            try:
                t = el.text_content().strip()
            except Exception:
                t = ''
            if t:
                parts.append(t)
        return '\n'.join(parts)
