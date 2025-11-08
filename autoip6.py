import requests
import re
import os
import time
import ipaddress
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from queue import Queue
from datetime import datetime
from functools import wraps

# ========== 配置 ==========
CONFIG = {
    'urls': [
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
    ],
    'request_timeout': 15,
    'max_workers_url': 8,
    'max_workers_ip_query': 12,
    'max_retries': 3,
    'results_folder': 'cf_ip_results',
    'baidu_api_timeout': 10,
    'batch_size': 500,
}

# IP地址正则表达式
ipv4_pattern = r'\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
ipv6_pattern = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'

# 请求头
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/json,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# Cloudflare IP范围
CF_IP_RANGES = {
    'ipv4': [
        '173.245.48.0/20', '103.21.244.0/22', '103.22.200.0/22', '103.31.4.0/22',
        '141.101.64.0/18', '108.162.192.0/18', '190.93.240.0/20', '188.114.96.0/20',
        '197.234.240.0/22', '198.41.128.0/17', '162.158.0.0/15', '104.16.0.0/13',
        '104.24.0.0/14', '172.64.0.0/13', '131.0.72.0/22'
    ],
    'ipv6': [
        '2606:4700::/32', '2803:f800::/32', '2405:b500::/32', '2405:8100::/32',
        '2a06:98c0::/29', '2c0f:f248::/32'
    ]
}

# 全局变量
progress_lock = threading.Lock()
completed_count = 0
total_count = 0
success_count = 0

# ========== 日志设置 ==========
def setup_logging():
    """设置日志记录"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )

# ========== 工具函数 ==========
def timer(func):
    """计时装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        logging.info(f'{func.__name__} 执行时间: {end_time - start_time:.2f}秒')
        return result
    return wrapper

def fetch_url_with_retry(url, max_retries=3):
    """带重试机制的URL获取"""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=CONFIG['request_timeout'])
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                logging.warning(f'请求 {url} 失败 (尝试 {attempt + 1} 次): {e}')
                return None
            logging.info(f'请求 {url} 失败，第 {attempt + 1} 次重试...')
            time.sleep(2)  # 重试前等待

def validate_cloudflare_ip(ip, is_ipv6=False):
    """验证是否为Cloudflare IP范围"""
    try:
        if is_ipv6:
            ip_obj = ipaddress.IPv6Address(ip)
            cf_ranges = [ipaddress.IPv6Network(net) for net in CF_IP_RANGES['ipv6']]
        else:
            ip_obj = ipaddress.IPv4Address(ip)
            cf_ranges = [ipaddress.IPv4Network(net) for net in CF_IP_RANGES['ipv4']]
        
        return any(ip_obj in network for network in cf_ranges)
    except Exception as e:
        logging.debug(f'IP验证失败 {ip}: {e}')
        return False

def extract_ips_from_text(text):
    """从文本中提取IP地址"""
    ipv4_matches = re.findall(ipv4_pattern, text)
    ipv6_matches = re.findall(ipv6_pattern, text)
    
    valid_ipv4 = set()
    valid_ipv6 = set()
    
    # 验证IPv4地址
    for ip in ipv4_matches:
        try:
            if isinstance(ip, tuple):
                ip_str = '.'.join(ip)
            else:
                ip_str = ip
            
            if validate_cloudflare_ip(ip_str, False):
                ipaddress.IPv4Address(ip_str)
                valid_ipv4.add(ip_str)
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    # 验证IPv6地址
    for ip in ipv6_matches:
        try:
            ip_obj = ipaddress.IPv6Address(ip)
            if validate_cloudflare_ip(ip, True):
                valid_ipv6.add(ip_obj.compressed.lower())
        except (ValueError, ipaddress.AddressValueError):
            continue
    
    return valid_ipv4, valid_ipv6

def get_location_from_baidu(ip):
    """从百度API获取IP的地理位置信息"""
    try:
        url = f'https://opendata.baidu.com/api.php?co=&resource_id=6006&oe=utf8&query={ip}&lang=en'
        resp = requests.get(url, headers=headers, timeout=CONFIG['baidu_api_timeout'])
        
        if resp.status_code == 200:
            try:
                data = resp.json()
                status = data.get('status')
                if status == '0':
                    if data.get('data') and len(data['data']) > 0:
                        location = data['data'][0].get('location', '未知')
                        if location and location != '未知':
                            return location, True
            except json.JSONDecodeError:
                pass
    except Exception as e:
        logging.debug(f'百度API查询失败 {ip}: {e}')
    
    return '未知', False

def process_single_ip(ip):
    """处理单个IP地址查询"""
    global completed_count, success_count
    
    location, success = get_location_from_baidu(ip)
    
    with progress_lock:
        completed_count += 1
        if success:
            success_count += 1
        
        # 每处理50个IP或完成时显示进度
        if completed_count % 50 == 0 or completed_count == total_count:
            success_rate = (success_count / completed_count * 100) if completed_count > 0 else 0
            logging.info(f'进度: {completed_count}/{total_count} (成功率: {success_rate:.1f}%)')
    
    return ip, location, success

@timer
def process_urls_parallel(urls, max_workers=None):
    """并行处理URL获取"""
    if max_workers is None:
        max_workers = CONFIG['max_workers_url']
    
    all_ipv4 = set()
    all_ipv6 = set()
    failed_urls = []
    
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
                    logging.info(f'✅ 成功处理: {url} (IPv4: {len(ipv4)}, IPv6: {len(ipv6)})')
                else:
                    failed_urls.append(url)
            except Exception as e:
                logging.error(f'❌ 处理 {url} 时出错: {e}')
                failed_urls.append(url)
    
    if failed_urls:
        logging.warning(f'失败的数据源: {len(failed_urls)} 个')
    
    return all_ipv4, all_ipv6

@timer
def query_ips_parallel(ip_set, max_workers=None, is_ipv6=False):
    """并行查询IP地址的地理位置"""
    global completed_count, total_count, success_count
    
    if max_workers is None:
        max_workers = CONFIG['max_workers_ip_query']
    
    # 重置计数器
    completed_count = 0
    total_count = len(ip_set)
    success_count = 0
    
    if not ip_set:
        return []
    
    ip_type = "IPv6" if is_ipv6 else "IPv4"
    logging.info(f'开始并行查询 {total_count} 个{ip_type}地址的地理位置...')
    logging.info(f'使用 {max_workers} 个线程同时查询')
    
    results = []
    ip_list = list(ip_set)
    
    # 分批处理以避免内存问题
    for i in range(0, len(ip_list), CONFIG['batch_size']):
        batch = ip_list[i:i + CONFIG['batch_size']]
        logging.info(f'处理批次 {i//CONFIG["batch_size"] + 1}/{(len(ip_list)-1)//CONFIG["batch_size"] + 1}')
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {executor.submit(process_single_ip, ip): ip for ip in batch}
            
            for future in as_completed(future_to_ip):
                try:
                    ip, location, success = future.result()
                    results.append((ip, location))
                except Exception as e:
                    ip = future_to_ip[future]
                    logging.error(f"处理IP {ip} 时发生异常: {e}")
                    results.append((ip, '未知'))
        
        # 批次间休息
        if i + CONFIG['batch_size'] < len(ip_list):
            time.sleep(1)
    
    # 最终进度显示
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    logging.info(f'✅ 查询完成: 总计 {total_count}, 成功 {success_count}, 成功率: {success_rate:.1f}%')
    
    return results

def is_us_location(location):
    """判断是否为美国区域"""
    us_keywords = ['美国', 'United States', 'US', 'USA', '加利福尼亚', '加州', '洛杉矶', 
                   '旧金山', '纽约', '芝加哥', '西雅图', '达拉斯', '亚特兰大', '迈阿密', '华盛顿']
    
    if not location or location == '未知':
        return False
    
    location_lower = location.lower()
    return any(keyword.lower() in location_lower for keyword in us_keywords)

def save_results_with_location(ip_results, filename, is_ipv6=False):
    """保存结果到文件，并分离美国和非美国IP"""
    if not ip_results:
        logging.warning(f'没有要保存的{"IPv6" if is_ipv6 else "IPv4"}地址结果。')
        return [], []
    
    # 按IP地址排序结果
    if is_ipv6:
        sorted_results = sorted(ip_results, key=lambda x: x[0])
    else:
        sorted_results = sorted(ip_results, key=lambda x: [int(part) for part in x[0].split('.')])
    
    # 分离美国和非美国IP
    us_results = []
    non_us_results = []
    failed_count = 0
    
    for ip, location in sorted_results:
        if location == '未知':
            failed_count += 1
        
        if is_us_location(location):
            us_results.append((ip, location))
        else:
            non_us_results.append((ip, location))
    
    # 保存所有IP到文件
    all_results = []
    for ip, location in sorted_results:
        if is_ipv6:
            all_results.append(f"[{ip}]:8443#{location}-IPV6")
        else:
            all_results.append(f"{ip}:8443#{location}")
    
    with open(filename, 'w', encoding='utf-8') as file:
        for line in all_results:
            file.write(line + '\n')
    
    ip_type = "IPv6" if is_ipv6 else "IPv4"
    logging.info(f'✅ 已保存 {len(all_results)} 个{ip_type}地址到 {filename}')
    logging.info(f'📊 成功获取地理位置: {len(all_results) - failed_count}, 失败: {failed_count}')
    logging.info(f'🌎 美国IP: {len(us_results)}个, 非美国IP: {len(non_us_results)}个')
    
    return non_us_results, us_results

def save_non_us_ips(non_us_ipv4, non_us_ipv6):
    """保存非美国IP到日期时间命名的文件中"""
    if not non_us_ipv4 and not non_us_ipv6:
        logging.info("没有非美国IP需要保存。")
        return
    
    # 创建结果文件夹
    if not os.path.exists(CONFIG['results_folder']):
        os.makedirs(CONFIG['results_folder'])
    
    # 生成日期时间文件名
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"non_us_ips_{current_time}.txt"
    filepath = os.path.join(CONFIG['results_folder'], filename)
    
    # 合并IPv4和IPv6结果
    all_results = []
    
    # 处理IPv4
    for ip, location in non_us_ipv4:
        all_results.append(f"{ip}:8443#{location}")
    
    # 处理IPv6
    for ip, location in non_us_ipv6:
        all_results.append(f"[{ip}]:8443#{location}-IPV6")
    
    # 保存到文件
    with open(filepath, 'w', encoding='utf-8') as file:
        for line in all_results:
            file.write(line + '\n')
    
    logging.info(f'✅ 已保存 {len(all_results)} 个非美国IP到 {filepath}')
    logging.info(f'📊 其中IPv4: {len(non_us_ipv4)}个, IPv6: {len(non_us_ipv6)}个')

def clean_old_files():
    """清理旧文件，但保留结果文件夹"""
    for filename in ['ip.txt', 'ipv6.txt']:
        if os.path.exists(filename):
            os.remove(filename)
            logging.info(f'已删除旧文件: {filename}')

@timer
def test_baidu_api():
    """测试百度API接口是否正常工作"""
    test_ips = ['8.8.8.8', '1.1.1.1', '162.159.58.65']
    logging.info("测试百度API接口...")
    success_count = 0
    
    for ip in test_ips:
        location, success = get_location_from_baidu(ip)
        status = "✅" if success else "❌"
        logging.info(f"{status} 测试 {ip} -> {location}")
        if success:
            success_count += 1
        time.sleep(0.5)  # 短暂延迟避免触发限制
    
    return success_count >= 2  # 至少2个成功算API正常

def generate_summary(ipv4_count, ipv6_count, non_us_ipv4_count, non_us_ipv6_count):
    """生成执行摘要"""
    summary = f"""
📊 IP地址收集完成摘要
========================
🌐 数据源: {len(CONFIG['urls'])} 个
📅 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📁 收集结果:
├── IPv4地址: {ipv4_count} 个
├── IPv6地址: {ipv6_count} 个
├── 非美国IPv4: {non_us_ipv4_count} 个
└── 非美国IPv6: {non_us_ipv6_count} 个

💾 输出文件:
├── ip.txt (所有IPv4地址)
├── ipv6.txt (所有IPv6地址)
└── {CONFIG['results_folder']}/non_us_ips_*.txt (非美国IP历史记录)

✅ 任务执行完成
"""
    print(summary)

@timer
def main():
    """主函数"""
    setup_logging()
    logging.info("🚀 开始收集Cloudflare IP地址...")
    
    # API测试
    if not test_baidu_api():
        logging.warning("⚠️ 百度API测试结果不理想，可能会影响地理位置查询")
    
    clean_old_files()
    
    # 并行获取IP地址
    logging.info(f"🌍 开始从 {len(CONFIG['urls'])} 个数据源收集IP地址...")
    unique_ipv4, unique_ipv6 = process_urls_parallel(CONFIG['urls'])
    
    logging.info(f"✅ 收集完成: IPv4: {len(unique_ipv4)}个, IPv6: {len(unique_ipv6)}个")
    
    # 并行查询地理位置并保存结果
    non_us_ipv4 = []
    non_us_ipv6 = []
    
    if unique_ipv4:
        logging.info(f"🔍 开始处理IPv4地址...")
        ipv4_results = query_ips_parallel(unique_ipv4, is_ipv6=False)
        non_us_ipv4, us_ipv4 = save_results_with_location(ipv4_results, 'ip.txt', False)
    
    if unique_ipv6:
        logging.info(f"🔍 开始处理IPv6地址...")
        ipv6_results = query_ips_parallel(unique_ipv6, max_workers=8, is_ipv6=True)
        non_us_ipv6, us_ipv6 = save_results_with_location(ipv6_results, 'ipv6.txt', True)
    
    # 保存非美国IP到日期时间命名的文件
    save_non_us_ips(non_us_ipv4, non_us_ipv6)
    
    # 生成摘要
    generate_summary(
        len(unique_ipv4), 
        len(unique_ipv6),
        len(non_us_ipv4),
        len(non_us_ipv6)
    )
    
    logging.info("🎉 所有任务完成！")

if __name__ == "__main__":
    main()
