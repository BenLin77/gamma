import re
import argparse
from datetime import datetime
import os

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
    parser.add_argument('-p', '--path', help='指定GEX文件路徑')
    parser.add_argument('-d', '--debug', action='store_true', help='顯示調試信息')
    parser.add_argument('-f', '--file', help='指定要處理的文件名')
    parser.add_argument('--overwrite', action='store_true', help='直接覆蓋原始文件')
    args = parser.parse_args()
    
    # 確定文件路徑
    base_path = args.path if args.path else find_gex_path()
    if not base_path:
        print("錯誤：找不到有效的GEX文件路徑")
        exit(1)
    
    # 獲取文件名
    filename = args.file if args.file else get_today_filename()
    input_file = os.path.join(base_path, filename)
    
    if args.overwrite:
        # 如果使用覆蓋模式，輸出文件就是輸入文件
        output_file = input_file
    else:
        # 修改命名方式：轉換後的檔案使用原始檔名，原始檔案加上 orig 字樣
        if args.reverse:
            # 反向轉換時，輸入檔案是原始檔案，輸出檔案是原始格式加上 orig 字樣
            input_file = os.path.join(base_path, filename)
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
                except Exception as e:
                    print(f"警告：備份原始檔案時出錯: {str(e)}")
            output_file = input_file
    
    # 檢查輸入文件是否存在
    if not os.path.exists(input_file):
        print(f"錯誤：找不到輸入文件 {input_file}")
        exit(1)
    
    try:
        # 讀取輸入文件
        with open(input_file, 'r', encoding='utf-8') as f:
            input_data = f.read()
            if args.debug:
                print(f"讀取的輸入數據：\n{input_data}\n")
        
        # 根據參數選擇轉換方向
        if args.reverse:
            output = convert_to_long(input_data)
        else:
            output = convert_to_short(input_data)
        
        if args.debug:
            print(f"轉換後的數據：\n{output}\n")
        
        # 保存到輸出文件
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(output)
        
        print(f"轉換完成！")
        print(f"文件已更新：{output_file}")
        
    except Exception as e:
        print(f"錯誤：處理文件時發生錯誤 - {str(e)}")
        if args.debug:
            import traceback
            traceback.print_exc()
        exit(1)