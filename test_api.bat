@echo off
setlocal EnableExtensions
title FROSTGUARD - API Test
set "BASE=http://127.0.0.1:8000"

echo ============================================================
echo  FROSTGUARD quick API test (server must be running)
echo ============================================================
echo.

echo [1] GET /api/health
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/api/health' -TimeoutSec 5).Content } catch { 'FAILED: ' + $_.Exception.Message }"
echo.
echo.

echo [2] GET /api/device/status
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/api/device/status' -TimeoutSec 5).Content } catch { 'FAILED: ' + $_.Exception.Message }"
echo.
echo.

echo [3] POST /api/device/events (fake door event)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$b='{\"event_id\":\"test-'+(Get-Random)+'\",\"device_id\":\"esp32-freezer-01\",\"event_type\":\"DOOR_OPEN\",\"door_state\":\"OPEN\",\"door_open_seconds\":0}'; try { (Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/api/device/events' -Method POST -ContentType 'application/json' -Body $b -TimeoutSec 5).Content } catch { 'FAILED: ' + $_.Exception.Message }"
echo.
echo.

echo [4] GET /api/events
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri '%BASE%/api/events?limit=5' -TimeoutSec 5).Content } catch { 'FAILED: ' + $_.Exception.Message }"
echo.
echo.
echo If all 4 show JSON, the backend is healthy.
pause
