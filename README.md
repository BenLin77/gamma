# GEX 股票分析系統

這是一個綜合性的股票分析系統，專注於 Gamma Exposure (GEX) 分析和自動化交易。

## 主要功能

### 1. 數據視覺化 (gamma_view.py)
- 互動式 K 線圖顯示
- Gamma 指標疊加顯示
- 支援多股票數據
- 自定義時間範圍查看

### 2. 數據採集 (playwright_record.py)
- 自動化數據採集
- 支援多股票數據下載
- 包含 Gamma、Smile 圖表擷取
- TV Code 文本擷取

### 3. Discord 通知 (sending_discord.py)
- 自動發送分析結果到 Discord
- 支援圖片和文本消息
- 多頻道訊息分發

### 4. 數據處理 (gamma_converter.py)
- Gamma 數據轉換和處理
- 數據格式標準化
- Excel 檔案處理

### 5. 交易系統 (trade_gamma.py, ibkr_order.py)
- 基於 Gamma 的交易策略
- Interactive Brokers 自動下單
- 風險管理

### 6. 市場分析 (market_analyzer.py)
- 綜合市場分析
- 技術指標計算
- 市場趨勢判斷

### 7. 數據備份 (backup_gex.py)
- 自動備份歷史數據
- 維護數據完整性

## 安裝指南

1. 安裝依賴：
```bash
# 使用 pipenv
pipenv install

# 或使用 pip
pip install -r requirements.txt
```

2. 設置配置文件：
- 配置 Discord webhook (如需使用通知功能)
- 設置 IBKR 帳戶資訊 (如需使用交易功能)

## 使用說明

### 數據視覺化
```bash
pipenv run streamlit run gamma_view.py
```

### 數據採集
```bash
pipenv run python playwright_record.py
```

### Discord 通知
```bash
pipenv run python sending_discord.py
```

### 自動化運行
```bash
./run.sh
```

## 檔案結構
- `gamma_view.py`: 視覺化界面
- `playwright_record.py`: 數據採集
- `sending_discord.py`: Discord 通知
- `gamma_converter.py`: 數據轉換
- `trade_gamma.py`: 交易策略
- `ibkr_order.py`: IBKR 下單
- `market_analyzer.py`: 市場分析
- `backup_gex.py`: 數據備份
- `analysis_gamma.py`: Gamma 分析

## 注意事項
1. 請確保已安裝所有必要的依賴
2. 運行前請確認配置文件設置正確
3. 建議先在測試環境中運行交易相關功能

## 開發環境
- Python 3.12
- Pipenv 虛擬環境
- Playwright 自動化測試
- Streamlit 視覺化框架

## 更新日誌
- 2024-03-12: 新增視覺化界面
- 2024-02-21: 更新交易系統
- 2024-02-12: 優化市場分析功能 