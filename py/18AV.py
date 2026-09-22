# -*- coding: utf-8 -*-
import sys
import re
import json
import base64
import threading
import requests
import urllib3
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import unquote, quote

urllib3.disable_warnings()
sys.path.append('..')
from base.spider import Spider

# ===== 纯 Python AES-128 工具 =====
_sbox = bytes([
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16])

_inv_sbox = bytes([
    0x52,0x09,0x6a,0xd5,0x30,0x36,0xa5,0x38,0xbf,0x40,0xa3,0x9e,0x81,0xf3,0xd7,0xfb,
    0x7c,0xe3,0x39,0x82,0x9b,0x2f,0xff,0x87,0x34,0x8e,0x43,0x44,0xc4,0xde,0xe9,0xcb,
    0x54,0x7b,0x94,0x32,0xa6,0xc2,0x23,0x3d,0xee,0x4c,0x95,0x0b,0x42,0xfa,0xc3,0x4e,
    0x08,0x2e,0xa1,0x66,0x28,0xd9,0x24,0xb2,0x76,0x5b,0xa2,0x49,0x6d,0x8b,0xd1,0x25,
    0x72,0xf8,0xf6,0x64,0x86,0x68,0x98,0x16,0xd4,0xa4,0x5c,0xcc,0x5d,0x65,0xb6,0x92,
    0x6c,0x70,0x48,0x50,0xfd,0xed,0xb9,0xda,0x5e,0x15,0x46,0x57,0xa7,0x8d,0x9d,0x84,
    0x90,0xd8,0xab,0x00,0x8c,0xbc,0xd3,0x0a,0xf7,0xe4,0x58,0x05,0xb8,0xb3,0x45,0x06,
    0xd0,0x2c,0x1e,0x8f,0xca,0x3f,0x0f,0x02,0xc1,0xaf,0xbd,0x03,0x01,0x13,0x8a,0x6b,
    0x3a,0x91,0x11,0x41,0x4f,0x67,0xdc,0xea,0x97,0xf2,0xcf,0xce,0xf0,0xb4,0xe6,0x73,
    0x96,0xac,0x74,0x22,0xe7,0xad,0x35,0x85,0xe2,0xf9,0x37,0xe8,0x1c,0x75,0xdf,0x6e,
    0x47,0xf1,0x1a,0x71,0x1d,0x29,0xc5,0x89,0x6f,0xb7,0x62,0x0e,0xaa,0x18,0xbe,0x1b,
    0xfc,0x56,0x3e,0x4b,0xc6,0xd2,0x79,0x20,0x9a,0xdb,0xc0,0xfe,0x78,0xcd,0x5a,0xf4,
    0x1f,0xdd,0xa8,0x33,0x88,0x07,0xc7,0x31,0xb1,0x12,0x10,0x59,0x27,0x80,0xec,0x5f,
    0x60,0x51,0x7f,0xa9,0x19,0xb5,0x4a,0x0d,0x2d,0xe5,0x7a,0x9f,0x93,0xc9,0x9c,0xef,
    0xa0,0xe0,0x3b,0x4d,0xae,0x2a,0xf5,0xb0,0xc8,0xeb,0xbb,0x3c,0x83,0x53,0x99,0x61,
    0x17,0x2b,0x04,0x7e,0xba,0x77,0xd6,0x26,0xe1,0x69,0x14,0x63,0x55,0x21,0x0c,0x7d])

_rcon = [0x01,0x02,0x04,0x08,0x10,0x20,0x40,0x80,0x1b,0x36]

def _xtime(a):
    return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff

def _gf_mul(a, b):
    r = 0
    for _ in range(8):
        if b & 1: r ^= a
        a = _xtime(a)
        b >>= 1
    return r

_mul_e = bytes(_gf_mul(0x0e, i) for i in range(256))
_mul_b = bytes(_gf_mul(0x0b, i) for i in range(256))
_mul_d = bytes(_gf_mul(0x0d, i) for i in range(256))
_mul_9 = bytes(_gf_mul(0x09, i) for i in range(256))

_key_schedules = {}

def _key_schedule(key):
    k = bytes(key)
    if k in _key_schedules: return _key_schedules[k]
    w = []
    for i in range(4):
        w.append([key[4*i], key[4*i+1], key[4*i+2], key[4*i+3]])
    for i in range(4, 44):
        temp = w[i-1][:]
        if i % 4 == 0:
            temp = temp[1:] + temp[:1]
            temp = [_sbox[b] for b in temp]
            temp[0] ^= _rcon[i//4 - 1]
        w.append([w[i-4][j] ^ temp[j] for j in range(4)])
    _key_schedules[k] = w
    return w

def _dec_block(block, w):
    s0,s1,s2,s3,s4,s5,s6,s7,s8,s9,s10,s11,s12,s13,s14,s15 = block
    s0 ^= w[40][0]; s1 ^= w[40][1]; s2 ^= w[40][2]; s3 ^= w[40][3]
    s4 ^= w[41][0]; s5 ^= w[41][1]; s6 ^= w[41][2]; s7 ^= w[41][3]
    s8 ^= w[42][0]; s9 ^= w[42][1]; s10^= w[42][2]; s11^= w[42][3]
    s12^= w[43][0]; s13^= w[43][1]; s14^= w[43][2]; s15^= w[43][3]
    box = _inv_sbox
    for rnd in range(9, 0, -1):
        t0=box[s0]; t1=box[s13]; t2=box[s10]; t3=box[s7]
        t4=box[s4]; t5=box[s1]; t6=box[s14]; t7=box[s11]
        t8=box[s8]; t9=box[s5]; t10=box[s2]; t11=box[s15]
        t12=box[s12]; t13=box[s9]; t14=box[s6]; t15=box[s3]
        rk=w[rnd*4]; t0^=rk[0]; t1^=rk[1]; t2^=rk[2]; t3^=rk[3]
        rk=w[rnd*4+1]; t4^=rk[0]; t5^=rk[1]; t6^=rk[2]; t7^=rk[3]
        rk=w[rnd*4+2]; t8^=rk[0]; t9^=rk[1]; t10^=rk[2]; t11^=rk[3]
        rk=w[rnd*4+3]; t12^=rk[0]; t13^=rk[1]; t14^=rk[2]; t15^=rk[3]
        s0 =_mul_e[t0]^_mul_b[t1]^_mul_d[t2]^_mul_9[t3]
        s1 =_mul_9[t0]^_mul_e[t1]^_mul_b[t2]^_mul_d[t3]
        s2 =_mul_d[t0]^_mul_9[t1]^_mul_e[t2]^_mul_b[t3]
        s3 =_mul_b[t0]^_mul_d[t1]^_mul_9[t2]^_mul_e[t3]
        s4 =_mul_e[t4]^_mul_b[t5]^_mul_d[t6]^_mul_9[t7]
        s5 =_mul_9[t4]^_mul_e[t5]^_mul_b[t6]^_mul_d[t7]
        s6 =_mul_d[t4]^_mul_9[t5]^_mul_e[t6]^_mul_b[t7]
        s7 =_mul_b[t4]^_mul_d[t5]^_mul_9[t6]^_mul_e[t7]
        s8 =_mul_e[t8]^_mul_b[t9]^_mul_d[t10]^_mul_9[t11]
        s9 =_mul_9[t8]^_mul_e[t9]^_mul_b[t10]^_mul_d[t11]
        s10=_mul_d[t8]^_mul_9[t9]^_mul_e[t10]^_mul_b[t11]
        s11=_mul_b[t8]^_mul_d[t9]^_mul_9[t10]^_mul_e[t11]
        s12=_mul_e[t12]^_mul_b[t13]^_mul_d[t14]^_mul_9[t15]
        s13=_mul_9[t12]^_mul_e[t13]^_mul_b[t14]^_mul_d[t15]
        s14=_mul_d[t12]^_mul_9[t13]^_mul_e[t14]^_mul_b[t15]
        s15=_mul_b[t12]^_mul_d[t13]^_mul_9[t14]^_mul_e[t15]
    t0=box[s0]; t1=box[s13]; t2=box[s10]; t3=box[s7]
    t4=box[s4]; t5=box[s1]; t6=box[s14]; t7=box[s11]
    t8=box[s8]; t9=box[s5]; t10=box[s2]; t11=box[s15]
    t12=box[s12]; t13=box[s9]; t14=box[s6]; t15=box[s3]
    rk=w[0]; t0^=rk[0]; t1^=rk[1]; t2^=rk[2]; t3^=rk[3]
    rk=w[1]; t4^=rk[0]; t5^=rk[1]; t6^=rk[2]; t7^=rk[3]
    rk=w[2]; t8^=rk[0]; t9^=rk[1]; t10^=rk[2]; t11^=rk[3]
    rk=w[3]; t12^=rk[0]; t13^=rk[1]; t14^=rk[2]; t15^=rk[3]
    return bytes([t0,t1,t2,t3,t4,t5,t6,t7,t8,t9,t10,t11,t12,t13,t14,t15])

def _aes_cbc_decrypt(data, key, iv):
    if not data or len(data) % 16: return data
    n = len(data) // 16
    w = _key_schedule(key)
    out = bytearray(len(data))
    prev = iv
    for i in range(n):
        block = data[i*16:(i+1)*16]
        dec = _dec_block(block, w)
        for j in range(16):
            out[i*16+j] = dec[j] ^ prev[j]
        prev = block
    pad = out[-1]
    if 1 <= pad <= 16:
        return bytes(out[:-pad])
    return bytes(out)


# ===== 全局代理服务（封面图走代理绕过 SSL） =====
_proxy_port = 0
_proxy_started = False
_proxy_session = requests.Session()
_proxy_session.verify = False
_proxy_headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://mjv011.com/',
}

class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class _ProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            real_url = unquote(self.path[1:])
            if not real_url or not real_url.startswith('http'):
                self.send_response(404); self.end_headers(); return
            r = _proxy_session.get(real_url, headers=_proxy_headers, timeout=20, verify=False)
            ct = r.headers.get('Content-Type', 'image/jpeg')
            self.send_response(200)
            self.send_header('Content-Type', ct)
            self.send_header('Content-Length', len(r.content))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(r.content)
        except BrokenPipeError:
            pass
        except Exception:
            self.send_response(404); self.end_headers()
    def log_message(self, format, *args): pass

def _find_free_port():
    import socket
    sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sk.bind(('127.0.0.1', 0))
    port = sk.getsockname()[1]
    sk.close()
    return port

def _start_proxy():
    global _proxy_port, _proxy_started
    if _proxy_started: return
    _proxy_port = _find_free_port()
    server = _ThreadedHTTPServer(('127.0.0.1', _proxy_port), _ProxyHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _proxy_started = True


# ===== 内容类型判断 =====
def _is_novel(tid_or_vid):
    if not tid_or_vid: return False
    return tid_or_vid.startswith('novel')

def _is_image(tid_or_vid):
    if not tid_or_vid: return False
    return any(tid_or_vid.startswith(p) for p in ['18H', 'doujin', 'cg', 'cwp'])


# ===== Spider =====
class Spider(Spider):
    session = requests.Session()
    host = 'https://mjv011.com'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Referer': 'https://mjv011.com/',
    }

    def getName(self): return "mjv011"

    def isVideoFormat(self, url):
        if not url: return False
        return '.m3u8' in url or '.mp4' in url or '.ts' in url

    def manualVideoCheck(self): return False
    def destroy(self): pass

    def localProxy(self, param):
        return [404, 'text/plain', '']

    def init(self, extend=""):
        self.session.verify = False
        _start_proxy()
        try:
            self.session.get(
                f'{self.host}/zh/chinese_IamOverEighteenYearsOld/19/index.html',
                headers=self.headers, timeout=15, verify=False)
        except Exception:
            pass

    def _proxy_url(self, url):
        if not url: return ''
        if url.startswith('http://127.0.0.1'):
            return url
        return f'http://127.0.0.1:{_proxy_port}/{quote(url, safe="")}'

    def _fetch(self, url):
        try:
            r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
            r.encoding = 'utf-8'
            if r.status_code == 200:
                text = r.text
                # 年龄验证页检测：自动绕过
                if len(text) < 3000 and ('同意(enter)' in text or 'IamOverEighteenYearsOld' in text):
                    self.session.get(
                        f'{self.host}/zh/chinese_IamOverEighteenYearsOld/19/index.html',
                        headers=self.headers, timeout=20, verify=False)
                    r = self.session.get(url, headers=self.headers, timeout=20, verify=False)
                    r.encoding = 'utf-8'
                    if r.status_code == 200:
                        return r.text
                    return ''
                return text
            return ''
        except Exception:
            return ''

    # ===== 列表解析 =====
    def _parse_text_posts(self, text):
        """小说列表（无图）"""
        items = []
        for m in re.finditer(r"<div class='post'>\s*<div class='con'>\s*<h3[^>]*><a[^>]*href=\"([^\"]+)\"[^>]*>([^<]+)</a></h3>", text):
            href, title = m.groups()
            mm = re.search(r'/([^/]+)_content/(\d+)/([^/]+)\.html', href)
            if not mm: continue
            ctype, vid, slug = mm.group(1), mm.group(2), mm.group(3)
            items.append({
                'vod_id': f'{ctype}#{vid}#{slug}',
                'vod_name': title.strip(),
                'vod_pic': '',
                'vod_remarks': '',
            })
        return items

    def _parse_posts(self, text, tid=''):
        """根据分类解析列表：小说单独处理，其他统一按带图 post 处理"""
        if _is_novel(tid):
            return self._parse_text_posts(text)

        items = []
        for m in re.finditer(r"<div class='post'>\s*<a[^>]*href=\"([^\"]+)\"[^>]*><img[^>]*src='([^']+)'[^>]*>\s*</a>\s*<div class='con'>\s*<h3[^>]*><a[^>]*>([^<]+)</a></h3>(?:\s*<div class='meta'>([^<]*)</div>)?", text):
            href, pic, title, date = m.groups()
            date = date or ''
            mm = re.search(r'/([^/]+)_content/(\d+)/([^/]+)\.html', href)
            if not mm: continue
            ctype, vid, slug = mm.group(1), mm.group(2), mm.group(3)
            items.append({
                'vod_id': f'{ctype}#{vid}#{slug}',
                'vod_name': title.strip(),
                'vod_pic': self._proxy_url(pic),
                'vod_remarks': date.strip(),
            })
        return items

    def _build_cat_url(self, tid, page, extend=None):
        if extend and extend.get('sub'):
            sub = quote(unquote(extend['sub']), safe='/()')
            return f'{self.host}/zh/{sub}/{page}.html'
        if tid.startswith('search_'):
            kw = tid[7:]
            return f'{self.host}/zh/chinese_search/all/{kw}/{page}.html'
        # TVBox 可能截断 type_id，自动补全
        if tid.endswith('_random'):
            tid = tid + '/all'
        elif '/' not in tid:
            tid = tid + '_random/all'
        if page == 1:
            return f'{self.host}/zh/{tid}/index.html'
        return f'{self.host}/zh/{tid}/index_{page}.html'

    # ===== 接口 =====
    def homeContent(self, filter):
        classes = [
                {'type_id': 'chinese_random/all', 'type_name': '中文字幕'},
                {'type_id': 'censored_random/all', 'type_name': '有码'},
                {'type_id': 'uncensored_random/all', 'type_name': '无码'},
                {'type_id': 'reducing-mosaic_random/all', 'type_name': '无码破解'},
                {'type_id': 'amateurjav_random/all', 'type_name': '素人'},                
                {'type_id': 'animation_random/all', 'type_name': 'H动画'},
                {'type_id': 'dt_random/all', 'type_name': '国产自拍'},
                {'type_id': '18H_random/all', 'type_name': '18H漫画'},
                {'type_id': 'cg_random/all', 'type_name': '写真图集'},
                {'type_id': 'cwp_random/all', 'type_name': '国产写真'},
                {'type_id': 'novel_random/all', 'type_name': '小说'},
            ]
        
        filter = self._build_filters()
        return {'class': classes, 'filters': filter, 'type': '影视'}

    def _build_filters(self):
        """构造 TVBox filter 格式（网站左侧导航真实子分类）"""
        filters = {}
        chinese_opts = [
            {'n': '全部', 'v': ''},
            {'n': '随机', 'v': 'chinese_randomall/all'},
            {'n': '类别清单', 'v': 'chinese_categorylist/list'},
        ]
        filters['chinese_random/all'] = [{'key': 'sub', 'name': '中文字幕', 'value': chinese_opts}]
        uncensored_opts: list[dict[str, str]] = [
            {'n': '全部', 'v': ''},
            {'n': '一本道(1pondo)', 'v': 'uncensored_makersr/32/一本道(1pondo)'},
            {'n': 'カリビアンコム(Caribbeancom)', 'v': 'uncensored_makersr/30/カリビアンコム(Caribbeancom)'},
            {'n': 'カリビアンコムPPV', 'v': 'uncensored_makersr/40/カリビアンコムPPV(Caribbeancompr)'},
            {'n': '天然むすめ(10musume)', 'v': 'uncensored_makersr/31/天然むすめ(10musume)'},
            {'n': 'HEYZO', 'v': 'uncensored_makersr/17/HEYZO'},
            {'n': '東京熱(Tokyo Hot)', 'v': 'uncensored_makersr/29/東京熱(Tokyo Hot)'},
            {'n': 'ガチん娘！(Gachinco)', 'v': 'uncensored_makersr/35/ガチん娘！(Gachinco)'},
            {'n': 'パコパコママ(pacopacomama)', 'v': 'uncensored_makersr/36/パコパコママ(pacopacomama)'},
            {'n': 'エッチな4610', 'v': 'uncensored_makersr/34/エッチな4610'},
            {'n': '人妻斬り0930', 'v': 'uncensored_makersr/38/人妻斬り0930'},
            {'n': 'エッチな0930', 'v': 'uncensored_makersr/39/エッチな0930'},
            {'n': 'トリプルエックス(XXX-AV)', 'v': 'uncensored_makersr/126/トリプルエックス (XXX-AV)'},
        ]
        filters['uncensored_random/all'] = [{'key': 'sub', 'name': '厂商', 'value': uncensored_opts}]
        
        animation_opts = [
            {'n': '全部', 'v': ''},
            {'n': 'H有码动画', 'v': 'CensoredAnimation_random/all'},
            {'n': 'H无码动画', 'v': 'UncensoredAnimation_random/all'},
            {'n': 'H_3D动画', 'v': 'tdAnimation_random/all'},   
        ]
        filters['animation_random/all'] = [{'key': 'sub', 'name': '动漫', 'value': animation_opts}]

        comic_opts = [
            {'n': '全部', 'v': ''},
            {'n': '短篇同人', 'v': 'doujin_random/all'},
        ]
        filters['18H_random/all'] = [{'key': 'sub', 'name': '漫画', 'value': comic_opts}]

        cg_opts = [
            {'n': '全部', 'v': ''},
            {'n': 'Bejean On Line', 'v': 'cg_search/all/Bejean On Line'},
            {'n': 'Bomb.tv', 'v': 'cg_search/all/Bomb.tv'},
            {'n': 'DGC', 'v': 'cg_search/all/DGC'},
            {'n': 'Graphis Gals', 'v': 'cg_search/all/Graphis Gals'},
            {'n': 'Graphis Hatsunugi', 'v': 'cg_search/all/Graphis Hatsunugi'},
            {'n': 'image.tv', 'v': 'cg_search/all/image.tv'},
            {'n': 'Sabra.net', 'v': 'cg_search/all/Sabra.net'},
            {'n': 'S-Cute', 'v': 'cg_search/all/S-Cute'},
            {'n': 'X-City', 'v': 'cg_search/all/X-City'},
            {'n': 'YS Web', 'v': 'cg_search/all/YS Web'},
        ]
        filters['cg_random/all'] = [{'key': 'sub', 'name': '系列', 'value': cg_opts}]
        
        cwp_opts = [
            {'n': '全部', 'v': ''},
            {'n': '3AGirl AAA女郎', 'v': 'cwp_search/all/3AGirl AAA女郎'},
            {'n': 'ROSI寫真', 'v': 'cwp_search/all/ROSI寫真'},
            {'n': 'RU1MM 如壹寫真', 'v': 'cwp_search/all/RU1MM 如壹寫真'},
            {'n': 'DISI第四印象', 'v': 'cwp_search/all/DISI第四印象'},
        ]
        filters['cwp_random/all'] = [{'key': 'sub', 'name': '系列', 'value': cwp_opts}]

        novel_opts = [
            {'n': '全部', 'v': ''},
            {'n': '學生校園', 'v': 'novel_search/all/學生校園'},
            {'n': '職場激情', 'v': 'novel_search/all/職場激情'},
            {'n': '經驗故事', 'v': 'novel_search/all/經驗故事'},
            {'n': '暴力虐待', 'v': 'novel_search/all/暴力虐待'},
            {'n': '不倫戀情', 'v': 'novel_search/all/不倫戀情'},
            {'n': '群體換伴', 'v': 'novel_search/all/群體換伴'},
            {'n': '人妻熟女', 'v': 'novel_search/all/人妻熟女'},
            {'n': '科學幻想', 'v': 'novel_search/all/科學幻想'},
            {'n': '其他故事', 'v': 'novel_search/all/其他故事'},
            {'n': '玄幻仙俠', 'v': 'novel_search/all/玄幻仙俠'},
            {'n': '動漫修改', 'v': 'novel_search/all/動漫修改'},
            {'n': '長篇連載', 'v': 'novel_search/all/長篇連載'},
        ]
        filters['novel_random/all'] = [{'key': 'sub', 'name': '主题', 'value': novel_opts}]
        return filters           

    def homeVideoContent(self):
            text = self._fetch(f'{self.host}/zh/chinese_IamOverEighteenYearsOld/19/index.html')
            items = self._parse_posts(text, 'content_news/all')
            return {'list': items}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            return self._categoryContent_inner(tid, pg, filter, extend)
        except Exception:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _categoryContent_inner(self, tid, pg, filter, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        if not extend:
            extend = {}
        page = int(pg) if pg else 1
        # ===== 类别清单（中文字幕的子分类）: 文件夹形式（仿 18av） =====
        if extend.get('sub') == 'chinese_categorylist/list':
            return self._category_folder(page)
        if '@' in str(tid):
            return self._folder_detail(tid, page)
        url = self._build_cat_url(tid, page, extend)
        # 子分类筛选时按子分类内容类型解析
        parse_tid = tid
        if parse_tid.endswith('_random'):
            parse_tid = parse_tid + '/all'
        elif '/' not in parse_tid:
            parse_tid = parse_tid + '_random/all'
        if extend and extend.get('sub'):
            sub = extend['sub']
            if _is_novel(sub):
                parse_tid = 'novel_random/all'
            elif _is_image(sub):
                parse_tid = sub.split('_')[0] + '_random/all' if '_' in sub else 'cg_random/all'
        text = self._fetch(url)
        items = self._parse_posts(text, parse_tid)
        return {'list': items, 'page': page, 'pagecount': page + 1,
                'limit': len(items), 'total': page * len(items) + 1}

    # ===== 类别清单（文件夹形式，仿 18av） =====
    def _category_folder(self, pg):
        """类别清单: 抓取子分类索引页，以 folder 形式返回，点文件夹进入视频列表"""
        html = self._fetch(f'{self.host}/zh/chinese_categorylist/list/index.html')
        lst = []
        for m in re.finditer(
                r"<a[^>]+href=[\"']([^\"']*chinese_category/(\d+)/([^\"'/]+)/[^\"']*)[\"'][^>]*>([^<]+)</a>",
                html, re.I):
            category_url = m.group(1).strip()
            category_name = m.group(4).strip()
            if category_url.startswith(self.host):
                category_url = category_url[len(self.host):]
            lst.append({
                'vod_id': category_url + '@',
                'vod_name': category_name,
                'vod_pic': self.host.rstrip('/') + '/images/1v.jpg', 
                'vod_tag': 'folder',
                'vod_remarks': '分类',
            })
        return {'list': lst, 'page': 1, 'pagecount': 1,
                'limit': len(lst), 'total': len(lst)}

    def _folder_detail(self, tid, pg):
        """@ 文件夹: 去掉 @, 把子分类链接当作真实 URL 拉取视频列表（支持翻页）"""
        tid = str(tid).replace('@', '')
        url = self.host.rstrip('/') + tid
        if re.search(r'/\d+\.html$', url):
            url = re.sub(r'/\d+\.html$', '/' + str(pg) + '.html', url)
        else:
            base = url.rstrip('/')
            url = base + ('/index.html' if pg <= 1 else f'/index_{pg}.html')
        html = self._fetch(url)
        lst = self._parse_posts(html, 'chinese_category')
        return {'list': lst, 'page': pg, 'pagecount': 9999,
                'limit': len(lst), 'total': 9999}

    def detailContent(self, ids):
        try:
            return self._detailContent_inner(ids)
        except Exception:
            return {'list': []}

    def _detailContent_inner(self, ids):
        vid = str(ids[0] if isinstance(ids, list) else ids)
        ctype, num, slug = vid.split('#', 2)
        if _is_novel(ctype):
            return self._novel_detail(vid, ctype, num, slug)
        elif _is_image(ctype):
            return self._image_detail(vid, ctype, num, slug)
        else:
            return self._video_detail(vid, ctype, num, slug)

    def _video_detail(self, vid, ctype, num, slug):
        """视频详情（有播放器解密）"""
        url = f'{self.host}/zh/{ctype}_content/{num}/{slug}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        if not title:
            m = re.search(r'<title>([^<]+)</title>', text)
            if m: title = m.group(1).strip()

        cover = ''
        m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', text)
        if m: cover = m.group(1)
        if not cover:
            m = re.search(r"<meta[^>]*property=\"og:image\"[^>]*content=\"([^\"]+)\"", text)
            if m: cover = m.group(1)
        if not cover:
            m = re.search(r"<div class='post'>.*?<img[^>]*src='([^']+)'", text, re.S)
            if m: cover = m.group(1)

        m = re.search(r'hadeedg252=(\d+)', text)
        if not m: return {'list': []}
        hadeedg252 = int(m.group(1))
        m = re.search(r'hcdeedg252=(\d+)', text)
        if not m: return {'list': []}
        hcdeedg252 = int(m.group(1))
        m = re.search(r"var argdeqweqweqwe = '([^']+)'", text)
        if not m: return {'list': []}
        aes_key = m.group(1)
        m = re.search(r"var hdddedg252 = '([^']+)'", text)
        if not m: return {'list': []}
        aes_iv = m.group(1)

        mm = re.search(r"mvarr\['10_1'\]=(\[.*?\]);", text, re.S)
        if not mm: return {'list': []}
        mvarr_str = mm.group(1)
        items = re.findall(r"\['([^']*)','([^']*)','([^']*)','([^']*)','([^']*)','([^']*)'\]", mvarr_str)
        if not items: return {'list': []}

        urls = []
        for iframe_id, enc, html, prefix, empty, label in items:
            if not enc or not prefix: continue
            pid = self._decrypt_id(enc, hadeedg252, hcdeedg252, aes_key, aes_iv)
            if not pid: continue
            for res, label_name in [('1080', '1080P'), ('720', '720P'), ('480', '480P')]:
                urls.append(f'{label_name}${num}|{slug}|{pid}|{res}')

        if not urls: return {'list': []}

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(cover),
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': 'mjv011',
            'vod_play_url': '#'.join(urls),
        }
        return {'list': [vod]}

    def _novel_detail(self, vid, ctype, num, slug):
        """小说详情"""
        url = f'{self.host}/zh/{ctype}_content/{num}/{slug}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        content = ''
        m = re.search(r"id=['\"]novel_content_txtsize['\"][^>]*>(.*?)</div>", text, re.S)
        if m:
            raw = m.group(1)
            content = re.sub(r'<[^>]+>', '', raw)
            content = re.sub(r'&nbsp;', ' ', content)
            content = re.sub(r'\s+', ' ', content).strip()
        if not content:
            m = re.search(r"<span class='content_18h_wpcg'>([\s\S]*?)</span>\s*<div class='contents'", text)
            if m:
                raw = m.group(1)
                content = re.sub(r'<[^>]+>', '', raw)
                content = re.sub(r'&nbsp;', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()

        if len(content) > 3000:
            content = content[:3000] + '...'

        novel_json = json.dumps({'title': title, 'content': content}, ensure_ascii=False)
        play_url = f'阅读$novel://{novel_json}'

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': '',
            'vod_content': '',
            'vod_remarks': '',
            'vod_play_from': '小说',
            'vod_play_url': play_url,
            'vod_tag': 'text',
            'vod_player': '书',
        }
        return {'list': [vod]}

    def _image_detail(self, vid, ctype, num, slug):
        """图片详情（写真/漫画）"""
        url = f'{self.host}/zh/{ctype}_content/{num}/{slug}.html'
        text = self._fetch(url)
        if not text: return {'list': []}

        title = ''
        m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S)
        if m: title = re.sub(r'<[^>]+>', '', m.group(1)).strip()

        cover = ''
        m = re.search(r'"thumbnailUrl"\s*:\s*"([^"]+)"', text)
        if m: cover = m.group(1)

        # 提取详情页所有大图（第一页已包含全部）
        all_imgs = re.findall(r"src=['\"]([^'\"]*eemmhh02\.com/[^'\"]+\.(?:jpg|png|webp))['\"]", text, re.I)
        big_imgs = []
        seen = set()
        for img in all_imgs:
            if img in seen:
                continue
            seen.add(img)
            big_imgs.append(self._proxy_url(img))

        if not big_imgs:
            return {'list': []}

        pics = '&&'.join(big_imgs)
        play_url = f'查看$pics://{pics}'

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': self._proxy_url(cover),
            'vod_content': f'共 {len(big_imgs)} 张图片',
            'vod_remarks': str(len(big_imgs)) + 'P',
            'vod_play_from': '图片',
            'vod_play_url': play_url,
            'vod_tag': 'image',
            'vod_player': '画',
        }
        return {'list': [vod]}

    def _decrypt_id(self, enc, xor_key, base, aes_key, aes_iv):
        try:
            sep = chr(base + 97)
            parts = enc.split(sep)
            s1 = ''.join(chr(int(p, base) ^ xor_key) for p in parts if p)
            data = base64.b64decode(s1)
            plain = _aes_cbc_decrypt(data, aes_key.encode(), aes_iv.encode())
            return plain.decode('utf-8')
        except Exception:
            return ''

    def searchContent(self, key, quick, pg="1"):
        try:
            return self._searchContent_inner(key, quick, pg)
        except Exception:
            return {'list': [], 'page': int(pg) if pg else 1, 'pagecount': 1, 'limit': 0, 'total': 0}

    def _searchContent_inner(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        return self._categoryContent_inner(f'search_{key}', page, False, {})

    def playerContent(self, flag, id, vipFlags=None):
        try:
            return self._playerContent_inner(flag, id, vipFlags)
        except Exception:
            return {'parse': 0, 'url': '', 'header': {}, 'position': '0'}

    def _playerContent_inner(self, flag, id, vipFlags=None):
        # 小说
        if id.startswith('novel://'):
            return {'parse': 0, 'url': id, 'header': '', 'vod_player': '书'}
        # 图片
        if id.startswith('pics://'):
            return {'parse': 0, 'playUrl': '', 'url': id, 'header': self.headers}
        # 视频播放
        num, slug, pid, res = id.split('|', 3)
        url = f'{self.host}/js/player/play.php?numresolution={res}&lo=on&id={pid}'
        text = self._fetch(url)
        m3u8 = ''
        if text:
            mm = re.search(r'videoSources\s*=\s*(\[.*?\]);', text, re.S)
            if mm:
                arr = mm.group(1)
                sources = re.findall(r"src:\s*'([^']+)'[^}]*?size:\s*(\d+)", arr, re.S)
                if sources:
                    target = int(res) if str(res).isdigit() else 0
                    for u, s in sources:
                        if int(s) == target:
                            m3u8 = u
                            break
                    if not m3u8:
                        m3u8 = sources[0][0]
            if not m3u8:
                mm = re.search(r'https?://[^\s"<>\']+?\.m3u8', text)
                if mm: m3u8 = mm.group(0)
        return {'parse': 0, 'url': m3u8, 'header': {'Referer': self.host + '/'}, 'position': '0'}