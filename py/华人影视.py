import re
import json
import requests
from urllib.parse import quote
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    def __init__(self):
        super().__init__()
        self.name = "华人影院"
        self.host = "https://huarw.com"
        self.header = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/150.0.0.0 Mobile",
            "Referer": self.host + "/",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.units = {
            "dianying": "电影",
            "dianshiju": "电视剧",
            "zongyi": "综艺",
            "dongman": "动漫",
            "duanju": "短剧"
        }
        self.class_map = {
            "dianying": ["喜剧片", "动作片", "剧情片", "爱情片", "科幻片", "恐怖片", "动画片", "战争片"],
            "dianshiju": ["国产剧", "欧美剧", "日本剧", "韩国剧", "海外剧"]
        }
        self.years = ["2026", "2025", "2024", "2023", "2022", "2021", "2020", "2019", "2018"]
        self.areas = ["大陆", "香港", "台湾", "美国", "法国", "英国", "日本", "韩国", "泰国", "印度", "其他"]
        self.langs = ["国语", "英语", "粤语", "韩语", "日语"]
        self.areas_tv = ["大陆", "香港", "台湾", "美国", "日本", "韩国", "泰国", "其他"]
        self.arts = ["大陆", "日本", "欧美"]

    def init(self, extend=""):
        try:
            if extend:
                cfg = json.loads(extend)
                if cfg.get("host"):
                    self.host = str(cfg.get("host")).rstrip("/")
                    self.header["Referer"] = self.host + "/"
        except Exception:
            pass

    def getName(self):
        return self.name

    def isVideoFormat(self, url):
        if not url:
            return False
        return bool(re.search(r'\.(m3u8|mp4|ts|flv)(\?|$)', url)) or 'm3u8' in url

    def isTextFormat(self, url):
        return False

    def localProxy(self, param):
        return {}

    def fix_url(self, u):
        if not u:
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _get(self, path):
        url = path if path.startswith("http") else self.host + path
        for _ in range(2):
            try:
                r = requests.get(url, headers=self.header, timeout=20, verify=False)
                if r.status_code == 200 and r.text:
                    return r.text
            except Exception:
                continue
        return ""

    def _cards(self, html):
        cards = []
        seen = set()
        chunks = re.split(r'(?=class="public-list-box)', html)
        for c in chunks:
            if 'href="/movie/' not in c:
                continue
            try:
                mid = re.search(r'href="/movie/(\d+)"', c)
                if not mid:
                    continue
                mid = mid.group(1)
                if mid in seen:
                    continue
                nm = re.search(r'<h3>\s*<a[^>]*>([^<]+)</a>', c)
                if not nm:
                    nm = re.search(r'title="([^"]+)"', c)
                if not nm:
                    nm = re.search(r'alt="([^"]+?)封面图"', c)
                if not nm:
                    nm = re.search(r'class="slide-info-title hide">([^<]+)<', c)
                pc = re.search(r'data-src="(//[^"]+|https?://[^"]+)"', c)
                if not pc:
                    pc = re.search(r"background-image:\s*url\('([^']+)'", c)
                rm = re.search(r'public-list-prb[^>]*>\s*([^<]+?)\s*<', c)
                if not rm:
                    rm = re.search(r'cdn-data-src="(//[^"]+|https?://[^"]+)"', c)
                cards.append({
                    "vod_id": mid,
                    "vod_name": nm.group(1).strip() if nm else mid,
                    "vod_pic": self.fix_url(pc.group(1)) if pc else "",
                    "vod_remarks": rm.group(1).strip() if rm else ""
                })
                seen.add(mid)
            except Exception:
                continue
        return cards

    def homeContent(self, filter):
        cates = [{"type_id": k, "type_name": v} for k, v in self.units.items()]
        html = self._get("/type/dianying")
        cards = self._cards(html)[:24]
        return {"class": cates, "list": cards, "filters": self._filters()}

    def homeVideoContent(self):
        html = self._get("/type/dianying")
        return {"list": self._cards(html)[:12]}

    def _filters(self):
        fs = {}
        for tid, cname in self.units.items():
            vals = [{"n": "全部", "v": ""}]
            for c in self.class_map.get(tid, []):
                vals.append({"n": c, "v": c})
            flt = [{"key": "class", "name": "分类", "value": vals}]
            flt.append({"key": "year", "name": "年份",
                        "value": [{"n": "全部", "v": ""}] + [{"n": y, "v": y} for y in self.years]})
            ar = self.arts if tid == "dongman" else (self.areas_tv if tid != "dianying" else self.areas)
            flt.append({"key": "area", "name": "地区",
                        "value": [{"n": "全部", "v": ""}] + [{"n": a, "v": a} for a in ar]})
            flt.append({"key": "lang", "name": "语言",
                        "value": [{"n": "全部", "v": ""}] + [{"n": l, "v": l} for l in self.langs]})
            flt.append({"key": "by", "name": "排序", "value": [
                {"n": "最新", "v": "time"}, {"n": "最热", "v": "hits"}, {"n": "评分", "v": "score"}]})
            fs[tid] = flt
        return fs

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        extend = extend or {}
        keys = []
        if extend.get("class"):
            keys.append(("class", extend["class"]))
        if extend.get("year"):
            keys.append(("year", extend["year"]))
        if extend.get("area"):
            keys.append(("area", extend["area"]))
        if extend.get("lang"):
            keys.append(("lang", extend["lang"]))
        if keys:
            path = "/search"
            for k, v in keys:
                path += "/%s/%s" % (k, quote(str(v)))
            if extend.get("by"):
                path += "/by/%s" % extend["by"]
            path += "/page/%d" % pg
        else:
            path = "/type/%s/page/%d" % (tid, pg)
        cards = self._cards(self._get(path))
        if keys:
            pagecount = pg if len(cards) < 10 else pg + 1
            total = pg * 10
        else:
            pagecount = 1
            total = len(cards)
        return {"list": cards, "page": pg, "pagecount": pagecount,
                "limit": 20, "total": total}

    def detailContent(self, ids):
        mid = str(ids[0]).split('-')[0]
        html = self._get("/movie/%s" % mid)
        vod = {"vod_id": mid, "vod_name": mid, "vod_pic": "", "vod_remarks": "",
               "vod_year": "", "vod_area": "", "vod_actor": "", "vod_director": "",
               "vod_content": "", "type_name": ""}
        try:
            nm = re.search(r'<h1 class="seo-h1">([^<]+)</h1>', html)
            if nm:
                vod["vod_name"] = nm.group(1).strip()
            pc = re.search(r'(?:data-src|src)="(//[^"]+|https?://[^"]+/upload/vod/[^"]+)"', html)
            if pc:
                vod["vod_pic"] = self.fix_url(pc.group(1))
            yr = re.search(r'href="/search/year/(\d{4})"', html)
            if yr:
                vod["vod_year"] = yr.group(1)
            ar = re.search(r'href="/search/area/([^"]+)"', html)
            if ar:
                vod["vod_area"] = __import__("urllib.parse", fromlist=["unquote"]).unquote(ar.group(1))
            cl = re.search(r'href="/show/13/class/([^"]+)"', html)
            if cl:
                vod["type_name"] = __import__("urllib.parse", fromlist=["unquote"]).unquote(cl.group(1))
            rm = re.search(r'备注\s*:\s*([^<]{1,24})', html)
            if rm:
                vod["vod_remarks"] = rm.group(1).strip()
            dr = re.search(r'导演\s*:\s*([^/]{1,60})/', html)
            if dr:
                vod["vod_director"] = dr.group(1).strip()
            ac = re.search(r'演员\s*:\s*([^<]{1,200})', html)
            if ac:
                vod["vod_actor"] = ac.group(1).strip()
            de = re.search(r'id="height_limit"[^>]*>([^<]{10,2000})<', html)
            if de:
                vod["vod_content"] = de.group(1).strip()
            ld = re.search(r'"description"\s*:\s*"([^"]{10,2000})"', html)
            if not vod["vod_content"] and ld:
                vod["vod_content"] = ld.group(1)
        except Exception:
            pass
        tabs = []
        for m in re.finditer(r'<a class="swiper-slide">\s*(?:<i[^>]*></i>)?\s*&nbsp;?([^<]+?)\s*<span class="badge">(\d+)</span>\s*</a>', html):
            tabs.append(m.group(1).strip())
        if not tabs:
            for m in re.finditer(r'<a class="swiper-slide"><i class="fa[^"]*"></i>&nbsp;([^<]+?)<span', html):
                tabs.append(m.group(1).strip())
        lines = {}
        order = []
        for m in re.finditer(r'<div class="anthology-list-box[^"]*">([\s\S]*?)(?=<div class="anthology-list-box|<div class="anthology|$)', html):
            blk = m.group(1)
            eps = re.findall(r'href="/play/(\d+-\d+-\d+)"[^>]*>\s*([^<]+?)\s*</a>', blk)
            if not eps:
                continue
            ln = sorted(set(x[0].split('-')[1] for x in eps))[0]
            order.append(ln)
            lines[ln] = eps
        if not order:
            eps = re.findall(r'href="/play/(\d+-\d+-\d+)"[^>]*>\s*([^<]+?)\s*</a>', html)
            if eps:
                ln = sorted(set(x[0].split('-')[1] for x in eps))[0]
                order = [ln]
                lines[ln] = eps
        froms = []
        urls = []
        for i, ln in enumerate(order):
            nm = tabs[i] if i < len(tabs) else ("线路%d" % (i + 1))
            nm = nm.strip() or ("线路%d" % (i + 1))
            eps = lines[ln]
            seen = set()
            seg = []
            for pid, en in eps:
                if pid in seen:
                    continue
                seen.add(pid)
                seg.append("%s$%s" % (en.strip(), pid))
            froms.append(nm)
            urls.append("#".join(seg))
        vod["vod_play_from"] = "$$$".join(froms)
        vod["vod_play_url"] = "$$$".join(urls)
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        path = "/search/wd/%s" % quote(str(key))
        if pg > 1:
            path += "/page/%d" % pg
        cards = self._cards(self._get(path))
        return {"list": cards, "page": pg,
                "pagecount": pg if len(cards) < 10 else pg + 1,
                "limit": 10, "total": pg * 10}

    def playerContent(self, flag, id, vipFlags):
        pid = str(id)
        html = self._get("/play/%s" % pid)
        url = ""
        frm = ""
        try:
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*;?\s*</script>', html, re.S)
            if m:
                d = json.loads(re.sub(r',(\s*[}\]])', r'\1', m.group(1)))
                url = str(d.get("url") or "")
                frm = str(d.get("from") or "")
        except Exception:
            pass
        if not url:
            return {"parse": 1, "playUrl": "", "url": self.host + "/play/" + pid, "jx": 0,
                    "header": {"User-Agent": self.header["User-Agent"], "Referer": self.host + "/"}}
        return {"parse": 0, "playUrl": "", "url": url, "jx": 0,
                "header": {"User-Agent": self.header["User-Agent"], "Referer": self.host + "/"}}
