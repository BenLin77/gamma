import re
import time
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Stock, LimitOrder, Future, PriceCondition, Order, MarketOrder, Index, StopOrder
import argparse
import json
from flask import Flask, request, jsonify
from threading import Thread
import logging

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

# 創建 Flask 應用程序來接收 TradingView 的 webhook
app = Flask(__name__)

# 設置日誌
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler("ibkr_webhook.log"),
                              logging.StreamHandler()])
logger = logging.getLogger(__name__)

# 全局 IB 連接對象
ib_connection = None

# 初始化 IB 連接
def initialize_ib():
    global ib_connection
    if ib_connection is not None and ib_connection.isConnected():
        return ib_connection
    
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)
        logger.info("已連接到 IB Gateway")
        
        # 檢查帳戶類型
        account = ib.managedAccounts()[0]
        logger.info(f"帳戶號碼: {account}")
        
        # Paper Trading 帳戶通常以 'DU' 開頭
        is_paper = account.startswith('DU')
        logger.info(f"當前連接到{'模擬帳戶 (Paper Trading)' if is_paper else '實盤帳戶 (Live Trading)'}")
        
        # 獲取帳戶餘額
        account_value = ib.accountSummary(account)
        net_liq = next(v.value for v in account_value if v.tag == 'NetLiquidation')
        logger.info(f"帳戶淨值: ${net_liq}")
        
        ib_connection = ib
        return ib
    except Exception as e:
        logger.error(f"連接 IB Gateway 時出錯: {str(e)}")
        return None

# 處理 TradingView 的 webhook 請求
@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # 獲取 webhook 數據
        data = request.json
        logger.info(f"收到 TradingView webhook: {data}")
        
        # 驗證必要字段
        required_fields = ['symbol', 'action', 'gamma_level']
        for field in required_fields:
            if field not in data:
                logger.error(f"缺少必要字段: {field}")
                return jsonify({"status": "error", "message": f"缺少必要字段: {field}"}), 400
        
        # 獲取 gamma level 配置
        gamma_level = data['gamma_level']
        symbol = data['symbol']
        action = data['action']
        quantity = data.get('quantity', 1)
        contract_type = data.get('contract_type', 'MNQ' if symbol == 'QQQ' else 'MES')
        stop_loss_points = data.get('stop_loss_points', 200 if contract_type == 'MNQ' else 20)
        take_profit_points = data.get('take_profit_points', 400 if contract_type == 'MNQ' else 40)
        
        # 讀取 gamma level 配置
        try:
            with open('gamma_levels.yaml', 'r', encoding='utf-8') as f:
                gamma_config = yaml.safe_load(f)
                
            if gamma_level not in gamma_config:
                logger.error(f"找不到指定的 gamma level: {gamma_level}")
                return jsonify({"status": "error", "message": f"找不到指定的 gamma level: {gamma_level}"}), 400
                
            level_price = gamma_config[gamma_level].get(symbol)
            if not level_price:
                logger.error(f"在 gamma level '{gamma_level}' 中找不到 {symbol} 的價格")
                return jsonify({"status": "error", "message": f"在 gamma level '{gamma_level}' 中找不到 {symbol} 的價格"}), 400
                
            # 初始化 IB 連接
            ib = initialize_ib()
            if ib is None:
                return jsonify({"status": "error", "message": "無法連接到 IB Gateway"}), 500
            
            # 創建合約
            contract = create_contract(symbol, contract_type)
            
            # 創建條件合約
            if symbol == 'QQQ':
                condition_contract = Stock(symbol, 'SMART', 'USD')
            else:  # SPX
                condition_contract = Index(symbol, 'CBOE', 'USD')
            ib.qualifyContracts(condition_contract)
            
            # 創建主訂單（條件市價單）
            main_order = MarketOrder(action, quantity)
            
            # 創建價格條件
            is_greater = action == 'SELL'
            price_condition = PriceCondition(
                price=level_price,
                conId=condition_contract.conId,
                exchange=condition_contract.exchange,
                isMore=is_greater
            )
            main_order.conditions.append(price_condition)
            
            # 下主訂單
            main_trade = ib.placeOrder(contract, main_order)
            logger.info(f"已下主訂單: {main_trade}")
            
            # 如果有設定停損
            if stop_loss_points:
                # 計算停損價格
                if action == 'BUY':
                    # 買入時，停損價格 = 條件價格 - 停損點數
                    stop_price = level_price - stop_loss_points
                    stop_action = 'SELL'
                else:
                    # 賣出時，停損價格 = 條件價格 + 停損點數
                    stop_price = level_price + stop_loss_points
                    stop_action = 'BUY'
                    
                # 創建停損單
                stop_order = StopOrder(stop_action, quantity, stop_price)
                stop_trade = ib.placeOrder(contract, stop_order)
                logger.info(f"已下停損單: {stop_trade}, 停損價格: {stop_price}")
            
            # 如果有設定目標獲利
            if take_profit_points:
                # 計算目標價格
                if action == 'BUY':
                    # 買入時，目標價格 = 條件價格 + 獲利點數
                    profit_price = level_price + take_profit_points
                    profit_action = 'SELL'
                else:
                    # 賣出時，目標價格 = 條件價格 - 獲利點數
                    profit_price = level_price - take_profit_points
                    profit_action = 'BUY'
                    
                # 創建限價獲利單
                profit_order = LimitOrder(profit_action, quantity, profit_price)
                profit_trade = ib.placeOrder(contract, profit_order)
                logger.info(f"已下獲利單: {profit_trade}, 目標價格: {profit_price}")
            
            return jsonify({
                "status": "success", 
                "message": f"已成功下單 {action} {quantity} {contract_type} 在 {symbol} 達到 {gamma_level} ({level_price}) 時",
                "order_details": {
                    "symbol": symbol,
                    "contract_type": contract_type,
                    "action": action,
                    "quantity": quantity,
                    "gamma_level": gamma_level,
                    "level_price": level_price,
                    "stop_loss_points": stop_loss_points,
                    "take_profit_points": take_profit_points
                }
            })
            
        except Exception as e:
            logger.error(f"處理訂單時出錯: {str(e)}")
            return jsonify({"status": "error", "message": f"處理訂單時出錯: {str(e)}"}), 500
            
    except Exception as e:
        logger.error(f"處理 webhook 請求時出錯: {str(e)}")
        return jsonify({"status": "error", "message": f"處理請求時出錯: {str(e)}"}), 500

# 健康檢查端點
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

def main(test_mode=False, start_webhook=False):
    # 讀取配置
    try:
        with open('order.yaml', 'r') as f:
            config = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"讀取 order.yaml 時出錯: {str(e)}")
        return
    
    # 連接到 IB Gateway
    ib = IB()
    try:
        ib.connect('127.0.0.1', 7497, clientId=1)
        
        # 檢查帳戶類型
        account = ib.managedAccounts()[0]
        logger.info(f"\n帳戶號碼: {account}")
        
        # Paper Trading 帳戶通常以 'DU' 開頭
        is_paper = account.startswith('DU')
        logger.info(f"\n當前連接到{'模擬帳戶 (Paper Trading)' if is_paper else '實盤帳戶 (Live Trading)'}")
        
        # 獲取帳戶餘額
        account_value = ib.accountSummary(account)
        net_liq = next(v.value for v in account_value if v.tag == 'NetLiquidation')
        logger.info(f"帳戶淨值: ${net_liq}")
        
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
                logger.info(f"\n測試模式 - 將下放以下訂單：")
                logger.info(f"合約: {condition['contract_type']}")
                logger.info(f"動作: {condition['action']}")
                logger.info(f"數量: {condition['quantity']}")
                logger.info(f"停損點數: {condition['stop_loss_points']}")
            else:
                logger.info(f"\n準備下放實際訂單...")
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
        if not start_webhook:  # 如果啟動 webhook 服務器，保持連接
            ib.disconnect()

# 啟動 webhook 服務器的函數
def start_webhook_server(host='0.0.0.0', port=5000):
    logger.info(f"啟動 webhook 服務器在 {host}:{port}...")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='測試模式，不實際下單')
    parser.add_argument('--webhook', action='store_true', help='啟動 webhook 服務器')
    parser.add_argument('--port', type=int, default=5000, help='webhook 服務器端口')
    args = parser.parse_args()
    
    if args.webhook:
        # 初始化 IB 連接
        initialize_ib()
        # 啟動 webhook 服務器
        start_webhook_server(port=args.port)
    else:
        main(test_mode=args.test)
