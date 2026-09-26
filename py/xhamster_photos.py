# -*- coding: utf-8 -*-
"""
xHamster Photos (zh.xhamster.com/photos)
图集爬虫 - 对齐老司机禁漫：列表 + 章节 + pics:// 阅读

注意：部分地区有年龄验证/注册墙；用户端网络需能正常打开站点。
可用 extend 指定 host，如 https://xhamster.com
"""
import json
import re
import sys
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=''):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://zh.xhamster.com'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        )
        self.cookie = (
            'parental-control=no; ageProtectAgreement=1; av_banner_closed=1; av_started=1; '
            'lang=zh; locale=zh; cookie_accept_v2=%7B%22e%22%3A1%2C%22f%22%3A1%2C%22t%22%3A1%2C%22a%22%3A1%7D'
        )
        self.classes = [
            {'type_id': 'photos', 'type_name': '最新图集'},
            {'type_id': 'photos/newest', 'type_name': 'Newest'},
            {'type_id': 'photos/best', 'type_name': 'Best'},
            {'type_id': 'photos/categories/amateur', 'type_name': 'Amateur'},
            {'type_id': 'photos/categories/asian', 'type_name': 'Asian'},
            {'type_id': 'photos/categories/brunette', 'type_name': 'Brunette'},
            {'type_id': 'photos/categories/blonde', 'type_name': 'Blonde'},
            {'type_id': 'photos/categories/teen', 'type_name': 'Teen'},
            {'type_id': 'photos/categories/milf', 'type_name': 'MILF'},
            {'type_id': 'photos/categories/lesbian', 'type_name': 'Lesbian'},
            {'type_id': 'photos/categories/japanese', 'type_name': 'Japanese'},
            {'type_id': 'photos/categories/chinese', 'type_name': 'Chinese'},
        ]

    def getName(self):
        return 'xHamster图集'

    def init(self, extend=''):
        if not extend:
            return
        if str(extend).startswith('http'):
            self.host = str(extend).rstrip('/')
        else:
            try:
                j = json.loads(extend)
                if j.get('host'):
                    self.host = str(j['host']).rstrip('/')
            except Exception:
                pass

    def get_header(self, url=None):
        return {
            'User-Agent': self.ua,
            'Referer': self.host + '/photos',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': self.cookie,
        }

    def fetch(self, url, timeout=20):
        if requests is None:
            return None
        try:
            if url.startswith('/'):
                url = self.host + url
            r = requests.get(url, headers=self.get_header(url), timeout=timeout)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r
        except Exception as e:
            print('fetch', url, e)
            return None

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        r = self.fetch('/photos')
        videos = self._parse_list(r.text) if r is not None else []
        return {'list': videos[:30]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'photos').lstrip('/')
        path = '/' + tid
        if pg > 1:
            path += '/%d' % pg
        r = self.fetch(path)
        videos = self._parse_list(r.text) if r is not None else []
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 30,
            'total': 9999,
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        gid = re.sub(r'\D', '', str(raw)) or str(raw)
        url = '/photos/gallery/%s/' % gid
        r = self.fetch(url)
        if r is None:
            return {'list': []}
        html = r.text
        name = 'Gallery ' + gid
        m = re.search(r'<h1[^>]*>([\s\S]*?)</h1>', html, re.I) or re.search(r'<title>([^<]+)', html, re.I)
        if m:
            name = self._text(m.group(1).split('|')[0].split('-')[0]) or name
        pic = ''
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if m:
            pic = self._fix(m.group(1))
        eps = []
        seen = set()
        for m in re.finditer(r'href="([^"]*/photos/gallery/\d+/[^"]*)"[^>]*>\s*(\d+)\s*<', html, re.I):
            href = self._fix(m.group(1))
            if href in seen:
                continue
            seen.add(href)
            eps.append('第%s页$%s' % (m.group(2), href))
        if not eps:
            eps.append('图集$%s' % self._fix(url))
        play_url = '#'.join(eps)
        return {
            'list': [{
                'vod_id': gid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_content': name,
                'vod_play_from': 'xHamster图集',
                'vod_play_url': play_url,
                'book_id': gid,
                'book_name': name,
                'book_pic': pic,
                'book_content': name,
                'volumes': 'xHamster Photos',
                'urls': play_url,
            }]
        }

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        q = urllib.parse.quote(str(key or '').strip())
        path = '/search/%s?type=photos' % q
        if pg > 1:
            path += '&page=%d' % pg
        r = self.fetch(path)
        videos = self._parse_list(r.text) if r is not None else []
        if not videos:
            r2 = self.fetch('/photos/search/%s%s' % (q, ('/%d' % pg) if pg > 1 else ''))
            if r2 is not None:
                videos = self._parse_list(r2.text)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 15 else pg,
        }

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '')
        if not url.startswith('http'):
            if re.match(r'^\d+$', url):
                url = self.host + '/photos/gallery/%s/' % url
            else:
                url = self._fix(url)
        r = self.fetch(url)
        imgs = self._parse_images(r.text) if r is not None else []
        if not imgs:
            return {'parse': 0, 'url': '', 'msg': '未找到图片（可能触发年龄验证墙）'}
        return {
            'parse': 0,
            'url': 'pics://' + '&&'.join(imgs),
            'content': imgs,
            'header': {
                'User-Agent': self.ua,
                'Referer': self.host + '/',
                'Cookie': self.cookie,
            },
            'vod_player': '画',
        }

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass

    def _fix(self, u):
        if not u:
            return ''
        u = str(u).strip().replace('&amp;', '&')
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        return u

    def _text(self, s):
        s = re.sub(r'<[^>]+>', '', str(s or ''))
        return re.sub(r'\s+', ' ', s.replace('&amp;', '&').replace('&nbsp;', ' ')).strip()

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(
            r'href="((?:https?://[^"]*)?/photos/gallery/(\d+)/[^"]*)"[^>]*>'
            r'[\s\S]{0,1500}?(?:data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"'
            r'[\s\S]{0,500}?(?:alt|title)="([^"]*)"',
            html,
            re.I,
        ):
            gid = m.group(2)
            if gid in seen:
                continue
            seen.add(gid)
            name = self._text(m.group(4)) or ('Gallery ' + gid)
            item = {
                'vod_id': gid,
                'vod_name': name,
                'vod_pic': self._fix(m.group(3)),
                'vod_remarks': '',
                'book_id': gid,
                'book_name': name,
                'book_pic': self._fix(m.group(3)),
                'book_remarks': '',
            }
            videos.append(item)
        if not videos:
            for m in re.finditer(r'/photos/gallery/(\d+)/([a-z0-9\-_%]+)', html, re.I):
                if m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                name = urllib.parse.unquote(m.group(2).replace('-', ' '))
                videos.append({
                    'vod_id': m.group(1),
                    'vod_name': name,
                    'vod_pic': '',
                    'vod_remarks': '',
                    'book_id': m.group(1),
                    'book_name': name,
                    'book_pic': '',
                    'book_remarks': '',
                })
        return videos

    def _parse_images(self, html):
        imgs, seen = [], set()
        if not html:
            return imgs
        for m in re.finditer(
            r'(?:data-src|data-preview|data-original|src)="(https?://[^"]+(?:xhcdn|xhamster)[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html,
            re.I,
        ):
            src = self._fix(m.group(1))
            if not src or src in seen:
                continue
            if re.search(r'logo|icon|avatar|sprite|flag|emoji', src, re.I):
                continue
            src = re.sub(r'/\d+x\d+/', '/1280x720/', src)
            if src in seen:
                continue
            seen.add(src)
            imgs.append(src)
        # JSON 内图片
        for m in re.finditer(r'"imageURL"\s*:\s*"(https?:\\?/\\?/[^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"', html, re.I):
            src = m.group(1).replace('\\/', '/').replace('\\/', '/')
            src = self._fix(src)
            if src and src not in seen:
                seen.add(src)
                imgs.append(src)
        return imgs


if __name__ == '__main__':
    sp = Spider()
    print(json.dumps(sp.homeContent(True), ensure_ascii=False, indent=2))
    print('note: age wall may block datacenter IPs')
