@echo off
chcp 65001 >nul
title Site Link Finder
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Install it from https://python.org
    echo and tick "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

python -c "import requests, bs4, openpyxl" >nul 2>&1
if errorlevel 1 (
    echo Installing missing libraries...
    python -m pip install --quiet requests beautifulsoup4 openpyxl
)

python app.py
pause
