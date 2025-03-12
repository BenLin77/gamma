# 導入所需的庫
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import numpy as np

def calculate_indicator_stats(df, selected_markers):
    """計算每個指標的統計數據"""
    stats = {}
    for marker in selected_markers:
        if marker in df.columns:
            # 計算收盤價穿過指標的次數
            crosses = ((df['Close'] <= df[marker]) & 
                      (df['Close'].shift(1) > df[marker])) | \
                     ((df['Close'] >= df[marker]) & 
                      (df['Close'].shift(1) < df[marker]))
            
            # 計算收盤價在指標下方的次數
            below_count = (df['Close'] < df[marker]).sum()
            total_valid = df[marker].notna().sum()  # 排除 NaN 值
            
            # 收集統計數據
            stats[marker] = {
                '穿越次數': crosses.sum(),
                '向下穿越機率': f"{(below_count / total_valid * 100):.2f}%" if total_valid > 0 else "N/A",
                '平均持續時間(天)': f"{(total_valid / crosses.sum()):.1f}" if crosses.sum() > 0 else "N/A",
                '最近距離': f"{(df['Close'].iloc[-1] - df[marker].iloc[-1]):.2f}" if not pd.isna(df[marker].iloc[-1]) else "N/A"
            }
    return stats

def load_stock_data(file_path):
    """讀取Excel檔案中的所有分頁數據"""
    xls = pd.ExcelFile(file_path)
    stock_data = {}
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        if 'Date' in df.columns:  # 確保有日期欄位
            df['Date'] = pd.to_datetime(df['Date'])
            stock_data[sheet_name] = df
    return stock_data

def create_candlestick_chart(df, selected_markers=None, title="Stock Chart"):
    """創建K線圖和指標線"""
    fig = go.Figure()

    # 添加K線圖
    fig.add_trace(go.Candlestick(
        x=df['Date'],
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='OHLC'
    ))

    # 添加選擇的指標線
    colors = ['pink', 'lightgreen', 'yellow', 'cyan', 'orange', 
             'purple', 'white', 'red', 'blue', 'gray', 'brown', 'lime']
    if selected_markers:
        for i, marker in enumerate(selected_markers):
            if marker in df.columns:
                fig.add_trace(go.Scatter(
                    x=df['Date'],
                    y=df[marker],
                    mode='lines+markers',
                    name=marker,
                    line=dict(color=colors[i % len(colors)]),
                    marker=dict(size=6)
                ))

    # 更新圖表佈局
    fig.update_layout(
        title=title,
        yaxis_title='Price',
        xaxis_title='Date',
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        height=800,  # 增加圖表高度
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.05
        ),
        margin=dict(r=250)  # 為右側圖例留出空間
    )

    return fig

def main():
    st.set_page_config(layout="wide")
    st.title("股票 Gamma 分析圖表")

    # 上傳Excel文件
    uploaded_file = st.file_uploader("上傳Excel文件", type=['xlsx'])
    
    if uploaded_file:
        # 讀取所有股票數據
        stock_data = load_stock_data(uploaded_file)
        
        if stock_data:
            # 選擇股票
            selected_stock = st.sidebar.selectbox(
                "選擇股票",
                options=list(stock_data.keys())
            )

            # 定義可選擇的指標
            marker_options = [
                'Gamma Field', 'Call Dominate', 'Put Dominate', 'Gamma Flip',
                'Call Wall', 'Put Wall', 'Call Wall CE', 'Put Wall CE',
                'Gamma Field CE', 'Gamma Flip CE',
                'Implied Movement +σ', 'Implied Movement -σ',
                'Implied Movement +2σ', 'Implied Movement -2σ'
            ]

            # 多選指標
            selected_markers = st.sidebar.multiselect(
                "選擇要顯示的指標",
                options=marker_options
            )

            # 日期範圍選擇
            df = stock_data[selected_stock]
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            
            date_range = st.sidebar.date_input(
                "選擇日期範圍",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )

            if len(date_range) == 2:
                start_date, end_date = date_range
                mask = (df['Date'].dt.date >= start_date) & (df['Date'].dt.date <= end_date)
                df_filtered = df.loc[mask]

                # 計算統計數據
                if selected_markers:
                    stats = calculate_indicator_stats(df_filtered, selected_markers)
                    
                    # 顯示統計數據
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("### 指標統計")
                    for marker, stat in stats.items():
                        st.sidebar.markdown(f"#### {marker}")
                        for key, value in stat.items():
                            st.sidebar.write(f"{key}: {value}")
                        st.sidebar.markdown("---")

                # 創建並顯示圖表
                fig = create_candlestick_chart(
                    df_filtered, 
                    selected_markers,
                    f"{selected_stock} Gamma Analysis"
                )
                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()