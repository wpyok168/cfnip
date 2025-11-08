#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
import glob
import re

def extract_date_from_filename(filename):
    """从文件名中提取日期"""
    # 匹配 non_us_ips_YYYYMMDD_HHMMSS.txt 格式
    match = re.search(r'non_us_ips_(\d{8})_\d+\.txt', filename)
    if match:
        return match.group(1)
    return None

def get_files_by_date(target_date):
    """根据日期获取匹配的文件"""
    base_dir = "non_us_ips"
    if not os.path.exists(base_dir):
        return []
    
    # 查找所有匹配的文件
    pattern = os.path.join(base_dir, f"non_us_ips_{target_date}_*.txt")
    files = glob.glob(pattern)
    
    # 如果没有找到精确匹配，尝试查找包含该日期的文件
    if not files:
        all_files = glob.glob(os.path.join(base_dir, "non_us_ips_*.txt"))
        files = [f for f in all_files if target_date in os.path.basename(f)]
    
    return sorted(files)

def get_latest_date_from_files():
    """从现有文件中获取最新日期"""
    base_dir = "non_us_ips"
    if not os.path.exists(base_dir):
        return None
    
    dates = set()
    for filename in os.listdir(base_dir):
        if filename.startswith("non_us_ips_") and filename.endswith(".txt"):
            date_str = extract_date_from_filename(filename)
            if date_str:
                dates.add(date_str)
    
    return sorted(dates)[-1] if dates else None

def merge_non_us_ips(target_date):
    """
    合并指定日期的non_us_ips目录下的所有文件
    """
    print(f"开始处理日期: {target_date}")
    
    # 转换日期格式（如果需要）
    if '-' in target_date:
        # 如果是 YYYY-MM-DD 格式，转换为 YYYYMMDD
        target_date = target_date.replace('-', '')
    
    print(f"处理日期格式: {target_date}")
    
    # 获取匹配的文件
    files = get_files_by_date(target_date)
    
    if not files:
        print(f"⚠️ 未找到日期为 {target_date} 的文件")
        
        # 显示可用的日期
        latest_date = get_latest_date_from_files()
        if latest_date:
            print(f"可用的最新日期: {latest_date}")
            # 自动使用最新日期
            target_date = latest_date
            files = get_files_by_date(target_date)
            print(f"自动使用最新日期: {target_date}")
        else:
            print("❌ 没有找到任何 non_us_ips 文件")
            return False
    
    print(f"找到 {len(files)} 个文件进行合并:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    # 确保merged目录存在
    merged_dir = "non_us_ips/merged"
    os.makedirs(merged_dir, exist_ok=True)
    
    # 合并文件
    # 将 YYYYMMDD 转换回 YYYY-MM-DD 用于输出文件名
    output_date = f"{target_date[:4]}-{target_date[4:6]}-{target_date[6:8]}"
    merged_file = os.path.join(merged_dir, f"merged_ips_{output_date}.txt")
    
    unique_ips = set()
    total_lines = 0
    
    for file_path in files:
        try:
            print(f"处理文件: {os.path.basename(file_path)}")
            with open(file_path, 'r', encoding='utf-8') as f:
                file_ips = 0
                for line_num, line in enumerate(f, 1):
                    ip = line.strip()
                    # 简单的IP验证
                    if ip and not ip.startswith('#') and '.' in ip:
                        # 移除可能的端口号 192.168.1.1:8080 -> 192.168.1.1
                        ip = ip.split(':')[0]
                        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                            unique_ips.add(ip)
                            file_ips += 1
                
                print(f"  从 {os.path.basename(file_path)} 提取了 {file_ips} 个IP")
                total_lines += file_ips
                
        except Exception as e:
            print(f"❌ 处理文件 {file_path} 时出错: {e}")
    
    print(f"总共处理了 {total_lines} 行，去重后得到 {len(unique_ips)} 个唯一IP")
    
    if not unique_ips:
        print("⚠️ 没有提取到任何有效的IP地址")
        return False
    
    # 写入合并后的文件
    try:
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write(f"# Merged non-US IPs for {output_date}\n")
            f.write(f"# Source date: {target_date}\n")
            f.write(f"# Total unique IPs: {len(unique_ips)}\n")
            f.write(f"# Source files: {len(files)}\n")
            f.write(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for ip in sorted(unique_ips):
                f.write(ip + '\n')
        
        print(f"✅ 成功合并 {len(unique_ips)} 个唯一IP到 {merged_file}")
        return True
    except Exception as e:
        print(f"❌ 写入合并文件时出错: {e}")
        return False

def main():
    print("=== 开始执行合并脚本 ===")
    
    # 获取目标日期参数
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        print(f"使用参数提供的日期: {target_date}")
    else:
        # 使用前天日期
        target_date = (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')
        print(f"使用自动计算的前天日期: {target_date}")
    
    # 执行合并
    success = merge_non_us_ips(target_date)
    
    if success:
        print("=== 合并成功 ===")
        sys.exit(0)
    else:
        print("=== 合并失败 ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
