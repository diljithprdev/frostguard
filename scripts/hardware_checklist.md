# FROSTGUARD — Hardware Test Checklist (you run these)

Server running + firmware flashed. Mark each: PASS / FAIL + note.
Serial Monitor at 115200 open during all tests.

| # | Scenario | Steps | Expected | Result |
|---|---|---|---|---|
| 1 | Door opens | Move magnet away from sensor | Website → OPEN within 1 s; serial `[DOOR] OPEN`; DOOR_OPEN in event list | |
| 2 | Door closes | Magnet back near sensor | Website → CLOSED; elapsed resets to 0 | |
| 3 | Close before threshold | Open, close in < 30 s | No OVERDUE event, no alarm | |
| 4 | Stay open past threshold | Hold open ≥ 30 s | OVERDUE event appears; alarm_active true (buzzer if enabled) | |
| 5 | Overdue visible in backend | After #4, check dashboard | Alarm ACTIVE + OVERDUE in stream | |
| 6 | Threshold change applies | `PUT /api/settings {"warning_threshold_seconds":10}` via test_api/curl, wait ≤10 s | Serial `[CONFIG] applied threshold=10`; door now alarms at 10 s | |
| 7 | Close after overdue | Close door after alarm | Alarm clears, RECOVERY event, buzzer stops | |
| 8 | Wi-Fi outage | Change router/wifi or set wrong SSID, power-cycle ESP32 | Serial shows `[WIFI] LOST`; door events still logged locally; buzzer still works | |
| 9 | Wi-Fi reconnect | Restore Wi-Fi | `[TCP] CONNECTED` returns; status resumes; no duplicate events (server dedupes) | |
| 10 | ESP32 restart | Press EN/RST while running | Reconnects, re-reads door state, resumes reporting | |
| 11 | Backend restart | stop_server.bat → start_server.bat | History still in SQLite (`/api/events`); device reconnects ≤ 5 s | |
| 12 | Offline detection | Stop firmware (unplug ESP32) > 10 s | Dashboard shows disconnected/stale, NOT a false all-clear | |
| 13 | Invalid threshold | PUT settings with `{"warning_threshold_seconds":2}` | Rejected 422 with clear error | |
| 14 | Bounce resistance | Tap magnet quickly / wiggle | No rapid OPEN/CLOSE flapping (50 ms debounce) | |
| 15 | TCP down → HTTP fallback | Block port 8081 (firewall) or stop TCP while server HTTP runs | Events arrive via HTTP after 15 s (`[HTTP] sent ...`) | |

Notes:
- Test 6 quick command:
  `curl -X PUT http://127.0.0.1:8000/api/settings -H "Content-Type: application/json" -d "{\"warning_threshold_seconds\":10}`
- Report any FAIL with the serial log lines around it.
