#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
import glob

def debug_info():
    """打印调试信息"""
    print("=== 调试信息 ===")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python版本: {sys.version}")
    print(f"当前UTC时间: {datetime.utcnow()}")
    
    # 检查 non_us_ips 目录
    if os.path.exists("non_us_ips"):
        print("non_us_ips 目录存在")
        items = os.listdir("non_us_ips")
        print(f"目录内容: {items}")
    else:
        print("non_us_ips 目录不存在")
        # 创建示例目录结构用于测试
        os.makedirs("non_us_ips/2024-01-15", exist_ok=True)
        os.makedirs("non_us_ips/merged", exist_ok=True)
        # 创建示例文件
        with open("non_us_ips/2024-01-15/example.txt", "w") as f:
            f.write("192.168.1.1\n192.168.1.2\n")
        print("已创建示例目录和文件")

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
    print(f"确保合并目录存在: {os.path.exists(merged_dir)}")
    
    # 检查目标目录是否存在
    if not os.path.exists(target_dir):
        print(f"错误: 目录 {target_dir} 不存在")
        print("可用的日期目录:")
        for item in os.listdir("non_us_ips"):
            if os.path.isdir(os.path.join("non_us_ips", item)) and item != "merged":
                print(f"  - {item}")
        return False
    
    # 查找所有txt文件
    pattern = os.path.join(target_dir, "*.txt")
    print(f"搜索模式: {pattern}")
    files = glob.glob(pattern)
    
    if not files:
        print(f"警告: 在 {target_dir} 中未找到 .txt 文件")
        # 列出目录中的所有文件
        all_files = os.listdir(target_dir)
        print(f"目录中的文件: {all_files}")
        return False
    
    print(f"找到 {len(files)} 个文件进行合并: {files}")
    
    # 合并文件
    merged_file = os.path.join(merged_dir, f"merged_ips_{target_date}.txt")
    unique_ips = set()
    
    total_lines = 0
    for file_path in files:
        try:
            print(f"处理文件: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                file_lines = 0
                for line_num, line in enumerate(f, 1):
                    ip = line.strip()
                    if ip and not ip.startswith('#'):
                        unique_ips.add(ip)
                        file_lines += 1
                print(f"  从 {file_path} 提取了 {file_lines} 个IP")
                total_lines += file_lines
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    print(f"总共处理了 {total_lines} 行，去重后得到 {len(unique_ips)} 个唯一IP")
    
    # 计算北京时间（UTC+8）
    utc_now = datetime.utcnow()
    beijing_time = utc_now + timedelta(hours=8)
    
    # 写入合并后的文件
    print(f"写入合并文件: {merged_file}")
    try:
        with open(merged_file, 'w', encoding='utf-8') as f:
            f.write(f"# Merged non-US IPs for {target_date}\n")
            f.write(f"# Total unique IPs: {len(unique_ips)}\n")
            f.write(f"# Generated on (Beijing Time): {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} CST\n")
            f.write(f"# Source files: {len(files)}\n\n")
            
            for ip in sorted(unique_ips):
                f.write(ip + '\n')
        
        print(f"成功合并 {len(unique_ips)} 个唯一IP到 {merged_file}")
        return True
    except Exception as e:
        print(f"写入合并文件时出错: {e}")
        return False

if __name__ == "__main__":
    print("=== 开始执行合并脚本 ===")
    
    # 打印调试信息
    debug_info()
    
    # 获取目标日期参数
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        print(f"使用参数提供的日期: {target_date}")
    else:
        # 默认为前天（基于UTC+8的北京时间概念）
        utc_now = datetime.utcnow()
        beijing_now = utc_now + timedelta(hours=8)
        target_date = (beijing_now - timedelta(days=2)).strftime('%Y-%m-%d')
        print(f"使用自动计算的日期: {target_date}")
    
    print(f"目标日期: {target_date}")
    
    # 执行合并
    success = merge_non_us_ips(target_date)
    
    if success:
        print("=== 合并成功 ===")
        sys.exit(0)
    else:
        print("=== 合并失败 ===")
        sys.exit(1)
