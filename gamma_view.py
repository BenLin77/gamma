# 導入所需的庫
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import numpy as np
import yfinance as yf
from datetime import timedelta
from functools import lru_cache

@st.cache_data(ttl=3600)
def load_stock_data(file_path):
    """讀取Excel檔案中的所有分頁數據"""
    xls = pd.ExcelFile(file_path)
    stock_data = {}
    for sheet_name in xls.sheet_names:
        df = pd.read_excel(file_path, sheet_name=sheet_name)
        if 'Date' in df.columns:
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
            is_upward_break = any(keyword in marker.lower() for keyword in ['call', '+σ'])
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
            
            # 計算最近 N 天的趨勢
            last_n_days = 5
            if len(marker_values) >= last_n_days:
                recent_trend = "上升" if marker_values[-1] > marker_values[-last_n_days] else "下降"
                trend_change = abs(marker_values[-1] - marker_values[-last_n_days]) / marker_values[-last_n_days] * 100
            else:
                recent_trend = "無法計算"
                trend_change = 0
            
            # 計算成功率（實際突破/跌破後是否繼續朝預期方向發展）
            if len(cross_dates) > 0:
                success_count = 0
                for i, cross_date in enumerate(cross_dates):
                    cross_idx = np.where(dates == cross_date)[0][0]
                    if cross_idx + 3 < len(close_prices):  # 確保有足夠的後續數據
                        if is_upward_break:
                            # 向上突破後是否繼續上漲
                            success = close_prices[cross_idx + 3] > close_prices[cross_idx]
                        elif is_downward_break:
                            # 向下跌破後是否繼續下跌
                            success = close_prices[cross_idx + 3] < close_prices[cross_idx]
                        if success:
                            success_count += 1
                success_rate = (success_count / len(cross_dates)) * 100
            else:
                success_rate = 0
            
            # 計算最近一次穿越的表現
            if len(cross_dates) > 0:
                last_cross_idx = np.where(dates == cross_dates[-1])[0][0]
                if last_cross_idx + 1 < len(close_prices):
                    last_cross_change = ((close_prices[-1] - close_prices[last_cross_idx]) / 
                                       close_prices[last_cross_idx] * 100)
                else:
                    last_cross_change = 0
            else:
                last_cross_change = 0
            
            # 計算 Dominate 特殊統計（前一天打到後第二天的表現）
            dominate_next_day_stats = None
            if 'Dominate' in marker:
                dominate_next_day_stats = calculate_dominate_next_day_stats(df, marker)
            
            stats[marker] = {
                '指標趨勢': f"{recent_trend} ({trend_change:.2f}%)",
                '穿越次數': np.sum(crosses),
                f'{prob_text}': f"{(below_count / total_valid * 100):.2f}%" if total_valid > 0 else "N/A",
                '平均持續時間': f"{avg_duration:.1f}天" if avg_duration > 0 else "N/A",
                '成功率': f"{success_rate:.1f}%" if success_rate > 0 else "N/A",
                '最近穿越表現': f"{last_cross_change:+.2f}%" if last_cross_change != 0 else "N/A",
                '當前距離': f"{(close_prices[-1] - marker_values[-1]):+.2f}" if not np.isnan(marker_values[-1]) else "N/A"
            }
            
            # 添加 Dominate 特殊統計
            if dominate_next_day_stats:
                stats[marker].update(dominate_next_day_stats)
                
    return stats

def calculate_dominate_next_day_stats(df, marker):
    """計算 Dominate 特殊統計：前一天打到後第二天的表現"""
    result = {}
    
    # 獲取收盤價和指標值
    close_prices = df['Close'].values
    marker_values = df[marker].values
    dates = df['Date'].values
    
    # 檢查是否為 Call Dominate 或 Put Dominate
    is_call_dominate = 'Call Dominate' in marker
    is_put_dominate = 'Put Dominate' in marker
    
    if is_call_dominate or is_put_dominate:
        # 找出價格觸及 Dominate 的天數
        if is_call_dominate:
            # 價格打到 Call Dominate（價格 >= Call Dominate）
            hit_days = np.where(close_prices >= marker_values)[0]
            hit_text = "Call Dominate後第二天下跌率"
        else:  # is_put_dominate
            # 價格打到 Put Dominate（價格 <= Put Dominate）
            hit_days = np.where(close_prices <= marker_values)[0]
            hit_text = "Put Dominate後第二天上漲率"
        
        total_hits = 0
        expected_moves = 0
        
        for hit_idx in hit_days:
            # 確保有下一個交易日的數據
            if hit_idx + 1 < len(close_prices):
                total_hits += 1
                
                if is_call_dominate:
                    # 檢查第二天是否下跌（價格低於 Call Dominate）
                    if close_prices[hit_idx + 1] < marker_values[hit_idx]:
                        expected_moves += 1
                else:  # is_put_dominate
                    # 檢查第二天是否上漲（價格高於 Put Dominate）
                    if close_prices[hit_idx + 1] > marker_values[hit_idx]:
                        expected_moves += 1
        
        # 計算機率
        if total_hits > 0:
            probability = (expected_moves / total_hits) * 100
            result[hit_text] = f"{probability:.2f}% ({expected_moves}/{total_hits})"
        else:
            result[hit_text] = "N/A"
    
    return result

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
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        margin=dict(l=50, r=50, t=100, b=50)
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
            # 頂部設置區域
            col_stock, col_date, col_vix = st.columns([1, 2, 1])
            
            with col_stock:
                selected_stock = st.selectbox(
                    "選擇股票",
                    options=list(stock_data.keys())
                )
            
            df = stock_data[selected_stock]
            min_date = df['Date'].min()
            max_date = df['Date'].max()
            
            with col_date:
                date_range = st.date_input(
                    "選擇日期範圍",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )
            
            with col_vix:
                show_vix = st.checkbox("顯示VIX", value=True)
            
            # 指標選擇區域（使用水平佈局）
            marker_options = [
                'Gamma Field', 'Call Dominate', 'Put Dominate', 'Gamma Flip',
                'Call Wall', 'Put Wall', 'Call Wall CE', 'Put Wall CE',
                'Gamma Field CE', 'Gamma Flip CE',
                'Implied Movement +σ', 'Implied Movement -σ',
                'Implied Movement +2σ', 'Implied Movement -2σ'
            ]
            
            selected_markers = st.multiselect(
                "選擇要顯示的指標",
                options=marker_options
            )
            
            # 主要內容區域 - 響應式佈局
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

                # 使用選項卡來分離圖表和統計信息
                tab1, tab2 = st.tabs(["K線圖", "指標統計"])
                
                with tab1:
                    # 顯示圖表
                    fig = create_candlestick_chart(
                        df_filtered, 
                        selected_markers,
                        f"{selected_stock} Gamma Analysis",
                        show_vix
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with tab2:
                    if selected_markers:
                        stats = calculate_indicator_stats(df_filtered, selected_markers)
                        # 使用列佈局顯示統計信息
                        cols = st.columns(min(3, len(stats)))
                        for i, (marker, stat) in enumerate(stats.items()):
                            with cols[i % len(cols)]:
                                with st.expander(marker, expanded=True):
                                    for key, value in stat.items():
                                        st.write(f"**{key}:** {value}")

if __name__ == "__main__":
    main()