@echo off
setlocal EnableExtensions
title FROSTGUARD - Setup
set "ROOT=%~dp0"

echo ============================================================
echo            FROSTGUARD SETUP (Windows 11)
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [FAIL] Python not found. Install Python 3.11+ from python.org
    echo        and tick "Add python.exe to PATH" during install.
    pause
    exit /b 1
)
echo [OK] Python found.

if exist "%ROOT%venv\Scripts\python.exe" (
    echo [OK] Virtual environment already exists - skipping create.
) else (
    echo [..] Creating virtual environment...
    python -m venv "%ROOT%venv"
    if errorlevel 1 (
        echo [FAIL] Could not create venv.
        pause
        exit /b 1
    )
    echo [OK] venv created.
)

echo [..] Installing dependencies (first run takes a minute)...
"%ROOT%venv\Scripts\python.exe" -m pip install --upgrade pip -q
"%ROOT%venv\Scripts\python.exe" -m pip install -r "%ROOT%backend\requirements.txt" -q
if errorlevel 1 (
    echo [FAIL] pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo [OK] Dependencies installed.

if exist "%ROOT%.env" (
    echo [OK] .env already exists - NOT overwriting.
) else (
    copy "%ROOT%.env.example" "%ROOT%.env" >nul
    echo [OK] Created .env from .env.example.
)

echo.
echo ============================================================
echo  SETUP COMPLETE
echo.
echo  Next:
echo    1. Run  start_server.bat  to launch the backend
echo    2. The dashboard opens automatically at http://127.0.0.1:8000
echo    3. In another terminal run the simulator:
echo       venv\Scripts\python.exe tools\esp32_sim.py
echo ============================================================
pause
