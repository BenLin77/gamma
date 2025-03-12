import re
import time
import pandas as pd
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Stock, LimitOrder, Future, PriceCondition, Order, MarketOrder, Index

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

def generate_limit_orders(levels):
    """根據市場層級生成限價單清單
    
    Args:
        levels (dict): 市場層級資訊
        
    Returns:
        list: 限價單清單
    """
    orders = []
    
    # QQQ交易信號 (使用QQQ價格作為條件，交易MNQ)
    qqq = levels['QQQ']
    
    # 預掛買單邏輯
    buy_levels = {
        'Put Wall': '強支撐',
        'Put Wall CE': '次級支撐',
        'Large Gamma 1': '大Gamma支撐',
        'Large Gamma 2': '次級大Gamma支撐',
        'Put Dominate': 'Put主導支撐'
    }
    
    # 預掛賣單邏輯
    sell_levels = {
        'Call Wall': '強壓力',
        'Call Wall CE': '次級壓力',
        'Call Dominate': 'Call主導壓力',
        'Gamma Field': 'Gamma場壓力',
        'Gamma Field CE': '次級Gamma場壓力'
    }
    
    # 生成MNQ買單 (使用QQQ價格作為條件)
    for level_name, description in buy_levels.items():
        if level_name in qqq:
            orders.append({
                'symbol': 'MNQ',  # 交易MNQ
                'condition_symbol': 'QQQ',  # 使用QQQ價格作為條件
                'condition_price': qqq[level_name],  # QQQ的價格條件
                'action': 'BUY',
                'quantity': 1,
                'reason': f'當QQQ到達{description}位置 {qqq[level_name]} 時買入MNQ'
            })
    
    # 生成MNQ賣單
    for level_name, description in sell_levels.items():
        if level_name in qqq:
            orders.append({
                'symbol': 'MNQ',  # 交易MNQ
                'condition_symbol': 'QQQ',  # 使用QQQ價格作為條件
                'condition_price': qqq[level_name],  # QQQ的價格條件
                'action': 'SELL',
                'quantity': 1,
                'reason': f'當QQQ到達{description}位置 {qqq[level_name]} 時賣出MNQ'
            })
    
    # SPX交易信號 (使用SPX價格作為條件，交易MES)
    spx = levels['SPX']
    
    # 生成MES買單 (使用SPX價格作為條件)
    for level_name, description in buy_levels.items():
        if level_name in spx:
            orders.append({
                'symbol': 'MES',  # 交易MES
                'condition_symbol': 'SPX',  # 使用SPX價格作為條件
                'condition_price': spx[level_name],  # SPX的價格條件
                'action': 'BUY',
                'quantity': 1,
                'reason': f'當SPX到達{description}位置 {spx[level_name]} 時買入MES'
            })
    
    # 生成MES賣單
    for level_name, description in sell_levels.items():
        if level_name in spx:
            orders.append({
                'symbol': 'MES',  # 交易MES
                'condition_symbol': 'SPX',  # 使用SPX價格作為條件
                'condition_price': spx[level_name],  # SPX的價格條件
                'action': 'SELL',
                'quantity': 1,
                'reason': f'當SPX到達{description}位置 {spx[level_name]} 時賣出MES'
            })
    
    return orders

def place_limit_order(ib, order_info):
    """下條件限價單
    
    Args:
        ib: IB連接實例
        order_info: 訂單信息，包含：
            - symbol: 交易商品代碼
            - condition_symbol: 條件商品代碼
            - condition_price: 條件價格
            - action: 買賣方向
            - quantity: 數量
    """
    from ib_insync import Future, PriceCondition, Order, MarketOrder
    
    # 設定交易合約
    if order_info['symbol'] in ['MNQ', 'MES']:
        # 獲取最近月份的期貨合約
        contract = Future(order_info['symbol'], exchange='CME')
        ib.qualifyContracts(contract)
        
    # 設定條件合約
    if order_info['condition_symbol'] == 'QQQ':
        condition_contract = Stock(order_info['condition_symbol'], 'SMART', 'USD')
    else:  # SPX
        from ib_insync import Index
        condition_contract = Index(order_info['condition_symbol'], 'CBOE', 'USD')
    ib.qualifyContracts(condition_contract)
    
    # 創建條件市價單（當條件滿足時以市價執行）
    order = MarketOrder(order_info['action'], order_info['quantity'])
    
    # 創建價格條件
    # 對於買單，當價格低於等於條件價格時觸發
    # 對於賣單，當價格高於等於條件價格時觸發
    is_greater = order_info['action'] == 'SELL'
    
    price_condition = PriceCondition(
        price=order_info['condition_price'],
        conId=condition_contract.conId,
        exchange=condition_contract.exchange,
        isMore=is_greater
    )
    
    # 將條件添加到訂單
    order.conditions.append(price_condition)
    
    # 下單
    trade = ib.placeOrder(contract, order)
    return trade

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

def main():
    # 讀取最新的tvcode文件
    text = get_latest_tvcode_file()
    if not text:
        print("無法獲取市場層級資訊，程式結束")
        return
        
    # 解析市場層級
    market_levels = parse_market_levels(text)
    
    # 生成限價單清單
    orders = generate_limit_orders(market_levels)
    
    if not orders:
        print("沒有生成任何訂單")
        return
        
    print(f"共生成 {len(orders)} 個條件單")
    for order in orders:
        print(f"- {order['symbol']} {order['action']}: {order['reason']}")
    
    # 詢問是否執行下單
    response = input("是否執行下單？(y/n): ")
    if response.lower() != 'y':
        print("取消下單")
        return
    
    # 連接 IBKR API
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)
        
        # 下條件單
        for order in orders:
            print(f"準備下單: {order['reason']}")
            trade = place_limit_order(ib, order)
            print(f"已下單: {trade}")
            time.sleep(1)  # 避免請求過快
            
    except Exception as e:
        print(f"下單出錯: {str(e)}")
    finally:
        # 斷開連接
        if ib.isConnected():
            ib.disconnect()

if __name__ == '__main__':
    main()
