# -*- coding: utf-8 -*-
import json
import re
from urllib.parse import quote, urljoin

import requests
from lxml import etree
from base.spider import Spider


class Spider(Spider):
    def getName(self): return "Gimy影视"

    def init(self, extend=""):
        self.host = "https://gimytv.biz"
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": self.host + "/"}
        self.classes = [{"type_id": "2", "type_name": "电视剧"}, {"type_id": "4", "type_name": "动漫"}, {"type_id": "3", "type_name": "综艺"}, {"type_id": "1", "type_name": "电影"}, {"type_id": "25", "type_name": "短剧"}]
        subtypes = {
            "1": [("全部", "1"), ("动作片", "6"), ("喜剧片", "7"), ("爱情片", "8"), ("科幻片", "9"), ("恐怖片", "10"), ("剧情片", "11"), ("战争片", "12"), ("动画电影", "24")],
            "2": [("全部", "2"), ("陆剧", "13"), ("短剧", "25"), ("韩剧", "15"), ("美剧", "16"), ("日剧", "20"), ("台剧", "14"), ("海外剧", "21"), ("港剧", "22"), ("纪录片", "23")],
            "3": [("全部", "3")], "4": [("全部", "4")], "25": [("全部", "25")]
        }
        years = [{"n": "全部", "v": ""}] + [{"n": str(x), "v": str(x)} for x in range(2026, 2015, -1)]
        sorts = [{"n": "最新更新", "v": "time"}, {"n": "最新上架", "v": "time_add"}, {"n": "周人气", "v": "hits_week"}, {"n": "总人气", "v": "hits"}]
        self.filters = {tid: [{"key": "type", "name": "类型", "value": [{"n": n, "v": v} for n, v in values]}, {"key": "year", "name": "年份", "value": years}, {"key": "by", "name": "排序", "value": sorts}] for tid, values in subtypes.items()}

    def _get(self, url, sid=""):
        try:
            headers = dict(self.headers)
            if sid: headers["Cookie"] = "sid=" + str(sid)
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "utf-8"
            return response.text
        except Exception:
            return ""

    def _fix(self, url): return urljoin(self.host + "/", url or "")

    def _parse_list(self, html):
        if not html: return []
        tree, result, seen = etree.HTML(html), [], set()
        for node in tree.xpath('//a[contains(concat(" ",normalize-space(@class)," ")," video-pic ") and contains(@href,"/voddetail/")]'):
            match = re.search(r"/voddetail/(\d+)\.html", node.get("href", ""))
            if not match or match.group(1) in seen: continue
            seen.add(match.group(1))
            name = node.get("title") or "".join(node.xpath('.//img/@alt')).strip()
            pic = node.get("data-original") or node.get("data-src") or node.get("data-lazyload") or "".join(node.xpath('.//img/@data-original | .//img/@data-src | .//img/@src'))
            remark = "".join(node.xpath('.//*[contains(@class,"note")]//text()')).strip()
            result.append({"vod_id": match.group(1), "vod_name": name.strip(), "vod_pic": self._fix(pic), "vod_remarks": remark})
        return result

    def _pagecount(self, tree, page):
        values = [int(x) for x in tree.xpath('//a[contains(@href,"/vodshow/")]/@href') for x in re.findall(r"-(\d+)---", x)]
        return max(values + [page])

    def homeContent(self, filter): return {"class": self.classes, "list": self._parse_list(self._get(self.host + "/")), "filters": self.filters}

    def categoryContent(self, tid, pg, filter, extend):
        page, ext = max(1, int(pg or 1)), extend if isinstance(extend, dict) else {}
        selected, year, by = str(ext.get("type") or tid), str(ext.get("year") or ""), str(ext.get("by") or "time")
        url = f"{self.host}/vodshow/{selected}--{by}------{page}---{year}.html"
        html = self._get(url)
        tree = etree.HTML(html) if html else etree.HTML("<html/>")
        videos = self._parse_list(html)
        return {"page": page, "pagecount": self._pagecount(tree, page), "limit": len(videos), "total": self._pagecount(tree, page) * max(len(videos), 1), "list": videos}

    def detailContent(self, ids):
        result = []
        for vid in ids:
            html = self._get(f"{self.host}/voddetail/{vid}.html")
            if not html: continue
            tree = etree.HTML(html)
            name = "".join(tree.xpath('//h1/text()')).strip() or "".join(tree.xpath('//h2/text()')).strip()
            pic = "".join(tree.xpath('//meta[@property="og:image"]/@content | //div[contains(@class,"detail-pic")]//img/@data-original | //div[contains(@class,"detail-pic")]//img/@src'))
            content = " ".join(x.strip() for x in tree.xpath('//span[contains(@class,"detail-intro")]//text() | //div[contains(@class,"details-content-all")]//text()') if x.strip())
            sources, playlists = [], []
            panels = tree.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," playlist-mobile ")]')
            for panel in panels:
                episodes = panel.xpath('.//ul//a[contains(@href,"/video/")]')
                if not episodes: continue
                source = "".join(panel.xpath('./li[1]//text()')).strip() or "".join(panel.xpath('./span[1]//text()')).strip() or f"线路{len(sources) + 1}"
                plays = []
                for episode in episodes:
                    href = episode.get("href", "")
                    sid_match = re.search(r"sid=(\d+)", href)
                    onclick_match = re.search(r"changeSid\(['\"]?(\d+)", episode.get("onclick", ""))
                    sid = (onclick_match or sid_match).group(1) if onclick_match or sid_match else "1"
                    path = href.split("#", 1)[0]
                    label = "".join(episode.xpath(".//text()")).strip() or str(len(plays) + 1)
                    plays.append(f"{label}${path}@@{sid}")
                sources.append(source)
                playlists.append("#".join(plays))
            result.append({"vod_id": str(vid), "vod_name": name, "vod_pic": self._fix(pic), "vod_content": content, "vod_play_from": "$$$".join(sources), "vod_play_url": "$$$".join(playlists)})
        return {"list": result}

    def searchContent(self, key, quick, pg="1"):
        page = max(1, int(pg or 1))
        url = f"{self.host}/vodsearch/-------------.html?wd={quote(key)}&page={page}"
        return {"page": page, "pagecount": page, "list": self._parse_list(self._get(url))}

    def playerContent(self, flag, id, vipFlags):
        path, sid = (id.rsplit("@@", 1) + ["1"])[:2] if "@@" in id else (id, "1")
        url = self._fix(path)
        html = self._get(url, sid)
        marker = "var player_aaaa="
        if marker in html:
            try:
                data = json.JSONDecoder().raw_decode(html.split(marker, 1)[1])[0]
                play_url = data.get("url", "")
                if int(data.get("encrypt", 0)) == 1: play_url = quote(play_url, safe=":/?&=%")
                if play_url and any(x in play_url.lower() for x in (".m3u8", ".mp4", ".flv")):
                    return {"parse": 0, "url": play_url, "header": {"User-Agent": self.headers["User-Agent"], "Referer": url}}
            except Exception:
                pass
        return {"parse": 1, "url": url, "header": {**self.headers, "Cookie": "sid=" + sid}}
