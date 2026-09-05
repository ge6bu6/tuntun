# -*- coding: utf-8 -*-
# 大马猴影视 - 整合 bubutv 线路解析逻辑，实现直接播放（无需外置解析）

import sys
sys.path.append('..')

import json
import re
import time
import random
import hashlib
from urllib.parse import urlencode, quote
from html.parser import HTMLParser
from base.spider import Spider


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._text = []

    def handle_data(self, data):
        self._text.append(data)

    def get_text(self):
        return ''.join(self._text)


class Spider(Spider):
    def __init__(self):
        self.host = 'https://dmhyy.com'
        self.classes = [
            {'type_id': '23', 'type_name': '电影'},
            {'type_id': '22', 'type_name': '剧集'},
            {'type_id': '24', 'type_name': '动漫'},
            {'type_id': '25', 'type_name': '综艺'},
        ]
        self.web_sign = ''
        self.x_client = 'YOUR_PUBLIC_CLIENT_ID'  # 请替换为真实值
        self._app_device_id = ''

    def init(self, extend=''):
        try:
            if extend:
                if isinstance(extend, dict):
                    ext = extend
                else:
                    text = str(extend).strip()
                    ext = json.loads(text) if text.startswith('{') else {'site': text}
                site = ext.get('site') or ext.get('host') or ''
                if site:
                    self.host = str(site).split(',')[0].strip().rstrip('/')
                self.web_sign = ext.get('web-sign') or ext.get('web_sign') or self.web_sign
                self.x_client = ext.get('x-client') or ext.get('x_client') or self.x_client
        except Exception:
            pass
        return None

    def _ensure_ready(self):
        if not getattr(self, 'host', ''):
            self.host = 'https://dmhyy.com'
        self.host = self.host.rstrip('/')

    def getName(self):
        return '大马猴影视'

    def destroy(self):
        pass

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv|avi)(\?|#|$|\s)', str(url or ''), re.I))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def _headers(self, referer=''):
        self._ensure_ready()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': referer or (self.host + '/'),
            'x-client': self.x_client,
            'x-platform': 'web',
            'x-requested-with': 'XMLHttpRequest',
        }
        if getattr(self, 'web_sign', ''):
            headers['web-sign'] = self.web_sign
        return headers

    def _app_headers(self):
        """生成 app 接口需要的签名头（与 bubutv 一致）"""
        timestamp = str(int(time.time()))
        nonce = ''.join([str(random.randint(0, 9)) for _ in range(3)])
        pkg = 'com.sunshine.tv'
        ver = '4'
        finger = 'SF-C3B2B41F6EFFFF9869176CF68F6790E8F07506FC88632C94B4F5F0430D5498CA'
        sign_str = f"finger={finger}&id={pkg}&nonce={nonce}&sk=SK-thanks&time={timestamp}&v={ver}"
        sign = hashlib.sha256(sign_str.encode()).hexdigest().upper()

        if not self._app_device_id or len(self._app_device_id) != 16:
            self._app_device_id = ''.join([random.choice('0123456789abcdef') for _ in range(16)])

        return {
            'User-Agent': 'okhttp/4.12.0',
            'Accept': 'application/json',
            'x-aid': pkg,
            'x-ave': ver,
            'x-time': timestamp,
            'x-nonc': nonce,
            'x-sign': sign,
            'x-device-id': self._app_device_id,
            'x-device-brand': 'vivo',
            'x-device-model': 'V2309A',
            'x-update-id': '0245861b-2ebf-5524-389d-f983830651ec'
        }

    def _api_get(self, path, params=None, referer=''):
        self._ensure_ready()
        params = params or {}
        qs = urlencode(params, doseq=True)
        url = self.host + path + (('?' + qs) if qs else '')
        try:
            r = self.fetch(url, headers=self._headers(referer), timeout=12)
            text = getattr(r, 'text', '') or getattr(r, 'content', b'')
            if isinstance(text, bytes):
                text = text.decode('utf-8', errors='ignore')
            if not text:
                return {}
            return json.loads(text)
        except Exception as e:
            print('大马猴接口请求失败:', path, params, e)
            return {}

    def _clean_text(self, s):
        s = str(s or '')
        s = re.sub(r'<[^>]+>', ' ', s)
        s = s.replace('&nbsp;', ' ')
        return re.sub(r'\s+', ' ', s).strip()

    def _html2text(self, html):
        try:
            p = _HTMLTextExtractor()
            p.feed(str(html or ''))
            return self._clean_text(p.get_text())
        except Exception:
            return self._clean_text(html)

    def _as_list(self, data):
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for k in ('data', 'list', 'items', 'records', 'rows', 'vod_list'):
                v = data.get(k)
                if isinstance(v, list):
                    return v
                if isinstance(v, dict):
                    vv = self._as_list(v)
                    if vv:
                        return vv
        return []

    def _vod_item(self, item):
        if not isinstance(item, dict):
            return None
        vid = item.get('vod_id') or item.get('id') or item.get('vodId')
        name = item.get('vod_name') or item.get('name') or item.get('title')
        if not vid or not name:
            return None
        area = item.get('vod_area', '')
        cls = item.get('vod_class', '')
        if isinstance(area, list):
            area = ','.join([str(x) for x in area if x])
        if isinstance(cls, list):
            cls = ','.join([str(x) for x in cls if x])
        return {
            'vod_id': str(vid),
            'vod_name': self._clean_text(name),
            'vod_pic': str(item.get('vod_pic') or item.get('pic') or item.get('cover') or ''),
            'vod_remarks': str(item.get('vod_remarks') or item.get('remarks') or item.get('vod_douban_score') or item.get('vod_year') or ''),
            'vod_year': str(item.get('vod_year') or ''),
            'type_name': self._clean_text(item.get('type_name') or cls or ''),
            'vod_area': self._clean_text(area),
        }

    def _vod_list(self, data):
        arr = self._as_list(data)
        out = []
        seen = set()
        for item in arr:
            v = self._vod_item(item)
            if not v:
                continue
            if v['vod_id'] in seen:
                continue
            seen.add(v['vod_id'])
            out.append(v)
        return out

    def _category_match(self, item, real_tid):
        if not isinstance(item, dict):
            return False
        real_tid = str(real_tid)
        item_tid = str(item.get('type_id') or item.get('typeId') or item.get('tid') or '')
        if item_tid == real_tid:
            return True
        name = str(item.get('type_name') or '')
        class_value = item.get('vod_class') or []
        if isinstance(class_value, list):
            cls = ','.join([str(x) for x in class_value if x])
        else:
            cls = str(class_value or '')
        text = name + ',' + cls
        if real_tid == '23':
            return ('电影' in text or '动作片' in text or '剧情片' in text or '喜剧片' in text) and '电视剧' not in text
        if real_tid == '22':
            return any(k in text for k in ('剧集', '电视剧', '国产剧', '连续剧', '韩剧', '陆剧', '欧美剧', '日剧'))
        if real_tid == '24':
            return '动漫' in text or '动画' in text or '国产动漫' in text or '日韩动漫' in text
        if real_tid == '25':
            return '综艺' in text or '真人秀' in text
        return True

    def _filter_items_by_category(self, data, real_tid):
        arr = self._as_list(data)
        return [x for x in arr if self._category_match(x, real_tid)]

    def homeContent(self, filter):
        return {'class': self.classes}

    def homeVideoContent(self):
        j = self._api_get('/api.php/web/filter/vod', {
            'type_id': '23',
            'page': '1',
            'sort': 'hits'
        }, self.host + '/type/23')
        return {'list': self._vod_list(j)}

    def categoryContent(self, tid, pg, filter, extend):
        self._ensure_ready()
        page = str(pg or '1')
        sort = 'hits'
        if isinstance(extend, dict):
            sort = extend.get('sort') or extend.get('by') or sort

        tid_map = {'1': '23', '2': '22', '3': '24', '4': '25'}
        real_tid = tid_map.get(str(tid), str(tid))
        j = self._api_get('/api.php/web/filter/vod', {
            'type_id': real_tid,
            'page': page,
            'sort': sort
        }, self.host + '/type/' + real_tid)

        filtered_items = self._filter_items_by_category(j, real_tid)

        try:
            cur_page = int(page)
        except Exception:
            cur_page = 1
        if len(filtered_items) < 8:
            seen_ids = set(str(x.get('vod_id') or x.get('id') or '') for x in filtered_items if isinstance(x, dict))
            for extra_page in range(cur_page + 1, cur_page + 3):
                jj = self._api_get('/api.php/web/filter/vod', {
                    'type_id': real_tid,
                    'page': str(extra_page),
                    'sort': sort
                }, self.host + '/type/' + real_tid)
                for item in self._filter_items_by_category(jj, real_tid):
                    vid = str(item.get('vod_id') or item.get('id') or '')
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        filtered_items.append(item)
                if len(filtered_items) >= 24:
                    break

        videos = self._vod_list(filtered_items)
        pagecount = 1
        total = len(videos)
        limit = 24
        if isinstance(j, dict):
            pagecount = int(j.get('pageCount') or j.get('pagecount') or (cur_page + 1 if videos else cur_page))
            total = int(j.get('total') or total)
            limit = int(j.get('limit') or limit)

        return {
            'list': videos,
            'page': cur_page,
            'pagecount': pagecount,
            'limit': limit,
            'total': total
        }

    def searchContent(self, key, quick, pg='1'):
        self._ensure_ready()
        wd = str(key or '').strip()
        page = str(pg or '1')
        if not wd:
            return {'list': [], 'page': int(page)}

        paths = [
            ('/api.php/web/search/vod', {'wd': wd, 'page': page}),
            ('/api.php/web/vod/search', {'wd': wd, 'page': page}),
            ('/api.php/web/search', {'wd': wd, 'page': page}),
            ('/api.php/web/filter/vod', {'keyword': wd, 'page': page, 'sort': 'hits'}),
        ]
        for path, params in paths:
            j = self._api_get(path, params, self.host + '/search?keyword=' + quote(wd))
            videos = self._vod_list(j)
            if videos:
                return {'list': videos, 'page': int(page)}
        return {'list': [], 'page': int(page)}

    def _first_detail(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        j = self._api_get('/api.php/web/vod/get_detail', {'vod_id': vid}, self.host + '/play/' + vid)
        arr = self._as_list(j)
        return (arr[0] if arr else {}), j

    def _aggregate_sources(self, vid):
        paths = [
            '/api.php/web/internal/search_aggregate',
            '/api.php/web/search_aggregate',
        ]
        for path in paths:
            j = self._api_get(path, {'vod_id': str(vid)}, self.host + '/play/' + str(vid))
            arr = self._as_list(j)
            if arr:
                return arr
        return []

    # ---------- 线路构建（与 JS 版一致） ----------
    def detailContent(self, ids):
        self._ensure_ready()
        if not ids:
            return {'list': []}
        vid = str(ids[0])
        detail, raw = self._first_detail([vid])

        if not detail:
            agg = self._aggregate_sources(vid)
            if agg:
                detail = agg[0]
            else:
                return {'list': []}

        vodplayer = raw.get('vodplayer', []) if isinstance(raw, dict) else []

        shows = []
        play_urls = []

        # 1. 聚合接口的直链（优先，need_parse=0）
        agg_sources = self._aggregate_sources(vid)
        if agg_sources:
            agg_sources.sort(key=lambda s: (
                0 if re.search(r'\.(m3u8|mp4|flv)(\?|#|$|\s)', str(s.get('vod_play_url', '')), re.I) else 1,
                s.get('site_name', '')
            ))
            for src in agg_sources[:4]:
                play_url = str(src.get('vod_play_url', '')).strip()
                if not play_url:
                    continue
                need_parse = 0  # 聚合直链通常不需要解析
                site_name = src.get('site_name') or src.get('external_display_name') or '聚合线路'
                encoded = f"1${site_name}@{need_parse}@{play_url}"
                shows.append(site_name)
                play_urls.append(encoded)

        # 2. 详情自带的线路
        pf = str(detail.get('vod_play_from', '') or '')
        pu = str(detail.get('vod_play_url', '') or '')
        if pf and pu:
            froms = pf.split('$$$')
            urls = pu.split('$$$')
            for show_code, urls_str in zip(froms, urls):
                need_parse = 1
                is_show = 0
                show_name = show_code

                for player in vodplayer:
                    if player.get('from') == show_code:
                        is_show = 1
                        need_parse = int(player.get('decode_status', 1))
                        if player.get('show', '').lower() != show_code.lower():
                            show_name = f"{player['show']}\u2005({show_code})"
                        break

                if not is_show:
                    is_show = 1
                    sample_url = urls_str.split('#')[0].split('$')[-1] if urls_str else ''
                    if sample_url.startswith('http') and self.isVideoFormat(sample_url):
                        need_parse = 0

                if is_show:
                    episodes = []
                    for url_item in urls_str.split('#'):
                        if '$' in url_item:
                            ep, raw_url = url_item.split('$', 1)
                            episodes.append(f"{ep}${show_code}@{need_parse}@{raw_url}")
                    if episodes:
                        play_urls.append('#'.join(episodes))
                        shows.append(show_name)

        # 3. 如果没有线路，尝试用聚合接口的未处理项
        if not shows and agg_sources:
            for src in agg_sources[:2]:
                play_url = str(src.get('vod_play_url', '')).strip()
                if play_url:
                    need_parse = 0
                    name = src.get('site_name', '线路')
                    play_urls.append(f"1${name}@{need_parse}@{play_url}")
                    shows.append(name)

        area = detail.get('vod_area', '')
        cls = detail.get('vod_class', '')
        if isinstance(area, list):
            area = ','.join([str(x) for x in area if x])
        if isinstance(cls, list):
            cls = ','.join([str(x) for x in cls if x])

        vod = {
            'vod_id': vid,
            'vod_name': self._clean_text(detail.get('vod_name') or ''),
            'vod_pic': str(detail.get('vod_pic') or ''),
            'vod_remarks': str(detail.get('vod_remarks') or ''),
            'type_name': self._clean_text(detail.get('type_name') or cls or ''),
            'vod_year': str(detail.get('vod_year') or ''),
            'vod_area': self._clean_text(area),
            'vod_actor': self._clean_text(detail.get('vod_actor') or ''),
            'vod_director': self._clean_text(detail.get('vod_director') or ''),
            'vod_content': self._html2text(detail.get('vod_content') or ''),
            'vod_play_from': '$$$'.join(shows),
            'vod_play_url': '$$$'.join(play_urls),
        }
        return {'list': [vod]}

    # ---------- 播放解析（使用 app 解码接口，实现直接播放） ----------
    def playerContent(self, flag, id, vipFlags):
        self._ensure_ready()
        url = str(id or '').strip()
        if not url:
            return {'parse': 0, 'url': ''}

        # 处理 @ 标记格式（集数$线路@need_parse@真实地址）
        if '@' in url and not url.startswith('http'):
            try:
                parts = url.split('@', 2)
                if len(parts) == 3:
                    play_from, need_parse, raw_url = parts
                    if need_parse == '0':
                        if self.isVideoFormat(raw_url) or raw_url.startswith('http'):
                            return {
                                'parse': 0, 'jx': 0,
                                'url': raw_url,
                                'header': self._app_headers()
                            }
                        else:
                            return {'parse': 1, 'jx': 1, 'url': raw_url}
                    # need_parse == '1'，尝试解码
                    decoded = self._try_decode(raw_url, play_from)
                    if decoded:
                        return {
                            'parse': 0, 'jx': 0,
                            'url': decoded,
                            'header': self._app_headers()
                        }
                    # 解码失败，若原地址可用则直接播，否则交壳解析
                    if self.isVideoFormat(raw_url) or raw_url.startswith('http'):
                        return {'parse': 0, 'jx': 0, 'url': raw_url,
                                'header': self._app_headers()}
                    else:
                        return {'parse': 1, 'jx': 1, 'url': raw_url}
            except Exception:
                pass

        # 旧格式直链直接播放
        if url.startswith('http') and self.isVideoFormat(url):
            return {
                'parse': 0, 'jx': 0,
                'url': url,
                'header': self._app_headers()
            }

        # 尝试旧版解码接口（web 方式）
        decoded = self._try_decode(url, None)
        if decoded:
            return {
                'parse': 0, 'jx': 0,
                'url': decoded,
                'header': self._app_headers()
            }

        # 腾讯/优酷等大站交给壳
        if re.search(r'(v\.qq\.com|youku\.com|iqiyi\.com|mgtv\.com|bilibili\.com)', url, re.I):
            return {'parse': 1, 'jx': 1, 'url': url}

        return {'parse': 1, 'jx': 1, 'url': url}

    def _try_decode(self, raw_url, play_from=None):
        """优先使用 app 解码接口，失败再尝试 web 接口"""
        # ---- 1. app 解码接口（带签名）----
        if play_from:
            try:
                app_headers = self._app_headers()
                app_url = f"{self.host}/api.php/app/decode/url/?url={quote(raw_url)}&vodFrom={play_from}"
                r = self.fetch(app_url, headers=app_headers, timeout=10)
                data = json.loads(r.text) if r.text else {}
                link = data.get('data', '')
                if isinstance(link, str) and link.startswith('http'):
                    return link
            except Exception as e:
                print(f'App解码失败: {e}')

        # ---- 2. web 解码接口（原有多参数尝试）----
        decode_tries = [
            {'url': raw_url},
            {'play_url': raw_url},
            {'vod_url': raw_url},
        ]
        for params in decode_tries:
            j = self._api_get('/api.php/web/decode/url', params, self.host + '/play')
            link = self._extract_url(j)
            if link:
                return link
        return None

    def _extract_url(self, resp_data):
        """从解码响应中提取直链"""
        if isinstance(resp_data, str):
            return resp_data if resp_data.startswith('http') else None
        if isinstance(resp_data, dict):
            data = resp_data.get('data')
            if isinstance(data, str):
                return data if data.startswith('http') else None
            if isinstance(data, dict):
                url = data.get('url') or data.get('play_url') or data.get('playUrl') or ''
                return url if url.startswith('http') else None
            url = resp_data.get('url') or resp_data.get('play_url') or ''
            return url if url.startswith('http') else None
        return None