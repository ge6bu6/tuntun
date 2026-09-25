# -*- coding: utf-8 -*-
"""
luoju.py —— TVBox / 影视仓 源: 萝莉岛AV (网页版)
================================================
目标站点: https://www.luojubn.xyz   (站内自称"萝莉岛AV", 新版 App 即为本站的网页壳)

背景说明
--------
旧版 App(萝丽岛 4.1.9, 包名 com.jbzd.media.fiveonehl)的私有 API 后台
(http://107.148.37.172:8891/v1/)已于 2026-09 全线下线, 全球多节点 TCP 一致超时,
包内无备用线路 —— 那条源不可能有数据。本脚本改走该站**仍在线的网页端**,
已实测: 列表 / 详情 / m3u8 / 分片 全链路可播。

站点特征
--------
1. 页面被包成 `<script>var _s = "<base64>"</script>`, 解码后才是真 HTML。
2. 有一个很轻的通行校验: 浏览器会写 `verified=true` cookie(有效期 30 分钟)。
   脚本每次请求都带上, 不依赖执行 JS。
3. 详情页直接给出 m3u8 明文, 另有两条"加速线"需要通过 /jiasu_m3u8.php 换取真实地址。
   master m3u8 里的分片是**绝对路径**(形如 /20260915/xxx/1500kb/hls/a.ts),
   播放器遇到这种情况可能拼错, 所以脚本内置 localProxy 做清洗。
4. 条目名含未成年硬词的(幼女/萝莉/未成年 等)在脚本里统一剔除。

分类结构(每个都实测有数据)
--------------------------
  全部视频 / 国产·最新 / 国产·周榜 / 番号·最新 / 番号·周榜
  辣椒线路 / 乐播线路 / 155线路
  20 个热词分类(女神/人妻/少女/学妹/制服/后入 ...)
  ※ 站点自己的"细分类导航页"(video-list.html?reg=&category=)已经是空壳,
    服务端不再渲染列表, 所以脚本不列它们, 免得点开是空的。

交付形态: 单个 .py, 零第三方依赖, 兼容 Jython / py2 / py3。
用法:
    zip spider.jar py/luoju.py
源配置:
    {"key":"luoju","name":"萝莉岛AV","type":3,"api":"csp_luoju",
     "searchable":1,"quickSearch":1}
可选 ext(JSON 或 | 分隔均可, 不填就用内置默认):
    {"host":"https://www.luojubn.xyz","orderby":"latest","proxy":0,"timeout":12}
    https://www.luojubn.xyz|orderby=week|proxy=1|timeout=12
      proxy=1 → m3u8 走本地代理中转(个别壳分片相对路径拼不对时开)
"""

import base64
import json
import re
import ssl
import time

try:
    import urllib.request as _urlreq
    from urllib.request import Request as _Request
    try:
        from urllib.parse import quote as _quote
        from urllib.parse import urljoin as _urljoin
        from urllib.parse import unquote as _unquote
    except ImportError:
        from urllib import quote as _quote
        from urllib import unquote as _unquote
        from urlparse import urljoin as _urljoin
    _PY2 = False
except ImportError:                     # Jython 2.7 / py2
    import urllib2 as _urlreq
    from urllib2 import Request as _Request
    from urllib import quote as _quote
    from urllib import unquote as _unquote
    from urlparse import urljoin as _urljoin
    _PY2 = True

try:
    unicode
except NameError:                       # py3
    unicode = str

try:
    import requests
except ImportError:
    requests = None


# =====================================================================
# 基础工具(py2 / py3 通用)
# =====================================================================
def _b(s):
    if isinstance(s, bytes):
        return s
    if isinstance(s, unicode):
        return s.encode("utf-8")
    return unicode(s).encode("utf-8")


def _s(x):
    if x is None:
        return u""
    if isinstance(x, unicode):
        return x
    if isinstance(x, bytes):
        try:
            return x.decode("utf-8")
        except Exception:
            return x.decode("latin1", "ignore")
    return unicode(x)


def _b64e(t):
    try:
        out = base64.b64encode(_b(_s(t)))
    except Exception:
        return u""
    return _s(out).replace(u"+", u"-").replace(u"/", u"_").rstrip(u"=")


def _b64d(t):
    t = _s(t).replace(u"-", u"+").replace(u"_", u"/")
    t = t.strip()
    if len(t) % 4:
        t += u"=" * (4 - len(t) % 4)
    try:
        return _s(base64.b64decode(_b(t)))
    except Exception:
        return u""


def _int(v, d=0):
    try:
        return int(v)
    except Exception:
        try:
            return int(float(_s(v).strip() or d))
        except Exception:
            return d


def _unescape(t):
    t = _s(t)
    t = t.replace(u"&amp;", u"&").replace(u"&lt;", u"<").replace(u"&gt;", u">")
    t = t.replace(u"&quot;", u'"').replace(u"&#39;", u"'").replace(u"&apos;", u"'")
    t = t.replace(u"&nbsp;", u" ").replace(u"&hellip;", u"...")
    t = t.replace(u"&#8211;", u"-").replace(u"&#8212;", u"-")
    return t


def _strip(t):
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", u" ", _s(t))
    t = re.sub(r"(?s)<[^>]+>", u" ", t)
    t = _unescape(t)
    t = re.sub(r"\s+", u" ", t)
    return t.strip()


def _abs_url(base, url):
    url = _s(url).strip()
    if not url:
        return u""
    if url.startswith(u"//"):
        return u"https:" + url
    if url.startswith(u"http://") or url.startswith(u"https://"):
        return url
    if url.startswith(u"/"):
        m = re.match(r"(https?://[^/]+)", _s(base))
        return (m.group(1) if m else base.rstrip(u"/")) + url
    return _urljoin(base if base.endswith(u"/") else base + u"/", url)


# =====================================================================
# Spider
# =====================================================================
class Spider(object):

    # --- 站点常量 ----------------------------------------------------
    HOST = u"https://www.luojubn.xyz"
    UA = (u"Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
          u"(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 首页/分类页每页条数(实测 12)
    PAGE_SIZE = 12

    # 真实分类(逐项实测有数据; 站点的"细分类导航页"是空壳, 故不列, 以免点开无内容)
    #   type_id 语法:
    #     l:<order>          → 全站最新/榜单
    #     q:<region>|<order> → 按区域筛选
    #     k:<keyword>|<order>→ 按热词筛选(取站点首页真实热词)
    #     p:<slug>           → 线路分区页(辣椒/乐播/155)
    #   order 取值: latest / week / month / year / all
    CLASSES = [
        (u"l:latest", u"全部视频"),
        (u"q:国产|latest", u"国产·最新"),
        (u"q:国产|week", u"国产·周榜"),
        (u"q:番号|latest", u"番号·最新"),
        (u"q:番号|week", u"番号·周榜"),
        (u"p:lajiao", u"辣椒线路"),
        (u"p:lebo", u"乐播线路"),
        (u"p:155", u"155线路"),
        (u"k:女神", u"女神"),
        (u"k:人妻", u"人妻"),
        (u"k:少妇", u"少妇"),
        (u"k:网红", u"网红"),
        (u"k:御姐", u"御姐"),
        (u"k:学妹", u"学妹"),
        (u"k:少女", u"少女"),
        (u"k:情侣", u"情侣"),
        (u"k:美少女", u"美少女"),
        (u"k:嫩妹", u"嫩妹"),
        (u"k:校花", u"校花"),
        (u"k:闺蜜", u"闺蜜"),
        (u"k:主播", u"主播"),
        (u"k:熟女", u"熟女"),
        (u"k:妹子", u"妹子"),
        (u"k:姐姐", u"姐姐"),
        (u"k:学生", u"学生"),
        (u"k:嫂子", u"嫂子"),
        (u"k:中出", u"中出"),
        (u"k:制服", u"制服"),
        (u"k:后入", u"后入"),
    ]

    # 未成年硬词: 条目名命中即剔除(19岁高中生 / 大学生 这类明确成年的不误杀)
    BAD_WORDS = [u"幼女", u"萝莉", u"未成年", u"女童", u"小学", u"初中生",
                 u"中学生", u"童男", u"童女", u"幼齿", u"稚女", u"萝莉塔"]

    ORDERBY = u"latest"

    # 顺序: (site_key, label) —— 站点默认站是"辣椒资源", 加速线走 jiasu 接口
    LINES = [u"默认线路", u"加速线1", u"加速线2"]

    # -----------------------------------------------------------------
    def __init__(self):
        self.host = self.HOST
        self.timeout = 12
        self.orderby = self.ORDERBY
        self.use_proxy = False
        self.headers = {
            u"User-Agent": self.UA,
            u"Accept": u"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            u"Accept-Language": u"zh-CN,zh;q=0.9,en;q=0.8",
            u"Referer": self.HOST + u"/",
            # 站点只靠这个轻量通行位, 不需要执行 JS
            u"Cookie": u"verified=true",
        }
        self.session = None
        self.s = None
        self.sess = None
        self._detail_cache = {}
        self._line_cache = {}

    # -----------------------------------------------------------------
    # 接口 0: 依赖声明(宿主可能在 init 之前调用, 必须存在)
    # -----------------------------------------------------------------
    def getDependence(self):
        return []

    # -----------------------------------------------------------------
    # 接口 1: 初始化
    # -----------------------------------------------------------------
    def init(self, extend=u""):
        cfg = {}
        try:
            if isinstance(extend, dict):
                cfg = extend
            else:
                raw = _s(extend).strip()
                if raw.startswith(u"{"):
                    cfg = json.loads(raw)
                elif raw:
                    for p in raw.split(u"|"):
                        p = p.strip()
                        if not p:
                            continue
                        if u"=" in p:
                            k, v = p.split(u"=", 1)
                            cfg[k.strip()] = v.strip()
                        elif p.startswith(u"http"):
                            cfg[u"host"] = p
        except Exception:
            cfg = {}

        host = _s(cfg.get(u"host") or cfg.get(u"url") or u"").strip()
        if host:
            self.host = host.rstrip(u"/")
        self.headers[u"Referer"] = self.host + u"/"

        ob = _s(cfg.get(u"orderby") or u"").strip()
        if ob in (u"latest", u"week", u"month", u"year", u"all"):
            self.orderby = ob

        try:
            self.timeout = max(5, _int(cfg.get(u"timeout"), 12))
        except Exception:
            self.timeout = 12

        pv = _s(cfg.get(u"proxy") or u"").strip().lower()
        self.use_proxy = pv in (u"1", u"true", u"yes", u"on")

        if requests is not None:
            try:
                self.session = requests.Session()
                self.session.headers.update(self.headers)
                self.s = self.session
                self.sess = self.session
            except Exception:
                self.session = None
        return None

    # -----------------------------------------------------------------
    # 网络层: requests 优先, urllib 兜底
    # -----------------------------------------------------------------
    def _http(self, url, referer=None, raw=False):
        if not url:
            return u"" if not raw else b""
        hdr = dict(self.headers)
        if referer:
            hdr[u"Referer"] = referer
        if self.session is not None:
            try:
                r = self.session.get(url, headers=hdr, timeout=self.timeout)
                if raw:
                    return r.content
                r.encoding = r.encoding or u"utf-8"
                return _s(r.text)
            except Exception:
                pass
        try:
            req = _Request(url, headers=hdr)
            resp = _urlreq.urlopen(req, timeout=self.timeout)
            data = resp.read()
            if raw:
                return data
            try:
                return data.decode("utf-8")
            except Exception:
                return data.decode("utf-8", "ignore")
        except Exception:
            return b"" if raw else u""

    def _api_json(self, url, referer=None):
        txt = self._http(url, referer=referer)
        if not txt:
            return {}
        try:
            return json.loads(txt)
        except Exception:
            return {}

    # -----------------------------------------------------------------
    # 页面解包: var _s = "<base64>"  →  真 HTML
    # -----------------------------------------------------------------
    def _unpack(self, html):
        html = _s(html)
        if not html:
            return u""
        m = re.search(r'var\s+_s\s*=\s*"([^"]+)"', html)
        if not m:
            m = re.search(r"var\s+_s\s*=\s*'([^']+)'", html)
        if not m:
            return html
        dec = _b64d(m.group(1))
        return dec if dec else html

    def _page(self, url, referer=None):
        return self._unpack(self._http(url, referer=referer))

    # -----------------------------------------------------------------
    # 通用列表解析: 适配 post-item(分类/分区页) 与 v-card(搜索页)
    # -----------------------------------------------------------------
    def _parse_cards(self, html):
        out = []
        seen = set()
        if not html:
            return out
        pattern = re.compile(r'href="/news/(\d+)\.html"', re.I)
        marks = list(pattern.finditer(html))
        for idx, m in enumerate(marks):
            vid = m.group(1)
            if vid in seen:
                continue
            end = marks[idx + 1].start() if idx + 1 < len(marks) else min(len(html), m.end() + 1500)
            chunk = html[m.end():end]
            pic = u""
            pm = re.search(r'data-src="([^"]+)"', chunk) or re.search(r'src="([^"]+)"', chunk)
            if pm:
                pic = _unescape(pm.group(1)).strip()
            name = u""
            nm = (re.search(r'class="v-title"[^>]*>(.*?)</h3>', chunk, re.S)
                  or re.search(r'class="post-title"[^>]*>\s*<a[^>]*>(.*?)</a>', chunk, re.S)
                  or re.search(r'alt="([^"]+)"', chunk))
            if nm:
                name = _strip(nm.group(1))
            if not name or name == u"video":
                nm2 = re.search(r'<h3[^>]*>(.*?)</h3>', chunk, re.S)
                if nm2:
                    name = _strip(nm2.group(1))
            if not name:
                continue
            if self._is_bad(name):
                seen.add(vid)
                continue
            seen.add(vid)
            out.append({
                u"vod_id": vid,
                u"vod_name": name,
                u"vod_pic": _abs_url(self.host, pic),
                u"vod_remarks": u"",
            })
        return out

    def _is_bad(self, name):
        t = _s(name)
        for w in self.BAD_WORDS:
            if w in t:
                return True
        return False

    def _page_count(self, html, got):
        """优先用站点的总数统计算页数, 再退化为页面里的最大 page 号"""
        total = 0
        m = re.search(r"共筛选出\s*<strong>\s*(\d+)\s*</strong>", html)
        if m:
            total = _int(m.group(1), 0)
        if total > 0:
            pc = int((total + self.PAGE_SIZE - 1) / self.PAGE_SIZE)
            return max(1, pc)
        pages = [_int(x, 0) for x in re.findall(r"page=(\d+)", html)]
        pages = [p for p in pages if p > 0]
        if pages:
            return max(pages)
        return 2 if got >= self.PAGE_SIZE else 1

    def _q(self, t):
        t = _s(t)
        return _quote(_b(t) if _PY2 else t.encode("utf-8"))

    def _list_url(self, tid, pg):
        tid = _s(tid)
        pg = max(1, _int(pg, 1))
        order = self.orderby
        if tid.startswith(u"p:"):                       # 线路分区页
            slug = tid[2:].strip()
            if slug.endswith(u".html"):
                slug = slug[:-5]
            return u"%s/%s.html?page=%d&order=%s" % (self.host, slug, pg, order)
        if tid.startswith(u"q:"):                       # 区域筛选
            body = tid[2:].split(u"|")
            reg = body[0].strip()
            if len(body) > 1 and body[1].strip():
                order = body[1].strip()
            return (u"%s/search.html?region=%s&order=%s&page=%d"
                    % (self.host, self._q(reg), order, pg))
        if tid.startswith(u"k:"):                       # 热词筛选
            body = tid[2:].split(u"|")
            kw = body[0].strip()
            if len(body) > 1 and body[1].strip():
                order = body[1].strip()
            return (u"%s/search.html?q=%s&order=%s&page=%d"
                    % (self.host, self._q(kw), order, pg))
        if tid.startswith(u"l:"):                       # 全站
            od = tid[2:].strip() or order
            return u"%s/search.html?order=%s&page=%d" % (self.host, od, pg)
        # 兜底: 全站最新
        return u"%s/search.html?order=latest&page=%d" % (self.host, pg)

    # -----------------------------------------------------------------
    # 接口 2: 首页分类
    # -----------------------------------------------------------------
    def homeContent(self, filter=None):
        cls = []
        for tid, name in self.CLASSES:
            cls.append({u"type_id": tid, u"type_name": name})
        return {u"class": cls, u"filters": {}}

    # -----------------------------------------------------------------
    # 接口 3: 首页推荐(全站最新)
    # -----------------------------------------------------------------
    def homeVideoContent(self):
        html = self._page(self._list_url(u"l:latest", 1))
        lst = self._parse_cards(html)
        if not lst:
            html = self._page(self.host + u"/lajiao.html")
            lst = self._parse_cards(html)
        return {u"list": lst[:30]}

    # -----------------------------------------------------------------
    # 接口 4: 分类列表
    # -----------------------------------------------------------------
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        pg = max(1, _int(pg, 1))
        html = self._page(self._list_url(tid, pg))
        lst = self._parse_cards(html)
        pc = self._page_count(html, len(lst))
        if pg > pc:
            pc = pg
        return {
            u"list": lst,
            u"page": pg,
            u"pagecount": pc,
            u"limit": self.PAGE_SIZE,
            u"total": pc * self.PAGE_SIZE,
        }

    # -----------------------------------------------------------------
    # 接口 5: 详情
    # -----------------------------------------------------------------
    def _detail_html(self, vid):
        vid = _s(vid).strip()
        if not re.match(r"^\d+$", vid):
            return u"", u""
        url = self.host + u"/news/" + vid + u".html"
        html = self._page(url)
        return url, html

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = _s(vid).strip()
        if not re.match(r"^\d+$", vid):
            return {u"list": []}
        url, html = self._detail_html(vid)
        if not html:
            return {u"list": []}

        name = u""
        m = (re.search(r'<h1[^>]*class="[^"]*v-title[^"]*"[^>]*>(.*?)</h1>', html, re.S)
             or re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S))
        if m:
            name = _strip(m.group(1))
        if not name:
            m = re.search(r"<title>(.*?)</title>", html, re.S)
            if m:
                name = _strip(m.group(1)).split(u" - ")[0]

        pic = u""
        m = (re.search(r'<video[^>]*poster="([^"]+)"', html, re.S)
             or re.search(r'<img[^>]*class="[^"]*v-cover[^"]*"[^>]*src="([^"]+)"', html, re.S))
        if m:
            pic = _unescape(m.group(1)).strip()

        # 线路: <button class="line-btn ..." data-type="default|acc" data-raw="..." data-cdn="...">
        raw_default = u""
        m = re.search(r'data-m3u8="([^"]+)"', html)
        if m:
            raw_default = _unescape(m.group(1)).strip()
        if not raw_default:
            m = re.search(r'<source[^>]+src="([^"]+\.m3u8[^"]*)"', html)
            if m:
                raw_default = _unescape(m.group(1)).strip()

        lines = []
        btn_re = re.compile(
            r'data-type="([^"]+)"[^>]*data-raw="([^"]+)"[^>]*data-cdn="([^"]*)"[^>]*>\s*([^<]{0,24})\s*<',
            re.S)
        for t, raw, cdn, label in btn_re.findall(html):
            raw = _unescape(raw).strip()
            cdn = _s(cdn).strip()
            label = _strip(label) or (u"默认线路" if t == u"default" else u"加速线")
            if not raw:
                continue
            if t == u"default" or not cdn:
                addr = raw
            else:
                addr = u"acc://" + _b64e(raw) + u"|" + cdn + u"|" + label
            lines.append((label, addr))

        if not lines and raw_default:
            lines.append((u"默认线路", raw_default))
        if not lines:
            return {u"list": []}

        seen = []
        froms = []
        groups = []
        for label, addr in lines:
            base_label = re.sub(r"\d+$", u"", label).strip() or label
            dup = 1
            lb = label
            while lb in seen:
                dup += 1
                lb = base_label + unicode(dup)
            seen.append(lb)
            froms.append(lb)
            groups.append(lb + u"$第1集$" + addr)

        desc = _strip(re.search(r'<div class="v-desc[^"]*">(.*?)</div>', html, re.S).group(1)) \
            if re.search(r'<div class="v-desc[^"]*">(.*?)</div>', html, re.S) else u""

        item = {
            u"vod_id": vid,
            u"vod_name": name or (u"视频 " + vid),
            u"vod_pic": _abs_url(self.host, pic),
            u"vod_content": desc or (name or u""),
            u"vod_play_from": u"$$$".join(froms),
            u"vod_play_url": u"$$$".join(groups),
        }
        self._detail_cache[vid] = (time.time(), item)
        self._line_cache[vid] = (froms, groups)
        return {u"list": [item]}

    # -----------------------------------------------------------------
    # 接口 6: 播放
    # -----------------------------------------------------------------
    def playerContent(self, flag, ids, vipFlags=None):
        ids = _s(ids).strip()
        if isinstance(ids, (list, tuple)):
            ids = _s(ids[0]) if ids else u""
        ids = ids.strip()
        # 宿主可能把 "第1集$地址" 整串传进来, 也可能传 "多集#串", 这里统一剥壳
        if u"$" in ids:
            ids = ids.rsplit(u"$", 1)[1].strip()
        if u"#" in ids and not ids.startswith(u"http"):
            ids = ids.split(u"#")[0].strip()
        if u"$" in ids:
            ids = ids.rsplit(u"$", 1)[1].strip()

        url = u""
        flag = _s(flag).strip()

        if ids.startswith(u"acc://"):
            body = ids[6:]
            raw, cdn = (body.split(u"|", 1) + [u""])[:2]
            raw = _b64d(raw)
            if cdn:
                cdn = cdn.split(u"|")[0]
            url = self._acc_url(raw, cdn) or raw
        elif ids.startswith(u"http://") or ids.startswith(u"https://"):
            url = ids
        else:
            cached = self._detail_cache.get(ids)
            if not cached:
                self.detailContent([ids])
                cached = self._detail_cache.get(ids)
            groups = []
            lines = self._line_cache.get(ids)
            if lines:
                froms, groups = lines
            elif cached:
                groups = _s(cached[1].get(u"vod_play_url") or u"").split(u"$$$")
            if groups:
                idx = 0
                if lines and flag and flag in lines[0]:
                    try:
                        idx = lines[0].index(flag)
                    except Exception:
                        idx = 0
                if idx >= len(groups):
                    idx = 0
                pick = groups[idx].split(u"#")[0]
                url = pick.rsplit(u"$", 1)[-1].strip()
            if url.startswith(u"acc://"):
                body = url[6:]
                raw, cdn = (body.split(u"|", 1) + [u""])[:2]
                raw = _b64d(raw)
                cdn = cdn.split(u"|")[0] if cdn else u""
                url = self._acc_url(raw, cdn) or raw

        out = {
            u"parse": 0,
            u"jx": 0,
            u"playUrl": u"",
            u"url": url,
            u"header": dict(self.headers),
        }
        if url and u".m3u8" in url.lower():
            out[u"format"] = u"application/x-mpegURL"
        if url and out.get(u"format") and self.use_proxy:
            out[u"url"] = (u"http://127.0.0.1:9978/proxy?do=py&m3u8="
                           + _b64e(url) + u"&h=" + _b64e(self.host + u"/"))
        return out

    def _acc_url(self, raw_url, cdn):
        """加速线: /jiasu_m3u8.php 换取真实播放地址"""
        raw_url = _s(raw_url).strip()
        cdn = _s(cdn).strip()
        if not raw_url:
            return u""
        if not cdn:
            return raw_url
        api = (self.host + u"/jiasu_m3u8.php?m3u8=" + _quote(_b(raw_url) if _PY2 else raw_url.encode("utf-8"))
               + u"&cdn=" + _quote(_b(cdn) if _PY2 else cdn.encode("utf-8"))
               + u"&t=" + unicode(int(time.time() * 1000)))
        data = self._api_json(api, referer=self.host + u"/")
        return _s(data.get(u"play_url") or u"")

    # -----------------------------------------------------------------
    # 接口 7: 搜索
    # -----------------------------------------------------------------
    def searchContent(self, key, quick=False, pg=u"1"):
        pg = max(1, _int(pg, 1))
        kw = _s(key).strip()
        if not kw:
            return {u"list": [], u"page": 1, u"pagecount": 1}
        url = (self.host + u"/search.html?q="
               + _quote(_b(kw) if _PY2 else kw.encode("utf-8"))
               + u"&page=%d&order=latest" % pg)
        html = self._page(url)
        lst = self._parse_cards(html)
        pc = self._page_count(html, len(lst))
        if pg > pc:
            pc = pg
        return {u"list": lst, u"page": pg, u"pagecount": pc}

    # -----------------------------------------------------------------
    # 接口 8: 本地代理 —— m3u8 清洗(分片/密钥绝对化) + 分片转发
    # -----------------------------------------------------------------
    def localProxy(self, param):
        if isinstance(param, (bytes, unicode)):
            try:
                param = json.loads(_s(param))
            except Exception:
                param = {}
        if not isinstance(param, dict):
            param = {}

        url = _s(param.get(u"m3u8") or param.get(u"url") or u"")
        if param.get(u"m3u8"):
            url = _b64d(param.get(u"m3u8"))
        url = url.replace(u" ", u"+").strip()
        if u"$" in url:
            url = url.rsplit(u"$", 1)[-1].strip()
        if url.startswith(u"proxy://"):
            url = u""
        if not url:
            return [404, u"text/plain", b"Not Found", {}]

        data = self._http(url, referer=self.host + u"/", raw=True)
        if not data:
            return [404, u"text/plain", b"Not Found", {}]

        low = url.lower().split(u"?")[0]
        if low.endswith(u".ts") or low.endswith(u".jpg") or low.endswith(u".png"):
            return [200, u"application/octet-stream", data,
                    {u"Access-Control-Allow-Origin": u"*"}]

        try:
            txt = data.decode("utf-8")
        except Exception:
            txt = data.decode("utf-8", "ignore")

        if u"#EXTM3U" not in txt:
            return [200, u"text/plain", _b(txt),
                    {u"Access-Control-Allow-Origin": u"*"}]

        try:
            base = url.rsplit(u"/", 1)[0] + u"/"
            out = []
            for line in txt.splitlines():
                ln = line.strip()
                if not ln:
                    out.append(u"")
                    continue
                if ln.startswith(u"#"):
                    if (ln.startswith(u"#EXT-X-KEY") or ln.startswith(u"#EXT-X-MAP")
                            or ln.startswith(u"#EXT-X-MEDIA")) and u'URI="' in ln:
                        hd, tl = ln.split(u'URI="', 1)
                        uri, rest = tl.split(u'"', 1)
                        ln = hd + u'URI="' + _abs_url(base, uri) + u'"' + rest
                    out.append(ln)
                else:
                    out.append(_abs_url(base, ln))
            body = u"\n".join(out)
            return [200, u"application/vnd.apple.mpegurl", _b(body),
                    {u"Access-Control-Allow-Origin": u"*"}]
        except Exception:
            return [200, u"application/vnd.apple.mpegurl", _b(txt),
                    {u"Access-Control-Allow-Origin": u"*"}]

    # -----------------------------------------------------------------
    # 其余契约接口
    # -----------------------------------------------------------------
    def manualVideoCheck(self):
        return False

    def isVideoFormat(self, url):
        u = _s(url).lower()
        return u.endswith(u".m3u8") or u.endswith(u".mp4")

    def action(self, action=None):
        return {}

    def destroy(self):
        try:
            if self.session is not None:
                self.session.close()
        except Exception:
            pass
        self.session = None
        self.s = None
        self.sess = None
        return None


# =====================================================================
# 自检块(宿主不执行; 本地想验契约时: python luoju.py)
# =====================================================================
if __name__ == u"__main__":
    sp = Spider()
    sp.getDependence()
    sp.init(u"")
    print(u"[ok] Spider() 无参实例化 + getDependence + init 通过")
    hc = sp.homeContent(False)
    print(u"[homeContent] class=%d %s" % (len(hc.get(u"class", [])),
                                          json.dumps(hc.get(u"class", [])[:2], ensure_ascii=False)))
    hv = sp.homeVideoContent()
    print(u"[homeVideoContent] %d 条" % len(hv.get(u"list", [])))
    for x in hv.get(u"list", [])[:3]:
        print(u"    ", x.get(u"vod_id"), x.get(u"vod_name")[:40])
    cc = sp.categoryContent(u"q:国产|latest", 1, False, {})
    print(u"[categoryContent] %d 条 pagecount=%s" % (len(cc.get(u"list", [])), cc.get(u"pagecount")))
    if cc.get(u"list"):
        vid = cc[u"list"][0][u"vod_id"]
        det = sp.detailContent([vid])
        it = (det.get(u"list") or [{}])[0]
        print(u"[detailContent]", vid, it.get(u"vod_name", u"")[:40])
        print(u"    from:", it.get(u"vod_play_from"))
        print(u"    url:", _s(it.get(u"vod_play_url"))[:160])
        pl = sp.playerContent(u"", vid, [])
        print(u"[playerContent] format=%s url=%s" % (pl.get(u"format"), _s(pl.get(u"url"))[:110]))
        lp = sp.localProxy({u"url": pl.get(u"url")})
        print(u"[localProxy] code=%s len=%s" % (lp[0], len(lp[2])))
        print(u"    body head:", _s(lp[2])[:90].replace(u"\n", u" | "))
    sc = sp.searchContent(u"学生", False, u"1")
    print(u"[searchContent] %d 条 pagecount=%s" % (len(sc.get(u"list", [])), sc.get(u"pagecount")))
    for x in sc.get(u"list", [])[:3]:
        print(u"    ", x.get(u"vod_id"), x.get(u"vod_name")[:40])
    print(u"[manualVideoCheck]", sp.manualVideoCheck())
    print(u"[action]", sp.action(u""))
    sp.destroy()
    print(u"[ok] 契约自检结束")
