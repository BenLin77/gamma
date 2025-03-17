# GEX 股票分析系統

這是一個綜合性的股票分析系統，專注於 Gamma Exposure (GEX) 分析和自動化數據採集。

## 主要功能

### 1. 數據視覺化 (gamma_view.py)
- 互動式 K 線圖顯示
- Gamma 指標疊加顯示
- VIX 即時數據整合
- 支援多股票數據
- 自定義時間範圍查看
- 指標統計分析：
  * 穿越次數統計
  * 向下穿越機率
  * 平均持續時間
  * 最近價格距離

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

### 5. 數據備份 (backup_gex.py)
- 自動備份歷史數據
- 維護數據完整性

### 6. Put Dominate 分析 (put_dom_trade.py)
- 自動分析多個股票的 Put Dominate 數據
- 計算並顯示：
  * Gamma Flip
  * Gamma Flip CE
  * Put Dominate
  * Put Dominate 變化
  * Daily Gamma Environment
  * All Contracts Gamma Environment
- 特殊情況提醒：
  * V型反轉（看漲）
  * 倒V型反轉（看跌）
  * 首次跌破 Gamma Flip
- 自動發送分析結果到 Discord
- 支援批量下載歷史價格數據

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
- 設置 auth.json 認證文件

## 使用說明

### 數據視覺化 (gamma_view.py)
```bash
pipenv run streamlit run gamma_view.py
```

功能特點：
1. 基本功能：
   - 上傳 Excel 文件
   - 選擇股票代碼
   - 自定義時間範圍
   - 多重指標疊加

2. 指標分析：
   - 選擇多個技術指標
   - 查看指標統計數據
   - 分析指標有效性

3. VIX 整合：
   - 自動獲取 VIX 數據
   - 雙 Y 軸顯示
   - 即時數據同步
   - 可選擇性顯示

4. 數據統計：
   - 指標穿越統計
   - 機率分析
   - 持續時間計算
   - 價格距離分析

### 數據採集 (playwright_record.py)
```bash
# 基本使用
python playwright_record.py

# 參數說明
--auth          認證文件路徑 (預設: auth.json)
--config        配置文件路徑 (預設: config.json)
--download-dir  下載目錄路徑 (預設: /home/ben/pCloudDrive/stock/GEX/GEX_file/)

# 範例
python playwright_record.py --auth ming_auth.json --config custom_config.json
```

### 數據轉換 (gamma_converter.py)
```bash
# 基本使用
python gamma_converter.py

# 參數說明
-r, --reverse   將簡化格式轉換回原始格式
-p, --path      指定 GEX 文件路徑
-d, --debug     顯示調試信息
-f, --file      指定要處理的文件名
--overwrite     直接覆蓋原始文件

# 範例
python gamma_converter.py -f tvcode_20240312.txt
```

### Put Dominate 分析
```bash
pipenv run python put_dom_trade.py
```

功能特點：
1. 數據分析：
   - 自動計算多個關鍵指標
   - 追蹤 Put Dominate 趨勢變化
   - 識別重要市場轉折點

2. 趨勢反轉偵測：
   - V型反轉（看漲信號）
   - 倒V型反轉（看跌信號）
   - 變化幅度過濾（>1.0）

3. Gamma 環境分析：
   - Daily Gamma Environment
   - All Contracts Gamma Environment
   - Gamma Flip 突破提醒

4. 自動化報告：
   - 生成美觀的表格圖片
   - Discord 自動通知
   - 中文說明訊息

### Discord 通知
```bash
pipenv run python sending_discord.py
```

### 自動化運行
```bash
./run.sh
```

## 配置文件說明

### config.json
```json
{
    "tickers": [
        "spx", "qqq", "iwm", "smh", "vix",
        "smci", "nvda", "tsla", "uvix", "svix", "tlt"
    ],
    "download_settings": {
        "wait_time": {
            "page_load": 15,
            "gamma_load": 15,
            "smile_load": 20,
            "tvcode_load": 45
        },
        "retries": 3
    }
}
```

## 檔案結構
- `gamma_view.py`: 視覺化界面
- `playwright_record.py`: 數據採集
- `sending_discord.py`: Discord 通知
- `gamma_converter.py`: 數據轉換
- `backup_gex.py`: 數據備份
- `put_dom_trade.py`: Put Dominate 分析

## 注意事項
1. 請確保已安裝所有必要的依賴
2. 運行前請確認配置文件設置正確
3. 建議定期備份重要數據

## 開發環境
- Python 3.12
- Pipenv 虛擬環境
- Playwright 自動化測試
- Streamlit 視覺化框架

## 更新日誌
- 2024-03-17: 新增 Put Dominate 分析功能
- 2024-03-12: 新增 VIX 數據整合
- 2024-03-12: 優化視覺化界面
- 2024-03-10: 更新數據備份功能 