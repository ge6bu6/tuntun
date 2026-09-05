import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

class Spider:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
            "Accept-Encoding": "gzip, deflate",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Dest": "document",
        })
        self.cache = {}
        self.host = self._compute_host()
        self.cats = [
            {"type_id": "23", "type_name": "国产视频"},
            {"type_id": "25", "type_name": "国产传媒"},
            {"type_id": "72", "type_name": "国产大制作"},
            {"type_id": "86", "type_name": "中文剧情"},
            {"type_id": "91", "type_name": "剧情故事"},
            {"type_id": "87", "type_name": "燃烧荷尔蒙"},
            {"type_id": "36", "type_name": "网曝黑料"},
            {"type_id": "34", "type_name": "抖阴视频"},
            {"type_id": "38", "type_name": "AV解说"},
            {"type_id": "71", "type_name": "偷拍自拍"},
            {"type_id": "77", "type_name": "监控摄像头"},
            {"type_id": "74", "type_name": "嫖妓全过程"},
            {"type_id": "75", "type_name": "淫乱学生妹"},
            {"type_id": "76", "type_name": "黑料不打烊"},
            {"type_id": "84", "type_name": "少女破处"},
            {"type_id": "83", "type_name": "为国争光"},
            {"type_id": "26", "type_name": "日本有码"},
            {"type_id": "30", "type_name": "制服诱惑"},
            {"type_id": "35", "type_name": "女优明星"},
            {"type_id": "80", "type_name": "中文字幕"},
            {"type_id": "93", "type_name": "激情中字"},
            {"type_id": "37", "type_name": "伦理三级"},
            {"type_id": "81", "type_name": "成人综艺"},
            {"type_id": "27", "type_name": "日本无码"},
            {"type_id": "79", "type_name": "高清无码"},
            {"type_id": "29", "type_name": "强奸乱伦"},
            {"type_id": "73", "type_name": "乱伦毁三观"},
            {"type_id": "39", "type_name": "SM调教"},
            {"type_id": "89", "type_name": "重口味"},
            {"type_id": "85", "type_name": "人兽典藏"},
            {"type_id": "28", "type_name": "欧美无码"},
            {"type_id": "31", "type_name": "国产主播"},
            {"type_id": "45", "type_name": "韩国主播"},
            {"type_id": "78", "type_name": "主播网红"},
            {"type_id": "43", "type_name": "网红头条"},
            {"type_id": "33", "type_name": "明星换脸"},
            {"type_id": "41", "type_name": "极品媚黑"},
            {"type_id": "82", "type_name": "媚黑母狗"},
            {"type_id": "32", "type_name": "激情动漫"},
            {"type_id": "90", "type_name": "3D动漫"},
            {"type_id": "92", "type_name": "同人动漫"},
            {"type_id": "40", "type_name": "萝莉少女"},
            {"type_id": "42", "type_name": "女同性恋"},
            {"type_id": "88", "type_name": "女同口交"},
            {"type_id": "44", "type_name": "人妖系列"},
            {"type_id": "94", "type_name": "东南亚"},
            {"type_id": "46", "type_name": "VR视角"},
            {"type_id": "24", "type_name": "中文字幕"},
            {"type_id": "20", "type_name": "更多精彩"},
            {"type_id": "22", "type_name": "稀缺资源"},
        ]

    def _compute_host(self):
        base = datetime(2026, 2, 1, 17, 0, 0)
        now = datetime.now()
        cut = now.replace(hour=17, minute=0, second=0, microsecond=0)
        if now < cut:
            cut = cut - timedelta(days=1)
        diff = (cut - base).days
        num = 232 + diff
        cn_map = ['零', '壹', '贰', '叁', '肆', '伍', '陆', '柒', '捌', '玖']
        prefix = ''.join(cn_map[int(d)] for d in str(num))
        return f"https://{prefix}.avzxmf127.sbs"

    def getDependence(self):
        return ""

    def init(self, extend):
        try:
            if isinstance(extend, str):
                extend = json.loads(extend)
        except Exception:
            pass
        self._fetch(self.host + "/index.php/vod/show/id/26.html")

    def homeContent(self, filter):
        result = {}
        result["class"] = self.cats
        result["filters"] = {}
        vod_list, pagecount, total = self._parse_list(self.host + "/index.php/vod/show/id/26.html")
        result["list"] = vod_list
        return result

    def homeVideoContent(self):
        vod_list, pagecount, total = self._parse_list(self.host + "/index.php/vod/show/id/26.html")
        return {"page": 1, "pagecount": pagecount, "limit": 12, "total": total, "list": vod_list}

    def categoryContent(self, tid, pg, filter, extend):
        if int(pg) <= 1:
            url = f"{self.host}/index.php/vod/show/id/{tid}.html"
        else:
            url = f"{self.host}/index.php/vod/show/id/{tid}/page/{pg}.html"
        vod_list, pagecount, total = self._parse_list(url)
        return {"page": int(pg), "pagecount": pagecount, "limit": 12, "total": total, "list": vod_list}

    def detailContent(self, ids):
        vod_id = ids[0]
        detail_url = f"{self.host}/vodhtml/{vod_id}.html"
        play_url = f"{self.host}/vodplayhtml/{vod_id}/index_1_1.html"
        html = self._fetch(detail_url)
        vod = {"vod_id": vod_id, "vod_name": "", "vod_pic": "", "vod_remarks": "", "vod_play_from": "", "vod_play_url": ""}
        soup = BeautifulSoup(html, "lxml")
        title_tag = soup.find("title")
        if title_tag:
            t = title_tag.get_text(strip=True)
            t = re.sub(r"详情介绍.*$", "", t)
            t = re.sub(r"\s*-\s*$", "", t)
            vod["vod_name"] = t.strip()
        for a in soup.find_all("a", href=re.compile(r"/vodhtml/\d+\.html")):
            img = a.find("img")
            if img:
                src = img.get("data-original", "") or img.get("src", "")
                if src and not vod["vod_pic"]:
                    vod["vod_pic"] = src
                    break
        if not vod["vod_pic"]:
            for img in soup.find_all("img"):
                src = img.get("data-original", "") or img.get("src", "")
                if src and ("uqetyzxa.com" in src or "jkuntubrwjbe.com" in src or "kjbwhcnao.com" in src):
                    vod["vod_pic"] = src
                    break
        play_html = self._fetch(play_url)
        m = re.search(r'var player_aaaa\s*=\s*(\{.*?\})', play_html, re.DOTALL)
        real_url = ""
        src_from = "aosika"
        if m:
            try:
                pdata = json.loads(m.group(1))
                real_url = pdata.get("url", "")
                src_from = pdata.get("from", "aosika")
            except Exception:
                url_m = re.search(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                if url_m:
                    real_url = url_m.group(1).replace("\\/", "/")
        if real_url:
            vod["vod_play_from"] = src_from
            vod["vod_play_url"] = f"正片${real_url}"
        return {"list": [vod]}

    def searchContent(self, key, quick):
        return self._search(key, 1)

    def searchContentPage(self, key, pg):
        return self._search(key, pg)

    def _search(self, key, pg):
        enc = urllib.parse.quote(key)
        if int(pg) <= 1:
            url = f"{self.host}/index.php/vod/search.html?wd={enc}"
        else:
            url = f"{self.host}/index.php/vod/search/wd/{enc}/page/{pg}.html"
        vod_list, pagecount, total = self._parse_list(url)
        return {"page": int(pg), "pagecount": pagecount, "limit": 12, "total": total, "list": vod_list}

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "jx": 0, "url": id, "header": {"User-Agent": self.session.headers["User-Agent"], "Referer": self.host + "/"}, "format": "application/x-mpegURL"}

    def localProxy(self, param):
        try:
            if param.startswith("http"):
                url = param
            elif param.startswith("?"):
                qs = urllib.parse.parse_qs(param[1:])
                url = qs.get("url", [""])[0]
            else:
                url = param
            if not url:
                return [404, "text/plain", ""]
            resp = self.session.get(url, timeout=15, headers={"Referer": self.host + "/"})
            if resp.status_code == 200:
                ctype = resp.headers.get("Content-Type", "image/jpeg")
                return {"code": 200, "content": resp.content, "headers": {"Content-Type": ctype}}
        except Exception:
            pass
        return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        return True

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def destroy(self):
        self.cache.clear()

    def _fetch(self, url):
        if url in self.cache:
            return self.cache[url]
        try:
            resp = self.session.get(url, timeout=15)
            resp.encoding = resp.apparent_encoding or "utf-8"
            text = resp.text
            if len(self.cache) > 24:
                old_keys = list(self.cache.keys())[:8]
                for k in old_keys:
                    del self.cache[k]
            self.cache[url] = text
            return text
        except Exception:
            return ""

    def _parse_list(self, url):
        html = self._fetch(url)
        if not html:
            return [], 1, 0
        soup = BeautifulSoup(html, "lxml")
        vod_list = []
        seen_ids = set()
        boxes = soup.find_all("div", class_="stui-vodlist__box")
        for box in boxes:
            a_tag = box.find("a", href=re.compile(r"/vodhtml/\d+\.html"))
            if not a_tag:
                continue
            href = a_tag.get("href", "")
            m = re.search(r"/vodhtml/(\d+)\.html", href)
            if not m:
                continue
            vid = m.group(1)
            if vid in seen_ids:
                continue
            seen_ids.add(vid)
            title = a_tag.get("title", "") or a_tag.get_text(strip=True)
            pic = a_tag.get("data-original", "")
            if not pic:
                img = a_tag.find("img")
                if img:
                    pic = img.get("data-original", "") or img.get("src", "")
            vod_list.append({
                "vod_id": vid,
                "vod_name": title.strip(),
                "vod_pic": pic,
                "vod_remarks": "",
            })
        pagecount = 1
        total = len(vod_list)
        page_links = soup.find_all("a", href=re.compile(r"/page/\d+\.html"))
        max_p = 1
        for pl in page_links:
            pm = re.search(r"/page/(\d+)\.html", pl.get("href", ""))
            if pm:
                max_p = max(max_p, int(pm.group(1)))
        pagecount = max_p
        if pagecount > 1 and vod_list:
            total = pagecount * len(vod_list)
        return vod_list, pagecount, total
