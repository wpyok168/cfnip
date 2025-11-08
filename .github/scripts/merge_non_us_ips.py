#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
import glob

def get_available_dates():
    """获取所有可用的日期目录"""
    base_dir = "non_us_ips"
    if not os.path.exists(base_dir):
        return []
    
    dates = []
    for item in os.listdir(base_dir):
        if item == "merged":
            continue
        try:
            datetime.strptime(item, '%Y-%m-%d')
            dates.append(item)
        except ValueError:
            continue
    
    return sorted(dates)

def merge_non_us_ips(target_date):
    """
    合并指定日期的non_us_ips目录下的所有文件
    """
    print(f"开始处理日期: {target_date}")
    
    # 构建目标目录路径
    target_dir = f"non_us_ips/{target_date}"
    merged_dir = "non_us_ips/merged"
    
    print(f"目标目录: {target_dir}")
    print(f"合并目录: {merged_dir}")
    
    # 确保merged目录存在
    os.makedirs(merged_dir, exist_ok=True)
    
    # 检查目标目录是否存在
    if not os.path.exists(target_dir):
        print(f"❌ 错误: 目录 {target_dir} 不存在")
        
        # 显示可用的日期
        available_dates = get_available_dates()
        if available_dates:
            print("可用的日期目录:")
            for date in available_dates[-10:]:  # 显示最近10个日期
                print(f"  - {date}")
            
            # 建议使用最近的日期
            latest_date = available_dates[-1] if available_dates else None
            if latest_date:
                print(f"💡 建议: 使用最近的日期 {latest_date}")
                use_latest = input("是否使用最近日期? (y/n): ").strip().lower()
                if use_latest == 'y':
                    target_date = latest_date
                    target_dir = f"non_us_ips/{target_date}"
                    print(f"使用日期: {target_date}")
                else:
                    return False
        else:
            print("没有可用的日期目录")
            return False
    
    # 查找所有txt文件
    pattern = os.path.join(target_dir, "*.txt")
    files = glob.glob(pattern)
    
    if not files:
        print(f"⚠️ 警告: 在 {target_dir} 中未找到 .txt 文件")
        # 列出目录中的所有文件
        all_files = os.listdir(target_dir)
        if all_files:
            print(f"目录中的文件: {all_files}")
            # 尝试处理所有文件，不仅仅是.txt
            files = [os.path.join(target_dir, f) for f in all_files if os.path.isfile(os.path.join(target_dir, f))]
            print(f"将处理所有 {len(files)} 个文件")
        else:
            print("目录为空")
            return False
    
    print(f"找到 {len(files)} 个文件进行合并")
    
    # 合并文件
    merged_file = os.path.join(merged_dir, f"merged_ips_{target_date}.txt")
    unique_ips = set()
    
    for file_path in files:
        try:
            print(f"处理文件: {os.path.basename(file_path)}")
            with open(file_path, 'r', encoding='utf-8') as f:
                file_ips = 0
                for line in f:
                    ip = line.strip()
                    if ip and not ip.startswith('#'):
                        unique_ips.add(ip)
                        file_ips += 1
                print(f"  从 {os.path.basename(file_path)} 提取了 {file_ips} 个IP")
        except Exception as e:
            print(f"❌ 处理文件 {file_path} 时出错: {e}")
    
    print(f"去重后得到 {len(unique_ips)} 个唯一IP")
    
    # 计算北京时间（UTC+8）
    utc_now = datetime.utcnow()
    beijing_time = utc_now + timedelta(hours=8)
    
    # 写入合并后的文件
    try:
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write(f"# Merged non-US IPs for {target_date}\n")
            f.write(f"# Total unique IPs: {len(unique_ips)}\n")
            f.write(f"# Generated on (Beijing Time): {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} CST\n")
            f.write(f"# Source files: {len(files)}\n\n")
            
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
        # 更可靠的方法计算前天
        utc_now = datetime.utcnow()
        beijing_now = utc_now + timedelta(hours=8)
        target_date = (beijing_now - timedelta(days=2)).strftime('%Y-%m-%d')
        print(f"使用自动计算的前天日期: {target_date}")
    
    # 验证日期格式
    try:
        datetime.strptime(target_date, '%Y-%m-%d')
    except ValueError:
        print(f"❌ 错误的日期格式: {target_date}，应该为 YYYY-MM-DD")
        # 使用昨天作为备选
        utc_now = datetime.utcnow()
        beijing_now = utc_now + timedelta(hours=8)
        target_date = (beijing_now - timedelta(days=1)).strftime('%Y-%m-%d')
        print(f"使用备选日期: {target_date}")
    
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
