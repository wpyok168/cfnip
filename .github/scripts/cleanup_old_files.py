#!/usr/bin/env python3
import os
import glob
from datetime import datetime, timedelta
import re

def extract_date_from_filename(filename):
    """从文件名中提取日期"""
    # 匹配 non_us_ips_YYYYMMDD_HHMMSS.txt 格式
    match = re.search(r'non_us_ips_(\d{8})_\d+\.txt', filename)
    if match:
        return match.group(1)
    return None

def cleanup_old_files():
    """
    删除过期的文件，保留最近7天的数据
    """
    print("=== 开始清理旧文件 ===")
    
    # 设置保留天数
    retention_days = 7
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    
    print(f"当前时间: {datetime.now()}")
    print(f"清理截止日期: {cutoff_date.date()}")
    print(f"保留最近 {retention_days} 天的文件")
    
    # 清理原始文件
    base_dir = "non_us_ips"
    deleted_count = 0
    
    if not os.path.exists(base_dir):
        print("non_us_ips 目录不存在，跳过清理")
        return 0
    
    # 处理原始文件
    for filename in os.listdir(base_dir):
        if filename.startswith("non_us_ips_") and filename.endswith(".txt"):
            date_str = extract_date_from_filename(filename)
            if date_str:
                try:
                    file_date = datetime.strptime(date_str, '%Y%m%d')
                    if file_date < cutoff_date:
                        file_path = os.path.join(base_dir, filename)
                        print(f"删除旧文件: {filename}")
                        os.remove(file_path)
                        deleted_count += 1
                    else:
                        print(f"保留文件: {filename} (在保留期内)")
                except ValueError:
                    print(f"跳过格式不正确的文件: {filename}")
    
    # 清理merged目录中的旧文件
    merged_dir = os.path.join(base_dir, "merged")
    if os.path.exists(merged_dir):
        for file in os.listdir(merged_dir):
            if file.startswith("merged_ips_") and file.endswith(".txt"):
                try:
                    # 从文件名提取日期 YYYY-MM-DD
                    date_str = file.replace("merged_ips_", "").replace(".txt", "")
                    file_date = datetime.strptime(date_str, '%Y-%m-%d')
                    
                    if file_date < cutoff_date:
                        file_path = os.path.join(merged_dir, file)
                        print(f"删除旧合并文件: {file}")
                        os.remove(file_path)
                        deleted_count += 1
                    else:
                        print(f"保留合并文件: {file} (在保留期内)")
                except ValueError:
                    print(f"跳过格式不正确的合并文件: {file}")
    
    print(f"清理完成。共删除 {deleted_count} 个项目。")
    return deleted_count

if __name__ == "__main__":
    try:
        cleanup_old_files()
        print("=== 清理脚本执行成功 ===")
    except Exception as e:
        print(f"清理脚本执行失败: {e}")
        sys.exit(1)
