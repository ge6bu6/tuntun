# -*- coding: utf-8 -*-
# JAVMenu https://javmenu.com/zh
# 模板参考: 91成人短剧.py
import re
import json
import sys
from urllib.parse import quote

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def init(self, extend=""):
            pass

try:
    import requests
except ImportError:
    requests = None


class Spider(BaseSpider):
    def __init__(self):
        self.host = 'https://javmenu.com'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/131.0.0.0 Safari/537.36'
        )
        # 在线分类优先（有 data-m3u8），目录类次之
        self.channels = {
            'censored_online': {'name': '有码在线', 'path': '/zh/censored/online'},
            'uncensored_online': {'name': '无码在线', 'path': '/zh/uncensored/online'},
            'chinese_online': {'name': '中文在线', 'path': '/zh/chinese/online'},
            'fc2_online': {'name': 'FC2在线', 'path': '/zh/fc2/online'},
            'western_online': {'name': '欧美在线', 'path': '/zh/western/online'},
            'hanime_online': {'name': '里番在线', 'path': '/zh/hanime/online'},
            'censored': {'name': '有码', 'path': '/zh/censored'},
            'uncensored': {'name': '无码', 'path': '/zh/uncensored'},
            'chinese': {'name': '中文', 'path': '/zh/chinese'},
            'fc2': {'name': 'FC2', 'path': '/zh/fc2'},
            'rank_day': {'name': '日榜', 'path': '/zh/rank/censored/day'},
            'rank_week': {'name': '周榜', 'path': '/zh/rank/censored/week'},
            'rank_month': {'name': '月榜', 'path': '/zh/rank/censored/month'},
        }

    def getName(self):
        return 'JAVMenu'

    def init(self, extend=""):
        if extend:
            try:
                conf = json.loads(extend) if isinstance(extend, str) and extend.strip().startswith('{') else {}
                if conf.get('host'):
                    self.host = conf['host'].rstrip('/')
            except Exception:
                pass

    def _headers(self, referer=None):
        return {
            'User-Agent': self.ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.host + '/zh'),
        }

    def _get(self, url, referer=None):
        try:
            if requests is None:
                import urllib.request
                req = urllib.request.Request(url, headers=self._headers(referer))
                with urllib.request.urlopen(req, timeout=18) as resp:
                    return resp.read().decode('utf-8', 'ignore')
            r = requests.get(url, headers=self._headers(referer), timeout=18, verify=False)
            r.encoding = 'utf-8'
            return r.text if r.status_code == 200 else ''
        except Exception as e:
            print('GET error', url, e)
            return ''

    def _abs(self, u):
        if not u:
            return ''
        u = u.strip().replace('\\/', '/')
        if u.startswith('//'):
            return 'https:' + u
        if u.startswith('/'):
            return self.host + u
        if not u.startswith('http'):
            return self.host + '/' + u
        return u

    def _parse_list(self, html):
        videos, seen = [], set()
        if not html:
            return videos
        # 番号详情: /zh/ABC-123 或 /zh/FC2-PPV-123
        for m in re.finditer(
            r'href="(https?://(?:www\.)?javmenu\.com/zh/([A-Za-z0-9]+-[A-Za-z0-9._-]+))"',
            html, re.I
        ):
            href, code = m.group(1), m.group(2)
            if href in seen:
                continue
            # 排除分类/搜索等非番号
            low = code.lower()
            if low in ('censored', 'uncensored', 'chinese', 'western', 'hanime', 'fc2', 'search', 'rank'):
                continue
            if not re.search(r'\d', code):
                continue
            seen.add(href)
            block = html[max(0, m.start() - 200):m.end() + 800]
            title = ''
            tm = re.search(r'(?:title|alt)=["\']([^"\']{2,200})["\']', block)
            if tm:
                title = tm.group(1).strip()
            if not title or len(title) < 2:
                title = code
            pic = ''
            for pat in (
                r'data-src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                r'src=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            ):
                pm = re.search(pat, block, re.I)
                if pm and 'logo' not in pm.group(1) and 'loading' not in pm.group(1):
                    pic = self._abs(pm.group(1))
                    break
            videos.append({
                'vod_id': href,
                'vod_name': title[:90],
                'vod_pic': pic,
                'vod_remarks': code.upper(),
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'list': []}

    def homeVideoContent(self):
        html = self._get(self.host + '/zh/censored/online')
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'censored_online')
        info = self.channels.get(tid) or self.channels['censored_online']
        path = info['path']
        if pg <= 1:
            url = self.host + path
        else:
            sep = '&' if '?' in path else '?'
            url = self.host + path + sep + 'page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        pagecount = pg
        if videos and (len(videos) >= 12 or re.search(r'[?&]page=%d' % (pg + 1), html)):
            pagecount = pg + 1
        return {
            'list': videos,
            'page': pg,
            'pagecount': pagecount,
            'limit': 24,
            'total': 9999,
        }

    def detailContent(self, ids):
        result = {'list': []}
        if not ids:
            return result
        page_url = str(ids[0])
        if not page_url.startswith('http'):
            page_url = self.host + (page_url if page_url.startswith('/') else '/zh/' + page_url)
        html = self._get(page_url)
        if not html:
            return result

        name = ''
        m = re.search(r'<h1[^>]*>[\s\S]*?<strong>([\s\S]*?)</strong>', html)
        if m:
            name = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = re.sub(r'\s*[-|—].*$', '', m.group(1)).strip()

        pic = ''
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(https?://c\d+\.jdbstatic\.com/[^"\'\s]+\.(?:jpg|jpeg|png|webp))', html, re.I)
        if m:
            pic = self._abs(m.group(1))

        desc = ''
        m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            desc = m.group(1).strip()[:500]

        # 播放源 data-m3u8
        plays = []
        seen = set()
        for i, u in enumerate(re.findall(r'data-m3u8=["\']([^"\']+)["\']', html)):
            u = u.replace('&amp;', '&').strip()
            if not u or u in seen or 'vod.jpg' in u.lower() or u.endswith('.jpg'):
                continue
            seen.add(u)
            plays.append(('线路%d' % (i + 1), u))
        if not plays:
            for u in re.findall(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html):
                u = u.replace('&amp;', '&')
                if u in seen or 'vod.jpg' in u.lower():
                    continue
                seen.add(u)
                plays.append(('直链', u))

        if not plays:
            plays = [('正片', page_url)]

        play_url = '#'.join(['%s$%s' % (n, u) for n, u in plays])
        vod = {
            'vod_id': page_url,
            'vod_name': name or 'JAVMenu',
            'vod_pic': pic,
            'vod_remarks': '',
            'vod_actor': '',
            'vod_director': '',
            'vod_content': desc,
            'vod_play_from': 'JAVMenu',
            'vod_play_url': play_url,
        }
        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        key = (key or '').strip()
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        url = self.host + '/zh/search?wd=' + quote(key)
        if pg > 1:
            url += '&page=%d' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 12 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
        }
        play = str(id or '').strip()
        if play.startswith('http') and re.search(r'\.(m3u8|mp4)(\?|$)', play, re.I):
            return {'parse': 0, 'url': play, 'header': header}

        if not play.startswith('http'):
            play = self._abs(play)
        html = self._get(play, referer=self.host + '/zh')
        for u in re.findall(r'data-m3u8=["\']([^"\']+)["\']', html or ''):
            u = u.replace('&amp;', '&')
            if u and 'vod.jpg' not in u.lower() and not u.endswith('.jpg'):
                return {'parse': 0, 'url': u, 'header': header}
        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html or '')
        if m:
            return {'parse': 0, 'url': m.group(1).replace('&amp;', '&'), 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|ts)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None
