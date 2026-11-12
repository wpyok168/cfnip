#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare IP 收集器｜终极融合版
单方案：TLS RealPing + cdn-cgi/trace
特性：扁平化配置 + 循环防半包 TLS 探测 + 外部配置文件 + IPv6 空文件保底
"""
import argparse
import requests
import re
import os
import time
import random
import ipaddress
import json
import traceback
import socket
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime, timezone, timedelta

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.7 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
]

# ===================== 全局默认配置 =====================
CFG = {
    "request": {
        "timeout": 10,
        "retry_times": 2,
        "retry_delay": 2,
        "geo_delay": 0.2,
        "trace_timeout": 7,
        "trace_random_delay": [0.4, 1.3],
        "max_workers_url": 10,
        "max_workers_ipv4": 10,
        "max_workers_ipv6": 6,
        "max_workers_trace": 3,
    },
    "trace": {
        "sni": "www.wetest.vip",
        "port": 443,
        "enable_v4": True,
        "enable_v6": False,
    },
    "output": {
        "ipv4_filename": "ip.txt",
        "ipv6_filename": "ipv6.txt",
        "pure_ipv4": "pure_v4.txt",
        "pure_ipv6": "pure_v6.txt",
        "non_us_folder": "non_us_ips",
        "port": 8443,
        "save_all_ips": True,
        "save_non_us_separately": True,
        "save_pure_ip": True,
    },
    "geo": {
        "baidu_api_url": "https://opendata.baidu.com/api.php",
        "fallback_api": "https://api.ip.sb/geoip/",
        "us_keywords": ["美国", "United States", "US", "USA"],
        "enable": True,
        "use_cache": True,
    },
    "filter": {
        "remove_private_ips": True,
        "remove_duplicates": True,
        "filter_to_cf_range": True,
    },
    "progress": {
        "show_progress": True,
        "progress_interval": 10,
    }
}
# =======================================================


class CFIPCollector:
    def __init__(self, urls_config="urls.json", main_config="config.json"):
        self.cfg = CFG
        self.beijing_tz = timezone(timedelta(hours=8))
        self.cache = dict()
        self.load_urls_config(urls_config)
        self.load_main_config(main_config)
        self.setup_global_variables()
        print("🌐 Cloudflare IP 收集器｜终极融合版")

    def get_beijing_time(self):
        return datetime.now(self.beijing_tz)

    def _github_blob_to_raw(self, url: str) -> str:
        if "github.com" in url and "/blob/" in url:
            return url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
        return url

    def load_urls_config(self, config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_list = data.get("url_sources", [])
            self.urls = [self._github_blob_to_raw(u.strip()) for u in raw_list if u.strip()]
            print(f"✅ 已加载 {len(self.urls)} 个数据源")
        except Exception:
            print("ℹ️ 未找到 urls.json，使用内置数据源")
            raw_list = [
                "https://ip.164746.xyz",
                "https://api.uouin.com/cloudflare.html",
                "https://addressesapi.090227.xyz/CloudFlareYes",
                "https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt",
                "https://www.wetest.vip/page/cloudflare/address_v6.html",
                "https://www.wetest.vip/page/cloudflare/address_v4.html",
                "https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/030101-bestcf.txt",
                "https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/wetest-cloudflare-v4.txt",
                "https://raw.githubusercontent.com/ZhiXuanWang/cf-speed-dns/main/ipTop10.html",
                "https://raw.githubusercontent.com/gslege/CloudflareIP/main/JP.txt",
                "https://raw.githubusercontent.com/gslege/CloudflareIP/main/DE.txt",
                "https://raw.githubusercontent.com/gslege/CloudflareIP/main/NL.txt",
                "https://raw.githubusercontent.com/gslege/CloudflareIP/main/SG.txt",
                "https://raw.githubusercontent.com/gslege/CloudflareIP/main/US.txt",
                "https://raw.githubusercontent.com/camel52zhang/yxip/main/ip.txt",
                "https://raw.githubusercontent.com/hubbylei/bestcf/main/bestcf.txt",
                "https://raw.githubusercontent.com/minghe168/cfip-auto/main/full_ips.txt",
                "https://raw.githubusercontent.com/yuanxiawan/cfipv4db/main/cfip.txt",
                "https://raw.githubusercontent.com/nyoungo/bestIp/main/best_ips.txt",
                "https://www.wetest.vip/page/cloudflare/address_v4.html",
            ]
            self.urls = [self._github_blob_to_raw(u.strip()) for u in raw_list if u.strip()]

    def load_main_config(self, config_file):
        try:
            with open(config_file, "r", encoding="utf-8") as f:
                text = f.read()
                text = re.sub(r"//.*", "", text)
                user_cfg = json.loads(text)
                for k, v in user_cfg.items():
                    if k in self.cfg and isinstance(v, dict):
                        self.cfg[k].update(v)
                    else:
                        self.cfg[k] = v
            print(f"✅ 已合并外部配置：{config_file}")
        except Exception:
            pass

    def setup_global_variables(self):
        self.ipv4_pattern = re.compile(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
            r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
        )
        self.ipv6_pattern = re.compile(
            r"\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}|"
            r"(?:[0-9a-fA-F]{1,4}:){1,7}:|"
            r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|"
            r"(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|"
            r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|"
            r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|"
            r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|"
            r"[0-9a-fA-F]{1,4}:(?::[0-9a-fA-F]{1,4}){1,6}|"
            r":(?::[0-9a-fA-F]{1,4}){1,7}|"
            r"::(?:ffff(?::0{1,4}){0,1}:){0,1}"
            r"(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}"
            r"(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\b"
        )
        self.headers = {
            "User-Agent": random.choice(UA_POOL),
            "Accept": "application/json",
        }
        self.progress_lock = threading.Lock()
        self.completed_count = 0
        self.success_count = 0
        self.total_count = 0

        self.cf_v4_nets = [
            ipaddress.IPv4Network(p)
            for p in [
                "103.21.244.0/22",
                "103.22.200.0/22",
                "103.31.4.0/22",
                "104.16.0.0/12",
                "108.162.192.0/18",
                "131.0.72.0/22",
                "141.101.64.0/18",
                "162.158.0.0/15",
                "172.64.0.0/13",
                "185.199.108.0/22",
                "188.114.96.0/20",
                "190.93.240.0/20",
                "197.234.240.0/22",
                "198.41.128.0/17",
            ]
        ]
        self.cf_v6_nets = [
            ipaddress.IPv6Network(p)
            for p in [
                "2400:cb00::/32",
                "2606:4700::/32",
                "2803:f800::/32",
                "2405:b500::/32",
                "2405:8100::/32",
                "2a06:98c0::/29",
                "2c0f:f248::/32",
            ]
        ]

    def is_ip_in_cf_range(self, ip_obj):
        if isinstance(ip_obj, ipaddress.IPv4Address):
            return any(ip_obj in net for net in self.cf_v4_nets)
        return any(ip_obj in net for net in self.cf_v6_nets)

    def real_connection_check(self, ip: str, sni: str, port: int = 443, timeout: int = 5):
        try:
            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            sock = socket.create_connection((ip, port), timeout=timeout)
            with sock:
                with context.wrap_socket(sock, server_hostname=sni) as ssock:
                    req = (
                        f"GET / HTTP/1.1\r\n"
                        f"Host: {sni}\r\n"
                        f"User-Agent: Mozilla/5.0\r\n"
                        f"Connection: close\r\n\r\n"
                    )
                    ssock.sendall(req.encode("utf-8"))
                    buf = b""
                    while len(buf) < 1024:
                        chunk = ssock.recv(128)
                        if not chunk:
                            break
                        buf += chunk
                        if b"HTTP/" in buf:
                            break
                    if not buf:
                        return False
                    if b"HTTP/1.1" in buf or b"HTTP/1.0" in buf:
                        return True
            return False
        except Exception:
            return False

    def fetch_trace_loc(self, ip: str, is_v6: bool, timeout: int = 5):
        try:
            headers = {"User-Agent": random.choice(UA_POOL)}
            if is_v6:
                url = f"https://[{ip}]/cdn-cgi/trace"
            else:
                url = f"https://{ip}/cdn-cgi/trace"
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200 and "loc=" in resp.text:
                m = re.search(r"loc=([A-Z]{2})", resp.text)
                return m.group(1) if m else None
            return None
        except Exception:
            return None

    def trace_check(self, ip: str, is_v6: bool):
        time.sleep(random.uniform(*self.cfg["request"]["trace_random_delay"]))
        ok_tls = self.real_connection_check(
            ip,
            self.cfg["trace"]["sni"],
            port=self.cfg["trace"]["port"],
            timeout=self.cfg["request"]["trace_timeout"]
        )
        if not ok_tls:
            return False, ""
        cc = self.fetch_trace_loc(ip, is_v6, timeout=3)
        return True, cc or ""

    def run_trace_filter(self, ip_set, is_v6: bool):
        if is_v6 and not self.cfg["trace"]["enable_v6"]:
            return [(ip, None) for ip in ip_set]
        if not is_v6 and not self.cfg["trace"]["enable_v4"]:
            return [(ip, None) for ip in ip_set]

        print(f"\n🔎 TLS RealPing 预检，共 {len(ip_set)} 个 {'IPv6' if is_v6 else 'IPv4'}")
        passed = []
        with ThreadPoolExecutor(max_workers=self.cfg["request"]["max_workers_trace"]) as executor:
            futs = {executor.submit(self.trace_check, ip, is_v6): ip for ip in ip_set}
            for f in as_completed(futs):
                ip = futs[f]
                ok, cc = f.result()
                if ok:
                    passed.append((ip, cc))
        print(f"✅ RealPing 通过：{len(passed)} / {len(ip_set)}")
        if not passed:
            print("⚠️ 预检全部失败，触发降级，保留全部候选 IP，避免空文件")
            return [(ip, None) for ip in ip_set]
        return passed

    def ensure_folders(self):
        folder = self.cfg["output"]["non_us_folder"]
        if not os.path.exists(folder):
            os.makedirs(folder)

    def clean_old_files(self):
        out = self.cfg["output"]
        files = [out["ipv4_filename"], out["ipv6_filename"]]
        if out["save_pure_ip"]:
            files += [out["pure_ipv4"], out["pure_ipv6"]]
        for f in files:
            if os.path.exists(f):
                os.remove(f)

    def fetch_url(self, url):
        req = self.cfg["request"]
        for attempt in range(req["retry_times"] + 1):
            try:
                resp = requests.get(
                    url,
                    headers={"User-Agent": random.choice(UA_POOL)},
                    timeout=req["timeout"]
                )
                resp.raise_for_status()
                return resp.text
            except requests.exceptions.RequestException:
                if attempt < req["retry_times"]:
                    time.sleep(req["retry_delay"])
        return None

    def extract_ips_from_text(self, text):
        valid_ipv4, valid_ipv6 = set(), set()
        flt = self.cfg["filter"]
        for s in self.ipv4_pattern.findall(text):
            try:
                ip = ipaddress.IPv4Address(s)
                if flt["remove_private_ips"] and ip.is_private:
                    continue
                if flt["filter_to_cf_range"] and not self.is_ip_in_cf_range(ip):
                    continue
                valid_ipv4.add(str(ip))
            except Exception:
                pass
        for s in self.ipv6_pattern.findall(text):
            try:
                ip = ipaddress.IPv6Address(s)
                if flt["remove_private_ips"] and ip.is_private:
                    continue
                if flt["filter_to_cf_range"] and not self.is_ip_in_cf_range(ip):
                    continue
                valid_ipv6.add(ip.compressed.lower())
            except Exception:
                pass
        return valid_ipv4, valid_ipv6

    def get_location(self, ip, pre_cc=None):
        geo = self.cfg["geo"]
        if pre_cc and pre_cc != "UNKNOWN":
            name_map = {
                "JP": "日本",
                "SG": "新加坡",
                "DE": "德国",
                "NL": "荷兰",
                "US": "美国",
                "KR": "韩国",
                "HK": "中国香港",
                "TW": "中国台湾"
            }
            self.cache[ip] = name_map.get(pre_cc, pre_cc)
            return self.cache[ip], True
        if not geo["enable"]:
            return "未知", False
        if geo["use_cache"] and ip in self.cache:
            return self.cache[ip], True

        try:
            url = f"{geo['baidu_api_url']}?co=&resource_id=6006&oe=utf8&query={ip}"
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
            r = requests.get(geo["fallback_api"] + ip, headers=self.headers, timeout=5)
            j = r.json()
            loc = j.get("country", "未知")
            self.cache[ip] = loc
            return loc, True
        except Exception:
            pass
        return "未知", False

    def process_single_ip(self, ip, pre_cc):
        time.sleep(self.cfg["request"]["geo_delay"])
        loc, ok = self.get_location(ip, pre_cc)
        if self.cfg["progress"]["show_progress"]:
            with self.progress_lock:
                self.completed_count += 1
                if ok:
                    self.success_count += 1
                if (
                    self.completed_count % self.cfg["progress"]["progress_interval"] == 0
                    or self.completed_count == self.total_count
                ):
                    rate = (
                        (self.success_count / self.completed_count * 100)
                        if self.completed_count
                        else 0
                    )
                    print(f"📊 进度：{self.completed_count}/{self.total_count}，成功率 {rate:.1f}%")
        return ip, loc, ok

    def process_urls_parallel(self):
        all_ipv4, all_ipv6 = set(), set()
        print(f"🚀 并行拉取 {len(self.urls)} 个数据源")
        with ThreadPoolExecutor(max_workers=self.cfg["request"]["max_workers_url"]) as executor:
            fu = {executor.submit(self.fetch_url, u): u for u in self.urls}
            for f in as_completed(fu):
                txt = f.result()
                if txt:
                    v4, v6 = self.extract_ips_from_text(txt)
                    all_ipv4.update(v4)
                    all_ipv6.update(v6)
        return all_ipv4, all_ipv6

    def query_ips_parallel(self, trace_passed_list, is_ipv6=False):
        self.completed_count = self.success_count = 0
        self.total_count = len(trace_passed_list)
        if not trace_passed_list:
            return []
        workers = self.cfg["request"]["max_workers_ipv6" if is_ipv6 else "max_workers_ipv4"]
        label = "IPv6" if is_ipv6 else "IPv4"
        print(f"🌍 查询 {self.total_count} 个 {label} 地理位置")
        res = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            fi = {
                executor.submit(self.process_single_ip, ip, pre_cc): (ip, pre_cc)
                for ip, pre_cc in trace_passed_list
            }
            for f in as_completed(fi):
                ip, pre_cc = fi[f]
                try:
                    ip_out, loc, _ = f.result()
                    res.append((ip_out, loc))
                except Exception:
                    res.append((ip, "未知"))
        print(f"✅ {label} 查询完成，成功 {self.success_count}/{self.total_count}")
        return res

    def is_us_location(self, location):
        if location == "未知":
            return False
        return any(k.lower() in location.lower() for k in self.cfg["geo"]["us_keywords"])

    def save_results_with_location(self, ip_results, filename, pure_filename, is_ipv6=False):
        if not ip_results:
            with open(filename, "w", encoding="utf-8") as fp:
                fp.write(f"# Cloudflare IP\n# 本次未收集到有效 {'IPv6' if is_ipv6 else 'IPv4'} 地址\n")
            if self.cfg["output"]["save_pure_ip"]:
                open(pure_filename, "w").close()
            return [], []

        sorted_list = sorted(
            ip_results,
            key=lambda x: ipaddress.IPv6Address(x[0])
            if is_ipv6
            else [int(p) for p in x[0].split(".")]
        )
        all_lines, us_lines, nonus_lines, pure_lines = [], [], [], []
        port = self.cfg["output"]["port"]
        t = self.get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")
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

        with open(filename, "w", encoding="utf-8") as fp:
            fp.write(
                f"# Cloudflare IP\n"
                f"# 生成时间 {t}\n"
                f"# {'IPv6' if is_ipv6 else 'IPv4'}\n"
                f"# 总数 {len(all_lines)} US:{len(us_lines)} NonUS:{len(nonus_lines)}\n\n"
            )
            fp.write("\n".join(all_lines))
        if self.cfg["output"]["save_pure_ip"]:
            with open(pure_filename, "w", encoding="utf-8") as fp:
                fp.write("\n".join(pure_lines))
        print(f"💾 {filename} | 总数 {len(all_lines)} US:{len(us_lines)} NonUS:{len(nonus_lines)}")
        return us_lines, nonus_lines

    def save_non_us_ips(self, nonus_v4, nonus_v6):
        if not nonus_v4 and not nonus_v6:
            return
        t = self.get_beijing_time().strftime("%Y%m%d_%H%M%S")
        folder = self.cfg["output"]["non_us_folder"]
        fn = f"{folder}/non_us_ips_{t}.txt"
        with open(fn, "w", encoding="utf-8") as fp:
            fp.write(
                f"# Non-US Cloudflare IP\n"
                f"# {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"# v4:{len(nonus_v4)} v6:{len(nonus_v6)}\n\n"
            )
            if nonus_v4:
                fp.write("# IPv4\n" + "\n".join(nonus_v4) + "\n\n")
            if nonus_v6:
                fp.write("# IPv6\n" + "\n".join(nonus_v6))
        print(f"💾 非美国 IP 文件：{fn}")

    def print_config_summary(self):
        print("\n📋 当前配置摘要")
        print(f"  • TLS 预检 SNI：{self.cfg['trace']['sni']}")
        print(f"  • IPv4 RealPing：{'开启' if self.cfg['trace']['enable_v4'] else '关闭'}")
        print(f"  • IPv6 RealPing：{'开启' if self.cfg['trace']['enable_v6'] else '关闭'}")
        print(f"  • 地理位置查询：{'开启' if self.cfg['geo']['enable'] else '关闭'}")
        print(f"  • 纯净 IP 输出：{'开启' if self.cfg['output']['save_pure_ip'] else '关闭'}")

    def test_geo_api(self):
        if not self.cfg["geo"]["enable"]:
            print("ℹ️ 地理位置查询已关闭")
            return
        test_ips = ["1.1.1.1", "8.8.8.8", "162.159.58.65"]
        print("\n🧪 地理接口预测试")
        for ip in test_ips:
            loc, ok = self.get_location(ip)
            print(f"{'✅' if ok else '❌'} {ip} -> {loc}")
            time.sleep(0.4)

    def main(self):
        print("=" * 50)
        print("🌐 Cloudflare IP 收集器｜终极融合版")
        print("=" * 50)
        print(f"🕐 {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        self.print_config_summary()
        self.test_geo_api()
        print("\n" + "=" * 30)

        self.ensure_folders()
        self.clean_old_files()
        v4_set, v6_set = self.process_urls_parallel()
        print(f"\n🎉 初步收集：IPv4 {len(v4_set)} | IPv6 {len(v6_set)}")

        trace_v4 = self.run_trace_filter(v4_set, is_v6=False)
        trace_v6 = self.run_trace_filter(v6_set, is_v6=True)

        nonus_v4, nonus_v6 = [], []
        res_v4 = self.query_ips_parallel(trace_v4, False)
        _, nonus_v4 = self.save_results_with_location(
            res_v4,
            self.cfg["output"]["ipv4_filename"],
            self.cfg["output"]["pure_ipv4"],
            False
        )

        res_v6 = self.query_ips_parallel(trace_v6, True)
        _, nonus_v6 = self.save_results_with_location(
            res_v6,
            self.cfg["output"]["ipv6_filename"],
            self.cfg["output"]["pure_ipv6"],
            True
        )

        self.save_non_us_ips(nonus_v4, nonus_v6)
        print("\n🎊 全部任务完成")
        print("=" * 50)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--urls", default="urls.json")
    parser.add_argument("--config", default="config.json", help="主配置文件")
    args = parser.parse_args()
    try:
        collector = CFIPCollector(urls_config=args.urls, main_config=args.config)
        collector.main()
    except KeyboardInterrupt:
        print("\n❌ 用户中断")
    except Exception:
        traceback.print_exc()
