# -*- coding: utf-8 -*-
# 一起影视 AppYQK TVBox/Drpy 源 (type 3)
# 站点: https://yzy0916.n0z6fkpuk.com (yqk1.app APP)
import base64, hashlib, json, random, string, time, uuid
from collections import OrderedDict
import urllib.request, urllib.parse

try:
    from base.spider import Spider as BaseSpider
except Exception:
    class BaseSpider:
        pass

class Spider(BaseSpider):
    HOST = "https://yzy0916.n0z6fkpuk.com"
    APP = "e6ddefe09e0349739874563459f56c54"
    KEY = "3359de478f8d45638125e446a10ec541"

    # 首页分类 (channelId -> 分类名), 短剧/体育被 Java 原版跳过
    CH = [("2", "电影"), ("3", "电视剧"), ("8", "动漫"),
          ("10", "综艺"), ("56", "高清韩剧")]

    def init(self, extend=""):
        pass

    def getName(self):
        return "一起影视"

    # ── 签名 POST ─────────────────────────────
    def _req(self, path, extra):
        # LinkedHashMap order is signature-sensitive.
        if "channelId" in extra:
            order = [("appId", self.APP), ("channelId", extra["channelId"]), ("cus1tom", "aabbcc"), ("deviceInfo", "Android")]
            tail = {}
        elif "keyword" in extra:
            order = [("appId", self.APP), ("cus1tom", "aabbcc"), ("deviceInfo", "Android"), ("keyword", extra["keyword"]), ("nextCount", extra.get("nextCount", "15"))]
            tail = {}
        elif "epId" in extra:
            order = [("appId", self.APP), ("cus1tom", "aabbcc"), ("deviceInfo", "Android"), ("epId", extra["epId"])]
            tail = {k: v for k, v in extra.items() if k != "epId"}
        elif "vodEpId" in extra:
            order = [("appId", self.APP), ("cus1tom", "aabbcc"), ("deviceInfo", "Android")]
            tail = {"vodEpId": extra["vodEpId"]}
        else:
            order = [("appId", self.APP), ("cus1tom", "aabbcc"), ("deviceInfo", "Android")]
            tail = dict(extra)
        order += [("reqDomain", "yqk1.app"), ("requestId", "".join(random.choice(string.ascii_letters + string.digits) for _ in range(32))), ("udid", str(uuid.uuid4()) + "-" + format(int(time.time() * 1000), "016x")), ("version", "1.2.7.104")]
        order += [(k, v) for k, v in tail.items() if k not in ("reqDomain", "requestId", "udid", "version")]
        x = OrderedDict(order)
        x["appKey"] = self.KEY
        raw = "&".join("%s=%s" % (k, v) for k, v in x.items())
        x.pop("appKey")
        x["sign"] = hashlib.md5(raw.encode()).hexdigest()
        req = urllib.request.Request(
            self.HOST + path,
            data=json.dumps(x, separators=(",", ":")).encode(),
            headers={
                "User-Agent": "Dart/3.1 (dart:io)",
                "Origin": "https://yqk1.app",
                "Referer": "https://yqk1.app/",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            return json.load(urllib.request.urlopen(req, timeout=15))
        except Exception:
            return {}

    @staticmethod
    def _card(x):
        return {
            "vod_id": str(x.get("vodId", x.get("id", ""))),
            "vod_name": x.get("vodName", x.get("title", "")),
            "vod_pic": x.get("coverImg", x.get("appCoverUrl", "")),
            "vod_remarks": x.get("remark", x.get("updateRemark", "")) or "",
        }

    # ── 接口 ──────────────────────────────────
    def homeContent(self, filter):
        return {"class": [{"type_id": a, "type_name": b} for a, b in self.CH],
                "list": []}

    def homeVideoContent(self):
        return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        x = self._req("/v2/api/channel/topicListView", {"channelId": int(tid)})
        out, seen = [], set()
        for t in ((x.get("data") or {}).get("topicList") or []):
            for v in (t.get("vodList") or []):
                c = self._card(v)
                if c["vod_id"] and c["vod_id"] not in seen:
                    seen.add(c["vod_id"])
                    out.append(c)
        return {"list": out, "page": int(pg or 1),
                "pagecount": 2 if out else 1,
                "limit": len(out) or 1, "total": len(out)}

    def detailContent(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids).split(",")[0]
        d = (self._req("/v2/api/vodInfo/index", {"vodId": vid}).get("data") or {})
        fs, us = [], []
        for pl in (d.get("playerList") or []):
            eps = []
            for ep in (pl.get("epList") or []):
                eps.append("%s$%s|%s|%s" % (
                    ep.get("epName", "正片"), ep.get("epId"),
                    d.get("vodName", ""), len(eps)))
            if eps:
                fs.append(pl.get("playerName", "线路"))
                us.append("#".join(eps))
        if not fs:
            return {"list": []}
        return {"list": [{
            "vod_id": vid,
            "vod_name": d.get("vodName", vid),
            "vod_pic": d.get("coverImg", ""),
            "vod_year": str(d.get("year", "")),
            "vod_area": d.get("areaName", ""),
            "vod_actor": "",
            "vod_content": d.get("intro", ""),
            "vod_play_from": "$$$".join(fs),
            "vod_play_url": "$$$".join(us),
        }]}

    def playerContent(self, flag, id, vipFlags):
        # id 格式: epId|vodName|epIndex
        ep = str(id).split("|")[0]
        # 1) 先查可播清晰度 (Java: /vodInfo/epDetail 过滤 canPlay)
        x = self._req("/v2/api/vodInfo/epDetail", {"vodEpId": ep})
        res = ""
        for r in ((x.get("data") or []) if isinstance(x.get("data"), list) else []):
            if str(r.get("canPlay", "")).lower() == "true":
                res = str(r.get("vodResolution", ""))
                break
        # 2) 取播放地址: epId 必须紧跟 deviceInfo 之后(签名顺序敏感)
        p = {"epId": ep}
        if res:
            p["vodResolution"] = res
        y = self._req("/v2/api/vodInfo/playUrl", p)
        data = y.get("data") or {}
        u = data.get("playUrl", "") if isinstance(data, dict) else ""
        return {"parse": 0 if u.startswith("http") else 1,
                "playUrl": "", "url": u or id, "jx": 0,
                "header": {"Referer": "https://yqk1.app/", "User-Agent": "Dart/3.1 (dart:io)"}}

    def searchContent(self, key, quick, pg):
        x = self._req("/v1/api/search/search", {"keyword": key, "nextCount": "15"})
        out = []
        for v in ((x.get("data") or {}).get("items") or []):
            if "短剧" not in (v.get("flags") or ""):
                out.append(self._card(v))
        return {"list": out, "page": int(pg or 1), "pagecount": 1,
                "limit": len(out) or 1, "total": len(out)}

    def isVideoFormat(self, url):
        return any(s in str(url).lower() for s in (".m3u8", ".mp4"))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return ""
