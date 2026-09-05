# -*- coding: utf-8 -*-
# 青牛影院 (m.artxyzy.com) 专用 OK影视爬虫插件

import sys
import re
import json
import time
import hmac
import hashlib
import os
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
requests.packages.urllib3.disable_warnings()

from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "青牛影院"

    def init(self, extend=""):
        super().init(extend)
        self.site_url = "https://m.artxyzy.com"
        # 多线路源：看剧AI（接口风格参考；当前其签名 API 被网关 403，保留框架待恢复/替换可达接口）
        self.kj_url = "https://kanju.ai"
        self.kj_api_secret = "557d0e4ae929f438da6bd84412374e6086b8af09b3fed54bf22601d5bf8c54a0"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
            "Referer": self.site_url,
            "Origin": self.site_url,
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        self.kj_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.kj_url + "/",
            "Origin": self.kj_url,
        }
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.sess.mount("http://", HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])))
        self.page_size = 24
        self.total = 9999
        self.default_pic = "https://pic.rmb.bdstatic.com/bjh/user/default.png"
        self.log("init done. 注意：当前青牛站点与看剧AI API 均存在 403 反爬，多线路框架已就绪，需源可达后生效。")

    def log(self, msg):
        try:
            sys.stdout.write("[青牛影院] " + str(msg) + "\n")
            sys.stdout.flush()
        except Exception:
            pass

    def fetch(self, url, timeout=10):
        try:
            res = self.sess.get(url, headers=self.headers, timeout=timeout, verify=False)
            res.encoding = "utf-8"
            return res
        except Exception as e:
            self.log("fetch error: " + repr(e) + " url=" + url)
            return None

    # ================= 看剧AI 风格：签名 + resolve 多线路框架 =================

    def _kj_sign_headers(self, method, path_with_search):
        ts = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        msg = "{0}\n{1}\n{2}\n{3}".format(method, path_with_search, ts, nonce)
        sig = hmac.new(self.kj_api_secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
        return {
            **self.kj_headers,
            "x-ai-movie-timestamp": ts,
            "x-ai-movie-nonce": nonce,
            "x-ai-movie-signature": sig,
        }

    def _kj_api_get(self, path):
        url = self.kj_url + path
        headers = self._kj_sign_headers("GET", path)
        try:
            resp = self.sess.get(url, headers=headers, timeout=12, verify=False)
            if not resp or resp.status_code != 200:
                self.log("kj api non-200: " + str(getattr(resp, "status_code", "None")) + " path=" + path)
                return {}
            return json.loads(resp.text)
        except Exception as e:
            self.log("kj api exception: " + repr(e) + " path=" + path)
            return {}

    def _is_valid_video_url(self, url):
        if not url:
            return False
        u = url.lower()
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
            if ext in u:
                return False
        return True

    def _resolve_token_to_real_url(self, token, selected_provider="", flag=""):
        """看剧AI 风格：用 playback token 解析出真实播放地址。

        返回 (real_url, header) 或 (None, None)。依次尝试：
          1) line_options 中 m3u8/mp4/hls 直链（按选中线路 + preference_weight 排序）；
          2) resolve_ticket 类型调用 resolve-line 换真实地址。
        """
        if not token or not token.startswith("YJ-"):
            return (None, None)
        path = "/v1/playback/resolve/" + urllib.parse.quote(token)
        data = self._kj_api_get(path)
        line_options = data.get("line_options", []) or []
        if not line_options:
            self.log("resolve: 无 line_options, token=" + token[:40])
            return (None, None)

        def is_selected(opt):
            if selected_provider and opt.get("provider_id") == selected_provider:
                return True
            if selected_provider and opt.get("play_from") == selected_provider:
                return True
            if flag and opt.get("provider_name") == flag:
                return True
            return False

        sorted_lines = sorted(line_options, key=lambda x: (not is_selected(x), -x.get("preference_weight", 0)))

        for line in sorted_lines:
            raw_url = line.get("url", "")
            if not raw_url:
                continue
            url_kind = line.get("url_kind", "")
            if url_kind in ["m3u8", "mp4", "hls"] and raw_url.startswith("http"):
                if self._is_valid_video_url(raw_url):
                    return (raw_url, {"User-Agent": self.kj_headers["User-Agent"], "Referer": self.kj_url + "/"})
            if url_kind == "resolve_ticket":
                ticket = raw_url.replace("resolve://", "")
                if not ticket:
                    continue
                payload = {
                    "ticket": ticket,
                    "line": line.get("playback_source_id", ""),
                    "provider_id": line.get("provider_id", ""),
                    "play_from": line.get("play_from", ""),
                }
                try:
                    resp = self.sess.post(self.kj_url + "/v1/playback/resolve-line",
                                          headers={**self._kj_sign_headers("POST", "/v1/playback/resolve-line"),
                                                   "Content-Type": "application/json"},
                                          data=json.dumps(payload, ensure_ascii=False), timeout=12, verify=False)
                    line_data = json.loads(resp.text) if resp and resp.ok else {}
                    real = (line_data.get("line") or {}).get("url", "")
                except Exception as e:
                    self.log("resolve-line exception: " + repr(e))
                    continue
                if real and self._is_valid_video_url(real):
                    return (real, {"User-Agent": self.kj_headers["User-Agent"], "Referer": self.kj_url + "/"})
        return (None, None)

    # ================= 首页 =================

    def homeContent(self, filter):
        cate_list = [
            {"type_name": "电视剧", "type_id": "dianshiju"},
            {"type_name": "电影", "type_id": "dianying"},
            {"type_name": "动漫", "type_id": "dongman"},
            {"type_name": "综艺", "type_id": "zongyi"},
            {"type_name": "短剧大全", "type_id": "duanjudaquan"},
            {"type_name": "体育", "type_id": "tiyu"},
            {"type_name": "电影解说", "type_id": "dianyingjieshuo"}
        ]
        videos = []
        kj_data = self._kj_api_get("/v1/feed/home")
        if kj_data:
            seen = set()
            for sec in kj_data.get("sections", []):
                for card in sec.get("cards", []):
                    vid = card.get("id", "")
                    if not vid or vid in seen:
                        continue
                    seen.add(vid)
                    videos.append({
                        "vod_id": vid,
                        "vod_name": card.get("title", "") or "",
                        "vod_pic": card.get("poster_url", "") or self.default_pic,
                        "vod_remarks": card.get("remarks", "") or "",
                        "style": {"type": "rect", "ratio": 1.33}
                    })
        return {"class": cate_list, "list": videos[:30], "filters": {}}

    # ================= 列表解析 =================

    def _parse_list_html(self, html):
        video_list = []
        for li in re.finditer(r'<li[^>]*>(.*?)</li>', html, re.S):
            item = li.group(1)
            if "/voddetail/" not in item or "data-original" not in item:
                continue
            m_id = re.search(r'<a[^>]+href="(/voddetail/[^"]+\.html)"[^>]*title="([^"]*)"', item)
            if not m_id:
                continue
            vod_id = m_id.group(1)
            vod_name = m_id.group(2).strip()
            if not vod_name:
                m_h3 = re.search(r'<h3>.*?</h3>', item, re.S)
                if m_h3:
                    vod_name = re.sub(r'<[^>]+>', '', m_h3.group(0)).strip()
            if not vod_name:
                continue
            m_pic = re.search(r'<div class="img-wrapper lazyload img-wrapper-pic"[^>]*data-original="([^"]+)"', item)
            if not m_pic:
                m_pic = re.search(r'<div class="img-wrapper lazyload"[^>]*data-original="([^"]+)"', item)
            if not m_pic:
                m_pic = re.search(r'data-original="([^"]+)"', item)
            pic_url = m_pic.group(1) if m_pic else ""
            if pic_url.startswith("//"):
                pic_url = "https:" + pic_url
            elif pic_url and not pic_url.startswith(("http://", "https://")):
                pic_url = self.site_url + (pic_url if pic_url.startswith("/") else "/" + pic_url)
            m_remarks = re.search(r'<p class="item-status[^"]*">(.*?)</p>', item, re.S)
            vod_remarks = re.sub(r'<[^>]+>', '', m_remarks.group(1)).strip() if m_remarks else ""
            if any(v["vod_id"] == vod_id for v in video_list):
                continue
            video_list.append({
                "vod_id": vod_id, "vod_name": vod_name, "vod_pic": pic_url,
                "vod_remarks": vod_remarks, "style": {"type": "rect", "ratio": 1.33}
            })
        return video_list

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if str(pg).isdigit() else 1
        kind_map = {"dianshiju": "series", "dianying": "movie", "dongman": "anime",
                    "zongyi": "variety", "duanjudaquan": "short_drama"}
        kind = kind_map.get(tid, "")
        videos = []
        if kind:
            data = self._kj_api_get("/v1/browse/catalog?kind={0}&page={1}&limit={2}".format(kind, pg, 30))
            for card in (data.get("cards") or []):
                if not card.get("id"):
                    continue
                videos.append({
                    "vod_id": card["id"],
                    "vod_name": card.get("title", "") or "",
                    "vod_pic": card.get("poster_url", "") or self.default_pic,
                    "vod_remarks": card.get("remarks", "") or "",
                    "style": {"type": "rect", "ratio": 1.33}
                })
        if not videos:
            list_url = "{0}/vodshow/{1}--time---------{2}.html".format(self.site_url, tid, pg)
            res = self.fetch(list_url)
            if res and res.ok:
                videos = self._parse_list_html(res.text)
            else:
                self.log("categoryContent: 青牛 HTML 不可用(可能403), tid=" + tid)
        pagecount = pg + 1 if len(videos) else pg
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": self.page_size, "total": self.total}

    # ================= 详情 =================

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        if not vod_id:
            return {"list": [{"vod_name": "视频ID为空"}]}
        if isinstance(vod_id, str) and (vod_id.startswith("av_") or vod_id.startswith("YJ-")):
            return self._detail_from_kj(vod_id)

        detail_url = vod_id if vod_id.startswith("http") else self.site_url + vod_id
        res = self.fetch(detail_url)
        if not res or not res.ok:
            return {"list": [{"vod_id": vod_id, "vod_name": "视频详情解析失败(站点403/不可达)"}]}
        html = res.text

        vod_name = "未知名称"
        m_title = re.search(r'<h3><a[^>]+href="/voddetail/[^"]+"[^>]*>(.*?)</a></h3>', html, re.S)
        if m_title:
            vod_name = re.sub(r'<[^>]+>', '', m_title.group(1)).strip()
        else:
            m_title2 = re.search(r'<title>([^<]+)</title>', html)
            if m_title2:
                vod_name = re.sub(r'[\s\-].*', '', m_title2.group(1).strip()).strip()

        vod_pic = ""
        m_pic = re.search(r'<div class="pic"><img[^>]+data-original="([^"]+)"', html)
        if m_pic:
            vod_pic = m_pic.group(1)
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic and not vod_pic.startswith(("http://", "https://")):
                vod_pic = self.site_url + vod_pic

        vod_remarks = ""
        m_status = re.search(r'<span[^>]*>状态：(.*?)</span>', html, re.S)
        if m_status:
            vod_remarks = re.sub(r'<[^>]+>', '', m_status.group(1)).strip()

        type_name = ""
        m_type = re.search(r'<div class="mbx_left[^"]*">.*?</a>&nbsp;»&nbsp;<a[^>]+>([^<]+)</a>', html, re.S)
        if m_type:
            type_name = m_type.group(1).strip()

        vod_content = ""
        m_intro = re.search(r'<div class="text text-row text-row-2">(.*?)</div>', html, re.S)
        if m_intro:
            vod_content = re.sub(r'<[^>]+>', '', m_intro.group(1)).strip()

        tab_map = {}
        for m in re.finditer(r'<li[^>]*class="[^"]*ewave-tab[^"]*"[^>]*data-target="([^"]+)"[^>]*>(.*?)</li>', html, re.S):
            target = m.group(1).strip()
            name = re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if "- " in name:
                name = name.split("- ", 1)[-1].strip()
            tab_map[target] = name or "默认线路"
        if not tab_map:
            tab_map = {"#ewave-playlist-1": "默认线路"}

        lines = []
        name_counter = {}
        for target, line_name in tab_map.items():
            pid = target.lstrip("#")
            pattern = r'<ul[^>]*class="[^"]*ewave-playlist-(?:sort-)?content[^"]*"[^>]*id="' + re.escape(pid) + r'"[^>]*>(.*?)</ul>'
            m_block = re.search(pattern, html, re.S)
            if not m_block:
                continue
            block = m_block.group(1)
            episodes = []
            seen = set()
            for em in re.finditer(r'<a[^>]+href="(/vodplay/[^"]+\.html)"[^>]*>(.*?)</a>', block, re.S):
                ep_url = em.group(1)
                ep_name = re.sub(r'<[^>]+>', '', em.group(2)).strip()
                if ep_url and ep_name and ep_url not in seen:
                    seen.add(ep_url)
                    m_ep = re.match(r'第(\d+)集$', ep_name)
                    if m_ep:
                        ep_name = "第{0:02d}集".format(int(m_ep.group(1)))
                    episodes.append("{0}${1}".format(ep_name, ep_url))
            if not episodes:
                continue
            base_name = line_name
            if base_name in name_counter:
                name_counter[base_name] += 1
                display_name = "{0}-{1}".format(base_name, name_counter[base_name])
            else:
                name_counter[base_name] = 1
                display_name = base_name
            lines.append((display_name, episodes))

        if not lines:
            all_eps = re.findall(r'<a[^>]+href="(/vodplay/[^"]+\.html)"[^>]*>(.*?)</a>', html, re.S)
            if all_eps:
                eps = []
                seen = set()
                for ep_url, ep_text in all_eps:
                    ep_name = re.sub(r'<[^>]+>', '', ep_text).strip()
                    if ep_url and ep_name and ep_url not in seen:
                        seen.add(ep_url)
                        m_ep = re.match(r'第(\d+)集$', ep_name)
                        if m_ep:
                            ep_name = "第{0:02d}集".format(int(m_ep.group(1)))
                        eps.append("{0}${1}".format(ep_name, ep_url))
                if eps:
                    lines.append(("默认线路", eps))

        if not lines:
            return {"list": [{"vod_id": vod_id, "vod_name": vod_name, "vod_play_from": "", "vod_play_url": ""}]}

        play_from = "|".join([l[0] for l in lines])
        play_url = "$$$".join(["#".join(l[1]) for l in lines])
        return {"list": [{"vod_id": vod_id, "vod_name": vod_name, "vod_pic": vod_pic,
                          "vod_remarks": vod_remarks, "type_name": type_name, "vod_content": vod_content,
                          "vod_play_from": play_from, "vod_play_url": play_url}]}

    def _detail_from_kj(self, vid):
        """看剧AI 风格详情：catalog 接口拿信息 + episodes token，按线路生成多线路播放列表"""
        data = self._kj_api_get("/v1/catalog/{0}".format(vid))
        if not data or "id" not in data:
            return {"list": [{"vod_id": vid, "vod_name": "看剧AI详情接口不可用(403/失效)"}]}
        title = data.get("title", "") or ""
        pic = data.get("poster_url", "") or self.default_pic
        content = data.get("description", "") or ""
        actor = " / ".join((data.get("actors") or [])[:20])
        director = " / ".join((data.get("directors") or [])[:10])
        year = str(data["year"]) if data.get("year") else ""
        area = data.get("area", "") or ""
        type_name = " / ".join((data.get("genres") or [])[:5])

        episodes = data.get("episodes", [])
        if not episodes:
            episodes = (self._kj_api_get("/v1/catalog/{0}/episodes".format(vid)) or {}).get("episodes", [])

        play_from, play_url = [], []
        if episodes:
            first_token = ""
            for ep in episodes:
                if ep.get("token"):
                    first_token = ep["token"]
                    break
            valid_lines = []
            if first_token:
                resolve_data = self._kj_api_get("/v1/playback/resolve/{0}".format(urllib.parse.quote(first_token)))
                for opt in (resolve_data.get("line_options") or []):
                    if not opt.get("url"):
                        continue
                    pid = opt.get("provider_id")
                    if any(v.get("provider_id") == pid for v in valid_lines):
                        continue
                    valid_lines.append(opt)
                def rank(o):
                    kind = o.get("url_kind", "")
                    nm = (o.get("provider_name") or "").lower()
                    if kind == "resolve_ticket":
                        return 2
                    if "资源" in nm:
                        return 0
                    return 1
                valid_lines.sort(key=lambda x: (-rank(x), -x.get("preference_weight", 0)))

            def make_eps(eps, provider_id=""):
                out = []
                suf = "@@{0}".format(provider_id) if provider_id else ""
                for ep in eps:
                    et = ep.get("title", "") or ""
                    if not et:
                        et = "第{0}集".format(ep["number"]) if ep.get("number") is not None else "播放"
                    tk = ep.get("token", "")
                    if not tk:
                        continue
                    out.append("{0}${1}{2}".format(et, tk, suf))
                return out

            if valid_lines:
                for line in valid_lines:
                    pn = line.get("provider_name") or line.get("label") or "默认线路"
                    pid = line.get("provider_id") or ""
                    play_from.append(pn)
                    ep_list = make_eps(episodes, pid)
                    if ep_list:
                        play_url.append("#".join(ep_list))
            if not play_from:
                play_from.append("默认线路")
                play_url.append("#".join(make_eps(episodes)))

        if not play_from:
            play_from.append("默认线路")
            play_url.append("播放${0}/v1/catalog/{1}".format(self.kj_url, vid))

        return {"list": [{"vod_id": vid, "vod_name": title, "vod_pic": pic, "vod_content": content,
                          "vod_actor": actor, "vod_director": director, "vod_year": year, "vod_area": area,
                          "vod_type": type_name, "vod_play_from": "$$$".join(play_from),
                          "vod_play_url": "$$$".join(play_url)}]}

    # ================= 搜索 =================

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg) if str(pg).isdigit() else 1
        videos = []
        data = self._kj_api_get("/v1/browse/catalog?q={0}&page={1}&limit={2}".format(urllib.parse.quote(key), pg, 30))
        for card in (data.get("cards") or []):
            if not card.get("id"):
                continue
            videos.append({
                "vod_id": card["id"],
                "vod_name": card.get("title", "") or "",
                "vod_pic": card.get("poster_url", "") or self.default_pic,
                "vod_remarks": card.get("remarks", "") or "",
                "style": {"type": "rect", "ratio": 1.33}
            })
        if not videos:
            keyword = requests.utils.quote(key)
            search_url = "{0}/vodsearch/-------------.html?wd={1}&page={2}".format(self.site_url, keyword, pg)
            res = self.fetch(search_url)
            if res and res.ok:
                videos = self._parse_list_html(res.text)
            else:
                self.log("searchContent: 青牛 HTML 搜索不可用(可能403), key=" + key)
        pagecount = pg + 1 if len(videos) else pg
        return {"list": videos, "page": pg, "pagecount": pagecount, "limit": self.page_size,
                "total": len(videos) if len(videos) < self.total else self.total}

    # ================= 播放 =================

    def playerContent(self, flag, id, vipFlags):
        raw_id = id.split("$")[-1].strip() if "$" in id else id.strip()
        token = raw_id
        selected_provider = ""
        if "@@" in token:
            token, selected_provider = token.split("@@", 1)
        token = token.strip()

        if token.startswith("http") and (".m3u8" in token or ".mp4" in token):
            return {"parse": 0, "url": token, "header": {"User-Agent": self.kj_headers["User-Agent"], "Referer": self.kj_url + "/"}}
        if token.startswith("YJ-"):
            real, hdr = self._resolve_token_to_real_url(token, selected_provider, flag)
            if real:
                return {"parse": 0, "url": real, "header": hdr}
            return {"parse": 1, "url": "{0}/yj/{1}".format(self.kj_url, token.replace("YJ-", "")), "header": self.kj_headers}

        play_url = raw_id
        if not play_url:
            return {"parse": 0, "url": "", "header": self.headers}
        play_url = play_url if play_url.startswith("http") else self.site_url + play_url
        res = self.fetch(play_url)
        if not res or not res.ok:
            return {"parse": 0, "url": "", "header": self.headers}
        html = res.text
        m = re.search(r'var\s+player_\w+\s*=\s*({.*?})</script>', html, re.S)
        if m:
            try:
                data = json.loads(m.group(1))
                real_url = data.get("url", "")
                if real_url:
                    return {"parse": 0, "url": real_url, "header": self.headers}
            except Exception:
                pass
        m = re.search(r'(https?://[^\s\'"<>]+\.m3u8)', html)
        if m:
            return {"parse": 0, "url": m.group(1), "header": self.headers}
        m = re.search(r'(https?://[^\s\'"<>]+\.mp4)', html)
        if m:
            return {"parse": 0, "url": m.group(1), "header": self.headers}
        return {"parse": 0, "url": "", "header": self.headers}
