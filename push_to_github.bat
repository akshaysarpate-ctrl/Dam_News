@echo off
setlocal enabledelayedexpansion
title Push to GitHub Assistant
cd /d "%~dp0"

echo ===================================================
echo             Push to GitHub Assistant
echo ===================================================
echo.

:: 1. Set Git Identity if not already set
git config --global user.name >nul 2>&1
if errorlevel 1 (
    echo Setting default Git identity...
    git config --global user.name "Dam News User"
    git config --global user.email "user@damnews.local"
)
git config --global core.autocrlf true >nul 2>&1

:: 2. Stage and Commit
echo Staging and committing files...
git add .
git commit -m "Deploy to Render" >nul 2>&1
git branch -M main >nul 2>&1

echo Files committed successfully!
echo.
echo ===================================================
echo Go to https://github.com/new in your browser.
echo Create a new repository and copy its URL.
echo ===================================================
echo.
set /p REPO_URL="Paste your GitHub repository URL here: "

if "%REPO_URL%"=="" (
    echo No URL entered. Exiting.
    pause
    exit /b
)

:: Remove old origin if exists
git remote remove origin >nul 2>&1

:: Add new origin and push
echo.
echo Connecting to %REPO_URL% ...
git remote add origin %REPO_URL%

echo Uploading files to GitHub...
git push -u origin main

if errorlevel 1 (
    echo.
    echo ---------------------------------------------------
    echo Push failed. Please check the URL and sign in if prompted.
    echo ---------------------------------------------------
) else (
    echo.
    echo ===================================================
    echo SUCCESS! Your code is now on GitHub!
    echo You can now connect it on https://render.com
    echo ===================================================
)

echo.
pause
