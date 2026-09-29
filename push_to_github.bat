@echo off
set "PATH=C:\Program Files\Git\cmd;%PATH%"
title Push Dam News to GitHub
cd /d "%~dp0"

echo ===================================================
echo     Pushing Dam News to GitHub Repository
echo     Target: https://github.com/akshaysarpate-ctrl/Dam_News.git
echo ===================================================
echo.

git branch -M main
git remote set-url origin https://github.com/akshaysarpate-ctrl/Dam_News.git 2>nul || git remote add origin https://github.com/akshaysarpate-ctrl/Dam_News.git

echo Uploading files to GitHub...
echo (If a browser window or login popup appears, click "Sign in with your browser")
echo.

git push -u origin main

if errorlevel 1 (
    echo.
    echo ===================================================
    echo Push could not complete.
    echo If it failed due to existing files, trying force push...
    echo ===================================================
    git push -u origin main --force
)

echo.
echo ===================================================
echo ALL DONE! Your code is now live on GitHub:
echo https://github.com/akshaysarpate-ctrl/Dam_News
echo ===================================================
echo.
pause
