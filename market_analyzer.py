import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

class FSAnalyzer:
    def __init__(self):
        """初始化分析器"""
        self.df = None
        
    def load_excel_data(self, file_path, sheet_name):
        """載入Excel檔案"""
        try:
            # 讀取Excel檔案
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            print(f"\n正在載入 {sheet_name} 工作表...")
            
            # 確保必要的欄位存在
            required_columns = ['Date', 'Close']
            if not all(col in df.columns for col in required_columns):
                print(f"錯誤: 缺少必要的欄位 {required_columns}")
                return False
            
            # 處理日期數據
            print("正在處理日期數據...")
            df['Date'] = pd.to_datetime(df['Date'])
            df['Month'] = df['Date'].dt.strftime('%Y-%m')  # 添加月份欄位
            
            print(f"成功載入 {len(df)} 筆記錄")
            print(f"日期範圍: {df['Date'].min()} 到 {df['Date'].max()}")
            print(f"可用欄位: {df.columns.tolist()}")
            
            self.df = df
            return True
                
        except Exception as e:
            print(f"載入Excel檔案時發生錯誤: {str(e)}")
            return False
            
    def handle_missing_values(self):
        """處理資料框中的空值"""
        if self.df is not None:
            # 使用前向填充和後向填充方法填充空值
            self.df.ffill(inplace=True)
            self.df.bfill(inplace=True)
            print("已處理空值，使用前向填充和後向填充方法。")

    def find_closest_indicator(self, valid_indicators, price_label, price_value):
        """找出與指定價格最接近的指標"""
        try:
            print(f"\n正在計算{price_label}的指標距離...")
            # 計算每個指標與指定價格的距離
            distance_columns = []
            for indicator in valid_indicators:
                # 確保指標和指定價格都是數值型別
                if indicator in self.df.columns:
                    self.df[indicator] = pd.to_numeric(self.df[indicator], errors='coerce')
                    price_series = pd.Series([price_value] * len(self.df))

                    # 只在兩個值都不是 NaN 時計算距離
                    mask = self.df[indicator].notna() & price_series.notna()
                    distance_col = f"{indicator}_distance_{price_label}"
                    self.df[distance_col] = float('nan')  # 初始化為 NaN
                    self.df.loc[mask, distance_col] = abs(
                        self.df.loc[mask, indicator] - price_series.loc[mask]
                    )
                    distance_columns.append(distance_col)

            # 找出距離最小的指標
            if distance_columns:
                print(f"正在找出與{price_label}最接近的指標...")
                # 只在至少有一個非 NaN 值時找最小值
                self.df[f'closest_indicator_{price_label}'] = None
                valid_rows = self.df[distance_columns].notna().any(axis=1)
                if valid_rows.any():
                    self.df.loc[valid_rows, f'closest_indicator_{price_label}'] = (
                        self.df.loc[valid_rows, distance_columns]
                        .idxmin(axis=1, skipna=True)
                        .str.replace(f'_distance_{price_label}', '')
                    )

            print(f"找到的距離欄位：{distance_columns}")
            print(f"欄位: {self.df.columns.tolist()}")

        except Exception as e:
            print(f"計算與{price_label}最接近指標時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()

    def calculate_period_stats(self, data):
        """計算特定期間的統計數據"""
        stats = []
        
        # 基本價格統計
        stats.append("價格統計：")
        for col in ['Open', 'High', 'Low', 'Close']:
            if col in data.columns:
                stats.append(f"{col}:")
                stats.append(f"  最高: {data[col].max():.2f}")
                stats.append(f"  最低: {data[col].min():.2f}")
                stats.append(f"  平均: {data[col].mean():.2f}")
                stats.append(f"  標準差: {data[col].std():.2f}")
        stats.append("")
        
        # 計算指標出現次數
        indicator_columns = ['Call Wall', 'Call Wall CE', 'Call Dominate', 
                           'Put Wall', 'Put Wall CE', 'Put Dominate',
                           'Gamma Flip', 'Gamma Flip CE', 'Gamma Field', 'Gamma Field CE']
        
        stats.append("指標統計：")
        closest_counts = {}
        if 'closest_indicator_Close' in data.columns:
            closest_counts = data['closest_indicator_Close'].value_counts()
            for indicator, count in closest_counts.items():
                if pd.notna(indicator):
                    stats.append(f"{indicator} 最接近收盤價次數: {count} ({(count/len(data)*100):.1f}%)")
        stats.append("")
        
        # 計算與 VIX 的相關性
        if 'VIX' in data.columns:
            stats.append("與 VIX 的相關性：")
            for indicator in indicator_columns:
                if indicator in data.columns:
                    correlation = data[indicator].corr(data['VIX'])
                    if not pd.isna(correlation):
                        stats.append(f"{indicator}: {correlation:.3f}")
            stats.append("")
        
        # 波動性分析
        stats.append("波動性分析：")
        if 'Close' in data.columns:
            daily_returns = data['Close'].pct_change()
            stats.append(f"日均波動率: {daily_returns.std()*100:.2f}%")
            stats.append(f"最大單日漲幅: {daily_returns.max()*100:.2f}%")
            stats.append(f"最大單日跌幅: {daily_returns.min()*100:.2f}%")
        stats.append("")
        
        # 趨勢分析
        if 'Close' in data.columns:
            stats.append("趨勢分析：")
            start_price = data['Close'].iloc[0]
            end_price = data['Close'].iloc[-1]
            price_change = (end_price - start_price) / start_price * 100
            stats.append(f"期間漲跌幅: {price_change:.2f}%")
            
            # 計算上漲和下跌天數
            daily_changes = data['Close'].diff()
            up_days = len(daily_changes[daily_changes > 0])
            down_days = len(daily_changes[daily_changes < 0])
            flat_days = len(daily_changes[daily_changes == 0])
            total_days = len(daily_changes)
            
            stats.append(f"上漲天數: {up_days} ({up_days/total_days*100:.1f}%)")
            stats.append(f"下跌天數: {down_days} ({down_days/total_days*100:.1f}%)")
            stats.append(f"持平天數: {flat_days} ({flat_days/total_days*100:.1f}%)")
        stats.append("")
        
        # 指標預測準確度分析
        if 'Close' in data.columns and len(data) > 1:
            stats.append("指標預測準確度分析：")
            for indicator in indicator_columns:
                if indicator in data.columns:
                    # 計算指標預測正確的次數（當指標值接近實際收盤價時）
                    accuracy = self.calculate_indicator_accuracy(data, indicator)
                    if accuracy is not None:
                        stats.append(f"{indicator} 預測準確度: {accuracy:.1f}%")
        stats.append("")
        
        return stats

    def calculate_indicator_accuracy(self, data, indicator):
        """計算指標的預測準確度"""
        if indicator not in data.columns or 'Close' not in data.columns:
            return None
            
        # 將指標值與下一天的收盤價比較
        data = data.copy()
        data['next_close'] = data['Close'].shift(-1)
        data['indicator_diff'] = (data[indicator] - data['Close']).abs()
        data['actual_diff'] = (data['next_close'] - data['Close']).abs()
        
        # 計算預測正確的次數（指標與實際價格的差異小於某個閾值）
        threshold = data['Close'].std() * 0.1  # 使用收盤價標準差的10%作為閾值
        correct_predictions = len(data[data['indicator_diff'] <= threshold])
        total_predictions = len(data.dropna())
        
        if total_predictions == 0:
            return None
            
        return (correct_predictions / total_predictions) * 100

    def generate_statistics(self, symbol):
        """生成統計報告和圖表"""
        try:
            # 確保日期欄位存在
            if 'Date' not in self.df.columns:
                print("錯誤：找不到日期欄位")
                return
        
            # 準備統計報告
            report = []
            report.append(f"=== {symbol} 統計報告 ===\n")
            report.append(f"分析期間：{self.df['Date'].min().strftime('%Y-%m-%d')} 到 {self.df['Date'].max().strftime('%Y-%m-%d')}\n")
            report.append(f"總記錄數：{len(self.df)} 筆\n\n")
        
            # 計算總體統計
            total_stats = self.calculate_period_stats(self.df)
            report.append("=== 總體統計 ===\n")
            report.append("\n".join(total_stats))
            report.append("\n")
        
            # 計算每月統計
            report.append("=== 月度統計 ===\n")
            for month in sorted(self.df['Month'].unique()):
                monthly_data = self.df[self.df['Month'] == month]
                if not monthly_data.empty:
                    report.append(f"\n--- {month} ---")
                    report.append(f"數據筆數: {len(monthly_data)}")
                    monthly_stats = self.calculate_period_stats(monthly_data)
                    report.append("\n".join(monthly_stats))
        
            # 寫入報告文件
            os.makedirs('charts', exist_ok=True)
            report_file = f'charts/{symbol.lower()}.txt'
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report))
            print(f"已生成 {report_file} 統計報告")
        
        except Exception as e:
            print(f"生成統計報告時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()

    def generate_monthly_chart(self, data, symbol, month):
        """生成月度圖表"""
        try:
            if data.empty:
                print(f"錯誤: {month} 的資料框為空，無法生成圖表。")
                return
            
            # 檢查必要的欄位
            required_columns = ['Date', 'Open', 'High', 'Low', 'Close']
            if not all(col in data.columns for col in required_columns):
                print(f"錯誤: {month} 缺少必要的欄位 {required_columns}，無法生成圖表。")
                return
            
            # 確保所有必要欄位都有數據
            if data[required_columns].isnull().any().any():
                print(f"錯誤: {month} 的必要欄位中存在空值，無法生成圖表。")
                return
            
            # 創建圖表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), height_ratios=[2, 1])
            fig.suptitle(f'{symbol} vs VIX Analysis - {month}', fontsize=16)
            
            # 設置圖表樣式
            plt.style.use('default')
            plt.rcParams['axes.grid'] = True
            plt.rcParams['grid.linestyle'] = '--'
            plt.rcParams['grid.alpha'] = 0.5
            
            # 上半部圖表標題
            ax1.set_title(f'{symbol} Price and Indicators')
            
            # 確保日期是正確的格式
            dates = mdates.date2num(data['Date'].tolist())
            
            # 準備K線圖數據
            ohlc = []
            for idx, row in data.iterrows():
                if all(pd.notna(row[col]) for col in required_columns):
                    ohlc.append([
                        mdates.date2num(row['Date']),
                        float(row['Open']),
                        float(row['High']),
                        float(row['Low']),
                        float(row['Close'])
                    ])
            
            if ohlc:  # 只有在有數據時才繪製K線圖
                # 繪製K線圖
                from mplfinance.original_flavor import candlestick_ohlc
                candlestick_ohlc(ax1, ohlc, width=0.6, colorup='g', colordown='r')
                
                # 定義指標和顏色
                indicators = {
                    'Call Wall': 'green',
                    'Call Wall CE': 'lime',
                    'Call Dominate': 'cyan',
                    'Put Wall': 'red',
                    'Put Wall CE': 'orange',
                    'Put Dominate': 'magenta',
                    'Gamma Flip': 'blue',
                    'Gamma Flip CE': 'purple',
                    'Gamma Field': 'yellow',
                    'Gamma Field CE': 'brown',
                    'Implied Movement -σ': 'gray',
                    'Implied Movement -2σ': 'darkgray',
                    'Implied Movement +σ': 'lightgray',
                    'Implied Movement +2σ': 'silver',
                    'Implied Movement -3σ': 'pink',
                    'Implied Movement +3σ': 'olive'
                }
                
                # 為每個價格點找出最接近的指標
                for idx, row in data.iterrows():
                    # 檢查每個價格點（最高價、最低價、收盤價）
                    price_points = {
                        'High': float(row['High']),
                        'Low': float(row['Low']),
                        'Close': float(row['Close'])
                    }
                    
                    for price_type, price in price_points.items():
                        min_distance = float('inf')
                        closest_indicator = None
                        closest_value = None
                        
                        # 檢查所有指標
                        for indicator in indicators.keys():
                            if indicator in row and pd.notna(row[indicator]):
                                distance = abs(price - float(row[indicator]))
                                if distance < min_distance:
                                    min_distance = distance
                                    closest_indicator = indicator
                                    closest_value = float(row[indicator])
                        
                        # 如果找到最接近的指標，就畫出來
                        if closest_indicator:
                            label = f"{closest_indicator}" if closest_indicator not in ax1.get_legend_handles_labels()[1] else "_nolegend_"
                            ax1.scatter(mdates.date2num(row['Date']), closest_value,
                                      color=indicators[closest_indicator],
                                      alpha=0.7, marker='o', label=label)
            
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Price')
                ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
                # 設置x軸格式
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax1.xaxis.set_major_locator(mdates.DayLocator(interval=5))
                plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
            
                # 調整布局以確保圖例不會被截斷
                plt.subplots_adjust(right=0.85)
            
                # 保存圖表
                os.makedirs('charts', exist_ok=True)  # 確保charts目錄存在
                chart_path = os.path.join('charts', f"{symbol.lower()}_{month}.png")
                plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                plt.close(fig)  # 關閉圖表以釋放記憶體
            
                print(f"已生成 {chart_path} 圖表")
            else:
                print(f"警告: {month} 沒有足夠的OHLC數據來生成K線圖")
            
        except Exception as e:
            print(f"生成月度圖表時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()
        
class VixSpxAnalyzer:
    def __init__(self, vix_data, spx_data):
        """初始化VIX和SPX分析器"""
        self.vix_data = vix_data.copy()
        self.spx_data = spx_data.copy()
        
        # 確保日期格式一致
        self.vix_data['Date'] = pd.to_datetime(self.vix_data['Date']).dt.date
        self.spx_data['Date'] = pd.to_datetime(self.spx_data['Date']).dt.date
        
    def analyze_vix_spx_patterns(self, consecutive_days=3):
        """分析VIX連續上升的模式及其對SPX的影響
        
        Args:
            consecutive_days (int): 連續幾天VIX沒有下降的閾值
        """
        results = []
        
        # 確保日期排序並重置索引
        self.vix_data = self.vix_data.sort_values('Date').reset_index(drop=True)
        self.spx_data = self.spx_data.sort_values('Date').reset_index(drop=True)
        
        # 計算VIX的變化並處理空值
        self.vix_data['VIX_Change'] = self.vix_data['Close'].diff()
        self.vix_data['VIX_Change'] = self.vix_data['VIX_Change'].fillna(0)
        
        # 尋找連續上升的期間
        pattern_start = None
        consecutive_count = 0
        
        for idx, row in self.vix_data.iterrows():
            if row['VIX_Change'] >= 0:  # VIX沒有下降
                if pattern_start is None:
                    pattern_start = row['Date']
                consecutive_count += 1
            else:  # VIX下降
                if consecutive_count >= consecutive_days:
                    # 找到符合條件的模式
                    pattern_end = self.vix_data.loc[idx-1, 'Date']
                    
                    # 分析這段期間的SPX走勢
                    spx_period = self.spx_data[
                        (self.spx_data['Date'] >= pattern_start) &
                        (self.spx_data['Date'] <= pattern_end)
                    ]
                    
                    if not spx_period.empty:
                        spx_change = (spx_period['Close'].iloc[-1] - spx_period['Close'].iloc[0]) / spx_period['Close'].iloc[0] * 100
                        vix_change = (self.vix_data[self.vix_data['Date'] == pattern_end]['Close'].iloc[0] -
                                    self.vix_data[self.vix_data['Date'] == pattern_start]['Close'].iloc[0])
                        
                        results.append({
                            'start_date': pattern_start,
                            'end_date': pattern_end,
                            'duration': consecutive_count,
                            'spx_change_pct': spx_change,
                            'vix_change': vix_change,
                            'initial_vix': self.vix_data[self.vix_data['Date'] == pattern_start]['Close'].iloc[0],
                            'final_vix': self.vix_data[self.vix_data['Date'] == pattern_end]['Close'].iloc[0]
                        })
                
                pattern_start = None
                consecutive_count = 0
        
        return pd.DataFrame(results)
    
    def analyze_vix_streaks(self):
        """分析VIX連續上升的模式"""
        # 確保日期格式正確
        if not pd.api.types.is_datetime64_any_dtype(self.vix_data['Date']):
            self.vix_data['Date'] = pd.to_datetime(self.vix_data['Date'])
        if not pd.api.types.is_datetime64_any_dtype(self.spx_data['Date']):
            self.spx_data['Date'] = pd.to_datetime(self.spx_data['Date'])
            
        # 計算VIX的變化
        self.vix_data['VIX_Change'] = self.vix_data['Close'].pct_change()
        self.vix_data['VIX_Change_Streak'] = (self.vix_data['VIX_Change'] > 0).astype(int)
        
        # 找出連續上升的天數
        streak_groups = []
        current_streak = 0
        
        for i in range(len(self.vix_data)):
            if self.vix_data['VIX_Change'].iloc[i] > 0:
                current_streak += 1
            else:
                if current_streak >= 3:  # 只記錄3天或以上的連續上升
                    streak_start = i - current_streak
                    streak_groups.append({
                        'start_idx': streak_start,
                        'end_idx': i - 1,
                        'duration': current_streak
                    })
                current_streak = 0
        
        # 分析每個連續上升期間的SPX表現
        results = []
        for streak in streak_groups:
            start_date = self.vix_data['Date'].iloc[streak['start_idx']]
            end_date = self.vix_data['Date'].iloc[streak['end_idx']]
            
            # VIX數據
            streak_vix = self.vix_data.iloc[streak['start_idx']:streak['end_idx']+1]
            vix_start = streak_vix['Close'].iloc[0]
            vix_end = streak_vix['Close'].iloc[-1]
            vix_change = (vix_end - vix_start) / vix_start * 100
            
            # SPX數據
            spx_data = self.spx_data[
                (self.spx_data['Date'].dt.date >= start_date.date()) & 
                (self.spx_data['Date'].dt.date <= end_date.date())
            ]
            
            if len(spx_data) > 0:
                spx_start = spx_data['Close'].iloc[0]
                spx_end = spx_data['Close'].iloc[-1]
                spx_change = (spx_end - spx_start) / spx_start * 100
                
                results.append({
                    'start_date': start_date,
                    'end_date': end_date,
                    'duration': streak['duration'],
                    'initial_vix': vix_start,
                    'final_vix': vix_end,
                    'vix_change': vix_change,
                    'spx_change': spx_change
                })
        
        # 轉換為DataFrame並保存結果
        self.pattern_results = pd.DataFrame(results)
        
        # 生成報告
        report = self.generate_analysis_report()
        print("\n" + report)
        
        return self.pattern_results

    def generate_analysis_report(self):
        """生成分析報告"""
        report = []
        report.append("VIX和SPX關係分析報告\n")
        report.append("=" * 50 + "\n")
        
        # Convert dates to datetime if they're not already
        if not pd.api.types.is_datetime64_any_dtype(self.vix_data['Date']):
            self.vix_data['Date'] = pd.to_datetime(self.vix_data['Date'])
        
        # Get the date range
        min_date = self.vix_data['Date'].min()
        max_date = self.vix_data['Date'].max()
        report.append(f"分析期間: {min_date.strftime('%Y-%m-%d')} 至 {max_date.strftime('%Y-%m-%d')}\n")
        
        # VIX統計
        report.append("\nVIX統計:")
        report.append(f"平均值: {self.vix_data['Close'].mean():.2f}")
        report.append(f"最大值: {self.vix_data['Close'].max():.2f}")
        report.append(f"最小值: {self.vix_data['Close'].min():.2f}")
        report.append(f"中位數: {self.vix_data['Close'].median():.2f}\n")
        
        # 分析不同VIX水平下的市場行為
        vix_levels = [15, 17, 20, 25]
        for vix_level in vix_levels:
            high_vix_days = self.vix_data[self.vix_data['Close'] > vix_level]
            if len(high_vix_days) > 0:
                report.append(f"\nVIX > {vix_level} 的分析:")
                report.append(f"總天數: {len(high_vix_days)}天")
                report.append(f"佔總樣本比例: {(len(high_vix_days) / len(self.vix_data) * 100):.2f}%")
                
                # 分析這些天數的SPX變化
                if hasattr(self, 'spx_data'):
                    high_vix_dates = high_vix_days['Date'].tolist()
                    spx_on_high_vix = self.spx_data[self.spx_data['Date'].isin(high_vix_dates)]
                    if len(spx_on_high_vix) > 0:
                        spx_changes = spx_on_high_vix['Close'].pct_change()
                        report.append(f"SPX平均日變化: {spx_changes.mean()*100:.2f}%")
                        report.append(f"SPX上漲天數比例: {(spx_changes > 0).mean()*100:.2f}%")
        
        return "\n".join(report)

    def analyze_vix_put_wall(self):
        """分析VIX Put Wall的變化"""
        print("\n=== VIX Put Wall分析 ===")
        if 'Put Wall' in self.vix_data.columns:
            # 確保日期格式正確
            if not pd.api.types.is_datetime64_any_dtype(self.vix_data['Date']):
                self.vix_data['Date'] = pd.to_datetime(self.vix_data['Date'])
            if not pd.api.types.is_datetime64_any_dtype(self.spx_data['Date']):
                self.spx_data['Date'] = pd.to_datetime(self.spx_data['Date'])
            
            # 計算Put Wall的變化
            self.vix_data['Put_Wall_Change'] = self.vix_data['Put Wall'].pct_change()
            
            # 找出Put Wall保持不變或上升的期間
            stable_periods = []
            current_period = {'start': None, 'end': None, 'count': 0}
            
            for i in range(1, len(self.vix_data)):
                if self.vix_data['Put_Wall_Change'].iloc[i] >= 0:
                    if current_period['start'] is None:
                        current_period['start'] = i - 1
                    current_period['count'] += 1
                else:
                    if current_period['count'] >= 3:  # 只記錄3天或以上的連續上升
                        current_period['end'] = i - 1
                        stable_periods.append(current_period.copy())
                    current_period = {'start': None, 'end': None, 'count': 0}
            
            # 分析每個連續上升期間的SPX表現
            results = []
            for period in stable_periods:
                start_date = self.vix_data['Date'].iloc[period['start']]
                end_date = self.vix_data['Date'].iloc[period['end']]
                
                # VIX數據
                period_vix = self.vix_data.iloc[period['start']:period['end']+1]
                vix_start = period_vix['Close'].iloc[0]
                vix_end = period_vix['Close'].iloc[-1]
                put_wall_start = period_vix['Put Wall'].iloc[0]
                put_wall_end = period_vix['Put Wall'].iloc[-1]
                
                # SPX數據
                spx_period = self.spx_data[
                    (self.spx_data['Date'].dt.date >= start_date.date()) & 
                    (self.spx_data['Date'].dt.date <= end_date.date())
                ]
                
                if len(spx_period) > 0:
                    spx_start = spx_period['Close'].iloc[0]
                    spx_end = spx_period['Close'].iloc[-1]
                    spx_change = (spx_end - spx_start) / spx_start * 100
                    
                    results.append({
                        'start_date': start_date,
                        'end_date': end_date,
                        'duration': period['count'],
                        'vix_start': vix_start,
                        'vix_end': vix_end,
                        'vix_change': (vix_end - vix_start) / vix_start * 100,
                        'put_wall_start': put_wall_start,
                        'put_wall_end': put_wall_end,
                        'put_wall_change': (put_wall_end - put_wall_start) / put_wall_start * 100,
                        'spx_change': spx_change
                    })
            
            # 輸出分析結果
            if results:
                df_results = pd.DataFrame(results)
                print(f"\n找到 {len(df_results)} 個VIX Put Wall穩定或上升的期間（持續3天或以上）")
                print("\n統計摘要:")
                print(f"平均持續天數: {df_results['duration'].mean():.1f}天")
                print(f"平均VIX變化: {df_results['vix_change'].mean():.2f}%")
                print(f"平均Put Wall變化: {df_results['put_wall_change'].mean():.2f}%")
                print(f"平均SPX變化: {df_results['spx_change'].mean():.2f}%")
                print(f"SPX上漲比例: {(df_results['spx_change'] > 0).mean()*100:.1f}%")
                
                print("\n詳細期間列表:")
                for _, period in df_results.iterrows():
                    print(f"\n時間區間: {period['start_date'].strftime('%Y-%m-%d')} 至 {period['end_date'].strftime('%Y-%m-%d')} ({period['duration']}天)")
                    print(f"VIX: {period['vix_start']:.2f} → {period['vix_end']:.2f} ({period['vix_change']:.2f}%)")
                    print(f"Put Wall: {period['put_wall_start']:.2f} → {period['put_wall_end']:.2f} ({period['put_wall_change']:.2f}%)")
                    print(f"SPX變化: {period['spx_change']:.2f}%")
            else:
                print("未發現VIX Put Wall穩定或上升的期間（持續3天或以上）")
        else:
            print("VIX數據中未找到Put Wall欄位")

    def _analyze_vix_put_wall_flat_periods(self):
        """分析VIX Put Wall連續三天沒下降後的SPX走勢"""
        print("\n=== VIX Put Wall平穩期分析 ===\n")
        
        # 計算Put Wall的日變化率
        self.vix_data['Put_Wall_Change'] = self.vix_data['Put Wall'].pct_change()
        
        # 初始化變量
        flat_periods = []
        current_period = None
        min_days = 3
        
        # 遍歷數據找出Put Wall平穩期
        for i in range(len(self.vix_data)):
            row = self.vix_data.iloc[i]
            
            # 如果Put Wall沒有下降（變化率>=0或為NaN）
            if pd.isna(row['Put_Wall_Change']) or row['Put_Wall_Change'] >= 0:
                if current_period is None:
                    current_period = {'start_idx': i, 'start_date': row['Date']}
            else:
                if current_period is not None:
                    period_length = i - current_period['start_idx']
                    if period_length >= min_days:
                        current_period['end_idx'] = i - 1
                        current_period['end_date'] = self.vix_data.iloc[i-1]['Date']
                        flat_periods.append(current_period)
                    current_period = None
        
        # 處理最後一個可能的平穩期
        if current_period is not None:
            period_length = len(self.vix_data) - current_period['start_idx']
            if period_length >= min_days:
                current_period['end_idx'] = len(self.vix_data) - 1
                current_period['end_date'] = self.vix_data.iloc[-1]['Date']
                flat_periods.append(current_period)
        
        # 分析每個平穩期後的SPX走勢
        print(f"找到 {len(flat_periods)} 個Put Wall連續{min_days}天或以上沒有下降的期間\n")
        
        # 統計變量
        total_spx_changes = []
        spx_up_count = 0
        
        print("統計摘要:")
        print(f"平均持續天數: {sum(p['end_idx'] - p['start_idx'] + 1 for p in flat_periods) / len(flat_periods):.1f}天")
        
        print("\n詳細期間列表:\n")
        for period in flat_periods:
            start_idx = period['start_idx']
            end_idx = period['end_idx']
            
            # 計算期間內的變化
            period_length = end_idx - start_idx + 1
            start_put_wall = self.vix_data.iloc[start_idx]['Put Wall']
            end_put_wall = self.vix_data.iloc[end_idx]['Put Wall']
            put_wall_change = ((end_put_wall - start_put_wall) / start_put_wall * 100) if not pd.isna(start_put_wall) and not pd.isna(end_put_wall) else float('nan')
            
            # 分析期間結束後的SPX走勢（未來1-5天）
            future_days = min(5, len(self.spx_data) - end_idx - 1)
            if future_days > 0:
                spx_start = self.spx_data.iloc[end_idx]['Close']
                spx_changes = []
                
                for days in range(1, future_days + 1):
                    future_idx = end_idx + days
                    if future_idx < len(self.spx_data):
                        spx_end = self.spx_data.iloc[future_idx]['Close']
                        spx_change = (spx_end - spx_start) / spx_start * 100
                        spx_changes.append(spx_change)
                
                # 記錄5天內的最大變化
                if spx_changes:
                    max_change = max(spx_changes, key=abs)
                    total_spx_changes.append(max_change)
                    if max_change > 0:
                        spx_up_count += 1
                
                print(f"時間區間: {period['start_date'].strftime('%Y-%m-%d')} 至 {period['end_date'].strftime('%Y-%m-%d')} ({period_length}天)")
                print(f"Put Wall: {start_put_wall:.2f} → {end_put_wall:.2f} ({put_wall_change:.2f}%)")
                print(f"後續{future_days}天內SPX最大變化: {max_change:.2f}%")
                print(f"每日SPX變化: {', '.join([f'Day {i+1}: {change:.2f}%' for i, change in enumerate(spx_changes)])}")
                print()
        
        # 輸出總體統計
        if total_spx_changes:
            avg_spx_change = sum(total_spx_changes) / len(total_spx_changes)
            up_ratio = spx_up_count / len(total_spx_changes) * 100
            
            print("\n總體統計:")
            print(f"平均SPX最大變化: {avg_spx_change:.2f}%")
            print(f"SPX上漲比例: {up_ratio:.1f}%")
            print(f"樣本數: {len(total_spx_changes)}")

    def analyze_vix_spx_patterns(self):
        """分析VIX和SPX的關係"""
        print("\n開始分析VIX和SPX的關係...")
        
        # VIX水平分析
        self._analyze_vix_levels()
        
        # VIX Put Wall分析
        self._analyze_vix_put_wall()
        
        # VIX連續上升分析
        self._analyze_vix_streaks()
        
        # 分析VIX Put Wall連續三天沒下降後的SPX走勢
        self._analyze_vix_put_wall_flat_periods()

class MarketAnalyzer:
    def __init__(self, file_path):
        self.symbols = ['SPX', 'QQQ', 'IWM', 'SOXX']
        self.file_path = file_path
        self.data = {}
        self.merged_data = None
        
    def load_data(self):
        """載入所有股票數據"""
        try:
            print("\n開始載入數據...")
            # 讀取 Excel 檔案
            excel_file = pd.ExcelFile(self.file_path)
            print(f"Excel文件已打開，可用的工作表: {excel_file.sheet_names}\n")
            
            # 讀取每個股票的數據
            self.data = {}
            total_symbols = len(self.symbols) + 1  # +1 for VIX
            for idx, symbol in enumerate(self.symbols + ['VIX'], 1):
                print(f"[{idx}/{total_symbols}] === 處理 {symbol} ===")
        
                # 讀取工作表
                df = pd.read_excel(excel_file, sheet_name=symbol)
                print(f"載入 {len(df)} 筆記錄")
                if len(df) > 0:
                    print(f"日期範圍: {df['Date'].min()} 到 {df['Date'].max()}")
        
                # 確保日期列是 datetime 格式
                if 'Date' in df.columns:
                    df['Date'] = pd.to_datetime(df['Date'])
        
                # 如果是 VIX，不限制欄位
                if symbol == 'VIX':
                    print(f"\n正在載入 {symbol} 工作表...")
                    print("正在處理日期數據...")
                    df['Date'] = pd.to_datetime(df['Date'])
                    print(f"成功載入 {len(df)} 筆記錄")
                    print(f"日期範圍: {df['Date'].min()} 到 {df['Date'].max()}")
                    print(f"可用欄位: {df.columns.tolist()}")
                    print(f"\n欄位: {df.columns.tolist()}")
                else:
                    # 分析指標
                    analyzer = FSAnalyzer()
                    analyzer.load_excel_data(self.file_path, symbol)
                    analyzer.handle_missing_values()
                    print("\n欄位列表：")
                    print(analyzer.df.columns.tolist())
                    analyzer.find_closest_indicator([col for col in analyzer.df.columns if col not in ['Date', 'Open', 'High', 'Low', 'Close', 'TV Code']], 'Close', 520)
                    analyzer.generate_statistics(symbol)  # 生成統計報告
                    df = analyzer.df
        
                self.data[symbol] = df
        
                # 打印列名
                print(f"欄位: {df.columns.tolist()}")
        
            return True
        
        except Exception as e:
            print(f"載入數據時發生錯誤: {str(e)}")
            return False

    def analyze_vix_relationships(self):
        """分析各指標與VIX的關係"""
        # 確保 charts 目錄存在
        import os
        if not os.path.exists('charts'):
            os.makedirs('charts')
            
        vix_data = self.data['VIX'].copy()
        vix_data['Date'] = pd.to_datetime(vix_data['Date']).dt.date
        vix_thresholds = [15, 17, 20, 25]  # VIX閾值
        
        for symbol in ['SPX', 'QQQ', 'IWM', 'SOXX']:
            if symbol not in self.data:
                continue
                
            symbol_data = self.data[symbol].copy()
            symbol_data['Date'] = pd.to_datetime(symbol_data['Date']).dt.date
            print(f"\n分析 {symbol} 與 VIX 的關係...")
            
            # 合併VIX數據
            merged_data = pd.merge(symbol_data, vix_data[['Date', 'Close']], 
                                 on='Date', how='inner', suffixes=('', '_VIX'))
            print(f"合併後的數據筆數: {len(merged_data)}")
            
            # 分析每個指標
            indicators = ['Call Wall', 'Call Wall CE', 'Call Dominate', 
                        'Put Wall', 'Put Wall CE', 'Put Dominate',
                        'Gamma Flip', 'Gamma Flip CE', 'Gamma Field', 'Gamma Field CE']
            
            report = []
            report.append(f"\n=== {symbol} 與 VIX 關係分析 ===\n")
            report.append("VIX 閾值分析：")
            
            # 先分析低VIX時期
            low_vix_data = merged_data[merged_data['Close_VIX'] <= 15]
            total_low_vix = len(low_vix_data)
            report.append(f"\nVIX <= 15 時的指標出現機率：")
            
            if total_low_vix > 0:
                # 計算每個指標在低VIX時期的出現次數
                indicator_counts = {}
                for _, row in low_vix_data.iterrows():
                    closest_indicator = row['closest_indicator_Close']
                    print(f"最接近的指標: {closest_indicator}")
                    if closest_indicator in indicators:
                        indicator_counts[closest_indicator] = indicator_counts.get(closest_indicator, 0) + 1
                
                # 計算並記錄每個指標的出現機率
                for indicator, count in indicator_counts.items():
                    probability = count / total_low_vix * 100
                    report.append(f"{indicator}: {probability:.1f}% ({count}/{total_low_vix})")
            
            # 分析每個高VIX閾值
            for threshold in vix_thresholds:
                report.append(f"\nVIX > {threshold} 時的指標出現機率：")
                high_vix_data = merged_data[merged_data['Close_VIX'] > threshold]
                total_high_vix = len(high_vix_data)
                print(f"VIX > {threshold} 的數據筆數: {total_high_vix}")
                
                if total_high_vix > 0:
                    # 計算每個指標在高VIX時期的出現次數
                    indicator_counts = {}
                    for _, row in high_vix_data.iterrows():
                        closest_indicator = row['closest_indicator_Close']
                        print(f"最接近的指標: {closest_indicator}")
                        if closest_indicator in indicators:
                            indicator_counts[closest_indicator] = indicator_counts.get(closest_indicator, 0) + 1
                    
                    print(f"指標出現次數: {indicator_counts}")
                    
                    # 計算並添加每個指標的出現機率
                    for indicator, count in indicator_counts.items():
                        probability = (count / total_high_vix) * 100
                        report.append(f"{indicator}: {probability:.1f}% ({count}/{total_high_vix})")
            
            # 將報告寫入檔案
            report_text = '\n'.join(report)
            with open(f'charts/{symbol.lower()}_vix_analysis.txt', 'w', encoding='utf-8') as f:
                f.write(report_text)

            # 生成月度圖表
            merged_data['Month'] = pd.to_datetime(merged_data['Date']).dt.strftime('%Y-%m')
            for month, month_data in merged_data.groupby('Month'):
                if len(month_data) > 0:
                    print(f"\n處理 {symbol} {month} 的數據...")
                    print(f"數據筆數: {len(month_data)}")
                    self.generate_monthly_chart(month_data, symbol, month)
        
        # 生成總體分析報告
        self.generate_overall_vix_analysis()

    def generate_overall_vix_analysis(self):
        """生成總體VIX分析報告"""
        # 確保 charts 目錄存在
        import os
        if not os.path.exists('charts'):
            os.makedirs('charts')
            
        vix_data = self.data['VIX'].copy()
        vix_data['Date'] = pd.to_datetime(vix_data['Date']).dt.date
        vix_thresholds = [15, 17, 20, 25]
        
        report = []
        report.append("=== 總體 VIX 關係分析 ===\n")
        report.append("\nVIX 閾值分析（所有指數合計）：")
        
        # 先分析低VIX時期
        all_indicators_count = {}
        total_low_vix = 0
        
        for symbol in ['SPX', 'QQQ', 'IWM', 'SOXX']:
            if symbol not in self.data:
                continue
                
            symbol_data = self.data[symbol].copy()
            symbol_data['Date'] = pd.to_datetime(symbol_data['Date']).dt.date
            merged_data = pd.merge(symbol_data, vix_data[['Date', 'Close']], 
                                 on='Date', how='inner', suffixes=('', '_VIX'))
            
            print(f"\n分析 {symbol} 在 VIX <= 15 時的數據...")
            print(f"合併後的數據筆數: {len(merged_data)}")
            
            # 篩選低VIX時期的數據
            low_vix_data = merged_data[merged_data['Close_VIX'] <= 15]
            total_low_vix += len(low_vix_data)
            print(f"低VIX時期的數據筆數: {len(low_vix_data)}")
            
            # 計算每個指標在低VIX時期的出現次數
            for _, row in low_vix_data.iterrows():
                closest_indicator = row['closest_indicator_Close']
                print(f"最接近的指標: {closest_indicator}")
                if closest_indicator in ['Call Wall', 'Call Wall CE', 'Call Dominate', 
                                      'Put Wall', 'Put Wall CE', 'Put Dominate',
                                      'Gamma Flip', 'Gamma Flip CE', 'Gamma Field', 'Gamma Field CE']:
                    all_indicators_count[closest_indicator] = all_indicators_count.get(closest_indicator, 0) + 1
        
        print(f"\nVIX <= 15 時的總數據筆數: {total_low_vix}")
        
        if total_low_vix > 0:
            report.append(f"\nVIX <= 15 時的指標出現機率：")
            # 計算並記錄每個指標的出現機率
            for indicator in all_indicators_count:
                count = all_indicators_count[indicator]
                probability = count / total_low_vix * 100
                report.append(f"{indicator}: {probability:.1f}% ({count}/{total_low_vix})")
        
        # 分析每個高VIX閾值
        for threshold in vix_thresholds:
            report.append(f"\nVIX > {threshold} 時的指標出現機率：")
            
            # 收集所有指數的數據
            all_indicators_count = {}
            total_high_vix = 0
            
            for symbol in ['SPX', 'QQQ', 'IWM', 'SOXX']:
                if symbol not in self.data:
                    continue
                    
                symbol_data = self.data[symbol].copy()
                symbol_data['Date'] = pd.to_datetime(symbol_data['Date']).dt.date
                merged_data = pd.merge(symbol_data, vix_data[['Date', 'Close']], 
                                     on='Date', how='inner', suffixes=('', '_VIX'))
                
                print(f"\n分析 {symbol} 在 VIX > {threshold} 時的數據...")
                print(f"合併後的數據筆數: {len(merged_data)}")
                
                # 篩選高VIX時期的數據
                high_vix_data = merged_data[merged_data['Close_VIX'] > threshold]
                total_high_vix += len(high_vix_data)
                print(f"高VIX時期的數據筆數: {len(high_vix_data)}")
                
                # 計算每個指標在高VIX時期的出現次數
                for _, row in high_vix_data.iterrows():
                    closest_indicator = row['closest_indicator_Close']
                    print(f"最接近的指標: {closest_indicator}")
                    if closest_indicator in ['Call Wall', 'Call Wall CE', 'Call Dominate', 
                                          'Put Wall', 'Put Wall CE', 'Put Dominate',
                                          'Gamma Flip', 'Gamma Flip CE', 'Gamma Field', 'Gamma Field CE']:
                        all_indicators_count[closest_indicator] = all_indicators_count.get(closest_indicator, 0) + 1
            
            print(f"\nVIX > {threshold} 時的總數據筆數: {total_high_vix}")
            print(f"指標出現次數: {all_indicators_count}")
            
            # 計算並添加到報告
            if total_high_vix > 0:
                for indicator, count in sorted(all_indicators_count.items(), 
                                            key=lambda x: x[1], reverse=True):
                    probability = (count / total_high_vix) * 100
                    report.append(f"{indicator}: {probability:.1f}% ({count}/{total_high_vix})")
        
        # 將報告寫入檔案
        report_text = '\n'.join(report)
        with open('charts/vix_analysis.txt', 'w', encoding='utf-8') as f:
            f.write(report_text)

    def generate_monthly_chart(self, data, symbol, month):
        """生成月度圖表"""
        try:
            if data.empty:
                print(f"警告: {month} 的資料框為空，跳過生成圖表。")
                return
            
            # 檢查必要的欄位
            required_columns = ['Date', 'Open', 'High', 'Low', 'Close']
            if not all(col in data.columns for col in required_columns):
                print(f"警告: {month} 缺少必要的欄位 {required_columns}，跳過生成圖表。")
                return

            # 確保所有必要欄位都有數據
            if data[required_columns].isnull().any().any():
                print(f"警告: {month} 的必要欄位中存在空值，跳過生成圖表。")
                return
            
            # 創建圖表
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), height_ratios=[2, 1])
            fig.suptitle(f'{symbol} vs VIX Analysis - {month}', fontsize=16)
            
            # 設置圖表樣式
            plt.style.use('default')
            plt.rcParams['axes.grid'] = True
            plt.rcParams['grid.linestyle'] = '--'
            plt.rcParams['grid.alpha'] = 0.5
            
            # 上半部圖表標題
            ax1.set_title(f'{symbol} Price and Indicators')
            
            # 確保日期是正確的格式
            dates = mdates.date2num(data['Date'].tolist())
            
            # 準備K線圖數據
            ohlc = []
            for idx, row in data.iterrows():
                if all(pd.notna(row[col]) for col in required_columns):
                    ohlc.append([
                        mdates.date2num(row['Date']),
                        float(row['Open']),
                        float(row['High']),
                        float(row['Low']),
                        float(row['Close'])
                    ])
            
            if ohlc:  # 只有在有數據時才繪製K線圖
                # 繪製K線圖
                from mplfinance.original_flavor import candlestick_ohlc
                candlestick_ohlc(ax1, ohlc, width=0.6, colorup='g', colordown='r')
                
                # 定義指標和顏色
                indicators = {
                    'Call Wall': 'green',
                    'Call Wall CE': 'lime',
                    'Call Dominate': 'cyan',
                    'Put Wall': 'red',
                    'Put Wall CE': 'orange',
                    'Put Dominate': 'magenta',
                    'Gamma Flip': 'blue',
                    'Gamma Flip CE': 'purple',
                    'Gamma Field': 'yellow',
                    'Gamma Field CE': 'brown',
                    'Implied Movement -σ': 'gray',
                    'Implied Movement -2σ': 'darkgray',
                    'Implied Movement +σ': 'lightgray',
                    'Implied Movement +2σ': 'silver',
                    'Implied Movement -3σ': 'pink',
                    'Implied Movement +3σ': 'olive'
                }
                
                # 為每個價格點找出最接近的指標
                for idx, row in data.iterrows():
                    # 檢查每個價格點（最高價、最低價、收盤價）
                    price_points = {
                        'High': float(row['High']),
                        'Low': float(row['Low']),
                        'Close': float(row['Close'])
                    }
                    
                    for price_type, price in price_points.items():
                        min_distance = float('inf')
                        closest_indicator = None
                        closest_value = None
                        
                        # 檢查所有指標
                        for indicator in indicators.keys():
                            if indicator in row and pd.notna(row[indicator]):
                                distance = abs(price - float(row[indicator]))
                                if distance < min_distance:
                                    min_distance = distance
                                    closest_indicator = indicator
                                    closest_value = float(row[indicator])
                        
                        # 如果找到最接近的指標，就畫出來
                        if closest_indicator:
                            label = f"{closest_indicator}" if closest_indicator not in ax1.get_legend_handles_labels()[1] else "_nolegend_"
                            ax1.scatter(mdates.date2num(row['Date']), closest_value,
                                      color=indicators[closest_indicator],
                                      alpha=0.7, marker='o', label=label)
            
                ax1.set_xlabel('Date')
                ax1.set_ylabel('Price')
                ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            
                # 設置x軸格式
                ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                ax1.xaxis.set_major_locator(mdates.DayLocator(interval=5))
                plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)
                
                # 在下方顯示 VIX 數據
                if 'VIX' in self.data:
                    vix_data = self.data['VIX']
                    vix_monthly = vix_data[vix_data['Date'].dt.strftime('%Y-%m') == month]
                    if not vix_monthly.empty:
                        ax2.plot(vix_monthly['Date'], vix_monthly['Close'], color='purple', label='VIX')
                        ax2.set_title('VIX Close Price')
                        ax2.set_xlabel('Date')
                        ax2.set_ylabel('VIX')
                        ax2.legend()
                        ax2.grid(True)
                        # 設置x軸格式，與上圖保持一致
                        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                        ax2.xaxis.set_major_locator(mdates.DayLocator(interval=5))
                        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)
            
                # 調整布局以確保圖例不會被截斷
                plt.subplots_adjust(right=0.85, bottom=0.15)
            
                # 保存圖表
                os.makedirs('charts', exist_ok=True)
                chart_path = os.path.join('charts', f"{symbol.lower()}_{month}.png")
                plt.savefig(chart_path, dpi=300, bbox_inches='tight')
                plt.close(fig)
            
                print(f"已生成 {chart_path} 圖表")
            else:
                print(f"警告: {month} 沒有足夠的OHLC數據來生成K線圖")
            
        except Exception as e:
            print(f"生成月度圖表時發生錯誤: {str(e)}")
            import traceback
            traceback.print_exc()

    def analyze_market(self):
        """分析市場數據"""
        try:
            # 載入所有股票數據
            if not self.load_data():
                print("載入數據失敗")
                return

            # 確保所有數據框都有月份欄位
            for symbol in self.data:
                if 'Date' in self.data[symbol].columns:
                    # 確保日期是datetime格式
                    self.data[symbol]['Date'] = pd.to_datetime(self.data[symbol]['Date'])
                    self.data[symbol]['Month'] = self.data[symbol]['Date'].dt.strftime('%Y-%m')

            # 為每個股票分別處理數據
            for symbol in self.symbols:
                if symbol not in self.data:
                    continue

                df = self.data[symbol]
                if df.empty:
                    print(f"警告: {symbol} 的數據為空")
                    continue

                # 按月份分組並生成圖表
                months = sorted(df['Month'].unique())
                for month in months:
                    monthly_data = df[df['Month'] == month].copy()
                    if not monthly_data.empty:
                        print(f"\n處理 {symbol} {month} 的數據...")
                        print(f"數據筆數: {len(monthly_data)}")
                        self.generate_monthly_chart(monthly_data, symbol, month)

            # 分析與VIX的關係
            self.analyze_vix_relationships()
            
        except Exception as e:
            print(f"分析市場數據時發生錯誤：{str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def analyze_vix_spx_patterns(self):
        """分析VIX和SPX的關係模式"""
        if 'VIX' not in self.data or 'SPX' not in self.data:
            print("錯誤: 需要VIX和SPX的數據")
            return
        
        analyzer = VixSpxAnalyzer(self.data['VIX'], self.data['SPX'])
        print("\n=== VIX水平分析 ===")
        report = analyzer.generate_analysis_report()
        print(report)
        
        print("\n=== VIX連續上升分析 ===")
        streak_results = analyzer.analyze_vix_streaks()
        if len(streak_results) > 0:
            print(f"\n找到 {len(streak_results)} 個VIX連續上升3天或以上的模式")
            print("\n統計摘要:")
            print(f"平均持續天數: {streak_results['duration'].mean():.1f}天")
            print(f"平均VIX變化: {streak_results['vix_change'].mean():.2f}%")
            print(f"平均SPX變化: {streak_results['spx_change'].mean():.2f}%")
            print(f"SPX上漲比例: {(streak_results['spx_change'] > 0).mean()*100:.1f}%")
            
            # 顯示詳細模式
            print("\n詳細模式列表:")
            for _, pattern in streak_results.iterrows():
                print(f"\n時間區間: {pattern['start_date'].strftime('%Y-%m-%d')} 至 {pattern['end_date'].strftime('%Y-%m-%d')} ({pattern['duration']}天)")
                print(f"VIX變化: {pattern['initial_vix']:.2f} → {pattern['final_vix']:.2f} ({pattern['vix_change']:.2f}%)")
                print(f"SPX變化: {pattern['spx_change']:.2f}%")
        else:
            print("未發現VIX連續上升3天或以上的模式")
        
        # 保存報告到文件
        report_path = os.path.join('charts', 'vix_spx_pattern_analysis.txt')
        os.makedirs('charts', exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n分析報告已保存到: {report_path}")
        return report

def main():
    """主程序"""
    analyzer = MarketAnalyzer('2024 US Stock Gamma History.xlsx')
    if analyzer.load_data():
        print("\n開始分析VIX和SPX的關係...")
        
        # 分析VIX和SPX的關係
        if 'VIX' in analyzer.data and 'SPX' in analyzer.data:
            vix_analyzer = VixSpxAnalyzer(analyzer.data['VIX'], analyzer.data['SPX'])
            
            # 執行VIX水平分析
            print("\n=== VIX水平分析 ===")
            level_report = vix_analyzer.generate_analysis_report()
            print(level_report)
            
            # 執行VIX Put Wall分析
            vix_analyzer.analyze_vix_put_wall()
            
            # 執行VIX連續上升分析
            print("\n=== VIX連續上升分析 ===")
            streak_results = vix_analyzer.analyze_vix_streaks()
            if len(streak_results) > 0:
                print(f"\n找到 {len(streak_results)} 個VIX連續上升3天或以上的模式")
                print("\n統計摘要:")
                print(f"平均持續天數: {streak_results['duration'].mean():.1f}天")
                print(f"平均VIX變化: {streak_results['vix_change'].mean():.2f}%")
                print(f"平均SPX變化: {streak_results['spx_change'].mean():.2f}%")
                print(f"SPX上漲比例: {(streak_results['spx_change'] > 0).mean()*100:.1f}%")
                
                print("\n詳細模式列表:")
                for _, pattern in streak_results.iterrows():
                    print(f"\n時間區間: {pattern['start_date'].strftime('%Y-%m-%d')} 至 {pattern['end_date'].strftime('%Y-%m-%d')} ({pattern['duration']}天)")
                    print(f"VIX變化: {pattern['initial_vix']:.2f} → {pattern['final_vix']:.2f} ({pattern['vix_change']:.2f}%)")
                    print(f"SPX變化: {pattern['spx_change']:.2f}%")
            else:
                print("未發現VIX連續上升3天或以上的模式")
            
            # 保存報告到文件
            report_path = os.path.join('charts', 'vix_spx_pattern_analysis.txt')
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write(level_report)
        else:
            print("未找到VIX或SPX的數據，無法進行分析")

if __name__ == '__main__':
    main()
