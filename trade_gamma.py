import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
import matplotlib.dates as mdates
from matplotlib.ticker import AutoMinorLocator
import seaborn as sns
import mplfinance as mpf

def calculate_next_day_probability(df, indicator_col, price_col='Close'):
    """計算指標上升時，價格在下一個交易日上升的機率"""
    # 計算指標和價格的日變化
    indicator_change = df[indicator_col].diff()
    next_day_price_change = df[price_col].diff().shift(-1)
    
    # 當指標上升時
    indicator_up_days = indicator_change > 0
    
    # 計算在指標上升日中，下一日價格也上升的比例
    if indicator_up_days.sum() == 0:
        return 0
    
    probability = (next_day_price_change[indicator_up_days] > 0).mean()
    return probability * 100

def analyze_correlations(df):
    """分析各指標之間的相關性"""
    base_cols = ['Close']
    optional_cols = ['Call Wall', 'Put Wall', 'Gamma Flip', 'Put Dominate', 'Call Dominate']
    cols = base_cols + [col for col in optional_cols if col in df.columns]
    corr_matrix = df[cols].corr()
    return corr_matrix

def plot_correlation_heatmap(corr_matrix, stock_name, output_dir):
    """繪製相關性熱圖"""
    plt.figure(figsize=(10, 8))
    sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', vmin=-1, vmax=1, center=0)
    plt.title(f'{stock_name} - Correlation Matrix')
    plt.tight_layout()
    plt.savefig(output_dir / f'{stock_name}_correlation.png', bbox_inches='tight', dpi=300)
    plt.close()

def analyze_stock_data(excel_file):
    # Read all sheets from the Excel file
    excel = pd.ExcelFile(excel_file)
    
    # 創建結果DataFrame
    results = []
    
    # 創建輸出目錄
    output_dir = Path('charts')
    output_dir.mkdir(exist_ok=True)
    
    # 獲取文件類型（Major或Minor）
    file_type = 'Major' if 'Major' in excel_file else 'Minor'
    
    # Print column names for debugging
    print(f"\nChecking columns in {excel_file}:")
    first_sheet = excel.sheet_names[0]
    df_sample = pd.read_excel(excel_file, sheet_name=first_sheet)
    print("Available columns:", df_sample.columns.tolist())
    
    # Process each sheet (stock)
    for sheet_name in excel.sheet_names:
        # Read the sheet
        df = pd.read_excel(excel_file, sheet_name=sheet_name)
        
        # Convert Date column to datetime and set it as index
        df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d')
        df = df.set_index('Date')
        
        # 確保數據類型正確
        numeric_columns = ['Open', 'High', 'Low']
        optional_columns = ['Call Wall', 'Put Wall', 'Gamma Flip', 'Put Dominate', 'Call Dominate']
        
        # 只處理存在的欄位
        numeric_columns.extend([col for col in optional_columns if col in df.columns])
        
        for col in numeric_columns:
            if col in df.columns:  # 只有當欄位存在時才進行轉換
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 清理數據，移除任何有NaN的行
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
        
        # 準備K線圖數據
        ohlc_data = df[['Open', 'High', 'Low', 'Close']].copy()
        
        # 確保索引是日期時間格式
        ohlc_data.index = pd.to_datetime(ohlc_data.index)
        
        # 計算各指標與Close的相關性和上升機率
        probabilities = {
            'Stock': sheet_name,
        }
        
        # 為每個存在的指標計算機率
        for indicator in optional_columns:
            if indicator in df.columns:
                prob_key = f'{indicator} → Close'
                probabilities[prob_key] = round(calculate_next_day_probability(df, indicator), 1)
        
        results.append(probabilities)
        
        # 計算相關性矩陣
        corr_matrix = analyze_correlations(df)
        
        # 繪製相關性熱圖
        plot_correlation_heatmap(corr_matrix, f"{file_type}_{sheet_name}", output_dir)
        
        # 創建K線圖
        fig = plt.figure(figsize=(15, 8), dpi=150)
        
        # 繪製K線圖
        mpf.plot(ohlc_data, 
                type='candle',
                style='charles',
                ylabel='Price',
                volume=False,
                returnfig=True,
                show_nontrading=True,
                tight_layout=True,
                ax=plt.gca())
        
        # 添加其他指標線
        colors = {
            'Call Wall': ('green', '--'),
            'Put Wall': ('purple', '--'),
            'Gamma Flip': ('red', ':'),
            'Call Dominate': ('blue', '-.'),
            'Put Dominate': ('orange', '-.')
        }
        
        for indicator, (color, style) in colors.items():
            if indicator in df.columns:
                plt.plot(df.index, df[indicator], label=indicator, color=color, 
                        linewidth=2, linestyle=style)
        
        # 設置圖表
        plt.grid(True, which='major', linestyle='-', alpha=0.7)
        plt.grid(True, which='minor', linestyle=':', alpha=0.4)
        plt.legend(loc='upper left')
        plt.tick_params(axis='x', rotation=45)
        
        # 調整布局並保存圖表
        plt.tight_layout()
        plt.savefig(output_dir / f'{file_type}_{sheet_name}_analysis.png', 
                   bbox_inches='tight', dpi=300)
        plt.close()
    
    # 打印分析結果
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False))
    
    return results

def main():
    # 設定輸出目錄
    output_dir = Path('charts')
    output_dir.mkdir(exist_ok=True)
    
    # 創建結果列表
    all_results = []
    
    # 分析 Major 數據
    major_file = 'TV Code Major.xlsx'
    print("\nMajor 相關性分析結果：")
    major_results = analyze_stock_data(major_file)
    all_results.extend(major_results)
    
    # 分析 Minor 數據
    minor_file = 'TV Code Minor.xlsx'
    print("\nMinor 相關性分析結果：")
    minor_results = analyze_stock_data(minor_file)
    all_results.extend(minor_results)
    
    # 合併並保存所有結果
    results_df = pd.DataFrame(all_results)
    results_df.to_csv(output_dir / 'probability_analysis.csv', index=False, float_format='%.1f')

if __name__ == '__main__':
    main()
