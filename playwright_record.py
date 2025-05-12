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

def wait_for_chart(page, max_retries=5):
    """等待圖表加載的輔助函數，包含重試機制"""
    for attempt in range(max_retries):
        try:
            # 等待頁面加載完成，增加超時時間
            page.wait_for_load_state("networkidle", timeout=60000)
            # 等待圖表容器出現
            page.wait_for_selector(".js-plotly-plot", state="visible", timeout=60000)
            # 等待工具欄出現
            page.wait_for_selector(".modebar-btn", state="visible", timeout=60000)
            # 確保圖表完全渲染
            page.wait_for_function("""
                () => {
                    const plot = document.querySelector('.js-plotly-plot');
                    return plot && plot.querySelector('.plot-container');
                }
            """, timeout=60000)
            return True
        except Exception as e:
            print(f"等待圖表加載嘗試 {attempt + 1}/{max_retries} 失敗: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(10)  # 增加等待時間至10秒後重試
                page.reload()  # 重新加載頁面
                time.sleep(5)  # 重載後等待5秒
            else:
                print(f"嘗試 {max_retries} 次後仍然失敗，但將繼續執行")
                return False  # 返回失敗而不是拋出異常，允許腳本繼續執行

def safe_click_and_wait(page, selector_func, timeout=60000, max_retries=3, description="元素"):
    """安全地點擊元素並等待，包含重試機制"""
    for attempt in range(max_retries):
        try:
            element = selector_func()
            # 確保元素可見並可點擊
            if hasattr(element, 'wait_for'):
                element.wait_for(state="visible", timeout=timeout)
            # 嘗試點擊
            element.click(timeout=timeout)
            return True
        except Exception as e:
            print(f"點擊{description}嘗試 {attempt + 1}/{max_retries} 失敗: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(5)
                # 嘗試滾動頁面以確保元素在視圖中
                try:
                    page.mouse.wheel(0, 100)
                    time.sleep(2)
                except:
                    pass
            else:
                print(f"點擊{description}失敗，但將繼續執行")
                return False

def safe_inner_text(page, selector, timeout=60000, default_text=""):
    """安全地獲取元素文本內容"""
    try:
        # 等待元素出現
        page.wait_for_selector(selector, state="visible", timeout=timeout)
        # 獲取文本
        return page.inner_text(selector)
    except Exception as e:
        print(f"獲取文本內容失敗: {str(e)}")
        return default_text

def process_ticker(page, ticker, download_dir):
    """處理單個股票的數據採集"""
    try:
        print(f"開始處理 {ticker}...")
        
        # 重置頁面狀態
        try:
            page.reload()
            page.wait_for_load_state("networkidle", timeout=60000)
            time.sleep(10)  # 給頁面充分時間加載
        except Exception as e:
            print(f"重置頁面狀態失敗: {str(e)}")
        
        # 輸入股票代碼
        try:
            ticker_input = page.get_by_placeholder("Ticker")
            ticker_input.click(timeout=60000)
            ticker_input.fill(ticker, timeout=60000)
            print(f"已輸入股票代碼: {ticker}")
            time.sleep(3)
        except Exception as e:
            print(f"輸入股票代碼失敗: {str(e)}")
            return False
        
        # 選擇模型 - 使用更穩健的方法
        try:
            # 先嘗試直接點擊
            model_selector = page.get_by_text("Select model...")
            model_selector.click(timeout=60000)
            time.sleep(3)
            
            # 選擇Gamma選項
            gamma_option = page.get_by_role("option", name="Gamma")
            gamma_option.click(timeout=60000)
            time.sleep(2)
            
            # 點擊Enter按鈕
            enter_button = page.get_by_role("button", name="Enter")
            enter_button.click(timeout=60000)
            print("已選擇Gamma模型並點擊Enter")
            time.sleep(20)  # 增加等待時間
        except Exception as e:
            print(f"選擇模型失敗: {str(e)}")
            # 嘗試替代方法
            try:
                # 使用JavaScript點擊
                page.evaluate("""
                    () => {
                        const selectElements = Array.from(document.querySelectorAll('button, select, div')).
                            filter(el => el.textContent.includes('Select model'));
                        if (selectElements.length > 0) selectElements[0].click();
                        
                        setTimeout(() => {
                            const gammaOptions = Array.from(document.querySelectorAll('div[role="option"]')).
                                filter(el => el.textContent.includes('Gamma'));
                            if (gammaOptions.length > 0) gammaOptions[0].click();
                            
                            setTimeout(() => {
                                const enterButtons = Array.from(document.querySelectorAll('button')).
                                    filter(el => el.textContent.includes('Enter'));
                                if (enterButtons.length > 0) enterButtons[0].click();
                            }, 2000);
                        }, 2000);
                    }
                """)
                print("使用替代方法選擇模型")
                time.sleep(25)
            except Exception as e2:
                print(f"替代選擇模型方法也失敗: {str(e2)}")
                return False

        # 使用等待函數，但不因失敗而中斷
        chart_loaded = wait_for_chart(page)
        if not chart_loaded:
            print(f"等待圖表加載失敗，但將嘗試繼續處理 {ticker}")
        
        # 下載HTML
        try:
            with page.expect_download(timeout=60000) as download_info:
                download_button = page.get_by_role("button", name="下載")
                download_button.click(timeout=60000)
            download = download_info.value
            time.sleep(5)  # 增加等待時間
            
            # 創建HTML保存目錄
            html_dir = os.path.join(download_dir, ticker, "html")
            os.makedirs(html_dir, exist_ok=True)
            today_date = datetime.today().strftime('%Y%m%d')
            html_filename = f"Gamma_{ticker}_{today_date}.html"
            html_filepath = os.path.join(html_dir, html_filename)
            
            # 將下載的HTML文件移動到指定目錄
            try:
                shutil.move(download.path(), html_filepath)
                print(f"成功保存HTML文件到 {html_filepath}")
            except Exception as e:
                print(f"移動HTML文件失敗: {str(e)}")
        except Exception as e:
            print(f"下載HTML失敗: {str(e)}")

        # 下載 Gamma 圖片
        try:
            # 移動鼠標到圖表區域
            page.mouse.move(200, 200)
            time.sleep(2)
            
            with page.expect_download(timeout=60000) as download_info:
                modebar_button = page.locator(".modebar-btn").first
                modebar_button.wait_for(state="visible", timeout=60000)
                modebar_button.click(timeout=60000)
            download = download_info.value
            time.sleep(5)

            # 處理 Gamma 圖片
            ticker_dir = os.path.join(download_dir, ticker)
            gamma_dir = os.path.join(ticker_dir, "gamma")
            os.makedirs(gamma_dir, exist_ok=True)
            today_date = datetime.today().strftime('%Y%m%d')
            new_filename = f"Gamma_{ticker}_{today_date}.png"
            new_filepath = os.path.join(gamma_dir, new_filename)
            shutil.move(download.path(), new_filepath)
            print(f"成功保存Gamma圖片到 {new_filepath}")
            time.sleep(15)
        except Exception as e:
            print(f"下載Gamma圖片失敗: {str(e)}")

        # TV Code 處理
        try:
            # 選擇TV Code模型
            safe_click_and_wait(page, lambda: page.get_by_text("Gamma", exact=True), description="Gamma選項")
            time.sleep(2)
            safe_click_and_wait(page, lambda: page.get_by_role("option", name="TV Code"), description="TV Code選項")
            time.sleep(2)
            safe_click_and_wait(page, lambda: page.get_by_role("button", name="Enter"), description="Enter按鈕")
            time.sleep(45)  # 給足夠時間加載

            # 獲取文本內容
            page.mouse.move(300, 300)
            # 使用更穩健的方式獲取文本
            try:
                # 先等待元素出現
                page.wait_for_selector(".pt-5 p", state="visible", timeout=60000)
                text_content = page.inner_text(".pt-5 p")
            except Exception as e:
                print(f"獲取TV Code文本失敗: {str(e)}")
                # 嘗試替代方法
                try:
                    text_content = page.evaluate("""
                        () => {
                            const elements = document.querySelectorAll('.pt-5 p, p, pre, code');
                            for (const el of elements) {
                                if (el.textContent && el.textContent.trim().length > 0) {
                                    return el.textContent;
                                }
                            }
                            return '';
                        }
                    """)
                except:
                    text_content = "無法獲取TV Code"

            if text_content and text_content.strip():
                # 過濾掉「掌握數據」相關的行
                filtered_lines = []
                for line in text_content.split('\n'):
                    if '掌握數據' not in line and '掌握資料' not in line and '掌握資訊' not in line:
                        filtered_lines.append(line)
                
                # 重新組合過濾後的文本
                filtered_text = '\n'.join(filtered_lines)
                
                # 只有在過濾後的文本不為空時才保存
                if filtered_text.strip():
                    tvcode_dir = os.path.join(download_dir, "tvcode")
                    os.makedirs(tvcode_dir, exist_ok=True)
                    today_date = datetime.today().strftime('%Y%m%d')
                    text_filename = f"tvcode_{today_date}.txt"
                    text_filepath = os.path.join(tvcode_dir, text_filename)

                    with open(text_filepath, "a") as text_file:
                        text_file.write(filtered_text + "\n\n")
                print(f"成功保存TV Code到 {text_filepath}")
        except Exception as e:
            print(f"處理TV Code失敗: {str(e)}")

        # Smile 圖片處理
        try:
            # 選擇Smile模型
            safe_click_and_wait(page, lambda: page.get_by_text("TV Code"), description="TV Code選項")
            time.sleep(2)
            safe_click_and_wait(page, lambda: page.get_by_role("option", name="Smile"), description="Smile選項")
            time.sleep(2)
            safe_click_and_wait(page, lambda: page.get_by_role("button", name="Enter"), description="Enter按鈕")
            time.sleep(30)  # 增加等待時間
            
            # 等待圖表加載
            chart_loaded = wait_for_chart(page)
            if not chart_loaded:
                print(f"等待Smile圖表加載失敗，但將嘗試繼續處理")
            
            # 下載圖片
            with page.expect_download(timeout=60000) as download2_info:
                modebar_button = page.locator(".modebar-btn").first
                modebar_button.wait_for(state="visible", timeout=60000)
                modebar_button.click(timeout=60000)
            download2 = download2_info.value
            time.sleep(5)

            smile_dir = os.path.join(ticker_dir, "smile")
            os.makedirs(smile_dir, exist_ok=True)
            new_filename = f"Smile_{ticker}_{today_date}.png"
            new_filepath = os.path.join(smile_dir, new_filename)
            shutil.move(download2.path(), new_filepath)
            print(f"成功保存Smile圖片到 {new_filepath}")
        except Exception as e:
            print(f"處理Smile圖片失敗: {str(e)}")

        # 重新加載頁面，準備處理下一個股票
        try:
            page.reload()
            time.sleep(10)  # 給頁面充分時間加載
        except Exception as e:
            print(f"重新加載頁面失敗: {str(e)}")
        
        print(f"{ticker} 處理完成")
        return True

    except Exception as e:
        print(f"處理 {ticker} 時發生錯誤: {str(e)}")
        # 嘗試重置頁面狀態
        try:
            page.reload()
            time.sleep(10)
        except:
            pass
        return False

def run(playwright: Playwright, auth_file: str, tickers: list, download_dir: str) -> None:
    """主要運行函數"""
    # 設置更長的超時時間和更穩健的瀏覽器選項
    browser = playwright.chromium.launch(
        headless=False,
        args=[
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-dev-shm-usage',
            '--no-sandbox'
        ]
    )
    context = browser.new_context(
        storage_state=auth_file, 
        viewport={"width":1920,"height":1080},
        accept_downloads=True
    )
    
    # 配置頁面
    page = context.new_page()
    
    # 設置更長的默認超時時間
    page.set_default_timeout(60000)
    
    # 監聽頁面錯誤
    page.on("pageerror", lambda err: print(f"頁面錯誤: {err}"))
    page.on("crash", lambda: print("頁面崩潰"))
    
    # 導航到目標網站
    try:
        page.goto("https://www.lietaresearch.com/platform", timeout=60000)
        page.wait_for_load_state("networkidle", timeout=60000)
        time.sleep(20)  # 給頁面充分時間加載
        print("成功加載網站")
    except Exception as e:
        print(f"加載網站失敗: {str(e)}")
    
    # 處理每個股票
    for ticker in tickers:
        print(f"\n===== 開始處理 {ticker} =====")
        success = process_ticker(page, ticker, download_dir)
        if not success:
            print(f"處理 {ticker} 失敗，將繼續處理下一個股票")
        time.sleep(10)  # 在處理下一個股票前等待
    
    print("\n所有股票處理完成")
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

