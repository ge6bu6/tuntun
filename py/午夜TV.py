#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
午夜TV (www.wuye.tv)
SPA + 签名 API: api8.wuye.tv
vv = MD5(publicKey & query.lower() & privateKey)
"""
import hashlib
import json
import re
import sys
import time
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
        self.siteUrl = 'https://www.wuye.tv'
        self.apiHost = 'https://api8.wuye.tv'
        self.userAgent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        self.publicKey = ''
        self.privateKey = []
        # cid 与爱壹帆同系后端
        self.channels = {
            '3': {'name': '电影', 'cid': '3'},
            '4': {'name': '剧集', 'cid': '4'},
            '5': {'name': '综艺', 'cid': '5'},
            '6': {'name': '动漫', 'cid': '6'},
            '7': {'name': '纪录片', 'cid': '7'},
            '95': {'name': '体育', 'cid': '95'},
        }

    def getName(self):
        return '午夜TV'

    def init(self, extend=""):
        if extend:
            try:
                if isinstance(extend, str) and extend.strip().startswith('{'):
                    ext = json.loads(extend)
                    if ext.get('host'):
                        self.siteUrl = str(ext['host']).rstrip('/')
                    if ext.get('api'):
                        self.apiHost = str(ext['api']).rstrip('/')
            except Exception:
                pass
        self._load_keys()

    def _load_keys(self):
        html = self.fetch_text(self.siteUrl + '/')
        m = re.search(
            r'"pConfig"\s*:\s*\{\s*"publicKey"\s*:\s*"([^"]+)"\s*,\s*"privateKey"\s*:\s*(\[[^\]]+\])',
            html or '',
        )
        if m:
            self.publicKey = m.group(1)
            try:
                self.privateKey = json.loads(m.group(2))
            except Exception:
                self.privateKey = re.findall(r'"([^"]+)"', m.group(2))
        if not self.publicKey:
            # 页面内兜底（可能随版本变化，优先从首页解析）
            self.publicKey = (
                'CJSuEJ8tD3SuD2umD35VLLDVCpGkCZ4kCounCJ9VEJPaCpDcP3KmEJ9YD64rEM4m'
                'D3GqOZavOMDYCZKtCMLVPMDZP69YE6CvPJ0tC3GsC3KmCJ5cOcGsCsPYCJamD30'
            )
            self.privateKey = ['SuEJJSuEJ8tD3SuD2umD']

    def _sign(self, query):
        if not self.publicKey:
            self._load_keys()
        pk_list = self.privateKey or ['']
        pk = pk_list[int(time.time() * 1000) % len(pk_list)]
        raw = self.publicKey + '&' + str(query).lower() + '&' + pk
        return hashlib.md5(raw.encode('utf-8')).hexdigest()

    def fetch(self, url, headers=None, params=None):
        if headers is None:
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json, text/html;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9',
            }
        try:
            if requests:
                resp = requests.get(url, headers=headers, params=params, timeout=15)
                # api 根路径可能 403 但业务接口 200
                if resp.status_code >= 500:
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
                    self.status_code = 200

                def json(self):
                    return json.loads(self.text)

            return R(raw)
        except Exception as e:
            print('请求失败: %s, %s' % (url, e))
            return None

    def fetch_text(self, url, params=None):
        resp = self.fetch(url, params=params)
        return getattr(resp, 'text', '') if resp else ''

    def _api(self, path, query):
        """query 为无 vv/pub 的查询串"""
        if not self.publicKey:
            self._load_keys()
        vv = self._sign(query)
        url = '%s%s?%s&vv=%s&pub=%s' % (
            self.apiHost, path, query, vv, self.publicKey
        )
        headers = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Accept': 'application/json',
        }
        resp = self.fetch(url, headers=headers)
        if not resp:
            return {}
        try:
            return resp.json()
        except Exception:
            text = getattr(resp, 'text', '') or ''
            try:
                return json.loads(text)
            except Exception:
                return {}

    def _map_item(self, e):
        if not isinstance(e, dict):
            return None
        vid = str(e.get('key') or e.get('contxt') or '')
        name = e.get('title') or e.get('name') or vid
        if not vid:
            return None
        pic = e.get('image') or e.get('imgPath') or ''
        remarks = e.get('cid') or e.get('lastName') or e.get('atypeName') or ''
        if e.get('hot'):
            remarks = (str(remarks) + ' · ' if remarks else '') + str(e.get('hot'))
        return {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'vod_remarks': str(remarks),
        }

    def _list(self, cid, pg=1, size=36):
        pg = int(pg or 1)
        # cid 格式: 0,1,{id}
        cid_s = str(cid)
        if not cid_s.startswith('0,'):
            cid_s = '0,1,' + cid_s
        query = (
            'cinema=1&page=%s&size=%s&orderby=0&desc=1&cid=%s'
            '&isserial=-1&isIndex=-1&isfree=-1'
        ) % (pg, size, cid_s)
        data = self._api('/api/list/Search', query)
        info = ((data.get('data') or {}).get('info') or [{}])
        block = info[0] if info else {}
        items = block.get('result') or []
        videos = []
        for e in items:
            v = self._map_item(e)
            if v:
                videos.append(v)
        total = int(block.get('recordcount') or len(videos))
        pagecount = max(1, (total + size - 1) // size) if total else pg
        return videos, pagecount, total

    def homeContent(self, filter):
        if not self.publicKey:
            self._load_keys()
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            videos, _, _ = self._list('3', 1, 24)
        except Exception as e:
            print('获取首页视频失败: %s' % e)
        return {'list': videos[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos, pagecount, total = [], pg, 0
        try:
            cid = self.channels.get(str(tid), {}).get('cid', str(tid) or '3')
            videos, pagecount, total = self._list(cid, pg)
        except Exception as e:
            print('获取分类内容失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 36,
            'total': total or len(videos),
        }

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        videos = []
        try:
            text = urllib.parse.quote(str(key or ''))
            # rank 搜索接口通常无需 vv（与爱壹帆一致）
            url = (
                'https://rankv21.wuye.tv/v3/list/briefsearch'
                '?tags=%s&orderby=4&page=%s&size=20&desc=0&isserial=-1&istitle=true'
            ) % (text, pg)
            headers = {
                'User-Agent': self.userAgent,
                'Referer': self.siteUrl + '/',
                'Accept': 'application/json',
            }
            resp = self.fetch(url, headers=headers)
            data = {}
            if resp:
                try:
                    data = resp.json()
                except Exception:
                    pass
            items = []
            info = ((data.get('data') or {}).get('info') or [])
            if info:
                items = info[0].get('result') or []
            if not items:
                # 回退列表搜索
                query = (
                    'cinema=1&page=%s&size=20&orderby=4&desc=0&cid=0,1'
                    '&isserial=-1&isIndex=-1&isfree=-1&tags=%s'
                ) % (pg, text)
                data = self._api('/api/list/Search', query)
                info = ((data.get('data') or {}).get('info') or [{}])
                items = (info[0] if info else {}).get('result') or []
            for e in items:
                v = self._map_item(e)
                if v:
                    videos.append(v)
        except Exception as e:
            print('搜索失败: %s' % e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 10 else pg,
            'limit': 20,
            'total': len(videos),
        }

    def detailContent(self, ids):
        vid = str((ids or [''])[0])
        name, pic, remarks = vid, '', ''
        parts = []
        try:
            query = 'cinema=1&vid=%s&lsk=1&taxis=0&cid=0,1,4' % urllib.parse.quote(vid)
            data = self._api('/v3/video/languagesplaylist', query)
            info = ((data.get('data') or {}).get('info') or [{}])
            block = info[0] if info else {}
            playlist = block.get('playList') or []
            for ep in playlist:
                ep_name = ep.get('name') or '播放'
                ep_key = ep.get('key') or vid
                parts.append('%s$%s' % (ep_name, ep_key))
            if not parts:
                parts.append('播放$%s' % vid)
            # 标题用列表信息补
            try:
                q2 = (
                    'cinema=1&page=1&size=1&orderby=0&desc=1&cid=0,1'
                    '&isserial=-1&isIndex=-1&isfree=-1&tags=%s'
                ) % urllib.parse.quote(vid)
                # 直接用 key 无法 tags，跳过
            except Exception:
                pass
        except Exception as e:
            print('获取详情失败: %s' % e)
            parts = ['播放$%s' % vid]
        return {
            'list': [{
                'vod_id': vid,
                'vod_name': name,
                'vod_pic': pic,
                'vod_remarks': remarks or ('%s路' % len(parts) if len(parts) > 1 else ''),
                'vod_content': '',
                'vod_play_from': '午夜TV',
                'vod_play_url': '#'.join(parts),
            }]
        }

    def _play_url(self, key):
        query = (
            'cinema=1&id=%s&a=0&lang=none&usersign=1&region=GL.'
            '&device=1&isMasterSupport=1'
        ) % urllib.parse.quote(str(key))
        data = self._api('/v3/video/play', query)
        info = ((data.get('data') or {}).get('info') or [{}])
        block = info[0] if info else {}
        paths = block.get('flvPathList') or []
        # 优先 HLS
        best = ''
        for p in paths:
            if not isinstance(p, dict):
                continue
            link = p.get('result') or p.get('link') or ''
            if not link:
                continue
            if p.get('isHls'):
                # 部分 CDN 需要再签空 query
                if '?' not in link:
                    link = link + '?vv=%s&pub=%s' % (self._sign(''), self.publicKey)
                return link
            if not best:
                best = link
        return best

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.userAgent,
            'Referer': self.siteUrl + '/',
            'Origin': self.siteUrl,
        }
        play = str(id or '')
        if self.isVideoFormat(play) and play.startswith('http'):
            return {'parse': 0, 'jx': '0', 'url': play, 'header': header}
        url = self._play_url(play)
        if url:
            return {'parse': 0, 'jx': '0', 'url': url, 'header': header}
        return {
            'parse': 1,
            'jx': '1',
            'url': self.siteUrl + '/#/play?id=' + urllib.parse.quote(play),
            'header': header,
        }

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
    spider.init()
    print(json.dumps(spider.homeContent(True), ensure_ascii=False, indent=2))
    r = spider.categoryContent('3', 1, {}, {})
    print('list', len(r.get('list') or []), (r.get('list') or [{}])[0].get('vod_name'))
    if r.get('list'):
        vid = r['list'][0]['vod_id']
        d = spider.detailContent([vid])
        print('detail', d['list'][0]['vod_play_url'][:80])
        token = d['list'][0]['vod_play_url'].split('#')[0].split('$')[-1]
        print(json.dumps(spider.playerContent('午夜TV', token, []), ensure_ascii=False)[:350])
