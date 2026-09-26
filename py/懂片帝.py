# -*- coding: utf-8 -*-
# 懂片帝 / dongpian1.com (dongpian.ai) TVBox 爬虫
# 站点为 React SPA，公开数据走 /v1 签名 API
# 签名: HMAC-SHA256(secret, METHOD\\npath?query\\ntimestamp\\nnonce)
# 可浏览公开片单与影片元数据；真实 m3u8 需站内播放器会话，本源播放走站内 /player 页 parse=1
import hashlib
import hmac
import json
import os
import re
import sys
import time
from urllib.parse import quote, urlencode

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    BaseSpider = object

try:
    import requests
except Exception:
    requests = None

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')
DEFAULT_HOST = 'https://dongpian1.com'
# 前端写死的请求签名密钥 (movie-card-runtime)
SIGN_SECRET = '8b9a908a05eac640e1ee06f52acaa741bfe4ba9e004eeffdbeb635e532e06666'

CATS = [
    ('hot', '热门片单'),
    ('latest', '最新片单'),
]


class Spider(BaseSpider):

    def __init__(self):
        try:
            super().__init__()
        except Exception:
            pass
        self.host = DEFAULT_HOST
        self._sess = None
        if requests is not None:
            try:
                self._sess = requests.Session()
            except Exception:
                self._sess = None

    def getName(self):
        return '懂片帝'

    def init(self, extend=''):
        ext = extend
        if isinstance(ext, dict):
            ext = ext.get('ext') or ext.get('host') or ext.get('url') or ''
        if isinstance(ext, (list, tuple)):
            ext = ext[0] if ext else ''
        ext = str(ext or '').strip().strip('"').strip("'")
        if ext.startswith('{'):
            try:
                o = json.loads(ext)
                ext = o.get('host') or o.get('url') or ''
            except Exception:
                pass
        if ext.startswith('http'):
            self.host = ext.rstrip('/')

    def destroy(self):
        if self._sess is not None:
            try:
                self._sess.close()
            except Exception:
                pass

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4)(\?|$)', str(url), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return [404, 'text/plain', '']

    # ---------- 签名请求 ----------
    def _sign_headers(self, method, path):
        ts = str(int(time.time() * 1000))
        nonce = os.urandom(16).hex()
        msg = '%s\n%s\n%s\n%s' % (method.upper(), path, ts, nonce)
        sig = hmac.new(SIGN_SECRET.encode(), msg.encode(), hashlib.sha256).hexdigest()
        return {
            'User-Agent': UA,
            'Accept': 'application/json',
            'Referer': self.host + '/',
            'Origin': self.host,
            'x-ai-movie-timestamp': ts,
            'x-ai-movie-nonce': nonce,
            'x-ai-movie-signature': sig,
        }

    def _api(self, path, method='GET', body=None, timeout=15):
        if not path.startswith('/'):
            path = '/' + path
        url = self.host + path
        headers = self._sign_headers(method, path)
        try:
            if self._sess is not None:
                if body is not None:
                    headers['Content-Type'] = 'application/json'
                    r = self._sess.request(
                        method, url, headers=headers,
                        data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
                        timeout=timeout, verify=False,
                    )
                else:
                    r = self._sess.request(method, url, headers=headers, timeout=timeout, verify=False)
                if r.status_code >= 400:
                    return None
                return r.json()
        except Exception:
            return None
        return None

    # ---------- 解析 ----------
    def _playlist_item(self, p):
        cover = p.get('cover') or {}
        pic = cover.get('poster_url') or ''
        if not pic and isinstance(cover.get('posters'), list) and cover['posters']:
            pic = cover['posters'][0]
        return {
            'vod_id': 'pl:' + str(p.get('id') or ''),
            'vod_name': p.get('title') or '片单',
            'vod_pic': pic,
            'vod_remarks': '%s部' % (p.get('item_count') or 0),
            'vod_tag': 'folder',
        }

    def _video_item(self, it):
        tid = str(it.get('target_id') or it.get('id') or '')
        disp = it.get('display') or {}
        remarks = ''
        if disp.get('year'):
            remarks = str(disp.get('year'))
        if disp.get('area'):
            remarks = (remarks + ' ' + str(disp.get('area'))).strip()
        return {
            'vod_id': tid,
            'vod_name': it.get('title') or tid,
            'vod_pic': it.get('poster_url') or '',
            'vod_remarks': remarks or str(it.get('content_kind') or ''),
        }

    # ---------- TVBox ----------
    def homeContent(self, filter):
        classes = [{'type_id': a, 'type_name': b} for a, b in CATS]
        return {
            'class': classes,
            'filters': {
                'hot': [{'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最热', 'v': 'hot'}, {'n': '最新', 'v': 'latest'}
                ]}],
                'latest': [{'key': 'sort', 'name': '排序', 'value': [
                    {'n': '最新', 'v': 'latest'}, {'n': '最热', 'v': 'hot'}
                ]}],
            },
        }

    def homeVideoContent(self):
        data = self._api('/v1/playlists/explore?sort=hot') or {}
        items = [self._playlist_item(p) for p in (data.get('data') or [])]
        return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        page = max(1, int(pg or 1))
        tid = str(tid or '').strip()
        extend = extend if isinstance(extend, dict) else {}

        # 片单目录展开
        if tid.startswith('pl:'):
            pid = tid[3:]
            path = '/v1/playlists/' + quote(pid, safe='')
            data = self._api(path) or {}
            items = [self._video_item(it) for it in (data.get('items') or [])]
            has_more = bool((data.get('items_page') or {}).get('has_more'))
            return {
                'list': items,
                'page': page,
                'pagecount': page + 1 if has_more else page,
                'limit': len(items) or 24,
                'total': data.get('item_count') or len(items),
            }

        sort = str(extend.get('sort') or tid or 'hot')
        if sort not in ('hot', 'latest'):
            sort = 'hot'
        path = '/v1/playlists/explore?sort=' + sort
        data = self._api(path) or {}
        items = [self._playlist_item(p) for p in (data.get('data') or [])]
        return {
            'list': items,
            'page': page,
            'pagecount': page,  # 接口 has_more 常为 false，单页约 20
            'limit': len(items) or 20,
            'total': len(items),
        }

    def searchContent(self, key, quick, pg='1'):
        # 站内搜索走 AI 会话，无公开检索 API；用片单标题本地过滤作弱搜索
        page = max(1, int(pg or 1))
        key = str(key or '').strip()
        data = self._api('/v1/playlists/explore?sort=hot') or {}
        latest = self._api('/v1/playlists/explore?sort=latest') or {}
        merged = (data.get('data') or []) + (latest.get('data') or [])
        seen, items = set(), []
        for p in merged:
            pid = p.get('id')
            title = p.get('title') or ''
            if not pid or pid in seen:
                continue
            if key and key not in title:
                continue
            seen.add(pid)
            items.append(self._playlist_item(p))
        return {'list': items, 'page': page, 'pagecount': page}

    def detailContent(self, ids):
        raw = str(ids[0] if isinstance(ids, (list, tuple)) else ids).strip()
        # 片单详情：展开为多「集」
        if raw.startswith('pl:'):
            pid = raw[3:]
            data = self._api('/v1/playlists/' + quote(pid, safe='')) or {}
            items = data.get('items') or []
            play = []
            for i, it in enumerate(items):
                tid = str(it.get('target_id') or '')
                if not tid:
                    continue
                name = it.get('title') or ('第%d部' % (i + 1))
                play.append('%s$%s' % (name, tid))
            cover = data.get('cover') or {}
            vod = {
                'vod_id': raw,
                'vod_name': data.get('title') or '片单',
                'vod_pic': cover.get('poster_url') or '',
                'vod_content': data.get('description') or ('共%s部' % (data.get('item_count') or len(items))),
                'vod_remarks': '%s部' % (data.get('item_count') or 0),
                'vod_play_from': '片单',
                'vod_play_url': '#'.join(play),
            }
            return {'list': [vod]}

        # 影片 catalog
        path = '/v1/catalog/' + quote(raw, safe='')
        data = self._api(path) or {}
        if not data:
            return {'list': []}
        ep_data = self._api(path + '/episodes') or {}
        episodes = ep_data.get('episodes') or data.get('episodes') or []
        variants = (self._api(path + '/variants') or {}).get('variants') or data.get('variants') or []

        play_from, play_url = [], []
        if episodes:
            eps = []
            for i, ep in enumerate(episodes):
                name = ep.get('title') or ('第%d集' % (i + 1))
                # 用 variant + episode token 交给播放器页
                token = ep.get('token') or ep.get('id') or ''
                eps.append('%s$%s||%s' % (name, raw, token))
            play_from.append('默认')
            play_url.append('#'.join(eps))
        if variants and len(variants) > 1:
            for v in variants:
                vid = v.get('variant_id') or v.get('id') or ''
                if not vid:
                    continue
                label = v.get('season_label') or v.get('title') or '线路'
                play_from.append(label)
                play_url.append('播放$%s' % vid)

        if not play_url:
            play_from = ['懂片帝']
            play_url = ['正片$%s' % raw]

        actors = data.get('actors') or []
        directors = data.get('directors') or []
        genres = data.get('genres') or []
        vod = {
            'vod_id': raw,
            'vod_name': data.get('title') or raw,
            'vod_pic': data.get('poster_url') or data.get('carousel_url') or '',
            'vod_year': str(data.get('year') or ''),
            'vod_area': data.get('area') or '',
            'vod_actor': ','.join(actors) if isinstance(actors, list) else str(actors or ''),
            'vod_director': ','.join(directors) if isinstance(directors, list) else str(directors or ''),
            'type_name': ','.join(genres) if isinstance(genres, list) else str(genres or ''),
            'vod_content': (data.get('description') or '')[:800],
            'vod_remarks': data.get('remarks') or data.get('episode_progress_text') or '',
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def playerContent(self, flag, id, vipFlags):
        raw = str(id or '').strip()
        variant, _, token = raw.partition('||')
        variant = variant or raw
        # 站内播放页（SPA），由壳解析或外部浏览器打开
        player = self.host + '/player/' + quote(variant, safe='')
        if token:
            player += '?episode=' + quote(token, safe='')
        return {
            'parse': 1,
            'jx': 0,
            'url': player,
            'header': {
                'User-Agent': UA,
                'Referer': self.host + '/',
            },
        }


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print(sp.homeContent(False))
    print(sp.categoryContent('hot', '1', False, {}))
