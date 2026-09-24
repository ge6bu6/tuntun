# coding=utf-8
# !/usr/bin/python
"""
2026小马拉车 (lamak3doo.cyou) — FongMi/TVBox T3 爬虫
CMS: MacCMS(苹果CMS) 模板 lmjl —— API closed，纯 HTML 解析
落地域会轮换：启动自动从 canonical 主域 lamak3doo.cyou 的 301 探测当前落地域
播放：详情页单集 -> /vodplay/{id}-1-1/ 页面内 player_data.url 即 m3u8 直链(parse:0)
"""
import sys
import re
import json

sys.path.append('..')
try:
    from base.spider import Spider
except Exception:
    class Spider:  # 本地 mock 兜底，实机由框架注入
        def init(self, extend=""):
            pass


class Spider(Spider):

    # canonical 主域：稳定入口，301 跳转到当前落地/内容域
    MAIN = "https://lamak3doo.cyou"

    # 手动覆盖：留空=启动时自动探测落地域；若要写死某域，填这里即可
    HOST = ""

    # 自动探测失败时的历史落地域兜底（按新到旧排列）
    FALLBACK_HOSTS = [
        "https://linke.buzh1sbui.buzz",
        "https://dforandand.edzh1sbit.buzz",
    ]

    UA = ("Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

    # 分类清单：首页导航真实分类被 HTML 注释隐藏，硬编码写死
    CATE = [
        {"type_id": "600", "type_name": "极品资源"},
        {"type_id": "423", "type_name": "麻豆资源"},
        {"type_id": "1",   "type_name": "百万资源"},
        {"type_id": "18",  "type_name": "大地资源"},
        {"type_id": "48",  "type_name": "桃花资源"},
        {"type_id": "61",  "type_name": "森林资源"},
        {"type_id": "132", "type_name": "杏吧资源"},
        {"type_id": "154", "type_name": "色猫资源"},
        {"type_id": "268", "type_name": "奶香香资源"},
        {"type_id": "382", "type_name": "黄色仓库"},
        {"type_id": "296", "type_name": "奥斯卡资源"},
        {"type_id": "387", "type_name": "网红主播"},
    ]

    def init(self, extend=""):
        try:
            self.session = self._new_session()
        except Exception:
            self.session = None
        try:
            self._resolve_host()
        except Exception:
            pass
        return

    def getName(self):
        return "2026小马拉车"

    def isVideoFormat(self, url):
        pats = ['.m3u8', '.mp4', '.flv', '.ts', '.mkv', '.avi', '.m4a']
        for p in pats:
            if p in url:
                return True
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        return

    # ---------------- 内部工具 ----------------

    def _new_session(self):
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })
        return s

    def _headers(self):
        return {"User-Agent": self.UA}

    # ---------- 落地域自动探测 ----------

    def _host_of(self, u):
        m = re.match(r'(https?://[^/]+)', u or "")
        return m.group(1) if m else ""

    def _probe_main(self):
        """请求 canonical 主域，跟随 301 跳转拿到当前落地/内容域。"""
        try:
            if getattr(self, "session", None) is None:
                self.session = self._new_session()
            r = self.session.get(self.MAIN + "/", headers=self._headers(),
                                  timeout=15, allow_redirects=True)
            if r is not None:
                # 优先用最终 URL 的 host；再退回 Location 头
                host = self._host_of(getattr(r, "url", "") or "")
                if not host:
                    loc = r.headers.get("Location", "") if getattr(r, "headers", None) else ""
                    host = self._host_of(loc)
                # 排除跳回主域自身的情况
                if host and self._host_of(self.MAIN + "/") not in host:
                    return host
        except Exception:
            pass
        return ""

    def _verify_host(self, host):
        """确认该域根路径能返回真实 MacCMS 列表内容。"""
        if not host:
            return False
        try:
            if getattr(self, "session", None) is None:
                self.session = self._new_session()
            r = self.session.get(host + "/vodtype/1/", headers=self._headers(),
                                  timeout=12, allow_redirects=True)
            if r is not None and getattr(r, "status_code", 0) == 200:
                t = r.text or ""
                if "/voddetail/" in t or "group-item" in t:
                    return True
        except Exception:
            pass
        return False

    def _resolve_host(self, force=False):
        """解析可用内容域。已有 HOST 且非强制则直接返回。"""
        if self.HOST and not force:
            return self.HOST
        candidates = []
        probed = self._probe_main()
        if probed:
            candidates.append(probed)
        for h in self.FALLBACK_HOSTS:
            if h not in candidates:
                candidates.append(h)
        for h in candidates:
            if self._verify_host(h):
                self.HOST = h
                return h
        # 全部校验失败：退回探测域或首个兜底，避免彻底不可用
        self.HOST = probed or (self.FALLBACK_HOSTS[0] if self.FALLBACK_HOSTS else self.MAIN)
        return self.HOST

    def host(self):
        """URL 构建统一入口，惰性解析并缓存。"""
        if not self.HOST:
            try:
                self._resolve_host()
            except Exception:
                self.HOST = self.FALLBACK_HOSTS[0] if self.FALLBACK_HOSTS else self.MAIN
        return self.HOST or self.MAIN


    def fetch(self, url, headers=None, timeout=15):
        """GET，优先复用框架 self.fetch，缺省用 requests。返回 requests.Response 兼容对象。"""
        try:
            # 框架若已注入原生 fetch，会被子类覆盖，这里保证本地可跑
            if getattr(self, "session", None) is None:
                self.session = self._new_session()
            return self.session.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        except Exception:
            return None

    def post(self, url, data=None, headers=None, timeout=15):
        try:
            if getattr(self, "session", None) is None:
                self.session = self._new_session()
            return self.session.post(url, data=data, headers=headers, timeout=timeout, allow_redirects=True)
        except Exception:
            return None

    def _abs(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host() + u
        return self.host() + "/" + u

    def _parse_list(self, html):
        """解析 layui-col-md3 卡片列表 -> [{vod_id, vod_name, vod_pic, vod_remarks}]"""
        vods = []
        if not html:
            return vods
        # 每张卡片：<a href="/voddetail/{id}/" ... class="group-item...">(inner)</a>
        cards = re.findall(
            r'<a\s+href="/voddetail/(\d+)/"[^>]*class="group-item[^>]*>(.*?)</a>',
            html, re.S)
        for vid, inner in cards:
            # 图片：优先 data-src(懒加载真图)，退回 src
            pic = ""
            m = re.search(r'data-src="([^"]+)"', inner)
            if m:
                pic = m.group(1)
            else:
                m = re.search(r'\bsrc="([^"]+)"', inner)
                if m:
                    pic = m.group(1)
            # 标题：<p>...</p>
            name = ""
            m = re.search(r'<p>(.*?)</p>', inner, re.S)
            if m:
                name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            # 备注：score 徽标 ❤️ 82624 / 日期
            remark = ""
            m = re.search(r'class="[^"]*score[^"]*"[^>]*>(.*?)</span>', inner, re.S)
            if m:
                remark = re.sub(r'<[^>]+>', '', m.group(1)).replace("❤️", "").strip()
            if vid and name:
                vods.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self._abs(pic),
                    "vod_remarks": remark,
                })
        return vods

    # ---------------- 首页 ----------------

    def homeContent(self, filter):
        """成人站：本地零网络返回分类，避免首页广告噪声"""
        classes = [{"type_id": c["type_id"], "type_name": c["type_name"]} for c in self.CATE]
        result = {"class": classes}
        try:
            vods = self.homeVideoContent().get("list", [])
            result["list"] = vods
        except Exception:
            result["list"] = []
        return result

    def homeVideoContent(self):
        """首页推荐：取第一个分类首页"""
        url = "%s/vodtype/%s/" % (self.host(), self.CATE[0]["type_id"])
        r = self.fetch(url, headers=self._headers())
        if not r or getattr(r, "status_code", 0) != 200:
            return {"list": []}
        return {"list": self._parse_list(r.text)}

    # ---------------- 分类 ----------------

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = int(pg)
        except Exception:
            page = 1
        if page <= 1:
            url = "%s/vodtype/%s/" % (self.host(), tid)
        else:
            url = "%s/vodtype/%s-%d/" % (self.host(), tid, page)
        r = self.fetch(url, headers=self._headers())
        vods = []
        if r and getattr(r, "status_code", 0) == 200:
            vods = self._parse_list(r.text)
        return {
            "list": vods,
            "page": page,
            "pagecount": 9999 if vods else page,
            "limit": len(vods),
            "total": 999999 if vods else 0,
        }

    # ---------------- 详情 ----------------

    def detailContent(self, ids):
        vid = ids[0]
        url = "%s/voddetail/%s/" % (self.host(), vid)
        r = self.fetch(url, headers=self._headers())
        if not r or getattr(r, "status_code", 0) != 200:
            return {"list": []}
        html = r.text

        name = ""
        m = re.search(r'<div class="group-title">\s*<h1>\s*(.*?)</h1>', html, re.S)
        if m:
            name = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 详情主图：detail-info 前的图片
        pic = ""
        m = re.search(r'<div class="detail-pic"[^>]*>.*?data-src="([^"]+)"', html, re.S)
        if not m:
            m = re.search(r'data-src="([^"]+)"[^>]*>\s*</div>\s*<div class="detail-info"', html, re.S)
        if m:
            pic = m.group(1)

        def _field(label):
            mm = re.search(label + r'\s*:?：?\s*(.*?)\s*<br', html, re.S)
            if mm:
                return re.sub(r'<[^>]+>', '', mm.group(1)).strip()
            return ""

        actor = _field("主演")
        remarks = _field("备注")
        area = _field("地区")
        year = _field("年代")
        lang = _field("语言")

        # 简介
        desc = ""
        m = re.search(r'详细介绍:\s*<br\s*/?>\s*<p>(.*?)</p>', html, re.S)
        if m:
            desc = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not desc:
            desc = name

        # 播放链接：单集 /vodplay/{id}-1-1/
        m = re.search(r'<a\s+class="play"\s+href="/vodplay/([\d\-]+)/"', html)
        play_seg = m.group(1) if m else ("%s-1-1" % vid)

        vod = {
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._abs(pic),
            "vod_actor": actor,
            "vod_director": "",
            "vod_area": area,
            "vod_year": year,
            "vod_lang": lang,
            "vod_remarks": remarks,
            "vod_content": desc,
            "vod_play_from": "hsckm3u8",
            "vod_play_url": "正片$" + play_seg,
        }
        return {"list": [vod]}

    # ---------------- 搜索 ----------------

    def searchContent(self, key, quick, pg="1"):
        url = "%s/vodsearch/-------------/" % self.host()
        headers = self._headers()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        r = self.post(url, data={"wd": key}, headers=headers)
        vods = []
        if r and getattr(r, "status_code", 0) == 200:
            vods = self._parse_list(r.text)
        return {"list": vods, "page": 1}

    # ---------------- 播放 ----------------

    def playerContent(self, flag, id, vipFlags):
        """id 形如 1913282-1-1，取 /vodplay/{id}/ 内 player_data.url (m3u8 直链)"""
        url = "%s/vodplay/%s/" % (self.host(), id)
        r = self.fetch(url, headers=self._headers())
        play_url = ""
        if r and getattr(r, "status_code", 0) == 200:
            m = re.search(r'var\s+player_data\s*=\s*(\{.*?\})\s*</script>', r.text, re.S)
            if m:
                raw = m.group(1)
                try:
                    data = json.loads(raw)
                    play_url = data.get("url", "")
                except Exception:
                    mm = re.search(r'"url"\s*:\s*"([^"]+)"', raw)
                    if mm:
                        play_url = mm.group(1).replace("\\/", "/")
        play_url = play_url.replace("\\/", "/")
        return {
            "parse": 0,
            "playUrl": "",
            "url": play_url,
            "header": {"User-Agent": self.UA, "Accept": "*/*"},
        }

    def localProxy(self, param):
        return [200, "video/MP2T", {}]
