# coding=utf-8
# ============================================================================
#  MissAV 专线 · TVBox py 插件   v3.0  (自愈版)
#  适配: TVBox / NewBox 一类带 Python(Chaquopy) 内核的壳
# ----------------------------------------------------------------------------
#  v3 相对上一版修了什么:
#   1. 补齐壳真正会调的方法: setExtendInfo / getDependence / liveContent /
#      isVideoFormat / manualVideoCheck / localProxy / action / destroy。
#      **上一版缺 setExtendInfo** —— 壳初始化插件时会直接 AttributeError,
#      表现就是"接口挂上去了, 但一点反应都没有"。
#   2. __getattr__ 兜底: 壳去探任何没实现的方法, 都返回空实现。以后壳升级
#      加新方法也不会再因为一个 AttributeError 把整条 py 通道带崩。
#   3. 所有对外方法一律不抛异常: 失败会变成列表里一张能看见的"诊断卡",
#      而不是无声的空白(排障不用再靠猜)。
#   4. 详情直接用服务端给的线路和清晰度(自动 / 720P / 1080P / 原画 四档),
#      播放走服务端 relay, header 自带。
#   5. 去推广: 服务端塞在简介里的群广告整段剔除; 片单里混进来的推广条目丢掉。
#   6. 零第三方依赖; import 阶段不联网、不读写任何文件; 令牌只放内存。
# ============================================================================

import json
import time

try:
    import urllib.request as _R
    import urllib.parse as _P
except Exception:                       # py2 兜底
    try:
        import urllib2 as _R
    except Exception:
        _R = None
    try:
        import urllib as _P
    except Exception:
        _P = None

try:
    import ssl as _SSL                  # 可选, 缺了也能跑
except Exception:
    _SSL = None

BASE = "https://missav.ws.ystv.top"
UA = "okhttp/3.12.0"
TIMEOUT = 12
RETRY = 2

# 想手填令牌就填这里; 留空 = 脚本自己匿名开号(推荐)
TOKEN = ""

# ---- 推广/广告关键词: 命中即整行丢弃(只作用于简介文本, 不动片名) ----
_AD_WORDS = (
    "t.me/", "telegram", "twitter", "官方群", "福利群", "交流群", "群组", "群組",
    "加群", "进群", "進群", "推广", "推廣", "广告", "廣告", "帝皇", "影视app",
    "发布页", "發布頁", "永久域名", "永久地址", "备用域名", "備用域名",
    "防失联", "防失聯", "下载app", "下載app", "官网", "官網", "客服",
    "请收藏", "請收藏", "http://", "https://", "www.",
)
# ---- 片单里混进来的推广条目(按片名判断, 宁可漏杀不误杀) ----
_AD_ITEMS = ("官方群", "福利群", "交流群", "加群", "进群", "進群",
             "永久域名", "永久地址", "发布页", "發布頁", "广告位")


def _ctx():
    """不校验证书的 SSL 上下文; 拿不到就返回 None(退回默认)"""
    if _SSL is None:
        return None
    try:
        return _SSL._create_unverified_context()
    except Exception:
        return None


def _get(url):
    """取文本; 出错返回空串, 绝不外抛"""
    if _R is None:
        return ""
    for _ in range(RETRY + 1):
        try:
            req = _R.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
            fh = None
            try:
                c = _ctx()
                if c is not None:
                    try:
                        fh = _R.urlopen(req, timeout=TIMEOUT, context=c)
                    except TypeError:
                        fh = _R.urlopen(req, timeout=TIMEOUT)
                else:
                    fh = _R.urlopen(req, timeout=TIMEOUT)
                data = fh.read()
            finally:
                try:
                    if fh is not None:
                        fh.close()
                except Exception:
                    pass
        except Exception:
            time.sleep(0.4)
            continue
        try:
            data = data.decode("utf-8", "replace")
        except Exception:
            pass                            # py2: 本来就是 str
        if data:
            return data
    return ""


def _jget(url):
    try:
        return json.loads(_get(url) or "{}")
    except Exception:
        return {}


def _q(s):
    s = "" if s is None else str(s)
    if _P is None:
        return s
    try:
        return _P.quote(s, safe="")
    except Exception:
        pass
    try:
        if not isinstance(s, bytes):
            s = s.encode("utf-8")
        return _P.quote(s, safe="")
    except Exception:
        return s


def _clean_text(text):
    """逐行剔推广; 顺带清掉 ━━━ / ---- 这类装饰线"""
    if not text:
        return ""
    keep = []
    for line in str(text).replace("\r", "").split("\n"):
        s = line.strip()
        if not s:
            continue
        low = s.lower()
        if any(w in low for w in _AD_WORDS):
            continue
        if len(set(s)) <= 2:                # 装饰线
            continue
        keep.append(s)
    return "\n".join(keep)


def _drop_ads(lst):
    out = []
    for v in (lst or []):
        if not isinstance(v, dict):
            continue
        nm = str(v.get("vod_name") or "")
        if any(w in nm for w in _AD_ITEMS):
            continue
        out.append(v)
    return out


class Spider(object):
    NAME = "MissAV 专线"

    # ---------------------------------------------------------------- 基础
    def __init__(self, *args, **kwargs):
        self.name = self.NAME
        self.extend = ""
        self._tok = TOKEN
        self._err = ""
        self._need = ""          # 想换令牌就写这里, 下一次请求自动换

    def __getattr__(self, key):
        # 壳探到没实现的方法 -> 给个空实现, 不让 AttributeError 带崩整条通道
        if key.startswith("_") or key in ("name", "extend", "_tok"):
            raise AttributeError(key)

        def _noop(*a, **kw):
            return None
        return _noop

    def getName(self):
        return self.name

    def setExtendInfo(self, extend):
        """壳在初始化时一定会调这个 —— 上一版就是缺它才"没反应" """
        try:
            if extend is None or isinstance(extend, (list, tuple, dict)):
                if isinstance(extend, dict):
                    self._extend_obj(extend)
                return
            self.extend = str(extend)
            self._extend_obj(self.extend)
        except Exception:
            pass

    def init(self, extend=""):
        try:
            if isinstance(extend, dict):
                self._extend_obj(extend)
            elif isinstance(extend, str) and extend.strip():
                self.extend = extend.strip()
                self._extend_obj(self.extend)
        except Exception:
            pass
        return None

    def _extend_obj(self, ext):
        """extend 支持: 裸令牌 / {"token":"xxx"} / 带 token=xxx 的串"""
        try:
            tok = ""
            if isinstance(ext, dict):
                tok = str(ext.get("token") or ext.get("tk") or "")
            else:
                s = str(ext).strip()
                if s.startswith("{"):
                    try:
                        tok = str(json.loads(s).get("token") or "")
                    except Exception:
                        tok = ""
                elif "=" in s:
                    for kv in s.replace("&", ";").split(";"):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            if k.strip().lower() in ("token", "t", "tk"):
                                tok = v.strip()
                                break
                elif "://" not in s and len(s) > 8:
                    tok = s
            if tok:
                self._tok = tok
        except Exception:
            pass

    def getDependence(self):
        """不依赖任何外部 py, 返回空表"""
        return []

    def destroy(self):
        return None

    def isVideoFormat(self, url):
        try:
            u = str(url or "").lower()
            return u.endswith(".m3u8") or u.endswith(".mp4") or ".m3u8?" in u
        except Exception:
            return False

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return ""

    def liveContent(self, url=""):
        return {"lives": []}

    def localProxy(self, param):
        return None

    # ---------------------------------------------------------------- 令牌
    def _new_tok(self):
        j = _jget(BASE + "/api/tvbox/reg?ts=" + str(int(time.time() * 1000)))
        tok = str(j.get("tok") or "")
        if tok:
            self._tok = tok
            self._err = ""
        return tok

    def _token(self, force=False):
        if force:
            self._tok = ""
        if not self._tok:
            self._new_tok()
        return self._tok

    def _api(self, path, **kw):
        """调服务端; 令牌废了自动换新重试一次; 失败把原因记进 self._err"""
        if _R is None:
            self._err = "本机 Python 没有 urllib, 无法联网"
            return {}
        if self._need:
            self._tok = str(self._need)
            self._need = ""
        last = ""
        for i in range(2):
            tok = self._token(force=(i > 0))
            parts = []
            for k in kw:
                v = kw[k]
                if v is None or v == "":
                    continue
                parts.append("%s=%s" % (k, _q(v)))
            if tok:
                parts.append("t=" + _q(tok))
            url = BASE + path + ("?" + "&".join(parts) if parts else "")
            txt = _get(url)
            if not txt:
                last = "连不上服务端(%s)" % BASE
                continue
            try:
                j = json.loads(txt)
            except Exception:
                last = "服务端返回的不是 JSON: " + txt[:120]
                continue
            if isinstance(j, dict) and (j.get("ok") is False or j.get("error")):
                last = str(j.get("msg") or j.get("error") or "服务端拒绝")
                continue
            self._err = ""
            return j if isinstance(j, dict) else {"list": j}
        self._err = last or "服务端没有返回数据"
        return {}

    # ---------------------------------------------------------------- 诊断
    def _diag(self):
        return [{
            "vod_id": "diag:info",
            "vod_name": "[诊断] 服务端没响应",
            "vod_pic": BASE + "/img/diag",
            "vod_remarks": "点开看原因",
            "vod_content": (
                "原因: %s\n\n"
                "· 先确认手机能上网\n"
                "· 服务端地址: %s\n"
                "· 令牌是脚本自动开的, 不用你填\n"
                "· 若一直失败, 多半是服务端暂时下线或换了域名"
            ) % (self._err or "未知", BASE),
        }]

    # ---------------------------------------------------------------- 接口
    def homeContent(self, filter=False):
        try:
            j = self._api("/api/tvbox/home")
            cls = j.get("class") or []
            if not cls:
                return {"class": [], "list": self._diag(), "filters": {}}
            return {"class": cls, "filters": j.get("filters") or {}}
        except Exception as e:
            self._err = str(e)
            return {"class": [], "list": self._diag(), "filters": {}}

    def homeVideoContent(self):
        try:
            return {"list": self.categoryContent("hot:latest", 1, False, "").get("list") or []}
        except Exception:
            return {"list": []}

    def categoryContent(self, tid, pg=1, filter=False, extend=""):
        try:
            tid = str(tid or "hot:latest")
            if tid.startswith("diag"):
                return {"list": self._diag(), "page": 1, "pagecount": 1,
                        "limit": 1, "total": 1}
            try:
                pg = int(pg)
            except Exception:
                pg = 1
            if pg < 1:
                pg = 1
            j = self._api("/api/tvbox/list", tid=tid, pg=pg)
            lst = _drop_ads(j.get("list"))
            if not lst and self._err:
                lst = self._diag()
            return {
                "list": lst,
                "page": j.get("page") or pg,
                "pagecount": j.get("pagecount") or 1,
                "limit": j.get("limit") or 48,
                "total": j.get("total") or 0,
            }
        except Exception as e:
            self._err = str(e)
            return {"list": self._diag(), "page": 1, "pagecount": 1,
                    "limit": 1, "total": 1}

    def detailContent(self, ids):
        try:
            if isinstance(ids, (list, tuple)):
                vid = str(ids[0]) if len(ids) else ""
            else:
                vid = str(ids or "")
            vid = vid.split("@")[0].strip()
            if not vid or vid.startswith("diag"):
                return {"list": self._diag()}
            j = self._api("/api/tvbox/detail", id=vid)
            lst = _drop_ads(j.get("list"))
            if not lst:
                return {"list": self._diag()}
            for v in lst:
                # 去推广: 只留演员/标签等有用信息
                v["vod_content"] = _clean_text(v.get("vod_content"))
                if not v["vod_content"]:
                    v["vod_content"] = "片名: %s" % (v.get("vod_name") or vid)
                pic = str(v.get("vod_pic") or "")
                if not pic.startswith("http"):
                    v["vod_pic"] = BASE + "/img/" + vid
                # 播放线路/清晰度直接用服务端给的(自动/720P/1080P/原画)
                if not v.get("vod_play_url"):
                    v["vod_play_from"] = "MissAV专线"
                    v["vod_play_url"] = "自动$%s@auto" % vid
            return {"list": lst}
        except Exception as e:
            self._err = str(e)
            return {"list": self._diag()}

    def searchContent(self, key, quick=False, pg=1):
        try:
            try:
                pg = int(pg)
            except Exception:
                pg = 1
            if pg < 1:
                pg = 1
            j = self._api("/api/tvbox/search", wd=key, pg=pg)
            lst = _drop_ads(j.get("list"))
            if not lst:
                return {"list": [], "page": pg, "pagecount": 1,
                        "limit": 24, "total": 0}
            return {
                "list": lst,
                "page": j.get("page") or pg,
                "pagecount": j.get("pagecount") or 1,
                "limit": j.get("limit") or 24,
                "total": j.get("total") or 0,
            }
        except Exception as e:
            self._err = str(e)
            return {"list": [], "page": 1, "pagecount": 1, "limit": 1, "total": 0}

    def playerContent(self, flag, id, vipFlags=""):
        try:
            s = str(id or "")
            if "@" in s:
                rid, q = s.split("@", 1)
            else:
                rid, q = s, ""
            rid = rid.strip()
            if not rid or rid.startswith("diag"):
                return {"parse": 0, "url": "", "header": ""}
            j = self._api("/api/tvbox/play", id=rid, q=q.strip())
            url = str(j.get("url") or "")
            if not url:
                return {"parse": 0, "url": "", "header": ""}
            header = j.get("header") or {}
            if not isinstance(header, (dict, str)):
                header = {}
            return {"parse": 0, "url": url, "header": header}
        except Exception:
            return {"parse": 0, "url": "", "header": ""}


# ----------------------------------------------------------------------------
# 自检: 本机直接 python3 missav.py 就会把每一段的真实返回打出来
# (壳加载插件时不会执行这段)
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    sp = Spider()
    print("getDependence :", sp.getDependence())
    sp.setExtendInfo("")                      # 壳初始化一定会调这一步
    sp.init("")
    home = sp.homeContent(False)
    print("homeContent   : 分类 %d 个" % len(home.get("class") or []))
    lst = sp.categoryContent("hot:latest", 1, False, "")
    print("category      : 第1页 %d 条 / 共 %s 页 / 共 %s 部"
          % (len(lst.get("list") or []), lst.get("pagecount"), lst.get("total")))
    if lst.get("list"):
        vid = lst["list"][0].get("vod_id")
        det = sp.detailContent([vid])
        d = (det.get("list") or [{}])[0]
        print("detail        : %s | 简介=%r" % (d.get("vod_name"), d.get("vod_content")))
        print("play_url      : %s" % d.get("vod_play_url"))
        if d.get("vod_play_url"):
            first = d["vod_play_url"].split("$$$")[0].split("#")[0].split("$")[-1]
            pl = sp.playerContent("", first, "")
            print("player        : %s" % str(pl.get("url"))[:90])
    se = sp.searchContent("abc", False, 1)
    print("search        : 命中 %s 条" % se.get("total"))
