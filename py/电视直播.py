# coding=utf-8
# TVBox直播源Python爬虫

import sys
sys.path.append('..')
from base.spider import Spider
import json

class Spider(Spider):
    def getName(self):
        return "电视直播源"

    def init(self, extend=""):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_name": "电影台", "type_id": "📺电影台"},
            {"type_name": "体育台", "type_id": "📺体育台"},
			{"type_name": "港台", "type_id": "📺港台"},
			{"type_name": "🔞+直播台", "type_id": "📺直播台🔞"},
			{"type_name": "港台三级🔞", "type_id": "港台三级🔞"}
        ]
        result['class'] = classes
        return result

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        videos = []

        # 频道数据
        channels = {
            "📺电影台": [
                {"name": "CCTV6电影", "url": "http://107.150.60.122/live/cctv6hd.m3u8"},
                {"name": "NOW爆谷台", "url": "http://173.208.234.146/live/nowbg.m3u8"},
                {"name": "NOW星影台", "url": "http://173.208.234.146/live/nowxy.m3u8"},
                {"name": "美亚电影HD", "url": "http://173.208.234.146/live/mymovie.m3u8"},
                {"name": "龙华电影*线路1", "url": "https://cdn.qd.je/163189/lhdy"},
				{"name": "龙华电影*线路2", "url": "http://iptv.4666888.xyz/iptv2A.php?id=45"},
				{"name": "靖天电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=56"},
				{"name": "東森电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=48"},
            ],
            "📺体育台": [
                {"name": "CCTV5体育*线路1", "url": "http://173.208.212.130:8181/1080p/cctv5.m3u8"},
				{"name": "CCTV5体育*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv5"},
				{"name": "CCTV5+体育赛事", "url": "http://107.150.60.122/live/cctv5p.m3u8"},
				{"name": "CCTV16奥林匹克*线路1", "url": "http://207.56.13.146:81/cdnlive/cctv16.m3u8"},
				{"name": "CCTV16奥林匹克*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv16"},
            ],
			"📺港台": [
                {"name": "翡翠台*线路1", "url": "http://183.62.8.58:50085/tsfile/live/0017_1.m3u8?key=txiptv&playlive=1&authid=0"},
				{"name": "翡翠台*线路2(挂梯)", "url": "https://cdn.qd.je/163189.php?id=fct"},
				{"name": "翡翠台4K(挂梯)", "url": "https://cdn3.indevs.in/stream/tvb/fct4k/"},
				],
			"📺直播台🔞": [
                {"name": "俄罗斯极限电影台", "url": "http://ef90a6cd.rossteleccom.net/iptv/2TBC4G2WWDG6RSUSN5SXSQEC/14158/index.m3u8"},
				{"name": "极限电影台", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855fdf/index.m3u8"},
				{"name": "惊艳台*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/85.ts"},
				{"name": "惊艳台*线路2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/87.ts"},
				{"name": "惊艳台*线路3", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/sajdxxzc/index.m3u8"},
				{"name": "潘多啦完美*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/86.ts"},
				{"name": "潘多啦完美*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855d75/index.m3u8"},
				{"name": "香蕉台HD*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/117.ts"},
				{"name": "香蕉台HD*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/mdfdc123/index.m3u8"},
				{"name": "松视1线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/88.ts"},
				{"name": "松视1线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c85giea/index.m3u8"},
				{"name": "松视2*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/89.ts"},
				{"name": "松视2*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c85fsaf/index.m3u8"},
				{"name": "松视3", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/90.ts"},
				{"name": "松视4", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_404_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "HOT", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_403_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "HAPPY", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/mdfdc125/index.m3u8"},
				{"name": "彩虹E", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855daa/index.m3u8"},
				{"name": "彩虹R", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_408_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "樂活頻道", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_410_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE8"},
				{"name": "奧視", "url": "http://125.227.210.55:1022/VideoInput/play.ts"},
				{"name": "奧視2", "url": "http://125.227.210.55:3031/VideoInput/play.ts"},
			],
			"港台三级🔞": [
                {"name": "1色降2之血玫瑰", "url": "https://vip1.lz-cdn1.com/20220331/733_58b741b7/index.m3u8"},
				{"name": "2色降2之萬里驅魔", "url": "https://m3u8.cdn202511.com/videos/202411/21/673e5ba03276de039d31a162/7cd5f8/index.m3u8"},
				{"name": "3倩女幽魂", "url": "https://jkunnzyx.com/20250423/nU0wWqCw/2000kb/hls/index.m3u8"},
				{"name": "4艳降勾魂", "url": "https://jkunnzyx.com/20250422/QZeJpxSo/2000kb/hls/index.m3u8"},
				{"name": "5唐朝禁宫秘史", "url": "https://jkunnzyx.com/20250422/IzZnh5aN/2000kb/hls/index.m3u8"},
				{"name": "6唐朝豪放女", "url": "https://jkunnzyx.com/20250422/ACOOZ77D/2000kb/hls/index.m3u8?t=1759862410098"},
				{"name": "7禁春", "url": "https://jkunnzyx.com/20250420/C6pNQeJa/2000kb/hls/index.m3u8"},
				{"name": "8聊斋画皮", "url": "https://vip1.lz-cdn1.com/20220602/7244_b84ad9e5/1200k/hls/mixed.m3u8"},
				{"name": "9惊变", "url": "https://jkunnzyx.com/20250216/DcmNwFCD/2000kb/hls/index.m3u8"},
				{"name": "10玉蒲团之偷情宝鉴", "url": "https://sex8sex811.com/20250726/gyeUh9IH/3000kb/hls/index.m3u8"},
				{"name": "11鸭王", "url": "https://vip1.lz-cdn.com/20220917/33110_558f97e4/1200k/hls/mixed.m3u8"},
				{"name": "12鸭王2", "url": "https://sex8sex811.com/20250720/ZVJOiFu6/3000kb/hls/index.m3u8"},
				{"name": "13玉蒲团之玉女心经", "url": "https://vip.lzcdn2.com/20220525/7634_7f4228f1/1200k/hls/mixed.m3u8"},
                {"name": "14聊斋艳谭之玉女聊斋", "url": "https://v8.rstu6.com/202310/10/9PN2VB66wu1/video/index.m3u8"},
				{"name": "15聊斋艳谭之月宫宝盒", "url": "https://vip1.lz-cdn1.com/20220602/7246_8dec3f14/1200k/hls/mixed.m3u8"},
                {"name": "16聊斋婴宁", "url": "https://vip1.lz-cdn1.com/20220602/7243_6ac4f584/1200k/hls/mixed.m3u8"},
				{"name": "17聊斋荷花三娘子", "url": "https://vip1.lz-cdn1.com/20220602/7247_71485294/1200k/hls/mixed.m3u8"},
				{"name": "18金瓶梅", "url": "https://vip1.lz-cdn1.com/20220516/5775_36eacadc/1200k/hls/mixed.m3u8"},
                {"name": "19金瓶梅2", "url": "https://vip1.lz-cdn1.com/20220516/5774_3b77c66d/1200k/hls/mixed.m3u8"},
				{"name": "20.3D肉蒲团之极乐宝鉴", "url": "https://vip1.lz-cdn.com/20220917/33091_abc5295d/1200k/hls/mixed.m3u8"},
				{"name": "21血恋", "url": "https://m.892539.xyz/play.php?site_id=12&source_id=136514"},
				{"name": "22血恋2", "url": "https://1.mysqldata3202s4l.com/20220906/vTtXOZiJ/index.m3u8"},
				{"name": "23鸭之一族", "url": "https://vip.lz15uu.com/20221016/425_d50261a1/index.m3u8"},
				{"name": "24五月樱唇", "url": "https://vostrely.com/20230510/TmmcwJpA/index.m3u8?t=1764471414752"},
				{"name": "25青楼十二房", "url": "https://yzzy.play-cdn7.com/20220701/2057_5582dfdc/index.m3u8?t=1764471518907"},
				{"name": "26现代情欲篇之换妻档案", "url": "https://v8.yuglf.com/202310/16/4j17Meq1LR1/video/index.m3u8?t=1764471651631"},
				{"name": "27舞男情未了", "url": "https://v.huosucdn.com/20251012/4HbI8O9k/index.m3u8"},
				{"name": "28桃色香居", "url": "https://yzzy.play-cdn14.com/20230728/30714_4c69114e/index.m3u8?t=1764472133794"},
				{"name": "29花街狂奔", "url": "https://svip.high23-playback.com/20240730/25025_60d99e11/index.m3u8?t=1764472224721"},
				{"name": "30三度诱惑", "url": "https://yzzy.play-cdn8.com/20220705/1308_6ed1e7c5/index.m3u8?t=1764472324424"},
			],
        }

        group = channels.get(tid, [])
        for idx, ch in enumerate(group):
            videos.append({
                "vod_id": tid + "_" + str(idx),
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_play_url": ch["url"]
            })

        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = 1
        result['limit'] = len(videos)
        result['total'] = len(videos)
        return result

    def detailContent(self, ids):
        result = {}
        id = ids[0]
        tid_idx = id.rsplit("_", 1)
        tid = tid_idx[0]
        idx = int(tid_idx[1])

        channels = {
            "📺电影台": [
                {"name": "CCTV6电影", "url": "http://107.150.60.122/live/cctv6hd.m3u8"},
                {"name": "NOW爆谷台", "url": "http://173.208.234.146/live/nowbg.m3u8"},
                {"name": "NOW星影台", "url": "http://173.208.234.146/live/nowxy.m3u8"},
                {"name": "美亚电影HD", "url": "http://173.208.234.146/live/mymovie.m3u8"},
                {"name": "龙华电影*线路1", "url": "https://cdn.qd.je/163189/lhdy"},
				{"name": "龙华电影*线路2", "url": "http://iptv.4666888.xyz/iptv2A.php?id=45"},
				{"name": "靖天电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=56"},
				{"name": "東森电影", "url": "http://iptv.4666888.xyz/iptv2A.php?id=48"},
            ],
            "📺体育台": [
                {"name": "CCTV5体育*线路1", "url": "http://173.208.212.130:8181/1080p/cctv5.m3u8"},
				{"name": "CCTV5体育*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv5"},
				{"name": "CCTV5+体育赛事", "url": "http://107.150.60.122/live/cctv5p.m3u8"},
				{"name": "CCTV16奥林匹克*线路1", "url": "http://207.56.13.146:81/cdnlive/cctv16.m3u8"},
				{"name": "CCTV16奥林匹克*线路2", "url": "https://php.jdshipin.com:2096/TVOD/iptv.php?id=cctv16"},
            ],
			"📺港台": [
                {"name": "翡翠台*线路1", "url": "http://183.62.8.58:50085/tsfile/live/0017_1.m3u8?key=txiptv&playlive=1&authid=0"},
				{"name": "翡翠台*线路2(挂梯)", "url": "https://cdn.qd.je/163189.php?id=fct"},
				{"name": "翡翠台4K(挂梯)", "url": "https://cdn3.indevs.in/stream/tvb/fct4k/"},
				],
			"📺直播台🔞": [
                {"name": "俄罗斯极限电影台", "url": "http://ef90a6cd.rossteleccom.net/iptv/2TBC4G2WWDG6RSUSN5SXSQEC/14158/index.m3u8"},
				{"name": "极限电影台", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855fdf/index.m3u8"},
				{"name": "惊艳台*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/85.ts"},
				{"name": "惊艳台*线路2", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/87.ts"},
				{"name": "惊艳台*线路3", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/sajdxxzc/index.m3u8"},
				{"name": "潘多啦完美*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/86.ts"},
				{"name": "潘多啦完美*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855d75/index.m3u8"},
				{"name": "香蕉台HD*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/117.ts"},
				{"name": "香蕉台HD*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/mdfdc123/index.m3u8"},
				{"name": "松视1线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/88.ts"},
				{"name": "松视1线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c85giea/index.m3u8"},
				{"name": "松视2*线路1", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/89.ts"},
				{"name": "松视2*线路2", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c85fsaf/index.m3u8"},
				{"name": "松视3", "url": "http://15.204.105.50:25461/live/G2s9zK2n9m/xDtwVfWM8T/90.ts"},
				{"name": "松视4", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_404_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "HOT", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_403_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "HAPPY", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/mdfdc125/index.m3u8"},
				{"name": "彩虹E", "url": "http://x315601.serv00.net/cr.php?url=http://lc.aacalive.com:26789/i/ghjnvq5o/8c855daa/index.m3u8"},
				{"name": "彩虹R", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_408_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE"},
				{"name": "樂活頻道", "url": "http://58.99.33.2:1935/liveedge2/QWXxqkAC_410_1/chunklist_w.m3u8?checkCode=37050688asdfsdfsadf&aa=60999&as=abcdefg&mmmm=&dr=123&dt=&cust_type=NE8"},
				{"name": "奧視", "url": "http://125.227.210.55:1022/VideoInput/play.ts"},
				{"name": "奧視2", "url": "http://125.227.210.55:3031/VideoInput/play.ts"},
			],
			"港台三级🔞": [
                {"name": "1色降2之血玫瑰", "url": "https://vip1.lz-cdn1.com/20220331/733_58b741b7/index.m3u8"},
				{"name": "2色降2之萬里驅魔", "url": "https://m3u8.cdn202511.com/videos/202411/21/673e5ba03276de039d31a162/7cd5f8/index.m3u8"},
				{"name": "3倩女幽魂", "url": "https://jkunnzyx.com/20250423/nU0wWqCw/2000kb/hls/index.m3u8"},
				{"name": "4艳降勾魂", "url": "https://jkunnzyx.com/20250422/QZeJpxSo/2000kb/hls/index.m3u8"},
				{"name": "5唐朝禁宫秘史", "url": "https://jkunnzyx.com/20250422/IzZnh5aN/2000kb/hls/index.m3u8"},
				{"name": "6唐朝豪放女", "url": "https://jkunnzyx.com/20250422/ACOOZ77D/2000kb/hls/index.m3u8?t=1759862410098"},
				{"name": "7禁春", "url": "https://jkunnzyx.com/20250420/C6pNQeJa/2000kb/hls/index.m3u8"},
				{"name": "8聊斋画皮", "url": "https://vip1.lz-cdn1.com/20220602/7244_b84ad9e5/1200k/hls/mixed.m3u8"},
				{"name": "9惊变", "url": "https://jkunnzyx.com/20250216/DcmNwFCD/2000kb/hls/index.m3u8"},
				{"name": "10玉蒲团之偷情宝鉴", "url": "https://sex8sex811.com/20250726/gyeUh9IH/3000kb/hls/index.m3u8"},
				{"name": "11鸭王", "url": "https://vip1.lz-cdn.com/20220917/33110_558f97e4/1200k/hls/mixed.m3u8"},
				{"name": "12鸭王2", "url": "https://sex8sex811.com/20250720/ZVJOiFu6/3000kb/hls/index.m3u8"},
				{"name": "13玉蒲团之玉女心经", "url": "https://vip.lzcdn2.com/20220525/7634_7f4228f1/1200k/hls/mixed.m3u8"},
                {"name": "14聊斋艳谭之玉女聊斋", "url": "https://v8.rstu6.com/202310/10/9PN2VB66wu1/video/index.m3u8"},
				{"name": "15聊斋艳谭之月宫宝盒", "url": "https://vip1.lz-cdn1.com/20220602/7246_8dec3f14/1200k/hls/mixed.m3u8"},
                {"name": "16聊斋婴宁", "url": "https://vip1.lz-cdn1.com/20220602/7243_6ac4f584/1200k/hls/mixed.m3u8"},
				{"name": "17聊斋荷花三娘子", "url": "https://vip1.lz-cdn1.com/20220602/7247_71485294/1200k/hls/mixed.m3u8"},
				{"name": "18金瓶梅", "url": "https://vip1.lz-cdn1.com/20220516/5775_36eacadc/1200k/hls/mixed.m3u8"},
                {"name": "19金瓶梅2", "url": "https://vip1.lz-cdn1.com/20220516/5774_3b77c66d/1200k/hls/mixed.m3u8"},
				{"name": "20.3D肉蒲团之极乐宝鉴", "url": "https://vip1.lz-cdn.com/20220917/33091_abc5295d/1200k/hls/mixed.m3u8"},
				{"name": "21血恋", "url": "https://m.892539.xyz/play.php?site_id=12&source_id=136514"},
				{"name": "22血恋2", "url": "https://1.mysqldata3202s4l.com/20220906/vTtXOZiJ/index.m3u8"},
				{"name": "23鸭之一族", "url": "https://vip.lz15uu.com/20221016/425_d50261a1/index.m3u8"},
				{"name": "24五月樱唇", "url": "https://vostrely.com/20230510/TmmcwJpA/index.m3u8?t=1764471414752"},
				{"name": "25青楼十二房", "url": "https://yzzy.play-cdn7.com/20220701/2057_5582dfdc/index.m3u8?t=1764471518907"},
				{"name": "26现代情欲篇之换妻档案", "url": "https://v8.yuglf.com/202310/16/4j17Meq1LR1/video/index.m3u8?t=1764471651631"},
				{"name": "27舞男情未了", "url": "https://v.huosucdn.com/20251012/4HbI8O9k/index.m3u8"},
				{"name": "28桃色香居", "url": "https://yzzy.play-cdn14.com/20230728/30714_4c69114e/index.m3u8?t=1764472133794"},
				{"name": "29花街狂奔", "url": "https://svip.high23-playback.com/20240730/25025_60d99e11/index.m3u8?t=1764472224721"},
				{"name": "30三度诱惑", "url": "https://yzzy.play-cdn8.com/20220705/1308_6ed1e7c5/index.m3u8?t=1764472324424"},
			],
        }

        group = channels.get(tid, [])
        if idx < len(group):
            ch = group[idx]
            vod = {
                "vod_id": id,
                "vod_name": ch["name"],
                "vod_pic": "",
                "vod_remarks": tid,
                "vod_content": ch["name"],
                "vod_play_from": "直链",
                "vod_play_url": ch["url"]
            }
            result['list'] = [vod]
        return result

    def playerContent(self, flag, id, vipFlags):
        result = {
            "parse": 0,
            "playUrl": "",
            "url": id,
            "header": ""
        }
        return result