@echo off
title AI Gaming Editor - New Device Setup
echo =======================================================
echo   AI GAMING EDITOR - ONE-CLICK NEW DEVICE SETUP
echo =======================================================
echo.

:: 1. Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.11 or 3.12 from https://www.python.org
    pause
    exit /b 1
)
echo [OK] Python found.

:: 2. Check Node
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js (v20+) from https://nodejs.org
    pause
    exit /b 1
)
echo [OK] Node.js found.

echo.
echo [1/3] Installing Python worker dependencies & bundled FFmpeg...
python -m pip install -r "%~dp0python-worker\requirements.txt"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies.
    pause
    exit /b 1
)

echo.
echo [2/3] Installing Node.js UI dependencies...
cd /d "%~dp0"
call npm ci
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install npm dependencies.
    pause
    exit /b 1
)

echo.
echo [3/3] Building desktop bundle...
call npm run dist
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   SETUP COMPLETE! 
echo   You can now double-click 'launch-app.bat' to start!
echo =======================================================
pause
