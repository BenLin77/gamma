cd /home/ben/code/gex
/home/ben/.local/bin/pipenv run python playwright_record.py >> /home/ben/Downloads/crontab.log 2>&1
sleep 60
/home/ben/.local/bin/pipenv run python playwright_record1.py >> /home/ben/Downloads/crontab.log 2>&1
sleep 10
/home/ben/.local/bin/pipenv run python gamma_converter.py --overwrite >> /home/ben/Downloads/crontab.log 2>&1
sleep 600
/home/ben/.local/bin/pipenv run python sending_discord.py >> /home/ben/Downloads/crontab.log 2>&1
