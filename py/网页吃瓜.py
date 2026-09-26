# coding=utf-8
"""
网页吃瓜（土豆 / 5866视频，videoh5.86027a.xyz）· TVBox Python 插件 · 纯标准库
=====================================================================================
接口： homeContent / categoryContent / detailContent / searchContent / playerContent
挂法： {"name":"🔞网页吃瓜┃原生","type":3,"api":"py_网页吃瓜.py"}   （extend 可传 {"host":"换域名"}）

【站情 · 2026-09-26 实地逆向】
  推广链路：qzmuk48k02.qvfbtz.cn/?channelCode=AF077（App 下载落地页）
    → 安卓包 com.po4EI1290t6wCGTi.* 是 VM 壳（classes.dex 只有 3 个类，真实 dex 以 8.0 熵
      塞在 10.2MB~11.9MB 段，libpgctzaqx.so 运行时解密）—— 静态扒不动
    → 改切 iOS ipa（未加固）：字符串表直接躺着 /api/... 路径与 api.cjjadu.com、videoh5.86027a.xyz
    → H5 站是 uni-app 打包的 Vue（标题「小视频」），axios baseURL = 同源 + /api
    → 全部接口在 https://<h5host>/api/... 上裸奔，游客注册即出数据（无需手机号、无需付费）

【接口（全部实测）】
  POST /api/user/dunGustRegister {"machine_code":"<32位hex>"}  -> data.token
  POST /api/user/getVideoUrl     {}                            -> data.video_url（播放前缀域名）
  GET  /api/video/category                                     -> [{id,name}] 20 个分类
  POST /api/video/v2/list        {"page":1,"page_size":20,"category_id":X}
  POST /api/video/v2/list        {"page":1,"page_size":20,"keyword":"X"}      搜索
  POST /api/video/v2/home        {"page":1,"page_size":N}      首页分栏 [{id,n,ch:[...]}]
  POST /api/v2/detail            {"id":X}                      详情 pu=play_url / c=cover

  请求头：token / cid=1 / timestamp(秒) / Accept-Language: tw / Referer: <h5host>/

【字段缩写表（H5 里那张映射，别按长名去取，取不到）】
  c=cover  tm=time(秒)  t=title  n=name  m=money  iv=is_vip  ib=is_buy  a=actress
  tl=tag_list  ch=children  ob=orderby  pu=play_url  ic=is_collect  cid=category_id
  rwn=remaining_watch_num  fwt=free_watch_time  vl=vip_level  vwt=video_watch_type

【播放】
  最终地址 = video_url + play_url
  例： https://xas92c.xn--tlqu4rt97b3jfmwiqta.com/20251001/oTb2PUi3/index.m3u8
  视频 CDN 的出口只对国内放行（沙箱/机房出口连不上），带 Referer 回 H5 站。
  ⚠️ 播放链路未在真机验证（本地出口到该 CDN 不通），列表/详情/字段全部实测。
"""
import gzip
import io
import json
import random
import threading
import time
import urllib.parse
import urllib.request

try:
    from base.spider import Spider as _Spider
except Exception:
    class _Spider(object):
        pass

DEFAULT_HOST = 'https://videoh5.86027a.xyz'
IMG_HOST = 'https://image.86027a.xyz'
DEFAULT_UA = ('Mozilla/5.0 (Linux; Android 12) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36')
SITE_NAME = '网页吃瓜'
PAGE_LIMIT = 20
TOKEN_TTL = 6 * 3600          # 游客 token 复用 6 小时
VHOST_TTL = 3600              # 播放前缀域名缓存 1 小时


class Spider(_Spider):

    def __init__(self):
        self.host = DEFAULT_HOST
        self.label = SITE_NAME
        self._token = ''
        self._token_ts = 0.0
        self._vhost = ''
        self._vhost_ts = 0.0
        self._pu = {}            # vod_id -> play_url 路径
        # ★ 必须用可重入锁：_video_host 持锁后会再调 _post -> _ensure_token 拿同一把锁，
        #   用普通 Lock 就是自锁（实测 detail 直接挂死 120s+ 不动）
        self._lock = threading.RLock()

    # ------------------------------------------------------------ 基建

    def init(self, extend=''):
        try:
            e = (extend or '').strip() if isinstance(extend, str) else ''
            if e.startswith('{'):
                o = json.loads(e)
                h = str(o.get('host') or o.get('site') or '').strip()
                if len(h) > 6:
                    if not h.startswith('http'):
                        h = 'https://' + h
                    self.host = h.rstrip('/')
                n = str(o.get('name') or '').strip()
                if n:
                    self.label = n
            elif e.startswith('http'):
                self.host = e.rstrip('/')
        except Exception:
            pass
        return self

    def getName(self):
        return self.label

    def isVideoFormat(self, url):
        u = str(url or '').lower()
        return '.m3u8' in u or '.mp4' in u

    def manualVideoCheck(self):
        return False

    def _log(self, msg):
        try:
            print('[' + SITE_NAME + '] ' + str(msg)[:200])
        except Exception:
            pass

    @staticmethod
    def _machine_code():
        return ''.join(random.choice('0123456789abcdef') for _ in range(32))

    def _open(self, url, data=None, headers=None, timeout=15):
        req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data else 'GET')
        try:
            req.add_header('Accept-Encoding', 'gzip')
        except Exception:
            pass
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            enc = (r.headers.get('Content-Encoding') or '').lower()
        if 'gzip' in enc:
            try:
                raw = gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
            except Exception:
                pass
        return raw.decode('utf-8', 'replace')

    def _base_headers(self, with_token=True):
        h = {
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'cid': '1',
            'timestamp': str(int(time.time())),
            'Accept-Language': 'tw',
            'User-Agent': DEFAULT_UA,
            'Origin': self.host,
            'Referer': self.host + '/',
        }
        if with_token and self._token:
            h['token'] = self._token
        return h

    def _ensure_token(self):
        with self._lock:
            if self._token and time.time() - self._token_ts < TOKEN_TTL:
                return self._token
            try:
                body = json.dumps({'machine_code': self._machine_code()}).encode('utf-8')
                txt = self._open(self.host + '/api/user/dunGustRegister', body,
                                 self._base_headers(with_token=False))
                d = (json.loads(txt) or {}).get('data') or {}
                tk = str(d.get('token') or '') if isinstance(d, dict) else ''
                if len(tk) > 8:
                    self._token = tk
                    self._token_ts = time.time()
                else:
                    self._log('register miss: %s' % txt[:120])
            except Exception as ex:
                self._log('register err: %s' % str(ex)[:120])
            return self._token

    def _post(self, path, obj=None):
        if not self._ensure_token():
            return {}
        try:
            body = json.dumps(obj or {}).encode('utf-8')
            txt = self._open(self.host + '/api/' + path, body, self._base_headers())
            return json.loads(txt) or {}
        except Exception as ex:
            self._log('post %s: %s' % (path, str(ex)[:120]))
            return {}

    def _get(self, path):
        if not self._ensure_token():
            return {}
        try:
            txt = self._open(self.host + '/api/' + path, None, self._base_headers())
            return json.loads(txt) or {}
        except Exception as ex:
            self._log('get %s: %s' % (path, str(ex)[:120]))
            return {}

    def _video_host(self):
        with self._lock:
            if self._vhost and time.time() - self._vhost_ts < VHOST_TTL:
                return self._vhost
            j = self._post('user/getVideoUrl', {})
            v = str((j.get('data') or {}).get('video_url') or '').strip()
            if len(v) > 8:
                self._vhost = v.rstrip('/')
                self._vhost_ts = time.time()
            return self._vhost

    # ------------------------------------------------------------ 解析

    @staticmethod
    def _rows(j, key=None):
        """data 可能是数组，也可能是 {l:[...]} / {list:[...]} 包一层"""
        d = (j or {}).get('data')
        if isinstance(d, list):
            return d
        if isinstance(d, dict):
            if key and isinstance(d.get(key), list):
                return d[key]
            for k in ('l', 'list', 'ch'):
                if isinstance(d.get(k), list):
                    return d[k]
        return []

    @staticmethod
    def _img(c):
        c = str(c or '').strip()
        if not c:
            return ''
        if c.startswith('http'):
            return c
        return IMG_HOST + (c if c.startswith('/') else '/' + c)

    @staticmethod
    def _dur(sec):
        try:
            sec = int(sec)
        except Exception:
            return ''
        if sec <= 0:
            return ''
        return '%02d:%02d' % (sec // 60, sec % 60)

    def _card(self, it):
        if not isinstance(it, dict):
            return None
        vid = str(it.get('id') or '').strip()
        if not vid:
            return None
        rem = []
        d = self._dur(it.get('tm'))
        if d:
            rem.append(d)
        a = str(it.get('a') or it.get('actress') or '').strip()
        if a:
            rem.append(a)
        tl = str(it.get('tl') or it.get('tag_list') or '').strip()
        if tl:
            rem.append(tl)
        if int(it.get('iv') or 0) == 1:
            rem.append('VIP')
        elif int(it.get('ib') or 0) == 1:
            rem.append('付费')
        return {
            'vod_id': vid,
            'vod_name': str(it.get('t') or it.get('title') or '').strip(),
            'vod_pic': self._img(it.get('c') or it.get('cover')),
            'vod_remarks': ' · '.join(rem),
        }

    def _cards(self, arr):
        out = []
        for it in (arr or []):
            c = self._card(it)
            if c and c['vod_name']:
                out.append(c)
        return out

    @staticmethod
    def _player(url):
        return {
            'parse': 0,
            'jx': 0,
            'url': url,
            'header': json.dumps({'User-Agent': DEFAULT_UA, 'Referer': DEFAULT_HOST + '/'}),
            'format': 'application/x-mpegURL',
            'contentType': 'application/x-mpegURL',
        }

    # ------------------------------------------------------------ 接口

    def homeContent(self, filter=False):
        cls = []
        j = self._post('video/category', {})   # ★ 实测是 POST，GET 回 405
        for c in self._rows(j):
            if not isinstance(c, dict):
                continue
            cid = str(c.get('id') or '').strip()
            name = str(c.get('name') or '').strip()
            if cid and name:
                cls.append({'type_name': name, 'type_id': cid})

        lst = []
        try:
            j2 = self._post('video/v2/home', {'page': 1, 'page_size': 6})
            for blk in self._rows(j2):
                if isinstance(blk, dict):
                    lst.extend(self._cards(blk.get('ch')))
        except Exception as ex:
            self._log('home: %s' % str(ex)[:100])

        if not lst and cls:
            try:
                j3 = self._post('video/v2/list', {'page': 1, 'page_size': 30,
                                                  'category_id': cls[0]['type_id']})
                lst = self._cards(self._rows(j3, 'l'))
            except Exception:
                pass
        return {'class': cls, 'list': lst[:60]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        tid = str(tid or '').strip()
        body = {'page': page, 'page_size': PAGE_LIMIT}
        try:
            body['category_id'] = int(tid)
        except Exception:
            body['category_id'] = tid
        j = self._post('video/v2/list', body)
        rows = self._rows(j, 'l')
        lst = self._cards(rows)
        return {
            'list': lst,
            'page': page,
            'pagecount': page if len(rows) < PAGE_LIMIT else 9999,
            'limit': PAGE_LIMIT,
            'total': 999999,
        }

    def detailContent(self, ids):
        vid = ids[0] if isinstance(ids, (list, tuple)) and ids else ids
        vid = str(vid or '').strip()
        if not vid:
            return {'list': []}
        body = {'id': int(vid) if vid.isdigit() else vid}
        j = self._post('video/v2/detail', body)
        d = (j or {}).get('data') or {}
        if not isinstance(d, dict):
            d = {}
        name = str(d.get('t') or d.get('title') or vid).strip()
        pic = self._img(d.get('c') or d.get('cover'))
        pu = str(d.get('pu') or d.get('play_url') or '').strip()
        tag = str(d.get('tl') or d.get('tag_list') or '').strip()
        dur = self._dur(d.get('tm'))
        if pu:
            self._pu[vid] = pu

        host = self._video_host() if pu else ''
        url = (host + pu) if (host and pu) else ''

        v = {
            'vod_id': vid,
            'vod_name': name,
            'vod_pic': pic,
            'type_name': tag,
            'vod_remarks': dur or ('VIP' if int(d.get('iv') or 0) == 1 else ''),
            'vod_content': '【站源】网页吃瓜（土豆/5866视频）· 游客直取，免登入\n【分类】'
                           + (tag or '-') + '\n【说明】播放地址由站点按出口下发，带 Referer 取流',
            'vod_play_from': SITE_NAME,
            'vod_play_url': (name.replace('$', ' ') + '$' + url) if url
                            else ('暂无可播地址$'),
        }
        return {'list': [v]}

    def searchContent(self, key, quick, pg='1'):
        try:
            page = max(1, int(pg))
        except Exception:
            page = 1
        kw = str(key or '').strip()
        if not kw:
            return {'list': [], 'page': 1, 'pagecount': 1, 'limit': PAGE_LIMIT, 'total': 0}
        j = self._post('video/v2/list', {'page': page, 'page_size': PAGE_LIMIT, 'keyword': kw})
        rows = self._rows(j, 'l')
        return {
            'list': self._cards(rows),
            'page': page,
            'pagecount': page if len(rows) < PAGE_LIMIT else 9999,
            'limit': PAGE_LIMIT,
            'total': 999999,
        }

    def playerContent(self, flag, id, vipFlags):
        u = str(id or '').strip()
        if u.startswith('http'):
            return self._player(u)
        vid = u
        pu = self._pu.get(vid)
        if not pu:
            body = {'id': int(vid) if vid.isdigit() else vid}
            d = (self._post('video/v2/detail', body) or {}).get('data') or {}
            if isinstance(d, dict):
                pu = str(d.get('pu') or d.get('play_url') or '').strip()
                if pu:
                    self._pu[vid] = pu
        if pu:
            host = self._video_host()
            if host:
                return self._player(host + pu)
        return self._player(self.host + '/')
