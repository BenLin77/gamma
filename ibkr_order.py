import re
import time
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Stock, LimitOrder, Future, PriceCondition, Order, MarketOrder, Index, StopOrder
import argparse

def parse_market_levels(text):
    """解析市場層級資訊
    
    Returns:
        dict: 包含 SPX 和 QQQ 的各個價位資訊
    """
    # 分割成QQQ和SPX部分
    sections = text.split('QQQ:')
    spx_text = sections[0].replace('SPX:', '').strip()
    qqq_text = sections[1].strip()
    
    def parse_section(text):
        # 用逗號分割，但保留逗號前後的空格
        pairs = [p.strip() for p in text.split(',')]
        data = {}
        
        for i in range(0, len(pairs), 2):
            if i + 1 < len(pairs):
                key = pairs[i]
                try:
                    value = float(pairs[i + 1])
                    # 如果key包含多個條件（用&分隔），每個條件都使用相同的value
                    if '&' in key:
                        conditions = [c.strip() for c in key.split('&')]
                        for condition in conditions:
                            data[condition] = value
                    else:
                        data[key] = value
                except ValueError:
                    continue
                    
        return data

    spx_data = parse_section(spx_text)
    qqq_data = parse_section(qqq_text)
    
    return {
        'SPX': spx_data,
        'QQQ': qqq_data
    }

def load_order_config():
    """載入訂單配置"""
    config_path = Path(__file__).parent / 'order.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def generate_limit_orders(levels):
    """根據市場層級生成限價單清單"""
    orders = []
    config = load_order_config()
    price_types = config['price_types']
    
    for order_config in config['orders']:
        condition_symbol = order_config['condition']['symbol']
        price_type = price_types[order_config['condition']['type']]
        
        # 檢查是否有對應的價格水平
        if price_type not in levels[condition_symbol]:
            continue
            
        condition_price = levels[condition_symbol][price_type]
        trade_info = order_config['trade']
        
        # 生成主訂單
        orders.append({
            'symbol': trade_info['symbol'],
            'condition_symbol': condition_symbol,
            'condition_price': condition_price,
            'action': trade_info['action'],
            'quantity': trade_info['quantity'],
            'reason': f'當{condition_symbol}到達{price_type}位置 {condition_price} 時{"買入" if trade_info["action"] == "BUY" else "賣出"}{trade_info["symbol"]}',
            'stop_loss': trade_info.get('stop_loss'),
            'take_profit': trade_info.get('take_profit'),
            'is_main_order': True
        })
    
    return orders

def place_limit_order(ib, order_info):
    """下條件限價單"""
    # 設定交易合約
    if order_info['symbol'] in ['MNQ', 'MES']:
        contract = Future(order_info['symbol'], exchange='CME')
        ib.qualifyContracts(contract)
        
    # 設定條件合約
    if order_info['condition_symbol'] == 'QQQ':
        condition_contract = Stock(order_info['condition_symbol'], 'SMART', 'USD')
    else:  # SPX
        condition_contract = Index(order_info['condition_symbol'], 'CBOE', 'USD')
    ib.qualifyContracts(condition_contract)
    
    # 創建主訂單（條件市價單）
    main_order = MarketOrder(order_info['action'], order_info['quantity'])
    
    # 創建價格條件
    is_greater = order_info['action'] == 'SELL'
    price_condition = PriceCondition(
        price=order_info['condition_price'],
        conId=condition_contract.conId,
        exchange=condition_contract.exchange,
        isMore=is_greater
    )
    main_order.conditions.append(price_condition)
    
    # 下主訂單
    main_trade = ib.placeOrder(contract, main_order)
    print(f"已下主訂單: {main_trade}")
    
    # 如果有設定停損
    if order_info.get('stop_loss'):
        # 計算停損價格
        stop_points = order_info['stop_loss']
        if order_info['action'] == 'BUY':
            # 買入時，停損價格 = 條件價格 - 停損點數
            stop_price = order_info['condition_price'] - stop_points
            stop_action = 'SELL'
        else:
            # 賣出時，停損價格 = 條件價格 + 停損點數
            stop_price = order_info['condition_price'] + stop_points
            stop_action = 'BUY'
            
        # 創建停損單
        stop_order = StopOrder(stop_action, order_info['quantity'], stop_price)
        stop_trade = ib.placeOrder(contract, stop_order)
        print(f"已下停損單: {stop_trade}, 停損價格: {stop_price}")
    
    # 如果有設定目標獲利
    if order_info.get('take_profit'):
        # 計算目標價格
        profit_points = order_info['take_profit']
        if order_info['action'] == 'BUY':
            # 買入時，目標價格 = 條件價格 + 獲利點數
            profit_price = order_info['condition_price'] + profit_points
            profit_action = 'SELL'
        else:
            # 賣出時，目標價格 = 條件價格 - 獲利點數
            profit_price = order_info['condition_price'] - profit_points
            profit_action = 'BUY'
            
        # 創建限價獲利單
        profit_order = LimitOrder(profit_action, order_info['quantity'], profit_price)
        profit_trade = ib.placeOrder(contract, profit_order)
        print(f"已下獲利單: {profit_trade}, 目標價格: {profit_price}")
    
    return main_trade

def get_latest_tvcode_file():
    """獲取最新的tvcode文件
    
    Returns:
        str: 文件內容，如果文件不存在則返回None
    """
    # 設定基礎路徑
    base_path = Path('/home/ben/pCloudDrive/stock/GEX/GEX_file/tvcode')
    
    # 獲取當前日期並格式化
    today = datetime.now()
    file_name = f'tvcode_{today.strftime("%Y%m%d")}.txt'
    file_path = base_path / file_name
    
    try:
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            print(f"找不到今天的文件: {file_path}")
            # 嘗試找到最近的文件
            files = list(base_path.glob('tvcode_*.txt'))
            if files:
                latest_file = max(files, key=lambda x: x.stat().st_mtime)
                print(f"使用最近的文件: {latest_file}")
                with open(latest_file, 'r', encoding='utf-8') as f:
                    return f.read()
            else:
                print("找不到任何tvcode文件")
                return None
    except Exception as e:
        print(f"讀取文件時出錯: {str(e)}")
        return None

def create_contract(symbol, contract_type):
    """創建合約對象"""
    if contract_type == "MNQ":
        # 使用當前年月
        from datetime import datetime
        current_date = datetime.now()
        # 找到最近的季月（3,6,9,12月）
        month = ((current_date.month - 1) // 3 * 3 + 3)
        year = current_date.year
        if month < current_date.month:
            year += 1
        contract = Future('MNQ', f'{year}{month:02d}', 'CME')
        contract.multiplier = "2"  # MNQ 的乘數
        contract.currency = "USD"
    else:
        contract = Stock(symbol, 'SMART', 'USD')
    return contract

def create_order(action, quantity, order_type='MKT', stop_price=None):
    """創建訂單對象"""
    if order_type == 'MKT':
        order = MarketOrder(action, quantity)
    elif order_type == 'STP':
        order = StopOrder(action, quantity, stop_price)
    
    order.transmit = True
    order.outsideRth = True
    return order

def place_bracket_order(ib, contract, entry_order, stop_loss_points):
    """下放括號訂單（包含進場和停損）"""
    # 下市價單
    print("下放市價單...")
    trade = ib.placeOrder(contract, entry_order)
    
    # 等待市價單成交
    while not trade.isDone():
        ib.sleep(1)
    
    if trade.orderStatus.status == 'Filled':
        fill_price = trade.orderStatus.avgFillPrice
        print(f"市價單已成交，價格: {fill_price}")
        
        # 使用成交價格計算停損
        if entry_order.action == 'BUY':
            stop_loss_price = fill_price - stop_loss_points
        else:
            stop_loss_price = fill_price + stop_loss_points
        
        print(f"設置停損價格: {stop_loss_price}")
        
        # 創建停損訂單
        stop_order = create_order(
            'SELL' if entry_order.action == 'BUY' else 'BUY',
            entry_order.totalQuantity,
            'STP',
            stop_loss_price
        )
        
        # 下停損單
        stop_trade = ib.placeOrder(contract, stop_order)
        print(f"停損訂單已下放")
    else:
        print(f"訂單狀態: {trade.orderStatus.status}")
    
    return trade

def main(test_mode=False):
    # 讀取配置
    try:
        with open('order.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        print(f"讀取 order.yaml 時出錯: {str(e)}")
        return
    
    # 連接到 IB Gateway
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)
        
        # 檢查帳戶類型
        account = ib.managedAccounts()[0]
        print(f"\n帳戶號碼: {account}")
        
        # Paper Trading 帳戶通常以 'DU' 開頭
        is_paper = account.startswith('DU')
        print(f"\n當前連接到{'模擬帳戶 (Paper Trading)' if is_paper else '實盤帳戶 (Live Trading)'}")
        
        # 獲取帳戶餘額
        account_value = ib.accountSummary(account)
        net_liq = next(v.value for v in account_value if v.tag == 'NetLiquidation')
        print(f"帳戶淨值: ${net_liq}")
        
        for condition in config.get('order_conditions', []):
            # 創建合約
            contract = create_contract(condition['symbol'], condition['contract_type'])
            
            # 創建進場訂單
            entry_order = create_order(
                condition['action'],
                condition['quantity'],
                condition['order_type']
            )
            
            if test_mode:
                print(f"\n測試模式 - 將下放以下訂單：")
                print(f"合約: {condition['contract_type']}")
                print(f"動作: {condition['action']}")
                print(f"數量: {condition['quantity']}")
                print(f"停損點數: {condition['stop_loss_points']}")
            else:
                print(f"\n準備下放實際訂單...")
                # 下放訂單
                trade = place_bracket_order(
                    ib,
                    contract,
                    entry_order,
                    condition['stop_loss_points']
                )
                
                # 等待訂單更新
                ib.sleep(1)
        
    finally:
        ib.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='測試模式，不實際下單')
    args = parser.parse_args()
    
    main(test_mode=args.test)
