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
    
    # 直接取整行作为IP（假设每行只有一个IP）
    ip_candidate = line.split()[0]  # 取第一个单词
    ip_candidate = ip_candidate.split(':')[0]  # 移除端口
    ip_candidate = ip_candidate.split('/')[0]  # 移除CIDR
    
    if is_valid_ip(ip_candidate):
        return ip_candidate
    
    return None

def get_files_by_date(target_date):
    """根据日期获取匹配的文件"""
    base_dir = "non_us_ips"
    if not os.path.exists(base_dir):
        print(f"❌ 基础目录 {base_dir} 不存在")
        return []
    
    # 显示所有可用的文件
    all_files = glob.glob(os.path.join(base_dir, "non_us_ips_*.txt"))
    print(f"所有可用的文件: {[os.path.basename(f) for f in all_files]}")
    
    # 查找匹配目标日期的文件
    pattern = os.path.join(base_dir, f"non_us_ips_{target_date}_*.txt")
    files = glob.glob(pattern)
    
    if not files:
        print(f"未找到精确匹配的文件，尝试模糊匹配")
        files = [f for f in all_files if target_date in os.path.basename(f)]
    
    return sorted(files)

def merge_and_deduplicate_ips(target_date):
    """
    合并指定日期的文件，并去重IP地址
    """
    print(f"开始处理日期: {target_date}")
    
    # 确保日期格式正确
    if '-' in target_date:
        target_date_clean = target_date.replace('-', '')
    else:
        target_date_clean = target_date
    
    print(f"清理后的日期格式: {target_date_clean}")
    
    files = get_files_by_date(target_date_clean)
    
    if not files:
        print(f"❌ 未找到日期为 {target_date_clean} 的文件")
        # 显示最近的几个文件作为参考
        all_files = glob.glob("non_us_ips/non_us_ips_*.txt")
        if all_files:
            recent_files = sorted(all_files)[-5:]
            print("最近的文件:")
            for f in recent_files:
                print(f"  - {os.path.basename(f)}")
        return False
    
    print(f"找到 {len(files)} 个文件进行合并和去重:")
    for f in files:
        print(f"  - {os.path.basename(f)}")
    
    # 确保merged目录存在
    merged_dir = "non_us_ips/merged"
    os.makedirs(merged_dir, exist_ok=True)
    print(f"合并目录: {merged_dir} (存在: {os.path.exists(merged_dir)})")
    
    # 使用集合进行去重
    unique_ips = set()
    total_lines_processed = 0
    
    for file_path in files:
        try:
            print(f"处理文件: {os.path.basename(file_path)}")
            file_ips_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    total_lines_processed += 1
                    clean_ip = extract_clean_ip(line)
                    if clean_ip:
                        unique_ips.add(clean_ip)
                        file_ips_count += 1
            
            print(f"  从此文件提取了 {file_ips_count} 个唯一IP")
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    print(f"处理了 {total_lines_processed} 行，去重后得到 {len(unique_ips)} 个唯一IP地址")
    
    if not unique_ips:
        print("❌ 没有提取到任何有效的IP地址")
        # 显示一些原始数据来调试
        if files:
            sample_file = files[0]
            print(f"样本文件 {os.path.basename(sample_file)} 的前5行:")
            try:
                with open(sample_file, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if i >= 5:
                            break
                        print(f"  行 {i+1}: {repr(line)}")
            except Exception as e:
                print(f"读取样本文件失败: {e}")
        return False
    
    # 写入合并后的文件
    output_date = f"{target_date_clean[:4]}-{target_date_clean[4:6]}-{target_date_clean[6:8]}"
    merged_file = os.path.join(merged_dir, f"merged_ips_{output_date}.txt")
    
    try:
        with open(merged_file, 'w', encoding='utf-8') as f:
            # 写入文件头
            f.write(f"# 合并去重的非美国IP地址 - 日期: {output_date}\n")
            f.write(f"# 源日期: {target_date_clean}\n")
            f.write(f"# 唯一IP数量: {len(unique_ips)}\n")
            f.write(f"# 源文件数量: {len(files)}\n")
            f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # 按数字顺序写入IP
            sorted_ips = sorted(unique_ips, key=lambda ip: [int(part) for part in ip.split('.')])
            for ip in sorted_ips:
                f.write(ip + '\n')
        
        # 验证文件是否成功创建
        if os.path.exists(merged_file):
            file_size = os.path.getsize(merged_file)
            
            print(f"✅ 成功生成合并文件: {merged_file}")
            print(f"📏 文件大小: {file_size} 字节")
            print(f"🔢 包含 {len(unique_ips)} 个唯一IP")
            
            # 显示文件预览
            print("文件预览 (前5行):")
            with open(merged_file, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= 5:
                        break
                    print(f"  {line.strip()}")
            
            return True
        else:
            print(f"❌ 文件生成失败: {merged_file} 不存在")
            return False
            
    except Exception as e:
        print(f"❌ 写入合并文件时出错: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("=== 开始执行IP合并去重脚本 ===")
    
    # 获取目标日期参数
    if len(sys.argv) > 1:
        target_date = sys.argv[1]
        print(f"输入日期参数: {target_date}")
    else:
        # 使用前天日期
        target_date = (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')
        print(f"使用自动计算的前天日期: {target_date}")
    
    success = merge_and_deduplicate_ips(target_date)
    
    if success:
        print("🎉 合并去重成功完成")
        sys.exit(0)
    else:
        print("💥 合并去重失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
