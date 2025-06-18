# Gamma 交易系統

基於 SPX Gamma 層級的自動化期貨交易系統。

## 快速開始

```bash
# 測試 IB 連接
./run_trading.sh test

# 啟動監控（模擬模式）
./run_trading.sh monitor

# 檢查狀態
./run_trading.sh status

# 停止監控
./run_trading.sh stop
```

## 主要檔案

- `gamma_config.yaml` - 交易配置
- `ibkr_order.py` - 主程式
- `run_trading.sh` - 管理腳本
- `performance_analyzer.py` - 績效分析

## 期貨合約自動管理

系統會自動選擇合適的期貨合約，避免交易接近到期的合約。

更多詳細說明請參考 `gamma_trading_guide.md`。 