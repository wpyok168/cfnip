name: 🌐 收集IP地址

on:
  schedule:
    - cron: '30 * * * *'
  workflow_dispatch:
    inputs:
      reason:
        description: '手动触发原因'
        required: false
        default: '手动执行'

env:
  PYTHON_VERSION: '3.10'
  RETAIN_DAYS: 0
  KEEP_MINIMUM_RUNS: 5

permissions:
  contents: write

jobs:
  collect-ip-addresses:
    name: 🚀 收集IP地址
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - name: 📥 检出仓库
        uses: actions/checkout@v4

      - name: 🐍 设置Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: 📦 安装依赖
        run: |
          python -m pip install --upgrade pip
          pip install requests

      - name: 🌍 收集IP地址
        id: ip-collection
        run: |
          echo "🕸️ 开始收集IP地址..."
          start_time=$(date +%s)
          
          # 运行Python脚本并捕获退出码
          if python cf_ip_collector.py; then
            end_time=$(date +%s)
            duration=$((end_time - start_time))
            echo "✅ IP地址收集完成"
            echo "⏱️ 执行时间: ${duration} 秒"
            echo "result=success" >> $GITHUB_OUTPUT
          else
            echo "❌ IP地址收集失败"
            echo "result=failure" >> $GITHUB_OUTPUT
            # 不立即退出，继续检查文件状态
          fi

      - name: 🔍 检查文件状态
        id: file-check
        run: |
          echo "📋 检查文件状态..."
          
          # 检查文件是否存在且非空
          files_exist=true
          files_non_empty=true
          
          if [ -f "ip.txt" ]; then
            ip_count=$(wc -l < ip.txt | tr -d ' ')
            echo "📄 ip.txt: $ip_count 行"
            if [ $ip_count -eq 0 ]; then
              files_non_empty=false
              echo "⚠️ ip.txt 文件为空"
            fi
          else
            files_exist=false
            echo "❌ ip.txt 文件不存在"
          fi
          
          if [ -f "ipv6.txt" ]; then
            ipv6_count=$(wc -l < ipv6.txt | tr -d ' ')
            echo "📄 ipv6.txt: $ipv6_count 行"
            if [ $ipv6_count -eq 0 ]; then
              files_non_empty=false
              echo "⚠️ ipv6.txt 文件为空"
            fi
          else
            files_exist=false
            echo "❌ ipv6.txt 文件不存在"
          fi
          
          echo "files_exist=$files_exist" >> $GITHUB_OUTPUT
          echo "files_non_empty=$files_non_empty" >> $GITHUB_OUTPUT
          echo "ip_count=$ip_count" >> $GITHUB_OUTPUT
          echo "ipv6_count=$ipv6_count" >> $GITHUB_OUTPUT

      - name: 📊 检查变更
        id: changes-check
        run: |
          echo "📊 检查文件变更..."
          if git diff --quiet HEAD -- ip.txt ipv6.txt 2>/dev/null; then
            echo "📭 未检测到变更"
            echo "has_changes=false" >> $GITHUB_OUTPUT
          else
            echo "📬 检测到变更"
            echo "has_changes=true" >> $GITHUB_OUTPUT
          fi

      - name: 💾 提交变更
        id: auto-commit
        if: steps.changes-check.outputs.has_changes == 'true' && steps.file-check.outputs.files_exist == 'true' && steps.file-check.outputs.files_non_empty == 'true'
        uses: stefanzweifel/git-auto-commit-action@v4
        with:
          commit_message: |
            chore: 自动更新IP地址
            
            • IPv4: ${{ steps.file-check.outputs.ip_count }} 个地址
            • IPv6: ${{ steps.file-check.outputs.ipv6_count }} 个地址
            • 时间: $(date -u +'%Y-%m-%d %H:%M:%S UTC')
          file_pattern: |
            ip.txt
            ipv6.txt
            cf_ip_results/

      - name: 📈 生成总结
        if: always()
        run: |
          echo "## IP地址收集结果" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          echo "### 文件状态" >> $GITHUB_STEP_SUMMARY
          echo "- IPv4地址: ${{ steps.file-check.outputs.ip_count }} 个" >> $GITHUB_STEP_SUMMARY
          echo "- IPv6地址: ${{ steps.file-check.outputs.ipv6_count }} 个" >> $GITHUB_STEP_SUMMARY
          echo "" >> $GITHUB_STEP_SUMMARY
          
          if steps.file-check.outputs.files_exist == 'true' && steps.file-check.outputs.files_non_empty == 'true'; then
            if steps.changes-check.outputs.has_changes == 'true'; then
              echo "✅ **文件已更新并提交**" >> $GITHUB_STEP_SUMMARY
            else
              echo "ℹ️ **文件无变更**" >> $GITHUB_STEP_SUMMARY
            fi
          else
            echo "❌ **文件生成失败**" >> $GITHUB_STEP_SUMMARY
          fi

      - name: ❌ 失败处理
        if: steps.file-check.outputs.files_exist != 'true' || steps.file-check.outputs.files_non_empty != 'true'
        run: |
          echo "❌ IP地址收集失败"
          echo "请检查以下可能的问题："
          echo "1. 网络连接问题"
          echo "2. 数据源URL失效"
          echo "3. API限制"
          exit 1
