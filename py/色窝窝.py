# -*- coding: utf-8 -*-
"""
色窝窝 TVBox 四壳通用 Spider
站点: https://vkcxvjk.aa-swwsss879aass.cyou/
类型: 苹果CMS v10 + mytheme主题
协议: TVBox / 影视仓 / OK影视 / PickTV 四壳通用
"""

import re
import json
import gzip
import io

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    import urllib.request
    import urllib.parse
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


class Spider:
    # 站点基础配置
    baseUrl = "https://vkcxvjk.aa-swwsss879aass.cyou"
    rawSite = "https://vkcxvjk.aa-swwsss879aass.cyou"
    siteUrl = "https://vkcxvjk.aa-swwsss879aass.cyou"
    HOST = siteUrl

    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
          "AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/131.0.0.0 Safari/537.36")

    # 分类定义: type_id -> 脱敏后分类名
    # 原始分类名经古典映射脱敏，未成年相关分类(教师学生ID=31)已剔除
    CLASS_MAP = {
        "1": "东瀛素纱",
        "2": "华夏主播",
        "3": "东瀛精品",
        "4": "西洋劲爆",
        "25": "风月丹青",
        "26": "窥帘自拍",
        "27": "丰盈尤物",
        "28": "玉露系列",
        "29": "含朱视频",
        "30": "弄玉系列",
        "32": "合卺换妻",
        "33": "AI换脸",
        "34": "中文字幕",
        "35": "罗敷系列",
        "36": "官衣诱惑",
        "37": "强占禁脔",
        "38": "AV明星",
        "39": "直播裸聊",
    }

    # 古典映射脱敏词典（铁律11）
    CLASSICAL_MAP = {
        "成人": "风月", "色情": "春宫", "淫": "风月", "黄色": "春宫",
        "淫秽": "猥亵", "激情": "云雨", "做爱": "云雨", "性交": "交欢",
        "欲": "情思", "高潮": "云端", "偷拍": "窥帘", "偷窥": "窥帘",
        "乱伦": "禁脔", "乱论": "禁脔", "强奸": "强占", "轮奸": "群辱",
        "迷奸": "迷占", "无码": "素纱", "有码": "遮面", "熟女": "徐娘",
        "萝莉": "豆蔻", "幼女": "玉蕊", "少女": "碧玉", "学生": "书生",
        "人妻": "罗敷", "少妇": "艳妇", "御姐": "玉人", "护士": "药女",
        "教师": "先生", "医生": "郎中", "警察": "捕快", "军人": "军爷",
        "巨乳": "丰盈", "爆乳": "丰盈", "胸": "酥胸", "乳": "玉兔",
        "臀": "玉臀", "屁股": "玉臀", "脚": "莲步", "玉足": "莲步",
        "腿": "玉腿", "裸体": "玉体", "全裸": "玉体", "半裸": "半褪",
        "自慰": "弄玉", "口交": "含朱", "口活": "含朱", "肛交": "后庭",
        "群交": "合卺", "群P": "合卺", "丝袜": "丝履", "网袜": "网履",
        "内衣": "亵衣", "内裤": "亵裤", "情趣": "风月", "春药": "催情",
        "暴力": "杀伐", "血腥": "殷红", "恐怖": "幽冥", "赌博": "孤注",
        "毒品": "药石", "国产": "华夏", "日韩": "东瀛", "欧美": "西洋",
        "港台": "香江", "动漫": "丹青", "综艺": "百戏", "电视剧": "传奇",
        "电影": "光影", "颜射": "玉露", "制服": "官衣", "换妻": "换妻",
        "主播": "主播", "直播": "直播", "裸聊": "裸聊", "自拍": "自拍",
        "中出": "中出", "内射": "内射",
    }

    # 未成年相关关键词（铁律13，命中即剔除）
    MINOR_KEYWORDS = [
        "萝莉", "幼女", "少女", "学生", "童", "未成年", "teen", "loli",
        "schoolgirl", "school", "13岁", "14岁", "15岁", "初中", "高中",
        "豆蔻", "玉蕊", "碧玉", "书生", "稚子",
    ]

    def __init__(self):
        self.extend = {}
        self._session = None
        if HAS_REQUESTS:
            try:
                self._session = requests.Session()
                self._session.headers.update({
                    "User-Agent": self.UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                })
                self._session.verify = False
                # 禁用SSL警告
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                except Exception:
                    pass
            except Exception:
                self._session = None

    # ========== 工具方法 ==========

    def _get(self, url, timeout=15):
        """HTTP GET 请求 - 优先requests，fallback urllib"""
        # 方式1: requests库（TVBox Chaquo环境首选）
        if self._session is not None:
            try:
                resp = self._session.get(url, timeout=timeout,
                                          headers={"Referer": self.siteUrl + "/"})
                if resp.status_code == 200:
                    resp.encoding = resp.apparent_encoding or "utf-8"
                    return resp.text
                return ""
            except Exception:
                pass  # fallback到urllib

        # 方式2: urllib.request
        if HAS_URLLIB:
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": self.UA,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                    "Accept-Encoding": "gzip, deflate",
                    "Referer": self.siteUrl + "/",
                })
                resp = urllib.request.urlopen(req, timeout=timeout)
                data = resp.read()
                # 处理gzip压缩
                if resp.headers.get("Content-Encoding", "").lower() == "gzip":
                    try:
                        data = gzip.decompress(data)
                    except Exception:
                        try:
                            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
                        except Exception:
                            pass
                # 尝试解码
                for enc in ["utf-8", "gbk", "gb2312"]:
                    try:
                        return data.decode(enc)
                    except (UnicodeDecodeError, LookupError):
                        continue
                return data.decode("utf-8", errors="ignore")
            except Exception:
                return ""

        return ""

    def desensitize(self, text):
        """古典映射脱敏（铁律11）"""
        if not text:
            return text
        result = text
        for k, v in self.CLASSICAL_MAP.items():
            result = result.replace(k, v)
        return result

    def _is_minor(self, text):
        """检测是否含未成年相关内容（铁律13）"""
        if not text:
            return False
        low = text.lower()
        for kw in self.MINOR_KEYWORDS:
            if kw.lower() in low:
                return True
        return False

    def _parse_vod_list(self, html):
        """解析视频列表页（分类页/搜索页通用，兼容两种卡片结构）"""
        vod_list = []
        seen_ids = set()
        # 通用匹配：所有 myui-vodlist__thumb 链接（分类页 box 结构 + 搜索页 thumb 结构）
        pattern = re.compile(
            r'<a[^>]*class="[^"]*myui-vodlist__thumb[^"]*"[^>]*'
            r'href="(/detail/\?(\d+)\.html)"[^>]*'
            r'(?:title="([^"]*)")?[^>]*'
            r'data-original="([^"]*)"',
            re.DOTALL
        )
        for m in pattern.finditer(html):
            vod_id = m.group(2)
            if vod_id in seen_ids:
                continue
            seen_ids.add(vod_id)
            vod_name = (m.group(3) or "").strip()
            vod_pic = m.group(4).strip()
            # 如果title为空，从h4.title中补
            if not vod_name:
                # 在该a标签附近找h4标题
                nearby = html[max(0, m.start()-200):m.end()+500]
                tm = re.search(r'<h4[^>]*class="[^"]*title[^"]*"[^>]*>\s*<a[^>]*>([^<]+)</a>', nearby)
                if tm:
                    vod_name = tm.group(1).strip()
            # 未成年内容剔除（铁律13）
            if self._is_minor(vod_name):
                continue
            # 脱敏（铁律11）
            vod_name = self.desensitize(vod_name)
            # 修复封面URL
            if vod_pic.startswith("//"):
                vod_pic = "https:" + vod_pic
            elif vod_pic.startswith("/"):
                vod_pic = self.siteUrl + vod_pic
            # 去除 #err 后缀
            vod_pic = vod_pic.split("#")[0]
            vod_list.append({
                "vod_id": vod_id,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_remarks": "",
            })
        return vod_list

    def _parse_page_info(self, html):
        """解析分页信息，返回 (page, pagecount, limit, total)"""
        page = 1
        pagecount = 1
        total = 0
        # 尝试匹配分页栏中的总页数/总数
        m = re.search(r'共(\d+)条', html)
        if m:
            total = int(m.group(1))
        m = re.search(r'(\d+)\s*/\s*(\d+)\s*页', html)
        if m:
            page = int(m.group(1))
            pagecount = int(m.group(2))
        # 匹配分页链接中的最大页码
        pages = re.findall(r'/list/\?\d+-(\d+)\.html|search\.php\?[^"]*page=(\d+)', html)
        max_p = 0
        for p1, p2 in pages:
            p = int(p1) if p1 else (int(p2) if p2 else 0)
            if p > max_p:
                max_p = p
        if max_p > pagecount:
            pagecount = max_p
        if total > 0 and pagecount == 1:
            pagecount = (total + 19) // 20  # 假设每页20条
        limit = 20
        return page, pagecount, limit, total

    def _parse_detail(self, html, vod_id):
        """解析详情页，返回视频详情字典"""
        vod = {
            "vod_id": vod_id,
            "vod_name": "",
            "vod_pic": "",
            "vod_content": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_year": "",
            "vod_area": "",
            "vod_play_from": "",
            "vod_play_url": "",
        }

        # 标题
        m = re.search(r'<h1[^>]*class="[^"]*title[^"]*"[^>]*>(.*?)</h1>', html, re.DOTALL)
        if m:
            vod["vod_name"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not vod["vod_name"]:
            m = re.search(r'<title>《?([^》<]+)》?[^<]*</title>', html)
            if m:
                vod["vod_name"] = m.group(1).strip()

        # 封面
        m = re.search(r'data-original="([^"]+)"', html)
        if m:
            pic = m.group(1).strip()
            if pic.startswith("//"):
                pic = "https:" + pic
            elif pic.startswith("/"):
                pic = self.siteUrl + pic
            vod["vod_pic"] = pic.split("#")[0]

        # 简介
        m = re.search(r'<div class="tab-content myui-panel_bd">([^<]+)</div>', html)
        if m:
            vod["vod_content"] = m.group(1).strip()

        # 年份
        m = re.search(r'年份：</span><a[^>]*>(\d+)', html)
        if m:
            vod["vod_year"] = m.group(1)

        # 主演
        m = re.search(r'主演：</span>(.*?)</p>', html, re.DOTALL)
        if m:
            vod["vod_actor"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 导演
        m = re.search(r'导演：</span>(.*?)</p>', html, re.DOTALL)
        if m:
            vod["vod_director"] = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        # 播放线路 - 从 tab 导航提取线路名
        play_froms = []
        for m in re.finditer(r'<li><a href="#playlist(\d+)"[^>]*>([^<]+)</a></li>', html):
            play_froms.append(m.group(2).strip())

        # 播放集数 - 从每个 playlist div 中提取
        play_urls_parts = []
        for idx, pf in enumerate(play_froms):
            playlist_id = idx + 1
            # 匹配该线路下的集数链接
            pattern = re.compile(
                r'id="playlist' + str(playlist_id) + r'".*?'
                r'<ul[^>]*class="[^"]*sort-list[^"]*"[^>]*>(.*?)</ul>',
                re.DOTALL
            )
            m = pattern.search(html)
            episodes = []
            if m:
                for em in re.finditer(
                    r'<li[^>]*><a[^>]*title="([^"]*)"[^>]*href="/video/\?(\d+)-(\d+)-(\d+)\.html"',
                    m.group(1)
                ):
                    ep_name = em.group(1).strip()
                    vid = em.group(2)
                    vfrom = em.group(3)
                    vpart = em.group(4)
                    # 播放地址用占位符，playerContent时再解析真实m3u8
                    play_url = f"{ep_name}${vid}-{vfrom}-{vpart}"
                    episodes.append(play_url)
            if not episodes:
                #  fallback: 从"播放地址N"按钮提取
                for bm in re.finditer(
                    r'href="/video/\?(\d+)-(\d+)-(\d+)\.html"[^>]*>播放地址(\d+)',
                    html
                ):
                    vid, vfrom, vpart, num = bm.groups()
                    episodes.append(f"播放地址{num}${vid}-{vfrom}-{vpart}")
            play_urls_parts.append("#".join(episodes))

        vod["vod_play_from"] = "$$$".join(play_froms) if play_froms else "xingba"
        vod["vod_play_url"] = "$$$".join(play_urls_parts) if play_urls_parts else ""

        # 如果没有解析到播放地址，用默认的
        if not vod["vod_play_url"]:
            vod["vod_play_from"] = "xingba"
            vod["vod_play_url"] = f"HD${vod_id}-0-0"

        # 脱敏（铁律11）
        vod["vod_name"] = self.desensitize(vod["vod_name"])
        vod["vod_content"] = self.desensitize(vod["vod_content"])
        vod["vod_remarks"] = self.desensitize(vod["vod_remarks"])
        vod["vod_actor"] = self.desensitize(vod["vod_actor"])

        return vod

    def _parse_play_url(self, html):
        """从播放页提取真实m3u8地址"""
        m = re.search(r'var\s+now\s*=\s*["\']([^"\']+)["\']', html)
        if m:
            return m.group(1).strip()
        # fallback: 直接匹配m3u8 URL
        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
        if m:
            return m.group(1).strip()
        return ""

    # ========== 四壳协议 13 接口 ==========

    def getDependence(self):
        return ""

    def init(self, extend):
        self.extend = extend or {}
        # 支持 ext.proxy / ext.siteUrl 覆盖
        if isinstance(self.extend, dict):
            if self.extend.get("proxy"):
                self.siteUrl = self.extend["proxy"]
                self.HOST = self.siteUrl
            if self.extend.get("siteUrl"):
                self.siteUrl = self.extend["siteUrl"]
                self.HOST = self.siteUrl
            if self.extend.get("direct"):
                self.siteUrl = self.rawSite
                self.HOST = self.rawSite
        return True

    def homeContent(self):
        """首页：分类列表 + 筛选器"""
        classes = []
        filters = {}
        for tid, tname in self.CLASS_MAP.items():
            classes.append({"type_id": tid, "type_name": tname})
            # 每个分类的筛选器（排序）
            filters[tid] = [{
                "key": "order",
                "name": "排序",
                "init": "time",
                "value": [
                    {"n": "时间", "v": "time"},
                    {"n": "人气", "v": "hit"},
                    {"n": "评分", "v": "commend"},
                ]
            }]

        # 首页推荐视频（从首页提取）
        home_list = []
        html = self._get(self.siteUrl + "/")
        if html:
            home_list = self._parse_vod_list(html)
            # 首页只取前20条
            home_list = home_list[:20]

        return {
            "class": classes,
            "filters": filters,
            "list": home_list,
        }

    def homeVideoContent(self):
        """首页视频（兼容接口）"""
        html = self._get(self.siteUrl + "/")
        vod_list = self._parse_vod_list(html) if html else []
        return {
            "page": 1,
            "pagecount": 1,
            "limit": 20,
            "total": len(vod_list),
            "list": vod_list[:20],
        }

    def categoryContent(self, tid, pg, filter, extend):
        """分类页"""
        page = int(pg) if pg else 1
        # 分类页URL: /list/?{tid}-{page}.html
        if page > 1:
            url = f"{self.siteUrl}/list/?{tid}-{page}.html"
        else:
            url = f"{self.siteUrl}/list/?{tid}.html"

        # 处理排序筛选
        order = ""
        if extend and isinstance(extend, dict):
            order = extend.get("order", "")
        if order:
            url = f"{self.siteUrl}/search.php?page={page}&searchtype=5&order={order}&tid={tid}"

        html = self._get(url)
        if not html:
            return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

        vod_list = self._parse_vod_list(html)
        p, pc, limit, total = self._parse_page_info(html)
        if p != page:
            p = page

        return {
            "page": p,
            "pagecount": pc,
            "limit": limit,
            "total": total,
            "list": vod_list,
        }

    def detailContent(self, ids):
        """详情页 - 必须遍历ids（铁律）"""
        if not ids:
            return {"list": []}
        # ids 是 list/tuple，必须遍历
        if isinstance(ids, (list, tuple)):
            id_list = list(ids)
        else:
            id_list = [str(ids)]

        result_list = []
        for vod_id in id_list:
            vod_id = str(vod_id).strip()
            if not vod_id:
                continue
            url = f"{self.siteUrl}/detail/?{vod_id}.html"
            html = self._get(url)
            if not html:
                continue
            vod = self._parse_detail(html, vod_id)
            # 未成年内容剔除（铁律13）
            if self._is_minor(vod.get("vod_name", "")) or self._is_minor(vod.get("vod_content", "")):
                continue
            result_list.append(vod)

        return {"list": result_list}

    def searchContent(self, key, quick):
        """搜索"""
        return self.searchContentPage(key, 1)

    def searchContentPage(self, key, pg):
        """搜索分页"""
        page = int(pg) if pg else 1
        encoded_key = urllib.parse.quote(key)
        url = f"{self.siteUrl}/search.php?searchword={encoded_key}&page={page}"
        html = self._get(url)
        if not html:
            return {"page": page, "pagecount": 1, "limit": 20, "total": 0, "list": []}

        vod_list = self._parse_vod_list(html)
        p, pc, limit, total = self._parse_page_info(html)
        if p != page:
            p = page

        return {
            "page": p,
            "pagecount": pc,
            "limit": limit,
            "total": total,
            "list": vod_list,
        }

    def playerContent(self, flag, id, vipFlags):
        """播放页：解析真实m3u8地址"""
        # id 格式: {vod_id}-{vfrom}-{vpart}
        real_url = ""
        if id and "-" in str(id):
            parts = str(id).split("-")
            if len(parts) >= 3:
                vid, vfrom, vpart = parts[0], parts[1], parts[2]
                play_url = f"{self.siteUrl}/video/?{vid}-{vfrom}-{vpart}.html"
                html = self._get(play_url)
                if html:
                    real_url = self._parse_play_url(html)

        # 如果没解析到，尝试直接用id作为URL
        if not real_url and id:
            if str(id).startswith("http"):
                real_url = str(id)

        header = {
            "User-Agent": self.UA,
            "Referer": self.rawSite + "/",
            "Origin": self.rawSite,
        }

        return {
            "parse": 0,
            "jx": 0,
            "url": real_url,
            "header": header,
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        """本地代理（封面图代理）"""
        try:
            if isinstance(param, str):
                url = param
            elif isinstance(param, dict):
                url = param.get("url", "")
            else:
                url = str(param)
            if not url:
                return [404, "text/plain", ""]
            if url.startswith("local://"):
                url = url.replace("local://", "")
            req = urllib.request.Request(url, headers={
                "User-Agent": self.UA,
                "Referer": self.rawSite + "/",
            })
            resp = urllib.request.urlopen(req, timeout=10)
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            data = resp.read()
            return [200, content_type, data]
        except Exception:
            return [404, "text/plain", ""]

    def isVideoFormat(self, url):
        if not url:
            return False
        return any(url.lower().endswith(ext) for ext in
                   [".m3u8", ".mp4", ".ts", ".flv", ".mkv", ".avi"])

    def manualVideoCheck(self):
        return False

    def action(self, actionKey, param):
        return ""

    def destroy(self):
        return True
