cd /home/ben/code/gex

# 使用 uv 執行 playwright_record.py (第一個配置)
/home/ben/.local/bin/uv run python playwright_record.py --auth auth.json --config config.json >> /home/ben/Downloads/crontab.log 2>&1
sleep 60

# 使用 uv 執行 gamma_converter.py
/home/ben/.local/bin/uv run python gamma_converter.py --force --overwrite >> /home/ben/Downloads/crontab.log 2>&1
sleep 150

# 使用 uv 執行 extract_gamma_from_html.py (使用當日的 HTML 文件)
/home/ben/.local/bin/uv run python extract_gamma_from_html.py >> /home/ben/Downloads/crontab.log 2>&1
sleep 10

# 使用 uv 執行 sending_discord.py
/home/ben/.local/bin/uv run python sending_discord.py >> /home/ben/Downloads/crontab.log 2>&1

