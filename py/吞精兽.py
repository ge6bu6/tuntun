# coding: utf-8
# 站点：吞精兽
# 域名：https://pde.tjs4.beer
# 备用域名：https://jfl.ccavx.com/0/ (发布页)
# 类型：成人影视站 (HTML解析)
# 特点：分类列表 /vodtype/{tid}-{page}.html，详情页内联 m3u8
# 最后验证：2026-09-04
# m3u8 结构：多码率，锚点 /20260902/buAt7BCx/1500kb/hls/，可疑广告目录 /20260731/UTxI1Mxv/9567kb/hls/
# 需要清洗：是 (suspicious_ad_dirs 非空)

import re
import json
from urllib.parse import urljoin, quote, unquote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://pde.tjs4.beer"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/"
        }
        self.classes = [
            {"type_id": "20", "type_name": "国产自拍"},
            {"type_id": "21", "type_name": "制服丝袜"},
            {"type_id": "22", "type_name": "强奸乱伦"},
            {"type_id": "23", "type_name": "教师学生"},
            {"type_id": "24", "type_name": "素人系列"},
            {"type_id": "25", "type_name": "人妻熟女"},
            {"type_id": "26", "type_name": "日韩无码"},
            {"type_id": "27", "type_name": "日韩有码"},
            {"type_id": "28", "type_name": "中文字幕"},
            {"type_id": "29", "type_name": "欧美风情"},
            {"type_id": "30", "type_name": "经典伦理"},
            {"type_id": "31", "type_name": "卡通动漫"}
        ]
        self.filters = {}
        for c in self.classes:
            self.filters[c["type_id"]] = []

    def getName(self):
        return "吞精兽"

    def getDependence(self):
        return []

    def init(self, extend=""):
        pass

    def homeContent(self, filter=False):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter=False):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页推荐：抓取首页视频列表
        try:
            res = self.fetch(self.host + "/cn/home/web/", headers=self.headers)
            if not res:
                return {"list": []}
            html = res.text
            items = self._parse_video_list(html)
            return {"list": items}
        except Exception as e:
            self.log("homeVideoContent error: " + str(e))
            return {"list": []}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        page = pg or "1"
        url = f"{self.host}/vodtype/{tid}-{page}.html"
        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}
            html = res.text
            items = self._parse_video_list(html)
            # 解析总页数
            total_pages = self._parse_total_pages(html)
            return {
                "list": items,
                "page": int(page),
                "pagecount": total_pages or 1,
                "limit": 20,
                "total": 0
            }
        except Exception as e:
            self.log("categoryContent error: " + str(e))
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        # 使用 urljoin 构建完整 URL
        from urllib.parse import urljoin
        url = urljoin(self.host + "/", vod_id)
        if not url.startswith("http"):
            url = self.host + "/" + vod_id
        try:
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}
            # 优先使用 content，兼容沙盒环境
            html = ""
            if hasattr(res, "content") and res.content:
                try:
                    html = res.content.decode("utf-8", errors="ignore")
                except:
                    html = str(res.content)
            elif hasattr(res, "text") and res.text:
                html = res.text
            else:
                return {"list": []}
            if not html or len(html) < 100:
                return {"list": []}
            # 提取标题
            title_match = re.search(r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)</h1>', html)
            if not title_match:
                title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
            title = title_match.group(1).strip() if title_match else "未知标题"
            # 使用多级方法提取 m3u8
            play_url = self._extract_m3u8_from_html(html)
            # 提取图片
            pic_match = re.search(r'data-original="([^"]+)"', html)
            pic = pic_match.group(1) if pic_match else ""
            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": "成人",
                "vod_content": "",
                "vod_play_from": "播放",
                "vod_play_url": f"播放${play_url}" if play_url else ""
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        # 该站搜索接口为 /s/index.html?wd=xxx
        try:
            url = f"{self.host}/s/index.html?wd={quote(key)}"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": [], "page": 1}
            html = res.text
            items = self._parse_video_list(html)
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log("searchContent error: " + str(e))
            return {"list": [], "page": 1}

    def playerContent(self, flag, id, vipFlags):
        if not id:
            return {"parse": 0, "url": "", "header": {}}
        # 清洗 ID
        play_url = str(id).strip()
        # 提取干净的 m3u8 地址
        clean_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', play_url)
        if clean_match:
            play_url = clean_match.group(1)
        if play_url and ".m3u8" in play_url:
            # 需要清洗广告分片，走 localProxy
            return {
                "parse": 0,
                "url": self._m3u8_proxy_url(play_url),
                "header": {"User-Agent": self.headers["User-Agent"]}
            }
        return {"parse": 1, "url": play_url, "header": self.headers}

    def recommendContent(self, ids, pg):
        # 推荐使用详情页底部的"猜你喜欢"
        if not ids:
            return {"list": []}
        vod_id = ids[0]
        try:
            url = f"{self.host}/{vod_id}.html"
            res = self.fetch(url, headers=self.headers)
            if not res:
                return {"list": []}
            html = res.text
            # 提取"猜你喜欢"区域
            pattern = r'<h2 class="widget-title">猜你喜欢</h2>(.*?)</div>'
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                return {"list": []}
            section = match.group(1)
            items = self._parse_recommend_list(section)
            return {"list": items}
        except Exception as e:
            self.log("recommendContent error: " + str(e))
            return {"list": []}

    def destroy(self):
        pass

    def localProxy(self, param):
        """m3u8 代理 + 广告分片过滤（五层管线）"""
        try:
            if isinstance(param, dict):
                target = param.get("url", "") or param.get("source", "")
            else:
                target = str(param or "")
            if target.startswith("url="):
                target = target[4:]
            elif "url=" in target:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(target).query)
                if "url" in qs:
                    target = qs["url"][0]
            target = unquote(str(target or ""))
            if not target or not re.match(r"^https?://", target, re.I):
                return [400, "text/plain", b"invalid url"]

            resp = self.fetch(target, headers=self.headers, timeout=20)
            if not resp:
                return [502, "text/plain", b"fetch failed"]
            content = getattr(resp, "content", b"") or b""
            if not content and getattr(resp, "text", ""):
                content = resp.text.encode("utf-8", errors="ignore")
            if not content:
                return [502, "text/plain", b"empty content"]

            if b"#EXTM3U" in content[:256]:
                cleaned = self._clean_m3u8(content.decode("utf-8", errors="ignore"), target)
                return [200, "application/vnd.apple.mpegurl", cleaned.encode("utf-8")]
            return [200, "application/octet-stream", content]
        except Exception as e:
            self.log("localProxy error: " + str(e))
            return [500, "text/plain", f"localProxy error: {e}".encode("utf-8", errors="ignore")]

    def _m3u8_proxy_url(self, url):
        if url:
            url = url.replace("\\/", "/")
        return "http://127.0.0.1:9978/proxy?do=py&url=" + quote(str(url or ""), safe="")

    def _clean_m3u8(self, text, source_url):
        """五层管线清洗"""
        lines = [l.strip() for l in str(text or "").replace("\r", "").split("\n") if l.strip()]
        if not lines:
            return "#EXTM3U\n"

        # 第1层：图片流伪装检测
        if self._is_fake_image_stream(text, source_url):
            restored = text
            for ext in (".png", ".jpeg", ".jpg", ".webp"):
                restored = restored.replace(ext, ".ts")
            self.log("检测到图片流伪装，已还原扩展名 -> .ts，跳过广告过滤")
            return restored

        # 第2层：多码率主表
        if any(l.startswith("#EXT-X-STREAM-INF") for l in lines):
            return self._clean_m3u8_multi(lines, source_url)

        # 第3层：正片目录锚点
        main_dir = self._resolve_main_dir(lines, source_url)

        # 第4层：分片过滤
        segments, removed, kept = self._filter_segments(lines, source_url, main_dir)

        # 第5层：全滤兜底
        if removed > 0 and (kept == 0 or removed > kept):
            self.log(f"广告过滤命中过多分片(滤{removed}/留{kept})，判定锚点失效，回退为不过滤模式")
            out = [self._rewrite_m3u8_tag(l, source_url) for l in lines]
            return "\n".join(out) + "\n"

        if removed:
            self.log(f"m3u8已过滤广告分片: {removed}个，保留正片: {kept}个")

        # 第5层：冗余标签清理
        out = self._dedup_tags(segments, source_url)
        return "\n".join(out) + "\n"

    def _is_fake_image_stream(self, text, source_url):
        """检测图片流伪装 - 只有分片扩展名全部为图片格式且不存在 .ts/.m4s 时才判定为 True"""
        if not text:
            return False
        has_ts = False
        has_image_ext = False
        for line in str(text or "").split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            low = line.lower().split("?")[0]
            if low.endswith((".ts", ".m4s")):
                has_ts = True
            elif low.endswith((".png", ".jpg", ".jpeg", ".webp")):
                has_image_ext = True
        
        # 只有存在图片格式分片且不存在 ts/m4s 分片时，才判定为图片流
        if has_image_ext and not has_ts:
            return True
        
        # 域名特征作为辅助（优先级低于分片扩展名）
        low_url = (source_url or "").lower()
        if "imgcdn" in low_url or "doyinapi" in low_url or "photo" in low_url:
            if not has_ts:
                return True
        
        return False

    def _clean_m3u8_multi(self, lines, source_url):
        """多码率主表透传"""
        out = []
        for line in lines:
            if line.startswith("#"):
                out.append(line)
            else:
                child = urljoin(source_url, line)
                if ".m3u8" in child.lower():
                    out.append(self._m3u8_proxy_url(child))
                else:
                    out.append(child)
        return "\n".join(out) + "\n"

    def _resolve_main_dir(self, lines, source_url):
        """正片目录锚点：KEY URI 目录优先"""
        import posixpath
        parsed = re.match(r'^(https?://[^/]+)', source_url)
        if not parsed:
            return "/"
        base_url = parsed.group(1)
        parsed_path = re.sub(r'^https?://[^/]+', '', source_url)
        main_dir = posixpath.dirname(parsed_path)
        if not main_dir.endswith("/"):
            main_dir += "/"
        # 优先以 KEY URI 目录为锚点
        for line in lines:
            if not line.startswith("#EXT-X-KEY") or "URI=" not in line:
                continue
            m = re.search(r'URI="([^"]+)"', line)
            if not m:
                continue
            key_uri = m.group(1)
            if not key_uri.startswith("http"):
                key_uri = urljoin(source_url, key_uri)
            key_path = re.sub(r'^https?://[^/]+', '', key_uri)
            key_dir = posixpath.dirname(key_path)
            if key_dir and key_dir != "/":
                return key_dir + "/"
        return main_dir

    def _filter_segments(self, lines, source_url, main_dir):
        """分片过滤"""
        segments = []
        pending = []
        removed = 0
        kept = 0
        for line in lines:
            if line.startswith("#EXTINF"):
                pending = [line]
                continue
            if pending and line.startswith("#"):
                pending.append(line)
                continue
            if pending:
                media_url = urljoin(source_url, line)
                media_path = re.sub(r'^https?://[^/]+', '', media_url)
                if media_path.startswith(main_dir):
                    segments.extend(pending)
                    segments.append(media_url)
                    kept += 1
                else:
                    removed += 1
                pending = []
                continue
            if line.startswith("#"):
                segments.append(line)
            else:
                segments.append(urljoin(source_url, line))
        return segments, removed, kept

    def _dedup_tags(self, segments, source_url):
        """冗余标签清理"""
        NOISE = ("#EXT-X-DISCONTINUITY", "#EXT-X-KEY:METHOD=NONE")
        out = []
        for line in segments:
            line = self._rewrite_m3u8_tag(line, source_url)
            if line in NOISE:
                if not out or out[-1] in NOISE:
                    continue
            out.append(line)
        while len(out) > 1 and out[-1] in NOISE:
            out.pop()
        return out

    def _rewrite_m3u8_tag(self, line, source_url):
        """标签 URI 补全"""
        if line.startswith("#EXT-X-KEY") or line.startswith("#EXT-X-MAP"):
            def repl(match):
                uri = match.group(1)
                if uri.startswith(("http://", "https://")):
                    return 'URI="' + uri + '"'
                return 'URI="' + urljoin(source_url, uri) + '"'
            return re.sub(r'URI="([^"]+)"', repl, line)
        if line and not line.startswith("#"):
            if line.startswith(("http://", "https://")):
                return line
            return urljoin(source_url, line)
        return line

    def _parse_video_list(self, html):
        """解析视频列表"""
        items = []
        # 匹配 .thumb-block 中的 a 标签
        pattern = r'<article[^>]*class="[^"]*thumb-block[^"]*"[^>]*>.*?<a href="/([^"]+)" title="([^"]+)".*?data-original="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for vod_id, title, pic in matches:
            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items
    def _extract_m3u8_from_html(self, html):
        """从HTML中提取m3u8播放地址（多级兜底）"""
        if not html:
            return None
        # 方法1: 从 rawUrl 变量提取
        pattern = r"rawUrl\s*=\s*['\"]([^'\"]+\.m3u8[^'\"]*)['\"]"
        match = re.search(pattern, html)
        if match:
            url = match.group(1)
            # 清洗多余参数
            clean_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', url)
            if clean_match:
                return clean_match.group(1)
            return url
        # 方法2: 直接搜索任何 m3u8 链接
        pattern2 = r'https?://[^"\'<>]+\.m3u8[^"\'<>]*'
        match2 = re.search(pattern2, html)
        if match2:
            url = match2.group(0)
            # 去掉可能的尾部引号或多余字符
            clean_match = re.search(r'(https?://[^\s$#]+\.m3u8(?:\?[^\s#]*)?)', url)
            if clean_match:
                return clean_match.group(1)
            return url
        # 方法3: 从 player_data 中提取
        pattern3 = r'var\s+player_data\s*=\s*(\{[^;]+\});'
        match3 = re.search(pattern3, html, re.DOTALL)
        if match3:
            try:
                import json
                data = json.loads(match3.group(1))
                url = data.get("url", "")
                if url and ".m3u8" in url:
                    url = url.replace("\\/", "/")
                    return url
            except:
                pass
        return None

    def _parse_total_pages(self, html):
        """解析总页数"""
        # 从分页器中提取总页数
        pattern = r'<a[^>]*href="[^"]*-\d+\.html"[^>]*>(\d+)</a>'
        matches = re.findall(pattern, html)
        if matches:
            # 取最大的页码作为总页数
            pages = [int(m) for m in matches if m.isdigit()]
            if pages:
                return max(pages)
        return 1

    def _parse_recommend_list(self, html):
        """解析推荐列表"""
        items = []
        pattern = r'<a href="/([^"]+)" title="([^"]+)".*?data-original="([^"]+)"'
        matches = re.findall(pattern, html, re.DOTALL)
        for vod_id, title, pic in matches:
            if vod_id and title:
                items.append({
                    "vod_id": vod_id,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return items