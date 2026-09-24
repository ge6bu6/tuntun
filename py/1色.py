# coding: utf-8
# 1色搜索 (1色) - 支持视频/小说/美图
# 站点: https://yism5.yise62.xyz/sp/

import re
import json
import urllib.parse
from urllib.parse import quote

from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://yism5.yise62.xyz"
        self.site_name = "1色"
        
        # 视频分类（纯数字ID）
        self.video_classes = [
            {"type_id": "253", "type_name": "🎬 强奸乱伦"},
            {"type_id": "254", "type_name": "🎬 明星换脸"},
            {"type_id": "258", "type_name": "🎬 SM专区"},
            {"type_id": "259", "type_name": "🎬 女同专区"},
            {"type_id": "247", "type_name": "🎬 AV解说"},
            {"type_id": "248", "type_name": "🎬 欧美专区"},
            {"type_id": "249", "type_name": "🎬 网曝门事件"},
            {"type_id": "240", "type_name": "🎬 中文字幕"},
            {"type_id": "241", "type_name": "🎬 无码专区"},
            {"type_id": "242", "type_name": "🎬 VR专区"},
            {"type_id": "245", "type_name": "🎬 日韩专区"},
            {"type_id": "239", "type_name": "🎬 伦理三级"},
            {"type_id": "238", "type_name": "🎬 性感主播"},
            {"type_id": "234", "type_name": "🎬 国产视频"},
            {"type_id": "246", "type_name": "🎬 精品动漫"},
            {"type_id": "236", "type_name": "🎬 传媒视频"},
            {"type_id": "264", "type_name": "🎬 制服诱惑"},
            {"type_id": "265", "type_name": "🎬 萝莉少女"},
            {"type_id": "266", "type_name": "🎬 乌鸦传媒"},
            {"type_id": "267", "type_name": "🎬 精东影业"},
            {"type_id": "268", "type_name": "🎬 蜜桃传媒"},
            {"type_id": "269", "type_name": "🎬 麻豆视频"},
            {"type_id": "270", "type_name": "🎬 乐播传媒"},
            {"type_id": "271", "type_name": "🎬 mini传媒"},
            {"type_id": "272", "type_name": "🎬 兔子先生"},
            {"type_id": "273", "type_name": "🎬 星空传媒"},
            {"type_id": "274", "type_name": "🎬 杏吧原创"},
            {"type_id": "275", "type_name": "🎬 天美传媒"},
            {"type_id": "276", "type_name": "🎬 大象传媒"},
            {"type_id": "277", "type_name": "🎬 皇家华人"},
            {"type_id": "278", "type_name": "🎬 糖心Vlog"},
            {"type_id": "279", "type_name": "🎬 91制片厂"},
            {"type_id": "280", "type_name": "🎬 性视界"},
            {"type_id": "282", "type_name": "🎬 乱伦精品"},
            {"type_id": "284", "type_name": "🎬 萝莉少女"},
        ]
        # 小说分类（前缀 novel_）
        self.novel_classes = [
            {"type_id": "novel_288", "type_name": "📖 玄幻仙侠"},
            {"type_id": "novel_287", "type_name": "📖 学生校园"},
            {"type_id": "novel_289", "type_name": "📖 明星偶像"},
            {"type_id": "novel_285", "type_name": "📖 暴力虐待"},
            {"type_id": "novel_290", "type_name": "📖 生活都市"},
            {"type_id": "novel_291", "type_name": "📖 不伦恋情"},
            {"type_id": "novel_292", "type_name": "📖 经验故事"},
            {"type_id": "novel_293", "type_name": "📖 科学幻想"},
        ]
        # 美图分类（前缀 image_）
        self.image_classes = [
            {"type_id": "image_294", "type_name": "🖼️ 露出偷窥"},
            {"type_id": "image_295", "type_name": "🖼️ Gif动图"},
            {"type_id": "image_296", "type_name": "🖼️ 亚洲性爱"},
            {"type_id": "image_297", "type_name": "🖼️ 卡通漫画"},
            {"type_id": "image_298", "type_name": "🖼️ 高跟丝袜"},
            {"type_id": "image_299", "type_name": "🖼️ 唯美清纯"},
            {"type_id": "image_300", "type_name": "🖼️ 网友自拍"},
            {"type_id": "image_301", "type_name": "🖼️ 欧美激情"},
        ]
        # 合并所有分类
        self.classes = self.video_classes + self.novel_classes + self.image_classes
        self.filters = {str(c["type_id"]): [] for c in self.classes}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
        }

    def getName(self):
        return "1色"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        try:
            result = self.categoryContent("234", "1", False, None)
            return {"list": result.get("list", [])[:15]}
        except:
            return {"list": []}

    def categoryContent(self, tid, pg, filter, extend):
        pg = str(pg) if pg else "1"
        tid = str(tid)
        
        if tid.startswith("novel_"):
            real_tid = tid.replace("novel_", "")
            items, page_count = self._fetch_art_list(real_tid, pg, "novel")
            return {
                "list": items,
                "page": int(pg),
                "pagecount": page_count if page_count > 0 else 1,
                "limit": 20,
                "total": page_count * 20 if page_count > 0 else 20,
            }
        elif tid.startswith("image_"):
            real_tid = tid.replace("image_", "")
            items, page_count = self._fetch_art_list(real_tid, pg, "image")
            return {
                "list": items,
                "page": int(pg),
                "pagecount": page_count if page_count > 0 else 1,
                "limit": 20,
                "total": page_count * 20 if page_count > 0 else 20,
            }
        else:
            url = f"{self.host}/sp/index.php/vod/type/id/{tid}/page/{pg}.html"
            html = self._fetch_html(url)
            items = self._parse_video_list(html)
            page_count = self._parse_page_count(html)
            return {
                "list": items,
                "page": int(pg),
                "pagecount": page_count if page_count > 0 else 1,
                "limit": 20,
                "total": page_count * 20 if page_count > 0 else 20,
            }

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]) if isinstance(ids, list) else str(ids)
        
        if vid.startswith("novel_"):
            return self._detail_novel(vid)
        elif vid.startswith("image_"):
            return self._detail_image(vid)
        else:
            return self._detail_video(vid)

    def _detail_video(self, vid):
        detail_url = f"{self.host}/sp/index.php/vod/detail/id/{vid}.html"
        html = self._fetch_html(detail_url)
        if not html:
            return {"list": []}

        title = self._extract_title(html) or f"视频{vid}"
        pic = self._extract_pic(html) or ""
        remark = self._extract_remark(html) or ""
        content = self._extract_content(html) or ""
        actor = self._extract_actor(html) or ""
        director = self._extract_director(html) or ""

        play_url = self._extract_m3u8_from_html(html)
        if play_url:
            # 清理反斜杠
            play_url = play_url.replace("\\/", "/")
        if not play_url:
            play_page_url = f"{self.host}/sp/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            play_html = self._fetch_html(play_page_url)
            if play_html:
                play_url = self._extract_m3u8_from_html(play_html)
                if play_url:
                    play_url = play_url.replace("\\/", "/")

        if play_url:
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}",
            }
        else:
            play_page_url = f"{self.host}/sp/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remark,
                "vod_content": content,
                "vod_actor": actor,
                "vod_director": director,
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_page_url}",
            }
        return {"list": [vod]}
    def _detail_novel(self, vid):
        real_vid = vid.replace("novel_", "")
        url = f"{self.host}/sp/index.php/art/detail/id/{real_vid}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        
        title = self._extract_title(html) or f"小说{real_vid}"
        pic = self._extract_pic(html) or ""
        
        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": "阅读",
            "vod_play_url": f"阅读$novel://{real_vid}",
        }
        return {"list": [vod]}

    def _detail_image(self, vid):
        real_vid = vid.replace("image_", "")
        url = f"{self.host}/sp/index.php/art/detail/id/{real_vid}.html"
        html = self._fetch_html(url)
        if not html:
            return {"list": []}
        
        title = self._extract_title(html) or f"图集{real_vid}"
        pic = self._extract_pic(html) or ""
        images = self._parse_image_list_from_detail(html)
        
        if images:
            pic_urls = "&&".join(images)
            play_url = f"pics://{pic_urls}"
            play_from = "图片浏览"
        else:
            play_url = ""
            play_from = ""

        vod = {
            "vod_id": vid,
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": f"{len(images)}张图片" if images else "",
            "vod_content": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_play_from": play_from,
            "vod_play_url": play_url,
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        pg = str(pg) if pg else "1"
        url = f"{self.host}/sp/index.php/vod/search/page/{pg}/wd/{quote(key)}.html"
        html = self._fetch_html(url)
        items = self._parse_video_list(html)
        return {"list": items, "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        headers = {
            "User-Agent": self.headers.get("User-Agent", ""),
            "Referer": self.host + "/",
        }
        
        if id and id.startswith("novel://"):
            novel_id = id.replace("novel://", "")
            url = f"{self.host}/sp/index.php/art/detail/id/{novel_id}.html"
            html = self._fetch_html(url)
            if html:
                content = self._parse_novel_content(html)
                payload = json.dumps({"title": "小说内容", "content": content}, ensure_ascii=False)
                return {"parse": 0, "url": f"novel://{payload}", "header": headers}
            return {"parse": 0, "url": id, "header": headers}
        
        if id and id.startswith("pics://"):
            return {"parse": 0, "url": id, "header": headers}
        
        if id and id.startswith("http") and ".m3u8" in id:
            proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(str(id), safe="")
            return {"parse": 0, "url": proxy_url, "header": headers}
        
        if id and id.startswith("http") and "/play/" in id:
            html = self._fetch_html(id)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(str(play_url), safe="")
                return {"parse": 0, "url": proxy_url, "header": headers}
            return {"parse": 1, "url": id, "header": headers}
        
        if id:
            play_page_url = f"{self.host}/sp/index.php/vod/play/id/{id}/sid/1/nid/1.html"
            html = self._fetch_html(play_page_url)
            play_url = self._extract_m3u8_from_html(html)
            if play_url:
                proxy_url = self.getProxyUrl() + "?do=py&url=" + quote(str(play_url), safe="")
                return {"parse": 0, "url": proxy_url, "header": headers}
            return {"parse": 1, "url": play_page_url, "header": headers}
        
        return {"parse": 1, "url": "", "header": headers}

    def recommendContent(self, ids):
        return {"list": []}

    def destroy(self):
        pass

    def getProxyUrl(self):
        return "http://127.0.0.1:9978/proxy"

    def localProxy(self, param):
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")

            if target.startswith("url="):
                target = target[4:]
            target = urllib.parse.unquote(str(target or ""))

            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=15)
            if not resp:
                return [502, "text/plain", b"fetch failed"]

            content = getattr(resp, "content", b"") or b""
            if not content and hasattr(resp, "text") and resp.text:
                content = resp.text.encode("utf-8", errors="ignore")

            if not content:
                return [502, "text/plain", b"empty content"]

            text = content.decode("utf-8", errors="ignore")
            if "#EXTM3U" not in text:
                if target.endswith(".ts"):
                    return [200, "video/mp2t", content]
                return [200, "application/octet-stream", content]

            cleaned = self._clean_m3u8(text, target)
            return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]

        except Exception as e:
            error_msg = f"localProxy error: {str(e)}".encode("utf-8", errors="ignore")
            return [500, "text/plain", error_msg]

    def _clean_m3u8(self, text, source_url):
        lines = [line.strip() for line in str(text or "").replace("\r", "").split("\n") if line.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 处理多码率 Master Playlist (主 m3u8 代理嵌套)
        if any(line.startswith("#EXT-X-STREAM-INF") for line in lines):
            out = []
            for line in lines:
                if line.startswith("#"):
                    out.append(line)
                else:
                    child = urllib.parse.urljoin(source_url, line)
                    if ".m3u8" in child.lower():
                        out.append(self.getProxyUrl() + "?do=py&url=" + quote(str(child), safe=""))
                    else:
                        out.append(child)
            return "\n".join(out) + "\n"

        parsed = urllib.parse.urlparse(source_url)
        source_dir = parsed.path.rsplit('/', 1)[0] + '/' if parsed.path else '/'

        # 从 #EXT-X-KEY 提取正片目录（更准确）
        main_dir = source_dir
        for line in lines:
            if line.startswith("#EXT-X-KEY") and "URI=" in line:
                uri_match = re.search(r'URI="([^"]+)"', line)
                if uri_match:
                    key_path = uri_match.group(1)
                    if not key_path.startswith("http"):
                        key_dir = key_path.rsplit('/', 1)[0] + '/' if '/' in key_path else ''
                        if key_dir and key_dir != '/':
                            main_dir = key_dir
                            break

        segments = []
        pending = []

        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urllib.parse.urljoin(source_url, line) if not line.startswith(('http://', 'https://')) else line
                media_parsed = urllib.parse.urlparse(media_url)

                # 过滤逻辑：判断分片路径是否以正片目录开头
                is_ad = not media_parsed.path.startswith(main_dir)

                if not is_ad:
                    segments.extend(pending)
                    segments.append(media_url)
                pending = []
                continue

            if not line.startswith("#"):
                segments.append(urllib.parse.urljoin(source_url, line))
            else:
                segments.append(line)

        # 二次清洗：去除孤立/连续的 #EXT-X-DISCONTINUITY 和 KEY:METHOD=NONE
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in ("#EXT-X-KEY:METHOD=NONE", "#EXT-X-DISCONTINUITY"):
                if not out or out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
                    continue
            out.append(line)

        # 清理尾部多余的标记
        while len(out) > 1 and out[-1] in ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE"):
            out.pop()

        if out and out[0] != "#EXTM3U":
            out.insert(0, "#EXTM3U")

        return "\n".join(out) + "\n"
    def _rewrite_m3u8_tag(self, line, source_url):
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urllib.parse.urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urllib.parse.urljoin(source_url, line)
        return line

    def _fetch_html(self, url, params=None):
        full_url = url
        if params:
            if "?" in url:
                full_url = url + "&" + urllib.parse.urlencode(params)
            else:
                full_url = url + "?" + urllib.parse.urlencode(params)
        try:
            resp = self.fetch(full_url, headers=self.headers, timeout=15)
            if resp is None:
                return ""
            if hasattr(resp, "text"):
                return resp.text
            if hasattr(resp, "content"):
                if isinstance(resp.content, bytes):
                    try:
                        return resp.content.decode('utf-8', errors='ignore')
                    except:
                        pass
                return str(resp.content)
            if hasattr(resp, "body"):
                return resp.body
            if hasattr(resp, "data"):
                return resp.data
            if isinstance(resp, dict):
                if "body" in resp:
                    return resp["body"]
                if "text" in resp:
                    return resp["text"]
                if "content" in resp:
                    return resp["content"]
            if isinstance(resp, str):
                return resp
            return str(resp)
        except Exception as e:
            return ""

    def _fetch_art_list(self, tid, pg, content_type):
        url = f"{self.host}/sp/index.php/art/type/id/{tid}/page/{pg}.html"
        html = self._fetch_html(url)
        items = []
        if not html:
            return items, 1
        
        prefix = "novel_" if content_type == "novel" else "image_"
        name_suffix = "小说" if content_type == "novel" else "图集"
        
        pattern = r'<li[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for link, title in matches:
            if '/art/detail/id/' not in link:
                continue
            vid_match = re.search(r'/art/detail/id/(\d+)\.html', link)
            if vid_match:
                vid = prefix + vid_match.group(1)
                items.append({
                    "vod_id": vid,
                    "vod_name": title.strip() if title else f"未知{name_suffix}",
                    "vod_pic": "",
                    "vod_remarks": ""
                })
        
        page_count = self._parse_page_count(html)
        return items, page_count

    def _parse_video_list(self, html):
        items = []
        if not html:
            return items
        li_pattern = r'<li[^>]*>.*?<div[^>]*class="[^"]*stui-vodlist__box[^"]*"[^>]*>(.*?)</div>.*?</li>'
        li_matches = re.findall(li_pattern, html, re.DOTALL)
        
        for box_html in li_matches:
            thumb_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*data-original="([^"]+)"', box_html)
            if not thumb_match:
                continue
            play_link = thumb_match.group(1)
            pic = thumb_match.group(2)
            
            remark_match = re.search(r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]*)</span>', box_html)
            remark = remark_match.group(1).strip() if remark_match else ""
            
            title_match = re.search(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>', box_html, re.DOTALL)
            if not title_match:
                continue
            detail_link = title_match.group(1)
            title = title_match.group(2).strip()
            
            vid_match = re.search(r'/detail/id/(\d+)\.html', detail_link)
            if vid_match:
                vid = vid_match.group(1)
                items.append({
                    "vod_id": vid,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return items

    def _parse_page_count(self, html):
        if not html:
            return 1
        pattern = r'<a[^>]*data-num="(\d+)"[^>]*>'
        matches = re.findall(pattern, html)
        if matches:
            return int(matches[-1])
        pattern2 = r'/page/(\d+)\.html'
        matches2 = re.findall(pattern2, html)
        if matches2:
            nums = [int(x) for x in matches2]
            return max(nums) if nums else 1
        return 1

    def _extract_title(self, html):
        pattern = r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</h1>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return match.group(1).strip()
        pattern2 = r'<h1[^>]*>([^<]+)</h1>'
        match2 = re.search(pattern2, html)
        if match2:
            return match2.group(1).strip()
        return ""

    def _extract_pic(self, html):
        pattern = r'<img[^>]*data-original="([^"]+)"[^>]*>'
        match = re.search(pattern, html)
        if match:
            return match.group(1)
        pattern2 = r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*thumb[^"]*"'
        match2 = re.search(pattern2, html)
        if match2:
            return match2.group(1)
        return ""

    def _extract_remark(self, html):
        pattern = r'<span[^>]*class="[^"]*pic-text[^"]*"[^>]*>([^<]+)</span>'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_content(self, html):
        pattern = r'<div[^>]*class="[^"]*vod_content[^"]*"[^>]*>([^<]+)</div>'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            return re.sub(r'<[^>]+>', '', match.group(1)).strip()
        return ""

    def _extract_actor(self, html):
        pattern = r'<span[^>]*>演员：</span>([^<]+)'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_director(self, html):
        pattern = r'<span[^>]*>导演：</span>([^<]+)'
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_play_url_from_button(self, html):
        pattern = r'<a[^>]*class="[^"]*play-btn[^"]*"[^>]*href="([^"]+)"[^>]*>'
        match = re.search(pattern, html)
        if match:
            return match.group(1)
        return ""

    def _extract_play_data(self, html):
        play_from_list = []
        play_url_list = []
        tab_pattern = r'<li[^>]*data-tab="([^"]+)"[^>]*>(.*?)</li>'
        tabs = re.findall(tab_pattern, html, re.DOTALL)
        if tabs:
            for tab_id, tab_name in tabs:
                list_pattern = rf'<div[^>]*id="tab-{tab_id}"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>([^<]*)</a>'
                matches = re.findall(list_pattern, html, re.DOTALL)
                if matches:
                    play_from_list.append(re.sub(r'<[^>]+>', '', tab_name).strip())
                    eps = []
                    for href, ep_name in matches:
                        ep_name_clean = re.sub(r'<[^>]+>', '', ep_name).strip()
                        eps.append(f"{ep_name_clean}${href}")
                    play_url_list.append("#".join(eps))
        if not play_from_list:
            play_script = re.search(r'var\s+playList\s*=\s*(\{[^;]+\});', html, re.DOTALL)
            if play_script:
                try:
                    data = json.loads(play_script.group(1))
                    for key, value in data.items():
                        if isinstance(value, list) and value:
                            play_from_list.append(key)
                            eps = []
                            for item in value:
                                if isinstance(item, dict):
                                    name = item.get("name", "")
                                    url = item.get("url", "")
                                    if name and url:
                                        eps.append(f"{name}${url}")
                                elif isinstance(item, str):
                                    eps.append(item)
                            play_url_list.append("#".join(eps))
                except:
                    pass
        if not play_from_list:
            play_url_single = self._extract_play_url_from_button(html)
            if play_url_single:
                return "播放", f"播放${play_url_single}"
        return "$$$".join(play_from_list), "$$$".join(play_url_list)

    def _extract_m3u8_from_html(self, html):
        if not html:
            return None
        pattern = r'var\s+player_aaaa\s*=\s*({[^;]+?});'
        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                json_str = match.group(1)
                data = json.loads(json_str)
                url = data.get("url", "")
                if url and url.startswith("http") and ".m3u8" in url:
                    return url
            except:
                url_pattern = r'"url"\s*:\s*"([^"]+)"'
                url_match = re.search(url_pattern, json_str)
                if url_match:
                    url = url_match.group(1)
                    if url.startswith("http") and ".m3u8" in url:
                        return url
        pattern2 = r'"url"\s*:\s*"([^"]+\.m3u8[^"]*)"'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(1)
            if url.startswith("http") and ".m3u8" in url:
                return url
        pattern3 = r'https?://[^"\']+\.m3u8[^"\']*'
        match3 = re.search(pattern3, html)
        if match3:
            return match3.group(0)
        return None

    def _parse_novel_content(self, html):
        if not html:
            return ""
        
        html_clean = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html_clean = re.sub(r'<style[^>]*>.*?</style>', '', html_clean, flags=re.DOTALL)
        
        text = re.sub(r'<br\s*/?>', '\n', html_clean, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if len(line) < 5:
                continue
            if any(keyword in line for keyword in [
                '视频板块', '小说板块', '美图板块', '版权所有', '联系邮箱', '声明', '警告',
                '合作联系方式', '强奸乱伦', '明星换脸', 'SM专区', '女同专区', 'AV解说',
                '欧美专区', '网曝门事件', '中文字幕', '无码专区', 'VR专区', '日韩专区',
                '伦理三级', '性感主播', '国产视频', '精品动漫', '传媒视频', '制服诱惑',
                '萝莉少女', '乌鸦传媒', '精东影业', '蜜桃传媒', '麻豆视频', '乐播传媒',
                'mini传媒', '兔子先生', '星空传媒', '杏吧原创', '天美传媒', '大象传媒',
                '皇家华人', '糖心Vlog', '91制片厂', '性视界', '乱伦精品', '玄幻仙侠',
                '学生校园', '明星偶像', '暴力虐待', '生活都市', '不伦恋情', '经验故事',
                '科学幻想', '露出偷窥', 'Gif动图', '亚洲性爱', '卡通漫画', '高跟丝袜',
                '唯美清纯', '网友自拍', '欧美激情', '缅北爆料', '淫乱继母', 'UU15岁艹',
                '暗网人畜', '猎奇重口'
            ]):
                continue
            if re.match(r'^[\d\s，。、；：！？""''（）\u3000]+$', line):
                continue
            filtered_lines.append(line)
        
        result = '\n'.join(filtered_lines)
        
        if len(result) < 100:
            text_raw = re.sub(r'<[^>]+>', ' ', html_clean)
            text_raw = re.sub(r'\s+', ' ', text_raw).strip()
            for marker in ['目', '第一回', '第一章']:
                idx = text_raw.find(marker)
                if idx != -1:
                    start = max(0, idx - 10)
                    end = text_raw.find('来源：', start)
                    if end == -1:
                        end = text_raw.find('人气：', start)
                    if end == -1:
                        end = text_raw.find('更新：', start)
                    if end == -1:
                        end = len(text_raw)
                    result = text_raw[start:end].strip()
                    result = re.sub(r'\s+', ' ', result)
                    parts = result.split('。')
                    result = '\n'.join([p.strip() + '。' for p in parts if len(p.strip()) > 5])
                    break
        
        if len(result) > 10000:
            result = result[:10000]
        
        return result

    def _parse_image_list_from_detail(self, html):
        images = []
        if not html:
            return images
        
        ad_domains = ['aispsp02.top', 'img.aimga.top', 'pan.qianfan.app']
        
        pattern = r'<img[^>]*data-original="([^"]+)"[^>]*>'
        matches = re.findall(pattern, html)
        for url in matches:
            is_ad = False
            for ad in ad_domains:
                if ad in url:
                    is_ad = True
                    break
            if not is_ad and url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                images.append(url)
        
        if images:
            return images
        
        pattern2 = r'<img[^>]*src="([^"]+)"[^>]*>'
        matches2 = re.findall(pattern2, html)
        for url in matches2:
            is_ad = False
            for ad in ad_domains:
                if ad in url:
                    is_ad = True
                    break
            if not is_ad and url.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                images.append(url)
        
        return images

    def _fetch_and_clean_m3u8(self, url):
        """获取m3u8内容并清理广告分片"""
        try:
            resp = self.fetch(url, headers=self.headers, timeout=15)
            if not resp:
                return None
            text = ""
            if hasattr(resp, "text"):
                text = resp.text
            elif hasattr(resp, "content"):
                if isinstance(resp.content, bytes):
                    text = resp.content.decode('utf-8', errors='ignore')
                else:
                    text = str(resp.content)
            elif isinstance(resp, str):
                text = resp
            if not text:
                return None
            if "#EXTM3U" not in text:
                return None
            cleaned = self._clean_m3u8(text, url)
            return cleaned
        except Exception as e:
            return None