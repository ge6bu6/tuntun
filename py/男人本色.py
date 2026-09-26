# coding: utf-8
# 男人本色 (nanrenbense) T3 爬虫  —  成人站，MacCMS 风格 HTML 模板 bense
# 站点信息（换站只改这两行 + classes）
import re
from urllib.parse import quote, unquote, urljoin

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # ================= 站点信息 =================
    HOST = "https://nanrenbense9325123.buzz"

    def __init__(self):
        # 法则16/17：__init__ 零网络，分类静态硬编码
        self.host = self.HOST
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.HOST + "/",
        }
        # 静态分类（type_id 取站点 /type/id/{tid}.html）
        self.classes = [
            {"type_id": "1144", "type_name": "最近更新"},
            {"type_id": "1143", "type_name": "本月最热"},
            {"type_id": "1142", "type_name": "收藏最多"},
            {"type_id": "1141", "type_name": "最近加精"},
            {"type_id": "1145", "type_name": "91原创"},
            {"type_id": "61", "type_name": "国产情色"},
            {"type_id": "1202", "type_name": "国产视频"},
            {"type_id": "1210", "type_name": "国产主播"},
            {"type_id": "69", "type_name": "网红主播"},
            {"type_id": "1254", "type_name": "酒店探花"},
            {"type_id": "1217", "type_name": "网曝黑料"},
            {"type_id": "1258", "type_name": "熟女少妇"},
            {"type_id": "79", "type_name": "邻家人妻"},
            {"type_id": "63", "type_name": "日本无码"},
            {"type_id": "65", "type_name": "日本有码"},
            {"type_id": "67", "type_name": "中文字幕"},
            {"type_id": "73", "type_name": "欧美情色"},
            {"type_id": "1207", "type_name": "欧美无码"},
            {"type_id": "75", "type_name": "国模私拍"},
            {"type_id": "77", "type_name": "长腿丝袜"},
            {"type_id": "1209", "type_name": "制服诱惑"},
            {"type_id": "1219", "type_name": "伦理三级"},
            {"type_id": "71", "type_name": "成人动漫"},
            {"type_id": "1211", "type_name": "激情动漫"},
            {"type_id": "1213", "type_name": "抖阴视频"},
            {"type_id": "1222", "type_name": "萝莉少女"},
            {"type_id": "1224", "type_name": "女同性恋"},
            {"type_id": "1221", "type_name": "SM调教"},
            {"type_id": "1229", "type_name": "VR视角"},
            {"type_id": "1326", "type_name": "AI短剧"},
        ]
        self.filters = {}

    # ================= 基础 =================
    def getName(self):
        return "男人本色"

    def getDependence(self):
        return []

    def init(self, extend=""):
        # 法则17：init 零网络
        self.extend = extend or ""

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return (".m3u8" in u) or u.endswith(".mp4")

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ================= 工具 =================
    _CARD_RE = re.compile(
        r'''class="video-pic[^"]*"[^>]*background:\s*url\('([^']*)'\)'''
        r'''[^>]*?href="/?info/(\d+)\.html"[^>]*?title="([^"]*)"'''
        r'''[^>]*>\s*<span class="note[^"]*">([^<]*)</span>''',
        re.S,
    )

    def _get(self, url):
        """统一 GET，返回文本；失败返回空串（法则4：走 self.fetch）"""
        try:
            full = url if url.startswith("http") else urljoin(self.host + "/", url.lstrip("/"))
            res = self.fetch(full, headers=self.headers)
            if not res:
                return ""
            txt = getattr(res, "text", None)
            if txt is None and getattr(res, "content", None):
                txt = res.content.decode("utf-8", errors="ignore")
            return txt or ""
        except Exception as e:
            self.log("fetch fail: " + str(e))
            return ""

    def _pack(self, vid, name, pic, remark):
        """列表阶段把字段打包进 vod_id，详情零网络直出（分隔符 |$|）"""
        return "%s|$|%s|$|%s|$|%s" % (vid, name or "", pic or "", remark or "")

    def _aa(self, token, pid=""):
        """线路B：GET /aa/{token} 取真链（须带 X-Requested-With: XMLHttpRequest）"""
        try:
            full = urljoin(self.host + "/", "aa/" + token)
            h = dict(self.headers)
            h["X-Requested-With"] = "XMLHttpRequest"
            h["Accept"] = "*/*"
            if pid:
                h["Referer"] = urljoin(self.host + "/", "play/%s.html" % pid)
            res = self.fetch(full, headers=h)
            if not res:
                return ""
            txt = getattr(res, "text", None)
            if txt is None and getattr(res, "content", None):
                txt = res.content.decode("utf-8", errors="ignore")
            txt = (txt or "").strip()
            # 前端会做 url.replace("amp;","")，这里一并还原
            txt = txt.replace("&amp;", "&").replace("amp;", "")
            if txt.startswith("//"):
                txt = "https:" + txt
            if txt.startswith("http") and (".m3u8" in txt.lower() or ".mp4" in txt.lower()):
                return txt
            return ""
        except Exception as e:
            self.log("aa fetch fail: " + str(e))
            return ""

    # ============ m3u8 去广告管线（内联，法则26：仅代理 m3u8 文本，分片改绝对交播放器直连） ============
    def _proxy_url(self, target):
        """把真实 m3u8 地址包装成本地代理地址；取不到 getProxyUrl 时回退直链。"""
        if not target:
            return target
        base = ""
        try:
            base = self.getProxyUrl() or ""
        except Exception:
            base = ""
        if not base:
            return target
        if base.endswith("?") or base.endswith("&"):
            sep = ""
        elif "?" in base:
            sep = "&"
        else:
            sep = "?"
        return base + sep + "url=" + quote(target, safe="") + "&type=m3u8"

    @staticmethod
    def _resolve_url(uri, base_url):
        if not uri:
            return ""
        if uri.startswith("http"):
            return uri
        if uri.startswith("//"):
            return "https:" + uri
        try:
            return urljoin(base_url, uri)
        except Exception:
            return uri

    def _abs_tag_uri(self, line, base_url):
        """把 #EXT-X-KEY / #EXT-X-MAP 里的 URI="..." 改成绝对 CDN 地址。
        相对 key URI 若不改绝对，播放器会按代理 base(127.0.0.1) 解析 → 取金钥 404 黑屏。"""
        m = re.search(r'URI="([^"]*)"', line)
        if not m or not m.group(1):
            return line
        absu = self._resolve_url(m.group(1), base_url)
        return line[:m.start(1)] + absu + line[m.end(1):]

    def _filter_m3u8(self, text, base_url, depth=0):
        """主表(多码率)拉平为单跳代理；媒体清单走分片过滤。"""
        if "#EXT-X-STREAM-INF" in text:
            return self._flatten_master(text, base_url, depth)
        return self._filter_media(text, base_url)

    def _flatten_master(self, text, base_url, depth=0):
        """主表拉平（single hop）：取首个子流绝对地址，直接抓该 media 清单过滤后回传。
        线路A(sysl2026)为 master→variant 两层，广告在 variant 层混插，故须拉平后过滤。"""
        if depth >= 2:
            return text if text.endswith("\n") else text + "\n"
        sub = ""
        for raw in text.split("\n"):
            s = raw.strip()
            if not s or s.startswith("#"):
                continue
            sub = self._resolve_url(s, base_url)
            break
        if not sub:
            return text if text.endswith("\n") else text + "\n"
        media = self._get(sub)
        if not media or "#EXTM3U" not in media:
            return text if text.endswith("\n") else text + "\n"
        return self._filter_m3u8(media, sub, depth + 1)

    def _filter_media(self, text, base_url):
        """媒体清单去广告：
        锚点 = KEY URI 目录优先（正片 AES-128 段），无 KEY 回退 m3u8 URL 目录（线路B无加密）；
        只留锚点目录前缀分片，EXTINF/DISCONTINUITY/BYTERANGE 与分片成对丢弃，分片改绝对；
        广告段(METHOD=NONE + 不同目录，如线路A的 9637kb/hls)被剔除；
        仅当 kept==0（正片一段不剩）才整体回退，避免误伤。"""
        lines = text.split("\n")
        base_dir = base_url.rsplit("/", 1)[0]
        anchor = ""
        for ln in lines:
            m = re.search(r'#EXT-X-KEY:[^\n]*URI="([^"]+)"', ln)
            if m:
                anchor = self._resolve_url(m.group(1), base_url).rsplit("/", 1)[0]
                break
        if not anchor:
            anchor = base_dir

        out = []
        buf = []
        removed = 0
        kept = 0
        kept_any = False
        for raw in lines:
            s = raw.strip()
            if not s:
                continue
            if s.startswith("#EXTINF") or s.startswith("#EXT-X-DISCONTINUITY") \
                    or s.startswith("#EXT-X-BYTERANGE") or s.startswith("#EXT-X-PROGRAM-DATE-TIME"):
                buf.append(s)
                continue
            if s.startswith("#"):
                if s.startswith("#EXT-X-KEY") or s.startswith("#EXT-X-MAP"):
                    s = self._abs_tag_uri(s, base_url)
                out.append(s)
                continue
            seg_abs = self._resolve_url(s, base_url)
            if seg_abs.startswith(anchor):
                for t in buf:
                    if (not kept_any) and t.startswith("#EXT-X-DISCONTINUITY"):
                        continue
                    out.append(t)
                out.append(seg_abs)
                kept += 1
                kept_any = True
            else:
                removed += 1
            buf = []

        if kept == 0 and removed > 0:
            return text if text.endswith("\n") else text + "\n"
        return "\n".join(out) + "\n"

    def _cards(self, html):
        """通用卡片解析 -> vod list"""
        out = []
        seen = set()
        for pic, vid, title, remark in self._CARD_RE.findall(html or ""):
            if vid in seen:
                continue
            seen.add(vid)
            title = re.sub(r"\s+", " ", (title or "").strip())
            remark = (remark or "").strip()
            out.append({
                "vod_id": self._pack(vid, title, pic, remark),
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    @staticmethod
    def _norm_ids(ids):
        # 法则35：ids 归一化，禁止裸 ids[0]
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    # ================= 首页/分类 =================
    def homeContent(self, filter):
        # 法则16：首页零网络
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐用站点首页最新
        html = self._get("/")
        return {"list": self._cards(html)}

    def categoryContent(self, tid, pg, filter, extend):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        # 分页 URL：/type/{tid}/{pg}（第1页也可用）
        html = self._get("/type/%s/%d" % (tid, page))
        cards = self._cards(html)
        # 尾页解析 pagecount：尾页链接 /type/{tid}/{N}
        pagecount = page + (1 if cards else 0)
        m = re.search(r"href='/type/%s/(\d+)'[^>]*>\s*尾页" % re.escape(str(tid)), html)
        if m:
            try:
                pagecount = int(m.group(1))
            except Exception:
                pass
        elif not cards:
            pagecount = page
        return {
            "list": cards,
            "page": page,
            "pagecount": pagecount,
            "limit": 16,
            "total": pagecount * 16,
        }

    # ================= 详情 =================
    def _skeleton(self, vid, title="", pic="", remark="解析中"):
        pid = str(vid).split("|$|")[0].replace("$", "|")
        return {"list": [{
            "vod_id": vid, "vod_name": title or "未知标题", "vod_pic": pic or "",
            "vod_remarks": remark, "vod_content": "",
            "vod_play_from": "正片", "vod_play_url": "正片$" + pid,
        }]}

    def detailContent(self, ids):
        raw = self._norm_ids(ids)
        if not raw:
            return {"list": []}
        try:
            ps = raw.split("|$|")
            vid = ps[0]
            name = ps[1] if len(ps) > 1 else ""
            pic = ps[2] if len(ps) > 2 else ""
            remark = ps[3] if len(ps) > 3 else ""
            # 缺标题/封面时才补抓详情页
            if not name or not pic:
                html = self._get("/info/%s.html" % vid)
                if html:
                    if not name:
                        m = re.search(r"资源名称：([^<]+)", html)
                        if m:
                            name = re.sub(r"\s+", " ", m.group(1).strip())
                    if not pic:
                        m = re.search(r'<a[^>]+href="/play/\d+\.html"[^>]*>\s*<img src="([^"]+)"', html)
                        if m:
                            pic = m.group(1)
            if not vid:
                return self._skeleton(raw, name, pic)
            vod = {
                "vod_id": raw,
                "vod_name": name or "视频",
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": name or "",
                "vod_play_from": "正片",
                # 单集格式：名称$播放ID，ID 用纯数字
                "vod_play_url": "正片$" + vid,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detail exception: " + str(e))
            return self._skeleton(raw)

    # ================= 搜索 =================
    def searchContent(self, key, quick, pg="1"):
        page = 1
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page <= 1:
            url = "/search/%s" % quote(key)
        else:
            # 分页：/search/{kw}/n/{pg}
            url = "/search/%s/n/%d" % (quote(key), page)
        html = self._get(url)
        return {"list": self._cards(html), "page": page}

    # ================= 播放 =================
    def playerContent(self, flag, id, vipFlags):
        pid = self._norm_ids(id)
        # 处理「名称$地址」历史格式：取 $ 后段
        if "$" in pid:
            pid = pid.split("$")[-1]

        # 已是直链
        if pid.startswith("http") and (".m3u8" in pid.lower() or pid.lower().endswith(".mp4")):
            return {"parse": 0, "url": pid, "header": {"User-Agent": self.headers["User-Agent"]}}

        # pid 为纯数字 -> 抓播放页解析 playUrl
        url = ""
        if re.fullmatch(r"\d+", pid or ""):
            html = self._get("/play/%s.html" % pid)
            # 线路A：内联 var playUrl='...index.m3u8'
            m = re.search(r"var\s+playUrl\s*=\s*['\"]([^'\"]+)['\"]", html)
            if m:
                url = m.group(1)
            else:
                # 线路B：iframe player_new*.html?id=https://{token}
                #   前端 AJAX GET /aa/{token}（须带 X-Requested-With）取真链
                mi = re.search(
                    r'''player[^"']*\.html\?id=https?://([^"'&\s]+)''', html
                )
                if mi:
                    token = mi.group(1).strip()
                    if token:
                        real = self._aa(token, pid)
                        if real:
                            url = real
                # 兜底：页面里直接出现的 m3u8/mp4
                if not url:
                    m2 = re.search(
                        r'''(https?:)?//[^\s'"]+\.(?:m3u8|mp4)[^\s'"]*''', html
                    )
                    if m2:
                        url = m2.group(0)

        if url:
            if url.startswith("//"):
                url = "https:" + url
            ua = self.headers["User-Agent"]
            # m3u8 走 localProxy 去广告（线路A sysl2026 前贴片/中插广告；线路B 无广告直接透传）；
            # mp4 直链无需过滤
            if ".m3u8" in url.lower():
                return {"parse": 0, "url": self._proxy_url(url),
                        "header": {"User-Agent": ua, "Referer": self.host + "/"}}
            return {"parse": 0, "url": url,
                    "header": {"User-Agent": ua, "Referer": self.host + "/"}}

        # 兜底：交盒子解析
        fallback = pid if pid.startswith("http") else urljoin(self.host + "/", "play/%s.html" % pid)
        return {"parse": 1, "url": fallback, "header": self.headers}

    def localProxy(self, param):
        """代理并清洗 m3u8：过滤广告分片、KEY/分片改绝对地址，交播放器直连 CDN（法则26）。"""
        try:
            url = ""
            if isinstance(param, dict):
                url = param.get("url") or param.get("u") or ""
            else:
                url = str(param or "")
            if not url:
                return [404, "text/plain", b""]
            if "%" in url:
                try:
                    url = unquote(url)
                except Exception:
                    pass
            text = self._get(url)
            if not text or "#EXTM3U" not in text:
                return [404, "text/plain", b""]
            cleaned = self._filter_m3u8(text, url)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception:
            return [404, "text/plain", b""]
