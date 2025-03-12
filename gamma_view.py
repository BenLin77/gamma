# 導入所需的庫
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import numpy as np
import yfinance as yf
from datetime import timedelta

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

def get_vix_data(start_date, end_date):
    """獲取VIX數據"""
    try:
        # 向前多取5天數據，以確保有足夠的交易日數據
        adjusted_start = (pd.to_datetime(start_date) - timedelta(days=5)).strftime('%Y-%m-%d')
        adjusted_end = (pd.to_datetime(end_date) + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # 下載VIX數據
        vix = yf.download('^VIX', start=adjusted_start, end=adjusted_end, progress=False)
        
        # 只保留收盤價，並將索引轉換為日期
        vix_close = vix['Close']
        vix_close.index = vix_close.index.date
        
        return vix_close
    except Exception as e:
        st.warning(f"無法獲取VIX數據: {str(e)}")
        return None

def create_candlestick_chart(df, selected_markers=None, title="Stock Chart", show_vix=False):
    """創建K線圖和指標線"""
    # 創建帶有雙 Y 軸的子圖
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 添加K線圖
    fig.add_trace(
        go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name='OHLC'
        ),
        secondary_y=False
    )

    # 添加選擇的指標線
    colors = ['pink', 'lightgreen', 'yellow', 'cyan', 'orange', 
             'purple', 'white', 'red', 'blue', 'gray', 'brown', 'lime']
    if selected_markers:
        for i, marker in enumerate(selected_markers):
            if marker in df.columns and marker != 'VIX':  # 排除 VIX，因為它會用次要 Y 軸
                fig.add_trace(
                    go.Scatter(
                        x=df['Date'],
                        y=df[marker],
                        mode='markers',  # 只顯示點點，移除連線
                        name=marker,
                        marker=dict(
                            color=colors[i % len(colors)],
                            size=12,  # 增加點的大小
                            symbol='circle',  # 使用圓形符號
                            line=dict(
                                color='white',  # 點的邊框顏色
                                width=1  # 點的邊框寬度
                            )
                        )
                    ),
                    secondary_y=False
                )

    # 如果要顯示 VIX，添加到次要 Y 軸
    if show_vix and 'VIX' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=df['VIX'],
                mode='lines',
                name='VIX',
                line=dict(color='orange', width=2),
            ),
            secondary_y=True
        )

    # 更新圖表佈局
    fig.update_layout(
        title=title,
        xaxis_title='Date',
        xaxis_rangeslider_visible=False,
        template='plotly_dark',
        height=800,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=1.05
        ),
        margin=dict(r=250)
    )

    # 設置主要和次要 Y 軸的標題
    fig.update_yaxes(title_text="股價", secondary_y=False)
    fig.update_yaxes(title_text="VIX", secondary_y=True)

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

            # VIX 顯示選項
            show_vix = st.sidebar.checkbox("顯示VIX", value=True)

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

                # 獲取並添加 VIX 數據
                if show_vix:
                    with st.spinner('正在獲取 VIX 數據...'):
                        vix_data = get_vix_data(start_date, end_date)
                        if vix_data is not None:
                            # 將 VIX 數據對齊到交易日
                            vix_data = vix_data.reindex(df_filtered['Date'].dt.date)
                            df_filtered['VIX'] = vix_data.values

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
                    f"{selected_stock} Gamma Analysis",
                    show_vix
                )
                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()