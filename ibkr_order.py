import re
import time
import yaml
import pandas as pd
from datetime import datetime
from pathlib import Path
from ib_insync import IB, Stock, LimitOrder, Future, PriceCondition, Order, MarketOrder, Index, StopOrder
import argparse
import json
import logging
import os
import sys
import subprocess
import shutil
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ibkr_order.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('ibkr_order')

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

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ibkr_order')

# 全局 IB 連接對象
ib_connection = None

# 初始化 IB 連接
def initialize_ib():
    global ib_connection
    if ib_connection is not None and ib_connection.isConnected():
        return ib_connection
    
    ib = IB()
    try:
        ib.connect('127.0.0.1', 4002, clientId=1)
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



def process_order_from_file(file_path):
    """從文件中讀取訂單數據並根據 order.yaml 和 gamma level 下單"""
    try:
        logger.info(f"讀取訂單文件: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            signal_data = json.load(f)
            
        logger.info(f"收到信號數據: {signal_data}")
        
        # 從信號數據中提取信息
        # 支援多種可能的格式
        signal_symbol = signal_data.get('symbol')  # 信號的標的，如 QQQ
        signal_action = signal_data.get('action')  # 信號的動作，如 BUY
        
        # 如果沒有標準格式，嘗試解析文本格式
        if not signal_symbol and isinstance(signal_data.get('message'), str):
            message = signal_data.get('message', '')
            # 嘗試解析格式如 "buy QQQ 1000"
            parts = message.strip().split()
            if len(parts) >= 2:
                action_text = parts[0].upper()
                if action_text in ['BUY', 'SELL', '買入', '賣出']:
                    signal_action = 'BUY' if action_text in ['BUY', '買入'] else 'SELL'
                    signal_symbol = parts[1].upper()
        
        if not signal_symbol:
            logger.error("信號數據缺少必要信息 (symbol)")
            return False
        
        # 如果沒有指定動作，預設為買入
        if not signal_action:
            signal_action = 'BUY'
            logger.info(f"未指定動作，預設為: {signal_action}")
        
        # 讀取 order.yaml 配置
        try:
            with open('order.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"讀取 order.yaml 時出錯: {str(e)}")
            return False
        
        # 獲取最新的 gamma level 數據
        tvcode_content = get_latest_tvcode_file()
        if not tvcode_content:
            logger.error("無法獲取 gamma level 數據")
            return False
            
        # 解析 gamma level 數據
        market_levels = parse_market_levels(tvcode_content)
        logger.info(f"當前市場層級: {market_levels}")
        
        # 根據信號尋找匹配的訂單配置
        matched_orders = []
        for order_config in config.get('orders', []):
            condition = order_config.get('condition', {})
            
            # 檢查是否匹配信號的標的
            if condition.get('symbol') == signal_symbol:
                # 檢查動作方向是否匹配
                direction = condition.get('direction', '')
                if (direction == 'LONG' and signal_action == 'BUY') or \
                   (direction == 'SHORT' and signal_action == 'SELL') or \
                   not direction:  # 如果沒有指定方向，則視為匹配
                    matched_orders.append(order_config)
        
        if not matched_orders:
            logger.warning(f"沒有找到匹配的訂單配置: {signal_symbol} {signal_action}")
            
            # 移動文件到已處理資料夾
            processed_dir = Path(file_path).parent / 'processed'
            processed_dir.mkdir(exist_ok=True)
            processed_file = processed_dir / f"no_match_{Path(file_path).name}"
            os.rename(file_path, processed_file)
            logger.info(f"無匹配訂單，文件已移動到: {processed_file}")
            
            return False
        
        # 連接到 IB Gateway
        ib = initialize_ib()
        if not ib:
            logger.error("無法連接到 IB Gateway")
            return False
        
        try:
            # 處理每個匹配的訂單
            for order_config in matched_orders:
                try:
                    # 獲取訂單配置
                    condition = order_config.get('condition', {})
                    trade_info = order_config.get('trade', {})
                    
                    # 獲取對應的價格層級
                    price_type = condition.get('type')  # 如 PUT_DOM, CALL_DOM 等
                    price_types = config.get('price_types', {})
                    level_key = price_types.get(price_type)
                    
                    if not level_key or level_key not in market_levels.get(signal_symbol, {}):
                        logger.warning(f"無法找到價格層級: {price_type} -> {level_key}")
                        continue
                    
                    # 獲取對應的價格
                    condition_price = market_levels[signal_symbol][level_key]
                    
                    # 創建交易合約
                    trade_symbol = trade_info.get('symbol')
                    if trade_symbol in ['MNQ', 'MES']:
                        contract = Future(trade_symbol, exchange='CME')
                        ib.qualifyContracts(contract)
                    else:
                        logger.error(f"不支援的交易合約: {trade_symbol}")
                        continue
                    
                    # 創建交易訂單
                    action = trade_info.get('action')  # BUY 或 SELL
                    quantity = trade_info.get('quantity', 1)
                    stop_loss = trade_info.get('stop_loss', 10)
                    take_profit = trade_info.get('take_profit')
                    
                    logger.info(f"準備下單: {trade_symbol} {action} {quantity} 張, 價格層級: {level_key}={condition_price}, 停損: {stop_loss}")
                    
                    # 下放條件限價單
                    trade = place_limit_order(ib, {
                        'symbol': trade_symbol,
                        'condition_symbol': signal_symbol,
                        'condition_price': condition_price,
                        'action': action,
                        'quantity': quantity,
                        'reason': f'當{signal_symbol}到達{level_key}位置 {condition_price} 時{"\u8cb7\u5165" if action == "BUY" else "\u8ce3\u51fa"}{trade_symbol}',
                        'stop_loss': stop_loss,
                        'take_profit': take_profit,
                        'is_main_order': True
                    })
                    
                    logger.info(f"已下單: {trade}")
                    
                except Exception as e:
                    logger.error(f"處理訂單配置時出錯: {str(e)}")
            
            # 移動文件到已處理資料夾
            processed_dir = Path(file_path).parent / 'processed'
            processed_dir.mkdir(exist_ok=True)
            processed_file = processed_dir / f"processed_{Path(file_path).name}"
            os.rename(file_path, processed_file)
            logger.info(f"訂單文件已移動到: {processed_file}")
            
            return True
        finally:
            ib.disconnect()
            
    except Exception as e:
        logger.error(f"處理訂單文件時出錯: {str(e)}")
        return False

def initialize_ib():
    """初始化並連接到 IB Gateway"""
    try:
        ib = IB()
        ib.connect('127.0.0.1', 4002, clientId=1)
        
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
        
        return ib
    except Exception as e:
        logger.error(f"連接到 IB Gateway 時出錯: {str(e)}")
        return None

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
        ib.connect('127.0.0.1', 4002, clientId=1)
        
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




# Discord Bot 設定
def setup_discord_bot():
    """設定 Discord Bot"""
    # 載入環境變數
    load_dotenv()
    
    # 設定機器人前綴和權限
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    
    bot = commands.Bot(command_prefix='!', intents=intents)
    
    # 監聽頻道 ID
    TRADING_SIGNAL_CHANNEL_ID = 1359726707841437807
    
    @bot.event
    async def on_ready():
        """當 Bot 準備好時"""
        logger.info(f'已登入為 {bot.user}')
        logger.info(f'監聽頻道 ID: {TRADING_SIGNAL_CHANNEL_ID}')
        
        # 檢查頻道是否存在
        channel = bot.get_channel(TRADING_SIGNAL_CHANNEL_ID)
        if channel:
            logger.info(f'成功連接到頻道: {channel.name}')
        else:
            logger.error(f'找不到頻道 ID: {TRADING_SIGNAL_CHANNEL_ID}')
    
    @bot.event
    async def on_message(message):
        """當收到訊息時"""
        # 忽略自己的訊息
        if message.author == bot.user:
            return
            
        # 只處理特定頻道的訊息
        if message.channel.id == TRADING_SIGNAL_CHANNEL_ID:
            logger.info(f"收到頻道訊息: {message.content}")
            
            # 不從訊息中提取股票代號，而是檢查 order.yaml 中的所有股票代號是否在訊息中出現
            logger.info(f"檢查訊息是否包含 order.yaml 中的股票代號")
            
            # 載入訂單配置
            config = load_order_config()
            
            # 收集所有已配置的股票代號
            configured_symbols = set()
            for order_config in config['orders']:
                configured_symbols.add(order_config['trade']['symbol'])
            
            logger.info(f"order.yaml 中的股票代號: {configured_symbols}")
            
            # 檢查訊息中是否包含任何配置的股票代號
            found_symbols = []
            for symbol in configured_symbols:
                if symbol in message.content:
                    found_symbols.append(symbol)
            
            if not found_symbols:
                logger.warning(f"訊息中沒有找到任何配置的股票代號: {message.content}")
                await message.channel.send("❌ 訊息中沒有找到任何已配置的股票代號")
                return
            
            # 如果找到多個股票代號，都處理
            processed_results = []
            for symbol in found_symbols:
                logger.info(f"發現股票代號: {symbol}")
                try:
                    process_order_by_symbol(symbol)
                    processed_results.append(f"✅ {symbol} 訂單處理成功")
                except Exception as e:
                    error_msg = str(e)[:200]  # 限制錯誤訊息長度
                    processed_results.append(f"❌ {symbol} 訂單失敗: {error_msg}")
                    logger.error(f"處理 {symbol} 的訂單失敗: {str(e)}")
            
            # 回覆處理結果
            result_message = "\n".join(processed_results)
            await message.channel.send(result_message)
        
        await bot.process_commands(message)
    
    # 添加一個測試命令
    @bot.command(name='test')
    async def test_command(ctx, symbol=None):
        """測試處理訂單的命令"""
        if not symbol:
            await ctx.send("請提供股票代號，例如: !test QQQ")
            return
            
        await ctx.send(f"測試處理 {symbol} 的訂單...")
        try:
            process_order_by_symbol(symbol)
            await ctx.send(f"✅ 測試成功")
        except Exception as e:
            await ctx.send(f"❌ 測試失敗: {str(e)[:1000]}")
    
    return bot

def start_discord_bot():
    """啟動 Discord Bot"""
    bot = setup_discord_bot()
    
    # 使用環境變數中的 Token
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        logger.error("找不到 DISCORD_BOT_TOKEN 環境變數")
        return
        
    logger.info("啟動 Discord Bot...")
    bot.run(token)

def process_order_by_symbol(symbol):
    """根據股票代號處理訂單"""
    logger.info(f"處理 {symbol} 的訂單")
    
    # 初始化 IB 連接
    ib = initialize_ib()
    if not ib:
        raise Exception("無法連接到 IB Gateway")
    
    # 載入訂單配置
    config = load_order_config()
    
    # 獲取最新的市場層級
    tvcode_content = get_latest_tvcode_file()
    if not tvcode_content:
        raise Exception("無法獲取最新的市場層級")
    
    # 解析市場層級
    levels = parse_market_levels(tvcode_content)
    
    # 生成訂單
    orders = []
    for order_config in config['orders']:
        # 只處理符合指定股票代號的訂單
        if order_config['trade']['symbol'] == symbol:
            condition_symbol = order_config['condition']['symbol']
            price_type = config['price_types'][order_config['condition']['type']]
            
            # 檢查是否有對應的價格水平
            if price_type not in levels[condition_symbol]:
                logger.warning(f"找不到 {condition_symbol} 的 {price_type} 價格水平")
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
    
    if not orders:
        raise Exception(f"在配置中找不到 {symbol} 的訂單設定")
    
    # 下單
    for order_info in orders:
        logger.info(f"下單原因: {order_info['reason']}")
        place_limit_order(ib, order_info)
    
    # 關閉連接
    ib.disconnect()
    
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='測試模式，不實際下單')
    parser.add_argument('--process_order', type=str, help='處理指定的訂單文件')
    parser.add_argument('--symbol', type=str, help='處理指定股票代號的訂單')
    parser.add_argument('--discord', action='store_true', help='啟動 Discord Bot 監聽訂單')
    args = parser.parse_args()
    
    if args.process_order:
        process_order_from_file(args.process_order)
    elif args.symbol:
        try:
            process_order_by_symbol(args.symbol)
        except Exception as e:
            logger.error(f"處理 {args.symbol} 的訂單失敗: {str(e)}")
            sys.exit(1)
    elif args.discord:
        start_discord_bot()
    else:
        main(test_mode=args.test)
