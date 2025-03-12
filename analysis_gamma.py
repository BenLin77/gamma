import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns

class FSAnalyzer:
    def __init__(self, symbol='SPX'):
        self.symbol = symbol
        self.indicators = [
            'Gamma Flip', 'Gamma Flip CE',
            'Call Wall', 'Call Wall CE',
            'Put Wall', 'Put Wall CE',
            'Gamma Field', 'Gamma Field CE',
            'Implied Movement -σ', 'Implied Movement +σ',
            'Implied Movement -2σ', 'Implied Movement +2σ'
        ]

    def load_excel_data(self, file_path):
        """載入Excel檔案"""
        try:
            # 讀取Excel檔案，找到對應的工作表
            excel_file = pd.ExcelFile(file_path)
            sheets = excel_file.sheet_names
            
            # 尋找包含股票代碼的工作表
            matching_sheets = [s for s in sheets if self.symbol.lower() in s.lower()]
            if not matching_sheets:
                print(f"錯誤：找不到 {self.symbol} 的工作表")
                return False
                
            # 讀取工作表
            self.df = pd.read_excel(file_path, sheet_name=matching_sheets[0])
            
            # 確保日期欄位格式正確
            if 'Date' in self.df.columns:
                self.df['Date'] = pd.to_datetime(self.df['Date'])
            
            print(f"\n=== {self.symbol} 分析 ===")
            print(f"成功載入數據，共 {len(self.df)} 筆記錄")
            print("\n欄位列表：")
            print(self.df.columns.tolist())
            
            return True
        except Exception as e:
            print(f"載入數據錯誤: {e}")
            return False

    def calculate_distances(self):
        """計算收盤價與各指標的距離"""
        if 'Close' not in self.df.columns:
            print("錯誤：找不到 'Close' 欄位")
            print("可用的欄位：", self.df.columns.tolist())
            return False
            
        calculated_count = 0
        for indicator in self.indicators:
            if indicator in self.df.columns:
                self.df[f'{indicator}_distance'] = abs(self.df['Close'] - self.df[indicator])
                calculated_count += 1
            else:
                print(f"警告：找不到指標 '{indicator}'")
        
        print(f"成功計算了 {calculated_count} 個指標的距離")
        return calculated_count > 0

    def find_closest_indicator(self):
        """找出每天最接近的指標"""
        distance_columns = [col for col in self.df.columns if col.endswith('_distance')]
        
        if not distance_columns:
            print("錯誤：沒有找到任何距離欄位")
            return False
            
        print(f"找到的距離欄位：{distance_columns}")
        
        def get_closest(row):
            distances = {col.replace('_distance', ''): row[col] for col in distance_columns}
            if not distances:
                print(f"警告：行 {row.name} 沒有有效的距離值")
                return pd.Series({'closest_indicator': None, 'distance': None})
            closest = min(distances.items(), key=lambda x: x[1])
            return pd.Series({'closest_indicator': closest[0], 'distance': closest[1]})

        closest_data = self.df.apply(get_closest, axis=1)
        self.df = pd.concat([self.df, closest_data], axis=1)
        return True

    def plot_analysis(self):
        """繪製分析圖表"""
        plt.figure(figsize=(15, 10))
        
        # 繪製收盤價走勢和指標
        plt.subplot(2, 1, 1)
        plt.plot(self.df['Date'], self.df['Close'], label=f'{self.symbol} Close', color='black')
        
        # 為每個指標選擇不同的顏色
        colors = plt.cm.tab20(np.linspace(0, 1, len(self.indicators)))
        for indicator, color in zip(self.indicators, colors):
            if indicator in self.df.columns:
                plt.plot(self.df['Date'], self.df[indicator], 
                        label=indicator, alpha=0.5, linestyle='--')
        
        plt.title(f'{self.symbol} 收盤價與各指標走勢')
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True)
        
        # 繪製指標準確度統計
        plt.subplot(2, 1, 2)
        analysis = self.analyze()
        plt.bar(analysis['accuracy'].keys(), analysis['accuracy'].values())
        plt.title('各指標準確度（差距<10點的比例）')
        plt.xticks(rotation=45)
        plt.grid(True)
        
        plt.tight_layout()
        plt.show()

    def analyze(self):
        """進行完整分析"""
        # 1. 計算各指標成為最接近值的次數
        indicator_counts = self.df['closest_indicator'].value_counts()
        indicator_percentages = (indicator_counts / len(self.df) * 100).round(2)

        # 2. 計算平均差距
        avg_distances = {}
        for indicator in self.indicators:
            if f'{indicator}_distance' in self.df.columns:
                avg_distances[indicator] = self.df[f'{indicator}_distance'].mean()

        # 3. 計算準確度（差距<10點的比例）
        accuracy = {}
        for indicator in self.indicators:
            if f'{indicator}_distance' in self.df.columns:
                accuracy[indicator] = (self.df[f'{indicator}_distance'] < 10).mean() * 100

        return {
            'counts': indicator_counts,
            'percentages': indicator_percentages,
            'avg_distances': avg_distances,
            'accuracy': accuracy
        }

    def print_summary(self):
        """打印分析摘要"""
        analysis = self.analyze()
        
        print(f"\n=== {self.symbol} 指標出現次數統計 ===")
        for indicator, count in analysis['counts'].items():
            percentage = analysis['percentages'][indicator]
            print(f"{indicator}: {count}次 ({percentage:.1f}%)")

        print(f"\n=== {self.symbol} 平均差距分析 ===")
        for indicator, distance in analysis['avg_distances'].items():
            print(f"{indicator}: {distance:.2f}點")

        print(f"\n=== {self.symbol} 準確度分析（差距<10點） ===")
        for indicator, acc in analysis['accuracy'].items():
            print(f"{indicator}: {acc:.1f}%")

def analyze_symbol(symbol, file_path):
    """分析單個股票"""
    analyzer = FSAnalyzer(symbol)
    if analyzer.load_excel_data(file_path):
        analyzer.calculate_distances()
        analyzer.find_closest_indicator()
        analyzer.print_summary()
        analyzer.plot_analysis()
        return analyzer.df
    return None

def main():
    # 分析 SPX
    spx_df = analyze_symbol('SPX', '2024qqq_spx_iwm_vix.xlsx')
    
    # 分析 QQQ
    qqq_df = analyze_symbol('QQQ', '2024qqq_spx_iwm_vix.xlsx')
    
    # 分析 IWM
    iwm_df = analyze_symbol('IWM', '2024qqq_spx_iwm_vix.xlsx')

if __name__ == "__main__":
    main()