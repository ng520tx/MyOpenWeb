@echo off
setlocal

cd /d "%~dp0"

echo [MyOpenWeb] Starting FastAPI backend on http://127.0.0.1:8000
echo [MyOpenWeb] Keep this window open while using the app.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\dev-server.ps1"

echo.
echo [MyOpenWeb] Backend process exited.
pause
