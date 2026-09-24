# coding: utf-8
# =============================================================
# 站点信息（法则24 沉淀 / 换站只改这几行）
#   站名   : 顶一顶娇娃（成人影视站，自定义 CMS 模板 "mangguo"）
#   主域   : https://ding-yi-ding-jiao-wa.dingyidingjiaowa1.click
#   发布页 : 无（走 canonical 主域 301 探测 + 兜底，法则18）
#   内容型 : 未加密 m3u8 直链（flashvars.video_url），含广告分片需过滤
#   说明   : 抓取/拉流均无需 cookie/referer，实测无防盗链
#   验证于 : 2026-09-23
# =============================================================
import re
import sys
from urllib.parse import quote, urljoin, unquote, urlparse

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):

    # ---- 站点常量（法则17/18：只动态域名，分类静态） ----
    MAIN = "https://ding-yi-ding-jiao-wa.dingyidingjiaowa1.click"
    FALLBACK_HOSTS = [
        "https://ding-yi-ding-jiao-wa.dingyidingjiaowa1.click",
    ]

    def __init__(self):
        # __init__ 只做本地初始化，禁止网络（法则16）
        self._host = ""          # 探测后的落地域缓存
        self.extend = ""
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Mobile Safari/537.36",
            "Referer": self.MAIN + "/",
        }
        # 分类静态硬编码（法则16/17）
        self.classes = [
            {"type_id": "latest", "type_name": "最新"},
            {"type_id": "popular", "type_name": "最热"},
            {"type_id": "avmingxing", "type_name": "AV明星"},
            {"type_id": "zhongwenzimu", "type_name": "中文字幕"},
            {"type_id": "guochan", "type_name": "国产情色"},
            {"type_id": "renbenwuma", "type_name": "日本无码"},
            {"type_id": "oumeifengqing", "type_name": "欧美风情"},
            {"type_id": "gangtai", "type_name": "港台伦理"},
            {"type_id": "jingxuan", "type_name": "精品推荐"},
            {"type_id": "wangbo", "type_name": "网红主播"},
            {"type_id": "lingjiarenqi", "type_name": "邻家人妻"},
            {"type_id": "changtui", "type_name": "长腿丝袜"},
            {"type_id": "hanguo", "type_name": "韩国伦理"},
        ]
        self.filters = {}

    # ---------------- 基础接口 ----------------
    def getName(self):
        return "顶一顶娇娃"

    def getDependence(self):
        return []

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(x in u for x in (".m3u8", ".mp4", ".flv", ".ts"))

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def init(self, extend=""):
        # init 必须零网络（法则16）；域名探测懒加载到 site_host()
        self.extend = extend or ""

    # ---------------- 域名探测（法则18） ----------------
    def site_host(self):
        """canonical 主域 301 探测 + 列表页特征校验 + 兜底不空，结果缓存。"""
        if self._host:
            return self._host
        candidates = [self.MAIN] + [h for h in self.FALLBACK_HOSTS if h != self.MAIN]
        for cand in candidates:
            host = self._resolve_host(cand)
            if host:
                self._host = host
                return self._host
        # 探测全失败也绝不返回空串（法则18 保底不空）
        self._host = self.MAIN
        return self._host

    def _resolve_host(self, base):
        try:
            r = self.fetch(base + "/videos/", headers=self.headers, timeout=15)
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            final = str(getattr(r, "url", "") or base)
            # 落地域取 scheme://host
            pr = urlparse(final)
            host = "%s://%s" % (pr.scheme, pr.netloc) if pr.netloc else base
            txt = getattr(r, "text", "") or ""
            # 用列表页真实内容特征校验，防落地空壳页
            if '<div class="item"' in txt and re.search(r"/video/\d+/", txt):
                return host
        except Exception:
            return ""
        return ""

    def _get(self, url):
        """统一 GET，判 200 再返回文本（快速排错：fetch 失败返回 None）。"""
        try:
            r = self.fetch(url, headers=self.headers, timeout=15)
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            txt = getattr(r, "text", "") or ""
            return txt if len(txt) > 200 else txt
        except Exception as e:
            self.log("fetch fail %s: %s" % (url, type(e).__name__))
            return ""

    # ---------------- 首页（零网络） ----------------
    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        host = self.site_host()
        html = self._get(host + "/videos/")
        return {"list": self._parse_cards(html, host)}

    # ---------------- 列表解析 ----------------
    _RE_ITEM = re.compile(r'<div class="item">(.*?)</div>\s*</div>', re.S)
    _RE_HREF = re.compile(r'href="[^"]*?/video/(\d+)/"')
    _RE_TITLE = re.compile(r'title="([^"]+)"')
    _RE_PIC = re.compile(r'data-original="([^"]+)"')
    _RE_DUR = re.compile(r'class="duration">([^<]+)<')

    def _parse_cards(self, html, host):
        if not html:
            return []
        out = []
        # 以卡片起始标记切分，稳妥截取到下一张卡片之前
        blocks = re.split(r'<div class="item">', html)
        for blk in blocks[1:]:
            m_id = self._RE_HREF.search(blk)
            if not m_id:
                continue
            vid = m_id.group(1)
            m_t = self._RE_TITLE.search(blk)
            title = m_t.group(1).strip() if m_t else ("视频" + vid)
            m_p = self._RE_PIC.search(blk)
            pic = m_p.group(1).strip() if m_p else ""
            m_d = self._RE_DUR.search(blk)
            remark = m_d.group(1).strip() if m_d else ""
            # 打包 id|$|name|$|pic，详情阶段可直接取用
            packed = "|$|".join([vid, title, pic])
            out.append({
                "vod_id": packed,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        return out

    def _max_page(self, html, path_prefix):
        """从分页链接提取最大页数；path_prefix 如 /videos/ 或 /videos/categories/guochan/。"""
        if not html:
            return 1
        esc = re.escape(path_prefix.rstrip("/"))
        nums = re.findall(esc + r'/(\d+)/', html)
        pages = [int(n) for n in nums if n.isdigit()]
        return max(pages) if pages else 1

    # ---------------- 分类列表 ----------------
    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        if page < 1:
            page = 1
        host = self.site_host()
        tid = str(tid or "latest")

        if tid == "latest":
            prefix = "/videos/"
            url = host + "/videos/" if page == 1 else host + "/videos/%d/" % page
        elif tid == "popular":
            prefix = "/mostpopular-videos/"
            url = host + "/mostpopular-videos/" if page == 1 else host + "/mostpopular-videos/%d/" % page
        else:
            prefix = "/videos/categories/%s/" % tid
            url = host + prefix if page == 1 else host + prefix + "%d/" % page

        html = self._get(url)
        vlist = self._parse_cards(html, host)
        pagecount = self._max_page(html, prefix)
        if pagecount < page:
            pagecount = page
        return {
            "list": vlist,
            "page": page,
            "pagecount": pagecount,
            "limit": 8,
            "total": pagecount * 8,
        }

    # ---------------- ids 归一化（法则35） ----------------
    @staticmethod
    def _norm_ids(ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            if not ids:
                return ""
            ids = ids[0]
        if isinstance(ids, bytes):
            ids = ids.decode("utf-8", errors="ignore")
        return str(ids).strip()

    def _skeleton(self, packed, title="", pic="", remarks="解析中"):
        """法则35：详情兜底骨架，禁止返回空 list。play_url 用数字 id 让 playerContent 再抢救。"""
        vid = str(packed).split("|$|")[0]
        return {"list": [{
            "vod_id": packed,
            "vod_name": title or "未知标题",
            "vod_pic": pic or "",
            "vod_remarks": remarks,
            "vod_content": "",
            "vod_play_from": "顶一顶娇娃",
            "vod_play_url": "正片$" + vid,
        }]}

    # ---------------- 详情 ----------------
    _RE_VURL = re.compile(r"video_url:\s*'([^']+)'")
    _RE_PREVIEW = re.compile(r"preview_url:\s*'([^']+)'")
    _RE_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.S)
    _RE_TITLE_TAG = re.compile(r'<title>(.*?)</title>', re.S)
    _RE_DESC = re.compile(r'name="description"\s+content="([^"]*)"')

    def detailContent(self, ids):
        raw = self._norm_ids(ids)      # L0：唯一允许返回空 list 的分支
        if not raw:
            return {"list": []}
        ps = raw.split("|$|")
        vid = ps[0]
        old_name = ps[1] if len(ps) > 1 else ""
        old_pic = ps[2] if len(ps) > 2 else ""

        host = self.site_host()
        page_url = host + "/video/%s/" % vid
        html = self._get(page_url)
        if not html or len(html) < 500:
            # 请求失败也返回骨架（法则35，禁止空 list）
            return self._skeleton(raw, old_name, old_pic)

        try:
            # 标题：h1 > title(去站名后缀) > 列表旧值
            title = old_name
            m = self._RE_H1.search(html)
            if m:
                t = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                if t:
                    title = t
            if not title:
                m = self._RE_TITLE_TAG.search(html)
                if m:
                    t = m.group(1).strip()
                    t = re.sub(r"-顶一顶娇娃\s*$", "", t).strip()
                    if t:
                        title = t
            if not title:
                title = "视频" + vid

            # 封面：preview_url > 列表旧图
            pic = old_pic
            m = self._RE_PREVIEW.search(html)
            if m and m.group(1).strip():
                pic = m.group(1).strip()

            # 简介
            desc = ""
            m = self._RE_DESC.search(html)
            if m:
                desc = m.group(1).strip()

            # m3u8 直链
            m = self._RE_VURL.search(html)
            m3u8 = m.group(1).strip() if m else ""

            # 播放 ID：优先直链（parse:0 秒播）；无直链则回退数字 id 让 playerContent 抢救
            play_id = m3u8 if m3u8 else vid

            vod = {
                "vod_id": raw,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "",
                "vod_content": desc,
                "vod_play_from": "顶一顶娇娃",
                "vod_play_url": "正片$" + play_id,
            }
            return {"list": [vod]}
        except Exception as e:
            self.log("detail exception %s: %s" % (vid, type(e).__name__))
            return self._skeleton(raw, old_name, old_pic)

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            page = int(pg or 1)
        except Exception:
            page = 1
        host = self.site_host()
        kw = quote(str(key or ""), safe="")
        url = host + "/search/%s/" % kw if page == 1 else host + "/search/%s/%d/" % (kw, page)
        html = self._get(url)
        return {"list": self._parse_cards(html, host), "page": page}

    # ---------------- 播放 ----------------
    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "")
        host = self.site_host()

        # 情况1：直接就是 m3u8/直链
        if ".m3u8" in pid.lower():
            return {"parse": 0, "url": self._m3u8_proxy_url(pid), "header": self._play_headers()}
        if re.match(r"^https?://", pid, re.I) and self.isVideoFormat(pid):
            return {"parse": 0, "url": pid, "header": self._play_headers()}

        # 情况2：数字 id（骨架兜底路径）→ 抓详情页提取 m3u8
        if pid.isdigit():
            html = self._get(host + "/video/%s/" % pid)
            m = self._RE_VURL.search(html or "")
            if m:
                real = m.group(1).strip()
                if ".m3u8" in real.lower():
                    return {"parse": 0, "url": self._m3u8_proxy_url(real), "header": self._play_headers()}
                return {"parse": 0, "url": real, "header": self._play_headers()}

        # 情况3：兜底降级（法则5/32：url 非空 + 带 UA/Referer）
        fallback = pid if re.match(r"^https?://", pid, re.I) else (host + "/video/%s/" % pid)
        return {"parse": 1, "url": fallback, "header": self._play_headers()}

    def _play_headers(self):
        return {"User-Agent": self.headers["User-Agent"], "Referer": self.site_host() + "/"}

    def _m3u8_proxy_url(self, url):
        """有广告分片（实测确认），走 localProxy 过滤（法则30）。"""
        return self.getProxyUrl() + "&url=" + quote(str(url or ""), safe="")

    # ---------------- 本地代理：m3u8 广告过滤 ----------------
    def localProxy(self, param):
        target = unquote(str((param or {}).get("url", "") or ""))
        if not re.match(r"^https?://", target, re.I):
            return [400, "text/plain", b"invalid url"]
        try:
            res = self.fetch(target, headers={"User-Agent": self.headers.get("User-Agent", "")}, timeout=15)
            if not res or getattr(res, "status_code", 0) != 200:
                return [502, "text/plain", b"m3u8 fetch failed"]
            raw = getattr(res, "content", b"") or b""
            text = raw.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                return [502, "text/plain", b"invalid m3u8"]
            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
        except Exception as e:
            self.log("m3u8 proxy error: %s" % type(e).__name__)
            return [500, "text/plain", b"m3u8 proxy error"]

    def _clean_m3u8(self, text, source_url):
        """五层清洗：主表透传 / 众数目录锚点 / 分片成对过滤 / 冗余标签清理 / 全滤兜底。"""
        lines = [ln.strip() for ln in str(text or "").replace("\r", "").split("\n") if ln.strip()]
        if not lines:
            return "#EXTM3U\n"

        # Ⅱ 多码率主表：子流改代理地址
        if any(ln.startswith("#EXT-X-STREAM-INF") for ln in lines):
            out = []
            for ln in lines:
                if ln.startswith("#"):
                    out.append(ln)
                else:
                    child = urljoin(source_url, ln)
                    out.append(self._m3u8_proxy_url(child) if ".m3u8" in child.lower() else child)
            return "\n".join(out) + "\n"

        # 先收集所有分片的绝对地址与其目录，求众数目录作正片锚点（法则30 Ⅲ）
        seg_dirs = {}
        seg_urls = []  # (index_in_lines, abs_url)
        for i, ln in enumerate(lines):
            if ln.startswith("#"):
                continue
            media = urljoin(source_url, ln)
            d = "/".join(urlparse(media).path.split("/")[:-1])
            seg_dirs[d] = seg_dirs.get(d, 0) + 1
            seg_urls.append((i, media))
        content_dir = ""
        if seg_dirs:
            content_dir = max(seg_dirs.items(), key=lambda kv: kv[1])[0]

        # Ⅳ 分片过滤：EXTINF 与分片成对丢弃
        out = []
        pending = []
        removed = 0
        kept = 0
        for ln in lines:
            if ln.startswith("#EXTINF"):
                pending = [ln]
                continue
            if pending and ln.startswith("#"):
                pending.append(ln)
                continue
            if pending:
                media = urljoin(source_url, ln)
                d = "/".join(urlparse(media).path.split("/")[:-1])
                if content_dir and d != content_dir:
                    removed += 1
                else:
                    out.extend(pending)
                    out.append(media)   # 绝对地址交播放器直连
                    kept += 1
                pending = []
                continue
            # 非分片标签
            out.append(self._rewrite_tag(ln, source_url))

        # Ⅴ 全滤兜底：误杀过半或全灭则整体回退不过滤
        if removed > 0 and (kept == 0 or removed > kept):
            self.log("m3u8 清洗回退：removed=%d kept=%d" % (removed, kept))
            out = []
            for ln in lines:
                out.append(self._rewrite_tag(ln, source_url))
            return "\n".join(out) + "\n"

        # 冗余标签清理（连续 DISCONTINUITY / KEY:NONE 去重）
        dedup = []
        for ln in out:
            if ln in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                if dedup and dedup[-1] == ln:
                    continue
            dedup.append(ln)
        while len(dedup) > 1 and dedup[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            dedup.pop()
        if removed:
            self.log("m3u8 已过滤广告分片: %d" % removed)
        return "\n".join(dedup) + "\n"

    def _rewrite_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(m):
                return 'URI="' + urljoin(source_url, m.group(1)) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            return urljoin(source_url, line)
        return line
