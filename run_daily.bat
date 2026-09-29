@echo off
REM Daily 7:00 AM collection across national and regional newspapers
cd /d "%~dp0"
echo [%date% %time%] Starting 7:00 AM daily dam news collection >> collect.log
python collect.py --days 3 --workers 6 >> collect.log 2>&1
echo [%date% %time%] Finished 7:00 AM daily dam news collection >> collect.log
