#!/usr/bin/python
# -*- coding: utf-8 -*-
import re
import json
import ssl as _ssl
import html as html_lib
import urllib.parse
import urllib.request

import requests

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider(object):
        def fetch(self, url, headers=None, timeout=20, verify=False, cookies=None):
            return requests.get(url, headers=headers, timeout=timeout, verify=verify, cookies=cookies)


class Spider(BaseSpider):

    host = "https://jlm7.cc"
    name = "吉利猫"
    _ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    def init(self, extend=""):
        self.headers = {"User-Agent": self._ua, "Referer": self.host + "/"}
        self._filters = None
        self._categories = []
        try:
            self._ssl_ctx = _ssl._create_unverified_context()
        except Exception:
            self._ssl_ctx = None
        return {}

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

    def liveContent(self, url):
        return ""

    def action(self, action):
        return "{}"

    def localProxy(self, param):
        return [200, "text/plain", ""]

    def destroy(self):
        pass

    def _dict(self, v):
        if isinstance(v, dict):
            return v
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                return d if isinstance(d, dict) else {}
            except Exception:
                return {}
        return {}

    def _list(self, v):
        if isinstance(v, (list, tuple)):
            return [str(i) for i in v]
        if isinstance(v, (str, bytes)):
            try:
                d = json.loads(v)
                if isinstance(d, (list, tuple)):
                    return [str(i) for i in d]
            except Exception:
                pass
            return [str(v)]
        return []

    def _headers(self):
        return getattr(self, "headers", {"User-Agent": self._ua, "Referer": self.host + "/"})

    def _fetch(self, url, timeout=20):
        headers = dict(self._headers())
        try:
            r = requests.get(url, headers=headers, timeout=timeout, verify=False)
            if r.status_code == 200:
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers=headers)
            ctx = getattr(self, "_ssl_ctx", None)
            resp = urllib.request.urlopen(req, timeout=timeout, context=ctx)
            data = resp.read()
            try:
                return data.decode("utf-8")
            except Exception:
                return data.decode("gbk", errors="ignore")
        except Exception:
            return ""
        return ""

    def _fix(self, u):
        if not u:
            return ""
        u = u.strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _unesc(self, s):
        try:
            return html_lib.unescape(s or "").strip()
        except Exception:
            return (s or "").strip()

    def _vid(self, s):
        s = str(s or "").strip()
        m = re.search(r"/vod/(?:play|detail)/id/(\d+)\.html", s)
        if m:
            return m.group(1)
        if s.isdigit():
            return s
        m = re.search(r"(\d+)", s)
        return m.group(1) if m else s

    def _parse_list(self, html):
        results, seen = [], set()
        for b in re.findall(r'<li>\s*<div class="video-item">(.*?)</li>', html or "", re.S):
            m = re.search(r'href="[^"]*?/vod/play/id/(\d+)\.html"', b)
            if not m or m.group(1) in seen:
                continue
            seen.add(m.group(1))
            img = re.search(r'<img[^>]*data-src="([^"]+)"[^>]*alt="([^"]*)"', b)
            title = self._unesc(img.group(2)) if img else ""
            if not title:
                t = re.search(r'class="line-clamp-[^"]*"[^>]*>\s*([^<]+?)\s*</a>', b)
                title = self._unesc(t.group(1)) if t else ""
            pic = self._fix(img.group(1)) if img else ""
            if not pic:
                p2 = re.search(r'og:image" content="([^"]+)"', b)
                pic = self._fix(p2.group(1)) if p2 else ""
            rem = re.search(r'rounded-large text-white">([^<]+)</div>', b)
            results.append({
                "vod_id": m.group(1),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": rem.group(1).strip() if rem else "",
            })
        return results

    def _pagecount(self, html, pg):
        if not html or not re.search(r'class="video-item"', html):
            return int(pg) if int(pg) > 1 else 1
        if re.search(r'title="下一页"', html):
            return int(pg) + 1
        return int(pg)

    def _parse_sort_page(self, html):
        parents, children = [], {}
        parts = re.split(r'<h2[^>]*>([^<]+)</h2>', html or "")
        for i in range(1, len(parts), 2):
            pname = self._unesc(parts[i])
            subs = re.findall(r'href="/index\.php/vod/type/id/(\d+)\.html"[^>]*>([^<]+)<', parts[i + 1])
            if not subs:
                continue
            subs = [(tid, self._unesc(n)) for tid, n in subs]
            if pname == "视频类别":
                parents = subs
            else:
                children[pname] = subs
        if not parents:
            parents = [("46", "日韩自拍"), ("43", "色情主播"), ("44", "国产av"), ("59", "乱伦侵犯"),
                       ("47", "日本无码"), ("50", "无码字幕"), ("49", "色情动漫"), ("48", "有码字幕"),
                       ("51", "欧美av"), ("52", "18禁重口味"), ("53", "偷拍偷窥"), ("54", "网爆吃瓜"),
                       ("55", "传媒a片"), ("56", "探花约炮"), ("57", "三级伦理"), ("58", "av解说")]
        return parents, children

    def _build_filters(self):
        if getattr(self, "_filters", None) is not None:
            return self._filters
        sorts = [{"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "日榜", "v": "hits_day"},
                 {"n": "周榜", "v": "hits_week"}, {"n": "月榜", "v": "hits_month"}, {"n": "评分", "v": "score"}]
        html = self._fetch(self.host + "/index.php/label/sort.html")
        parents, children = self._parse_sort_page(html)
        self._categories = [{"type_id": tid, "type_name": name} for tid, name in parents]
        self._filters = {}
        for tid, pname in parents:
            f = [{"key": "by", "name": "排序", "value": sorts}]
            subs = children.get(pname, [])
            if subs:
                f.insert(0, {"key": "sub", "name": "子分类",
                             "value": [{"n": "全部", "v": ""}] + [{"n": n, "v": tid2} for tid2, n in subs]})
            self._filters[tid] = f
        return self._filters

    def homeContent(self, filter=False):
        filters = self._build_filters()
        home = self._fetch(self.host + "/")
        return {"class": getattr(self, "_categories", []), "filters": filters, "list": self._parse_list(home)}

    def homeVideoContent(self):
        return {"list": self._parse_list(self._fetch(self.host + "/"))}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        try:
            pg = max(1, int(str(pg).strip() or 1))
        except Exception:
            pg = 1
        f = {}
        ff = self._dict(filter)
        if ff:
            f.update(ff)
        fe = self._dict(extend)
        if fe:
            f.update(fe)
        cur = f.get("sub") or tid
        cur = str(cur) if str(cur).isdigit() else tid
        by = f.get("by") or ""
        if by and re.match(r"^[a-z_0-9]+$", str(by)):
            url = "%s/index.php/vod/show/id/%s/by/%s/page/%d.html" % (self.host, cur, by, pg)
        else:
            url = "%s/index.php/vod/type/id/%s/page/%d.html" % (self.host, cur, pg)
        html = self._fetch(url)
        vods = self._parse_list(html)
        pagecount = self._pagecount(html, pg)
        if not vods and pg > 1:
            pagecount = pg
        return {"page": pg, "pagecount": pagecount, "limit": 20, "total": 0, "list": vods}

    def detailContent(self, ids):
        vid = self._vid(self._list(ids)[0]) if self._list(ids) else ""
        if not vid:
            return {"list": []}
        html = html_lib.unescape(self._fetch("%s/index.php/vod/play/id/%s.html" % (self.host, vid)))
        name = ""
        m = re.search(r'<h1 class="dx-title[^"]*"[^>]*>([^<]+)</h1>', html)
        if m:
            name = self._unesc(m.group(1))
        if not name:
            m = re.search(r'og:title" content="([^"]*)"', html)
            if m:
                name = self._unesc(m.group(1).split(" - ")[0])
        pic = ""
        m = re.search(r'og:image" content="([^"]+)"', html)
        if m:
            pic = self._fix(m.group(1))
        vclass = ""
        m = re.search(r'href="/index\.php/vod/type/id/\d+\.html"[^>]*>([^<]+)</a>', html)
        if m:
            vclass = self._unesc(m.group(1))
        tags = []
        for tm in re.finditer(r'href="/index\.php/vod/search/wd/([^"]+)\.html"[^>]*>\s*([^<]+?)\s*</a>', html):
            t = self._unesc(tm.group(2))
            if t and t not in tags:
                tags.append(t)
            if len(tags) >= 8:
                break
        m = re.search(r'>([^<>]*(?:天前|小时前|分钟前))\s*<', html)
        remarks = m.group(1).strip() if m else ""
        play_url = "%s/index.php/vod/play/id/%s.html" % (self.host, vid)
        return {"list": [{
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": pic,
            "vod_class": vclass,
            "tag": ",".join(tags),
            "vod_remarks": remarks,
            "vod_content": "标签：" + " / ".join(tags) if tags else "",
            "vod_play_from": self.name,
            "vod_play_url": "播放$" + play_url,
        }]}

    def searchContent(self, key, quick, pg="1"):
        try:
            pg = max(1, int(str(pg).strip() or 1))
        except Exception:
            pg = 1
        q = urllib.parse.quote(str(key))
        if pg > 1:
            url = "%s/index.php/vod/search/page/%d/wd/%s.html" % (self.host, pg, q)
        else:
            url = "%s/index.php/vod/search/wd/%s.html" % (self.host, q)
        html = self._fetch(url)
        vods = self._parse_list(html)
        pagecount = self._pagecount(html, pg)
        if not vods and pg > 1:
            pagecount = pg
        return {"page": pg, "pagecount": pagecount, "list": vods}

    def playerContent(self, flag, id, vipFlags):
        url = id if str(id).startswith("http") else self._fix(id)
        parse = 0
        if ".m3u8" not in url and ".mp4" not in url:
            html = self._fetch(url)
            url2 = ""
            if html:
                m = re.search(r'const\s+source\s*=\s*[\'"]([^\'"]+)[\'"]', html)
                if m:
                    url2 = m.group(1)
                if not url2:
                    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
                    if m:
                        url2 = m.group(1)
                if not url2:
                    m = re.search(r'(https?://[^\s"\'<>]+\.mp4[^\s"\'<>]*)', html)
                    if m:
                        url2 = m.group(1)
            if url2:
                url = self._fix(url2)
            else:
                parse = 1
        return {"parse": parse, "playUrl": "", "url": url, "header": json.dumps({
            "User-Agent": self._ua, "Referer": self.host + "/"})}
