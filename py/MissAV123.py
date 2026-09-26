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
    """MissAV https://missav123.com  18+"""

    def __init__(self):
        self.siteUrl = 'https://missav123.com'
        self.lang = '/cn'
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'new': {'name': '最近更新', 'path': '/cn/new'},
            'release': {'name': '新作上市', 'path': '/cn/release'},
            'uncensored': {'name': '无码影片', 'path': '/cn/uncensored-leak'},
            'fc2': {'name': 'FC2', 'path': '/cn/fc2'},
            'madou': {'name': '麻豆', 'path': '/cn/madou'},
            'chinese-subtitle': {'name': '中文字幕', 'path': '/cn/chinese-subtitle'},
            'today-hot': {'name': '今日热门', 'path': '/cn/today-hot'},
            'weekly-hot': {'name': '本周热门', 'path': '/cn/weekly-hot'},
        }

    def getName(self):
        return 'MissAV123'

    def init(self, extend=""):
        pass

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                return resp
            full = url
            if params:
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            from urllib.request import Request, urlopen
            raw = urlopen(Request(full, headers=headers), timeout=15).read()

            class R:
                def __init__(self, raw):
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_text(self, url, params=None):
        resp = self.fetch(url, params=params)
        return getattr(resp, 'text', '') if resp else ''

    def _abs(self, u):
        if not u:
            return ''
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.siteUrl + u
        return u

    def _clean(self, s):
        return re.sub(r'<[^>]+>', '', str(s or '')).replace('&nbsp;', ' ').strip()

    def _code_from_path(self, path):
        path = str(path or '').split('#')[0].rstrip('/')
        name = path.split('/')[-1]
        return name or path

    def _parse_list(self, html):
        videos, seen = [], set()
        for m in re.finditer(
            r'href="((?:https?://[^"/]+)?(?:/dm\d+)?/cn/([a-z0-9][a-z0-9\-]+))(?:#[^"]*)?"[^>]{0,280}(?:title|alt)="([^"]*)"',
            html or '',
            re.I,
        ):
            href, code, title = m.group(1), m.group(2), self._clean(m.group(3))
            if code in ('new', 'release', 'uncensored-leak', 'fc2', 'madou', 'search', 'actresses', 'makers', 'genres'):
                continue
            if code in seen:
                continue
            seen.add(code)
            videos.append({
                'vod_id': '/cn/' + code,
                'vod_name': title or code.upper(),
                'vod_pic': '',
                'vod_remarks': code.upper(),
            })
        if not videos:
            for m in re.finditer(r'href="(/cn/([a-z0-9\-]+))"[^>]*>\s*([^<]{2,80})', html or '', re.I):
                path, code, title = m.group(1), m.group(2), self._clean(m.group(3))
                if code in seen or len(code) < 3:
                    continue
                seen.add(code)
                videos.append({
                    'vod_id': path,
                    'vod_name': title or code.upper(),
                    'vod_pic': '',
                    'vod_remarks': code.upper(),
                })
        for m in re.finditer(
            r'(?:src|data-src|data-original)="([^"]+\.(?:jpg|jpeg|png|webp)[^"]*)"',
            html or '',
            re.I,
        ):
            pic = self._abs(m.group(1))
            if any(x in pic.lower() for x in ('logo', 'icon', 'flag', 'avatar')):
                continue
            for v in videos:
                if not v['vod_pic']:
                    v['vod_pic'] = pic
                    break
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            html = self.fetch_text(self.siteUrl + '/cn/')
            videos = self._parse_list(html)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        try:
            info = self.channels.get(str(tid), {'path': '/cn/new'})
            url = self.siteUrl + info.get('path', '/cn/new')
            if pg > 1:
                url += '?page=' + str(pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 24,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            q = urllib.parse.quote(key)
            url = '%s/cn/search/%s' % (self.siteUrl, q)
            if pg > 1:
                url += '?page=' + str(pg)
            html = self.fetch_text(url)
            videos = self._parse_list(html)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def _page_url(self, vid):
        s = str(vid or '')
        if s.startswith('http'):
            return s
        if s.startswith('/'):
            return self.siteUrl + s
        return self.siteUrl + '/cn/' + s

    def _extract_m3u8(self, html):
        if not html:
            return ''
        m = re.search(r'https?://[^\s"\']+\.m3u8[^\s"\']*', html)
        if m:
            return m.group(0).replace('\\/', '/')
        m = re.search(r'source\s*=\s*[\'"]([^\'"]+)[\'"]', html)
        if m:
            src = m.group(1)
            if src.startswith('http') and ('.m3u8' in src or '.mp4' in src):
                return src
        m = re.search(r'uuid["\']?\s*[:=]\s*["\']([0-9a-f\-]{16,})["\']', html, re.I)
        if m:
            return 'https://surrit.com/%s/playlist.m3u8' % m.group(1)
        m = re.search(r'surrit\.com/([0-9a-f\-]{16,})', html, re.I)
        if m:
            return 'https://surrit.com/%s/playlist.m3u8' % m.group(1)
        return ''

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, desc, actor = self._code_from_path(vid).upper(), '', '', ''
        try:
            page = self._page_url(vid)
            html = self.fetch_text(page)
            tm = re.search(r'<title>([^<]+)</title>', html or '')
            if tm:
                name = re.sub(r'\s*[-_|].*$', '', tm.group(1)).strip() or name
            hm = re.search(r'<h1[^>]*>([\s\S]{2,200})</h1>', html or '')
            if hm:
                name = self._clean(hm.group(1)) or name
            pm = re.search(r'(?:og:image["\']\s+content=["\']|poster=["\'])([^"\']+)', html or '')
            if pm:
                pic = self._abs(pm.group(1))
            dm = re.search(r'og:description["\']\s+content=["\']([^"\']+)', html or '')
            if dm:
                desc = dm.group(1)
            am = re.search(r'(?:女优|女優|actress)[:：]?\s*([^<\n]{2,60})', html or '', re.I)
            if am:
                actor = self._clean(am.group(1))
            play = self._extract_m3u8(html)
            play_url = '播放$%s' % (play or page)
        except Exception as e:
            print('获取详情失败: %s' % e)
            play_url = '播放$%s' % self._page_url(vid)
        return {'list': [{
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': self._code_from_path(vid).upper(),
            'vod_actor': actor,
            'vod_director': '',
            'vod_content': (desc or '').strip(),
            'vod_play_from': 'MissAV',
            'vod_play_url': play_url,
        }]}

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        page = self._page_url(play)
        html = self.fetch_text(page)
        url = self._extract_m3u8(html)
        if url:
            return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.mp4', '.m3u8', '.flv', '.mpd'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
