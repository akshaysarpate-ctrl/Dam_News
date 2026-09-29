@echo off
title Dam Failure News Watch
cd /d "%~dp0"

echo ===================================================
echo           Dam Failure News Watch
echo ===================================================
echo.
echo Starting web server on http://127.0.0.1:5000 ...
echo Opening your web browser in 2 seconds...
echo.

:: Launch the browser in background after 2 seconds
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://127.0.0.1:5000"

:: Start Flask app
python app.py

if errorlevel 1 (
    echo.
    echo ===================================================
    echo Server stopped unexpectedly or Python is missing.
    echo ===================================================
    pause
)
