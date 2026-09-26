# -*- coding: utf-8 -*-
"""
麻豆视频 madou8 - https://madou8.pw/asian/zh-CN
热播APP风格 PY 源
播放: GET /asian/zh-CN/api/video/stream?videoUid=
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
        self.host = 'https://madou8.pw'
        self.base = '/asian/zh-CN'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
        )
        self.classes = [
            {'type_id': 'videos/recent', 'type_name': '最近更新'},
            {'type_id': 'videos/new-releases', 'type_name': '新作上市'},
            {'type_id': 'videos/hot/today', 'type_name': '今日热门'},
            {'type_id': 'videos/hot/week', 'type_name': '本周热门'},
            {'type_id': 'videos/hot/month', 'type_name': '本月热门'},
            {'type_id': 'videos/tag/中文字幕', 'type_name': '中文字幕'},
            {'type_id': 'videos/tag/无码流出', 'type_name': '无码流出'},
            {'type_id': 'videos/genre/%E5%B7%A8%E4%B9%B3', 'type_name': '巨乳'},
            {'type_id': 'videos/genre/%E4%BA%BA%E5%A6%BB', 'type_name': '人妻'},
            {'type_id': 'videos/genre/%E7%86%9F%E5%A5%B3', 'type_name': '熟女'},
            {'type_id': 'videos/genre/%E7%BE%8E%E5%B0%91%E5%A5%B3', 'type_name': '美少女'},
            {'type_id': 'videos/genre/%E7%B4%A0%E4%BA%BA', 'type_name': '素人'},
            {'type_id': 'videos/genre/%E4%B8%AD%E5%87%BA', 'type_name': '中出'},
            {'type_id': 'videos/genre/%E5%8F%A3%E4%BA%A4', 'type_name': '口交'},
        ]

    def getName(self):
        return '麻豆视频'

    def init(self, extend=''):
        if extend and str(extend).startswith('http'):
            self.host = str(extend).rstrip('/')

    def get_header(self, url=None):
        return {
            'User-Agent': self.ua,
            'Referer': self.host + self.base + '/',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

    def fetch(self, url, timeout=20, accept=None):
        if requests is None:
            return None
        try:
            if url.startswith('/'):
                url = self.host + url
            h = self.get_header(url)
            if accept:
                h['Accept'] = accept
            r = requests.get(url, headers=h, timeout=timeout)
            r.encoding = r.apparent_encoding or 'utf-8'
            return r
        except Exception as e:
            print('fetch', url, e)
            return None

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        r = self.fetch(self.base + '/videos/recent')
        return {'list': self._parse_list(r.text if r is not None else '')[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        path = self.base + '/' + str(tid or 'videos/recent').lstrip('/')
        if pg > 1:
            path += '/page/%d' % pg
        r = self.fetch(path)
        videos = self._parse_list(r.text if r is not None else '')
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg='1'):
        pg = int(pg or 1)
        q = urllib.parse.quote(str(key or '').strip())
        path = self.base + '/videos/search/' + q
        if pg > 1:
            path += '/page/%d' % pg
        r = self.fetch(path)
        videos = self._parse_list(r.text if r is not None else '')
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
        }

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, (list, tuple)) else ids
        raw = str(raw)
        cid, uid = raw, ''
        if '@' in raw:
            cid, uid = raw.split('@', 1)
        url = self.base + '/video/cid/' + urllib.parse.quote(cid)
        r = self.fetch(url)
        html = r.text if r is not None else ''
        if not uid:
            m = re.search(r'videoUid["\']?\s*[:=]\s*["\']([a-f0-9]+)', html, re.I)
            if m:
                uid = m.group(1)
        name = cid.upper()
        m = re.search(r'<title>([^<]+)', html, re.I)
        if m:
            name = re.sub(r'\s*\|\s*.*$', '', m.group(1))
            name = re.sub(r'^麻豆视频\s*\|\s*', '', name).strip() or name
        pic = ''
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if m:
            pic = m.group(1)
        content = ''
        m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)', html, re.I)
        if m:
            content = re.sub(r'\s+', ' ', m.group(1)).strip()
        play_id = ('%s@%s' % (cid, uid)) if uid else cid
        return {
            'list': [{
                'vod_id': play_id,
                'vod_name': name,
                'vod_pic': pic,
                'vod_content': content,
                'vod_remarks': cid.upper(),
                'vod_play_from': '麻豆',
                'vod_play_url': '正片$%s' % play_id,
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or '')
        cid, uid = raw, ''
        if '@' in raw:
            cid, uid = raw.split('@', 1)
        if not uid:
            r = self.fetch(self.base + '/video/cid/' + urllib.parse.quote(cid))
            html = r.text if r is not None else ''
            m = re.search(r'videoUid["\']?\s*[:=]\s*["\']([a-f0-9]+)', html, re.I)
            if m:
                uid = m.group(1)
        header = {
            'User-Agent': self.ua,
            'Referer': self.host + self.base + '/',
            'Origin': self.host,
        }
        if not uid:
            return {'parse': 0, 'url': '', 'header': header}
        api = self.base + '/api/video/stream?videoUid=' + urllib.parse.quote(uid)
        r = self.fetch(api, accept='application/json')
        if r is None:
            return {'parse': 0, 'url': '', 'header': header}
        try:
            j = r.json()
        except Exception:
            return {'parse': 0, 'url': '', 'header': header}
        pl = j.get('playlist') or []
        urls = []
        for i, p in enumerate(pl):
            if not p or not p.get('url'):
                continue
            label = p.get('urlType') or ('HLS%d' % (i + 1))
            urls.extend([label, p['url']])
        if not urls:
            return {'parse': 0, 'url': '', 'header': header}
        if len(urls) == 2:
            return {'parse': 0, 'url': urls[1], 'header': header}
        return {'parse': 0, 'url': urls, 'header': header}

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4)(\?|$)', url or '', re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def destroy(self):
        pass

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        for m in re.finditer(
            r'data-video-uid="([a-f0-9]+)"([\s\S]{0,3500}?)(?=data-video-uid="|$)',
            html,
            re.I,
        ):
            uid = m.group(1)
            if uid in seen:
                continue
            chunk = m.group(2) or ''
            cm = re.search(r'/video/cid/([^"]+)', chunk, re.I)
            if not cm:
                continue
            cid = cm.group(1)
            if cid in seen:
                continue
            seen.add(uid)
            seen.add(cid)
            name = ''
            am = re.search(r'alt="([^"]+)"', chunk, re.I)
            if am:
                name = re.sub(r'\s+', ' ', am.group(1)).strip()
            if not name:
                name = cid.upper()
            pic = ''
            im = re.search(r'src="(https?://[^"]*cover[^"]*)"', chunk, re.I) or re.search(
                r'src="(https?://spic[^"]+)"', chunk, re.I
            )
            if im:
                pic = im.group(1)
            videos.append({
                'vod_id': '%s@%s' % (cid, uid),
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': cid.upper(),
            })
        return videos



if __name__ == '__main__':
    sp = Spider()
    print(json.dumps(sp.homeContent(True), ensure_ascii=False)[:200])
    r = sp.categoryContent('videos/recent', 1, False, {})
    print('list', len(r.get('list') or []))
    if r.get('list'):
        print('first', r['list'][0])
        d = sp.detailContent([r['list'][0]['vod_id']])
        print('detail', (d.get('list') or [{}])[0].get('vod_name'))
        p = sp.playerContent('麻豆', r['list'][0]['vod_id'], None)
        print('play', str(p.get('url'))[:120])
