#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta, timezone
import glob

def merge_non_us_ips(target_date):
    """
    合并指定日期的non_us_ips目录下的所有文件
    """
    # 构建目标目录路径
    target_dir = f"non_us_ips/{target_date}"
    merged_dir = "non_us_ips/merged"
    
    # 确保merged目录存在
    os.makedirs(merged_dir, exist_ok=True)
    
    # 检查目标目录是否存在
    if not os.path.exists(target_dir):
        print(f"Directory {target_dir} does not exist")
        return False
    
    # 查找所有txt文件
    pattern = os.path.join(target_dir, "*.txt")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No .txt files found in {target_dir}")
        return False
    
    print(f"Found {len(files)} files to merge")
    
    # 合并文件
    merged_file = os.path.join(merged_dir, f"merged_ips_{target_date}.txt")
    unique_ips = set()
    
    for file_path in files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    ip = line.strip()
                    if ip and not ip.startswith('#'):
                        unique_ips.add(ip)
            print(f"Processed {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    # 使用北京时间
    beijing_tz = timezone(timedelta(hours=8))
    beijing_time = datetime.now(beijing_tz)
    
    # 写入合并后的文件
    with open(merged_file, 'w', encoding='utf-8') as f:
        f.write(f"# Merged non-US IPs for {target_date}\n")
        f.write(f"# Total unique IPs: {len(unique_ips)}\n")
        f.write(f"# Generated on (Beijing Time): {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} CST\n\n")
        
        for ip in sorted(unique_ips):
            f.write(ip + '\n')
    
    print(f"Merged {len(unique_ips)} unique IPs into {merged_file}")
    return True

if __name__ == "__main__":
    # 获取目标日期参数
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
    else:
        # 默认为前天（基于北京时间）
        beijing_tz = timezone(timedelta(hours=8))
        beijing_now = datetime.now(beijing_tz)
        target_date = (beijing_now - timedelta(days=2)).strftime('%Y-%m-%d')
    
    beijing_tz = timezone(timedelta(hours=8))
    print(f"Beijing Time: {datetime.now(beijing_tz)}")
    print(f"Starting merge for date: {target_date}")
    success = merge_non_us_ips(target_date)
    sys.exit(0 if success else 1)
