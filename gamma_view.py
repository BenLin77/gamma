# 導入所需的庫
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

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

                # 創建並顯示圖表
                fig = create_candlestick_chart(
                    df_filtered, 
                    selected_markers,
                    f"{selected_stock} Gamma Analysis"
                )
                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()