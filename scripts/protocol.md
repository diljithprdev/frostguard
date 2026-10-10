# FROSTGUARD Device Protocol (Step 1)

Transport: raw TCP, newline-delimited JSON (NDJSON), port 8081.
Device connects out to the server (ESP32 = TCP client). One JSON object per line.

## Device → Server

### status (send every 1s while active)
```json
{"type":"status","device_id":"esp32-freezer-01","door_state":"OPEN","door_open_seconds":35,"alarm_active":false,"wifi_rssi":-55,"uptime_seconds":1200,"firmware_version":"1.0.0"}
```

### event (send immediately on state change)
```json
{"type":"event","event_id":"<unique-uuid>","device_id":"esp32-freezer-01","event_type":"DOOR_OPEN","door_state":"OPEN","door_open_seconds":0}
```
- `event_type` ∈ DOOR_OPEN | DOOR_CLOSED | OVERDUE | RECOVERY | HEARTBEAT
- `event_id` must be unique per event → server drops duplicates (HTTP retry safety).

## Server → Device (Step 3, not yet used)
Config pushes will flow down the same socket as `{"type":"config",...}` lines.

## HTTP fallback (same payloads)
- `POST /api/device/heartbeat` (status body)
- `POST /api/device/events` (event body)
