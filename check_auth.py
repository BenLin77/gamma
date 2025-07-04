#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
檢查 auth.json 是否可以登入 https://www.lietaresearch.com/platform
"""

import json
import asyncio
from playwright.async_api import async_playwright
import os
import sys
import time
import argparse
import requests
from dotenv import load_dotenv

# 載入環境變數

load_dotenv()

def send_pushover_notification(message, priority=0, sound=None, repeat=1):
    """發送 Pushover 通知
    
    Args:
        message: 通知訊息
        priority: 優先級 (-2, -1, 0, 1, 2)
        sound: 聲音類型
        repeat: 重複發送次數
    """
    try:
        # 從環境變數讀取 PUSHOVER_TOKEN 和 PUSHOVER_USER
        pushover_token = os.getenv('PUSHOVER_TOKEN')
        pushover_user = os.getenv('PUSHOVER_USER')
        
        if not pushover_token:
            print("錯誤：找不到 PUSHOVER_TOKEN 環境變數，請確保已在 .env 文件中設置")
            return False
        
        if not pushover_user:
            print("錯誤：找不到 PUSHOVER_USER 環境變數，請確保已在 .env 文件中設置")
            return False
        
        success = True
        for i in range(repeat):
            # 準備 Pushover API 請求
            url = "https://api.pushover.net/1/messages.json"
            data = {
                'token': pushover_token,
                'user': pushover_user,
                'message': message,
                'priority': priority
            }
            
            # 設置聲音（如果有指定）
            if sound:
                data['sound'] = sound
            
            print(f"正在發送 Pushover 通知: {message}")
            response = requests.post(url, data=data)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 1:
                    print(f"Pushover 通知發送成功 ({i+1}/{repeat})")
                else:
                    print(f"Pushover 通知發送失敗: {result.get('errors', '未知錯誤')}")
                    success = False
            else:
                print(f"Pushover 通知發送失敗，HTTP 狀態碼: {response.status_code}")
                print(f"響應內容: {response.text}")
                success = False
                
            if i < repeat - 1 and repeat > 1:
                print(f"等待 3 秒後發送下一次通知 ({i+1}/{repeat})...")
                time.sleep(3)  # 如果需要重複發送，等待3秒再發送下一次
        
        return success
    except Exception as e:
        print(f"發送 Pushover 通知時發生錯誤: {e}")
        return False

async def check_login(auth_json_path, headless=True):
    """
    使用 auth.json 檢查是否可以登入 https://www.lietaresearch.com/platform
    
    Args:
        auth_json_path: auth.json 的路徑
    
    Returns:
        bool: 是否成功登入
    """
    # 檢查 auth.json 是否存在
    if not os.path.exists(auth_json_path):
        print(f"錯誤: {auth_json_path} 不存在")
        return False
    
    # 讀取 auth.json
    try:
        with open(auth_json_path, 'r', encoding='utf-8') as f:
            auth_data = json.load(f)
            
        print("成功讀取 auth.json")
        
        # 顯示 auth.json 的結構（不顯示實際值）
        print("auth.json 包含以下鍵：")
        for key in auth_data.keys():
            print(f"  - {key}")
            
    except json.JSONDecodeError:
        print(f"錯誤: {auth_json_path} 不是有效的 JSON 格式")
        return False
    except Exception as e:
        print(f"讀取 {auth_json_path} 時發生錯誤: {str(e)}")
        return False
    
    # 使用 Playwright 進行登入檢查
    async with async_playwright() as p:
        # 啟動瀏覽器，使用 auth.json 作為 storage_state
        print(f"啟動瀏覽器並加載 auth.json 作為 storage state (headless={headless})...")
        browser = await p.chromium.launch(headless=headless)
        
        # 直接使用 auth.json 作為 storage_state 創建上下文
        context = await browser.new_context(storage_state=auth_json_path)
        
        try:
            # 建立新頁面
            page = await context.new_page()
            
            # 設置頁面超時時間
            page.set_default_timeout(60000)  # 60 秒，增加超時時間以防止網路緩慢
            
            # 導航到登入頁面
            print("正在訪問平台頁面...")
            try:
                await page.goto("https://www.lietaresearch.com/platform", timeout=60000)
                await page.wait_for_load_state('networkidle', timeout=60000)
            except Exception as e:
                print(f"訪問平台頁面時發生錯誤: {str(e)}")
                return False
            
            # 檢查當前 URL 和頁面內容，判斷是否需要登入
            current_url = page.url
            print(f"當前頁面 URL: {current_url}")
            
            # 檢查是否已經登入
            if "/login" not in current_url and "/auth" not in current_url:
                print("似乎已經處於登入狀態，檢查是否可以訪問平台...")
                
                # 移除截圖功能
                
                # 檢查頁面上是否有 Login 字樣，如果有則表示未登入
                try:
                    # 先檢查是否有登入頁面的元素，更精確的選擇器
                    login_selectors = ["text=Login", "text=Sign in", "text=登入", "text=登录", ".login-form", "form[action*='login']", "form[action*='auth']", "input[name='password']"]
                    login_found = False
                    for selector in login_selectors:
                        if await page.query_selector(selector):
                            print(f"發現登入元素: '{selector}'，表示未登入")
                            login_found = True
                            break
                    
                    if login_found:
                        print("失敗: 頁面上有登入元素，表示未登入成功")
                        return False
                    else:
                        print("成功: 頁面上沒有登入元素，表示已登入成功")
                        return True
                except Exception as e:
                    print(f"檢查登入狀態時發生錯誤: {str(e)}")
            
            # 如果需要登入，先檢查是否在登入頁面
            if "/login" in current_url or "/auth" in current_url:
                print("正在嘗試登入...")
                # 不再嘗試使用 token，直接進入帳號密碼登入流程
            
            # 如果重定向到登入頁面，嘗試使用帳號密碼登入
            if "/login" in page.url or "/auth" in page.url:
                print("需要登入，正在嘗試使用帳號密碼...")
                
                # 檢查是否有必要的登入信息
                if not email or not password:
                    print("錯誤: auth.json 缺少必要的登入信息 (email/username 或 password)")
                    print("提示: 請確保 auth.json 包含以下任一組合的鍵：")
                    print("  - email 和 password")
                    print("  - username 和 password")
                    print("  - token 或 access_token")
                    print("  - cookies 列表")
                    return False
                
                # 等待登入表單出現
                try:
                    # 嘗試找到登入表單的輸入框
                    email_selectors = ['input[type="email"]', 'input[name="email"]', 'input[placeholder*="email"]', 
                                      'input[name="username"]', 'input[placeholder*="username"]']
                    password_selectors = ['input[type="password"]', 'input[name="password"]', 'input[placeholder*="password"]']
                    
                    # 尋找並填寫電子郵件/用戶名輸入框
                    email_input = None
                    for selector in email_selectors:
                        if await page.query_selector(selector):
                            email_input = selector
                            break
                    
                    if not email_input:
                        print("錯誤: 無法找到電子郵件/用戶名輸入框")
                        return False
                    
                    # 尋找並填寫密碼輸入框
                    password_input = None
                    for selector in password_selectors:
                        if await page.query_selector(selector):
                            password_input = selector
                            break
                    
                    if not password_input:
                        print("錯誤: 無法找到密碼輸入框")
                        return False
                    
                    # 填寫登入表單
                    print(f"找到登入表單，正在填寫...")
                    await page.fill(email_input, email)
                    await page.fill(password_input, password)
                    
                    # 尋找登入按鈕
                    login_button_selectors = [
                        'button[type="submit"]', 
                        'input[type="submit"]',
                        'button:has-text("Login")', 
                        'button:has-text("Sign in")',
                        'button:has-text("登入")',
                        'button:has-text("登录")',
                        '.login-button',
                        '.signin-button'
                    ]
                    
                    login_button = None
                    for selector in login_button_selectors:
                        if await page.query_selector(selector):
                            login_button = selector
                            break
                    
                    if not login_button:
                        print("錯誤: 無法找到登入按鈕")
                        return False
                    
                    # 點擊登入按鈕
                    print("點擊登入按鈕...")
                    await page.click(login_button)
                    
                    # 等待登入結果
                    print("等待登入處理...")
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(5000)  # 等待登入處理和可能的重定向
                    
                    # 檢查是否登入成功
                    if "/login" in page.url or "/auth" in page.url:
                        # 如果還在登入頁面，可能是登入失敗
                        error_selectors = [".error-message", ".alert-danger", ".error", "[role=alert]", "text=Invalid"]
                        error_message = "未找到具體錯誤信息"
                        
                        for selector in error_selectors:
                            try:
                                if await page.query_selector(selector):
                                    error_message = await page.inner_text(selector)
                                    break
                            except:
                                pass
                                
                        print(f"登入失敗: {error_message}")
                        
                        # 移除截圖功能
                        return False
                    else:
                        # 檢查頁面上是否有 Login 字樣，如果有則表示未登入
                        try:
                            # 檢查是否有登入頁面的元素，更精確的選擇器
                            login_selectors = ["text=Login", "text=Sign in", "text=登入", "text=登录", ".login-form", "form[action*='login']", "form[action*='auth']", "input[name='password']"]
                            login_found = False
                            for selector in login_selectors:
                                if await page.query_selector(selector):
                                    print(f"發現登入元素: '{selector}'，表示未登入")
                                    login_found = True
                                    break
                            
                            if login_found:
                                print("失敗: 頁面上有登入元素，表示未登入成功")
                                return False
                            else:
                                print("成功: 頁面上沒有登入元素，表示已登入成功")
                                return True
                        except Exception as e:
                            print(f"檢查登入狀態時發生錯誤: {str(e)}")
                            return False
                except Exception as e:
                    print(f"登入過程中發生錯誤: {str(e)}")
                    return False
            else:
                print("無法確定當前頁面狀態，請檢查網站結構是否有變化")
                return False
                    
        except Exception as e:
            print(f"登入過程中發生錯誤: {str(e)}")
            return False
        finally:
            # 關閉瀏覽器
            await browser.close()

async def main():
    # 解析命令行參數
    parser = argparse.ArgumentParser(description='檢查 auth.json 是否可以登入 Lieta Research 平台')
    parser.add_argument('--auth-path', '-a', default='auth.json', help='auth.json 的路徑 (預設: auth.json)')
    parser.add_argument('--headless', '-H', action='store_true', default=True, help='使用無頭模式 (預設: True)')
    parser.add_argument('--no-headless', dest='headless', action='store_false', help='不使用無頭模式')
    parser.add_argument('--no-notify', dest='notify', action='store_false', default=True, help='不發送 Pushover 通知')
    
    args = parser.parse_args()
    auth_json_path = args.auth_path
    
    print(f"開始檢查 {auth_json_path} 是否可以登入 Lieta Research 平台...")
    print(f"時間: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"無頭模式: {args.headless}")
    print("-" * 50)
    
    # 執行登入檢查
    success = await check_login(auth_json_path, headless=args.headless)
    
    print("-" * 50)
    if success:
        print("✅ auth.json 可以成功登入 https://www.lietaresearch.com/platform")
        return 0
    else:
        print("❌ auth.json 無法登入 https://www.lietaresearch.com/platform")
        print("請確保 auth.json 包含正確的登入憑證")
        
        # 發送 Pushover 通知
        if args.notify:
            hostname = os.uname().nodename
            message = f"\U0001F6A8 {hostname}: auth.json 已失效\n"
            message += f"時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"\n請盡快重新登入 Lieta Research 平台並更新 auth.json"
            
            send_pushover_notification(
                message=message,
                priority=1,  # 高優先級
                sound="siren",  # 警報聲
                repeat=2  # 重複發送 2 次
            )
            
        return 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n程序被用戶中斷")
        sys.exit(1)
    except Exception as e:
        print(f"執行過程中發生未處理的錯誤: {str(e)}")
        # 發送通知
        try:
            hostname = os.uname().nodename
            message = f"\U0001F6A8 {hostname}: auth.json 檢查腳本執行錯誤\n"
            message += f"時間: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
            message += f"錯誤: {str(e)}"
            send_pushover_notification(message=message, priority=1)
        except:
            pass
        sys.exit(1)
