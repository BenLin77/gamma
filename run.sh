#!/bin/bash

# GEX 資料處理腳本
# 執行順序：更新認證文件 -> 數據收集 -> 轉換 -> 提取

set -e

cd /home/ben/code/gex

LOG_FILE="/home/ben/Downloads/crontab.log"
PYTHON_CMD="/home/ben/.local/bin/uv run python"

# 步驟 0: 更新認證文件
cp -f "/home/ben/pCloudDrive/stock/GEX/code/auth.json" "./auth.json"


# 日誌函數
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] $1" >> "$LOG_FILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] $1" >> "$LOG_FILE"
}

# 步驟 1: 執行 playwright_record.py (數據收集)
log_info "開始執行數據收集..."
/home/ben/.local/bin/uv run python playwright_record.py --auth auth.json --config config.json >> "$LOG_FILE" 2>&1;
sleep 60

# 步驟 2: 執行 gamma_converter.py (數據轉換)
log_info "開始執行數據轉換..."
/home/ben/.local/bin/uv run python gamma_converter.py --force --overwrite >> "$LOG_FILE" 2>&1;

sleep 150

# 步驟 3: 執行 extract_gamma_from_html.py (提取 gamma 數據)
log_info "開始執行 gamma 數據提取..."
/home/ben/.local/bin/uv run python extract_gamma_from_html.py >> "$LOG_FILE" 2>&1

sleep 10

# 步驟 4: 執行 sending_discord.py (發送到 Discord)
log_info "開始發送資料到 Discord..."
/home/ben/.local/bin/uv run python sending_discord.py >> "$LOG_FILE" 2>&1

sleep 5

log_info "GEX 資料處理流程完成"

# 顯示幫助資訊
if [[ "${1:-}" == "help" || "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo "GEX 資料處理系統"
    echo "使用方法:"
    echo "  $0                    # 執行完整資料處理流程"
    echo ""
    echo "處理流程："
    echo "  1. 數據收集 (playwright_record.py)"
    echo "  2. 數據轉換 (gamma_converter.py)"
    echo "  3. Gamma 數據提取 (extract_gamma_from_html.py)"
    echo "  4. 發送到 Discord (sending_discord.py)"
    echo ""
    echo "注意：Gamma 交易功能已移至 /home/ben/code/gex_trade 專案"
fi

log_info "run.sh 執行完成"

