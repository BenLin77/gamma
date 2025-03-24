import os
import pandas as pd
from datetime import datetime, timedelta
import discord
from discord import Colour, File
import yfinance as yf
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import json

# 載入環境變數
load_dotenv()

def get_previous_trading_day(date):
    """獲取前一個交易日的日期"""
    current = date
    while True:
        current -= timedelta(days=1)
        # 跳過週末
        if current.weekday() < 5:
            return current

def parse_price_levels(line):
    """解析價格水平"""
    try:
        parts = line.split(':')
        if len(parts) < 2:
            print(f"行格式錯誤: {line}")
            return None, {}
            
        stock = parts[0]
        levels_str = parts[1]
        levels = {}
        
        # 分割成標籤=值的對
        items = levels_str.split('=')
        
        for i in range(len(items)-1):
            # 取得當前項和下一項
            current_item = items[i]
            next_item = items[i+1]
            
            # 從下一項中提取數值
            value = ""
            for char in next_item:
                if char.isdigit() or char == '.':
                    value += char
                else:
                    break
            
            if value:  # 如果找到數值
                value = float(value)
                # 從當前項中提取標籤
                if i == 0:
                    labels = current_item.split(',')
                else:
                    # 找到前一個數值的結尾位置
                    prev_value = ""
                    for char in current_item:
                        if char.isdigit() or char == '.':
                            prev_value += char
                        else:
                            break
                    labels = current_item[len(prev_value):].split(',')
                
                # 清理並儲存每個標籤
                for label in labels:
                    label = label.strip()
                    if label:  # 確保標籤不為空
                        levels[label] = value
        
        # 映射標籤到標準名稱
        standardized_levels = {}
        
        # 特殊處理 Gamma Flip：優先使用 GF，如果沒有則使用 GFCE
        if 'GF' in levels:
            standardized_levels['Gamma Flip'] = levels['GF']
        elif 'GFCE' in levels:
            standardized_levels['Gamma Flip'] = levels['GFCE']
            
        # 其他標籤的映射
        label_mapping = {
            'GFCE': 'Gamma Flip CE',      # Gamma Flip CE
            'GFLCE': 'Gamma Field CE',    # Gamma Field CE (不是 Gamma Flip CE)
            'PD': 'Put Dominate',         # Put Dominate
            'CD': 'Call Dominate',        # Call Dominate
            'PW': 'Put Wall',             # Put Wall
            'CW': 'Call Wall',            # Call Wall
            'KD': 'Key Delta',            # Key Delta
            'LG': 'Large Gamma',          # Large Gamma
            'IM+': 'Implied Movement +σ',  # Implied Movement +σ
            'IM-': 'Implied Movement -σ',  # Implied Movement -σ
            'IM2+': 'Implied Movement +2σ', # Implied Movement +2σ
            'IM2-': 'Implied Movement -2σ', # Implied Movement -2σ
        }
        
        # 轉換標籤
        for label, value in levels.items():
            if label in label_mapping:
                standard_label = label_mapping[label]
                if standard_label != 'Gamma Flip':  # 避免重複添加 Gamma Flip
                    standardized_levels[standard_label] = value
        
        # 調試輸出
        print(f"解析結果 {stock}: Gamma Flip={standardized_levels.get('Gamma Flip')}, Gamma Flip CE={standardized_levels.get('Gamma Flip CE')}, Gamma Field CE={standardized_levels.get('Gamma Field CE')}, Put Dominate={standardized_levels.get('Put Dominate')}")
            
        return stock, standardized_levels
    except Exception as e:
        print(f"解析價格水平時發生錯誤: {e}")
        return None, {}

def get_real_time_price(symbol):
    """獲取即時價格"""
    try:
        # 為指數添加前綴
        symbol_yf = f"^{symbol}" if symbol in ['SPX', 'VIX'] else symbol
        ticker = yf.Ticker(symbol_yf)
        data = ticker.history(period='1d')
        if not data.empty:
            return data['Close'].iloc[-1]
    except Exception as e:
        print(f"{symbol}: {str(e)}")
    return None

def create_market_table(market_data):
    """創建市場數據表格圖片"""
    # 定義表格數據
    columns = ['Symbol', 'Current Price', 'Gamma CE Env', 'Gamma Env', 'GF vs Prev', 'Prev GF', 'Gamma Flip', 'Gamma Flip CE', 'Prev GF CE']
    
    # 準備數據
    data = []
    special_notes = []  # 用於存儲特殊情況的說明
    
    for item in market_data:
        stock = item['stock']
        current_price = item.get('current_price', None)
        gamma_flip = item.get('gamma_flip', None)
        gamma_flip_ce = item.get('gamma_flip_ce', None)
        prev_gamma_flip = item.get('prev_gamma_flip', None)
        prev_gamma_flip_ce = item.get('prev_gamma_flip_ce', None)
        prev_prev_gamma_flip = item.get('prev_prev_gamma_flip', None)
        prev_day_price = item.get('prev_day_price', None)
        gamma_ce_env_days = item.get('gamma_ce_env_days', 0)
        gamma_env_days = item.get('gamma_env_days', 0)
        
        # 計算 Gamma Flip 變化
        gf_change = ""
        gf_pattern_found = False  # 用於標記是否已找到某種模式
        
        print(f"DEBUG - {stock} 的 Gamma Flip 數據:")
        print(f"  當前: {gamma_flip}")
        print(f"  昨日: {prev_gamma_flip}")
        print(f"  前日: {prev_prev_gamma_flip}")
        
        if gamma_flip is not None and prev_gamma_flip is not None:
            diff = gamma_flip - prev_gamma_flip
            if abs(diff) < 0.01:  # 考慮浮點數誤差
                gf_change = "Same"
                print(f"  計算結果: Same (diff={diff})")
            elif diff > 0:
                gf_change = f"+{diff:.2f}"
                print(f"  計算結果: +{diff:.2f}")
            else:
                gf_change = f"{diff:.2f}"
                print(f"  計算結果: {diff:.2f}")
        else:
            print(f"  計算結果: 空白 (原因: gamma_flip={gamma_flip}, prev_gamma_flip={prev_gamma_flip})")
        
        # 判斷Gamma環境
        daily_gamma = 'Positive' if gamma_flip_ce and current_price and current_price > gamma_flip_ce else 'Negative'
        all_gamma = 'Positive' if gamma_flip and current_price and current_price > gamma_flip else 'Negative'
        
        # 格式化Gamma環境顯示（加上維持天數）
        daily_gamma_display = f"{daily_gamma}"
        all_gamma_display = f"{all_gamma}"
        
        if gamma_ce_env_days > 0:
            daily_gamma_display = f"{daily_gamma} ({gamma_ce_env_days}d)"
        
        if gamma_env_days > 0:
            all_gamma_display = f"{all_gamma} ({gamma_env_days}d)"
        
        # 檢查是否首次跌破 Gamma Flip
        if (current_price and prev_day_price and gamma_flip and
            prev_day_price > gamma_flip and current_price < gamma_flip):
            special_notes.append({
                'stock': stock,
                'type': '跌破GF',
                'priority': 0,  # 最高優先級
                'message': f" {stock}: 價格跌破 Gamma Flip\n   昨收: {prev_day_price:.2f} ➡️ 現價: {current_price:.2f}\n   Gamma Flip: {gamma_flip:.2f}"
            })
        
        # 檢查是否首次突破 Gamma Flip
        if (current_price and prev_day_price and gamma_flip and
            prev_day_price < gamma_flip and current_price > gamma_flip):
            special_notes.append({
                'stock': stock,
                'type': '突破GF',
                'priority': 0,  # 最高優先級
                'message': f" {stock}: 價格突破 Gamma Flip\n   昨收: {prev_day_price:.2f} ➡️ 現價: {current_price:.2f}\n   Gamma Flip: {gamma_flip:.2f}"
            })

        # 添加到表格數據
        row = [
            stock,
            f"{current_price:.2f}" if current_price else "N/A",
            daily_gamma_display,
            all_gamma_display,
            gf_change,
            f"{prev_gamma_flip:.2f}" if prev_gamma_flip else "N/A",
            f"{gamma_flip:.2f}" if gamma_flip else "N/A",
            f"{gamma_flip_ce:.2f}" if gamma_flip_ce else "N/A",
            f"{prev_gamma_flip_ce:.2f}" if prev_gamma_flip_ce else "N/A"
        ]
        data.append(row)
    
    # 按優先級排序特殊情況提醒
    special_notes.sort(key=lambda x: (x['priority'], x['stock']))
    special_notes = [note['message'] for note in special_notes]
    
    # 創建圖片
    fig, ax = plt.figure(figsize=(16, len(data)*0.5 + 1)), plt.gca()
    ax.axis('tight')
    ax.axis('off')
    
    # 設置顏色映射函數
    def color_cells(text):
        if text == 'Positive':
            return 'blue'
        elif text == 'Negative':
            return 'red'
        else:
            return 'black'
    
    # 創建表格
    table = ax.table(
        cellText=data,
        colLabels=columns,
        loc='center',
        colColours=['#f2f2f2']*len(columns)
    )
    
    # 設置表格樣式
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)
    
    # 設置單元格顏色
    for i, row in enumerate(data):
        for j, cell in enumerate(row):
            if j == 2 or j == 3:  # Gamma環境列
                # 檢查是否包含天數信息
                is_positive = cell.startswith('Positive')
                cell_color = 'lightblue' if is_positive else 'lightcoral'
                table[(i+1, j)].set_facecolor(cell_color)
                table[(i+1, j)].set_text_props(color='white', weight='bold')
            elif j == 4:  # GF變化列
                if cell.startswith('+'):
                    table[(i+1, j)].set_facecolor('lightgreen')
                    table[(i+1, j)].set_text_props(weight='bold')
                elif cell.startswith('-'):
                    table[(i+1, j)].set_facecolor('lightcoral')
                    table[(i+1, j)].set_text_props(weight='bold')
                elif cell == "Same":
                    table[(i+1, j)].set_facecolor('lightyellow')
                    table[(i+1, j)].set_text_props(weight='bold')
    
    # 保存為圖片
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
    buf.seek(0)
    return buf, special_notes

async def send_market_status():
    """發送市場狀態到Discord"""
    base_path = "/home/ben/pCloudDrive/stock/GEX/GEX_file/tvcode"
    today = datetime.now()
    today_str = today.strftime("%Y%m%d")
    today_file = os.path.join(base_path, f"tvcode_{today_str}.txt")
    
    # 獲取前一個交易日
    prev_day = get_previous_trading_day(today)
    prev_day_str = prev_day.strftime("%Y%m%d")
    prev_file = os.path.join(base_path, f"tvcode_{prev_day_str}.txt")
    
    # 獲取前前一個交易日
    prev_prev_day = get_previous_trading_day(prev_day)
    prev_prev_day_str = prev_prev_day.strftime("%Y%m%d")
    prev_prev_file = os.path.join(base_path, f"tvcode_{prev_prev_day_str}.txt")
    
    gamma_history_file = os.path.join(base_path, "gamma_environment_history.json")
    gamma_history = {}
    try:
        with open(gamma_history_file, 'r') as f:
            gamma_history = json.load(f)
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"讀取Gamma環境歷史數據時發生錯誤: {e}")
    
    # 檢查今日文件是否存在
    if not os.path.exists(today_file):
        print(f"找不到今日的價格文件: {today_file}")
        # 嘗試找到最近的文件
        found = False
        test_date = today
        for _ in range(5):  # 嘗試往前找5天
            test_date = get_previous_trading_day(test_date)
            test_file = os.path.join(base_path, f"tvcode_{test_date.strftime('%Y%m%d')}.txt")
            if os.path.exists(test_file):
                today_file = test_file
                today_str = test_date.strftime("%Y%m%d")
                # 更新前一個交易日
                prev_day = get_previous_trading_day(test_date)
                prev_day_str = prev_day.strftime("%Y%m%d")
                prev_file = os.path.join(base_path, f"tvcode_{prev_day_str}.txt")
                # 更新前前一個交易日
                prev_prev_day = get_previous_trading_day(prev_day)
                prev_prev_day_str = prev_prev_day.strftime("%Y%m%d")
                prev_prev_file = os.path.join(base_path, f"tvcode_{prev_prev_day_str}.txt")
                found = True
                break
        if not found:
            print("無法找到最近的價格文件")
            return
    
    # 檢查前一個交易日文件是否存在
    if not os.path.exists(prev_file):
        print(f"找不到前一個交易日的價格文件: {prev_file}")
        # 嘗試找到更早的文件
        found = False
        test_date = prev_day
        for _ in range(5):  # 嘗試往前找5天
            test_date = get_previous_trading_day(test_date)
            test_file = os.path.join(base_path, f"tvcode_{test_date.strftime('%Y%m%d')}.txt")
            if os.path.exists(test_file):
                prev_file = test_file
                prev_day_str = test_date.strftime("%Y%m%d")
                # 更新前前一個交易日
                prev_prev_day = get_previous_trading_day(test_date)
                prev_prev_day_str = prev_prev_day.strftime("%Y%m%d")
                prev_prev_file = os.path.join(base_path, f"tvcode_{prev_prev_day_str}.txt")
                found = True
                break
        if not found:
            print("無法找到更早的價格文件進行比較")
    
    market_data = []
    
    # 讀取昨日數據（如果存在）
    prev_data = {}
    if os.path.exists(prev_file):
        try:
            print(f"正在讀取昨日數據文件: {prev_file}")
            with open(prev_file, 'r') as f:
                for line in f:
                    result = parse_price_levels(line.strip())
                    if result[0] is not None:  # 確保解析成功
                        stock, levels = result
                        prev_data[stock] = {
                            'gamma_flip': levels.get('Gamma Flip'),
                            'gamma_flip_ce': levels.get('Gamma Flip CE'),
                            'put_dominate': levels.get('Put Dominate')
                        }
                        print(f"昨日數據 - {stock}: Gamma Flip = {levels.get('Gamma Flip')}")
        except Exception as e:
            print(f"讀取昨日數據時發生錯誤: {e}")
    
    # 建立昨日數據的映射關係
    prev_gamma_flips = {}
    for stock, data in prev_data.items():
        prev_gamma_flips[stock] = data.get('gamma_flip')
        print(f"設置 {stock} 的昨日 Gamma Flip: {data.get('gamma_flip')}")
    
    # 讀取前前日數據（如果存在）
    prev_prev_data = {}
    if os.path.exists(prev_prev_file):
        try:
            with open(prev_prev_file, 'r') as f:
                for line in f:
                    result = parse_price_levels(line.strip())
                    if result[0] is not None:  # 確保解析成功
                        stock, levels = result
                        prev_prev_data[stock] = {
                            'gamma_flip': levels.get('Gamma Flip'),
                            'gamma_flip_ce': levels.get('Gamma Flip CE'),
                            'put_dominate': levels.get('Put Dominate')
                        }
        except Exception as e:
            print(f"讀取前前日數據時發生錯誤: {e}")
    
    # 獲取昨日股價數據 - 使用批量下載提高效率
    stocks = list(set(list(prev_data.keys()) + list(prev_prev_data.keys())))
    # 修正指數代碼
    stocks_yf = [f"^{stock}" if stock in ['SPX', 'VIX'] else stock for stock in stocks]
    
    prev_day_prices = {}
    try:
        # 批量下載所有股票的數據
        data = yf.download(
            stocks_yf,
            start=prev_day - timedelta(days=1),
            end=prev_day + timedelta(days=1),
            group_by='ticker'
        )
        
        # 處理數據
        if len(stocks) == 1:  # 如果只有一個股票，數據結構會不同
            if not data.empty:
                stock = stocks[0]
                prev_day_prices[stock] = data['Close'].iloc[-1]
        else:
            for i, stock in enumerate(stocks):
                try:
                    stock_yf = stocks_yf[i]
                    if not data[stock_yf].empty:
                        prev_day_prices[stock] = data[stock_yf]['Close'].iloc[-1]
                except Exception as e:
                    print(f"處理 {stock} 昨日價格時發生錯誤: {e}")
    except Exception as e:
        print(f"批量下載股價數據時發生錯誤: {e}")
    
    # 處理每個股票
    with open(today_file, 'r') as f:
        today_lines = f.readlines()
    
    for line in today_lines:
        try:
            result = parse_price_levels(line.strip())
            if result[0] is None:  # 如果解析失敗，跳過此行
                continue
                
            stock = result[0]
            levels = result[1]
            
            # 獲取當前價格
            current_price = get_real_time_price(stock)
            
            # 獲取今日數據
            gamma_flip = levels.get('Gamma Flip')
            gamma_flip_ce = levels.get('Gamma Flip CE')
            put_dominate = levels.get('Put Dominate')
            
            # 獲取昨日數據
            prev_gamma_flip = prev_gamma_flips.get(stock)
            prev_gamma_flip_ce = None
            prev_put_dominate = None
            
            if stock in prev_data:
                prev_gamma_flip_ce = prev_data[stock].get('gamma_flip_ce')
                prev_put_dominate = prev_data[stock].get('put_dominate')
            elif stock in prev_prev_data:  # 如果昨日數據不存在，嘗試使用前前日數據
                prev_gamma_flip_ce = prev_prev_data[stock].get('gamma_flip_ce')
                prev_put_dominate = prev_prev_data[stock].get('put_dominate')
            
            # 獲取前前日數據
            prev_prev_gamma_flip = None
            if stock in prev_prev_data:
                prev_prev_gamma_flip = prev_prev_data[stock].get('gamma_flip')
            
            # 獲取昨日價格
            prev_day_price = prev_day_prices.get(stock, None)
            
            # 計算當前Gamma環境
            current_gamma_ce_env = 'Positive' if gamma_flip_ce and current_price and current_price > gamma_flip_ce else 'Negative'
            current_gamma_env = 'Positive' if gamma_flip and current_price and current_price > gamma_flip else 'Negative'
            
            # 初始化歷史記錄（如果不存在）
            if stock not in gamma_history:
                gamma_history[stock] = {
                    'ce_env': {'status': current_gamma_ce_env, 'days': 1},
                    'env': {'status': current_gamma_env, 'days': 1}
                }
            else:
                # 更新CE環境天數
                if gamma_history[stock]['ce_env']['status'] == current_gamma_ce_env:
                    gamma_history[stock]['ce_env']['days'] += 1
                else:
                    gamma_history[stock]['ce_env'] = {'status': current_gamma_ce_env, 'days': 1}
                
                # 更新全部合約環境天數
                if gamma_history[stock]['env']['status'] == current_gamma_env:
                    gamma_history[stock]['env']['days'] += 1
                else:
                    gamma_history[stock]['env'] = {'status': current_gamma_env, 'days': 1}
            
            # 添加到市場數據列表
            stock_data = {
                'stock': stock,
                'current_price': current_price,
                'gamma_flip': gamma_flip,
                'gamma_flip_ce': gamma_flip_ce,
                'prev_gamma_flip': prev_gamma_flip,
                'prev_gamma_flip_ce': prev_gamma_flip_ce,
                'prev_prev_gamma_flip': prev_prev_gamma_flip,
                'prev_day_price': prev_day_price,
                'gamma_ce_env_days': gamma_history[stock]['ce_env']['days'],
                'gamma_env_days': gamma_history[stock]['env']['days']
            }
            
            market_data.append(stock_data)
            
        except Exception as e:
            current_stock = "未知股票"
            try:
                if 'stock' in locals():
                    current_stock = stock
            except:
                pass
            print(f"處理 {current_stock} 數據時發生錯誤: {e}")
            continue
    
    # 保存更新後的Gamma環境歷史數據
    try:
        with open(gamma_history_file, 'w') as f:
            json.dump(gamma_history, f)
    except Exception as e:
        print(f"保存Gamma環境歷史數據時發生錯誤: {e}")
    
    if not market_data:
        print("沒有有效的市場數據")
        return
    
    # 創建表格圖片
    table_image, special_notes = create_market_table(market_data)
    
    # 發送到Discord
    channel_id = 1351065456257273947
    channel = client.get_channel(channel_id)
    
    if channel:
        # 創建說明訊息
        today_date = datetime.strptime(today_str, "%Y%m%d").strftime("%Y/%m/%d")
        prev_date = datetime.strptime(prev_day_str, "%Y%m%d").strftime("%Y/%m/%d")
        message = f"**市場 Gamma 環境報告** ({today_date})\n"
        message += f"與前一交易日 ({prev_date}) 比較\n"
        message += f"綠色: Gamma Flip 比前一日高 (看漲)\n"
        message += f"紅色: Gamma Flip 比前一日低 (看跌)\n"
        message += f"黃色: Gamma Flip 與前一日相同\n"
        
        # 添加特殊情況說明
        if special_notes:
            message += "\n**特殊情況提醒:**\n"
            for note in special_notes:
                message += f"- {note}\n"
        
        # 發送訊息和表格圖片
        await channel.send(message, file=discord.File(fp=table_image, filename="market_status.png"))
    else:
        print("無法找到指定的Discord頻道")

async def main():
    """主程式"""
    await send_market_status()
    await client.close()

if __name__ == "__main__":
    # Discord設置
    intents = discord.Intents.default()
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        print(f'Bot已登入為 {client.user}')
        await main()

    # 運行 bot
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("錯誤：找不到 DISCORD_BOT_TOKEN 環境變數")
    else:
        client.run(token)
