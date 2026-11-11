#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare IP地址收集器 v3.1【修复完整版】
新增：cdn-cgi/trace 连通预检，优先从 trace 获取国家码
修复：trace 全失败兜底、随机UA、随机延迟、https预检、限流、重试、多 GeoIP 兜底、完善正则、blob 自动转 raw、官方段过滤
适配 GitHub Actions 定时运行，对齐 yuanxiawan/cfipv4db 容错策略
"""

import requests
import re
import os
import time
import random
import ipaddress
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime, timezone, timedelta

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.7 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
]

class CFIPCollector:
    def __init__(self, urls_config='urls.json', main_config='config.json'):
        self.beijing_tz = timezone(timedelta(hours=8))
        self.cache = dict()
        self.load_urls_config(urls_config)
        self.load_main_config(main_config)
        self.setup_global_variables()
        print("Cloudflare IP收集器 v3.1【修复完整版】初始化完成")

    def get_beijing_time(self):
        return datetime.now(self.beijing_tz)

    def _github_blob_to_raw(self, url: str) -> str:
        """把 github blob 链接自动转为 raw"""
        if "github.com" in url and "/blob/" in url:
            return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        return url

    def load_urls_config(self, config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                raw_list = config.get('url_sources', [])
            self.urls = [self._github_blob_to_raw(u.strip()) for u in raw_list if u.strip()]
            print(f'✅ 已加载 {len(self.urls)} 个URL数据源（blob自动转raw）')
        except Exception:
            print(f'ℹ️ 未找到 {config_file}，使用内置默认数据源')
            raw_list = [
                'https://ip.164746.xyz',
                'https://api.uouin.com/cloudflare.html',
                'https://addressesapi.090227.xyz/CloudFlareYes',
                'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt',
                'https://www.wetest.vip/page/cloudflare/address_v6.html',
                'https://www.wetest.vip/page/cloudflare/address_v4.html',
                'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/030101-bestcf.txt',
                'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/wetest-cloudflare-v4.txt',
                'https://raw.githubusercontent.com/ZhiXuanWang/cf-speed-dns/main/ipTop10.html',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/main/JP.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/main/DE.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/main/NL.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/main/SG.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/main/US.txt',
                'https://raw.githubusercontent.com/camel52zhang/yxip/main/ip.txt',
                'https://raw.githubusercontent.com/hubbylei/bestcf/main/bestcf.txt',
                'https://raw.githubusercontent.com/minghe168/cfip-auto/main/full_ips.txt',
                'https://raw.githubusercontent.com/yuanxiawan/cfipv4db/main/cfip.txt',
                'https://raw.githubusercontent.com/nyoungo/bestIp/main/best_ips.txt',
                'https://www.wetest.vip/page/cloudflare/address_v4.html'
            ]
            self.urls = [self._github_blob_to_raw(u.strip()) for u in raw_list if u.strip()]

    def load_main_config(self, config_file):
        def strip_json_comments(text: str):
            lines = []
            for line in text.splitlines():
                if not line.strip().startswith("//"):
                    lines.append(line)
            return "\n".join(lines)
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cleaned = strip_json_comments(f.read())
                self.config = json.loads(cleaned)
            print('✅ 主配置文件加载成功')
        except Exception:
            print(f'ℹ️ 未找到 {config_file}，启用内置默认配置')
            self.set_default_config()

    def set_default_config(self):
        self.config = {
            "request_settings": {
                "timeout": 10,
                "user_agent": random.choice(UA_POOL),
                "max_workers_url": 5,
                "max_workers_ipv4": 8,
                "max_workers_ipv6": 6,
                "max_workers_trace": 6,
                "retry_times": 2,
                "retry_delay": 1,
                "geo_delay": 0.2,
                "trace_timeout": 10,
                "trace_random_delay": [0.2, 0.7]
            },
            "output_settings": {
                "ipv4_filename": "ip.txt",
                "ipv6_filename": "ipv6.txt",
                "pure_ipv4": "pure_v4.txt",
                "pure_ipv6": "pure_v6.txt",
                "non_us_folder": "non_us_ips",
                "port": 8443,
                "save_all_ips": True,
                "save_non_us_separately": True,
                "save_pure_ip": True
            },
            "location_settings": {
                "baidu_api_url": "https://opendata.baidu.com/api.php",
                "fallback_api": "https://api.ip.sb/geoip/",
                "us_keywords": ["美国", "United States", "US", "USA"],
                "enable_location_query": True,
                "use_cache": True
            },
            "filter_settings": {
                "enable_ip_validation": True,
                "remove_private_ips": True,
                "remove_duplicates": True,
                "filter_to_cf_range": True,
                "enable_trace_check_v4": True,
                "enable_trace_check_v6": False
            },
            "progress_settings": {
                "show_progress": True,
                "progress_interval": 10
            }
        }

    def setup_global_variables(self):
        self.ipv4_pattern = re.compile(r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b")
        self.ipv6_pattern = re.compile(r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}|:(?::[0-9a-fA-F]{1,4}){1,7}|::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\b")
        self.headers = {
            'User-Agent': self.config['request_settings']['user_agent'],
            'Accept': 'application/json'
        }
        self.progress_lock = threading.Lock()
        self.completed_count = 0
        self.total_count = 0
        self.success_count = 0

        # Cloudflare 官方段
        self.cf_v4_nets = [ipaddress.IPv4Network(p) for p in [
            "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
            "104.16.0.0/12", "108.162.192.0/18", "131.0.72.0/22",
            "141.101.64.0/18", "162.158.0.0/15", "172.64.0.0/13",
            "185.199.108.0/22", "188.114.96.0/20", "190.93.240.0/20",
            "197.234.240.0/22", "198.41.128.0/17"
        ]]
        self.cf_v6_nets = [ipaddress.IPv6Network(p) for p in [
            "2400:cb00::/32", "2606:4700::/32", "2803:f800::/32",
            "2405:b500::/32", "2405:8100::/32", "2a06:98c0::/29",
            "2c0f:f248::/32"
        ]]

    def is_ip_in_cf_range(self, ip_obj):
        if isinstance(ip_obj, ipaddress.IPv4Address):
            return any(ip_obj in net for net in self.cf_v4_nets)
        else:
            return any(ip_obj in net for net in self.cf_v6_nets)

    def trace_check(self, ip: str, is_v6: bool):
        """cdn-cgi/trace 预检，成功返回 (True, country_code)，增加随机延时 + 随机UA + https"""
        req_cfg = self.config["request_settings"]
        time.sleep(random.uniform(*req_cfg["trace_random_delay"]))
        headers = {"User-Agent": random.choice(UA_POOL)}
        timeout = req_cfg["trace_timeout"]
        if is_v6:
            url = f"https://[{ip}]/cdn-cgi/trace"
        else:
            url = f"https://{ip}/cdn-cgi/trace"
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and "loc=" in resp.text:
                m = re.search(r"loc=([A-Z]{2})", resp.text)
                cc = m.group(1) if m else "UNKNOWN"
                return True, cc
            return False, ""
        except Exception:
            return False, ""

    def run_trace_filter(self, ip_set, is_v6: bool):
        flt = self.config["filter_settings"]
        if is_v6 and not flt.get("enable_trace_check_v6", False):
            return [(ip, None) for ip in ip_set]
        if not is_v6 and not flt.get("enable_trace_check_v4", True):
            return [(ip, None) for ip in ip_set]

        print(f"\n🔎 开始 cdn-cgi/trace 预检，共 {len(ip_set)} 个 {'IPv6' if is_v6 else 'IPv4'}")
        workers = self.config["request_settings"]["max_workers_trace"]
        passed = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futs = {executor.submit(self.trace_check, ip, is_v6): ip for ip in ip_set}
            for f in as_completed(futs):
                ip = futs[f]
                ok, cc = f.result()
                if ok:
                    passed.append((ip, cc))
        print(f"✅ trace 预检通过：{len(passed)} / {len(ip_set)}")
        # ========== 核心兜底：全部被拦截，放行全部候选 IP ==========
        if len(passed) == 0:
            print("\n⚠️ 全部 trace 请求被 Cloudflare 风控拦截，触发降级，保留全部候选IP，避免输出空文件")
            return [(ip, None) for ip in ip_set]
        return passed

    def ensure_folders(self):
        non_us_folder = self.config['output_settings']['non_us_folder']
        if not os.path.exists(non_us_folder):
            os.makedirs(non_us_folder)
            print(f'📁 创建文件夹: {non_us_folder}')

    def clean_old_files(self):
        out = self.config['output_settings']
        files = [out['ipv4_filename'], out['ipv6_filename']]
        if out.get("save_pure_ip"):
            files += [out['pure_ipv4'], out['pure_ipv6']]
        for f in files:
            if os.path.exists(f):
                os.remove(f)
                print(f'🗑️  删除旧文件: {f}')

    def fetch_url(self, url):
        req_cfg = self.config['request_settings']
        for attempt in range(req_cfg['retry_times'] + 1):
            try:
                headers = {"User-Agent": random.choice(UA_POOL)}
                resp = requests.get(url, headers=headers, timeout=req_cfg['timeout'])
                resp.raise_for_status()
                return resp.text
            except requests.exceptions.RequestException:
                if attempt < req_cfg['retry_times']:
                    time.sleep(req_cfg['retry_delay'])
        print(f'❌ 请求 {url} 多次失败')
        return None

    def extract_ips_from_text(self, text):
        ipv4_raw = self.ipv4_pattern.findall(text)
        ipv6_raw = self.ipv6_pattern.findall(text)
        valid_ipv4 = set()
        valid_ipv6 = set()
        flt = self.config['filter_settings']

        for s in ipv4_raw:
            try:
                ip = ipaddress.IPv4Address(s)
                if flt['remove_private_ips'] and ip.is_private:
                    continue
                if flt['filter_to_cf_range'] and not self.is_ip_in_cf_range(ip):
                    continue
                valid_ipv4.add(str(ip))
            except Exception:
                pass
        for s in ipv6_raw:
            try:
                ip = ipaddress.IPv6Address(s)
                if flt['remove_private_ips'] and ip.is_private:
                    continue
                if flt['filter_to_cf_range'] and not self.is_ip_in_cf_range(ip):
                    continue
                valid_ipv6.add(ip.compressed.lower())
            except Exception:
                pass
        return valid_ipv4, valid_ipv6

    def get_location(self, ip, pre_cc=None):
        loc_cfg = self.config['location_settings']
        if pre_cc is not None and pre_cc != "UNKNOWN":
            name_map = {
                "JP": "日本", "SG": "新加坡", "DE": "德国", "NL": "荷兰",
                "US": "美国", "KR": "韩国", "HK": "中国香港", "TW": "中国台湾"
            }
            self.cache[ip] = name_map.get(pre_cc, pre_cc)
            return self.cache[ip], True
        if not loc_cfg['enable_location_query']:
            return "未知", False
        if loc_cfg['use_cache'] and ip in self.cache:
            return self.cache[ip], True

        try:
            url = f"{loc_cfg['baidu_api_url']}?co=&resource_id=6006&oe=utf8&query={ip}"
            r = requests.get(url, headers=self.headers, timeout=5)
            j = r.json()
            if j.get("status") == "0" and j.get("data"):
                loc = j["data"][0].get("location", "未知")
                if loc != "未知":
                    self.cache[ip] = loc
                    return loc, True
        except Exception:
            pass
        try:
            r = requests.get(loc_cfg['fallback_api'] + ip, headers=self.headers, timeout=5)
            j = r.json()
            loc = j.get("country", "未知")
            self.cache[ip] = loc
            return loc, True
        except Exception:
            pass
        return "未知", False

    def process_single_ip(self, ip, pre_cc):
        req_delay = self.config["request_settings"]["geo_delay"]
        time.sleep(req_delay)
        location, success = self.get_location(ip, pre_cc)
        if self.config['progress_settings']['show_progress']:
            with self.progress_lock:
                self.completed_count += 1
                if success:
                    self.success_count += 1
                interval = self.config['progress_settings']['progress_interval']
                if self.completed_count % interval == 0 or self.completed_count == self.total_count:
                    rate = (self.success_count / self.completed_count * 100) if self.completed_count else 0
                    print(f'📊 进度: {self.completed_count}/{self.total_count} 成功率 {rate:.1f}%')
        return ip, location, success

    def process_urls_parallel(self):
        all_ipv4, all_ipv6 = set(), set()
        workers = self.config['request_settings']['max_workers_url']
        print(f'🚀 并行拉取 {len(self.urls)} 数据源')
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fu = {executor.submit(self.fetch_url, u): u for u in self.urls}
            for f in as_completed(fu):
                u = fu[f]
                txt = f.result()
                if txt:
                    v4, v6 = self.extract_ips_from_text(txt)
                    all_ipv4.update(v4)
                    all_ipv6.update(v6)
                    print(f'✅ {u} | v4:{len(v4)} v6:{len(v6)}')
        if self.config['filter_settings']['remove_duplicates']:
            all_ipv4 = set(all_ipv4)
            all_ipv6 = set(all_ipv6)
        return all_ipv4, all_ipv6

    def query_ips_parallel(self, trace_passed_list, is_ipv6=False):
        self.completed_count = self.success_count = 0
        self.total_count = len(trace_passed_list)
        if not trace_passed_list:
            return []
        workers_key = "max_workers_ipv6" if is_ipv6 else "max_workers_ipv4"
        workers = self.config['request_settings'][workers_key]
        label = "IPv6" if is_ipv6 else "IPv4"
        print(f'🌍 查询 {self.total_count} {label} 地理位置，线程 {workers}')
        res = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fi = {executor.submit(self.process_single_ip, ip, pre_cc): (ip, pre_cc) for ip, pre_cc in trace_passed_list}
            for f in as_completed(fi):
                ip, pre_cc = fi[f]
                try:
                    ip_out, loc, ok = f.result()
                    res.append((ip_out, loc))
                except Exception as e:
                    print(f'❌ {ip} 查询异常 {e}')
                    res.append((ip, "未知"))
        rate = (self.success_count / self.total_count * 100) if self.total_count else 0
        print(f'✅ {label} 查询结束，成功 {self.success_count}/{self.total_count}，成功率 {rate:.1f}%')
        return res

    def is_us_location(self, location):
        if location == "未知":
            return False
        kw = self.config['location_settings']['us_keywords']
        low = location.lower()
        return any(k.lower() in low for k in kw)

    def save_results_with_location(self, ip_results, filename, pure_filename, is_ipv6=False):
        if not ip_results:
            return [], []
        if is_ipv6:
            sorted_list = sorted(ip_results, key=lambda x: ipaddress.IPv6Address(x[0]))
        else:
            sorted_list = sorted(ip_results, key=lambda x: [int(p) for p in x[0].split('.')])
        all_lines, us_lines, nonus_lines, pure_lines = [], [], [], []
        port = self.config['output_settings']['port']
        t = self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        for ip, loc in sorted_list:
            pure_lines.append(ip)
            if is_ipv6:
                line = f"[{ip}]:{port}#{loc}-IPV6"
            else:
                line = f"{ip}:{port}#{loc}"
            all_lines.append(line)
            if self.is_us_location(loc):
                us_lines.append(line)
            else:
                nonus_lines.append(line)
        if self.config['output_settings']['save_all_ips']:
            with open(filename, "w", encoding="utf-8") as fp:
                fp.write(f"# Cloudflare IP\n# 生成时间 {t}\n# {'IPv6' if is_ipv6 else 'IPv4'}\n")
                fp.write(f"# 总数 {len(all_lines)} US:{len(us_lines)} NonUS:{len(nonus_lines)}\n\n")
                fp.write("\n".join(all_lines))
        if self.config['output_settings'].get("save_pure_ip"):
            with open(pure_filename, "w", encoding="utf-8") as fp:
                fp.write("\n".join(pure_lines))
        print(f'💾 {filename} | 总数 {len(all_lines)} US:{len(us_lines)} NonUS:{len(nonus_lines)}')
        return us_lines, nonus_lines

    def save_non_us_ips(self, nonus_v4, nonus_v6):
        if not nonus_v4 and not nonus_v6:
            return
        if not self.config['output_settings']['save_non_us_separately']:
            return
        t = self.get_beijing_time().strftime("%Y%m%d_%H%M%S")
        folder = self.config['output_settings']['non_us_folder']
        fn = f"{folder}/non_us_ips_{t}.txt"
        with open(fn, "w", encoding="utf-8") as fp:
            fp.write(f"# Non-US Cloudflare IP\n# {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}\n")
            fp.write(f"# v4:{len(nonus_v4)} v6:{len(nonus_v6)}\n\n")
            if nonus_v4:
                fp.write("# IPv4\n" + "\n".join(nonus_v4) + "\n\n")
            if nonus_v6:
                fp.write("# IPv6\n" + "\n".join(nonus_v6))
        print(f'💾 非美国 IP: {fn}')
        return fn

    def verify_results(self):
        out = self.config['output_settings']
        print("\n🔍 文件校验")
        for f in [out['ipv4_filename'], out['ipv6_filename']]:
            if os.path.exists(f):
                with open(f, "r", encoding="utf-8") as fp:
                    lines = [l.strip() for l in fp if l.strip() and not l.startswith("#")]
                print(f"📄 {f} : {len(lines)} 条有效")

    def test_geo_api(self):
        if not self.config['location_settings']['enable_location_query']:
            print("ℹ️ 地理位置查询关闭")
            return
        test_ips = ["1.1.1.1", "8.8.8.8", "162.159.58.65"]
        print("🧪 测试地理接口")
        for ip in test_ips:
            loc, ok = self.get_location(ip)
            print(f"{'✅' if ok else '❌'} {ip} -> {loc}")
            time.sleep(0.5)

    def print_config_summary(self):
        print("\n📋 配置摘要")
        print(f"  • 数据源 {len(self.urls)}")
        print(f"  • 地理位置查询 {'开启' if self.config['location_settings']['enable_location_query'] else '关闭'}")
        print(f"  • CF官方段过滤 {'开启' if self.config['filter_settings']['filter_to_cf_range'] else '关闭'}")
        print(f"  • trace 预检 v4: {self.config['filter_settings']['enable_trace_check_v4']}, v6: {self.config['filter_settings']['enable_trace_check_v6']}")
        print(f"  • 纯净IP输出 {'开启' if self.config['output_settings'].get('save_pure_ip') else '关闭'}")

    def main(self):
        print("=" * 50)
        print("🌐 Cloudflare IP地址收集器 v3.1【修复完整版】")
        print("=" * 50)
        print(f"🕐 {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        self.print_config_summary()
        self.ensure_folders()
        print("\n" + "=" * 30)
        self.test_geo_api()
        print("\n" + "=" * 30)
        self.clean_old_files()
        v4_set, v6_set = self.process_urls_parallel()
        print(f"\n🎉 初步收集: IPv4 {len(v4_set)} | IPv6 {len(v6_set)}")

        trace_v4 = self.run_trace_filter(v4_set, is_v6=False)
        trace_v6 = self.run_trace_filter(v6_set, is_v6=True)

        nonus_v4, nonus_v6 = [], []
        out_cfg = self.config['output_settings']
        if trace_v4:
            res_v4 = self.query_ips_parallel(trace_v4, False)
            _, nonus_v4 = self.save_results_with_location(res_v4, out_cfg['ipv4_filename'], out_cfg['pure_ipv4'], False)
        if trace_v6:
            res_v6 = self.query_ips_parallel(trace_v6, True)
            _, nonus_v6 = self.save_results_with_location(res_v6, out_cfg['ipv6_filename'], out_cfg['pure_ipv6'], True)
        self.save_non_us_ips(nonus_v4, nonus_v6)
        self.verify_results()
        print("\n" + "=" * 50)
        print("🎊 全部任务完成")
        print(f"🕐 {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

if __name__ == "__main__":
    try:
        collector = CFIPCollector('urls.json', 'config.json')
        collector.main()
    except KeyboardInterrupt:
        print("\n❌ 用户中断")
    except Exception:
        print("\n💥 致命异常")
        traceback.print_exc()
