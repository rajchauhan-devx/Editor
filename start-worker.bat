@echo off
title AI Gaming Editor - Python Worker Daemon
echo =======================================================
echo   AI GAMING EDITOR - LOCAL PYTHON WORKER DAEMON
echo   Running on http://127.0.0.1:8765
echo =======================================================
cd /d "%~dp0python-worker"
python server.py
pause
