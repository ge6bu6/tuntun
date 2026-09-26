# -*- coding: utf-8 -*-
# 91成人短剧 https://91crdj.com
# 模板参考: 爱奇艺.py
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
        self.host = 'https://91crdj.com'
        self.ua = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
        self.channels = {
            'duanju': {'name': '成人短剧', 'path': '/duanju/'},
            'manju': {'name': '成人漫剧', 'path': '/manju/'},
            'zhenrenju': {'name': '真人剧', 'path': '/zhenrenju/'},
            'aiduanju': {'name': 'AI短剧', 'path': '/biaoqian/aiduanju/'},
            '91duanju': {'name': '91短剧', 'path': '/biaoqian/91duanju/'},
            'chengrenduanju': {'name': '成人短剧标签', 'path': '/biaoqian/chengrenduanju/'},
            'wudaduanju': {'name': '武打短剧', 'path': '/biaoqian/wudaduanju/'},
            'xuanhuanduanju': {'name': '玄幻短剧', 'path': '/biaoqian/xuanhuanduanju/'},
            'xianxiaduanju': {'name': '仙侠短剧', 'path': '/biaoqian/xianxiaduanju/'},
        }

    def getName(self):
        return '91成人短剧'

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
            'Referer': referer or (self.host + '/'),
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
        videos = []
        seen = set()
        if not html:
            return videos
        # /duanju/1339-slug/ 或 manju/zhenrenju
        for m in re.finditer(
            r'href="(https?://[^"]*?/(?:duanju|manju|zhenrenju)/(\d+)-([^/"]+)/)"',
            html
        ):
            href, vid, slug = m.group(1), m.group(2), m.group(3)
            # 排除分集 /1/
            if re.search(r'/\d+-\w+/\d+/?$', href):
                continue
            if href in seen:
                continue
            seen.add(href)
            block = html[max(0, m.start() - 400):m.end() + 600]
            title = ''
            tm = re.search(r'(?:title|alt)=["\']([^"\']{2,120})["\']', block)
            if tm:
                title = tm.group(1).strip()
            if not title or title in ('立即观看', '从头看'):
                title = slug
            pic = ''
            pm = re.search(
                r'(?:src|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
                block, re.I
            )
            if pm:
                pic = self._abs(pm.group(1))
            videos.append({
                'vod_id': href,
                'vod_name': title[:80],
                'vod_pic': pic,
                'vod_remarks': '',
            })
        return videos

    def homeContent(self, filter):
        classes = [{'type_id': k, 'type_name': v['name']} for k, v in self.channels.items()]
        return {'class': classes, 'list': []}

    def homeVideoContent(self):
        html = self._get(self.host + '/')
        return {'list': self._parse_list(html)[:24]}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or 'duanju')
        info = self.channels.get(tid, {'path': '/duanju/'})
        path = info.get('path', '/duanju/')
        if pg <= 1:
            url = self.host + path
        else:
            url = self.host + path.rstrip('/') + '/page/%d/' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        pagecount = pg + 1 if (videos and len(videos) >= 10) else pg
        if re.search(r'/page/%d/' % (pg + 1), html) or '下一页' in html:
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
            page_url = self.host + (page_url if page_url.startswith('/') else '/' + page_url)
        html = self._get(page_url)
        if not html:
            return result

        name = ''
        m = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if m:
            name = m.group(1).strip()
        if not name:
            m = re.search(r'<title>([^<]+)</title>', html)
            if m:
                name = re.sub(r'\s*[-|—].*$', '', m.group(1)).strip()

        pic = ''
        m = re.search(r'property=["\']og:image["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if not m:
            m = re.search(r'(?:src|data-src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)
        if m:
            pic = self._abs(m.group(1))

        desc = ''
        m = re.search(r'property=["\']og:description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if m:
            desc = m.group(1).strip()[:500]

        # 分集: /duanju/1339-slug/1/
        eps = []
        seen = set()
        for m in re.finditer(
            r'href="(https?://[^"]*?/(?:duanju|manju|zhenrenju)/\d+-[^/"]+/(\d+)/)"',
            html
        ):
            href, ep = m.group(1), m.group(2)
            if href in seen:
                continue
            seen.add(href)
            eps.append((int(ep), '第%s集' % ep, href))
        eps.sort(key=lambda x: x[0])
        if not eps:
            # 单集：详情页本身可能可播，或只有 /1/
            eps = [(1, '第1集', page_url.rstrip('/') + '/1/')]

        play_url = '#'.join(['%s$%s' % (n, u) for _, n, u in eps])
        vod = {
            'vod_id': page_url,
            'vod_name': name or '短剧',
            'vod_pic': pic,
            'vod_remarks': '共%d集' % len(eps),
            'vod_actor': '',
            'vod_director': '',
            'vod_content': desc,
            'vod_play_from': '91短剧',
            'vod_play_url': play_url,
        }
        result['list'] = [vod]
        return result

    def searchContent(self, key, quick, pg=1):
        return self.searchContentPage(key, quick, pg)

    def searchContentPage(self, key, quick, pg=1):
        pg = int(pg or 1)
        key = (key or '').strip()
        videos = []
        if not key:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': 24, 'total': 0}
        # /search/关键词/
        url = self.host + '/search/' + quote(key) + '/'
        if pg > 1:
            url = self.host + '/search/' + quote(key) + '/page/%d/' % pg
        html = self._get(url)
        videos = self._parse_list(html)
        return {
            'list': videos,
            'page': pg,
            'pagecount': pg + 1 if len(videos) >= 8 else pg,
            'limit': 24,
            'total': len(videos),
        }

    def playerContent(self, flag, id, vipFlags):
        header = {
            'User-Agent': self.ua,
            'Referer': self.host + '/',
            'Origin': self.host,
        }
        play = str(id or '').strip()
        if play.startswith('http') and re.search(r'\.(m3u8|mp4)(\?|$)', play, re.I):
            return {'parse': 0, 'url': play, 'header': header}

        if not play.startswith('http'):
            play = self._abs(play)
        html = self._get(play, referer=self.host + '/')
        real = self._extract_m3u8(html)
        if real:
            return {'parse': 0, 'url': real, 'header': header}
        return {'parse': 1, 'jx': '1', 'url': play, 'header': header}

    def _extract_m3u8(self, html):
        if not html:
            return ''
        # JSON 配置 current.src
        m = re.search(r'"current"\s*:\s*\{[^}]*?"src"\s*:\s*"([^"]+)"', html)
        if m:
            u = m.group(1).replace('\\u0026', '&').replace('\\/', '/')
            if u.startswith('http'):
                return u
        m = re.search(r'"src"\s*:\s*"(https?://[^"]+\.m3u8[^"]*)"', html)
        if m:
            return m.group(1).replace('\\u0026', '&').replace('\\/', '/')
        m = re.search(r'(https?://[^\s"\'<>]+?\.m3u8[^\s"\'<>]*)', html)
        if m:
            return m.group(1).replace('\\u0026', '&')
        m = re.search(r'(https?://[^\s"\'<>]+?\.mp4[^\s"\'<>]*)', html)
        if m:
            return m.group(1)
        return ''

    def isVideoFormat(self, url):
        return bool(url and re.search(r'\.(m3u8|mp4|ts)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None


if __name__ == '__main__':
    sp = Spider()
    sp.init()
    print('home', sp.homeContent(False))
    print('homeVod', len(sp.homeVideoContent().get('list') or []))
    c = sp.categoryContent('duanju', 1, False, {})
    print('cat', len(c.get('list') or []), [x['vod_name'] for x in (c.get('list') or [])[:3]])
    if c.get('list'):
        d = sp.detailContent([c['list'][0]['vod_id']])
        print('detail', d['list'][0]['vod_name'] if d.get('list') else None)
        print('play_url', (d['list'][0].get('vod_play_url') or '')[:120] if d.get('list') else None)
        if d.get('list') and d['list'][0].get('vod_play_url'):
            first = d['list'][0]['vod_play_url'].split('#')[0].split('$')[-1]
            p = sp.playerContent('91短剧', first, [])
            print('player', p.get('parse'), (p.get('url') or '')[:100])
    s = sp.searchContentPage('惩奸侠', False, 1)
    print('search', len(s.get('list') or []), [x['vod_name'] for x in (s.get('list') or [])[:3]])
