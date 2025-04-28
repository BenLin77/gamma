import re
import os
import shutil
import time
import json
import argparse
from datetime import datetime
from playwright.sync_api import Playwright, sync_playwright, expect

def load_config(config_file):
    """載入配置文件"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"載入配置文件失敗: {str(e)}")
        return None

def wait_for_chart(page, max_retries=3):
    """等待圖表加載的輔助函數，包含重試機制"""
    for attempt in range(max_retries):
        try:
            # 等待頁面加載完成
            page.wait_for_load_state("networkidle", timeout=30000)
            # 等待圖表容器出現
            page.wait_for_selector(".js-plotly-plot", state="visible", timeout=30000)
            # 等待工具欄出現
            page.wait_for_selector(".modebar-btn", state="visible", timeout=30000)
            # 確保圖表完全渲染
            page.wait_for_function("""
                () => {
                    const plot = document.querySelector('.js-plotly-plot');
                    return plot && plot.querySelector('.plot-container');
                }
            """, timeout=30000)
            return True
        except Exception as e:
            print(f"等待圖表加載嘗試 {attempt + 1}/{max_retries} 失敗: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 等待5秒後重試
                page.reload()  # 重新加載頁面
            else:
                raise  # 最後一次嘗試失敗時拋出異常

def process_ticker(page, ticker, download_dir):
    """處理單個股票的數據採集"""
    try:
        page.get_by_placeholder("Ticker").click()
        page.get_by_placeholder("Ticker").fill(ticker)
        page.get_by_text("Select model...").click()
        page.get_by_role("option", name="Gamma").click()
        page.get_by_role("button", name="Enter").click()
        time.sleep(15)

        # 使用等待函數
        wait_for_chart(page)
        
        # 只點擊下載按鈕
        page.get_by_role("button", name="下載").click()
        time.sleep(3)  # 等待一下讓點擊操作完成
        
        # 創建HTML保存目錄
        html_dir = os.path.join(download_dir, ticker, "html")
        os.makedirs(html_dir, exist_ok=True)
        today_date = datetime.today().strftime('%Y%m%d')
        html_filename = f"Gamma_{ticker}_{today_date}.html"
        html_filepath = os.path.join(html_dir, html_filename)
        
        # 複製HTML文件到pCloud對應資料夾
        shutil.move(download_html.path(), html_filepath)
        
        # 另外保存當前頁面的HTML源碼
        page_html = page.content()
        with open(os.path.join(html_dir, f"page_source_{ticker}_{today_date}.html"), "w", encoding="utf-8") as html_file:
            html_file.write(page_html)

        # 下載 Gamma 圖片
        page.mouse.move(200, 200)
        with page.expect_download() as download_info:
            page.locator(".modebar-btn").first.click()
        download = download_info.value

        # 處理 Gamma 圖片
        ticker_dir = os.path.join(download_dir, ticker)
        gamma_dir = os.path.join(ticker_dir, "gamma")
        os.makedirs(gamma_dir, exist_ok=True)
        today_date = datetime.today().strftime('%Y%m%d')
        new_filename = f"Gamma_{ticker}_{today_date}.png"
        new_filepath = os.path.join(gamma_dir, new_filename)
        shutil.move(download.path(), new_filepath)

        # Smile 圖片處理
        page.get_by_text("Gamma", exact=True).click()
        page.get_by_role("option", name="Smile").click()
        page.get_by_role("button", name="Enter").click()
        time.sleep(20)
        
        wait_for_chart(page)

        with page.expect_download() as download2_info:
            page.locator(".modebar-btn").first.click()
        download2 = download2_info.value

        smile_dir = os.path.join(ticker_dir, "smile")
        os.makedirs(smile_dir, exist_ok=True)
        new_filename = f"Smile_{ticker}_{today_date}.png"
        new_filepath = os.path.join(smile_dir, new_filename)
        shutil.move(download2.path(), new_filepath)

        # TV Code 處理
        page.get_by_text("Smile", exact=True).click()
        page.get_by_role("option", name="TV Code").click()
        page.get_by_role("button", name="Enter").click()
        time.sleep(45)

        page.mouse.move(300, 300)
        text_content = page.inner_text(".pt-5 p")

        tvcode_dir = os.path.join(download_dir, "tvcode")
        os.makedirs(tvcode_dir, exist_ok=True)
        text_filename = f"tvcode_{today_date}.txt"
        text_filepath = os.path.join(tvcode_dir, text_filename)

        with open(text_filepath, "a") as text_file:
            text_file.write(text_content + "\n\n")

        page.keyboard.press('F5', delay=3000)
        page.reload()
        time.sleep(5)
        return True

    except Exception as e:
        print(f"處理 {ticker} 時發生錯誤: {str(e)}")
        return False

def run(playwright: Playwright, auth_file: str, tickers: list, download_dir: str) -> None:
    """主要運行函數"""
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context(
        storage_state=auth_file, 
        viewport={"width":1920,"height":1080}
    )
    page = context.new_page()
    page.goto("https://www.lietaresearch.com/platform")
    time.sleep(15)

    for ticker in tickers:
        if not process_ticker(page, ticker, download_dir):
            print(f"跳過 {ticker} 的後續處理")
            continue

    context.close()
    browser.close()

def main():
    """主程序"""
    parser = argparse.ArgumentParser(description='股票數據採集工具')
    parser.add_argument('--auth', type=str, default='auth.json',
                      help='認證文件路徑 (default: auth.json)')
    parser.add_argument('--config', type=str, default='config.json',
                      help='配置文件路徑 (default: config.json)')
    parser.add_argument('--download-dir', type=str,
                      default='/home/ben/pCloudDrive/stock/GEX/GEX_file/',
                      help='下載目錄路徑')
    
    args = parser.parse_args()
    
    # 載入配置
    config = load_config(args.config)
    if not config:
        print("無法載入配置文件，使用預設配置")
        config = {
            "tickers": ["spx", "qqq", "iwm", "smh", "vix", "smci", "nvda", 
                       "tsla", "uvix", "svix", "tlt"]
        }

    with sync_playwright() as playwright:
        run(playwright, args.auth, config['tickers'], args.download_dir)

if __name__ == "__main__":
    main()

