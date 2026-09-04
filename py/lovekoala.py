# coding: utf-8
# 站点: Love Koala
# 类型: 图片站 + 短视频
# 主域名: https://lovekoala.com
# 验证时间: 2026-09-04
# 来源: https://lovekoala.com/cn/

import json
import re
from urllib.parse import urljoin, quote

from base.spider import Spider as BaseSpider

class Spider(BaseSpider):
    def __init__(self):
        self.host = "https://lovekoala.com"
        self.classes = [
            {"type_id": "category-av", "type_name": "AV女优列表"},
            {"type_id": "condition-av", "type_name": "AV女优分类"},
            {"type_id": "category-idol", "type_name": "偶像列表"},
            {"type_id": "condition-idol", "type_name": "偶像分类"},
            {"type_id": "short", "type_name": "AV短视频"},
            {"type_id": "ai", "type_name": "AI色情图片"},
            {"type_id": "history-av", "type_name": "AV女优更新"},
            {"type_id": "history-idol", "type_name": "偶像更新"},
        ]
        self.filters = {
            "category-av": [],
            "condition-av": [],
            "category-idol": [],
            "condition-idol": [],
            "short": [],
            "ai": [],
            "history-av": [],
            "history-idol": [],
        }
        self.video_types = ["short"]  # 短视频分类
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 14; 22127RK46C) AppleWebKit/537.36",
            "Referer": self.host + "/cn/"
        }

    def getName(self):
        return "Love Koala"

    def getDependence(self):
        return []

    def init(self, extend=""):
        self.extend = extend or ""

    def homeContent(self, filter):
        return {"class": self.classes, "filters": self.filters if filter else {}}

    def getHomeContent(self, filter):
        return self.homeContent(filter)

    def homeVideoContent(self):
        # 首页最新的图片集
        try:
            res = self.fetch(f"{self.host}/cn/", headers=self.headers, timeout=10)
            if not res:
                return {"list": []}
            html = res.text
            items = []
            pattern = r'<li class="lpbox">.*?<a href="(.*?)" class="spimg">.*?<img src="(.*?)".*?<h3 class="lpname">(.*?)</h3>.*?<div class="lpcate">(.*?)</div>'
            for match in re.finditer(pattern, html, re.S):
                link, pic, name, cate = match.groups()
                vod_name = name.strip()
                items.append({
                    "vod_id": link,
                    "vod_name": vod_name,
                    "vod_pic": pic,
                    "vod_remarks": cate.strip().split("<br>")[0].strip(),
                })
                if len(items) >= 20:
                    break
            return {"list": items}
        except Exception as e:
            self.log({"action": "homeVideoContent", "error": str(e)})
            return {"list": []}

    def _parse_list_page(self, html, is_video=False):
        """解析列表页，返回条目列表"""
        items = []
        if is_video:
            # 短视频列表: 使用 crbox 容器提取视频
            pattern = r'<div class="crbox">.*?<video[^>]*src="([^"]+)"[^>]*>.*?</div>'
            for match in re.finditer(pattern, html, re.S):
                video_url = match.group(1)
                name_match = re.search(r'/([^/]+)\.mp4', video_url)
                vod_name = name_match.group(1) if name_match else "短视频"
                items.append({
                    "vod_id": video_url,
                    "vod_name": vod_name,
                    "vod_pic": "",
                    "vod_remarks": "短视频",
                })
            return items
        else:
            # 图片列表: 使用 lpbox / spbox2 容器
            # 先找所有 lpbox 或 spbox2
            blocks = re.findall(r'<li[^>]*class="[^"]*(?:lpbox|spbox2)[^"]*"[^>]*>(.*?)</li>', html, re.S)
            for block in blocks:
                # 提取链接
                link_match = re.search(r'<a[^>]*href="([^"]+)"[^>]*class="[^"]*spimg[^"]*"[^>]*>', block, re.S)
                if not link_match:
                    continue
                link = link_match.group(1)
                # 提取图片
                pic_match = re.search(r'<img[^>]*src="([^"]+)"', block, re.S)
                pic = pic_match.group(1) if pic_match else ""
                # 提取标题
                name_match = re.search(r'<h3[^>]*class="[^"]*(?:lpname|spname)[^"]*"[^>]*>(.*?)</h3>', block, re.S)
                vod_name = name_match.group(1).strip() if name_match else "未知"
                # 提取分类
                cate_match = re.search(r'<div[^>]*class="[^"]*(?:lpcate|spcate)[^"]*"[^>]*>(.*?)</div>', block, re.S)
                cate = cate_match.group(1).strip() if cate_match else ""
                cate = cate.split("<br>")[0].strip()
                items.append({
                    "vod_id": link,
                    "vod_name": vod_name,
                    "vod_pic": pic,
                    "vod_remarks": cate,
                })
            return items
    def _get_pagecount(self, html):
        """解析总页数"""
        # 方法1: 从"末页"链接提取
        last_match = re.search(r'<a href="[^"]*?/(\d+)/" class="plink1">末页</a>', html)
        if last_match:
            return int(last_match.group(1))
        # 方法2: 从"共X人"推算 (每页36人)
        count_match = re.search(r'<h2 class="mtxt">共(\d+)人</h2>', html)
        if count_match:
            total = int(count_match.group(1))
            import math
            return math.ceil(total / 36)
        # 方法3: 从分页链接中取最大页码
        page_links = re.findall(r'<a href="[^"]*?/(\d+)/"[^>]*>', html)
        if page_links:
            numbers = [int(p) for p in page_links if p.isdigit()]
            if numbers:
                return max(numbers)
        return 1

    def categoryContent(self, tid, pg, filter, extend):
        page = pg or "1"
        try:
            # 判断是否为视频类型
            is_video = tid in self.video_types
            url = f"{self.host}/cn/{tid}/{page}/" if page != "1" else f"{self.host}/cn/{tid}/"
            if page == "1":
                url = f"{self.host}/cn/{tid}/"
            else:
                url = f"{self.host}/cn/{tid}/{page}/"

            res = self.fetch(url, headers=self.headers, timeout=10)
            if not res:
                return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

            html = res.text
            items = self._parse_list_page(html, is_video)
            pagecount = self._get_pagecount(html)

            return {"list": items, "page": int(page), "pagecount": pagecount, "limit": 20, "total": len(items)}
        except Exception as e:
            self.log({"action": "categoryContent", "tid": tid, "pg": pg, "error": str(e)})
            return {"list": [], "page": int(page), "pagecount": 1, "limit": 20, "total": 0}

    def detailContent(self, ids):
        try:
            play_page = str(ids[0])
            if not play_page.startswith("http"):
                play_page = self.host + play_page

            # 检查是否为视频直链 (短视频)
            if play_page.endswith(".mp4") or "short" in play_page:
                vod = {
                    "vod_id": play_page,
                    "vod_name": "短视频",
                    "vod_pic": "",
                    "vod_remarks": "短视频",
                    "vod_content": "",
                    "vod_play_from": "播放",
                    "vod_play_url": f"播放${play_page}"
                }
                return {"list": [vod]}

            # 图片详情: 获取页面信息
            res = self.fetch(play_page, headers=self.headers, timeout=10)
            vod_name = ""
            vod_pic = ""
            vod_remarks = ""
            if res:
                html = res.text
                title_match = re.search(r'<h1 class="htxt1">(.*?)</h1>', html)
                if title_match:
                    vod_name = title_match.group(1).strip()
                pic_match = re.search(r'<figure class="icimg0"><img src="([^"]+)"', html)
                if pic_match:
                    vod_pic = pic_match.group(1)
                count_match = re.search(r'<h1 class="htxt1">.*?(\d+)张', html)
                if count_match:
                    vod_remarks = f"{count_match.group(1)}张图片"

            vod = {
                "vod_id": play_page,
                "vod_name": vod_name or "图片集",
                "vod_pic": vod_pic,
                "vod_remarks": vod_remarks,
                "vod_content": vod_remarks,
                "vod_play_from": "图片浏览",
                "vod_play_url": f"浏览图片${play_page}"
            }
            return {"list": [vod]}
        except Exception as e:
            self.log({"action": "detailContent", "ids": ids, "error": str(e)})
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            url = f"{self.host}/cn/search/"
            data = {"sc": key}
            res = self.post(url, data=data, headers=self.headers, timeout=10)
            if not res:
                return {"list": [], "page": int(pg)}
            html = res.text
            items = []
            pattern = r'<li class="spbox2">.*?<a href="(.*?)" class="spimg">.*?<img src="(.*?)".*?<span class="spcate">(.*?)</span>.*?<h3 class="spname">(.*?)</h3>'
            for match in re.finditer(pattern, html, re.S):
                link, pic, cate, name = match.groups()
                vod_name = name.strip()
                items.append({
                    "vod_id": link,
                    "vod_name": vod_name,
                    "vod_pic": pic,
                    "vod_remarks": cate.strip(),
                })
            return {"list": items, "page": int(pg)}
        except Exception as e:
            self.log({"action": "searchContent", "key": key, "pg": pg, "error": str(e)})
            return {"list": [], "page": int(pg)}

    def playerContent(self, flag, id, vipFlags):
        # 短视频: 返回视频直链
        if id and id.startswith("http") and id.endswith(".mp4"):
            return {"parse": 0, "url": id, "header": self.headers}

        # 图片站: 接收详情页URL，提取所有分页的图片
        try:
            if not id or not id.startswith("http"):
                return {"parse": 0, "url": "", "header": {}}

            all_imgs = []
            base_url = id.rstrip("/")
            
            # 先请求第一页，获取总页数
            res = self.fetch(base_url, headers=self.headers, timeout=10)
            if not res:
                return {"parse": 0, "url": "", "header": {}}

            html = res.text

            # 解析总页数
            pagecount = 1
            
            # 方法1: 从"末页"链接提取 (class="plink1")
            import re
            last_match = re.search(r'<a[^>]*href="[^"]*/(\d+)/"[^>]*class="[^"]*plink1[^"]*"[^>]*>末页</a>', html)
            if last_match:
                pagecount = int(last_match.group(1))
            else:
                # 方法2: 从标题提取总张数 (如 "羽田爱 图片152张【前偶像】")
                title_match = re.search(r'<h1[^>]*class="[^"]*htxt1[^"]*"[^>]*>.*?(\d+)张', html)
                if title_match:
                    total = int(title_match.group(1))
                    import math
                    pagecount = math.ceil(total / 36)
                else:
                    # 方法3: 从分页链接中取最大页码
                    page_links = re.findall(r'<a[^>]*href="[^"]*/(\d+)/"[^>]*>', html)
                    if page_links:
                        numbers = [int(p) for p in page_links if p.isdigit()]
                        if numbers:
                            pagecount = max(numbers)

            # 如果 pagecount 还是1，强制设为5（基于已知站点结构）
            if pagecount <= 1:
                # 尝试从标题提取总张数
                title_match = re.search(r'<h1[^>]*class="[^"]*htxt1[^"]*"[^>]*>.*?(\d+)张', html)
                if title_match:
                    total = int(title_match.group(1))
                    import math
                    pagecount = math.ceil(total / 36)
                else:
                    pagecount = 5  # 默认最多5页

            # 遍历所有页面提取图片
            for page in range(1, pagecount + 1):
                if page == 1:
                    page_url = base_url
                else:
                    page_url = f"{base_url}/{page}/"

                if page > 1:
                    res_page = self.fetch(page_url, headers=self.headers, timeout=10)
                    if not res_page:
                        continue
                    html = res_page.text

                # 限定在 gallery 或 ibox 容器内提取图片
                scope = html
                gallery_match = re.search(r'<div[^>]*class="[^"]*gallery[^"]*"[^>]*>(.*?)</div>', html, re.S)
                if gallery_match:
                    scope = gallery_match.group(1)
                else:
                    ibox_match = re.search(r'<ul[^>]*class="[^"]*ibox[^"]*"[^>]*>(.*?)</ul>', html, re.S)
                    if ibox_match:
                        scope = ibox_match.group(1)

                # 提取图片链接 (大图链接, 从 a[href] 中取)
                img_pattern = r'<a[^>]*href="([^"]+\.(?:jpg|jpeg|png|webp))"[^>]*>'
                imgs = re.findall(img_pattern, scope, re.S)

                if not imgs:
                    img_pattern2 = r'<img[^>]+src="([^"]+\.(?:jpg|jpeg|png|webp))"'
                    imgs = re.findall(img_pattern2, scope, re.S)

                # 过滤杂图
                bad_keywords = ['logo', 'avatar', 'icon', 'favicon', 'qrcode', 'ad', 'banner', 'thumb']
                imgs = [img for img in imgs if not any(k in img.lower() for k in bad_keywords)]

                all_imgs.extend(imgs)

                # 避免请求过快
                if page > 1:
                    import time
                    time.sleep(0.2)

            if not all_imgs:
                return {"parse": 0, "url": "", "header": {}}

            # 补全绝对地址，添加 Referer 防盗链
            pics = []
            seen = set()
            for img in all_imgs:
                if img in seen:
                    continue
                seen.add(img)
                if not img.startswith("http"):
                    img = urljoin(self.host, img)
                pics.append(f"{img}@Referer={self.host}/cn/")

            pics_url = "pics://" + "&&".join(pics)
            return {"parse": 0, "url": pics_url, "header": {}}

        except Exception as e:
            self.log({"action": "playerContent", "id": id, "error": str(e)})
            return {"parse": 0, "url": "", "header": {}}
    def recommendContent(self, ids, pg):
        return {"list": []}

    def destroy(self):
        pass

    def localProxy(self, params):
        return [404, "text/plain", b"not found"]

    def _parse_extend(self, extend):
        if not extend:
            return {}
        if isinstance(extend, dict):
            return extend
        if isinstance(extend, str):
            try:
                return json.loads(extend)
            except:
                pass
            result = {}
            for part in extend.split(','):
                if '=' in part:
                    k, v = part.split('=', 1)
                    result[k.strip()] = v.strip()
            return result
        return {}