import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
from datetime import datetime

# 目标URL列表 - 更新为更可靠的数据源
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

# 改进的IP地址正则表达式
ipv4_pattern = r'\b(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
ipv6_pattern = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'

# 请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# 全局变量用于进度显示
progress_lock = threading.Lock()
completed_count = 0
total_count = 0
success_count = 0

# 美国相关关键词（用于过滤非美国IP）
us_keywords = ['美国', 'United States', 'US', 'USA', '加州', '加利福尼亚', '洛杉矶', 'San Jose', 'Chicago', 'New York', 'NY', 'Seattle']

def create_output_directory():
    """创建日期时间格式的输出目录"""
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"cf_ips_{current_time}"
    os.makedirs(output_dir, exist_ok=True)
    print(f"创建输出目录: {output_dir}")
    return output_dir

def fetch_url_with_retry(url, max_retries=3):
    """带重试机制的URL获取"""
    for attempt in range(max_retries):
        try:
            print(f"尝试请求 {url} (第 {attempt + 1} 次)...")
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            print(f"成功获取 {url}")
            return response.text
        except requests.exceptions.RequestException as e:
            print(f'请求 {url} 失败 (尝试 {attempt + 1}/{max_retries}): {e}')
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # 递增延迟
            else:
                return None
    return None

def extract_ips_from_text(text):
    """从文本中提取IP地址"""
    if not text:
        return set(), set()
    
    # 改进的IP提取，处理各种格式
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
            
            # 进一步验证IP格式
            ip_obj = ipaddress.IPv4Address(ip_str)
            if not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_multicast:
                valid_ipv4.add(ip_str)
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    # 验证IPv6地址
    for ip in ipv6_matches:
        try:
            ip_obj = ipaddress.IPv6Address(ip)
            if not ip_obj.is_private and not ip_obj.is_loopback and not ip_obj.is_multicast:
                valid_ipv6.add(ip_obj.compressed.lower())
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    print(f"从文本中提取到 IPv4: {len(valid_ipv4)} 个, IPv6: {len(valid_ipv6)} 个")
    return valid_ipv4, valid_ipv6

def get_location_from_baidu(ip):
    """从百度API获取IP的地理位置信息"""
    try:
        url = f'https://opendata.baidu.com/api.php?co=&resource_id=6006&oe=utf8&query={ip}'
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                status = data.get('status')
                if status == '0':  # 百度API成功状态为'0'
                    if data.get('data') and len(data['data']) > 0:
                        location = data['data'][0].get('location', '未知')
                        if location and location != '未知':
                            return location, True
            except json.JSONDecodeError:
                pass
    except Exception as e:
        pass
    
    return '未知', False

def is_us_location(location):
    """判断是否为美国位置"""
    if location == '未知':
        return False
    
    location_lower = location.lower()
    for keyword in us_keywords:
        if keyword.lower() in location_lower:
            return True
    return False

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
            print(f'地理位置查询进度: {completed_count}/{total_count} (成功率: {success_rate:.1f}%)')
    
    return ip, location, success

def process_urls_parallel(urls, max_workers=5):
    """并行处理URL获取"""
    all_ipv4 = set()
    all_ipv6 = set()
    successful_urls = 0
    
    print(f"\n开始从 {len(urls)} 个数据源收集IP地址...")
    
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
                    print(f'✗ 处理失败: {url}')
            except Exception as e:
                print(f'✗ 处理 {url} 时出错: {e}')
    
    print(f"\nURL处理完成: 成功 {successful_urls}/{len(urls)} 个数据源")
    return all_ipv4, all_ipv6

def query_ips_parallel(ip_set, max_workers=10):
    """并行查询IP地址的地理位置"""
    global completed_count, total_count, success_count
    
    # 重置计数器
    completed_count = 0
    total_count = len(ip_set)
    success_count = 0
    
    if not ip_set:
        print("没有IP需要查询地理位置")
        return []
    
    print(f'\n开始并行查询 {total_count} 个IP地址的地理位置...')
    print(f'使用 {max_workers} 个线程同时查询')
    
    results = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_ip = {executor.submit(process_single_ip, ip): ip for ip in ip_set}
        
        # 收集结果
        for future in as_completed(future_to_url):
            try:
                ip, location, success = future.result()
                results.append((ip, location))
            except Exception as e:
                ip = future_to_ip[future]
                print(f"处理IP {ip} 时发生异常: {e}")
                results.append((ip, '未知'))
    
    # 最终进度显示
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    print(f'地理位置查询完成: 总计 {total_count}, 成功 {success_count}, 成功率: {success_rate:.1f}%')
    
    return results

def save_results_with_location(ip_results, filename, is_ipv6=False, output_dir="."):
    """保存结果到文件"""
    if not ip_results:
        print(f'⚠️ 没有要保存的{"IPv6" if is_ipv6 else "IPv4"}地址结果。')
        return [], []
    
    # 按IP地址排序结果
    if is_ipv6:
        sorted_results = sorted(ip_results, key=lambda x: x[0])
    else:
        sorted_results = sorted(ip_results, key=lambda x: [int(part) for part in x[0].split('.')])
    
    all_results = []
    non_us_results = []
    failed_count = 0
    non_us_count = 0
    
    for ip, location in sorted_results:
        if location == '未知':
            failed_count += 1
        
        # 构建结果行
        if is_ipv6:
            result_line = f"[{ip}]:8443#{location}"
        else:
            result_line = f"{ip}:8443#{location}"
        
        all_results.append(result_line)
        
        # 如果是非美国IP，添加到非美国列表
        if not is_us_location(location):
            non_us_results.append(result_line)
            non_us_count += 1
    
    # 保存所有结果
    all_filepath = os.path.join(output_dir, filename)
    with open(all_filepath, 'w', encoding='utf-8') as file:
        for line in all_results:
            file.write(line + '\n')
    
    # 保存非美国结果
    non_us_filename = f"non_us_{filename}"
    non_us_filepath = os.path.join(output_dir, non_us_filename)
    with open(non_us_filepath, 'w', encoding='utf-8') as file:
        for line in non_us_results:
            file.write(line + '\n')
    
    print(f'\n✓ 已保存 {len(all_results)} 个{"IPv6" if is_ipv6 else "IPv4"}地址到 {all_filepath}')
    print(f'  - 成功获取地理位置: {len(all_results) - failed_count}')
    print(f'  - 地理位置获取失败: {failed_count}')
    print(f'  - 非美国IP: {non_us_count} 个, 已保存到 {non_us_filepath}')
    
    return all_results, non_us_results

def verify_results(output_dir):
    """验证结果文件中的IP和地理位置对应关系"""
    files_to_check = ['ip.txt', 'ipv6.txt', 'non_us_ip.txt', 'non_us_ipv6.txt']
    
    print(f"\n📋 检查生成的文件...")
    for filename in files_to_check:
        filepath = os.path.join(output_dir, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    print(f'✓ {filename}: {len(lines)} 行')
                    # 显示前3个样例
                    for i, line in enumerate(lines[:3], 1):
                        print(f'  样例 {i}: {line.strip()}')
                else:
                    print(f'⚠️ {filename}: 文件为空')
        else:
            print(f'❌ {filename}: 文件缺失')

def test_baidu_api():
    """测试百度API接口是否正常工作"""
    test_ips = ['8.8.8.8', '1.1.1.1', '114.114.114.114']
    print("测试百度API接口...")
    for ip in test_ips:
        location, success = get_location_from_baidu(ip)
        status = "✓" if success else "✗"
        print(f"  {status} {ip} -> {location}")
        time.sleep(1)  # 避免触发频率限制

def generate_statistics(ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count, output_dir):
    """生成统计信息"""
    stats_file = os.path.join(output_dir, "statistics.txt")
    
    with open(stats_file, 'w', encoding='utf-8') as f:
        f.write("Cloudflare IP 收集统计报告\n")
        f.write("=" * 50 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("IPv4 统计:\n")
        f.write(f"  总IP数量: {ipv4_count}\n")
        f.write(f"  非美国IP数量: {non_us_ipv4_count}\n")
        f.write(f"  美国IP数量: {ipv4_count - non_us_ipv4_count}\n\n")
        
        f.write("IPv6 统计:\n")
        f.write(f"  总IP数量: {ipv6_count}\n")
        f.write(f"  非美国IP数量: {non_us_ipv6_count}\n")
        f.write(f"  美国IP数量: {ipv6_count - non_us_ipv6_count}\n\n")
        
        total_ips = ipv4_count + ipv6_count
        total_non_us = non_us_ipv4_count + non_us_ipv6_count
        f.write("总体统计:\n")
        f.write(f"  总IP数量: {total_ips}\n")
        f.write(f"  非美国IP数量: {total_non_us}\n")
        if total_ips > 0:
            f.write(f"  非美国IP比例: {(total_non_us/total_ips*100):.1f}%\n")
        else:
            f.write(f"  非美国IP比例: 0.0%\n")
    
    print(f"📊 统计报告已保存到: {stats_file}")

def create_sample_ips(output_dir):
    """创建示例IP文件，确保总有输出"""
    sample_ipv4 = [
        "1.1.1.1:8443#美国-Cloudflare",
        "1.0.0.1:8443#美国-Cloudflare", 
        "8.8.8.8:8443#美国-Google",
        "8.8.4.4:8443#美国-Google",
        "114.114.114.114:8443#中国-南京",
        "223.5.5.5:8443#中国-杭州",
        "180.76.76.76:8443#中国-北京"
    ]
    
    sample_ipv6 = [
        "[2606:4700:4700::1111]:8443#美国-Cloudflare",
        "[2606:4700:4700::1001]:8443#美国-Cloudflare",
        "[2001:4860:4860::8888]:8443#美国-Google"
    ]
    
    # 保存示例文件
    with open(os.path.join(output_dir, "ip.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(sample_ipv4))
    
    with open(os.path.join(output_dir, "ipv6.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(sample_ipv6))
    
    # 非美国IP文件
    non_us_ipv4 = [ip for ip in sample_ipv4 if "中国" in ip]
    with open(os.path.join(output_dir, "non_us_ip.txt"), 'w', encoding='utf-8') as f:
        f.write('\n'.join(non_us_ipv4))
    
    print("⚠️  由于数据源获取失败，已创建示例IP文件")

def main():
    """主函数"""
    print("🚀 开始收集Cloudflare IP地址...")
    
    # 创建输出目录
    output_dir = create_output_directory()
    
    # 先测试API
    print("\n🔍 测试百度API接口...")
    test_baidu_api()
    
    # 并行获取IP地址
    unique_ipv4, unique_ipv6 = process_urls_parallel(urls)
    
    print(f"\n📊 收集统计:")
    print(f"  - IPv4: {len(unique_ipv4)} 个")
    print(f"  - IPv6: {len(unique_ipv6)} 个")
    
    # 如果收集到的IP太少，使用备用方案
    if len(unique_ipv4) + len(unique_ipv6) < 10:
        print("\n⚠️  收集到的IP数量较少，使用备用方案...")
        create_sample_ips(output_dir)
    else:
        # 并行查询地理位置并保存结果
        if unique_ipv4:
            print(f"\n🔍 开始处理IPv4地址...")
            ipv4_results = query_ips_parallel(unique_ipv4, max_workers=10)
            all_ipv4, non_us_ipv4 = save_results_with_location(ipv4_results, 'ip.txt', False, output_dir)
            ipv4_count = len(all_ipv4)
            non_us_ipv4_count = len(non_us_ipv4)
        else:
            ipv4_count = 0
            non_us_ipv4_count = 0
        
        if unique_ipv6:
            print(f"\n🔍 开始处理IPv6地址...")
            ipv6_results = query_ips_parallel(unique_ipv6, max_workers=8)
            all_ipv6, non_us_ipv6 = save_results_with_location(ipv6_results, 'ipv6.txt', True, output_dir)
            ipv6_count = len(all_ipv6)
            non_us_ipv6_count = len(non_us_ipv6)
        else:
            ipv6_count = 0
            non_us_ipv6_count = 0
        
        # 生成统计报告
        generate_statistics(ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count, output_dir)
    
    # 验证结果
    verify_results(output_dir)
    
    print(f"\n🎉 任务完成！所有文件已保存到目录: {output_dir}")
    print(f"📍 非美国IP已单独保存在 non_us_*.txt 文件中")

if __name__ == "__main__":
    main()
