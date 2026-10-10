@echo off
setlocal EnableExtensions
title FROSTGUARD - Server
set "ROOT=%~dp0"

if not exist "%ROOT%venv\Scripts\python.exe" (
    echo [FAIL] venv not found. Run setup.bat first.
    pause
    exit /b 1
)

echo ============================================================
echo   FROSTGUARD backend starting...
echo   Dashboard : http://127.0.0.1:8000
echo   Device TCP: port 8081
echo   Close this window to STOP the server.
echo ============================================================
echo.

start "" "http://127.0.0.1:8000"

"%ROOT%venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir "%ROOT%backend"

echo.
echo Server stopped.
pause
