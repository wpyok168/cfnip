#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cloudflare IP地址收集器
功能：从多个数据源收集Cloudflare IP地址，查询地理位置，按地区分类保存
作者：基于原始脚本改进
版本：2.0
"""

import requests
import re
import os
import time
import ipaddress
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime, timezone, timedelta

class CFIPCollector:
    def __init__(self, urls_config='urls.json', main_config='config.json'):
        """初始化配置"""
        # 设置北京时区 (UTC+8)
        self.beijing_tz = timezone(timedelta(hours=8))
        self.load_urls_config(urls_config)
        self.load_main_config(main_config)
        self.setup_global_variables()
        print("Cloudflare IP收集器初始化完成")
        
    def get_beijing_time(self):
        """获取北京时间"""
        return datetime.now(self.beijing_tz)
        
    def load_urls_config(self, config_file):
        """加载URL列表配置"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.urls = config.get('url_sources', [])
            print(f'✅ 已加载 {len(self.urls)} 个URL数据源')
        except Exception as e:
            print(f'❌ 加载URL配置文件失败: {e}，使用默认URL列表')
            # 优选域名:https://github.com/gslege/CloudflareIP/blob/main/Domain.txt
            self.urls = [
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
                'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/JP.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/DE.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/NL.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt',
                'https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/US.txt',
                'https://raw.githubusercontent.com/camel52zhang/yxip/refs/heads/main/ip.txt',
                'https://raw.githubusercontent.com/Senflare/Senflare-IP/refs/heads/main/IPlist.txt',
                'https://raw.githubusercontent.com/hubbylei/bestcf/refs/heads/main/bestcf.txt'
            ]
    
    def load_main_config(self, config_file):
        """加载主配置文件，自动忽略注释"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 移除JSON注释（以"//"开头的行）
            lines = content.split('\n')
            cleaned_lines = []
            for line in lines:
                stripped_line = line.strip()
                # 保留空行和非注释行
                if not stripped_line.startswith('"//') and not stripped_line.startswith('//'):
                    cleaned_lines.append(line)
            
            cleaned_content = '\n'.join(cleaned_lines)
            self.config = json.loads(cleaned_content)
            print('✅ 主配置文件加载成功')
        except Exception as e:
            print(f'❌ 加载主配置文件失败: {e}，使用默认配置')
            self.set_default_config()
    
    def set_default_config(self):
        """设置默认配置"""
        self.config = {
            "request_settings": {
                "timeout": 10,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "max_workers_url": 5,
                "max_workers_ipv4": 15,
                "max_workers_ipv6": 10,
                "retry_times": 2,
                "retry_delay": 1
            },
            "output_settings": {
                "ipv4_filename": "ip.txt",
                "ipv6_filename": "ipv6.txt",
                "non_us_folder": "non_us_ips",
                "port": 8443,
                "save_all_ips": True,
                "save_non_us_separately": True
            },
            "location_settings": {
                "baidu_api_url": "https://opendata.baidu.com/api.php",
                "us_keywords": ["美国", "United States", "US", "USA"],
                "enable_location_query": True
            },
            "filter_settings": {
                "enable_ip_validation": True,
                "remove_private_ips": True,
                "remove_duplicates": True
            },
            "progress_settings": {
                "show_progress": True,
                "progress_interval": 10
            }
        }
    
    def setup_global_variables(self):
        """设置全局变量"""
        # IP地址正则表达式
        self.ipv4_pattern = r'\b(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        self.ipv6_pattern = r'(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}|(?:[A-Fa-f0-9]{1,4}:){1,7}:|(?:[A-Fa-f0-9]{1,4}:){1,6}:[A-Fa-f0-9]{1,4}'
        
        # 请求头
        self.headers = {
            'User-Agent': self.config['request_settings']['user_agent'],
            'Accept': 'application/json',
            'Referer': 'https://www.baidu.com/'
        }
        
        # 进度显示变量
        self.progress_lock = threading.Lock()
        self.completed_count = 0
        self.total_count = 0
        self.success_count = 0

    def ensure_folders(self):
        """确保必要的文件夹存在"""
        non_us_folder = self.config['output_settings']['non_us_folder']
        if not os.path.exists(non_us_folder):
            os.makedirs(non_us_folder)
            print(f'📁 创建文件夹: {non_us_folder}')

    def clean_old_files(self):
        """清理旧文件"""
        output_settings = self.config['output_settings']
        for filename in [output_settings['ipv4_filename'], output_settings['ipv6_filename']]:
            if os.path.exists(filename):
                os.remove(filename)
                print(f'🗑️  已删除旧文件: {filename}')

    def fetch_url(self, url):
        """获取URL内容"""
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.config['request_settings']['timeout']
            )
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f'❌ 请求 {url} 失败: {e}')
            return None

    def extract_ips_from_text(self, text):
        """从文本中提取IP地址"""
        ipv4_matches = re.findall(self.ipv4_pattern, text)
        ipv6_matches = re.findall(self.ipv6_pattern, text)
        
        valid_ipv4 = set()
        valid_ipv6 = set()
        
        # 验证IPv4地址
        for ip in ipv4_matches:
            try:
                if isinstance(ip, tuple):
                    ip_str = '.'.join(ip)
                else:
                    ip_str = ip
                
                if not self.config['filter_settings']['enable_ip_validation']:
                    valid_ipv4.add(ip_str)
                    continue
                    
                ip_obj = ipaddress.IPv4Address(ip_str)
                
                # 过滤私有IP
                if self.config['filter_settings']['remove_private_ips'] and ip_obj.is_private:
                    continue
                    
                valid_ipv4.add(ip_str)
            except (ValueError, ipaddress.AddressValueError):
                continue
        
        # 验证IPv6地址
        for ip in ipv6_matches:
            try:
                if not self.config['filter_settings']['enable_ip_validation']:
                    valid_ipv6.add(ip.lower())
                    continue
                    
                ip_obj = ipaddress.IPv6Address(ip)
                
                # 过滤私有IP
                if self.config['filter_settings']['remove_private_ips'] and ip_obj.is_private:
                    continue
                    
                valid_ipv6.add(ip_obj.compressed.lower())
            except (ValueError, ipaddress.AddressValueError):
                continue
        
        return valid_ipv4, valid_ipv6

    def get_location_from_baidu(self, ip):
        """从百度API获取IP的地理位置信息"""
        if not self.config['location_settings']['enable_location_query']:
            return '未知', False
            
        try:
            api_url = self.config['location_settings']['baidu_api_url']
            url = f'{api_url}?co=&resource_id=6006&oe=utf8&query={ip}&lang=en'
            resp = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.config['request_settings']['timeout']
            )
            
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
            return '未知', False
        except Exception as e:
            return '未知', False

    def process_single_ip(self, ip):
        """处理单个IP地址查询"""
        location, success = self.get_location_from_baidu(ip)
        
        if self.config['progress_settings']['show_progress']:
            with self.progress_lock:
                self.completed_count += 1
                if success:
                    self.success_count += 1
                
                progress_interval = self.config['progress_settings']['progress_interval']
                if self.completed_count % progress_interval == 0 or self.completed_count == self.total_count:
                    success_rate = (self.success_count / self.completed_count * 100) if self.completed_count > 0 else 0
                    print(f'📊 进度: {self.completed_count}/{self.total_count} (成功率: {success_rate:.1f}%)')
        
        return ip, location, success

    def process_urls_parallel(self):
        """并行处理URL获取"""
        all_ipv4 = set()
        all_ipv6 = set()
        
        max_workers = self.config['request_settings']['max_workers_url']
        
        print(f'🚀 开始并行从 {len(self.urls)} 个数据源获取IP地址...')
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(self.fetch_url, url): url for url in self.urls}
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    text = future.result()
                    if text:
                        ipv4, ipv6 = self.extract_ips_from_text(text)
                        all_ipv4.update(ipv4)
                        all_ipv6.update(ipv6)
                        print(f'✅ 成功处理: {url} (IPv4: {len(ipv4)}, IPv6: {len(ipv6)})')
                    else:
                        print(f'❌ 获取内容为空: {url}')
                except Exception as e:
                    print(f'❌ 处理 {url} 时出错: {e}')
        
        # 去重处理
        if self.config['filter_settings']['remove_duplicates']:
            original_ipv4_count = len(all_ipv4)
            original_ipv6_count = len(all_ipv6)
            all_ipv4 = set(all_ipv4)
            all_ipv6 = set(all_ipv6)
            print(f'🔄 去重后: IPv4 {original_ipv4_count} → {len(all_ipv4)}, IPv6 {original_ipv6_count} → {len(all_ipv6)}')
        
        return all_ipv4, all_ipv6

    def query_ips_parallel(self, ip_set, is_ipv6=False):
        """并行查询IP地址的地理位置"""
        # 重置计数器
        self.completed_count = 0
        self.total_count = len(ip_set)
        self.success_count = 0
        
        if not ip_set:
            return []
        
        worker_type = "IPv6" if is_ipv6 else "IPv4"
        max_workers = self.config['request_settings'][f'max_workers_{"ipv6" if is_ipv6 else "ipv4"}']
        
        print(f'🌍 开始并行查询 {self.total_count} 个{worker_type}地址的地理位置...')
        print(f'⚡ 使用 {max_workers} 个线程同时查询')
        
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ip = {executor.submit(self.process_single_ip, ip): ip for ip in ip_set}
            
            for future in as_completed(future_to_ip):
                try:
                    ip, location, success = future.result()
                    results.append((ip, location))
                except Exception as e:
                    ip = future_to_ip[future]
                    print(f"❌ 处理IP {ip} 时发生异常: {e}")
                    results.append((ip, '未知'))
        
        # 最终进度显示
        if self.config['progress_settings']['show_progress']:
            success_rate = (self.success_count / self.total_count * 100) if self.total_count > 0 else 0
            print(f'✅ 查询完成: 总计 {self.total_count}, 成功 {self.success_count}, 成功率: {success_rate:.1f}%')
        
        return results

    def is_us_location(self, location):
        """判断是否为美国区域"""
        if location == '未知':
            return False
            
        us_keywords = self.config['location_settings']['us_keywords']
        location_lower = location.lower()
        for keyword in us_keywords:
            if keyword.lower() in location_lower:
                return True
        return False

    def save_results_with_location(self, ip_results, filename, is_ipv6=False):
        """保存结果到文件"""
        if not ip_results:
            print(f'⚠️  没有要保存的{"IPv6" if is_ipv6 else "IPv4"}地址结果。')
            return [], []
        
        # 按IP地址排序结果
        if is_ipv6:
            sorted_results = sorted(ip_results, key=lambda x: x[0])
        else:
            sorted_results = sorted(ip_results, key=lambda x: [int(part) for part in x[0].split('.')])
        
        all_results = []
        us_results = []
        non_us_results = []
        failed_count = 0
        
        port = self.config['output_settings']['port']
        current_time = self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')
        
        for ip, location in sorted_results:
            if location == '未知':
                failed_count += 1
            
            if is_ipv6:
                result_line = f"[{ip}]:{port}#{location}-IPV6"
            else:
                result_line = f"{ip}:{port}#{location}"
            
            all_results.append(result_line)
            
            # 分离美国和非美国IP
            if self.is_us_location(location):
                us_results.append(result_line)
            else:
                non_us_results.append(result_line)
        
        # 保存所有结果
        if self.config['output_settings']['save_all_ips']:
            with open(filename, 'w', encoding='utf-8') as file:
                file.write(f"# Cloudflare IP地址列表\n")
                file.write(f"# 生成时间(北京时间): {current_time}\n")
                file.write(f"# 类型: {'IPv6' if is_ipv6 else 'IPv4'}\n")
                file.write(f"# 总数: {len(all_results)}, 美国: {len(us_results)}, 非美国: {len(non_us_results)}\n\n")
                for line in all_results:
                    file.write(line + '\n')
        
        print(f'💾 已保存 {len(all_results)} 个{"IPv6" if is_ipv6 else "IPv4"}地址到 {filename}')
        print(f'📍 成功获取地理位置: {len(all_results) - failed_count}, 失败: {failed_count}')
        print(f'🇺🇸 美国区域: {len(us_results)}, 🌍 非美国区域: {len(non_us_results)}')
        
        return us_results, non_us_results

    def save_non_us_ips(self, non_us_ipv4, non_us_ipv6):
        """保存非美国区域IP到日期时间命名的文件"""
        if not non_us_ipv4 and not non_us_ipv6:
            print('⚠️  没有非美国区域IP需要保存')
            return None
        
        if not self.config['output_settings']['save_non_us_separately']:
            return None
            
        # 生成日期时间文件名
        current_time = self.get_beijing_time().strftime("%Y%m%d_%H%M%S")
        non_us_folder = self.config['output_settings']['non_us_folder']
        filename = f"{non_us_folder}/non_us_ips_{current_time}.txt"
        
        with open(filename, 'w', encoding='utf-8') as file:
            file.write(f"# 非美国区域Cloudflare IP收集\n")
            file.write(f"# 生成时间(北京时间): {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write(f"# IPv4数量: {len(non_us_ipv4)}, IPv6数量: {len(non_us_ipv6)}\n")
            file.write(f"# 格式: IP:端口#地理位置\n\n")
            
            if non_us_ipv4:
                file.write("# IPv4地址:\n")
                for line in non_us_ipv4:
                    file.write(line + '\n')
                file.write("\n")
            
            if non_us_ipv6:
                file.write("# IPv6地址:\n")
                for line in non_us_ipv6:
                    file.write(line + '\n')
        
        print(f'💾 已保存非美国区域IP到: {filename}')
        return filename

    def verify_results(self):
        """验证结果文件中的IP和地理位置对应关系"""
        output_settings = self.config['output_settings']
        print('\n🔍 验证结果文件:')
        
        for filename in [output_settings['ipv4_filename'], output_settings['ipv6_filename']]:
            if os.path.exists(filename):
                print(f'\n📄 文件: {filename}')
                with open(filename, 'r', encoding='utf-8') as f:
                    lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
                    print(f'📊 有效IP数量: {len(lines)}')
                    if lines:
                        print('📝 前5个样例:')
                        for i, line in enumerate(lines[:5], 1):
                            print(f'   {i}. {line}')

    def test_baidu_api(self):
        """测试百度API接口是否正常工作"""
        if not self.config['location_settings']['enable_location_query']:
            print("ℹ️  地理位置查询已禁用")
            return
            
        test_ips = ['8.8.8.8', '1.1.1.1', '162.159.58.65']
        print("🧪 测试百度API接口...")
        for ip in test_ips:
            location, success = self.get_location_from_baidu(ip)
            status = "✅" if success else "❌"
            print(f"{status} 测试 {ip} -> {location}")
            time.sleep(0.5)  # 避免触发频率限制

    def print_config_summary(self):
        """打印配置摘要"""
        print('\n📋 配置摘要:')
        print(f'  • 数据源数量: {len(self.urls)}')
        print(f'  • URL获取线程: {self.config["request_settings"]["max_workers_url"]}')
        print(f'  • IPv4查询线程: {self.config["request_settings"]["max_workers_ipv4"]}')
        print(f'  • IPv6查询线程: {self.config["request_settings"]["max_workers_ipv6"]}')
        print(f'  • 地理位置查询: {"启用" if self.config["location_settings"]["enable_location_query"] else "禁用"}')
        print(f'  • 保存非美国IP: {"是" if self.config["output_settings"]["save_non_us_separately"] else "否"}')
        print(f'  • 使用时区: 北京时间(UTC+8)')

    def main(self):
        """主函数"""
        print("=" * 50)
        print("🌐 Cloudflare IP地址收集器 v2.0")
        print("=" * 50)
        print(f"🕐 当前北京时间: {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 打印配置摘要
        self.print_config_summary()
        
        # 确保文件夹存在
        self.ensure_folders()
        
        # 先测试API
        print('\n' + '='*30)
        self.test_baidu_api()
        
        # 清理旧文件
        print('\n' + '='*30)
        self.clean_old_files()
        
        # 并行获取IP地址
        print('\n' + '='*30)
        unique_ipv4, unique_ipv6 = self.process_urls_parallel()
        
        print(f"\n🎉 收集完成: IPv4: {len(unique_ipv4)}个, IPv6: {len(unique_ipv6)}个")
        
        # 并行查询地理位置并保存结果
        non_us_ipv4 = []
        non_us_ipv6 = []
        output_settings = self.config['output_settings']
        
        if unique_ipv4:
            print(f"\n" + '='*30)
            ipv4_results = self.query_ips_parallel(unique_ipv4, False)
            us_ipv4, non_us_ipv4 = self.save_results_with_location(
                ipv4_results, output_settings['ipv4_filename'], False
            )
        
        if unique_ipv6:
            print(f"\n" + '='*30)
            ipv6_results = self.query_ips_parallel(unique_ipv6, True)
            us_ipv6, non_us_ipv6 = self.save_results_with_location(
                ipv6_results, output_settings['ipv6_filename'], True
            )
        
        # 保存非美国区域IP
        if non_us_ipv4 or non_us_ipv6:
            print(f"\n" + '='*30)
            non_us_filename = self.save_non_us_ips(non_us_ipv4, non_us_ipv6)
            if non_us_filename:
                print(f"\n📊 非美国区域IP统计:")
                print(f"  • IPv4: {len(non_us_ipv4)}个")
                print(f"  • IPv6: {len(non_us_ipv6)}个")
                print(f"  • 保存位置: {non_us_filename}")
        
        # 验证结果
        print(f"\n" + '='*30)
        self.verify_results()
        
        print(f"\n" + '='*50)
        print("🎊 任务完成！")
        print(f"🕐 完成时间(北京时间): {self.get_beijing_time().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

if __name__ == "__main__":
    try:
        collector = CFIPCollector('urls.json', 'config.json')
        collector.main()
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断程序执行")
    except Exception as e:
        print(f"\n\n💥 程序执行出错: {e}")
        import traceback
        traceback.print_exc()
