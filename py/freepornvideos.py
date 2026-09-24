# coding=utf-8
# !/usr/bin/python
"""
FongMi / TVBox T3 (type=3) 爬虫源
站点：FreePornVideos.XXX  https://www.freepornvideos.xxx
类型：KVS(Kernel Video Sharing) 成人聚合站（HTML 解析 + mp4 直链）
说明：
  - 列表卡片 <a class="thumb_title" href="/zh/videos/{id}/{slug}/">，缩略图 img.thumb
  - 详情页 <video><source src=".../get_file/.../xxx_720m.mp4" label="720p"> 多清晰度直链
  - 直链已实测 206 可 Range 拉流（video/mp4），parse:0 直接交播放器
  - 分类/筛选静态硬编码（法则16/17），sort_by 走查询参数
  - 分页：/zh/{path}/{N}/?sort_by=xxx （首页 N 省略）
  - 搜索：/zh/search/{kw}/{N}/
最后验证：2026-09-24
"""
import sys
import re
from urllib.parse import quote, urljoin
try:
    import urllib.request as _urlreq
    import urllib.error as _urlerr
except Exception:
    _urlreq = None
    _urlerr = None
try:
    import ssl as _ssl
    _SSLCTX = _ssl.create_default_context()
    _SSLCTX.check_hostname = False
    _SSLCTX.verify_mode = _ssl.CERT_NONE
except Exception:
    _SSLCTX = None

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider(object):
        def init(self, extend=""):
            pass


class Spider(Spider):

    # ============ 站点信息（换站只改这里） ============
    siteName = "FreePornVideos"
    HOST = "https://www.freepornvideos.xxx"

    UA = ("Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    def getName(self):
        return self.siteName

    def init(self, extend=""):
        self.extend = extend
        return

    def isVideoFormat(self, url):
        pats = ['.m3u8', '.mp4', '.flv', '.mkv', 'get_file/']
        return any(p in (url or '') for p in pats)

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 公共请求 ----------------
    def _headers(self, referer=None):
        h = {
            "User-Agent": self.UA,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": referer or (self.HOST + "/"),
        }
        return h

    def _get(self, url, referer=None):
        try:
            r = self.fetch(url, headers=self._headers(referer))
            if not r or getattr(r, "status_code", 0) != 200:
                return ""
            return r.text or ""
        except Exception:
            return ""

    # ---------------- 首页分类（静态） ----------------
    def homeContent(self, filter):
        # tid 用 /zh/ 之后的路径片段
        cate = [
            {"type_name": "Nubiles Porn 🔥", "type_id": "networks/nubiles-porn-com"},
            {"type_name": "MILF", "type_id": "categories/milf"},
            {"type_name": "继母幻想", "type_id": "categories/step-fantasy"},
            {"type_name": "继妹", "type_id": "categories/stepsister"},
            {"type_name": "巨乳", "type_id": "categories/big-tits"},
            {"type_name": "青少年(18)", "type_id": "categories/18-years-old"},
            {"type_name": "亚洲", "type_id": "categories/asian"},
            {"type_name": "中国人", "type_id": "categories/chinese"},
            {"type_name": "POV视点", "type_id": "categories/pov"},
            {"type_name": "体内射精", "type_id": "categories/creampie"},
            {"type_name": "口活", "type_id": "categories/blowjob"},
            {"type_name": "肛交", "type_id": "categories/anal"},
            {"type_name": "三人行", "type_id": "categories/threesome"},
            {"type_name": "偷窥", "type_id": "categories/voyeur"},
            {"type_name": "微型身材", "type_id": "categories/petite"},
            {"type_name": "熟女/半老徐娘", "type_id": "categories/cougar"},
            {"type_name": "人妖", "type_id": "categories/shemale"},
            {"type_name": "VR色情", "type_id": "categories/vr-virtual-reality"},
            {"type_name": "免费使用", "type_id": "categories/freeuse"},
            {"type_name": "出轨", "type_id": "categories/cheating"},
        ]
        sort_opts = [
            {"n": "最新", "v": "post_date"},
            {"n": "最多观看", "v": "video_viewed"},
            {"n": "最高评分", "v": "rating"},
            {"n": "最长时长", "v": "duration"},
            {"n": "最多收藏", "v": "most_favourited"},
        ]
        flt = {"排序": [{"key": "sort", "name": "排序",
                       "value": [{"n": o["n"], "v": o["v"]} for o in sort_opts]}]}
        filters = {c["type_id"]: [flt["排序"][0]] for c in cate}
        result = {"class": cate, "filters": filters}
        return result

    def homeVideoContent(self):
        # 首页推荐：直接拉最新
        data = self._list_page("categories/milf", 1, "post_date")
        return {"list": data}

    # ---------------- 列表解析 ----------------
    def _build_list_url(self, tid, pg, sort):
        path = tid.strip("/")
        url = "%s/zh/%s/" % (self.HOST, path)
        if pg and int(pg) > 1:
            url += "%d/" % int(pg)
        if sort:
            url += "?sort_by=%s" % sort
        return url

    def _parse_cards(self, html):
        vods = []
        if not html:
            return vods
        # 以每个 item 卡片为单位切分（thumb_title 锚点）
        for m in re.finditer(
                r'<a\s+class="thumb_title"\s+href="([^"]*?/zh/videos/[^"]+?)"[^>]*title="([^"]*)"',
                html):
            href = m.group(1)
            title = self._clean(m.group(2))
            vid = self._href_to_id(href)
            if not vid:
                continue
            # 该卡片附近的缩略图与时长
            seg = html[max(0, m.start() - 2000):m.start() + 200]
            pic = ""
            pm = re.findall(
                r'<img[^>]+class="thumb[^"]*"[^>]+src="([^"]+)"', seg)
            if pm:
                pic = pm[-1]
            if not pic:
                pm = re.findall(r'src="(https://img\.freepornvideos\.xxx/[^"]+\.jpg)"', seg)
                if pm:
                    pic = pm[-1]
            dm = re.search(r'class="duration">([^<]+)<', seg)
            remark = self._clean(dm.group(1)) if dm else ""
            vods.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
            })
        # 去重保序
        seen = set()
        out = []
        for v in vods:
            if v["vod_id"] in seen:
                continue
            seen.add(v["vod_id"])
            out.append(v)
        return out

    def _href_to_id(self, href):
        m = re.search(r'/zh/(videos/\d+/[^"/?#]+)/?', href)
        if m:
            return m.group(1)
        m = re.search(r'/zh/videos/(\d+)/', href)
        return ("videos/%s" % m.group(1)) if m else ""

    def _list_page(self, tid, pg, sort):
        url = self._build_list_url(tid, pg, sort)
        html = self._get(url)
        return self._parse_cards(html)

    def _page_count(self, html):
        if not html:
            return 1
        # 仅在分页块内取所有 /zh/{path}/{N}/(?sort_by=...) 链接的最大页码
        block = html
        i = html.find('class="pagination"')
        if i >= 0:
            block = html[i:i + 8000]
        nums = re.findall(r'href="[^"]*?/(\d+)/(?:\?[^"]*)?"', block)
        vals = []
        for n in nums:
            try:
                vals.append(int(n))
            except Exception:
                pass
        if vals:
            return max(vals)
        return 1

    def categoryContent(self, tid, pg, filter, extend):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        # 默认 post_date：唯一稳定排序，避免 viewed/featured 排序翻页出现边界重复
        sort = "post_date"
        if isinstance(extend, dict):
            sort = extend.get("sort", "") or "post_date"
        url = self._build_list_url(tid, pg, sort)
        html = self._get(url)
        vods = self._parse_cards(html)
        pc = self._page_count(html) if pg == 1 else 9999
        result = {
            "list": vods,
            "page": pg,
            "pagecount": pc,
            "limit": 24,
            "total": 24 * pc if pc != 9999 else 999999,
        }
        return result

    # ---------------- 详情 ----------------
    def _norm_ids(self, ids):
        if ids is None:
            return ""
        if isinstance(ids, (list, tuple)):
            return str(ids[0]) if ids else ""
        if isinstance(ids, bytes):
            try:
                return ids.decode("utf-8", "ignore")
            except Exception:
                return ""
        return str(ids)

    def detailContent(self, ids):
        vid = self._norm_ids(ids)
        if not vid:
            return {"list": []}
        url = "%s/zh/%s/" % (self.HOST, vid.strip("/"))
        html = self._get(url)
        skeleton = {
            "vod_id": vid,
            "vod_name": "",
            "vod_play_from": self.siteName,
            "vod_play_url": "播放$" + url,
        }
        if not html or len(html) < 500:
            return {"list": [skeleton]}

        # 标题
        name = ""
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        if m:
            name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if m:
                name = self._clean(m.group(1))
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = self._clean(m.group(1))

        # 封面
        pic = ""
        m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        if m:
            pic = m.group(1)
        if not pic:
            m = re.search(r"poster='([^']+)'", html) or re.search(r'poster="([^"]+)"', html)
            if m:
                pic = m.group(1)

        # 简介
        desc = ""
        m = re.search(r'<meta property="og:description" content="([^"]+)"', html)
        if m:
            desc = self._clean(m.group(1))

        # 演员（models）
        actors = []
        for am in re.finditer(
                r'/zh/models/[^"/]+/"[^>]*>(?:\s|<[^>]+>)*<span>([^<]+)</span>', html):
            n = self._clean(am.group(1))
            if n and n not in actors:
                actors.append(n)
        if not actors:
            for am in re.finditer(r'class="models__item thumb_model"[^>]*>.*?<span>([^<]+)</span>', html, re.S):
                n = self._clean(am.group(1))
                if n and n not in actors:
                    actors.append(n)

        # 分类标签
        tags = []
        for tm in re.finditer(r'/zh/categories/[^"/]+/"\s+title="([^"]+)"', html):
            t = self._clean(tm.group(1))
            if t and t not in tags:
                tags.append(t)

        # 时长
        remark = ""
        dm = re.search(r'完整视频[^<0-9]*([0-9:]+)', html)
        if dm:
            remark = "完整视频 " + dm.group(1)

        # ---- 播放地址：mp4 直链多清晰度 ----
        sources = self._extract_sources(html)
        if sources:
            play_url = "#".join("%s$%s" % (lab, u) for lab, u in sources)
        else:
            play_url = "播放$" + url

        vod = {
            "vod_id": vid,
            "vod_name": name or "未知标题",
            "vod_pic": pic,
            "vod_content": desc,
            "vod_actor": ",".join(actors[:15]),
            "vod_director": "",
            "vod_tag": ",".join(tags[:20]),
            "vod_remarks": remark,
            "vod_play_from": self.siteName,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def _extract_sources(self, html):
        """提取 <source src=... label=...> 多清晰度 mp4 直链。
        排序为「兼容优先」：默认自动播放的首条放最易解码的清晰度(720p 优先，
        4K/1440p 放最后)，避免盒子/手机自动从 2160p 起播时因无法硬解而黑屏。
        所有清晰度仍全部保留，用户可在播放页手动切换。"""
        out = []
        for m in re.finditer(
                r"<source\s+src=['\"]([^'\"]+)['\"][^>]*?label=['\"]?([^'\">]+)['\"]?",
                html):
            u = m.group(1).strip()
            lab = self._clean(m.group(2))
            if not u:
                continue
            u = urljoin(self.HOST, u)
            out.append((lab or "播放", u))
        # 去重
        seen = set()
        uniq = []
        for lab, u in out:
            if u in seen:
                continue
            seen.add(u)
            uniq.append((lab, u))

        def q(lab):
            mm = re.search(r'(\d+)', lab)
            return int(mm.group(1)) if mm else 0

        # 兼容优先排名：720p 最佳默认，其次 1080/480/360…，4K/2K 最后
        rank_map = {720: 100, 1080: 90, 480: 85, 540: 84, 360: 80,
                    240: 70, 1440: 20, 2160: 10}

        def rank(lab):
            return rank_map.get(q(lab), 50)
        uniq.sort(key=lambda x: rank(x[0]), reverse=True)
        return uniq

    # ---------------- 搜索 ----------------
    def searchContent(self, key, quick, pg="1"):
        try:
            pg = int(pg)
        except Exception:
            pg = 1
        kw = quote(key)
        url = "%s/zh/search/%s/" % (self.HOST, kw)
        if pg > 1:
            url += "%d/" % pg
        html = self._get(url)
        vods = self._parse_cards(html)
        return {"list": vods, "page": pg}

    # ---------------- 播放 ----------------
    def _resolve_final(self, url):
        """在「本机」把 get_file 的 302 预先跟随一次，取出最终 CDN(fpvcdn) 直链。

        为什么要预解析（这是 410 的修复关键）：
          - get_file 的 302 响应带 Content-Type: text/html，FongMi/ExoPlayer 的
            DataSource 起播几秒后重开连接/探测时，容易把这个跳转响应判成非媒体而
            报错（用户端表现为「加载几秒后 410」）。直接把最终 mp4 直链交给播放器，
            全程 video/mp4 + 200/206，绕开跳转判定。
          - 爬虫此刻就运行在盒子本机，与播放器同一出口 IP；CDN key 绑定的是
            「发起 get_file 请求方」的 IP，因此本机预解析得到的 key 正好绑到盒子
            自己的 IP，播放器随后拉流 IP 一致，不会 403。
            （注意：只有当爬虫与播放器不同机时预跟随才会导致 IP 锁定错误——本部署两者同机，安全。）
        解析失败时回退返回原始 get_file 链接，保证不因预解析异常而无法播放。
        """
        if not url or not url.startswith("http") or _urlreq is None:
            return url
        if "get_file/" not in url:
            return url
        try:
            class _NoRedirect(_urlreq.HTTPRedirectHandler):
                def redirect_request(self, *a, **k):
                    return None
            handlers = [_NoRedirect()]
            if _SSLCTX is not None:
                handlers.append(_urlreq.HTTPSHandler(context=_SSLCTX))
            opener = _urlreq.build_opener(*handlers)
            req = _urlreq.Request(url, headers={
                "User-Agent": self.UA,
                "Referer": self.HOST + "/",
            })
            loc = ""
            try:
                resp = opener.open(req, timeout=15)
                loc = resp.headers.get("Location", "") or ""
                resp.close()
            except _urlerr.HTTPError as e:
                loc = e.headers.get("Location", "") or ""
            if loc.startswith("http") and (".mp4" in loc or "key=" in loc or "fpvcdn" in loc):
                return loc
        except Exception:
            pass
        return url

    def playerContent(self, flag, id, vipFlags):
        # id 即 detailContent 组装的 "清晰度$直链" 的 url 部分（get_file 直链）。
        # 站点已实测：get_file → 302 → fpvcdn CDN(video/mp4, 可 Range, 有效 1h)。
        # 修复「加载几秒后 410」：在本机预跟随 302，直接把最终 CDN 直链交给播放器。
        url = id or ""
        if not url.startswith("http"):
            # 兜底：id 可能是详情路径，去详情页再取一次首选清晰度
            html = self._get("%s/zh/%s/" % (self.HOST, str(id).strip("/")))
            src = self._extract_sources(html)
            if src:
                url = src[0][1]
        final = self._resolve_final(url)
        header = {
            "User-Agent": self.UA,
            "Referer": self.HOST + "/",
        }
        return {"parse": 0, "url": final or url, "header": header}

    def localProxy(self, param):
        return None

    # ---------------- 工具 ----------------
    def _clean(self, s):
        if not s:
            return ""
        s = re.sub(r'<[^>]+>', '', s)
        s = s.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        s = s.replace('\ufeff', '').replace('&nbsp;', ' ')
        s = s.replace('&amp;', '&').replace('&quot;', '"').replace('&#39;', "'")
        s = s.replace('&lt;', '<').replace('&gt;', '>')
        return re.sub(r'\s+', ' ', s).strip()
