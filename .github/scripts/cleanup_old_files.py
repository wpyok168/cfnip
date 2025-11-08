#!/usr/bin/env python3
import os
import glob
from datetime import datetime, timedelta, timezone
import shutil

def cleanup_old_files():
    """
    删除过期的文件，保留最近7天的数据（基于北京时间）
    """
    # 设置保留天数
    retention_days = 7
    
    # 使用北京时间
    beijing_tz = timezone(timedelta(hours=8))
    beijing_now = datetime.now(beijing_tz)
    cutoff_date = beijing_now - timedelta(days=retention_days)
    
    print(f"Beijing Time: {beijing_now.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"Cleaning up files older than {cutoff_date.strftime('%Y-%m-%d')}")
    
    # 清理原始数据目录
    base_dir = "non_us_ips"
    deleted_count = 0
    
    # 检查所有日期格式的目录 (YYYY-MM-DD)
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        
        # 跳过merged目录
        if item == "merged":
            continue
            
        # 检查是否是日期格式的目录
        try:
            # 将目录名解析为日期（无时区信息，假设为北京时区）
            dir_date = datetime.strptime(item, '%Y-%m-%d').replace(tzinfo=beijing_tz)
            if dir_date < cutoff_date:
                print(f"Removing old directory: {item_path}")
                shutil.rmtree(item_path)
                deleted_count += 1
        except ValueError:
            # 如果不是日期格式目录，跳过
            continue
    
    # 清理merged目录中的旧文件
    merged_dir = os.path.join(base_dir, "merged")
    if os.path.exists(merged_dir):
        for file in os.listdir(merged_dir):
            if file.startswith("merged_ips_") and file.endswith(".txt"):
                try:
                    # 从文件名提取日期
                    date_str = file.replace("merged_ips_", "").replace(".txt", "")
                    file_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=beijing_tz)
                    
                    if file_date < cutoff_date:
                        file_path = os.path.join(merged_dir, file)
                        print(f"Removing old merged file: {file_path}")
                        os.remove(file_path)
                        deleted_count += 1
                except ValueError:
                    # 如果文件名格式不正确，跳过
                    continue
    
    print(f"Cleanup completed. Removed {deleted_count} items.")
    return deleted_count

if __name__ == "__main__":
    cleanup_old_files()
