#!/usr/bin/env python3
import os
import sys
from datetime import datetime

def debug_file_system():
    """调试文件系统状态"""
    print("=== 文件系统调试信息 ===")
    
    # 检查工作目录
    print(f"当前工作目录: {os.getcwd()}")
    
    # 检查 non_us_ips 目录
    base_dir = "non_us_ips"
    if os.path.exists(base_dir):
        print(f"✅ {base_dir} 目录存在")
        print("目录内容:")
        for root, dirs, files in os.walk(base_dir):
            level = root.replace(base_dir, '').count(os.sep)
            indent = ' ' * 2 * level
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                if file.endswith('.txt'):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    print(f'{subindent}{file} ({file_size} bytes)')
    else:
        print(f"❌ {base_dir} 目录不存在")
        
    # 检查 merged 目录和文件
    merged_dir = "non_us_ips/merged"
    if os.path.exists(merged_dir):
        print(f"\n✅ {merged_dir} 目录存在")
        merged_files = [f for f in os.listdir(merged_dir) if f.endswith('.txt')]
        if merged_files:
            print("合并文件:")
            for file in sorted(merged_files)[-5:]:  # 显示最近5个文件
                file_path = os.path.join(merged_dir, file)
                file_size = os.path.getsize(file_path)
                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                print(f"  {file} ({file_size} bytes, 修改时间: {mtime})")
                
                # 显示文件内容前几行
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[:3]
                    print("    样本内容:")
                    for line in lines[:3]:
                        print(f"      {line.strip()}")
                except Exception as e:
                    print(f"    读取文件失败: {e}")
        else:
            print("  ❌ 没有合并文件")
    else:
        print(f"❌ {merged_dir} 目录不存在")

if __name__ == "__main__":
    debug_file_system()
