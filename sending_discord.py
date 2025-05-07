import os
from datetime import datetime
from discord.ext import commands
import discord
import sys
import asyncio
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

# 設定機器人前綴和權限
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)
# 頻道 ID 字典
channels = {
    'tvcode': 1336223966096003093,
    'gamma_spx': 1336224011763585114,
    'gamma_qqq': 1336224048270676048,
    'gamma_vix': 1336224107804495872,
    'gamma_spy': 1336224144311586816,
    'gamma_iwm': 1336224159872712724,
    'gamma_smh': 1336224185671876618,
    'gamma_nvda': 1336247721404928010,
    'gamma_tsla': 1338782377719369739,
    'gamma_smci': 1336296741498130462,
    'gamma_uvix': 1337229331902107669,
    'gamma_svix': 1337229377296924702,
    'gamma_hims': 1343744430410170388,
    'gamma_upst': 1343744481844793354,
    'gamma_sofi': 1343744509556686928,
    'gamma_avgo': 1344499598210760799,
    'smile_spx': 1336226869573320714,
    'smile_qqq': 1336226898178474005,
    'smile_iwm': 1336226945595342938,
    'smile_smh': 1336226969276125195,
    'smile_nvda': 1336247775670697984,
    'smile_tsla': 1338782533030248459,
    'smile_smci': 1336296804945235998,
}

# 遞迴查找目錄中的檔案
def find_files(directory, date_str):
    files = []
    for root, _, filenames in os.walk(directory):
        for filename in filenames:
            # 檢查檔名是否符合 tvcode_YYYYMMDD.txt 格式
            if filename.startswith('tvcode_') and filename.endswith('.txt'):
                if date_str in filename:
                    print(f"找到符合的檔案: {filename}")
                    files.append(os.path.join(root, filename))
                else:
                    pass
            elif filename.endswith('.png'):
                if date_str in filename:
                    print(f"找到符合的圖片: {filename}")
                    files.append(os.path.join(root, filename))
                else:
                    pass
            else:
                pass
    return files

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        today_str = datetime.now().strftime('%Y%m%d')
        print(f"搜尋日期: {today_str}")  # 添加日誌
        directory = '/home/ben/pCloudDrive/stock/GEX/GEX_file'
        print(f"搜尋目錄: {directory}")  # 添加日誌
        
        files = find_files(directory, today_str)

        if not files:
            print(f"找不到 {today_str} 的檔案")
            await bot.close()
            return

        for file_path in files:
            filename = os.path.basename(file_path)
            print(f"處理檔案: {filename}")  # 添加日誌
            
            # 如果檔案名稱以 tvcode_ 開頭，直接使用 'tvcode' 作為頻道名稱
            if filename.startswith('tvcode_'):
                channel_name = 'tvcode'
            else:
                prefix = filename.split('_')[0].lower()
                symbol = filename.split('_')[1].lower() if len(filename.split('_')) > 1 else ''
                channel_name = f"{prefix}_{symbol}".rstrip('_')
            
            print(f"頻道名稱: {channel_name}")  # 添加日誌

            channel_id = channels.get(channel_name)
            if channel_id:
                channel = bot.get_channel(channel_id)
                if channel:
                    if filename.endswith('.png'):
                        await channel.send(file=discord.File(file_path))
                        print(f"已發送圖片: {filename}")  # 添加日誌
                    elif filename.endswith('.txt'):
                        with open(file_path, 'r') as file:
                            content = file.read().strip()
                            # 先按段落分割
                            paragraphs = content.split('\n\n')
                            for paragraph in paragraphs:
                                if not paragraph.strip():  # 跳過空段落
                                    continue
                                
                                # 如果段落超過 1900 字元 (預留一些空間)，進一步分割
                                if len(paragraph) > 1900:
                                    # 按行分割
                                    lines = paragraph.split('\n')
                                    current_message = ""
                                    
                                    for line in lines:
                                        # 如果當前行加上現有訊息會超過限制，先發送現有訊息
                                        if len(current_message) + len(line) + 1 > 1900:
                                            if current_message:
                                                await channel.send(current_message)
                                                await asyncio.sleep(1)
                                                current_message = line + "\n"
                                            else:
                                                # 如果單行就超過限制，需要進一步分割
                                                chunks = [line[i:i+1900] for i in range(0, len(line), 1900)]
                                                for chunk in chunks:
                                                    await channel.send(chunk)
                                                    await asyncio.sleep(1)
                                        else:
                                            current_message += line + "\n"
                                    
                                    # 發送最後剩餘的訊息
                                    if current_message:
                                        await channel.send(current_message)
                                        await asyncio.sleep(1)
                                else:
                                    # 段落不超過限制，直接發送
                                    await channel.send(paragraph + "\n")
                                    await asyncio.sleep(1)
                    print(f'已發送 {filename} 到 {channel.name}')
                else:
                    print(f"找不到頻道: {channel_name}")  # 添加日誌
            else:
                print(f"頻道ID不存在: {channel_name}")  # 添加日誌

        print("檔案發送完成！")
        await bot.close()

    except Exception as e:
        print(f"錯誤：{str(e)}")
        await bot.close()

# 使用環境變數中的 Token
bot.run(os.getenv('DISCORD_BOT_TOKEN'))
