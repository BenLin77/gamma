# 導入所需的庫
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import numpy as np
import yfinance as yf
from datetime import timedelta
from functools import lru_cache

@st.cache_data(ttl=3600)  # 快取一小時
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

@st.cache_data(ttl=3600)  # 快取一小時
def get_vix_data(start_date, end_date):
    """獲取VIX數據"""
    try:
        adjusted_start = (pd.to_datetime(start_date) - timedelta(days=5)).strftime('%Y-%m-%d')
        adjusted_end = (pd.to_datetime(end_date) + timedelta(days=1)).strftime('%Y-%m-%d')
        vix = yf.download('^VIX', start=adjusted_start, end=adjusted_end, progress=False)
        vix_close = vix['Close']
        vix_close.index = vix_close.index.date
        return vix_close
    except Exception as e:
        st.warning(f"無法獲取VIX數據: {str(e)}")
        return None

def calculate_indicator_stats(df, selected_markers):
    """計算每個指標的統計數據"""
    stats = {}
    # 預先計算收盤價，避免重複計算
    close_prices = df['Close'].values
    close_prices_shift = np.roll(close_prices, 1)
    dates = df['Date'].values
    
    for marker in selected_markers:
        if marker in df.columns:
            # 獲取指標數據，避免重複訪問
            marker_values = df[marker].values
            valid_mask = ~np.isnan(marker_values)
            
            # 判斷指標類型
            is_upward_break = any(keyword in marker.lower() for keyword in ['call', '+σ', 'dominate'])
            is_downward_break = any(keyword in marker.lower() for keyword in ['put', '-σ', 'flip'])
            
            # 使用 NumPy 進行向量化運算
            if is_upward_break:
                crosses = (close_prices >= marker_values) & (close_prices_shift < marker_values)
                below_count = np.sum(close_prices >= marker_values)
                prob_text = "突破機率"
            elif is_downward_break:
                crosses = (close_prices <= marker_values) & (close_prices_shift > marker_values)
                below_count = np.sum(close_prices <= marker_values)
                prob_text = "跌破機率"
            else:
                crosses = ((close_prices <= marker_values) & (close_prices_shift > marker_values)) | \
                         ((close_prices >= marker_values) & (close_prices_shift < marker_values))
                below_count = np.sum(close_prices < marker_values)
                prob_text = "穿越機率"
            
            # 計算穿越點
            cross_dates = dates[crosses]
            
            # 計算持續時間
            if len(cross_dates) > 0:
                # 使用 NumPy 進行向量化運算計算時間差
                cross_dates_diff = np.diff(cross_dates).astype('timedelta64[D]').astype(int)
                if len(cross_dates) > 1:
                    last_duration = (dates[-1] - cross_dates[-1]).astype('timedelta64[D]').astype(int)
                    durations = np.append(cross_dates_diff, last_duration)
                else:
                    durations = np.array([(dates[-1] - cross_dates[0]).astype('timedelta64[D]').astype(int)])
                
                avg_duration = np.mean(durations)
            else:
                avg_duration = 0
            
            # 計算統計數據
            total_valid = np.sum(valid_mask)
            
            stats[marker] = {
                '穿越次數': np.sum(crosses),
                f'{prob_text}': f"{(below_count / total_valid * 100):.2f}%" if total_valid > 0 else "N/A",
                '平均持續時間(天)': f"{avg_duration:.1f}" if avg_duration > 0 else "N/A",
                '最近距離': f"{(close_prices[-1] - marker_values[-1]):.2f}" if not np.isnan(marker_values[-1]) else "N/A"
            }
    return stats

@st.cache_data(ttl=3600)  # 快取圖表一小時
def create_candlestick_chart(df, selected_markers=None, title="Stock Chart", show_vix=False):
    """創建K線圖和指標線"""
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 預先計算所需的數據
    dates = df['Date']
    close_prices = df['Close'].values
    close_prices_shift = np.roll(close_prices, 1)

    # 添加K線圖
    fig.add_trace(
        go.Candlestick(
            x=dates,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=close_prices,
            name='OHLC'
        ),
        secondary_y=False
    )

    colors = ['pink', 'lightgreen', 'yellow', 'cyan', 'orange', 
             'purple', 'white', 'red', 'blue', 'gray', 'brown', 'lime']
    
    if selected_markers:
        for i, marker in enumerate(selected_markers):
            if marker in df.columns and marker != 'VIX':
                marker_values = df[marker].values
                
                # 判斷指標類型
                is_upward_break = any(keyword in marker.lower() for keyword in ['call', '+σ', 'dominate'])
                is_downward_break = any(keyword in marker.lower() for keyword in ['put', '-σ', 'flip'])
                
                # 使用 NumPy 進行向量化運算
                if is_upward_break:
                    break_points = (close_prices >= marker_values) & (close_prices_shift < marker_values)
                    marker_symbol = 'triangle-down'
                    marker_color = 'green'
                    hover_text = '向上突破'
                elif is_downward_break:
                    break_points = (close_prices <= marker_values) & (close_prices_shift > marker_values)
                    marker_symbol = 'triangle-up'
                    marker_color = 'red'
                    hover_text = '向下跌破'
                else:
                    continue

                # 添加指標線
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=marker_values,
                        mode='markers',
                        name=marker,
                        marker=dict(
                            color=colors[i % len(colors)],
                            size=12,
                            symbol='circle',
                            line=dict(color='white', width=1)
                        )
                    ),
                    secondary_y=False
                )
                
                # 添加突破/跌破點
                break_dates = dates[break_points]
                break_prices = close_prices[break_points]
                
                if len(break_dates) > 0:
                    hover_texts = [
                        f"{marker}<br>{hover_text}: {price:.2f}<br>日期: {date.strftime('%Y-%m-%d')}"
                        for date, price in zip(break_dates, break_prices)
                    ]
                    
                    fig.add_trace(
                        go.Scatter(
                            x=break_dates,
                            y=break_prices,
                            mode='markers',
                            name=f'{marker} {hover_text}點',
                            marker=dict(
                                symbol=marker_symbol,
                                color=marker_color,
                                size=15,
                                line=dict(color='white', width=2)
                            ),
                            text=hover_texts,
                            hoverinfo='text'
                        ),
                        secondary_y=False
                    )

    if show_vix and 'VIX' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=df['VIX'],
                mode='lines',
                name='VIX',
                line=dict(color='orange', width=2),
            ),
            secondary_y=True
        )

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

    fig.update_yaxes(title_text="股價", secondary_y=False)
    fig.update_yaxes(title_text="VIX", secondary_y=True)

    return fig

def main():
    st.set_page_config(layout="wide")
    st.title("股票 Gamma 分析圖表")

    uploaded_file = st.file_uploader("上傳Excel文件", type=['xlsx'])
    
    if uploaded_file:
        stock_data = load_stock_data(uploaded_file)
        
        if stock_data:
            selected_stock = st.sidebar.selectbox(
                "選擇股票",
                options=list(stock_data.keys())
            )

            marker_options = [
                'Gamma Field', 'Call Dominate', 'Put Dominate', 'Gamma Flip',
                'Call Wall', 'Put Wall', 'Call Wall CE', 'Put Wall CE',
                'Gamma Field CE', 'Gamma Flip CE',
                'Implied Movement +σ', 'Implied Movement -σ',
                'Implied Movement +2σ', 'Implied Movement -2σ'
            ]

            selected_markers = st.sidebar.multiselect(
                "選擇要顯示的指標",
                options=marker_options
            )

            show_vix = st.sidebar.checkbox("顯示VIX", value=True)

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

                if show_vix:
                    with st.spinner('正在獲取 VIX 數據...'):
                        vix_data = get_vix_data(start_date, end_date)
                        if vix_data is not None:
                            vix_data = vix_data.reindex(df_filtered['Date'].dt.date)
                            df_filtered['VIX'] = vix_data.values

                if selected_markers:
                    stats = calculate_indicator_stats(df_filtered, selected_markers)
                    
                    st.sidebar.markdown("---")
                    st.sidebar.markdown("### 指標統計")
                    for marker, stat in stats.items():
                        st.sidebar.markdown(f"#### {marker}")
                        for key, value in stat.items():
                            st.sidebar.write(f"{key}: {value}")
                        st.sidebar.markdown("---")

                fig = create_candlestick_chart(
                    df_filtered, 
                    selected_markers,
                    f"{selected_stock} Gamma Analysis",
                    show_vix
                )
                st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()