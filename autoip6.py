#!/usr/bin/env python3
"""
Cloudflare IP地址收集脚本
自动从多个数据源收集Cloudflare IP地址，并筛选非美国IP
"""

import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 数据源URL列表
URLS = [
    'https://ip.164746.xyz',
    'https://api.uouin.com/cloudflare.html',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt',
    'https://www.wetest.vip/page/cloudflare/address_v6.html',
    'https://www.wetest.vip/page/cloudflare/address_v4.html',
    'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/030101-bestcf.txt',
    'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/main/wetest-cloudflare-v4.txt',
    'https://raw.githubusercontent.com/ZhiXuanWang/cf-speed-dns/main/ipTop10.html',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/main/result.txt',
    'https://raw.githubusercontent.com/camel52zhang/yxip/main/ip.txt',
    'https://raw.githubusercontent.com/Senflare/Senflare-IP/main/IPlist.txt',
    'https://raw.githubusercontent.com/hubbylei/bestcf/main/bestcf.txt',
    'https://raw.githubusercontent.com/XIU2/CloudflareSpeedTest/master/ip.txt',
    'https://www.cloudflare.com/ips-v4',
    'https://www.cloudflare.com/ips-v6'
]

# 正则表达式
IPV4_PATTERN = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
IPV6_PATTERN = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}

# 美国相关关键词
US_KEYWORDS = ['美国', 'United States', 'US', 'USA', '加州', '加利福尼亚', '洛杉矶', 
               'San Jose', 'Chicago', 'New York', 'NY', 'Seattle', 'Dallas', 'Miami']


class CloudflareIPCollector:
    def __init__(self):
        self.stats = {
            'urls_processed': 0,
            'urls_failed': 0,
            'ipv4_collected': 0,
            'ipv6_collected': 0,
            'start_time': None,
            'end_time': None
        }

    def fetch_url(self, url, max_retries=2):
        """获取URL内容"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                response.raise_for_status()
                return response.text
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    print(f"❌ 请求失败: {url} - {str(e)}")
        return None

    def extract_ips(self, text):
        """从文本中提取IP地址"""
        if not text:
            return set(), set()

        ipv4_matches = re.findall(IPV4_PATTERN, text)
        ipv6_matches = re.findall(IPV6_PATTERN, text)

        valid_ipv4 = set()
        valid_ipv6 = set()

        # 处理IPv4
        for ip_match in ipv4_matches:
            try:
                if isinstance(ip_match, tuple):
                    ip_str = '.'.join(ip_match)
                else:
                    ip_str = ip_match

                ip_obj = ipaddress.IPv4Address(ip_str)
                if not (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast):
                    valid_ipv4.add(ip_str)
            except Exception:
                continue

        # 处理IPv6
        for ip in ipv6_matches:
            try:
                ip_obj = ipaddress.IPv6Address(ip)
                if not (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_multicast):
                    valid_ipv6.add(ip_obj.compressed.lower())
            except Exception:
                continue

        return valid_ipv4, valid_ipv6

    def get_location(self, ip):
        """获取IP地理位置（简化版）"""
        try:
            # Cloudflare IP段识别
            if ip.startswith(('1.0.', '1.1.', '104.16.', '104.17.', '104.18.', '104.19.', 
                            '104.20.', '104.21.', '104.22.', '104.23.', '104.24.', '104.25.',
                            '104.26.', '104.27.', '104.28.', '104.29.', '104.30.', '104.31.',
                            '172.64.', '172.65.', '172.66.', '172.67.', '172.68.', '172.69.')):
                return '美国-Cloudflare'
            
            # 其他知名IP段
            elif ip.startswith('8.8.'):
                return '美国-Google'
            elif ip.startswith(('114.', '223.', '180.', '119.', '220.')):
                return '中国'
            elif ip.startswith(('192.168.', '10.', '172.16.', '172.17.', '172.18.', '172.19.')):
                return '本地网络'
            else:
                return '未知'
        except:
            return '未知'

    def is_us_location(self, location):
        """判断是否为美国位置"""
        if location == '未知':
            return False
        
        location_lower = location.lower()
        for keyword in US_KEYWORDS:
            if keyword.lower() in location_lower:
                return True
        return False

    def collect_ips_from_urls(self, urls, max_workers=5):
        """从多个URL收集IP地址"""
        all_ipv4 = set()
        all_ipv6 = set()

        print(f"🌐 开始从 {len(urls)} 个数据源收集IP地址...")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.fetch_url, url): url for url in urls}

            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    text = future.result()
                    if text:
                        ipv4, ipv6 = self.extract_ips(text)
                        all_ipv4.update(ipv4)
                        all_ipv6.update(ipv6)
                        self.stats['urls_processed'] += 1
                        print(f"✅ {url} - IPv4: {len(ipv4)}, IPv6: {len(ipv6)}")
                    else:
                        self.stats['urls_failed'] += 1
                        print(f"❌ {url} - 获取失败")
                except Exception as e:
                    self.stats['urls_failed'] += 1
                    print(f"❌ {url} - 错误: {str(e)}")

        self.stats['ipv4_collected'] = len(all_ipv4)
        self.stats['ipv6_collected'] = len(all_ipv6)

        return all_ipv4, all_ipv6

    def save_ip_files(self, ipv4_set, ipv6_set):
        """保存IP地址到文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 排序IP地址
        ipv4_list = sorted(ipv4_set, key=lambda x: [int(part) for part in x.split('.')])
        ipv6_list = sorted(ipv6_set)

        # 保存所有IPv4
        with open("ip.txt", "w", encoding="utf-8") as f:
            f.write(f"# Cloudflare IPv4 地址列表\n")
            f.write(f"# 生成时间: {timestamp}\n")
            f.write(f"# 总数: {len(ipv4_list)} 个\n")
            f.write(f"# 数据源: {len(URLS)} 个\n")
            f.write(f"# 格式: IP:端口#地理位置\n\n")
            for ip in ipv4_list:
                location = self.get_location(ip)
                f.write(f"{ip}:8443#{location}\n")

        # 保存非美国IPv4
        non_us_ipv4 = []
        for ip in ipv4_list:
            location = self.get_location(ip)
            if not self.is_us_location(location):
                non_us_ipv4.append(f"{ip}:8443#{location}")

        with open("non_us_ip.txt", "w", encoding="utf-8") as f:
            f.write(f"# 非美国 Cloudflare IPv4 地址列表\n")
            f.write(f"# 生成时间: {timestamp}\n")
            f.write(f"# 总数: {len(non_us_ipv4)} 个\n")
            f.write(f"# 格式: IP:端口#地理位置\n\n")
            for line in non_us_ipv4:
                f.write(f"{line}\n")

        # 保存所有IPv6
        with open("ipv6.txt", "w", encoding="utf-8") as f:
            f.write(f"# Cloudflare IPv6 地址列表\n")
            f.write(f"# 生成时间: {timestamp}\n")
            f.write(f"# 总数: {len(ipv6_list)} 个\n")
            f.write(f"# 数据源: {len(URLS)} 个\n")
            f.write(f"# 格式: [IP]:端口#地理位置\n\n")
            for ip in ipv6_list:
                location = self.get_location(ip)
                f.write(f"[{ip}]:8443#{location}\n")

        # 保存非美国IPv6
        non_us_ipv6 = []
        for ip in ipv6_list:
            location = self.get_location(ip)
            if not self.is_us_location(location):
                non_us_ipv6.append(f"[{ip}]:8443#{location}")

        with open("non_us_ipv6.txt", "w", encoding="utf-8") as f:
            f.write(f"# 非美国 Cloudflare IPv6 地址列表\n")
            f.write(f"# 生成时间: {timestamp}\n")
            f.write(f"# 总数: {len(non_us_ipv6)} 个\n")
            f.write(f"# 格式: [IP]:端口#地理位置\n\n")
            for line in non_us_ipv6:
                f.write(f"{line}\n")

        return len(ipv4_list), len(ipv6_list), len(non_us_ipv4), len(non_us_ipv6)

    def create_fallback_files(self):
        """创建备用IP文件"""
        print("⚠️  使用备用IP数据...")
        
        # 基础Cloudflare IP
        fallback_ipv4 = {
            "1.1.1.1", "1.0.0.1", "104.16.0.1", "104.16.1.1", "104.17.0.1",
            "172.64.0.1", "172.65.0.1", "162.159.36.1", "162.159.46.1",
            "188.114.96.1", "188.114.97.1", "198.41.128.1", "198.41.129.1"
        }
        
        fallback_ipv6 = {
            "2606:4700:4700::1111", "2606:4700:4700::1001",
            "2606:4700:4700::1112", "2606:4700:4700::1002",
            "2606:4700:4700::1113", "2606:4700:4700::1003",
            "2a06:98c0::1", "2a06:98c0::2", "2a06:98c1::1", "2a06:98c1::2"
        }
        
        return self.save_ip_files(fallback_ipv4, fallback_ipv6)

    def print_stats(self):
        """打印统计信息"""
        print(f"\n📊 收集统计:")
        print(f"  ✅ 成功处理: {self.stats['urls_processed']} 个数据源")
        print(f"  ❌ 处理失败: {self.stats['urls_failed']} 个数据源")
        print(f"  📧 IPv4地址: {self.stats['ipv4_collected']} 个")
        print(f"  📧 IPv6地址: {self.stats['ipv6_collected']} 个")
        
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            print(f"  ⏱️  总耗时: {duration:.2f} 秒")

    def run(self):
        """主运行函数"""
        self.stats['start_time'] = time.time()
        print("🚀 Cloudflare IP地址收集开始...")
        print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        try:
            # 收集IP地址
            ipv4_set, ipv6_set = self.collect_ips_from_urls(URLS)
            
            # 检查收集结果
            if len(ipv4_set) < 10 or len(ipv6_set) < 5:
                print("⚠️  收集到的IP数量较少，使用备用数据...")
                ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = self.create_fallback_files()
            else:
                # 保存文件
                ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = self.save_ip_files(ipv4_set, ipv6_set)

            self.stats['end_time'] = time.time()
            
            # 最终统计
            print(f"\n🎉 任务完成!")
            print(f"📁 生成文件:")
            print(f"  ✅ ip.txt: {ipv4_count} 个IPv4地址")
            print(f"  ✅ ipv6.txt: {ipv6_count} 个IPv6地址") 
            print(f"  ✅ non_us_ip.txt: {non_us_ipv4_count} 个非美国IPv4地址")
            print(f"  ✅ non_us_ipv6.txt: {non_us_ipv6_count} 个非美国IPv6地址")
            
        except Exception as e:
            print(f"❌ 发生错误: {str(e)}")
            self.create_fallback_files()
            return False

        return True


def main():
    """主函数"""
    collector = CloudflareIPCollector()
    success = collector.run()
    collector.print_stats()
    
    if success:
        print(f"\n📅 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("✅ 脚本执行成功!")
    else:
        print("❌ 脚本执行失败!")
        exit(1)


if __name__ == "__main__":
    main()
