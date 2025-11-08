name: 合并和去重非美国IP

on:
  schedule:
    - cron: '0 17 * * *'
  workflow_dispatch:
    inputs:
      date_override:
        description: '指定日期 (YYYY-MM-DD)，默认为昨天'
        required: false
        default: ''
        type: string

permissions:
  contents: write

jobs:
  merge-files:
    runs-on: ubuntu-latest
    
    steps:
      - name: 检出代码库
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          
      - name: 显示代码库结构
        run: |
          echo "=== 代码库结构 ==="
          find . -name "non_us_ips_*.txt" | head -10
          echo "=== non_us_ips 目录内容 ==="
          ls -la non_us_ips/ || echo "non_us_ips 目录不存在"
          
      - name: 计算目标日期
        id: date_calc
        run: |
          export TZ='Asia/Shanghai'
          if [ -n "${{ github.event.inputs.date_override }}" ]; then
            TARGET_DATE="${{ github.event.inputs.date_override }}"
          else
            TARGET_DATE=$(date -d "1 days ago" +%Y%m%d)
          fi
          echo "target_date=$TARGET_DATE" >> $GITHUB_OUTPUT
          echo "目标处理日期: $TARGET_DATE"
          
      - name: 合并和去重IP地址
        run: |
          TARGET_DATE="${{ steps.date_calc.outputs.target_date }}"
          echo "执行合并脚本，日期: $TARGET_DATE"
          python .github/scripts/merge_non_us_ips.py "$TARGET_DATE"
          
      - name: 清理旧文件
        run: |
          python .github/scripts/cleanup_old_files.py
          
      - name: 提交和推送更改
        run: |
          git config --global user.email "github-actions[bot]@users.noreply.github.com"
          git config --global user.name "github-actions[bot]"
          
          # 添加所有更改（包括删除的文件）
          git add -A
          
          # 检查是否有更改需要提交
          if git diff --cached --quiet; then
            echo "🟡 没有检测到更改，跳过提交"
          else
            echo "🟢 检测到更改，准备提交"
            # 获取删除的文件列表
            DELETED_FILES=$(git diff --cached --name-status | grep "^D" | wc -l)
            ADDED_FILES=$(git diff --cached --name-status | grep "^A" | wc -l)
            git commit -m "自动: 合并和去重非美国IP地址 ${{ steps.date_calc.outputs.target_date }} [删除$DELETED_FILES个源文件，添加$ADDED_FILES个合并文件]"
            git push
            echo "✅ 更改已提交并推送"
          fi
