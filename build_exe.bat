@echo off
chcp 65001 >nul
title Build SiteLinkFinder.exe
cd /d "%~dp0"

echo Building a standalone .exe (no Python needed on the target machine).
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo Python not found. Building requires Python; running the .exe does not.
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install --quiet pyinstaller
)

python -m PyInstaller ^
    --onefile ^
    --name SiteLinkFinder ^
    --add-data "static;static" ^
    --clean ^
    --noconfirm ^
    app.py

if errorlevel 1 (
    echo.
    echo BUILD FAILED - see the messages above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   Done: dist\SiteLinkFinder.exe
echo   Send that single file to a colleague - nothing else needed.
echo   The build\ folder holds temporary files and can be deleted.
echo ============================================================
pause
