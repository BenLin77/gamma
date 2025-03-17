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
        pairs = levels_str.split('=')
        
        for i in range(len(pairs) - 1):  # 最後一個元素沒有值
            label_part = pairs[i]
            value_part = pairs[i + 1]
            
            # 找到值部分的數字
            value_digits = ""
            for char in value_part:
                if char.isdigit() or char == '.':
                    value_digits += char
                else:
                    break
                    
            if value_digits:
                value = float(value_digits)
                
                # 處理標籤部分
                if i == 0:  # 第一個元素
                    labels = label_part.split(',')
                else:
                    # 找到上一個值的結尾位置
                    prev_value = pairs[i-1]
                    prev_digits = ""
                    for char in prev_value:
                        if char.isdigit() or char == '.':
                            prev_digits += char
                        else:
                            break
                    
                    # 提取標籤部分
                    label_start = len(prev_digits)
                    labels = prev_value[label_start:].split(',')
                
                # 添加到字典
                for label in labels:
                    if label:  # 確保標籤不為空
                        levels[label] = value
        
        # 映射標籤到標準名稱
        label_mapping = {
            'GF': 'Gamma Flip',
            'GFCE': 'Gamma Flip CE',
            'PD': 'Put Dominate',
            'GFLCE': 'Gamma Flip CE',
        }
        
        # 轉換標籤
        standardized_levels = {}
        for label, value in levels.items():
            standard_label = label_mapping.get(label, label)
            standardized_levels[standard_label] = value
        
        # 調試輸出
        print(f"解析結果 {stock}: Gamma Flip={standardized_levels.get('Gamma Flip')}, Gamma Flip CE={standardized_levels.get('Gamma Flip CE')}, Put Dominate={standardized_levels.get('Put Dominate')}")
            
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
    columns = ['Symbol', 'Current Price', 'Gamma Flip', 'Gamma Flip CE', 'Put Dominate', 'PD vs Prev', 'Daily Gamma Env', 'All Contracts Gamma Env']
    
    # 準備數據
    data = []
    special_notes = []  # 用於存儲特殊情況的說明
    
    for item in market_data:
        stock = item['stock']
        current_price = item.get('current_price', None)
        gamma_flip = item.get('gamma_flip', None)
        gamma_flip_ce = item.get('gamma_flip_ce', None)
        put_dominate = item.get('put_dominate', None)
        prev_put_dominate = item.get('prev_put_dominate', None)
        prev_prev_put_dominate = item.get('prev_prev_put_dominate', None)
        prev_day_price = item.get('prev_day_price', None)
        
        # 計算 Put Dominate 變化
        pd_change = ""
        pd_trend_reversed = False
        
        if put_dominate is not None and prev_put_dominate is not None:
            diff = put_dominate - prev_put_dominate
            if abs(diff) < 0.01:  # 考慮浮點數誤差
                pd_change = "Same"
            elif diff > 0:
                pd_change = f"+{diff:.2f}"
                # 檢查是否從下降轉為上升
                # 條件：前天 > 昨天，今天 > 昨天（V型反轉）
                if (prev_prev_put_dominate is not None and 
                    prev_prev_put_dominate > prev_put_dominate and 
                    put_dominate > prev_put_dominate and
                    abs(put_dominate - prev_put_dominate) > 1.0):  # 確保變化足夠大
                    pd_trend_reversed = True
                    special_notes.append(f"{stock}: Put Dominate V型反轉向上 ({prev_prev_put_dominate:.2f} -> {prev_put_dominate:.2f} -> {put_dominate:.2f})")
            else:
                pd_change = f"{diff:.2f}"
                # 檢查是否從上升轉為下降
                # 條件：前天 < 昨天，今天 < 昨天（倒V型反轉）
                if (prev_prev_put_dominate is not None and 
                    prev_prev_put_dominate < prev_put_dominate and 
                    put_dominate < prev_put_dominate and
                    abs(put_dominate - prev_put_dominate) > 1.0):  # 確保變化足夠大
                    pd_trend_reversed = True
                    special_notes.append(f"{stock}: Put Dominate 倒V型反轉向下 ({prev_prev_put_dominate:.2f} -> {prev_put_dominate:.2f} -> {put_dominate:.2f})")
        
        # 判斷Gamma環境
        daily_gamma = 'Positive' if gamma_flip_ce and current_price and current_price > gamma_flip_ce else 'Negative'
        all_gamma = 'Positive' if gamma_flip and current_price and current_price > gamma_flip else 'Negative'
        
        # 檢查是否首次跌破 Gamma Flip
        if current_price and gamma_flip and prev_day_price:
            if current_price < gamma_flip and prev_day_price > gamma_flip:
                special_notes.append(f"{stock}: 現價首次跌破 Gamma Flip (前一日: {prev_day_price:.2f} -> 現價: {current_price:.2f}, Gamma Flip: {gamma_flip:.2f})")
        
        data.append([
            stock,
            f"{current_price:.2f}" if current_price else "N/A",
            f"{gamma_flip:.2f}" if gamma_flip else "N/A",
            f"{gamma_flip_ce:.2f}" if gamma_flip_ce else "N/A",
            f"{put_dominate:.2f}" if put_dominate else "N/A",
            pd_change,
            daily_gamma,
            all_gamma
        ])
    
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
            if j == 6 or j == 7:  # Gamma環境列
                cell_color = 'lightblue' if cell == 'Positive' else 'lightcoral'
                table[(i+1, j)].set_facecolor(cell_color)
                table[(i+1, j)].set_text_props(color='white', weight='bold')
            elif j == 5:  # Put Dominate 變化列
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
    
    # 讀取今日數據
    with open(today_file, 'r') as f:
        today_lines = f.readlines()
        
    # 讀取昨日數據（如果存在）
    prev_data = {}
    if os.path.exists(prev_file):
        try:
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
        except Exception as e:
            print(f"讀取昨日數據時發生錯誤: {e}")
    
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
            prev_gamma_flip = None
            prev_gamma_flip_ce = None
            prev_put_dominate = None
            
            if stock in prev_data:
                prev_gamma_flip = prev_data[stock].get('gamma_flip')
                prev_gamma_flip_ce = prev_data[stock].get('gamma_flip_ce')
                prev_put_dominate = prev_data[stock].get('put_dominate')
            
            # 獲取前前日數據
            prev_prev_put_dominate = None
            if stock in prev_prev_data:
                prev_prev_put_dominate = prev_prev_data[stock].get('put_dominate')
            
            # 獲取昨日價格
            prev_day_price = prev_day_prices.get(stock, None)
            
            # 添加到市場數據列表
            stock_data = {
                'stock': stock,
                'current_price': current_price,
                'gamma_flip': gamma_flip,
                'gamma_flip_ce': gamma_flip_ce,
                'put_dominate': put_dominate,
                'prev_gamma_flip': prev_gamma_flip,
                'prev_gamma_flip_ce': prev_gamma_flip_ce,
                'prev_put_dominate': prev_put_dominate,
                'prev_prev_put_dominate': prev_prev_put_dominate,
                'prev_day_price': prev_day_price
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
        message += f"綠色: Put Dominate 比前一日高 (看漲)\n"
        message += f"紅色: Put Dominate 比前一日低 (看跌)\n"
        message += f"黃色: Put Dominate 與前一日相同\n"
        
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
