#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
import glob
import re

def is_valid_ip(ip):
    """验证IP地址格式是否正确"""
    if not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
        return False
    
    parts = ip.split('.')
    for part in parts:
        if not part.isdigit() or not (0 <= int(part) <= 255):
            return False
    
    return True

def extract_clean_ip(line):
    """从行中提取并清理IP地址"""
    line = line.strip()
    
    if not line or line.startswith('#'):
        return None
    
    ip_candidate = line.split()[0] if line else ''
    ip_candidate = ip_candidate.split(':')[0]
    ip_candidate = ip_candidate.split('/')[0]
    
    if is_valid_ip(ip_candidate):
        return ip_candidate
    
    return None

def get_files_by_date(target_date):
    """根据日期获取匹配的文件"""
    base_dir = "non_us_ips"
    if not os.path.exists(base_dir):
        print(f"❌ 基础目录 {base_dir} 不存在")
        return []
    
    pattern = os.path.join(base_dir, f"non_us_ips_{target_date}_*.txt")
    files = glob.glob(pattern)
    
    if not files:
        all_files = glob.glob(os.path.join(base_dir, "non_us_ips_*.txt"))
        files = [f for f in all_files if target_date in os.path.basename(f)]
    
    return sorted(files)

def merge_and_deduplicate_ips(target_date):
    """
    合并指定日期的文件，并去重IP地址
    """
    print(f"开始处理日期: {target_date}")
    
    if '-' in target_date:
        target_date = target_date.replace('-', '')
    
    print(f"处理日期格式: {target_date}")
    
    files = get_files_by_date(target_date)
    
    if not files:
        print(f"❌ 未找到日期为 {target_date} 的文件")
        return False
    
    print(f"找到 {len(files)} 个文件进行合并和去重:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    # 确保merged目录存在
    merged_dir = "non_us_ips/merged"
    os.makedirs(merged_dir, exist_ok=True)
    
    # 使用集合进行去重
    unique_ips = set()
    
    for file_path in files:
        try:
            print(f"处理文件: {os.path.basename(file_path)}")
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    clean_ip = extract_clean_ip(line)
                    if clean_ip:
                        unique_ips.add(clean_ip)
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    print(f"去重后得到 {len(unique_ips)} 个唯一IP地址")
    
    if not unique_ips:
        print("没有提取到任何有效的IP地址")
        return False
    
    # 写入合并后的文件
    output_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"
    merged_file = os.path.join(merged_dir, f"merged_ips_{output_date}.txt")
    
    try:
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write(f"# Merged and Deduplicated non-US IPs for {output_date}\n")
            f.write(f"# Total unique IPs: {len(unique_ips)}\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            sorted_ips = sorted(unique_ips, key=lambda ip: [int(part) for part in ip.split('.')])
            for ip in sorted_ips:
                f.write(ip + '\n')
        
        print(f"✅ 成功生成合并文件: {merged_file}")
        print(f"包含 {len(unique_ips)} 个唯一IP")
        return True
            
    except Exception as e:
        print(f"写入合并文件时出错: {e}")
        return False

def main():
    print("开始执行IP合并去重脚本")
    
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        print(f"使用参数提供的日期: {target_date}")
    else:
        target_date = (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')
        print(f"使用自动计算的前天日期: {target_date}")
    
    success = merge_and_deduplicate_ips(target_date)
    
    if success:
        print("合并去重成功")
        sys.exit(0)
    else:
        print("合并去重失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
