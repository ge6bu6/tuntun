#!/usr/bin/python
# coding=utf-8
"""极速追剧 jisuzhuiju.com —— TVBox Drpy 源。

站点: https://jisuzhuiju.com/  (自建站, 非标准 MacCMS)
结构:
  分类   /type/{dianshiju|dianying|dongman|zongyi}.html  (单页, 无分页)
  首页   /
  详情   /detail/{id}.html
         线路名: <button class="source-tab" data-target="source-N">线路名</button>
         播放面板: <div class="source-panel" id="source-N"> 内 <a href="/vodplay/{id}-{line}-{ep}.html">集名</a>
  播放   /vodplay/{id}-{line}-{ep}.html
         真实地址: GET /api/play-url?vodId={id}&playFrom={line}&index={ep}
                   → {"mode":"native","code":200,"url":"<m3u8>"}
  搜索   /search?keyword={kw}  (search-item 结构)
  详情字段: <span class="meta-label">年份/地区/导演：</span><span class="meta-value">...</span>
"""
import urllib.request, ssl, re, json
from urllib.parse import quote

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

HOST = "https://jisuzhuiju.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

CATS = [
    {"type_id": "dianshiju", "type_name": "电视剧"},
    {"type_id": "dianying", "type_name": "电影"},
    {"type_id": "dongman", "type_name": "动漫"},
    {"type_id": "zongyi", "type_name": "综艺"},
]


class Spider(BaseSpider):
    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = HOST
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE

    def init(self, extend=""):
        pass

    def getName(self):
        return "极速追剧"

    # ── 网络 ─────────────────────────────
    def fetch(self, url, ref=None):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": UA,
                "Referer": ref or (self.host + "/"),
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            return urllib.request.urlopen(req, timeout=20, context=self.ctx).read().decode("utf-8", "ignore")
        except Exception:
            return ""

    def _api(self, path, ref=None):
        try:
            req = urllib.request.Request(self.host + path, headers={
                "User-Agent": UA,
                "Referer": ref or (self.host + "/"),
            })
            return json.loads(urllib.request.urlopen(req, timeout=20, context=self.ctx).read().decode())
        except Exception:
            return {}

    @staticmethod
    def _clean(s):
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s or "")).strip()

    # ── 解析列表卡片 ─────────────────────
    def _cards(self, html):
        out, seen = [], set()
        for m in re.finditer(
                r'<a href="(/detail/(\d+)\.html)"[^>]*>\s*<div class="vod-card">([\s\S]*?)</div>\s*</div>\s*</a>',
                html):
            vid = m.group(2)
            if vid in seen:
                continue
            blk = m.group(3)
            title = (re.search(r'<p class="vod-title[^"]*">([^<]+)</p>', blk) or [None, ""])
            title = self._clean(title.group(1)) if hasattr(title, "group") else ""
            img = (re.search(r'<img[^>]+src="([^"]+)"', blk) or [None, ""])
            pic = img.group(1) if hasattr(img, "group") else ""
            sub = (re.search(r'<p class="vod-subtitle[^"]*">([^<]*)</p>', blk) or [None, ""])
            remarks = self._clean(sub.group(1)) if hasattr(sub, "group") else ""
            seen.add(vid)
            out.append({"vod_id": vid, "vod_name": title or vid,
                        "vod_pic": pic, "vod_remarks": remarks})
        return out

    # ── 接口 ─────────────────────────────
    def homeContent(self, filter):
        return {"class": CATS, "filters": {}, "list": self._cards(self.fetch(self.host + "/"))}

    def homeVideoContent(self):
        return {"list": self._cards(self.fetch(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        html = self.fetch("%s/type/%s.html" % (self.host, tid))
        vids = self._cards(html)
        return {"list": vids, "page": int(pg or 1), "pagecount": 1,
                "limit": len(vids) or 1, "total": len(vids)}

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, list) else str(ids).split(",")[0]
        html = self.fetch("%s/detail/%s.html" % (self.host, vid))
        if not html:
            return {"list": []}

        name = (re.search(r'<h1[^>]*>([^<]+)</h1>', html) or [None, vid])
        name = self._clean(name.group(1)) if hasattr(name, "group") else vid

        pic = ""
        im = re.search(r'<img[^>]+src="(https?://[^"]+)"[^>]*alt="[^"]*海报', html)
        if not im:
            im = re.search(r'<img[^>]+src="(https?://img\.jisuimage\.com/cover/[^"]+)"', html)
        if im:
            pic = im.group(1)

        def meta(label):
            mm = re.search(r'<span class="meta-label">%s：</span>\s*<span class="meta-value">([^<]*)</span>' % label, html)
            return self._clean(mm.group(1)) if mm else ""

        year, area, director = meta("年份"), meta("地区"), meta("导演")

        desc = ""
        dm = re.search(r'剧情简介[\s\S]{0,200}?<div[^>]*class="[^"]*synopsis[^"]*"[^>]*>([\s\S]*?)</div>', html)
        if dm:
            desc = self._clean(dm.group(1))[:900]

        # 线路名(按 source-N 顺序)
        tabs = re.findall(r'data-target="source-(\d+)"[^>]*>([^<]+)<', html)
        tab_map = {int(i): self._clean(n) for i, n in tabs}

        # 按面板切分
        parts = re.split(r'<div class="source-panel"[^>]*id="source-(\d+)"', html)
        froms, urls = [], []
        i = 1
        while i < len(parts) - 1:
            idx = int(parts[i])
            panel = parts[i + 1]
            eps = re.findall(r'href="(/vodplay/[^"]+)"[^>]*>\s*([^<]+)<', panel)
            items, seen = [], set()
            for href, label in eps:
                if href in seen:
                    continue
                seen.add(href)
                items.append("%s$%s" % (self._clean(label) or ("第%d集" % (len(items) + 1)), href))
            if items:
                froms.append(tab_map.get(idx, "线路%d" % (idx + 1)))
                urls.append("#".join(items))
            i += 2

        if not urls:
            return {"list": []}
        return {"list": [{
            "vod_id": vid, "vod_name": name, "vod_pic": pic,
            "vod_year": year, "vod_area": area, "vod_director": director,
            "vod_content": desc,
            "vod_play_from": "$$$".join(froms),
            "vod_play_url": "$$$".join(urls),
        }]}

    def playerContent(self, flag, id, vipFlags):
        # id = /vodplay/{vid}-{playFrom}-{index}.html
        m = re.search(r'/vodplay/(\d+)-([^-]+)-(\d+)\.html', str(id))
        if not m:
            return {"parse": 1, "url": str(id)}
        vid, play_from, index = m.group(1), m.group(2), m.group(3)
        data = self._api("/api/play-url?vodId=%s&playFrom=%s&index=%s" % (vid, play_from, index),
                         ref="%s/vodplay/%s-%s-%s.html" % (self.host, vid, play_from, index))
        url = data.get("url") or ""
        if url.startswith("http"):
            return {"parse": 0, "url": url, "header": {"User-Agent": UA, "Referer": self.host + "/"}}
        return {"parse": 1, "url": str(id)}

    def searchContent(self, key, quick, pg):
        html = self.fetch("%s/search?keyword=%s" % (self.host, quote(str(key))))
        out, seen = [], set()
        for m in re.finditer(r'<div class="search-item">([\s\S]*?)</div>\s*</div>\s*</div>', html):
            blk = m.group(1)
            a = re.search(r'href="(/detail/(\d+)\.html)"', blk)
            if not a:
                continue
            vid = a.group(2)
            if vid in seen:
                continue
            title = (re.search(r'class="search-item-title[^"]*">([^<]+)</a>', blk) or [None, ""])
            title = self._clean(title.group(1)) if hasattr(title, "group") else ""
            img = (re.search(r'<img[^>]+src="([^"]+)"', blk) or [None, ""])
            pic = img.group(1) if hasattr(img, "group") else ""
            typ = (re.search(r'class="search-item-type[^"]*">([^<]+)</span>', blk) or [None, ""])
            remarks = self._clean(typ.group(1)) if hasattr(typ, "group") else ""
            seen.add(vid)
            out.append({"vod_id": vid, "vod_name": title or vid,
                        "vod_pic": pic, "vod_remarks": remarks})
        return {"list": out, "page": int(pg or 1)}

    def localProxy(self, param):
        return None
