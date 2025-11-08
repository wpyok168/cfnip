#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
import glob

def extract_original_line_info(line):
    """提取原始行的信息，完全保留原始格式"""
    line = line.rstrip('\n\r')  # 只移除行尾的换行符
    
    if not line or line.startswith('#'):
        return None
    
    # 检查是否包含IP地址模式（基本验证）
    if '.' not in line or len(line) < 7:  # 最小IP长度
        return None
    
    return line

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
    合并指定日期的文件，并去重IP地址，完全保留原始格式
    如果合并文件已存在，则采用追加模式
    合并成功后删除源文件
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
    
    # 使用集合存储唯一的行内容
    unique_lines = set()
    total_lines_processed = 0
    valid_lines_count = 0
    
    # 读取现有合并文件的内容（如果存在）
    output_date = f"{target_date_clean[:4]}-{target_date_clean[4:6]}-{target_date_clean[6:8]}"
    merged_file = os.path.join(merged_dir, f"merged_ips_{output_date}.txt")
    
    existing_lines = set()
    file_exists = os.path.exists(merged_file)
    
    if file_exists:
        print(f"📁 合并文件已存在: {os.path.basename(merged_file)}")
        print("🔍 读取现有文件内容...")
        try:
            with open(merged_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.rstrip('\n\r')
                    if line and not line.startswith('#'):  # 跳过空行和注释行
                        existing_lines.add(line)
            print(f"  从现有文件中读取了 {len(existing_lines)} 个有效行")
        except Exception as e:
            print(f"❌ 读取现有合并文件时出错: {e}")
            return False
    
    # 处理所有源文件
    for file_path in files:
        try:
            print(f"处理文件: {os.path.basename(file_path)}")
            file_valid_lines = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    total_lines_processed += 1
                    original_line = extract_original_line_info(line)
                    
                    if original_line:
                        file_valid_lines += 1
                        valid_lines_count += 1
                        unique_lines.add(original_line)
            
            print(f"  从此文件提取了 {file_valid_lines} 个有效行")
            
        except Exception as e:
            print(f"处理文件 {file_path} 时出错: {e}")
    
    print(f"处理了 {total_lines_processed} 行，从源文件中得到 {len(unique_lines)} 个唯一行")
    
    # 合并现有内容和新增内容
    if file_exists:
        combined_lines = existing_lines.union(unique_lines)
        new_lines_count = len(combined_lines) - len(existing_lines)
        print(f"📊 合并统计:")
        print(f"  - 现有文件行数: {len(existing_lines)}")
        print(f"  - 新增源文件行数: {len(unique_lines)}")
        print(f"  - 合并后总行数: {len(combined_lines)}")
        print(f"  - 新增唯一行数: {new_lines_count}")
        
        if new_lines_count == 0:
            print("ℹ️ 没有新增的唯一行，跳过文件更新")
            # 虽然没有新增内容，但仍然删除源文件
            print(f"\n🗑️ 开始删除已处理的源文件...")
            deleted_count = 0
            for file_path in files:
                try:
                    os.remove(file_path)
                    print(f"  已删除: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  删除失败 {os.path.basename(file_path)}: {e}")
            
            print(f"✅ 已删除 {deleted_count}/{len(files)} 个源文件")
            return True
    else:
        combined_lines = unique_lines
        new_lines_count = len(combined_lines)
        print(f"🆕 创建新合并文件，包含 {new_lines_count} 个唯一行")
    
    if not combined_lines:
        print("❌ 没有有效的行可以写入")
        return False
    
    # 写入合并后的文件
    try:
        mode = 'a' if file_exists else 'w'  # 追加模式或写入模式
        with open(merged_file, mode, encoding='utf-8') as f:
            if not file_exists:
                # 新文件：写入完整的文件头
                f.write(f"# 合并和去重后的非美国IP地址 - {output_date}\n")
                f.write(f"# 源数据日期: {target_date_clean}\n")
                f.write(f"# 唯一行数: {len(combined_lines)}\n")
                f.write(f"# 源文件数量: {len(files)}\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 格式: 完全保留原始格式 (IP:端口#注释)\n\n")
            else:
                # 追加模式：写入追加标记和新内容
                f.write(f"\n# 追加内容 - 处理时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 新增源文件: {len(files)} 个\n")
                f.write(f"# 新增唯一行: {new_lines_count} 个\n")
                f.write(f"# 当前总行数: {len(combined_lines)} 个\n\n")
            
            # 写入新的唯一行（排除已存在的行）
            if file_exists:
                new_unique_lines = unique_lines - existing_lines
                for line in new_unique_lines:
                    f.write(line + '\n')
            else:
                for line in combined_lines:
                    f.write(line + '\n')
        
        # 验证文件是否成功创建/更新
        if os.path.exists(merged_file):
            file_size = os.path.getsize(merged_file)
            
            if file_exists:
                print(f"✅ 成功更新合并文件: {merged_file}")
            else:
                print(f"✅ 成功创建合并文件: {merged_file}")
            
            print(f"📏 文件大小: {file_size} 字节")
            print(f"🔢 总行数: {len(combined_lines)} 个唯一行")
            
            # 显示文件预览
            print("文件预览 (最后10行):")
            with open(merged_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                start_index = max(0, len(lines) - 10)
                for i in range(start_index, len(lines)):
                    print(f"  {lines[i].strip()}")
            
            # 合并成功，删除源文件
            print(f"\n🗑️ 开始删除已处理的源文件...")
            deleted_count = 0
            for file_path in files:
                try:
                    os.remove(file_path)
                    print(f"  已删除: {os.path.basename(file_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"  删除失败 {os.path.basename(file_path)}: {e}")
            
            print(f"✅ 已删除 {deleted_count}/{len(files)} 个源文件")
            
            return True
        else:
            print(f"❌ 文件操作失败: {merged_file} 不存在")
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
        print("🎉 合并去重成功完成，源文件已删除")
        sys.exit(0)
    else:
        print("💥 合并去重失败，保留源文件")
        sys.exit(1)

if __name__ == "__main__":
    main()
