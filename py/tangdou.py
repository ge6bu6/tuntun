# -*- coding: utf-8 -*-
"""
糖豆 api-h5 - 修复分类加载与搜索
"""
import json
import re
import sys

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
        self.host = 'https://m.tangdou.com'
        self.api = 'https://api-h5.tangdou.com'
        self.ua = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
        )
        self.classes = [
            {'type_id': 'home', 'type_name': '首页推荐'},
            {'type_id': 'space_170881', 'type_name': '慧慧广场舞'},
            {'type_id': 'space_36852', 'type_name': '杨丽萍'},
            {'type_id': 'space_350798', 'type_name': '美丽蓥华'},
            {'type_id': 'space_1903182', 'type_name': '红粉鞋健身舞'},
            {'type_id': 'space_3648894', 'type_name': '兰水心'},
            {'type_id': 'space_21562246', 'type_name': '焰焰广场舞'},
            {'type_id': 'space_385387', 'type_name': '雪妹广场舞'},
            {'type_id': 'space_149286', 'type_name': '吴川飞燕'},
            {'type_id': 'space_1855210', 'type_name': '妃儿舞蹈'},
            {'type_id': 'space_135231', 'type_name': '晓杰广场舞'},
            {'type_id': 'space_322247', 'type_name': '吉美广场'},
        ]

    def getName(self):
        return '糖豆'

    def init(self, extend=''):
        if not extend:
            return
        try:
            if isinstance(extend, str) and extend.strip().startswith('{'):
                extend = json.loads(extend)
            if isinstance(extend, dict):
                if extend.get('host'):
                    self.host = str(extend['host']).rstrip('/')
                if extend.get('api'):
                    self.api = str(extend['api']).rstrip('/')
        except Exception:
            pass

    def fetch(self, url, timeout=15):
        if requests is None:
            return None
        try:
            r = requests.get(
                url,
                headers={
                    'User-Agent': self.ua,
                    'Referer': self.host + '/',
                    'Origin': self.host,
                    'Accept': 'application/json, text/plain, */*',
                },
                timeout=timeout,
            )
            if r.status_code >= 400:
                return None
            return r
        except Exception as e:
            print('fetch', url, e)
            return None

    def api_get(self, path):
        r = self.fetch(self.api + path)
        if r is None:
            return None
        try:
            j = r.json()
            if j.get('code') != 0:
                return None
            return j.get('data')
        except Exception:
            return None

    def homeContent(self, filter):
        return {'class': self.classes, 'filters': {}}

    def homeVideoContent(self):
        data = self.api_get('/mtangdou/home/feed?page=1') or []
        return {'list': [v for v in (self._map(i) for i in data) if v][:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'home')
        if tid == 'home':
            data = self.api_get('/mtangdou/home/feed?page=%s' % pg) or []
        else:
            uid = tid.replace('space_', '')
            data = self.api_get('/mtangdou/space/videos?uid=%s&page=%s' % (uid, pg)) or []
        if not isinstance(data, list):
            data = []
        videos = [v for v in (self._map(i) for i in data) if v]
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 20,
            'total': 9999,
        }

    def detailContent(self, ids):
        vid = re.sub(r'\D', '', str(ids[0] if isinstance(ids, (list, tuple)) else ids))
        data = self.api_get('/mtangdou/video/play?vid=%s' % vid) or {}
        play_url = data.get('play_url') or ''
        name = data.get('title') or vid
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': self._pic(data.get('cover')),
                'vod_actor': data.get('name') or '',
                'vod_content': name,
                'vod_remarks': self._dur(data.get('duration')) or '糖豆',
                'vod_play_from': '糖豆直链' if play_url else '糖豆',
                'vod_play_url': ('正片$' + play_url) if play_url else ('正片$' + self.host + '/play/' + vid),
            }]
        }

    def searchContent(self, key, quick, pg='1'):
        kw = str(key or '').strip()
        if not kw:
            return {'list': []}
        # 官方 search 不可用：推荐流 + 老师空间关键词过滤
        tasks_paths = ['/mtangdou/home/feed?page=%s' % p for p in range(1, 4)]
        for c in self.classes:
            if c['type_id'].startswith('space_'):
                uid = c['type_id'].replace('space_', '')
                tasks_paths.append('/mtangdou/space/videos?uid=%s&page=1' % uid)
        seen, videos = set(), []
        for path in tasks_paths:
            data = self.api_get(path) or []
            if not isinstance(data, list):
                continue
            for it in data:
                v = self._map(it)
                if not v or v['vod_id'] in seen:
                    continue
                name = v.get('vod_name') or ''
                teacher = it.get('name') or ''
                if kw not in name and kw not in teacher:
                    continue
                seen.add(v['vod_id'])
                videos.append(v)
        return {'list': videos[:60], 'page': 1}

    def searchContentPage(self, key, quick, pg=1):
        return self.searchContent(key, quick, pg)

    def playerContent(self, flag, id, vipFlags):
        url = str(id or '')
        hdr = {'User-Agent': self.ua, 'Referer': self.host + '/'}
        if url.startswith('http') and any(x in url for x in ('.mp4', '.m3u8', 'sign=', 'aqiniu')):
            return {'parse': 0, 'url': url, 'header': hdr}
        vid = re.sub(r'\D', '', url) or url
        data = self.api_get('/mtangdou/video/play?vid=%s' % vid) or {}
        if data.get('play_url'):
            return {'parse': 0, 'url': data['play_url'], 'header': hdr}
        return {'parse': 1, 'url': self.host + '/play/' + vid, 'header': hdr}

    def isVideoFormat(self, url):
        if not url:
            return False
        low = str(url).lower()
        return any(x in low for x in ('.mp4', '.m3u8', 'aqiniu', 'sign='))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def _pic(self, u):
        if not u:
            return ''
        u = str(u)
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('http'):
            return u
        return 'https://bimg.tangdou.com' + (u if u.startswith('/') else '/' + u)

    def _dur(self, sec):
        try:
            sec = int(sec or 0)
        except Exception:
            return ''
        if not sec:
            return ''
        return "%d'%02d" % (sec // 60, sec % 60)

    def _map(self, it):
        if not it or not it.get('vid'):
            return None
        return {
            'vod_id': str(it['vid']),
            'vod_name': it.get('title') or str(it['vid']),
            'vod_pic': self._pic(it.get('cover')),
            'vod_remarks': self._dur(it.get('duration')) or (it.get('name') or ''),
        }


if __name__ == '__main__':
    sp = Spider()
    print('classes', len(sp.homeContent(True)['class']))
    for tid in ['home', 'space_170881', 'space_36852', 'space_350798']:
        cat = sp.categoryContent(tid, 1, {}, {})
        print('cat', tid, len(cat.get('list') or []))
    s = sp.searchContent('广场舞', False, 1)
    print('search 广场舞', len(s.get('list') or []))
    s2 = sp.searchContent('慧慧', False, 1)
    print('search 慧慧', len(s2.get('list') or []), (s2.get('list') or [{}])[0].get('vod_name', '')[:30])
    if s2.get('list'):
        p = sp.playerContent('x', s2['list'][0]['vod_id'], [])
        print('play', p.get('parse'), (p.get('url') or '')[:70])
