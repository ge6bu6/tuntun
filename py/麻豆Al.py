import sys
import json
import requests
import urllib.parse

try:
    from base.spider import BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): pass
        def homeVideoContent(self): pass
        def categoryContent(self, tid, pg, filter, extend): pass
        def detailContent(self, ids): pass
        def searchContent(self, key, quick, pg="1"): pass
        def playerContent(self, flag, id, vipFlags): pass
        def localProxy(self, param): pass
        def isVideoFormat(self, url): pass
        def manualVideoCheck(self): pass
        def getName(self): pass
        def destroy(self): pass

class Spider(BaseSpider):
    def __init__(self):
        self.siteUrl = 'https://www.madouai.xyz'
        self.apiUrl = 'https://www.madouai.xyz/api/v1'
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.madouai.xyz/',
            'Origin': 'https://www.madouai.xyz',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def getName(self):
        return "麻豆AI"

    def init(self, extend=""):
        pass

    def homeContent(self, filter):
        r = self.session.get(self.apiUrl + '/categories', timeout=15)
        cats = r.json()['data']
        classes = []
        for c in cats:
            if c.get('type') == 'video' and c.get('enabled'):
                classes.append({'type_name': c['name'], 'type_id': str(c['id'])})
        r = self.session.get(self.apiUrl + '/videos', params={'page': 1, 'pageSize': 20}, timeout=15)
        items = r.json()['data']['items']
        videos = []
        for item in items:
            videos.append({
                'vod_id': str(item['id']),
                'vod_name': item['title'],
                'vod_pic': self.siteUrl + item['coverUrl'],
                'vod_remarks': item.get('categoryName', '') + ' | ' + self._fmt_time(item.get('durationSec', 0)),
            })
        return {'class': classes, 'list': videos}

    def homeVideoContent(self):
        r = self.session.get(self.apiUrl + '/videos', params={'page': 1, 'pageSize': 20}, timeout=15)
        items = r.json()['data']['items']
        videos = []
        for item in items:
            videos.append({
                'vod_id': str(item['id']),
                'vod_name': item['title'],
                'vod_pic': self.siteUrl + item['coverUrl'],
                'vod_remarks': item.get('categoryName', '') + ' | ' + self._fmt_time(item.get('durationSec', 0)),
            })
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        r = self.session.get(self.apiUrl + '/videos', params={'categoryId': tid, 'page': int(pg), 'pageSize': 20}, timeout=15)
        data = r.json()['data']
        items = data['items']
        videos = []
        for item in items:
            videos.append({
                'vod_id': str(item['id']),
                'vod_name': item['title'],
                'vod_pic': self.siteUrl + item['coverUrl'],
                'vod_remarks': item.get('categoryName', '') + ' | ' + self._fmt_time(item.get('durationSec', 0)),
            })
        return {
            'list': videos,
            'page': int(pg),
            'pagecount': (data['total'] + 19) // 20,
            'limit': 20,
            'total': data['total']
        }

    def detailContent(self, ids):
        vid = ids[0]
        r = self.session.get(self.apiUrl + '/videos/' + vid, timeout=15)
        item = r.json()['data']
        play_url = self.apiUrl + '/m3u8/proxy?path=' + urllib.parse.quote(item['videoUrl'], safe='')
        return {
            'list': [{
                'vod_id': str(item['id']),
                'vod_name': item['title'],
                'vod_pic': self.siteUrl + item['coverUrl'],
                'vod_content': item.get('description') or item['title'],
                'vod_play_from': '麻豆AI',
                'vod_play_url': '第1集$' + play_url,
                'vod_remarks': item.get('categoryName', ''),
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        r = self.session.get(self.apiUrl + '/videos', params={'keyword': key, 'page': int(pg), 'pageSize': 20}, timeout=15)
        data = r.json()['data']
        items = data['items']
        videos = []
        for item in items:
            videos.append({
                'vod_id': str(item['id']),
                'vod_name': item['title'],
                'vod_pic': self.siteUrl + item['coverUrl'],
                'vod_remarks': item.get('categoryName', '') + ' | ' + self._fmt_time(item.get('durationSec', 0)),
            })
        return {
            'list': videos,
            'page': int(pg),
            'pagecount': (data['total'] + 19) // 20,
            'limit': 20,
            'total': data['total']
        }

    def playerContent(self, flag, id, vipFlags):
        return {
            'parse': 0,
            'playUrl': '',
            'url': id,
            'header': json.dumps(self.headers),
        }

    def localProxy(self, param):
        url = param.get('url', '') if isinstance(param, dict) else str(param)
        parsed = urllib.parse.urlparse(url)
        qs = urllib.parse.parse_qs(parsed.query)
        path = qs.get('path', [''])[0]
        if not path:
            return [404, 'text/plain', 'Not Found']
        proxy_url = self.apiUrl + '/m3u8/proxy?path=' + urllib.parse.quote(path, safe='')
        r = self.session.get(proxy_url, headers=self.headers, timeout=30)
        ct = r.headers.get('Content-Type', 'application/octet-stream')
        return [200, ct, r.content]

    def _fmt_time(self, sec):
        if not sec:
            return ''
        m = sec // 60
        s = sec % 60
        return str(m) + ':' + format(s, '02d')

    def isVideoFormat(self, url):
        return '.m3u8' in url or '.mp4' in url

    def manualVideoCheck(self):
        return True

    def destroy(self):
        pass
