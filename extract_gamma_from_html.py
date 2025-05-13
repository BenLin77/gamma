import os
import re
import json
import glob
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
from datetime import datetime

def parse_arguments(args_string):
    """解析 Plotly.newPlot 函數的參數字串"""
    args = []
    start = 0
    bracket_count = 0
    in_quotes = False
    current = ""
    
    for i, char in enumerate(args_string):
        if char == '"' and args_string[i-1:i] != '\\':
            in_quotes = not in_quotes
        
        if not in_quotes:
            if char in "{[":
                bracket_count += 1
            if char in "]}":
                bracket_count -= 1
        
        if char == "," and bracket_count == 0 and not in_quotes:
            try:
                args.append(json.loads(current.strip()))
            except json.JSONDecodeError:
                print(f"無法解析為 JSON: {current.strip()}")
            current = ""
        else:
            current += char
    
    # 處理最後一個參數
    if current.strip():
        try:
            args.append(json.loads(current.strip()))
        except json.JSONDecodeError:
            print(f"無法解析為 JSON: {current.strip()}")
    
    return args

def get_gamma_data(data):
    """從 Plotly 數據中提取 Gamma 數據"""
    extracted_data = [item for item in data[1] if item.get('type') == 'bar']
    sorted_by_price = []
    
    if extracted_data:
        totals = {}
        
        for item in extracted_data:
            for j, price in enumerate(item.get('y', [])):
                gamma = item.get('x', [])[j]
                if price in totals:
                    totals[price] += gamma
                else:
                    totals[price] = gamma
        
        # 將字典轉換為按價格排序的列表
        sorted_by_price = sorted(
            [(float(key), value) for key, value in totals.items()],
            key=lambda x: x[0]
        )
    
    return sorted_by_price

def get_delta25(data):
    """獲取 Delta 25 值"""
    target_data = [item for item in data[2].get('annotations', []) 
                  if item.get('text') == "\u0394 25" and item.get('xanchor') == "right"]
    return target_data[0].get('x') if target_data else -1

def get_gamma_field(data):
    """獲取 Gamma Field 值"""
    target_data = [item for item in data[2].get('annotations', []) 
                  if item.get('text') == "\u0393 Field" and item.get('xanchor') == "right"]
    return target_data[0].get('y') if target_data else -1

def get_gamma_flip(data):
    """獲取 Gamma Flip 值"""
    target_data = [item for item in data[2].get('annotations', []) 
                  if item.get('text') == "\u0393 Flip" and item.get('xanchor') == "right"]
    return target_data[0].get('y') if target_data else -1

def get_call_wall(data):
    """獲取 Call Wall 值"""
    target_data = [item for item in data[2].get('annotations', []) 
                  if item.get('text') == "Call Wall" and item.get('xanchor') == "right"]
    return target_data[0].get('y') if target_data else -1

def get_put_wall(data):
    """獲取 Put Wall 值"""
    target_data = [item for item in data[2].get('annotations', []) 
                  if item.get('text') == "Put Wall" and item.get('xanchor') == "right"]
    return target_data[0].get('y') if target_data else -1

def calculate_weak_gamma_filter_th(numbers):
    """計算弱 Gamma 過濾閾值"""
    sorted_numbers = sorted(numbers)
    select = int(len(sorted_numbers) * 0.5)
    return sorted_numbers[select] if sorted_numbers else 0

def union(arr1, arr2):
    """合併兩個數組並去重"""
    return list(set(arr1 + arr2))

def calculate_abs_gamma(sorted_by_price):
    """計算絕對 Gamma 值"""
    abs_gammas = [{'index': i, 'gamma': abs(sorted_by_price[i][1])} 
                 for i in range(len(sorted_by_price))]
    
    # 按 gamma 值降序排序
    abs_gammas.sort(key=lambda x: x['gamma'], reverse=True)
    return abs_gammas

def get_top_changes(changes, sorted_by_price, top_percentage):
    """獲取前 top_percentage% 的變化"""
    top_count = int(np.ceil(len(changes) * (top_percentage / 100.0)))
    top_changes = changes[:top_count]
    return [obj['index'] for obj in top_changes]

def generate_tv_code(index_of_data_to_show, sorted_by_price, right_shift=1):
    """生成 TradingView 代碼"""
    additional_tv_code = ""
    right_padding = " " * right_shift
    
    # 先按價格降序排序
    price_indices = [(sorted_by_price[index][0], index) for index in index_of_data_to_show if 0 <= index < len(sorted_by_price)]
    price_indices.sort(reverse=True)  # 按價格降序排序
    
    for price, index in price_indices:
        gamma_in_mega = sorted_by_price[index][1] / 1000000
        
        if abs(gamma_in_mega) >= 1:
            gamma_in_mega = f"{gamma_in_mega:.0f}"
        else:
            gamma_in_mega = f"{gamma_in_mega:.2f}"
        
        # 使用正確的格式：Σ_28M,530,
        additional_tv_code += f"{right_padding}\u0393_{gamma_in_mega}M,{price}, "
    
    return additional_tv_code.rstrip()  # 移除尾部空格

def generate_level_tv_code(gamma_field, gamma_flip, call_wall, put_wall):
    """生成 Level TradingView 代碼"""
    level_tv_code = ""
    
    if gamma_field >= 0:
        level_tv_code += f"Gamma Field ,{gamma_field} ,"
    
    if gamma_flip >= 0:
        level_tv_code += f"Gamma Flip ,{gamma_flip} ,"
    
    if call_wall >= 0:
        level_tv_code += f"Call Wall ,{call_wall} ,"
    
    if put_wall >= 0:
        level_tv_code += f"Put Wall ,{put_wall} ,"
    
    return level_tv_code

def extract_plotly_data_from_html(html_content):
    """從 HTML 內容中提取 Plotly 數據"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找包含 Plotly.newPlot 的 script 標籤
    plotly_scripts = [script for script in soup.find_all('script') 
                     if script.string and 'Plotly.newPlot' in script.string 
                     and 'plotly.js' not in script.string]
    
    if not plotly_scripts:
        print("未找到 Plotly.newPlot 腳本")
        return None, None, None, None, None, None
    
    script = plotly_scripts[0].string
    
    # 查找 Plotly.newPlot 函數調用
    plotly_match = re.search(r'Plotly\.newPlot\s*\(([\s\S]*)\)', script)
    if not plotly_match:
        print("未找到 Plotly.newPlot 函數調用")
        return None, None, None, None, None, None
    
    args_string = plotly_match.group(1)
    
    try:
        # 解析參數
        args = parse_arguments(args_string)
        
        # 提取數據
        gamma_data = get_gamma_data(args)
        delta25 = get_delta25(args)
        gamma_field = get_gamma_field(args)
        gamma_flip = get_gamma_flip(args)
        call_wall = get_call_wall(args)
        put_wall = get_put_wall(args)
        
        return gamma_data, delta25, gamma_field, gamma_flip, call_wall, put_wall
    
    except Exception as e:
        print(f"解析 Plotly 數據時出錯: {e}")
        return None, None, None, None, None, None

def process_html_file(html_file, output_data=None, top_percentage=10, use_level_with_gamma=True):
    """處理單個 HTML 文件並提取 Gamma 數據"""
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # 提取數據
        sorted_by_price, delta25, gamma_field, gamma_flip, call_wall, put_wall = extract_plotly_data_from_html(html_content)
        
        if not sorted_by_price:
            print(f"無法從 {html_file} 提取數據")
            return None
        
        # 計算需要顯示的數據索引
        changes = calculate_abs_gamma(sorted_by_price)
        index_of_data_to_show = get_top_changes(changes, sorted_by_price, top_percentage)
        
        # 過濾 Delta 25 數據
        if delta25:
            over_delta25_data = [i for i, (price, gamma) in enumerate(sorted_by_price) if abs(gamma) >= delta25]
            index_of_data_to_show = union(index_of_data_to_show, over_delta25_data)
        
        # 生成 TV 代碼
        tv_code = generate_tv_code(index_of_data_to_show, sorted_by_price, 1 if use_level_with_gamma else 4)
        level_tv_code = generate_level_tv_code(gamma_field, gamma_flip, call_wall, put_wall)
        
        # 獲取股票代碼和日期
        file_name = os.path.basename(html_file)
        match = re.search(r'Gamma_(\w+)_(\d+)\.html', file_name)
        if match:
            stock_symbol = match.group(1)
            date_str = match.group(2)
        else:
            stock_symbol = "unknown"
            date_str = datetime.now().strftime('%Y%m%d')
        
        # 如果有輸出數據字典，則添加到字典中
        if output_data is not None and isinstance(output_data, dict):
            if stock_symbol not in output_data:
                output_data[stock_symbol] = tv_code
            else:
                # 如果股票已存在，則追加新的代碼
                output_data[stock_symbol] = tv_code
        
        print(f"已處理 {html_file} 並提取 Gamma 數據")
        
        return {
            'stock': stock_symbol,
            'date': date_str,
            'gamma_code': tv_code,
            'level_code': level_tv_code
        }
    
    except Exception as e:
        print(f"處理 {html_file} 時出錯: {e}")
        return None

def get_latest_html_file(stock_dir, use_newest=False):
    """
    尋找 HTML 文件，根據 use_newest 參數決定是尋找最新的文件還是當日的文件
    
    Args:
        stock_dir (str): 股票目錄路徑
        use_newest (bool): 是否尋找最新的文件，而不是當日的文件
        
    Returns:
        str: HTML 文件路徑，如果沒有找到則返回 None
    """
    html_dir = os.path.join(stock_dir, "html")
    if not os.path.exists(html_dir):
        return None
    
    # 獲取當前日期
    today = datetime.now().strftime("%Y%m%d")
    
    if use_newest:
        # 尋找所有 HTML 文件並按日期排序
        html_files = glob.glob(os.path.join(html_dir, "Gamma_*.html"))
        if not html_files:
            return None
        
        # 按照文件名中的日期排序
        html_files.sort(key=lambda x: re.search(r'_(\d{8})\.html$', x).group(1) if re.search(r'_(\d{8})\.html$', x) else "", reverse=True)
    else:
        # 尋找當天的 HTML 文件
        html_files = glob.glob(os.path.join(html_dir, f"Gamma_*_{today}.html"))
        
        if not html_files:
            # 如果沒有當天的文件，則返回 None
            return None
    
    return html_files[0] if html_files else None

def save_gamma_levels(data, output_dir):
    """
    將股票的 Gamma 水平數據保存到指定目錄
    
    Args:
        data (str): 包含多行股票數據的字符串，每行格式為 "股票代碼:水平數據"
        output_dir (str): 輸出目錄路徑
    """
    # 確保輸出目錄存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 獲取當前日期
    today = datetime.now().strftime('%Y%m%d')
    
    # 分割每行數據
    lines = [line.strip() for line in data.strip().split('\n') if line.strip()]
    
    # 處理每行數據
    for line in lines:
        # 分割股票代碼和數據
        parts = line.split(':', 1)
        if len(parts) != 2:
            print(f"警告: 無法解析行 '{line}'，跳過")
            continue
        
        stock_symbol = parts[0].strip()
        level_data = parts[1].strip()
        
        # 創建股票特定的輸出目錄
        stock_dir = os.path.join(output_dir, stock_symbol)
        os.makedirs(stock_dir, exist_ok=True)
        
        # 創建輸出文件名
        output_file = os.path.join(stock_dir, f"gamma_levels_{today}.txt")
        
        # 保存數據
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(level_data)
        
        print(f"已保存 {stock_symbol} 的 Gamma 水平數據到 {output_file}")
    
    return len(lines)

def main():
    # 解析命令行參數
    import argparse
    parser = argparse.ArgumentParser(description="從 HTML 文件提取 Gamma 數據和處理 Gamma 水平數據")
    parser.add_argument("-n", "--newest", action="store_true", help="尋找最新的 HTML 文件，而不是當日的文件")
    parser.add_argument("-m", "--mode", type=int, choices=[1, 2, 3], default=3, help="處理模式: 1=提取HTML, 2=保存水平數據, 3=兩者都執行 (默認: 3)")
    args = parser.parse_args()
    
    # 設定目錄
    base_dir = "/home/ben/pCloudDrive/stock/GEX/GEX_file"
    output_base_dir = "/home/ben/pCloudDrive/stock/GEX/gamma_codes"
    gamma_code_dir = os.path.join(base_dir, "gamma_code")
    
    # 是否尋找最新的 HTML 文件
    use_newest = args.newest
    
    # 檢查基礎目錄是否存在
    if not os.path.exists(base_dir):
        print(f"錯誤: 基礎目錄 {base_dir} 不存在")
        return
    
    # 確保輸出目錄存在
    os.makedirs(output_base_dir, exist_ok=True)
    os.makedirs(gamma_code_dir, exist_ok=True)
    
    # 處理模式選擇
    print("請選擇處理模式:")
    print("1. 從 HTML 文件提取 Gamma 數據")
    print("2. 保存股票 Gamma 水平數據")
    print("3. 兩者都執行")
    
    # 使用命令行參數指定的模式
    choice = str(args.mode)
    
    # 在互動式環境中才嘗試獲取輸入
    import sys
    try:
        if sys.stdin.isatty() and not sys.argv[1:]:  # 檢查是否為互動式環境且沒有命令行參數
            print("請選擇處理模式:")
            print("1. 從 HTML 文件提取 Gamma 數據")
            print("2. 保存股票 Gamma 水平數據")
            print("3. 兩者都執行")
            choice = input("請輸入選擇 (1/2/3，默認為 3): ").strip() or "3"
        else:
            print(f"使用模式: {choice}")
    except (EOFError, KeyboardInterrupt):
        print(f"使用默認模式: {choice}")
    
    if use_newest:
        print("將尋找最新的 HTML 文件")
    else:
        print("將尋找當日的 HTML 文件")
    
    # 處理 HTML 文件
    if choice in ["1", "3"]:
        # 獲取當日日期
        today_date = datetime.now().strftime('%Y%m%d')
        
        # 嘗試直接獲取所有股票目錄
        stock_dirs = glob.glob(os.path.join(base_dir, "*"))
        
        if not stock_dirs:
            print(f"警告: 在 {base_dir} 中未找到任何股票目錄")
            if choice == "3":
                print("繼續執行保存 Gamma 水平數據的部分...")
            else:
                return
        
        print(f"找到 {len(stock_dirs)} 個可能的股票目錄")
        
        results = []
        processed_stocks = []
        skipped_stocks = []
        
        # 創建一個字典來存儲所有股票的 Gamma 數據
        all_gamma_data = {}
        
        for stock_dir in stock_dirs:
            if os.path.isdir(stock_dir):
                stock_symbol = os.path.basename(stock_dir)
                html_dir = os.path.join(stock_dir, "html")
                
                if not os.path.exists(html_dir):
                    print(f"跳過 {stock_symbol}: html 目錄不存在 ({html_dir})")
                    skipped_stocks.append(stock_symbol)
                    continue
                
                # 找出最新的 HTML 文件
                latest_html_file = get_latest_html_file(stock_dir, use_newest)
                
                if not latest_html_file:
                    print(f"跳過 {stock_symbol}: 未找到符合條件的 HTML 文件")
                    skipped_stocks.append(stock_symbol)
                    continue
                
                # 從檔案名中提取日期
                file_name = os.path.basename(latest_html_file)
                match = re.search(r'Gamma_\w+_(\d+)\.html', file_name)
                file_date = match.group(1) if match else today_date
                
                print(f"處理股票 {stock_symbol}: 使用最新的 HTML 文件 ({file_date})")
                
                # 處理 HTML 文件
                result = process_html_file(latest_html_file, all_gamma_data)
                
                if result:
                    results.append(result)
                    processed_stocks.append(stock_symbol)
                    print(f"成功處理 {stock_symbol}: 提取了 Gamma 數據")
                else:
                    print(f"警告: {stock_symbol} 的文件處理失敗")
                    skipped_stocks.append(stock_symbol)
                
                # 已經在上面處理過了，不需要重複
        
        # 將所有股票的 Gamma 數據存到同一個文件中
        if all_gamma_data:
            # 確保輸出目錄存在
            os.makedirs(gamma_code_dir, exist_ok=True)
            
            # 從結果中找出最新的日期
            # 預設使用最常見的日期
            date_counts = {}
            for result in results:
                if result and 'date' in result:
                    date = result['date']
                    date_counts[date] = date_counts.get(date, 0) + 1
            
            # 找出最常見的日期
            most_common_date = today_date
            max_count = 0
            for date, count in date_counts.items():
                if count > max_count:
                    max_count = count
                    most_common_date = date
            
            # 使用最常見的日期
            latest_date = most_common_date
            
            # 創建輸出文件路徑
            gamma_file = os.path.join(gamma_code_dir, f"gammacode_{latest_date}.txt")
            
            # 將所有股票的數據寫入文件
            with open(gamma_file, 'w', encoding='utf-8') as f:
                for stock, code in all_gamma_data.items():
                    # 確保每個股票的數據格式正確
                    # 移除可能的尾部空格和多餘的逗號
                    code = code.strip()
                    if code.endswith(','):
                        code = code[:-1]
                    f.write(f"{stock}:{code}\n")
            
            print(f"\n已將所有股票的 Gamma 數據存到: {gamma_file}")
            print(f"共處理了 {len(all_gamma_data)} 個股票的數據")
    
        # 生成摘要報告
        if results:
            df = pd.DataFrame(results)
            report_file = os.path.join(output_base_dir, f"gamma_extraction_report_{datetime.now().strftime('%Y%m%d')}.csv")
            df.to_csv(report_file, index=False)
            print(f"已生成摘要報告: {report_file}")
        
        # 顯示處理統計
        print(f"\n處理統計:")
        print(f"總共處理了 {len(results)} 個 HTML 文件")
        print(f"成功處理的股票: {len(processed_stocks)} 個")
        if processed_stocks:
            print(f"處理的股票代號: {', '.join(processed_stocks)}")
        print(f"跳過的股票: {len(skipped_stocks)} 個")
        if skipped_stocks:
            print(f"跳過的股票代號: {', '.join(skipped_stocks)}")
    
if __name__ == "__main__":
    main()
