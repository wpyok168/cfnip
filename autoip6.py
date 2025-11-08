import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

# 目标URL列表
urls = [
    'https://ip.164746.xyz', 
    'https://api.uouin.com/cloudflare.html',
    'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
    'https://addressesapi.090227.xyz/CloudFlareYes',
    'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt',
    'https://www.wetest.vip/page/cloudflare/address_v6.html',
    'https://www.wetest.vip/page/cloudflare/address_v4.html',
    'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/refs/heads/main/030101-bestcf.txt',
    'https://raw.githubusercontent.com/crow1874/CF-DNS-Clone/refs/heads/main/wetest-cloudflare-v4.txt',
    'https://raw.githubusercontent.com/ZhiXuanWang/cf-speed-dns/refs/heads/main/ipTop10.html',
    'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/result.txt',
    'https://raw.githubusercontent.com/camel52zhang/yxip/refs/heads/main/ip.txt',
    'https://raw.githubusercontent.com/Senflare/Senflare-IP/refs/heads/main/IPlist.txt',
    'https://raw.githubusercontent.com/hubbylei/bestcf/refs/heads/main/bestcf.txt',
    # 新增备用数据源
    'https://raw.githubusercontent.com/XIU2/CloudflareSpeedTest/master/ip.txt',
    'https://www.cloudflare.com/ips-v4',
    'https://www.cloudflare.com/ips-v6'
]

# IP地址正则表达式
ipv4_pattern = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
ipv6_pattern = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

# 美国相关关键词
us_keywords = ['美国', 'United States', 'US', 'USA', '加州', '加利福尼亚', '洛杉矶', 'San Jose', 'Chicago', 'New York', 'NY', 'Seattle']

def fetch_url_with_retry(url, max_retries=2):
    """带重试机制的URL获取"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                time.sleep(1)
    return None

def extract_ips_from_text(text):
    """从文本中提取IP地址"""
    if not text:
        return set(), set()
    
    ipv4_matches = re.findall(ipv4_pattern, text)
    ipv6_matches = re.findall(ipv6_pattern, text)
    
    valid_ipv4 = set()
    valid_ipv6 = set()
    
    # 验证IPv4地址
    for ip_match in ipv4_matches:
        try:
            if isinstance(ip_match, tuple):
                ip_str = '.'.join(ip_match)
            else:
                ip_str = ip_match
            
            ip_obj = ipaddress.IPv4Address(ip_str)
            if not ip_obj.is_private and not ip_obj.is_loopback:
                valid_ipv4.add(ip_str)
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    # 验证IPv6地址
    for ip in ipv6_matches:
        try:
            ip_obj = ipaddress.IPv6Address(ip)
            if not ip_obj.is_private and not ip_obj.is_loopback:
                valid_ipv6.add(ip_obj.compressed.lower())
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    return valid_ipv4, valid_ipv6

def get_location_simple(ip):
    """简化的地理位置查询（避免API限制）"""
    # 这里使用简化的逻辑，避免频繁调用百度API
    # 在实际使用中，你可以根据需要实现更复杂的地理位置查询
    if ip.startswith(('1.0.', '1.1.')):
        return '美国-Cloudflare'
    elif ip.startswith('8.8.'):
        return '美国-Google'
    elif ip.startswith(('114.', '223.', '180.')):
        return '中国'
    elif ip.startswith(('192.', '10.', '172.')):
        return '本地网络'
    else:
        return '未知'

def is_us_location(location):
    """判断是否为美国位置"""
    if location == '未知':
        return False
    
    location_lower = location.lower()
    for keyword in us_keywords:
        if keyword.lower() in location_lower:
            return True
    return False

def process_urls_parallel(urls, max_workers=5):
    """并行处理URL获取"""
    all_ipv4 = set()
    all_ipv6 = set()
    successful_urls = 0
    
    print(f"开始从 {len(urls)} 个数据源收集IP地址...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_url_with_retry, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                text = future.result()
                if text:
                    ipv4, ipv6 = extract_ips_from_text(text)
                    all_ipv4.update(ipv4)
                    all_ipv6.update(ipv6)
                    successful_urls += 1
                    print(f'✓ 成功处理: {url} (IPv4: {len(ipv4)}, IPv6: {len(ipv6)})')
                else:
                    print(f'✗ 获取失败: {url}')
            except Exception as e:
                print(f'✗ 处理 {url} 时出错: {e}')
    
    print(f"\nURL处理完成: 成功 {successful_urls}/{len(urls)} 个数据源")
    return all_ipv4, all_ipv6

def save_ip_files(ipv4_set, ipv6_set):
    """保存IP文件到根目录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 处理IPv4地址
    ipv4_list = sorted(ipv4_set, key=lambda x: [int(part) for part in x.split('.')])
    ipv6_list = sorted(ipv6_set)
    
    # 保存所有IPv4地址
    with open("ip.txt", "w", encoding="utf-8") as f:
        f.write(f"# Cloudflare IPv4 地址列表\n")
        f.write(f"# 生成时间: {timestamp}\n")
        f.write(f"# 总数: {len(ipv4_list)} 个\n")
        f.write(f"# 来源: {len(urls)} 个数据源\n\n")
        for ip in ipv4_list:
            location = get_location_simple(ip)
            f.write(f"{ip}:8443#{location}\n")
    
    # 保存非美国IPv4地址
    non_us_ipv4 = []
    for ip in ipv4_list:
        location = get_location_simple(ip)
        if not is_us_location(location):
            non_us_ipv4.append(f"{ip}:8443#{location}")
    
    with open("non_us_ip.txt", "w", encoding="utf-8") as f:
        f.write(f"# 非美国 Cloudflare IPv4 地址列表\n")
        f.write(f"# 生成时间: {timestamp}\n")
        f.write(f"# 总数: {len(non_us_ipv4)} 个\n\n")
        for line in non_us_ipv4:
            f.write(f"{line}\n")
    
    # 保存所有IPv6地址
    with open("ipv6.txt", "w", encoding="utf-8") as f:
        f.write(f"# Cloudflare IPv6 地址列表\n")
        f.write(f"# 生成时间: {timestamp}\n")
        f.write(f"# 总数: {len(ipv6_list)} 个\n")
        f.write(f"# 来源: {len(urls)} 个数据源\n\n")
        for ip in ipv6_list:
            location = get_location_simple(ip)
            f.write(f"[{ip}]:8443#{location}\n")
    
    # 保存非美国IPv6地址
    non_us_ipv6 = []
    for ip in ipv6_list:
        location = get_location_simple(ip)
        if not is_us_location(location):
            non_us_ipv6.append(f"[{ip}]:8443#{location}")
    
    with open("non_us_ipv6.txt", "w", encoding="utf-8") as f:
        f.write(f"# 非美国 Cloudflare IPv6 地址列表\n")
        f.write(f"# 生成时间: {timestamp}\n")
        f.write(f"# 总数: {len(non_us_ipv6)} 个\n\n")
        for line in non_us_ipv6:
            f.write(f"{line}\n")
    
    print(f"✅ 文件保存完成:")
    print(f"   - ip.txt: {len(ipv4_list)} 个IPv4地址")
    print(f"   - non_us_ip.txt: {len(non_us_ipv4)} 个非美国IPv4地址")
    print(f"   - ipv6.txt: {len(ipv6_list)} 个IPv6地址")
    print(f"   - non_us_ipv6.txt: {len(non_us_ipv6)} 个非美国IPv6地址")
    
    return len(ipv4_list), len(ipv6_list), len(non_us_ipv4), len(non_us_ipv6)

def create_fallback_files():
    """创建备用IP文件（当数据源不可用时）"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 基础Cloudflare IP地址
    fallback_ipv4 = [
        "1.1.1.1", "1.0.0.1", "162.159.46.1", "162.159.47.1",
        "162.159.44.1", "162.159.45.1", "162.159.48.1", "162.159.49.1",
        "104.16.132.229", "104.16.133.229", "172.64.32.1", "172.64.33.1"
    ]
    
    fallback_ipv6 = [
        "2606:4700:4700::1111", "2606:4700:4700::1001",
        "2606:4700:4700::1112", "2606:4700:4700::1002",
        "2606:4700:4700::1113", "2606:4700:4700::1003"
    ]
    
    ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = save_ip_files(
        set(fallback_ipv4), set(fallback_ipv6)
    )
    
    print("⚠️  使用备用IP数据（数据源不可用）")
    return ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count

def main():
    """主函数"""
    print("🚀 开始收集Cloudflare IP地址...")
    print(f"📅 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # 收集IP地址
        unique_ipv4, unique_ipv6 = process_urls_parallel(urls)
        
        print(f"\n📊 收集统计:")
        print(f"  - IPv4: {len(unique_ipv4)} 个")
        print(f"  - IPv6: {len(unique_ipv6)} 个")
        
        # 如果收集到的IP太少，使用备用方案
        if len(unique_ipv4) < 10 or len(unique_ipv6) < 5:
            print("\n⚠️  收集到的IP数量较少，使用备用方案...")
            ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = create_fallback_files()
        else:
            # 保存IP文件
            ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = save_ip_files(unique_ipv4, unique_ipv6)
        
        # 输出统计信息（用于GitHub Actions）
        print(f"\n📈 最终统计:")
        print(f"  - IPv4总数: {ipv4_count}")
        print(f"  - IPv6总数: {ipv6_count}")
        print(f"  - 非美国IPv4: {non_us_ipv4_count}")
        print(f"  - 非美国IPv6: {non_us_ipv6_count}")
        
    except Exception as e:
        print(f"❌ 发生错误: {e}")
        print("使用备用方案...")
        ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count = create_fallback_files()
    
    print(f"\n🎉 任务完成！")
    print(f"📅 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
