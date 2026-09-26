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
        self.siteUrl = 'https://m.sooplive.com'
        self.playHost = 'https://play.sooplive.com'
        self.liveApi = 'https://live.sooplive.com/afreeca/player_live_api.php'
        self.listHosts = [
            'https://live.sooplive.co.kr',
            'https://live.sooplive.com',
            'https://sch.sooplive.co.kr',
        ]
        self.userAgent = (
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) '
            'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        )
        self.channels = {
            'all': {'name': '全部直播', 'cate': ''},
            '0004': {'name': '游戏', 'cate': '0004'},
            '0002': {'name': '生活', 'cate': '0002'},
            '0008': {'name': '音乐', 'cate': '0008'},
            '0010': {'name': '体育', 'cate': '0010'},
            '0006': {'name': '美食', 'cate': '0006'},
            '0012': {'name': 'Talk', 'cate': '0012'},
        }

    def getName(self):
        return 'SOOP直播'

    def init(self, extend=""):
        pass

    def _headers(self, referer=None):
        return {
            'User-Agent': self.userAgent,
            'Referer': referer or (self.siteUrl + '/'),
            'Origin': 'https://play.sooplive.com',
            'Accept': 'application/json, text/plain, */*',
        }

    def fetch(self, url, headers=None, params=None, method='GET', data=None):
        if headers is None:
            headers = self._headers()
        try:
            if requests:
                if method == 'POST':
                    return requests.post(url, headers=headers, data=data, timeout=15)
                return requests.get(url, headers=headers, params=params, timeout=15)
            from urllib.request import Request, urlopen
            full = url
            if params and method == 'GET':
                full += ('&' if '?' in url else '?') + urllib.parse.urlencode(params)
            body = urllib.parse.urlencode(data or {}).encode() if method == 'POST' else None
            raw = urlopen(Request(full, data=body, headers=headers, method=method), timeout=15).read()

            class R:
                def __init__(self, raw):
                    self.text = raw.decode('utf-8', 'ignore')

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_json(self, url, params=None, method='GET', data=None, headers=None):
        resp = self.fetch(url, headers=headers, params=params, method=method, data=data)
        if not resp:
            return {}
        try:
            return resp.json()
        except Exception:
            text = getattr(resp, 'text', '') or ''
            m = re.search(r'\{[\s\S]+\}', text)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    return {}
            return {}

    def _pic(self, user_id):
        if not user_id:
            return ''
        pre = (user_id[:2] if len(user_id) >= 2 else user_id).lower()
        return 'https://stimg.sooplive.com/LOGO/%s/%s/m/%s.webp' % (pre, user_id, user_id)

    def _map(self, item):
        if not item:
            return None
        uid = str(item.get('user_id') or item.get('bj_id') or item.get('userId') or item.get('bid') or '')
        bno = str(item.get('broad_no') or item.get('bno') or item.get('broadNo') or '')
        if not uid:
            return None
        title = item.get('broad_title') or item.get('title') or item.get('broadTitle') or uid
        nick = item.get('user_nick') or item.get('bj_nick') or item.get('userNick') or uid
        viewers = item.get('total_view_cnt') or item.get('view_cnt') or item.get('pc_view_cnt') or item.get('viewer') or ''
        cate = item.get('broad_cate_name') or item.get('category') or ''
        pic = item.get('broad_thumb') or item.get('thumb') or self._pic(uid)
        if pic and pic.startswith('//'):
            pic = 'https:' + pic
        vod_id = uid + ('|' + bno if bno else '')
        return {
            'vod_id': vod_id,
            'vod_name': title,
            'vod_pic': pic,
            'vod_remarks': str(viewers) + '人' if viewers else (cate or nick),
            'vod_actor': nick,
        }

    def _pick_list(self, js):
        d = js.get('data') if isinstance(js, dict) else js
        if isinstance(d, list):
            return d
        if not isinstance(d, dict):
            return []
        for k in ('broad', 'list', 'broad_list', 'lives', 'result', 'CHANNEL'):
            v = d.get(k) if isinstance(d, dict) else None
            if isinstance(v, list):
                return v
            if isinstance(v, dict) and isinstance(v.get('broad'), list):
                return v.get('broad')
        if isinstance(js.get('broad'), list):
            return js.get('broad')
        return []

    def _live_list(self, page=1, cate=''):
        videos = []
        params_sets = [
            {'m': 'liveListHash', 'pageNo': str(page), 'pageSize': '30', 'order_type': 'view_cnt', 'cate_no': cate},
            {'page': str(page), 'order_type': 'view_cnt', 'selectType': 'action', 'selectValue': cate or 'all'},
            {'m': 'liveList', 'page': str(page), 'orderBy': 'view_cnt'},
        ]
        paths = ['/api.php', '/api/main_broad_list_api.php', '/afreeca/main_broad_list_api.php']
        for host in self.listHosts:
            for path in paths:
                for params in params_sets:
                    js = self.fetch_json(host + path, params=params)
                    for item in self._pick_list(js):
                        v = self._map(item)
                        if v:
                            videos.append(v)
                    if videos:
                        return videos
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos = self._live_list(1, '')[:24]
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        cate = self.channels.get(str(tid), {}).get('cate', '')
        videos = []
        try:
            videos = self._live_list(pg, cate)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 30,
            'total': 9999,
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            js = self.fetch_json('https://sch.sooplive.co.kr/api.php', {
                'm': 'searchLiveList',
                'v': '1.0',
                'szKeyword': key,
                'nPageNo': str(pg),
                'nListCnt': '20',
            })
            for item in self._pick_list(js):
                v = self._map(item)
                if v:
                    videos.append(v)
            if not videos:
                js = self.fetch_json('https://sch.sooplive.com/api.php', {
                    'm': 'broadSearch',
                    'szKeyword': key,
                    'nPageNo': str(pg),
                })
                for item in self._pick_list(js):
                    v = self._map(item)
                    if v:
                        videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 20 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def detailContent(self, ids):
        raw = str((ids or [''])[0])
        parts = raw.split('|')
        uid = parts[0]
        bno = parts[1] if len(parts) > 1 else ''
        title, nick, pic = uid, uid, self._pic(uid)
        try:
            js = self.fetch_json(self.liveApi, method='POST', data={
                'from_api': '0',
                'mode': 'landing',
                'player_type': 'html5',
                'stream_type': 'common',
                'type': 'live',
                'bid': uid,
                'bno': bno,
                'pwd': '',
            }, headers=self._headers(self.playHost + '/' + uid))
            ch = (js.get('CHANNEL') or js) if isinstance(js, dict) else {}
            title = ch.get('TITLE') or title
            nick = ch.get('BJNICK') or nick
            if ch.get('BNO'):
                bno = str(ch.get('BNO'))
        except Exception as e:
            print('获取详情失败: %s' % e)
        play_id = uid + ('|' + bno if bno else '')
        return {
            'list': [{
                'vod_id': play_id,
                'vod_name': title,
                'vod_pic': pic,
                'vod_actor': nick,
                'vod_remarks': 'LIVE',
                'vod_content': '%s 正在直播' % nick,
                'vod_play_from': 'SOOP',
                'vod_play_url': '直播$%s' % play_id,
            }]
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.playHost + '/',
            'Origin': 'https://play.sooplive.com',
        }
        raw = str(id or '')
        if raw.startswith('http') and self.isVideoFormat(raw):
            return {'parse': 0, 'url': raw, 'header': header}
        parts = raw.split('|')
        uid = parts[0]
        bno = parts[1] if len(parts) > 1 else ''
        page = self.playHost + '/' + uid + (('/' + bno) if bno else '')
        try:
            js = self.fetch_json(self.liveApi, method='POST', data={
                'from_api': '0',
                'mode': 'landing',
                'player_type': 'html5',
                'stream_type': 'common',
                'type': 'live',
                'bid': uid,
                'bno': bno,
                'pwd': '',
            }, headers=self._headers(page))
            ch = js.get('CHANNEL') or {}
            bno = str(ch.get('BNO') or bno)
            rmd = ch.get('RMD') or ''
            cdn = ch.get('CDN') or 'gs_cdn_pc_web'
            if not bno or not rmd:
                return {'parse': 1, 'url': page, 'header': header}
            aid_js = self.fetch_json(self.liveApi, method='POST', data={
                'from_api': '0',
                'mode': 'landing',
                'player_type': 'html5',
                'stream_type': 'common',
                'type': 'aid',
                'bid': uid,
                'bno': bno,
                'pwd': '',
                'quality': 'hd',
            }, headers=self._headers(page))
            aid = (aid_js.get('CHANNEL') or {}).get('AID') or ''
            cdn_type = 'gs_cdn_pc_web' if 'gs_cdn' in str(cdn) else ('lg_cdn_pc_web' if 'lg_cdn' in str(cdn) else cdn)
            info = self.fetch_json(rmd.rstrip('/') + '/broad_stream_assign.html', params={
                'return_type': cdn_type,
                'broad_key': '%s-common-hd-hls' % bno,
            }, headers=self._headers(page))
            view_url = info.get('view_url') or ''
            if view_url and aid:
                sep = '&' if '?' in view_url else '?'
                return {'parse': 0, 'url': view_url + sep + 'aid=' + urllib.parse.quote(aid), 'header': header}
            if view_url:
                return {'parse': 0, 'url': view_url, 'header': header}
        except Exception as e:
            print('获取播放内容失败: %s' % e)
        return {'parse': 1, 'url': page, 'header': header}

    def isVideoFormat(self, url):
        if not url:
            return False
        u = url.lower()
        return any(x in u for x in ('.m3u8', '.mp4', '.flv'))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    spider = Spider()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
