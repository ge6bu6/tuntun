#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import re
import json
import base64
import html as html_lib
import urllib.request
import urllib.parse
import http.cookiejar
import gzip
import zlib
import ssl

try:
    from base.spider import Spider as SpiderBase
except ImportError:
    class SpiderBase(object):
        pass


class Spider(SpiderBase):
    def __init__(self):
        super(Spider, self).__init__()
        self.domains = [
            "https://m.tangttiao.cc",
            "https://tangttiao.cc"
        ]
        self.currentDomain = self.domains[0]
        self.tgGroup = "https://t.me/tvshare23"
        self.brandActor = "🦋 TG群: @tvshare23"
        self.brandDirector = "🦋 蝴蝶影视"
        self._ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"

        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        try:
            self.ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        except Exception:
            pass

        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj),
            urllib.request.HTTPSHandler(context=self.ctx)
        )

        self.cats = [
            ("home", "精选"),
            ("cate3", "顶级网黄"), ("cate4", "福利姬"), ("cate5", "主播勾引"),
            ("cate6", "传媒精选"), ("cate7", "JVID"), ("cate8", "锅锅酱"),
            ("cate9", "巨乳大奶"), ("cate10", "抖音风"), ("cate11", "制服诱惑"),
            ("cate12", "樱花小猫"), ("cate13", "反差女友"), ("cate14", "探花约炮"),
            ("cate15", "调教性奴"), ("cate16", "ASMR"), ("cate17", "颜值网红"),
            ("cate18", "高潮自慰"), ("cate19", "欧美洋马"), ("cate20", "露出野战"),
            ("cate21", "SWAG"), ("cate22", "热门吃瓜"), ("cate23", "绿帽淫妻"),
            ("cate24", "群交滥交"), ("cate25", "风骚少妇"), ("cate26", "逆天乱伦"),
            ("cate27", "AI女神"), ("cate28", "风骚母狗"), ("cate29", "断袖男同"),
            ("cate30", "原创短剧"), ("cate31", "足交口爆"), ("cate32", "炮桶小屋"),
            ("cate33", "无套内射"), ("cate34", "黑鬼长屌"), ("cate35", "女同百合"),
            ("cate36", "伪娘人妖"), ("cate37", "吴梦梦"), ("cate39", "umate原创"),
            ("cate40", "Naomii"), ("cate41", "YuiPeach"), ("cate42", "唐伯虎"),
            ("cate43", "饼干姐姐"), ("cate44", "台北娜娜"), ("cate45", "MASKU"),
            ("cate46", "Xreind"), ("cate47", "小桃酱"), ("cate48", "安安小晗"),
            ("cate49", "柚子猫"), ("cate50", "王梨奈"), ("cate51", "辛尤里"),
            ("cate52", "粉色情人"), ("cate53", "阿朱"), ("cate54", "奶咪"),
            ("cate55", "有根棒棒"), ("cate56", "不见星空"), ("cate57", "Kitty"),
            ("cate58", "妮可"), ("cate59", "Cos女神"), ("cate60", "玩偶姊姊"),
            ("cate61", "司雨"), ("cate62", "谭晓彤"), ("cate63", "刘玥"),
            ("cate64", "Vivian"), ("cate65", "多乙"), ("cate66", "朱可儿"),
            ("cate67", "周大萌"), ("cate69", "麻豆传媒"), ("cate70", "蜜桃传媒"),
            ("cate71", "葫芦影业"), ("cate72", "香蕉视频"), ("cate73", "兔子先生"),
            ("cate74", "OnlyFans"), ("cate75", "91制片厂"), ("cate76", "ED Mosaic"),
            ("cate77", "IBiZa Media"), ("cate78", "SA国际传媒"), ("cate79", "乌托邦"),
            ("cate80", "大象传媒"), ("cate81", "天美传媒"), ("cate82", "扣扣传媒"),
            ("cate83", "性视界"), ("cate84", "星空传媒"), ("cate85", "映秀传媒"),
            ("cate86", "杏吧原版"), ("cate87", "果冻传媒"), ("cate88", "爱神传媒"),
            ("cate89", "爱豆传媒"), ("cate90", "精东影业"), ("cate91", "糖心Vlog"),
            ("cate92", "萝莉社"), ("cate94", "桥本香菜"), ("cate95", "米菲兔"),
            ("cate96", "捅主任"), ("cate97", "npxvip"), ("cate98", "Andm"),
            ("cate99", "liburin"), ("cate100", "谭晓彤"), ("cate101", "小水水"),
            ("cate102", "小鸟酱"), ("cate103", "HAMAR"), ("cate104", "铃木美子"),
            ("cate105", "占星猫"), ("cate106", "芋圆呀"), ("cate107", "小丁妹妹"),
            ("cate108", "米娜学姐"), ("cate109", "米胡桃"), ("cate110", "萌白酱"),
            ("cate111", "麻酥酥"), ("cate112", "白桃少女"), ("cate113", "八月未央"),
            ("cate115", "网红大瓜"), ("cate116", "校园猛料"), ("cate117", "大奶孕妇"),
            ("cate118", "独家泄密"), ("cate119", "热门吃瓜"), ("cate120", "潜规则"),
            ("cate121", "反差泄露"), ("cate122", "裸贷风波"), ("cate123", "轮奸呀"),
            ("cate124", "饥渴新娘"), ("cate125", "强奸醉奸"), ("cate126", "迷奸"),
            ("cate128", "AnnyWalker"), ("cate129", "MilaAzul"), ("cate130", "Comatozze"),
            ("cate131", "Honey"), ("cate132", "Luxury"), ("cate133", "kittyxk"),
            ("cate134", "JennyKitty"), ("cate135", "LeoLulu"), ("cate136", "PurpleB"),
            ("cate137", "MilaLioness"), ("cate138", "Pinklov"), ("cate139", "PornForce"),
            ("cate140", "Shinaryen"), ("cate141", "EvaElfie"), ("cate142", "Candy"),
            ("cate143", "Kenzie"), ("cate144", "CarlaCu"), ("cate145", "webto"),
            ("cate146", "SiaSib"), ("cate148", "沈先生"), ("cate149", "赵总寻花"),
            ("cate150", "小天探花"), ("cate151", "换妻探花"), ("cate152", "七天探花"),
            ("cate153", "千人斩"), ("cate154", "午夜尋花"), ("cate155", "91大神"),
            ("cate156", "按摩会所"), ("cate157", "韩国嫖妓"), ("cate158", "陈先生"),
            ("cate159", "太子寻花"), ("cate160", "翼屌寻花"), ("cate161", "小宝寻花"),
            ("cate162", "文轩探花"), ("cate164", "兄妹情深"), ("cate165", "最爱岳母"),
            ("cate166", "淫荡儿媳"), ("cate167", "淫乱父女"), ("cate168", "照顾小侄女"),
            ("cate169", "师生恋情"), ("cate170", "母子情深"), ("cate171", "姐弟爱恋"),
            ("cate172", "调教嫂子"), ("cate173", "照顾小姨子"), ("cate175", "韩国三级"),
            ("cate176", "香港三级"), ("cate177", "台湾三级"), ("cate178", "欧洲情色"),
            ("cate179", "俄乌色情"), ("cate180", "越南菲律宾"), ("cate181", "印度情色"),
            ("cate182", "日本三级"), ("cate183", "美国色情"), ("cate184", "东南亚情色"),
            ("cate186", "多人淫交"), ("cate187", "车震直播"), ("cate188", "日韩主播"),
            ("cate189", "户外直播"), ("cate190", "抖音网红"), ("cate191", "主播勾引"),
            ("cate192", "快手网红"), ("cate193", "对着你"), ("cate194", "AVOVE"),
            ("cate195", "MISSWAEM"), ("cate196", "妖骚蛇姬"), ("cate197", "大啵啵"),
            ("cate198", "虎牙辣妹"), ("cate200", "古装诱惑"), ("cate201", "萝莉塔"),
            ("cate202", "空姐诱惑"), ("cate203", "丝袜诱惑"), ("cate204", "职场OL"),
            ("cate205", "清涩校服"), ("cate206", "三点泳装"), ("cate207", "JK短裙"),
            ("cate208", "女仆装"), ("cate209", "护士打针"), ("cate210", "国风旗袍"),
            ("cate211", "体操运动"), ("cate212", "其他制服"), ("cate214", "骑兵精选"),
            ("cate215", "高清优质"), ("cate216", "FC2高清"), ("cate217", "VR视觉"),
            ("cate218", "人妻巨乳"), ("cate219", "少女制服"), ("cate220", "药物迷奸"),
            ("cate221", "强暴系列"), ("cate222", "轮奸系列"), ("cate223", "筱田佑"),
            ("cate224", "森澤佳奈"), ("cate225", "三上悠亜"), ("cate226", "AkihoYoshizawa"),
            ("cate227", "神宮寺奈緒"), ("cate228", "藤森里穗"), ("cate229", "松本一香"),
            ("cate230", "乙爱丽丝"), ("cate231", "沙月芽衣"), ("cate232", "姬咲華"),
            ("cate233", "AliceOtsu"), ("cate234", "佐山愛"), ("cate235", "水果解說"),
            ("cate237", "推荐观看"), ("cate238", "颜值少女"), ("cate239", "网红洋马"),
            ("cate240", "CandyLove"), ("cate241", "丝袜制服"), ("cate242", "欧美剧情"),
            ("cate243", "AngelX"), ("cate244", "商场性交"), ("cate245", "情色按摩"),
            ("cate246", "捷克搭讪"), ("cate247", "肤若凝脂"), ("cate248", "SweetieFox"),
            ("cate249", "Morgpie"), ("cate250", "DianRider"), ("cate251", "BadCuteGirl"),
            ("cate252", "Ailish"), ("cate253", "SamanthaFlair"), ("cate254", "滥交群交"),
            ("cate255", "巨乳少女"), ("cate256", "黑人大屌"), ("cate258", "深夜保健室"),
            ("cate259", "王竹子教学"), ("cate260", "中指通一下"), ("cate261", "Misa米砂"),
            ("cate262", "小哥哥艾理"), ("cate263", "Dr.She"), ("cate264", "1G老湿"),
            ("cate265", "两性知识"), ("cate266", "麻豆综艺"), ("cate267", "户外搭讪"),
            ("cate268", "性爱大秀"), ("cate269", "女优训练营"), ("cate270", "情趣k歌房"),
            ("cate271", "小鹏奇啪行"), ("cate272", "性爱自修室"), ("cate273", "女神体育祭"),
            ("cate274", "屁孩日记"), ("cate275", "薇傲的性趣"), ("cate276", "一三蜜桃说"),
            ("cate277", "Carrie雨千"), ("cate279", "喜剧片"), ("cate280", "古装片"),
            ("cate281", "武侠片"), ("cate282", "枪战片"), ("cate283", "灾难片"),
            ("cate284", "冒险片"), ("cate285", "犯罪片"), ("cate286", "科幻片"),
            ("cate287", "动作片"), ("cate288", "恐怖片")
        ]

    def init(self, extend=""):
        return {}

    def isVideoFormat(self, url):
        low = (url or "").lower()
        return any(k in low for k in (".m3u8", ".mp4", ".flv", ".mkv", ".avi", ".ts"))

    def manualVideoCheck(self):
        return False

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

    def _clean(self, s):
        if not s:
            return ""
        t = html_lib.unescape(str(s))
        t = re.sub(r'<[^>]+>', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    def _clean_url(self, raw_url):
        if not raw_url:
            return ""
        unquoted = urllib.parse.unquote(raw_url)
        parts = urllib.parse.urlsplit(unquoted)
        path = urllib.parse.quote(parts.path, safe="/:@&=+$,?#")
        query = urllib.parse.quote(parts.query, safe="/:@&=+$,?#")
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

    def _is_valid_html(self, html_text):
        if not html_text or len(html_text) < 200:
            return False
        block_keywords = ("发布页", "enter-link", "点击进入", "Just a moment...", "Attention Required")
        for kw in block_keywords:
            if kw in html_text:
                return False
        return True

    def _fetch_safe(self, path, referer="", headers_extra=None, raw_bytes=False):
        candidates = [self.currentDomain] + [d for d in self.domains if d != self.currentDomain]

        for domain in candidates:
            if path.startswith("http://") or path.startswith("https://"):
                target_url = self._clean_url(path)
            else:
                target_url = self._clean_url(domain + path if path.startswith("/") else (domain + "/" + path))

            headers = {
                "User-Agent": self._ua,
                "Referer": referer if referer else (domain + "/"),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "close"
            }
            if headers_extra:
                headers.update(headers_extra)

            try:
                req = urllib.request.Request(target_url, headers=headers)
                with self.opener.open(req, timeout=12) as resp:
                    code = resp.getcode()
                    if code != 200:
                        continue

                    final_url = resp.geturl()
                    raw = resp.read()
                    if raw.startswith(b"\x1f\x8b"):
                        raw = gzip.decompress(raw)
                    elif getattr(resp, "headers", {}).get("Content-Encoding") == "deflate":
                        try:
                            raw = zlib.decompress(raw)
                        except Exception:
                            raw = zlib.decompress(raw, -zlib.MAX_WBITS)

                    if raw_bytes:
                        return {"code": code, "bytes": raw, "text": "", "err": ""}

                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        try:
                            text = raw.decode("gbk")
                        except Exception:
                            text = raw.decode("latin1", errors="ignore")

                    if not (path.startswith("http://") or path.startswith("https://")):
                        if not self._is_valid_html(text):
                            continue

                    parts = urllib.parse.urlsplit(final_url)
                    real_base = "%s://%s" % (parts.scheme, parts.netloc)
                    if real_base and real_base.startswith("http") and real_base != self.currentDomain:
                        self.currentDomain = real_base
                        if real_base not in self.domains:
                            self.domains.insert(0, real_base)

                    return {"code": code, "text": text, "bytes": raw, "err": ""}
            except Exception:
                continue

        return {"code": -1, "text": "", "bytes": b"", "err": "请求失败"}

    def _parse_cards(self, html_text):
        if not html_text or len(html_text) < 200:
            return []

        covers = {}
        for m in re.finditer(r'<img([^>]+)>', html_text):
            tag = m.group(1)
            cm = re.search(r'data-cover=["\'](https?://[^"\']+)["\']', tag)
            vm = re.search(r'img(\d{15,})', tag)
            if cm and vm:
                vid = vm.group(1)
                if vid[-1] in "0123456789" and len(vid) > 15:
                    base = vid[:-1]
                    if base not in covers:
                        covers[base] = cm.group(1)
                if vid not in covers:
                    covers[vid] = cm.group(1)

        video_list = []
        seen = set()

        for m in re.finditer(r'href=["\'](/video/(\d+)/)["\'][^>]*title=["\']([^"\']+)["\']', html_text):
            href = m.group(1)
            vid = m.group(2)
            title = self._clean(m.group(3))
            if vid in seen or not title or title in ("HD", "畅看"):
                continue
            seen.add(vid)

            pic = covers.get(vid) or covers.get(vid + "0") or ""
            if not pic:
                chunk = html_text[max(0, m.start() - 500):m.end() + 200]
                cm = re.search(r'data-cover=["\'](https?://[^"\']+)["\']', chunk)
                if cm:
                    pic = cm.group(1)

            video_list.append({
                "vod_id": self.currentDomain + href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "高清"
            })

        if video_list:
            return video_list

        for m in re.finditer(r'href=["\'](/video/(\d+)/)["\'][^>]*>([^<]{4,})', html_text):
            href = m.group(1)
            vid = m.group(2)
            title = self._clean(m.group(3))
            if vid in seen or not title or title in ("HD", "畅看"):
                continue
            seen.add(vid)
            pic = covers.get(vid) or ""
            video_list.append({
                "vod_id": self.currentDomain + href,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "高清"
            })

        return video_list

    def _extract_play(self, html_text):
        if not html_text:
            return ""

        m_url = re.search(r'data-url=["\']([^"\']+)["\']', html_text)
        m_cdn = re.search(r'data-cdnline=["\']([^"\']+)["\']', html_text)
        if m_url and m_cdn:
            path = m_url.group(1).strip()
            cdn = m_cdn.group(1).rstrip("/")
            if path.startswith("http"):
                return path
            return "%s%s" % (cdn, path)

        for u in re.findall(r'["\']([^"\']+\.m3u8[^"\']*)["\']', html_text):
            u = html_lib.unescape(u)
            if u.startswith("http"):
                return u
            if u.startswith("/") and m_cdn:
                return "%s%s" % (m_cdn.group(1).rstrip("/"), u)

        return ""

    def homeContent(self, filter=False):
        classes = [{"type_id": c[0], "type_name": c[1]} for c in self.cats]
        res = self._fetch_safe("/")
        rec_list = self._parse_cards(res.get("text", ""))

        return {
            "class": classes,
            "list": rec_list
        }

    def homeVideoContent(self):
        res = self._fetch_safe("/")
        return {"list": self._parse_cards(res.get("text", ""))}

    def categoryContent(self, tid, pg, filter=False, extend=None, *args, **kwargs):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        clean_slug = str(tid or "home").strip()

        if clean_slug in ("home", "0", ""):
            target_path = "/" if page_num <= 1 else "/%d/" % page_num
        else:
            target_path = "/category/%s/" % clean_slug if page_num <= 1 else "/category/%s/%d/" % (clean_slug, page_num)

        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")
        vods = self._parse_cards(html_text)

        pages = 50
        if html_text and clean_slug not in ("home", "0", ""):
            ns = [int(x) for x in re.findall(r'/category/' + re.escape(clean_slug) + r'/(\d+)/', html_text)]
            if ns:
                pages = max(ns)

        return {
            "page": page_num,
            "pagecount": pages,
            "limit": 20,
            "total": pages * 20,
            "list": vods
        }

    def detailContent(self, ids):
        raw_id = self._list(ids)[0] if self._list(ids) else ""
        if not raw_id:
            return {"list": []}

        if raw_id.startswith("http://") or raw_id.startswith("https://"):
            target_url = raw_id
        else:
            target_url = self.currentDomain + (raw_id if raw_id.startswith("/") else "/" + raw_id)

        res = self._fetch_safe(target_url)
        html_text = res.get("text", "")
        if not html_text:
            return {"list": []}

        title = ""
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html_text)
        if not m:
            m = re.search(r'<title>(.*?)</title>', html_text)
        if m:
            title = self._clean(m.group(1).split("|")[0].split("_")[0])

        pic = ""
        pm = re.search(r'data-cover=["\'](https?://[^"\']+)["\']', html_text)
        if pm:
            pic = pm.group(1)

        real_stream = self._extract_play(html_text)
        final_stream = real_stream if real_stream else target_url

        custom_notice = "【💡 温馨提示：视频加载如遇卡顿请尝试切换线路或快进。】"
        group_info = "【🔥 官方交流群: %s】" % self.tgGroup
        vod_content = "%s\n\n%s\n\n【说明：本站持续为您搜集全网高清精彩视频，欢迎加入TG群获取最新资源！】" % (group_info, custom_notice)

        return {
            "list": [{
                "vod_id": raw_id,
                "vod_name": title or "精彩视频",
                "vod_pic": pic,
                "vod_actor": self.brandActor,
                "vod_director": self.brandDirector,
                "vod_remarks": "高清",
                "vod_content": vod_content,
                "vod_play_from": "官方专线",
                "vod_play_url": "正片$%s" % final_stream
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        url = str(id).strip()

        if not self.isVideoFormat(url) and not url.startswith("http"):
            res = self._fetch_safe(url)
            stream = self._extract_play(res.get("text", ""))
            if stream:
                url = stream

        play_headers = {
            "User-Agent": self._ua,
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

        return {
            "parse": 0,
            "playUrl": "",
            "url": url,
            "header": json.dumps(play_headers)
        }

    def searchContent(self, key, quick, pg="1"):
        try:
            page_num = max(1, int(str(pg).strip() or 1))
        except Exception:
            page_num = 1

        if not key:
            return {"list": []}

        kw = urllib.parse.quote(str(key).strip())
        target_path = "/search/%s/" % kw if page_num <= 1 else "/search/%s/%d/" % (kw, page_num)

        res = self._fetch_safe(target_path)
        html_text = res.get("text", "")
        vods = self._parse_cards(html_text)

        pages = page_num
        if html_text:
            ns = [int(x) for x in re.findall(r'/search/[^/]+/(\d+)/', html_text)]
            if ns:
                pages = max(ns)

        return {
            "page": page_num,
            "pagecount": max(pages, page_num),
            "limit": 20,
            "total": max(pages, page_num) * 20,
            "list": vods
        }