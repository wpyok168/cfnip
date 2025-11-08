import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue

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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://www.baidu.com/'
}

# 全局变量用于进度显示
progress_lock = threading.Lock()
completed_count = 0
total_count = 0
success_count = 0

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

def get_location_from_baidu(ip):
    """从百度API获取IP的地理位置信息"""
    try:
        url = f'https://opendata.baidu.com/api.php?co=&resource_id=6006&oe=utf8&query={ip}&lang=en'
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                
                # 检查百度API返回的status字段
                status = data.get('status')
                if status == '0':  # 百度API成功状态为'0'
                    if data.get('data') and len(data['data']) > 0:
                        location = data['data'][0].get('location', '未知')
                        if location and location != '未知':
                            return location, True
                        else:
                            return '未知', False
                    else:
                        return '未知', False
                else:
                    return '未知', False
                    
            except json.JSONDecodeError:
                return '未知', False
        else:
            return '未知', False
            
    except Exception as e:
        return '未知', False

def process_single_ip(ip):
    """处理单个IP地址查询"""
    global completed_count, success_count
    
    location, success = get_location_from_baidu(ip)
    
    with progress_lock:
        completed_count += 1
        if success:
            success_count += 1
        
        # 每处理10个IP或完成时显示进度
        if completed_count % 10 == 0 or completed_count == total_count:
            success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0
            print(f'进度: {completed_count}/{total_count} (成功率: {success_rate:.1f}%)')
    
    return ip, location, success

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

def query_ips_parallel(ip_set, max_workers=10):
    """并行查询IP地址的地理位置"""
    global completed_count, total_count, success_count
    
    # 重置计数器
    completed_count = 0
    total_count = len(ip_set)
    success_count = 0
    
    if not ip_set:
        return []
    
    print(f'开始并行查询 {total_count} 个IP地址的地理位置...')
    print(f'使用 {max_workers} 个线程同时查询')
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_ip = {executor.submit(process_single_ip, ip): ip for ip in ip_set}
        
        # 收集结果
        for future in as_completed(future_to_ip):
            try:
                ip, location, success = future.result()
                results.append((ip, location))
            except Exception as e:
                ip = future_to_ip[future]
                print(f"处理IP {ip} 时发生异常: {e}")
                results.append((ip, '未知'))
    
    # 最终进度显示
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    print(f'查询完成: 总计 {total_count}, 成功 {success_count}, 成功率: {success_rate:.1f}%')
    
    return results

def save_results_with_location(ip_results, filename, is_ipv6=False):
    """保存结果到文件"""
    if not ip_results:
        print(f'没有要保存的{"IPv6" if is_ipv6 else "IPv4"}地址结果。')
        return
    
    # 按IP地址排序结果
    if is_ipv6:
        sorted_results = sorted(ip_results, key=lambda x: x[0])
    else:
        sorted_results = sorted(ip_results, key=lambda x: [int(part) for part in x[0].split('.')])
    
    results = []
    failed_count = 0
    
    for ip, location in sorted_results:
        if location == '未知':
            failed_count += 1
        
        if is_ipv6:
            results.append(f"[{ip}]:8443#{location}-IPV6")
        else:
            results.append(f"{ip}:8443#{location}")
    
    # 保存结果
    with open(filename, 'w', encoding='utf-8') as file:
        for line in results:
            file.write(line + '\n')
    
    print(f'\n已保存 {len(results)} 个{"IPv6" if is_ipv6 else "IPv4"}地址到 {filename}')
    print(f'成功获取地理位置: {len(results) - failed_count}, 失败: {failed_count}')

def verify_results():
    """验证结果文件中的IP和地理位置对应关系"""
    for filename in ['ip.txt', 'ipv6.txt']:
        if os.path.exists(filename):
            print(f'\n验证 {filename}:')
            with open(filename, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                print(f'总行数: {len(lines)}')
                for i, line in enumerate(lines[:5], 1):
                    print(f'  样例 {i}: {line.strip()}')

def test_baidu_api():
    """测试百度API接口是否正常工作"""
    test_ips = ['8.8.8.8', '1.1.1.1', '162.159.58.65']
    print("测试百度API接口...")
    for ip in test_ips:
        location, success = get_location_from_baidu(ip)
        status = "✓" if success else "✗"
        print(f"{status} 测试 {ip} -> {location}")
        time.sleep(0.5)  # 短暂延迟避免触发限制

def main():
    """主函数"""
    print("开始收集Cloudflare IP地址...")
    
    # 先测试API
    test_baidu_api()
    
    clean_old_files()
    
    # 并行获取IP地址
    print("\n开始从各数据源收集IP地址...")
    unique_ipv4, unique_ipv6 = process_urls_parallel(urls)
    
    print(f"\n收集完成: IPv4: {len(unique_ipv4)}个, IPv6: {len(unique_ipv6)}个")
    
    # 并行查询地理位置并保存结果
    if unique_ipv4:
        print(f"\n开始处理IPv4地址...")
        ipv4_results = query_ips_parallel(unique_ipv4, max_workers=15)  # 增加IPv4查询线程数
        save_results_with_location(ipv4_results, 'ip.txt', False)
    
    if unique_ipv6:
        print(f"\n开始处理IPv6地址...")
        ipv6_results = query_ips_parallel(unique_ipv6, max_workers=10)  # IPv6查询线程数稍少
        save_results_with_location(ipv6_results, 'ipv6.txt', True)
    
    # 验证结果
    verify_results()
    
    print("\n任务完成！")

if __name__ == "__main__":
    main()
