@echo off
title Dam Failure News Watch - Online Sharing
cd /d "%~dp0"

echo ===================================================
echo     Dam Failure News Watch - Make Public Online
echo ===================================================
echo.
echo 1. Starting local server...
start "Dam News Server" cmd /c "python app.py"

echo 2. Waiting 3 seconds for server to start...
timeout /t 3 /nobreak >nul

echo 3. Creating secure public link with Cloudflare...
echo.
echo ---------------------------------------------------
echo LOOK FOR THE LINK BELOW (ends with .trycloudflare.com)
echo Anyone on the internet can open this link!
echo Keep this window OPEN while you want it online.
echo ---------------------------------------------------
echo.

cloudflared.exe tunnel --url http://127.0.0.1:5000

pause
