# -*- coding: utf-8 -*-
"""
MOMO图库 - 修复封面/加载失败
兼容：蜂蜜 / 鱼壳 / 默影视 / OK / PeekPro

封面：中等尺寸直链（站点无防盗链），FongMi 自动走 proxy
播放：直连 / 带头 / 代理 三线路
分隔符：pics 内用 &&，兼容部分壳的 $$$
"""
import re
import json
import time
import requests
from urllib.parse import quote, unquote
from base.spider import Spider
from urllib3 import disable_warnings

disable_warnings()


class Spider(Spider):
    host = "https://www.momo777.cc/888"
    ref = "https://www.momo777.cc/"

    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Referer": "https://www.momo777.cc/",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "close",
    }

    img_headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Referer": "https://www.momo777.cc/",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    _cache = {}
    _CACHE_TTL = 600
    _pic_mode = None  # 'proxy' | 'direct'

    def getName(self):
        return "MOMO图库"

    def init(self, extend=""):
        self._pic_mode = None
        try:
            if isinstance(extend, str) and extend.strip().startswith("{"):
                e = json.loads(extend)
                m = str(e.get("pic", "")).lower().strip()
                if m in ("proxy", "ref", "referer", "direct"):
                    self._pic_mode = "proxy" if m == "proxy" else "direct"
        except Exception:
            pass

    def destroy(self):
        pass

    # ──────────────────── 工具 ────────────────────

    def _detect_pic_mode(self):
        """有 getProxyUrl → proxy；否则直链（站点无防盗链）"""
        if self._pic_mode in ("proxy", "direct"):
            return self._pic_mode
        mode = "direct"
        try:
            fn = getattr(self, "getProxyUrl", None)
            if callable(fn):
                for args in ((True,), ()):
                    try:
                        u = fn(*args)
                        if u and ("proxy" in str(u).lower() or "9978" in str(u) or str(u).startswith("http")):
                            mode = "proxy"
                            break
                    except Exception:
                        continue
        except Exception:
            pass
        self._pic_mode = mode
        print(f"[pic_mode] {mode}")
        return mode

    def _abs(self, url):
        if not url:
            return ""
        url = str(url).strip().split("@")[0].strip()
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host.rstrip("/") + url
        return url

    def _strip_size(self, pic):
        """去掉 WordPress -WxH 后缀"""
        if not pic:
            return ""
        return re.sub(r"-\d+x\d+(\.[a-zA-Z0-9]+)(?:\?.*)?$", r"\1", pic)

    def _pick_srcset(self, srcset, prefer="large"):
        """
        prefer:
          large  - 最大宽度（详情原图）
          cover  - 适中封面 400~900w，加载快且不易失败
        """
        if not srcset:
            return ""
        candidates = []
        for part in srcset.split(","):
            part = part.strip()
            if not part:
                continue
            bits = part.rsplit(" ", 1)
            u = bits[0].strip()
            w = 0
            if len(bits) == 2 and bits[1].endswith("w"):
                try:
                    w = int(bits[1][:-1])
                except Exception:
                    w = 0
            if u.startswith("http") or u.startswith("//"):
                candidates.append((w, self._abs(u)))
        if not candidates:
            return ""
        candidates.sort(key=lambda x: x[0])
        if prefer == "cover":
            # 优先 400~900，否则最接近 600
            mid = [c for c in candidates if 400 <= c[0] <= 900]
            if mid:
                return mid[-1][1]
            # 没有合适宽度就取中间那个
            return candidates[len(candidates) // 2][1]
        # large
        return candidates[-1][1]

    def _pic_for_list(self, pic):
        pic = self._abs(pic)
        if not pic:
            return ""
        # 封面不要强制原图，中等尺寸更稳
        mode = self._detect_pic_mode()
        if mode == "proxy":
            return "proxy://do=py&url=" + quote(pic, safe="")
        # 直链即可（实测无防盗链）；部分壳可再拼 Referer
        return pic

    def _is_valid_img(self, url):
        if not url or not str(url).startswith("http"):
            return False
        low = url.lower()
        skip = (
            ".gif", "wp-smiley", "emoji", "avatar", "logo", "matomo",
            "browserpreview", "/icon", "/loader", "loading", "spinner",
            "placeholder", "data:image", "svg+xml", "1x1", "pixel",
            "gravatar", "wp-includes",
        )
        if any(x in low for x in skip):
            return False
        return True

    def _to_pid(self, raw):
        """统一成帖子数字 id，避免 URL 里的 ?&= 干扰播放解析"""
        s = str(raw or "").strip()
        if "$" in s:
            s = s.split("$")[-1].strip()
        m = re.search(r"[?&]p=(\d+)", s)
        if m:
            return m.group(1)
        m = re.search(r"/(\d+)/?$", s.rstrip("/"))
        if m:
            return m.group(1)
        if s.isdigit():
            return s
        return s

    def _pid_url(self, pid):
        pid = str(pid).strip()
        if pid.startswith("http"):
            return pid
        return f"{self.host}/?p={pid}"

    # ──────────────────── 首页 ────────────────────

    def homeContent(self, filter):
        cats = [
            {"type_name": "写真集", "type_id": "cat=2"},
            {"type_name": "白丝", "type_id": "cat=3"},
            {"type_name": "黑丝", "type_id": "cat=4"},
            {"type_name": "蠢沫沫", "type_id": "tag=%E8%A0%A2%E6%B2%AB%E6%B2%AB"},
            {"type_name": "奈汐酱", "type_id": "tag=%E5%A5%88%E6%B1%90%E9%85%B1"},
            {"type_name": "奶桃桃", "type_id": "tag=%E5%A5%B6%E6%A1%83%E6%A1%83"},
            {"type_name": "白银", "type_id": "tag=%E7%99%BD%E9%93%B6"},
            {"type_name": "兔娘", "type_id": "tag=%E5%85%94%E5%A8%98"},
            {"type_name": "AT鲨", "type_id": "tag=at%e9%b2%a8"},
            {"type_name": "日奈娇", "type_id": "tag=%E6%97%A5%E5%A5%88%E5%A8%87"},
            {"type_name": "水淼", "type_id": "tag=%E6%B0%B4%E6%B7%BC"},
            {"type_name": "雨波", "type_id": "tag=%E9%9B%A8%E6%B3%A2"},
            {"type_name": "布丁大法", "type_id": "tag=%E5%B8%83%E4%B8%81%E5%A4%A7%E6%B3%95"},
            {"type_name": "桜井宁宁", "type_id": "tag=%E6%A1%9C%E4%BA%95%E5%AE%81%E5%AE%81"},
            {"type_name": "森萝", "type_id": "tag=%E6%A3%AE%E8%90%9D"},
            {"type_name": "小仓千代", "type_id": "tag=%E5%B0%8F%E4%BB%93%E5%8D%83%E4%BB%A3"},
            {"type_name": "鹿八岁", "type_id": "tag=%E9%B9%BF%E5%85%AB%E5%B2%81"},
            {"type_name": "迷之呆梨", "type_id": "tag=%E8%BF%B7%E4%B9%8B%E5%91%86%E6%A2%A8"},
            {"type_name": "七月喵子", "type_id": "tag=%E4%B8%83%E6%9C%88%E5%96%B5%E5%AD%90"},
            {"type_name": "轩萧学姐", "type_id": "tag=%E8%BD%A9%E8%90%A7%E5%AD%A6%E5%A7%90"},
            {"type_name": "星之迟迟", "type_id": "tag=%E6%98%9F%E4%B9%8B%E8%BF%9F%E8%BF%9F"},
            {"type_name": "一只毛毛", "type_id": "tag=%E4%B8%80%E5%8F%AA%E6%AF%9B%E6%AF%9B"},
            {"type_name": "抖娘利世", "type_id": "tag=%E6%8A%96%E5%A8%98%E5%88%A9%E4%B8%96"},
            {"type_name": "疯猫ss", "type_id": "tag=%E7%96%AF%E7%8C%ABss"},
            {"type_name": "雪晴", "type_id": "tag=%E9%9B%AA%E6%99%B4"},
            {"type_name": "是一只废喵了", "type_id": "tag=%E6%98%AF%E4%B8%80%E5%8F%AA%E5%BA%9F%E5%96%B5%E4%BA%86"},
            {"type_name": "九言", "type_id": "tag=%E4%B9%9D%E8%A8%80"},
            {"type_name": "脸红", "type_id": "tag=%E8%84%B8%E7%BA%A2"},
            {"type_name": "阿朱", "type_id": "tag=%E9%98%BF%E6%9C%B1"},
            {"type_name": "小瑶幺幺", "type_id": "tag=%E5%B0%8F%E7%91%B6%E5%B9%BA%E5%B9%BA"},
            {"type_name": "仙仙桃", "type_id": "tag=%E4%BB%99%E4%BB%99%E6%A1%83"},
            {"type_name": "猫九酱", "type_id": "tag=%E7%8C%AB%E4%B9%9D%E9%85%B1"},
            {"type_name": "樱岛麻衣", "type_id": "tag=%E6%A8%B1%E5%B2%9B%E9%BA%BB%E8%A1%A3"},
            {"type_name": "年年", "type_id": "tag=%E5%B9%B4%E5%B9%B4"},
            {"type_name": "小樱", "type_id": "tag=%E5%B0%8F%E6%A8%B1"},
            {"type_name": "邦尼", "type_id": "tag=%E9%82%A6%E5%B0%BC"},
            {"type_name": "梨霜儿", "type_id": "tag=%E6%A2%A8%E9%9C%9C%E5%84%BF"},
        ]
        return {"class": cats, "filters": {}, "list": []}

    # ──────────────────── 列表 / 搜索 ────────────────────

    def _fetch(self, url, timeout=12):
        try:
            r = requests.get(url, headers=self.headers, verify=False, timeout=timeout)
            r.encoding = "utf-8"
            return r.text if r.status_code == 200 else ""
        except Exception as e:
            print("fetch fail:", url, e)
            return ""

    def _parse_list(self, html):
        vod_list = []
        items = re.findall(
            r'<article[^>]*class=["\'][^"\']*satin-card[^"\']*["\'][^>]*>(.*?)</article>',
            html, re.S,
        )
        for item in items:
            href_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', item)
            if not href_m:
                continue
            href = href_m.group(1)
            if any(x in href for x in (".css", ".js", "wp-includes", "/category/", "/tag/", "#")):
                continue

            # 封面：优先 srcset 中等尺寸，其次 src
            pic = ""
            ss = re.search(r'srcset=["\']([^"\']+)["\']', item)
            if ss:
                pic = self._pick_srcset(ss.group(1), prefer="cover")
            if not pic:
                im = re.search(r'(?:data-src|src)=["\']([^"\']+)["\']', item)
                if im:
                    pic = self._abs(im.group(1))

            title_m = re.search(
                r'<h2[^>]*class=["\'][^"\']*satin-card__title[^"\']*["\'][^>]*><a[^>]*>(.*?)</a></h2>',
                item, re.S,
            )
            if not title_m:
                title_m = re.search(r"<h2[^>]*>(.*?)</h2>", item, re.S)
            name = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
            if not name or len(name) > 200:
                continue

            pid = self._to_pid(href)
            if not pid:
                continue

            vod_list.append({
                "vod_id": pid,
                "vod_name": name,
                "vod_pic": self._pic_for_list(pic),
                "vod_remarks": "点击查看",
                "style": {"type": "rect", "ratio": 0.75},
            })
        return vod_list

    def _pagecount(self, html, pg):
        total = pg
        nav = re.search(r'<ul class="page-numbers">(.*?)</ul>', html, re.S)
        if nav:
            nums = re.findall(r"<a[^>]+>(\d+)</a>", nav.group(1))
            if nums:
                try:
                    total = max(int(p) for p in nums)
                except Exception:
                    pass
        return total if total > pg else pg + 1

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1
        url = f"{self.host}/?{tid}&paged={pg}" if pg > 1 else f"{self.host}/?{tid}"
        try:
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": pg, "pagecount": 1, "limit": 20, "total": 0}
            return {
                "list": self._parse_list(html),
                "page": pg,
                "pagecount": self._pagecount(html, pg),
                "limit": 20,
                "total": 9999,
            }
        except Exception as e:
            print("categoryContent error:", e)
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if pg else 1
        url = f"{self.host}/page/{pg}/?s={key}" if pg > 1 else f"{self.host}/?s={key}"
        try:
            html = self._fetch(url)
            if not html:
                return {"list": [], "page": 1, "pagecount": 1, "limit": 20, "total": 0}
            vod_list = self._parse_list(html)
            for v in vod_list:
                v["vod_remarks"] = "搜索结果"
            return {
                "list": vod_list,
                "page": pg,
                "pagecount": self._pagecount(html, pg),
                "limit": 20,
                "total": 9999,
            }
        except Exception as e:
            print("searchContent error:", e)
            return {"list": []}

    # ──────────────────── 图集解析 ────────────────────

    def _cache_get(self, key):
        item = self._cache.get(key)
        if not item:
            return None
        ts, imgs = item
        if time.time() - ts > self._CACHE_TTL:
            self._cache.pop(key, None)
            return None
        return imgs

    def _cache_set(self, key, imgs):
        self._cache[key] = (time.time(), imgs)

    def _get_album_images(self, pid):
        pid = self._to_pid(pid)
        cached = self._cache_get(pid)
        if cached is not None:
            print(f"[cache] {pid} -> {len(cached)}")
            return cached

        detail_url = self._pid_url(pid)
        html = self._fetch(detail_url, timeout=15)
        if not html:
            return []

        images = []
        seen = set()

        def add(src, srcset=None):
            # 优先 srcset 最大；同时保留一份「原始 src」作兜底
            best = self._pick_srcset(srcset, prefer="large") if srcset else ""
            candidates = []
            if best:
                candidates.append(best)
                candidates.append(self._strip_size(best))
            if src:
                s = self._abs(src)
                candidates.append(s)
                candidates.append(self._strip_size(s))
            for c in candidates:
                c = self._abs(c)
                if self._is_valid_img(c) and c not in seen:
                    # 同一张图只留一个最终 URL：优先无尺寸后缀的原图
                    base = self._strip_size(c)
                    # 若已有同 base 的尺寸版，用原图替换
                    replaced = False
                    for i, old in enumerate(images):
                        if self._strip_size(old) == base:
                            if old != base and c == base:
                                images[i] = base
                                seen.discard(old)
                                seen.add(base)
                            replaced = True
                            break
                    if not replaced:
                        seen.add(c)
                        images.append(c)
                    break

        content = re.search(
            r'<div[^>]*class=["\'][^"\']*entry-content[^"\']*["\'][^>]*>(.*?)'
            r'(?:<div[^>]*class=["\'][^"\']*category-and-tags|</article>|</main>)',
            html, re.S,
        )
        region = content.group(1) if content else html

        for m in re.finditer(r"<img\b[^>]*>", region, re.I):
            tag = m.group(0)
            src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.I)
            ss_m = re.search(r'\bsrcset=["\']([^"\']+)["\']', tag, re.I)
            src = src_m.group(1) if src_m else ""
            ss = ss_m.group(1) if ss_m else ""
            if src or ss:
                add(src, ss)

        if not images:
            for m in re.finditer(r"<img\b[^>]*>", html, re.I):
                tag = m.group(0)
                src_m = re.search(r'\bsrc=["\']([^"\']+)["\']', tag, re.I)
                ss_m = re.search(r'\bsrcset=["\']([^"\']+)["\']', tag, re.I)
                src = src_m.group(1) if src_m else ""
                if src and any(d in src for d in ("momo777.cc", "wp-content/uploads", "wp.com", "mmtk6.com")):
                    add(src, ss_m.group(1) if ss_m else None)

        print(f"解析到 {len(images)} 张 pid={pid}")
        self._cache_set(pid, images)
        return images

    def detailContent(self, ids):
        out = []
        try:
            raw = ""
            if isinstance(ids, (list, tuple)) and ids:
                raw = str(ids[0]).strip()
            elif isinstance(ids, str):
                raw = ids.strip()
            pid = self._to_pid(raw)
            if not pid:
                return {"list": []}

            images = self._get_album_images(pid)
            title = pid
            try:
                html = self._fetch(self._pid_url(pid), timeout=10)
                h1 = re.search(
                    r'<h1[^>]*class=["\'][^"\']*satin-single-title[^"\']*["\'][^>]*>(.*?)</h1>',
                    html or "", re.S,
                )
                if not h1:
                    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html or "", re.S)
                if h1:
                    title = re.sub(r"<[^>]+>", "", h1.group(1)).strip()
                else:
                    t = re.search(r"<title>([^<]+)</title>", html or "", re.I)
                    if t:
                        title = re.sub(r"\s*[-|–—].*$", "", t.group(1)).strip() or pid
            except Exception:
                pass

            pic = images[0] if images else ""
            # 详情封面也用中等策略：若原图太大，客户端可能不显示
            cover = pic
            if pic:
                # 尝试给封面一个相对稳妥的 URL
                cover = pic

            out.append({
                "vod_id": pid,
                "vod_name": title,
                "vod_pic": self._pic_for_list(cover),
                "vod_content": title,
                "vod_play_from": "直连$$$带头$$$代理",
                "vod_play_url": f"direct${pid}$$$ref${pid}$$$proxy${pid}",
                "vod_player": "pics",
                "vod_remarks": (str(len(images)) + "P") if images else "",
            })
        except Exception as e:
            print("detailContent error:", e)
        return {"list": out}

    # ──────────────────── 播放 ────────────────────

    def playerContent(self, flag, id, vipFlags):
        try:
            mode = "direct"
            raw = str(id).strip()
            fl = str(flag or "").strip().lower()

            if "$" in raw:
                parts = raw.split("$")
                mode = (parts[0] or "direct").lower()
                pid = parts[-1]
            else:
                pid = raw

            if fl in ("带头", "ref", "referer"):
                mode = "ref"
            elif fl in ("代理", "proxy"):
                mode = "proxy"
            elif fl in ("直连", "direct"):
                mode = "direct"

            pid = self._to_pid(pid)
            if not pid:
                return {"parse": 0, "playUrl": "", "url": ""}

            images = self._get_album_images(pid)
            if not images:
                return {"parse": 0, "playUrl": "", "url": ""}

            ua = self.img_headers["User-Agent"]
            # 清理可能残留的 @ 后缀
            clean = [u.split("@")[0].strip() for u in images if u]

            if mode == "ref":
                tagged = [f"{u}@Referer={self.ref}&User-Agent={ua}" for u in clean]
                # 双分隔：部分壳认 &&，部分认 $$$
                url = "pics://" + "&&".join(tagged)
            elif mode == "proxy":
                proxied = ["proxy://do=py&url=" + quote(u, safe="") for u in clean]
                url = "pics://" + "&&".join(proxied)
            else:
                url = "pics://" + "&&".join(clean)

            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps(self.img_headers, ensure_ascii=False),
            }
        except Exception as e:
            print("playerContent error:", e)
            return {"parse": 0, "playUrl": "", "url": ""}

    # ──────────────────── 本地代理 ────────────────────

    def localProxy(self, params):
        try:
            url = params.get("url") or params.get("u") or ""
            if not url:
                return [404, "text/plain", b""]
            url = unquote(str(url))
            if not url.startswith("http"):
                m = re.search(r"(https?://[^\s&]+)", url)
                if m:
                    url = m.group(1)
            url = url.split("@")[0].strip()
            # 补全
            url = self._abs(url)
            r = requests.get(url, headers=self.img_headers, verify=False, timeout=20)
            if r.status_code != 200:
                # 原图失败时尝试不带尺寸还原的反向：有时只有缩略图存在
                alt = url
                # 已是原图则无更多动作
                print("localProxy status", r.status_code, url[-50:])
            ct = r.headers.get("Content-Type", "image/jpeg")
            if "image" not in (ct or "") and r.content[:3] not in (b"\xff\xd8\xff", b"\x89PN"):
                ct = "image/jpeg"
            return [r.status_code if r.status_code == 200 else 200, ct, r.content]
        except Exception as e:
            print("localProxy error:", e)
            return [404, "text/plain", b""]
