import os
import yaml
import requests
import yfinance as yf
from datetime import datetime
import pandas as pd
import time
from typing import Dict, Set

class PriceMonitor:
    def __init__(self, interval: int = 30, duration_hours: float = 6.5):
        """
        初始化價格監控器
        :param interval: 檢查間隔（秒）
        :param duration_hours: 運行時長（小時）
        """
        self.interval = interval
        self.last_alert: Dict[str, Dict[str, datetime]] = {}  # 記錄上次警報時間
        self.alert_cooldown = 900  # 警報冷卻時間（秒）
        self.end_time = datetime.now().timestamp() + (duration_hours * 3600)  # 結束時間戳

    def should_send_alert(self, stock: str, level: str) -> bool:
        """
        檢查是否應該發送警報（避免重複警報）
        """
        now = datetime.now()
        if stock not in self.last_alert:
            self.last_alert[stock] = {}
        
        if level not in self.last_alert[stock]:
            self.last_alert[stock][level] = now
            return True
            
        time_diff = (now - self.last_alert[stock][level]).total_seconds()
        if time_diff >= self.alert_cooldown:
            self.last_alert[stock][level] = now
            return True
            
        return False

    def start_monitoring(self):
        """開始監控價格"""
        start_time = datetime.now()
        end_time = datetime.fromtimestamp(self.end_time)
        print(f"開始監控價格，檢查間隔: {self.interval} 秒")
        print(f"警報冷卻時間: {self.alert_cooldown} 秒")
        print(f"開始時間: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"預計結束時間: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        while datetime.now().timestamp() < self.end_time:
            try:
                current_time = datetime.now()
                remaining_time = (self.end_time - current_time.timestamp()) / 3600
                
                # 每小時顯示一次剩餘時間
                if current_time.minute == 0 and current_time.second < self.interval:
                    print(f"\n[{current_time.strftime('%H:%M:%S')}] 剩餘時間: {remaining_time:.2f} 小時")
                
                monitor_price_levels(self)
                time.sleep(self.interval)
                
            except KeyboardInterrupt:
                print("\n手動停止監控")
                break
            except Exception as e:
                print(f"發生錯誤: {e}")
                time.sleep(self.interval)
        
        print("\n達到預定運行時間，程式結束")

def load_alert_config():
    """載入 alert.yaml 設定檔"""
    try:
        with open('alert.yaml', 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {'stocks': {}}

def get_real_time_price(symbol):
    """獲取即時股價"""
    try:
        stock = yf.Ticker(symbol)
        current_price = stock.info.get('regularMarketPrice')
        if current_price is None:
            # 如果無法獲取即時價格，嘗試獲取最新收盤價
            hist = stock.history(period='1d')
            if not hist.empty:
                current_price = hist['Close'].iloc[-1]
        return current_price
    except Exception as e:
        print(f"獲取 {symbol} 股價時發生錯誤: {e}")
        return None

def parse_price_levels(line):
    """解析每一行的價格水平"""
    stock = line.split(':')[0]
    levels_str = line.split(':')[1]
    levels = {}
    
    for item in levels_str.split('='):
        if ',' in item:
            # 處理多個標籤共用同一價格
            labels = item.split(',')[:-1]
            price = float(item.split(',')[-1])
            for label in labels:
                levels[label] = price
        else:
            # 處理單一標籤
            parts = item.split(',')
            if len(parts) >= 2:
                label = parts[0]
                try:
                    price = float(parts[1])
                    levels[label] = price
                except ValueError:
                    continue
                    
    return stock, levels

def check_price_alerts(file_path, monitor: PriceMonitor):
    """檢查價格警報"""
    config = load_alert_config()
    stocks_config = config.get('stocks', {})
    # 建立小寫對照表
    stocks_config_lower = {k.lower(): v for k, v in stocks_config.items()}
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            stock, levels = parse_price_levels(line)
            stock_lower = stock.lower()  # 轉換為小寫
            
            if stock_lower not in stocks_config_lower:
                continue
            
            stock_config = stocks_config_lower[stock_lower]
            symbol = stock_config['symbol']
            monitored_levels = stock_config['levels']
            
            current_price = get_real_time_price(symbol)
            if current_price is None:
                continue
            
            print(f"{stock} ({symbol}) 現價: {current_price:.2f}")
            
            for level_name, level_price in levels.items():
                if level_name not in monitored_levels:
                    continue
                    
                price_diff_pct = abs(current_price - level_price) / level_price * 100
                
                if price_diff_pct <= 0.2 and monitor.should_send_alert(stock_lower, level_name):
                    message = (f"{stock} 接近 {level_name} 價位\n"
                             f"目標價: {level_price:.2f}\n"
                             f"現價: {current_price:.2f}\n"
                             f"差距: {price_diff_pct:.2f}%")
                    
                    alert_url = f"https://api.day.app/sv5b4v7Un9jzUi9Spf2Quh/{message}?isArchive=1"
                    try:
                        response = requests.get(alert_url)
                        if response.status_code == 200:
                            print(f"已發送警報:\n{message}")
                    except Exception as e:
                        print(f"發送警報失敗: {e}")
                        
    except Exception as e:
        print(f"處理文件時發生錯誤: {e}")

def monitor_price_levels(monitor: PriceMonitor = None):
    """監控價格水平"""
    base_path = "/home/ben/pCloudDrive/stock/GEX/GEX_file/tvcode"
    today = datetime.now().strftime("%Y%m%d")
    file_path = os.path.join(base_path, f"tvcode_{today}.txt")
    
    if os.path.exists(file_path):
        # 檢查文件的最後修改時間
        try:
            file_mtime = os.path.getmtime(file_path)
            file_age = time.time() - file_mtime
            # 如果文件超過12小時沒有更新，顯示警告但繼續執行
            if file_age > 12 * 3600:
                print(f"\n警告: 價格文件可能較舊 (最後更新: {datetime.fromtimestamp(file_mtime).strftime('%Y-%m-%d %H:%M:%S')})")
        except Exception as e:
            print(f"檢查文件時間時發生錯誤: {e}")
        
        check_price_alerts(file_path, monitor)
    else:
        print(f"找不到今日的價格文件: {file_path}")

if __name__ == "__main__":
    # 創建監控器實例（預設每60秒檢查一次，運行6.5小時）
    monitor = PriceMonitor(interval=30, duration_hours=6.5)
    # 開始監控
    monitor.start_monitoring()
