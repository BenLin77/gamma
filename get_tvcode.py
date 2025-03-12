import requests
import browser_cookie3
import json
from bs4 import BeautifulSoup
from datetime import datetime
import os
import time

def get_all_cookies():
    domain = 'www.lietaresearch.com'
    try:
        cookies = browser_cookie3.edge(domain_name=domain)
        return {cookie.name: cookie.value for cookie in cookies}
    except Exception:
        return {}

def save_response_to_txt(text):
    today = datetime.now().strftime('%Y%m%d')

    filename = f'{today}.txt'
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(f"{text}\n")

def get_token_from_browser():
    """從瀏覽器獲取最新的 token"""
    try:
        cookies = browser_cookie3.edge(domain_name='www.lietaresearch.com')
        for cookie in cookies:
            if cookie.name == 'sb-access-token':  # Supabase 的 token cookie 名稱
                return f"Bearer {cookie.value}"
        return None
    except Exception as e:
        print(f"獲取 token 失敗: {str(e)}")
        return None

cookies_dict = get_all_cookies()

options_headers = {
    'accept': '*/*',
    'accept-language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-CN;q=0.5',
    'access-control-request-headers': 'authorization',
    'access-control-request-method': 'GET',
    'origin': 'https://www.lietaresearch.com',
    'priority': 'u=1, i',
    'referer': 'https://www.lietaresearch.com/',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
}

get_headers = {
    'accept': '*/*',
    'accept-language': 'zh-TW,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6,zh-CN;q=0.5',
    'authorization': 'Bearer eyJhbGciOiJIUzI1NiIsImtpZCI6IjVpbllFa1dycldqQWZ1Z1giLCJ0eXAiOiJKV1QifQ.eyJpc3MiOiJodHRwczovL3Vud2dua3VyanhiaHl1bnVyc2doLnN1cGFiYXNlLmNvL2F1dGgvdjEiLCJzdWIiOiI5OTI4NWJjNS1lNmQyLTQyNTUtYmI5OC05YzI2M2JhYWZhNmQiLCJhdWQiOiJhdXRoZW50aWNhdGVkIiwiZXhwIjoxNzM1MTg0Mzc0LCJpYXQiOjE3MzUxODA3NzQsImVtYWlsIjoiZ29sZGtpbmc1MjFAZ21haWwuY29tIiwicGhvbmUiOiIiLCJhcHBfbWV0YWRhdGEiOnsicHJvdmlkZXIiOiJnb29nbGUiLCJwcm92aWRlcnMiOlsiZ29vZ2xlIl19LCJ1c2VyX21ldGFkYXRhIjp7ImF2YXRhcl91cmwiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NKNjVkN2xCWHJXSWZGU0tBblM3TFpCQXF2VGxEQmZoeWJBazU5d1ctcU03amhzNmc9czk2LWMiLCJlbWFpbCI6ImdvbGRraW5nNTIxQGdtYWlsLmNvbSIsImVtYWlsX3ZlcmlmaWVkIjp0cnVlLCJmdWxsX25hbWUiOiJCZW4gTGluIiwiaXNzIjoiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tIiwibmFtZSI6IkJlbiBMaW4iLCJwaG9uZV92ZXJpZmllZCI6ZmFsc2UsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS9BQ2c4b2NKNjVkN2xCWHJXSWZGU0tBblM3TFpCQXF2VGxEQmZoeWJBazU5d1ctcU03amhzNmc9czk2LWMiLCJwcm92aWRlcl9pZCI6IjEwMzQ1NTU5MTc3NjQ1MDA3NjUzMyIsInN1YiI6IjEwMzQ1NTU5MTc3NjQ1MDA3NjUzMyJ9LCJyb2xlIjoiYXV0aGVudGljYXRlZCIsImFhbCI6ImFhbDEiLCJhbXIiOlt7Im1ldGhvZCI6Im9hdXRoIiwidGltZXN0YW1wIjoxNzMzMjEwNTI2fV0sInNlc3Npb25faWQiOiI5NTI5MWExZi05M2I2LTRiZDQtYjAzMC00ZWJjNWFiNjAwYjEiLCJpc19hbm9ueW1vdXMiOmZhbHNlfQ.t5DTjEM3lDWfG2nCJBajyEe46IqLOAzRBw9ltOPEHR8',
    'origin': 'https://www.lietaresearch.com',
    'priority': 'u=1, i',
    'referer': 'https://www.lietaresearch.com/',
    'sec-ch-ua': '"Microsoft Edge";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Linux"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'cross-site',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
}

stock_list = ['qqq']
base_url = 'https://www.lietabackend.com/tvcode/'

for stock in stock_list:
    url = base_url + stock
    options_response = requests.options(url, headers=options_headers)
    
    if options_response.status_code == 200:
        # 嘗試發送請求
        response = requests.get(url, cookies=cookies_dict, headers=get_headers)
        
        # 如果收到 401（未授權），嘗試更新 token
        if response.status_code == 401:
            print("Token 已過期，嘗試更新...")
            new_token = get_token_from_browser()
            if new_token:
                get_headers['authorization'] = new_token
                print("Token 已更新，重試請求...")
                response = requests.get(url, cookies=cookies_dict, headers=get_headers)
            else:
                print("無法獲取新的 token，請確保瀏覽器已登入")
                continue
        
        if response.status_code == 200:
            try:
                soup = BeautifulSoup(response.text, 'html.parser')
                text_content = soup.p.text.strip() if soup.p else response.text
                print(text_content)
                save_response_to_txt(text_content)
                time.sleep(15)
            except Exception as e:
                print(f"處理回應時發生錯誤: {str(e)}")
        else:
            print(f"請求失敗: HTTP {response.status_code}")
    else:
        print(f"OPTIONS 請求失敗: HTTP {options_response.status_code}")

