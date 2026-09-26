# -*- coding: utf-8 -*-
# 抖音精选 https://www.douyin.com/jingxuan
# 仅直链播放 parse=0，不走解析站
# 热搜/热点视频可无登录；关键词搜索需 Cookie（官方强制登录）
import sys
from urllib.parse import quote, urlencode
sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def init(self, extend=""):
        self.cookie = ''
        if extend:
            try:
                import json
                obj = json.loads(extend) if str(extend).strip().startswith('{') else None
                if isinstance(obj, dict) and obj.get('cookie'):
                    self.cookie = obj['cookie']
                else:
                    self.cookie = str(extend).strip()
            except Exception:
                self.cookie = str(extend).strip()

    def getName(self):
        return '抖音精选'

    def isVideoFormat(self, url):
        return bool(url and ('.mp4' in url or 'mime_type=video' in url or 'bytevod' in url or 'zjcdn.com' in url))

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    rhost = 'https://www.douyin.com'
    snssdk = 'https://aweme.snssdk.com'
    api = 'https://www.douyin.com'

    def _headers(self, mobile=False):
        if mobile:
            ua = 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
        else:
            ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36'
        h = {
            'User-Agent': ua,
            'Referer': self.rhost + '/',
            'Accept': 'application/json, text/plain, */*',
        }
        if self.cookie:
            h['Cookie'] = self.cookie
        return h

    def homeContent(self, filter):
        classes = [
            {'type_name': '热搜视频', 'type_id': 'hotvideo'},
            {'type_name': '热搜榜', 'type_id': 'hotword'},
        ]
        # 热搜词作子分类入口
        try:
            data = self.fetch(
                f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                headers=self._headers()
            ).json()
            words = ((data.get('data') or {}).get('word_list')) or []
            for w in words[:15]:
                sid = w.get('sentence_id')
                word = w.get('word') or ''
                if sid and word:
                    classes.append({
                        'type_name': word[:12],
                        'type_id': f'sid_{sid}'
                    })
        except Exception:
            pass
        return {'class': classes, 'filters': {}}

    def homeVideoContent(self):
        videos = []
        try:
            data = self.fetch(
                f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                headers=self._headers()
            ).json()
            words = ((data.get('data') or {}).get('word_list')) or []
            # 取前几条热搜的视频
            for w in words[:5]:
                sid = w.get('sentence_id')
                if not sid:
                    continue
                for a in self._hot_videos(sid, count=4):
                    item = self._map_aweme(a)
                    if item:
                        videos.append(item)
                if len(videos) >= 20:
                    break
        except Exception as e:
            print('homeVideoContent', e)
        return {'list': videos[:24]}

    def _hot_videos(self, sentence_id, count=10, cursor=0):
        try:
            url = (
                f'{self.snssdk}/aweme/v1/hot/search/video/list/'
                f'?sentence_id={sentence_id}&device_id=0&aid=1128&count={count}&cursor={cursor}'
            )
            data = self.fetch(url, headers=self._headers(mobile=True)).json()
            return data.get('aweme_list') or []
        except Exception as e:
            print('hot_videos', e)
            return []

    def _pick_play_url(self, video):
        """从 video 对象取可直链 mp4，优先无水印/高清"""
        if not video or not isinstance(video, dict):
            return ''
        # download_addr 常为无水印
        for key in ('download_addr', 'play_addr', 'play_addr_h264', 'play_addr_265'):
            addr = video.get(key) or {}
            if isinstance(addr, dict):
                ul = addr.get('url_list') or []
                if ul:
                    return ul[0]
        # bit_rate 多档
        bits = video.get('bit_rate') or []
        if isinstance(bits, list):
            for b in bits:
                pa = (b or {}).get('play_addr') or {}
                ul = pa.get('url_list') or []
                if ul:
                    return ul[0]
        return ''

    def _map_aweme(self, a):
        if not a or not isinstance(a, dict):
            return None
        aweme_id = str(a.get('aweme_id') or a.get('id') or '')
        if not aweme_id:
            return None
        desc = (a.get('desc') or a.get('title') or aweme_id).strip()
        video = a.get('video') or {}
        pic = ''
        for ck in ('cover', 'origin_cover', 'dynamic_cover'):
            c = video.get(ck) or {}
            if isinstance(c, dict) and c.get('url_list'):
                pic = c['url_list'][0]
                break
        author = ((a.get('author') or {}).get('nickname')) or ''
        stats = a.get('statistics') or {}
        digg = stats.get('digg_count') or stats.get('play_count') or ''
        # 把直链缓存在 id 里：aweme_id@@url （避免详情再请求失败）
        play = self._pick_play_url(video)
        vod_id = f'{aweme_id}@@{play}' if play else aweme_id
        return {
            'vod_id': vod_id,
            'vod_name': desc[:80],
            'vod_pic': pic,
            'vod_remarks': f'{author} {digg}'.strip(),
        }

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        videos = []
        tid = str(tid or 'hotvideo')
        try:
            if tid == 'hotword':
                data = self.fetch(
                    f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                    headers=self._headers()
                ).json()
                for w in ((data.get('data') or {}).get('word_list')) or []:
                    word = w.get('word') or ''
                    sid = w.get('sentence_id')
                    if not word or not sid:
                        continue
                    cover = ''
                    wc = w.get('word_cover') or {}
                    if isinstance(wc, dict) and wc.get('url_list'):
                        cover = wc['url_list'][0]
                    videos.append({
                        'vod_id': f'sid_{sid}',
                        'vod_name': word,
                        'vod_pic': cover,
                        'vod_remarks': str(w.get('hot_value') or '热搜'),
                    })
            elif tid.startswith('sid_'):
                sid = tid[4:]
                cursor = (pg - 1) * 10
                for a in self._hot_videos(sid, count=12, cursor=cursor):
                    item = self._map_aweme(a)
                    if item:
                        videos.append(item)
            else:
                # 热搜视频：聚合前几个 sentence 的视频
                data = self.fetch(
                    f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                    headers=self._headers()
                ).json()
                words = ((data.get('data') or {}).get('word_list')) or []
                start = (pg - 1) * 3
                for w in words[start:start + 5]:
                    sid = w.get('sentence_id')
                    if not sid:
                        continue
                    for a in self._hot_videos(sid, count=6):
                        item = self._map_aweme(a)
                        if item:
                            videos.append(item)
        except Exception as e:
            print('categoryContent', e)
        return {
            'list': videos,
            'page': pg,
            'pagecount': 50,
            'limit': 20,
            'total': 9999
        }

    def detailContent(self, ids):
        raw = ids[0] if isinstance(ids, list) else ids
        raw = str(raw)

        # 热搜词分类点进来
        if raw.startswith('sid_'):
            sid = raw[4:]
            name = sid
            try:
                data = self.fetch(
                    f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                    headers=self._headers()
                ).json()
                for w in ((data.get('data') or {}).get('word_list')) or []:
                    if str(w.get('sentence_id')) == str(sid):
                        name = w.get('word') or name
                        break
            except Exception:
                pass
            eps = []
            for a in self._hot_videos(sid, count=20):
                item = self._map_aweme(a)
                if not item:
                    continue
                play = ''
                if '@@' in item['vod_id']:
                    play = item['vod_id'].split('@@', 1)[1]
                if play:
                    title = item['vod_name'][:24] or '视频'
                    eps.append(f'{title}${play}')
            return {'list': [{
                'vod_name': name,
                'type_name': '抖音热搜',
                'vod_content': name,
                'vod_play_from': '抖音直链',
                'vod_play_url': '#'.join(eps) if eps else ''
            }]}

        # 单作品
        aweme_id, play = raw, ''
        if '@@' in raw:
            aweme_id, play = raw.split('@@', 1)

        if not play:
            play = self._fetch_play_by_id(aweme_id)

        vod = {
            'vod_name': aweme_id,
            'type_name': '抖音',
            'vod_play_from': '抖音直链',
            'vod_play_url': f'正片${play}' if play else ''
        }
        # 补标题封面
        try:
            for a in self._hot_videos_by_aweme_fallback(aweme_id):
                if str(a.get('aweme_id')) == str(aweme_id):
                    vod['vod_name'] = (a.get('desc') or aweme_id)[:80]
                    video = a.get('video') or {}
                    c = video.get('cover') or {}
                    if c.get('url_list'):
                        vod['vod_pic'] = c['url_list'][0]
                    if not play:
                        play = self._pick_play_url(video)
                        if play:
                            vod['vod_play_url'] = f'正片${play}'
                    break
        except Exception:
            pass
        return {'list': [vod]}

    def _hot_videos_by_aweme_fallback(self, aweme_id):
        return []

    def _fetch_play_by_id(self, aweme_id):
        """用 ies iteminfo / web detail 补直链"""
        try:
            data = self.fetch(
                f'https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={aweme_id}',
                headers=self._headers(mobile=True)
            ).json()
            items = data.get('item_list') or data.get('items') or []
            if items:
                u = self._pick_play_url(items[0].get('video') or {})
                if u:
                    return u
        except Exception:
            pass
        try:
            data = self.fetch(
                f'{self.api}/aweme/v1/web/aweme/detail/?device_platform=webapp&aid=6383&aweme_id={aweme_id}',
                headers=self._headers()
            ).json()
            detail = data.get('aweme_detail') or {}
            u = self._pick_play_url(detail.get('video') or {})
            if u:
                return u
        except Exception:
            pass
        return ''

    def searchContent(self, key, quick, pg="1"):
        videos = []
        offset = (int(pg or 1) - 1) * 20
        try:
            params = {
                'device_platform': 'webapp',
                'aid': '6383',
                'channel': 'channel_pc_web',
                'search_channel': 'aweme_general',
                'keyword': key,
                'offset': str(offset),
                'count': '20',
                'search_source': 'normal_search',
            }
            data = self.fetch(
                f'{self.api}/aweme/v1/web/general/search/single/?{urlencode(params)}',
                headers=self._headers()
            ).json()
            if data.get('status_code') == 2483:
                # 未登录：在热搜视频里本地过滤关键词
                return {'list': self._local_filter_search(key), 'page': pg}
            for item in data.get('data') or []:
                aweme = item.get('aweme_info') or item.get('aweme') or item
                mapped = self._map_aweme(aweme)
                if mapped:
                    videos.append(mapped)
        except Exception as e:
            print('search', e)
            videos = self._local_filter_search(key)
        if not videos:
            videos = self._local_filter_search(key)
        return {'list': videos, 'page': pg}

    def _local_filter_search(self, key):
        """无登录时：从热搜视频里捞包含关键词的"""
        out = []
        try:
            data = self.fetch(
                f'{self.api}/aweme/v1/web/hot/search/list/?device_platform=webapp&aid=6383&detail_list=1',
                headers=self._headers()
            ).json()
            words = ((data.get('data') or {}).get('word_list')) or []
            for w in words:
                sid = w.get('sentence_id')
                if not sid:
                    continue
                for a in self._hot_videos(sid, count=8):
                    mapped = self._map_aweme(a)
                    if not mapped:
                        continue
                    if key in (mapped.get('vod_name') or '') or key in (w.get('word') or ''):
                        out.append(mapped)
                if len(out) >= 20:
                    break
        except Exception as e:
            print('local search', e)
        return out

    def playerContent(self, flag, id, vipFlags):
        """只直链，不用解析站"""
        url = str(id or '').strip()
        if '@@' in url:
            url = url.split('@@', 1)[-1]
        # 若仍是纯数字 id，再取一次直链
        if url.isdigit() and len(url) >= 15:
            url = self._fetch_play_by_id(url) or url
        header = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
            'Referer': self.rhost + '/',
        }
        if url and url.startswith('http') and ('mp4' in url or 'zjcdn' in url or 'bytevod' in url or 'douyinvod' in url or 'mime_type=video' in url):
            return {'parse': 0, 'url': url, 'header': header}
        # 无直链不返回页面、不走 jx
        return {'parse': 0, 'url': url if url.startswith('http') else '', 'header': header}

    def localProxy(self, param):
        pass
