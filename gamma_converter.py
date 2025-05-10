import re
import argparse
from datetime import datetime
import os
import sys
import logging
import hashlib

def convert_to_short(input_text):
    # 定義映射關係
    level_mapping = {
        'Put Dominate': 'PD',
        'Call Dominate': 'CD',
        'Gamma Flip': 'GF',
        'Put Wall': 'PW',
        'Call Wall': 'CW',
        'Key Delta': 'KD',
        'Large Gamma': 'LG',
        'Gamma Field': 'GFL',
        'Implied Movement +σ': 'IM+',
        'Implied Movement -σ': 'IM-',
        'Implied Movement +2σ': 'IM2+',
        'Implied Movement -2σ': 'IM2-'
    }
    
    # 分割每個股票的數據
    stocks = [s.strip() for s in input_text.strip().split('\n\n') if s.strip()]
    result = []
    
    for stock in stocks:
        # 提取股票代碼
        symbol = stock.split(':')[0].strip()
        
        # 創建價格到level的映射
        price_levels = {}
        
        # 提取所有價格和level對
        pairs = re.findall(r'([^,]+),\s*([\d.]+)', stock)
        
        for level, price in pairs:
            price = float(price)
            level = level.strip()
            has_ce = ' CE' in level
            
            # 分割多個level（如果有的話）
            sub_levels = [l.strip() for l in level.replace(' CE', '').split('&')]
            
            # 轉換每個level到簡短代碼
            for sub_level in sub_levels:
                for full_name, code in level_mapping.items():
                    if full_name in sub_level:
                        if price not in price_levels:
                            price_levels[price] = set()
                        if has_ce:
                            # 如果是 CE 後綴，只添加帶 CE 的代碼
                            price_levels[price].add(code + 'CE')
                        else:
                            # 如果不是 CE 後綴，只添加基礎代碼
                            price_levels[price].add(code)
                        break  # 找到匹配後就跳出，避免重複添加
        
        # 構建輸出字符串
        output_parts = [symbol + ':']
        for price, codes in sorted(price_levels.items()):
            # 將 set 轉換為列表並排序，確保每個代碼只出現一次
            codes_list = sorted(list(codes))
            codes_str = ','.join(codes_list)
            output_parts.append(f"{codes_str}={price}")
        
        result.append(''.join(output_parts))
    
    return '\n'.join(result)

def convert_to_long(input_text):
    # 定義反向映射關係
    reverse_mapping = {
        'PD': 'Put Dominate',
        'CD': 'Call Dominate',
        'GF': 'Gamma Flip',
        'PW': 'Put Wall',
        'CW': 'Call Wall',
        'KD': 'Key Delta',
        'LG': 'Large Gamma',
        'GFL': 'Gamma Field',
        'IM+': 'Implied Movement +σ',
        'IM-': 'Implied Movement -σ',
        'IM2+': 'Implied Movement +2σ',
        'IM2-': 'Implied Movement -2σ'
    }
    
    result = []
    lines = [l.strip() for l in input_text.strip().split('\n') if l.strip()]
    
    for line in lines:
        try:
            # 忽略分隔線（如 "===== spx ====="）
            if re.match(r'^=+\s+\w+\s+=+$', line):
                continue
                
            if ':' not in line:
                continue
                
            # 提取股票代碼和數據
            symbol, data = line.split(':', 1)
            symbol = symbol.strip()
            
            # 解析所有價格和代碼對
            levels = []
            
            # 使用正則表達式分割數據
            pairs = re.findall(r'([^=]+)=(\d+\.?\d*)', data)
            
            for codes, price in pairs:
                try:
                    price = float(price)
                    codes = [c.strip() for c in codes.split(',') if c.strip()]
                    
                    # 轉換代碼到完整名稱
                    full_names = []
                    for code in codes:
                        if code.endswith('CE'):
                            base_code = code[:-2]
                            if base_code in reverse_mapping:
                                full_names.append(reverse_mapping[base_code] + ' CE')
                        else:
                            if code in reverse_mapping:
                                full_names.append(reverse_mapping[code])
                    
                    if full_names:
                        levels.append(f"{' & '.join(full_names)}, {price}")
                except Exception as e:
                    print(f"警告：處理價格對時出錯 '{codes}={price}': {str(e)}")
                    continue
            
            # 組合結果
            if levels:
                result.append(f"{symbol}: {', '.join(levels)}")
                
        except Exception as e:
            print(f"警告：處理行 '{line}' 時出錯: {str(e)}")
            continue
    
    return '\n\n'.join(result)

def get_today_filename():
    """獲取今天的文件名格式"""
    return f"tvcode_{datetime.now().strftime('%Y%m%d')}.txt"

def validate_conversion(original_text, converted_text, is_reverse=False):
    """驗證轉換是否成功
    
    檢查轉換前後的數據是否保持一致性，確保沒有數據丟失
    
    Args:
        original_text: 原始文本
        converted_text: 轉換後的文本
        is_reverse: 是否為反向轉換
        
    Returns:
        (bool, str): 驗證結果和錯誤信息
    """
    # 移除空白行和空格進行比較
    original_clean = '\n'.join([line.strip() for line in original_text.strip().split('\n') if line.strip()])
    converted_clean = '\n'.join([line.strip() for line in converted_text.strip().split('\n') if line.strip()])
    
    # 檢查股票代碼是否一致
    original_symbols = set()
    converted_symbols = set()
    
    # 根據格式提取股票代碼
    if is_reverse:
        # 從短格式提取股票代碼
        for line in original_clean.split('\n'):
            if ':' in line:
                symbol = line.split(':', 1)[0].strip()
                original_symbols.add(symbol)
        
        # 從長格式提取股票代碼
        for block in converted_clean.split('\n\n'):
            if ':' in block:
                symbol = block.split(':', 1)[0].strip()
                converted_symbols.add(symbol)
    else:
        # 從長格式提取股票代碼
        for block in original_clean.split('\n\n'):
            if ':' in block:
                symbol = block.split(':', 1)[0].strip()
                original_symbols.add(symbol)
        
        # 從短格式提取股票代碼
        for line in converted_clean.split('\n'):
            if ':' in line:
                symbol = line.split(':', 1)[0].strip()
                converted_symbols.add(symbol)
    
    # 檢查股票代碼是否一致
    if original_symbols != converted_symbols:
        missing = original_symbols - converted_symbols
        extra = converted_symbols - original_symbols
        error_msg = []
        
        if missing:
            error_msg.append(f"缺少股票代碼: {', '.join(missing)}")
        if extra:
            error_msg.append(f"多出股票代碼: {', '.join(extra)}")
            
        return False, '\n'.join(error_msg)
    
    # 計算內容雜湊值，用於檢查數據完整性
    original_hash = hashlib.md5(original_clean.encode()).hexdigest()
    
    # 如果是正向轉換，再轉換回來檢查一致性
    if not is_reverse:
        back_converted = convert_to_long(converted_clean)
        back_converted_clean = '\n'.join([line.strip() for line in back_converted.strip().split('\n') if line.strip()])
        back_hash = hashlib.md5(back_converted_clean.encode()).hexdigest()
        
        # 檢查轉換回來的內容是否與原始內容一致
        if original_hash != back_hash:
            return False, "轉換後再轉換回來的內容與原始內容不一致，可能有數據丟失"
    else:
        # 如果是反向轉換，再轉換回來檢查一致性
        back_converted = convert_to_short(converted_clean)
        back_converted_clean = '\n'.join([line.strip() for line in back_converted.strip().split('\n') if line.strip()])
        
        # 與原始短格式比較
        original_short_hash = hashlib.md5(original_clean.encode()).hexdigest()
        back_short_hash = hashlib.md5(back_converted_clean.encode()).hexdigest()
        
        if original_short_hash != back_short_hash:
            return False, "反向轉換後再轉換回來的內容與原始短格式不一致，可能有數據丟失"
    
    return True, ""

def find_gex_path():
    """查找正確的GEX文件路徑"""
    possible_paths = [
        "/Users/ben/pCloud Drive/stock/GEX/GEX_file/tvcode",
        "/home/ben/pCloudDrive/stock/GEX/GEX_file/tvcode"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='轉換 Gamma Levels 數據格式')
    parser.add_argument('-r', '--reverse', action='store_true', help='將簡化格式轉換回原始格式')
    parser.add_argument('--filepath', help='指定完整的文件路徑，優先於自動查找')
    parser.add_argument('-d', '--debug', action='store_true', help='顯示調試信息')
    parser.add_argument('--overwrite', action='store_true', help='直接覆蓋原始文件')
    parser.add_argument('--force', action='store_true', help='強制轉換，即使驗證失敗')
    parser.add_argument('--log', help='指定日誌文件路徑')
    args = parser.parse_args()
    
    # 設置日誌
    log_level = logging.DEBUG if args.debug else logging.INFO
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    if args.log:
        logging.basicConfig(filename=args.log, level=log_level, format=log_format)
    else:
        logging.basicConfig(level=log_level, format=log_format)
    
    # 顯示棄用警告
    if hasattr(args, 'path') and args.path or hasattr(args, 'file') and args.file:
        logging.warning("--path 和 --file 參數已棄用，請使用 --filepath 指定完整文件路徑")
    
    # 確定文件路徑
    input_file = None
    base_path = None
    filename = None
    
    if args.filepath:
        # 優先使用完整文件路徑
        input_file = args.filepath
        # 從完整路徑中提取 base_path 和 filename
        base_path = os.path.dirname(input_file)
        filename = os.path.basename(input_file)
        logging.info(f"使用指定的完整文件路徑: {input_file}")
        logging.info(f"提取的路徑: {base_path}, 文件名: {filename}")
    else:
        # 使用自動查找的路徑
        base_path = find_gex_path()
        if not base_path:
            logging.error("錯誤：找不到有效的GEX文件路徑")
            print("錯誤：找不到有效的GEX文件路徑")
            exit(1)
        
        # 獲取文件名
        filename = get_today_filename()
        input_file = os.path.join(base_path, filename)
        logging.info(f"使用自動查找的文件路徑: {input_file}")
    
    # 確保 base_path 和 filename 已經設置
    if base_path is None or filename is None:
        logging.error("錯誤：base_path 或 filename 未設置")
        print("錯誤：base_path 或 filename 未設置")
        exit(1)
        
    if args.overwrite:
        # 如果使用覆蓋模式，輸出文件就是輸入文件
        output_file = input_file
    else:
        # 修改命名方式：轉換後的檔案使用原始檔名，原始檔案加上 orig 字樣
        if args.reverse:
            # 反向轉換時，輸入檔案是原始檔案，輸出檔案是原始格式加上 orig 字樣
            output_file = os.path.join(base_path, f"orig_{filename}")
        else:
            # 正向轉換時，輸入檔案是原始檔案，輸出檔案直接使用原始檔名
            # 先備份原始檔案
            orig_backup = os.path.join(base_path, f"orig_{filename}")
            if not os.path.exists(orig_backup):
                try:
                    import shutil
                    shutil.copy2(input_file, orig_backup)
                    print(f"已備份原始檔案至 {orig_backup}")
                    logging.info(f"已備份原始檔案至 {orig_backup}")
                except Exception as e:
                    error_msg = f"警告：備份原始檔案時出錯: {str(e)}"
                    print(error_msg)
                    logging.warning(error_msg)
            output_file = input_file
    
    # 檢查輸入文件是否存在
    if not os.path.exists(input_file):
        error_msg = f"錯誤：找不到輸入文件 {input_file}"
        logging.error(error_msg)
        print(error_msg)
        exit(1)
    
    try:
            
        # 讀取輸入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = f.read()
            if args.debug:
                logging.debug(f"讀取的輸入數據：\n{input_data}\n")
                print(f"讀取的輸入數據：\n{input_data}\n")
        
        # 根據參數選擇轉換方向
        if args.reverse:
            output = convert_to_long(input_data)
            logging.info("執行反向轉換：從簡化格式轉換為原始格式")
        else:
            output = convert_to_short(input_data)
            logging.info("執行正向轉換：從原始格式轉換為簡化格式")
        
        if args.debug:
            logging.debug(f"轉換後的數據：\n{output}\n")
            print(f"轉換後的數據：\n{output}\n")
        
        # 驗證轉換結果
        is_valid, error_msg = validate_conversion(input_data, output, args.reverse)
        
        if not is_valid:
            logging.warning(f"轉換驗證失敗: {error_msg}")
            print(f"警告：轉換驗證失敗: {error_msg}")
            
            if not args.force:
                print("轉換未完成。如果仍要繼續，請使用 --force 參數強制轉換。")
                logging.error("轉換中止：驗證失敗且未使用 --force 參數")
                exit(1)
            else:
                print("警告：強制繼續轉換，即使驗證失敗")
                logging.warning("強制繼續轉換，即使驗證失敗")
        else:
            logging.info("轉換驗證成功：數據保持一致性")
            print("轉換驗證成功：數據保持一致性")
        
        # 保存到輸出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        
        logging.info(f"轉換完成！文件已更新：{output_file}")
        print(f"轉換完成！")
        print(f"文件已更新：{output_file}")
        
    except Exception as e:
        logging.error(f"錯誤：處理文件時發生錯誤 - {str(e)}")
        print(f"錯誤：處理文件時發生錯誤 - {str(e)}")
        if args.debug:
            import traceback
            traceback_str = traceback.format_exc()
            logging.debug(traceback_str)
            print(traceback_str)
        exit(1)