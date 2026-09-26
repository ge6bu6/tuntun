#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re
import sys
import urllib.parse

try:
    import requests
except ImportError:
    requests = None

sys.path.append('../../')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""):
            pass


class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://missav.ws'
        self.lang = 'cn'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        )
        self.channels = {
            'new': {'name': '最近更新', 'path': 'new'},
            'release': {'name': '新作上市', 'path': 'release'},
            'today': {'name': '今日热门', 'path': 'today-hot'},
            'week': {'name': '本周热门', 'path': 'weekly-hot'},
            'month': {'name': '本月热门', 'path': 'monthly-hot'},
            'leak': {'name': '无码流出', 'path': 'uncensored-leak'},
            'fc2': {'name': 'FC2', 'path': 'fc2'},
            'cnsub': {'name': '中文字幕', 'path': 'chinese-subtitle'},
            'ensub': {'name': '英文字幕', 'path': 'english-subtitle'},
            'heyzo': {'name': 'HEYZO', 'path': 'heyzo'},
            'tokyo': {'name': 'Tokyo Hot', 'path': 'tokyohot'},
            'pondo': {'name': '1pondo', 'path': '1pondo'},
            'carib': {'name': 'Caribbean', 'path': 'caribbeancom'},
            'musume': {'name': '10musume', 'path': '10musume'},
            'paco': {'name': 'pacopacomama', 'path': 'pacopacomama'},
            'vr': {'name': 'VR', 'path': 'genres/VR'},
            'madou': {'name': '麻豆', 'path': 'madou'},
        }

    def getName(self):
        return 'MissAV'

    def init(self, extend=""):
        try:
            if extend:
                ext = json.loads(extend) if isinstance(extend, str) else (extend or {})
                if ext.get('host'):
                    self.siteUrl = str(ext.get('host')).rstrip('/')
                if ext.get('lang'):
                    self.lang = str(ext.get('lang'))
        except Exception:
            pass

    def fetch(self, url, headers=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, timeout=20)
                resp.raise_for_status()
                return resp.text
            from urllib.request import Request, urlopen
            raw = urlopen(Request(url, headers=headers), timeout=20).read()
            return raw.decode('utf-8', 'ignore')
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return ''

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('http'):
            return u
        if u.startswith('//'):
            return 'https:' + u
        return self.siteUrl + (u if u.startswith('/') else '/' + u)

    def _page_url(self, path, pg=1):
        path = (path or 'new').strip('/')
        base = '%s/%s/%s' % (self.siteUrl, self.lang, path)
        if int(pg or 1) > 1:
            return base + '?page=' + str(pg)
        return base

    def _parse_list(self, html):
        videos = []
        seen = set()
        html = html or ''
        for m in re.finditer(
            r'href="([^"]+/(?:cn|en|ja)/[A-Za-z0-9][^"]*)"[^>]*>[\s\S]{0,800}?src="([^"]+)"[\s\S]{0,400}?alt="([^"]*)"',
            html, re.I
        ):
            href, pic, title = m.group(1), m.group(2), m.group(3)
            slug = href.rstrip('/').split('/')[-1]
            if not slug or slug in seen or slug in ('cn', 'en', 'ja', 'new', 'search'):
                continue
            if not re.search(r'[A-Za-z0-9-]{3,}', slug):
                continue
            seen.add(slug)
            videos.append({
                'vod_id': slug,
                'vod_name': title or slug,
                'vod_pic': self._abs(pic),
                'vod_remarks': slug.upper() if re.search(r'[a-z]', slug) else '',
            })
        if videos:
            return videos
        for m in re.finditer(r'href="[^"]*/(?:cn|en|ja)/([A-Za-z0-9][A-Za-z0-9._-]{2,})"', html):
            slug = m.group(1)
            if slug in seen or slug in ('new', 'search', 'actresses', 'makers', 'genres'):
                continue
            seen.add(slug)
            videos.append({
                'vod_id': slug,
                'vod_name': slug,
                'vod_pic': '',
                'vod_remarks': '',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        html = self.fetch(self._page_url('new', 1))
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        info = self.channels.get(str(tid), {'path': str(tid or 'new')})
        html = self.fetch(self._page_url(info.get('path') or 'new', pg))
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 12,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        q = urllib.parse.quote(str(key or ''))
        url = '%s/%s/search/%s' % (self.siteUrl, self.lang, q)
        if pg > 1:
            url += '?page=' + str(pg)
        html = self.fetch(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 12,
            'total': len(videos),
        }

    def _uuid_from_html(self, html):
        html = html or ''
        pats = [
            r'surrit\.com/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
            r'uuid["\s:=]+["\']([0-9a-f-]{36})["\']',
            r'playlist["\s:=]+["\']([^"\']+)["\']',
        ]
        for p in pats:
            m = re.search(p, html, re.I)
            if m:
                return m.group(1)
        m3 = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        return m3.group(0) if m3 else ''

    def detailContent(self, ids):
        slug = str((ids or [''])[0]).strip('/')
        url = '%s/%s/%s' % (self.siteUrl, self.lang, slug)
        html = self.fetch(url)
        title = slug
        pic = ''
        tm = re.search(r'<title>([^<]+)</title>', html or '', re.I)
        if tm:
            title = re.sub(r'\s*[-|].*$', '', tm.group(1)).strip() or slug
        pm = re.search(r'og:image["\']\s+content=["\']([^"\']+)', html or '', re.I)
        if pm:
            pic = self._abs(pm.group(1))
        return {
            'list': [{
                'vod_id': slug,
                'vod_name': title,
                'vod_pic': pic,
                'vod_content': title,
                'vod_play_from': 'MissAV',
                'vod_play_url': '正片$%s' % slug,
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play_id = str(id or '')
        if play_id.startswith('http') and self.isVideoFormat(play_id):
            return {'parse': 0, 'url': play_id, 'header': header}
        slug = play_id.split('|')[0]
        page = '%s/%s/%s' % (self.siteUrl, self.lang, slug)
        html = self.fetch(page)
        token = self._uuid_from_html(html)
        url = ''
        if token.startswith('http'):
            url = token
        elif re.match(r'^[0-9a-f-]{36}$', token, re.I):
            url = 'https://surrit.com/%s/playlist.m3u8' % token
        elif token:
            url = token if token.startswith('http') else ('https://surrit.com/%s/playlist.m3u8' % token)
        if url:
            return {'parse': 0, 'url': url, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.mpd'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
