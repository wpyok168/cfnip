import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    'https://raw.githubusercontent.com/hubbylei/bestcf/refs/heads/main/bestcf.txt'
]

# 改进的IP地址正则表达式
ipv4_pattern = r'\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
ipv6_pattern = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'

# 请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def clean_old_files():
    """清理旧文件"""
    for filename in ['ip.txt', 'ipv6.txt']:
        if os.path.exists(filename):
            os.remove(filename)
            print(f'已删除旧文件: {filename}')

def fetch_url(url):
    """获取URL内容"""
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f'请求 {url} 失败: {e}')
        return None

def extract_ips_from_text(text):
    """从文本中提取IP地址"""
    ipv4_matches = re.findall(ipv4_pattern, text)
    ipv6_matches = re.findall(ipv6_pattern, text)
    
    valid_ipv4 = set()
    valid_ipv6 = set()
    
    # 验证IPv4地址
    for ip in ipv4_matches:
        try:
            if isinstance(ip, tuple):  # 如果匹配到分组
                ip_str = '.'.join(ip)
            else:
                ip_str = ip
            ipaddress.IPv4Address(ip_str)
            valid_ipv4.add(ip_str)
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    # 验证IPv6地址
    for ip in ipv6_matches:
        try:
            ip_obj = ipaddress.IPv6Address(ip)
            valid_ipv6.add(ip_obj.compressed.lower())
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    return valid_ipv4, valid_ipv6

def get_country_code_safe(ip, max_retries=3):
    """安全地获取IP的国家代码，使用新的API接口"""
    for attempt in range(max_retries):
        try:
            url = f'https://api.mir6.com/api/ip_json?ip={ip}&lang=en'
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                # 处理JSON解析
                try:
                    data = resp.json()
                    
                    # 检查API返回状态
                    if data.get('code') == 200:
                        country_code = data.get('data', {}).get('countryCode', 'ZZ')
                        if country_code and country_code != 'ZZ':
                            print(f"✓ {ip} -> {country_code}")
                            return country_code
                        else:
                            print(f"⚠ {ip} -> 未找到国家代码")
                            return 'ZZ'
                    else:
                        print(f"API返回错误: {data.get('msg', 'Unknown error')} for {ip}")
                        time.sleep(2)
                        continue
                        
                except json.JSONDecodeError:
                    print(f"JSON解析错误 for {ip}, 响应: {resp.text[:100]}")
                    time.sleep(2)
                    continue
            elif resp.status_code == 429:
                print(f"API限制，等待10秒... (尝试 {attempt + 1}/{max_retries})")
                time.sleep(10)
            else:
                print(f"API错误 {resp.status_code} for {ip} (尝试 {attempt + 1}/{max_retries})")
                time.sleep(2)
                
        except requests.exceptions.Timeout:
            print(f"查询超时 {ip} (尝试 {attempt + 1}/{max_retries})")
            time.sleep(2)
        except Exception as e:
            print(f"查询异常 {ip}: {e} (尝试 {attempt + 1}/{max_retries})")
            time.sleep(2)
    
    print(f"✗ 无法获取 {ip} 的国家代码")
    return 'ZZ'

def process_urls_parallel(urls, max_workers=5):
    """并行处理URL获取"""
    all_ipv4 = set()
    all_ipv6 = set()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(fetch_url, url): url for url in urls}
        
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                text = future.result()
                if text:
                    ipv4, ipv6 = extract_ips_from_text(text)
                    all_ipv4.update(ipv4)
                    all_ipv6.update(ipv6)
                    print(f'成功处理: {url} (IPv4: {len(ipv4)}, IPv6: {len(ipv6)})')
            except Exception as e:
                print(f'处理 {url} 时出错: {e}')
    
    return all_ipv4, all_ipv6

def save_results_with_country(ip_set, filename, is_ipv6=False):
    """保存结果到文件，确保IP和国家代码正确对应"""
    if not ip_set:
        print(f'未找到有效的{"IPv6" if is_ipv6 else "IPv4"}地址。')
        return
    
    # 排序IP地址
    if is_ipv6:
        sorted_ips = sorted(ip_set)
    else:
        sorted_ips = sorted(ip_set, key=lambda ip: [int(part) for part in ip.split('.')])
    
    results = []
    failed_ips = []
    
    print(f'\n开始查询 {len(sorted_ips)} 个{"IPv6" if is_ipv6 else "IPv4"}地址的国家代码...')
    
    # 逐个查询，确保顺序对应
    for i, ip in enumerate(sorted_ips, 1):
        country_code = get_country_code_safe(ip)
        
        if country_code == 'ZZ':
            failed_ips.append(ip)
        
        if is_ipv6:
            results.append(f"[{ip}]:8443#{country_code}-IPV6")
        else:
            results.append(f"{ip}:8443#{country_code}")
        
        # 进度显示
        if i % 5 == 0 or i == len(sorted_ips):
            print(f'进度: {i}/{len(sorted_ips)} (成功率: {((i - len(failed_ips)) / i * 100):.1f}%)')
        
        # 避免API限制
        time.sleep(0.8)
    
    # 保存结果
    with open(filename, 'w', encoding='utf-8') as file:
        for line in results:
            file.write(line + '\n')
    
    print(f'\n已保存 {len(results)} 个{"IPv6" if is_ipv6 else "IPv4"}地址到 {filename}')
    
    if failed_ips:
        print(f'其中 {len(failed_ips)} 个IP的国家代码查询失败:')
        for ip in failed_ips[:10]:  # 只显示前10个失败的
            print(f'  {ip}')
        if len(failed_ips) > 10:
            print(f'  ... 还有 {len(failed_ips) - 10} 个')

def verify_results():
    """验证结果文件中的IP和国家代码对应关系"""
    for filename in ['ip.txt', 'ipv6.txt']:
        if os.path.exists(filename):
            print(f'\n验证 {filename}:')
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f'总行数: {len(lines)}')
                for i, line in enumerate(lines[:5], 1):  # 只检查前5行
                    print(f'  样例 {i}: {line.strip()}')

def main():
    """主函数"""
    print("开始收集Cloudflare IP地址...")
    clean_old_files()
    
    # 并行获取IP地址
    unique_ipv4, unique_ipv6 = process_urls_parallel(urls)
    
    print(f"\n收集完成: IPv4: {len(unique_ipv4)}个, IPv6: {len(unique_ipv6)}个")
    
    # 保存结果（确保顺序对应）
    if unique_ipv4:
        save_results_with_country(unique_ipv4, 'ip.txt', False)
    
    if unique_ipv6:
        save_results_with_country(unique_ipv6, 'ipv6.txt', True)
    
    # 验证结果
    verify_results()
    
    print("\n任务完成！")

if __name__ == "__main__":
    main()
