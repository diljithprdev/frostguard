@echo off
setlocal EnableExtensions
title FROSTGUARD - Stop Server
echo Stopping FROSTGUARD / uvicorn processes...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*app.main:app*' } | ForEach-Object { Write-Host ('Killing PID ' + $_.ProcessId); Stop-Process -Id $_.ProcessId -Force }"
echo Done.
timeout /t 2 >nul
