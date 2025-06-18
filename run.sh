#!/bin/bash

# GEX 資料處理腳本
# 執行順序：數據收集 -> 轉換 -> 提取

set -e

cd /home/ben/code/gex

LOG_FILE="/home/ben/Downloads/crontab.log"
PYTHON_CMD="/home/ben/.local/bin/uv run python"

# 日誌函數
log_info() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [INFO] $1" >> "$LOG_FILE"
}

log_error() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - [ERROR] $1" >> "$LOG_FILE"
}

# 步驟 1: 執行 playwright_record.py (數據收集)
log_info "開始執行數據收集..."
if /home/ben/.local/bin/uv run python playwright_record.py --auth auth.json --config config.json >> "$LOG_FILE" 2>&1; then
    log_info "數據收集完成"
else
    log_error "數據收集失敗"
fi
sleep 60

# 步驟 2: 執行 gamma_converter.py (數據轉換)
log_info "開始執行數據轉換..."
if /home/ben/.local/bin/uv run python gamma_converter.py --force --overwrite >> "$LOG_FILE" 2>&1; then
    log_info "數據轉換完成"
else
    log_error "數據轉換失敗"
fi
sleep 150

# 步驟 3: 執行 extract_gamma_from_html.py (提取 gamma 數據)
log_info "開始執行 gamma 數據提取..."
if /home/ben/.local/bin/uv run python extract_gamma_from_html.py >> "$LOG_FILE" 2>&1; then
    log_info "gamma 數據提取完成"
else
    log_error "gamma 數據提取失敗"
fi
sleep 10

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
    echo ""
    echo "注意：Gamma 交易功能已移至 /home/ben/code/gex_trade 專案"
fi

log_info "run.sh 執行完成"

