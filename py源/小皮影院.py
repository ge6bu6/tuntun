#!/usr/bin/python
# -*- coding: utf-8 -*-
import re, requests, urllib.parse
from lxml import etree
from base.spider import Spider

class Spider(Spider):
    def getName(self): return "小皮影院"
    def init(self, extend=""):
        self.host = "https://www.xptv.cc"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/"}
        self.categories = [
            {"type_id": "dianying", "type_name": "电影"},
            {"type_id": "dianshiju", "type_name": "电视剧"},
            {"type_id": "dongman", "type_name": "动漫"}
        ]
        self.filters = {
            "dianying": [
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "2021", "v": "2021"}, {"n": "2020", "v": "2020"}, {"n": "更早", "v": "1800-1979"}
                ]},
                {"key": "area", "name": "地区", "value": [
                    {"n": "全部", "v": ""}, {"n": "内地", "v": "%E5%86%85%E5%9C%B0"}, {"n": "中国香港", "v": "%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF"},
                    {"n": "中国台湾", "v": "%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE"}, {"n": "韩国", "v": "%E9%9F%A9%E5%9B%BD"}, {"n": "日本", "v": "%E6%97%A5%E6%9C%AC"},
                    {"n": "美国", "v": "%E7%BE%8E%E5%9B%BD"}, {"n": "法国", "v": "%E6%B3%95%E5%9B%BD"}, {"n": "英国", "v": "%E8%8B%B1%E5%9B%BD"},
                    {"n": "泰国", "v": "%E6%B3%B0%E5%9B%BD"}, {"n": "印度", "v": "%E5%8D%B0%E5%BA%A6"}, {"n": "其它", "v": "%E5%85%B6%E5%AE%83"}
                ]},
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "剧情", "v": "%E5%89%A7%E6%83%85"}, {"n": "喜剧", "v": "%E5%96%9C%E5%89%A7"}, {"n": "爱情", "v": "%E7%88%B1%E6%83%85"},
                    {"n": "动作", "v": "%E5%8A%A8%E4%BD%9C"}, {"n": "犯罪", "v": "%E7%8A%AF%E7%BD%AA"}, {"n": "惊悚", "v": "%E6%83%8A%E6%82%9A"}, {"n": "悬疑", "v": "%E6%82%AC%E7%96%91"},
                    {"n": "科幻", "v": "%E7%A7%91%E5%B9%BB"}, {"n": "恐怖", "v": "%E6%81%90%E6%80%96"}, {"n": "奇幻", "v": "%E5%A5%87%E5%B9%BB"}, {"n": "冒险", "v": "%E5%86%92%E9%99%A9"},
                    {"n": "古装", "v": "%E5%8F%A4%E8%A3%85"}, {"n": "动画", "v": "%E5%8A%A8%E7%94%BB"}, {"n": "传记", "v": "%E4%BC%A0%E8%AE%B0"}, {"n": "纪录", "v": "%E7%BA%AA%E5%BD%95"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "按时间", "v": "time"}, {"n": "按热度", "v": "hits"}, {"n": "按评分", "v": "score"}
                ]}
            ],
            "dianshiju": [
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "更早", "v": "1800-1979"}
                ]},
                {"key": "area", "name": "地区", "value": [
                    {"n": "全部", "v": ""}, {"n": "内地", "v": "%E5%86%85%E5%9C%B0"}, {"n": "中国香港", "v": "%E4%B8%AD%E5%9B%BD%E9%A6%99%E6%B8%AF"},
                    {"n": "中国台湾", "v": "%E4%B8%AD%E5%9B%BD%E5%8F%B0%E6%B9%BE"}, {"n": "韩国", "v": "%E9%9F%A9%E5%9B%BD"}, {"n": "日本", "v": "%E6%97%A5%E6%9C%AC"},
                    {"n": "美国", "v": "%E7%BE%8E%E5%9B%BD"}, {"n": "其它", "v": "%E5%85%B6%E5%AE%83"}
                ]},
                {"key": "class", "name": "类型", "value": [
                    {"n": "全部", "v": ""}, {"n": "剧情", "v": "%E5%89%A7%E6%83%85"}, {"n": "喜剧", "v": "%E5%96%9C%E5%89%A7"}, {"n": "爱情", "v": "%E7%88%B1%E6%83%85"},
                    {"n": "动作", "v": "%E5%8A%A8%E4%BD%9C"}, {"n": "犯罪", "v": "%E7%8A%AF%E7%BD%AA"}, {"n": "悬疑", "v": "%E6%82%AC%E7%96%91"},
                    {"n": "古装", "v": "%E5%8F%A4%E8%A3%85"}, {"n": "历史", "v": "%E5%8E%86%E5%8F%B2"}, {"n": "战争", "v": "%E6%88%98%E4%BA%89"},
                    {"n": "动画", "v": "%E5%8A%A8%E7%94%BB"}, {"n": "纪录", "v": "%E7%BA%AA%E5%BD%95"}
                ]},
                {"key": "by", "name": "排序", "value": [
                    {"n": "按时间", "v": "time"}, {"n": "按热度", "v": "hits"}, {"n": "按评分", "v": "score"}
                ]}
            ],
            "dongman": [
                {"key": "year", "name": "年份", "value": [
                    {"n": "全部", "v": ""}, {"n": "2026", "v": "2026"}, {"n": "2025", "v": "2025"}, {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"}, {"n": "2022", "v": "2022"}, {"n": "更早", "v": "1800-1979"}
                ]},
                {"key": "isend", "name": "状态", "value": [
                    {"n": "全部", "v": ""}, {"n": "完结", "v": "%E5%AE%8C%E7%BB%93"}, {"n": "连载", "v": "%E8%BF%9E%E8%BD%BD"}
                ]}
            ]
        }
    def _get(self, url):
        try:
            r = requests.get(url, headers=self.headers, timeout=8)
            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except: return None
    def _fix(self, u):
        if not u: return ""
        if u.startswith("//"): return "https:" + u
        if u.startswith("/"): return self.host + u
        if u.startswith("http"): return u
        return ""
    def _parse_list(self, text):
        if not text: return []
        tree = etree.HTML(text); res, seen = [], set()
        for a in tree.xpath('//a[contains(@href,"/v/")]'):
            try:
                h = a.get("href", "") or ""
                m = re.search(r"/v/(\d+)\.html", h)
                if not m or m.group(1) in seen: continue
                seen.add(m.group(1))
                t = "".join(a.xpath('.//h3/text()')).strip() or a.get("title", "") or ""
                imgs = a.xpath('.//img')
                p = ""
                if imgs:
                    for attr in ["data-original", "data-src", "src"]:
                        p = imgs[0].get(attr, "") or ""
                        if p: break
                res.append({"vod_id": m.group(1), "vod_name": t, "vod_pic": self._fix(p)})
            except: continue
        return res
    def homeContent(self, filter):
        h = self._get(self.host + "/")
        return {"class": self.categories, "list": self._parse_list(h) if h else [], "filters": self.filters}
    def categoryContent(self, tid, pg, filter, extend):
        parts = []
        if extend:
            for k in ["year", "area", "class", "by", "isend"]:
                v = (extend.get(k, "") or "").strip()
                if v: parts.append(f"{k}/{v}")
        if parts:
            url = self.host + f"/show/{tid}/" + "/".join(parts) + ("/page/" + pg if pg != "1" else "") + ".html"
        else:
            url = self.host + f"/show/{tid}.html" if pg == "1" else self.host + f"/show/{tid}/page/{pg}.html"
        h = self._get(url)
        if not h: return {"page": int(pg), "pagecount": 99, "limit": 24, "total": 999, "list": []}
        tree = etree.HTML(h)
        pc = 1
        for x in tree.xpath('//div[contains(@class,"font-mono")]//text()'):
            if "/" in x:
                try: pc = int(x.split("/")[-1].strip()); break
                except: pass
        return {"page": int(pg), "pagecount": pc, "limit": 24, "total": 999, "list": self._parse_list(h)}
    def detailContent(self, ids):
        res = {"list": []}
        for vid in ids:
            try:
                h = self._get(f"{self.host}/v/{vid}.html")
                if not h: continue
                tree = etree.HTML(h)
                name = "".join(tree.xpath('//h1/text()')).strip()
                pic = self._fix("".join(tree.xpath('//main//img[1]/@src')))
                grids = tree.xpath('//div[contains(@class,"playlist-grid")]')
                if not grids:
                    grids = tree.xpath('//div[contains(@class,"playlist")]//div[contains(@class,"grid")]')
                srcs, eps = [], []
                for grid in grids:
                    items = grid.xpath('.//a[contains(@href,"/p/")]')
                    el = [f'{"".join(a.xpath(".//text()")).strip()}${self._fix(a.get("href",""))}' for a in items]
                    if el: srcs.append(f"节点{len(srcs)+1}" if len(grids) > 1 else "云播"); eps.append("#".join(el))
                if not srcs:
                    items = tree.xpath('//a[contains(@href,"/p/")]')
                    el = list(dict.fromkeys([f'{"".join(a.xpath(".//text()")).strip()}${self._fix(a.get("href",""))}' for a in items]))
                    if el: srcs.append("云播"); eps.append("#".join(el))
                res["list"].append({"vod_id": vid, "vod_name": name, "vod_pic": pic, "vod_play_from": "$$$".join(srcs), "vod_play_url": "$$$".join(eps)})
            except: continue
        return res
    def searchContent(self, key, quick, pg="1"):
        return {"list": [], "page": int(pg)}
    def playerContent(self, flag, id, vipFlags):
        url = id if id.startswith("http") else self._fix(id)
        try:
            h = self._get(url)
            if h and 'var player_aaaa=' in h:
                p = h.find('var player_aaaa=') + len('var player_aaaa=')
                depth, end, i = 0, p, p
                while i < len(h):
                    if h[i] == '{': depth += 1
                    elif h[i] == '}':
                        depth -= 1
                        if depth == 0: end = i + 1; break
                    i += 1
                import json
                data = json.loads(h[p:end])
                play_id = urllib.parse.unquote(data.get('url', ''))
                if data.get('from') == 'juhe' and play_id:
                    parse_url = 'https://api.apiimg.com/show/super.php?id=' + urllib.parse.quote(play_id, safe='=')
                    ph = self._get(parse_url)
                    if ph:
                        ms = re.findall(r'https?://[^"\'<>]+?\.(?:m3u8|mp4)[^"\'<>]*', ph, re.I)
                        ms += re.findall(r'https?:\\/\\/[^"\'<>]+?\.(?:m3u8|mp4)[^"\'<>]*', ph, re.I)
                        ms = list(dict.fromkeys([x.replace('\\/', '/') for x in ms if 'api.apiimg.com' not in x and 'playbg.php' not in x and x.lower().startswith('http')]))
                        if ms:
                            hd = {"User-Agent": self.headers["User-Agent"], "Referer": parse_url}
                            return {"parse": 0, "url": ms[0], "header": hd}
        except: pass
        return {"parse": 1, "url": url, "header": self.headers}