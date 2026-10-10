# FrostGuard ❄️ — Freezer Door Monitor (ESP32 + FastAPI + Web + Android)

Real-time freezer door monitor that alerts before food spoils. ESP32 sensor → Python FastAPI backend → Live Web dashboard + Android app via WebSocket.

**Stack:** ESP32 (C++) · FastAPI · SQLite · WebSocket · Vanilla JS frontend · Kotlin Android

## What it does

- Detects `DOOR_OPEN / DOOR_CLOSED / OVERDUE / RECOVERY` from ESP32 `esp32-freezer-01`
- Live status page with big door UI (green SEALED / amber OPEN / red OVERDUE pulsing)
- History timeline with filters + pagination, Settings (threshold 5-1800s, buzzer, repeat alerts)
- Pushes every event over `/ws/live` in <1s, survives WiFi drops via HTTP fallback

## Project structure

```
frostguard/
├── firmware/frostguard/   ESP32 sensor code
├── backend/
│   ├── app/
│   │   ├── main.py        FastAPI + lifespan (HTTP + TCP + WS)
│   │   ├── tcp_server.py  raw TCP ingest from ESP32
│   │   ├── ws_hub.py      WebSocket fan-out
│   │   ├── store.py       SQLite persistence (events, status, settings)
│   │   ├── schemas.py     Pydantic models
│   │   └── config.py      env-based config (.env)
│   └── tests/
├── frontend/              live dashboard (index.html + css/ + js/)
├── android/               native Kotlin app
├── docs/UI_PLAN.md        UI spec (Home v3 Big Door)
├── .env.example           safe template — copy to .env
└── setup.bat / start_server.bat
```

## API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | health check |
| GET | `/api/device/status` | latest door state + last-seen |
| POST | `/api/device/heartbeat` | ESP32 status update |
| POST | `/api/device/events` | ESP32 event ingest (dedupe by event_id) |
| GET | `/api/events?limit=50&event_type=OVERDUE` | history |
| GET/PUT | `/api/settings` | threshold, buzzer, repeat |
| GET | `/api/device/config` | ESP32 pulls config + version |
| WS | `/ws/live` | live push: `{"type":"event"/"state"/"settings"}` |

## Quick start

```bash
# 1. Config
copy .env.example .env
# edit FROSTGUARD_HOST, FROSTGUARD_PORT, FROSTGUARD_TCP_PORT if needed

# 2. Install + run
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m app.main
# or from root: start_server.bat
```

- Dashboard: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/health`

Test without hardware:

```bash
test_api.bat
# or: curl -X POST http://127.0.0.1:8000/api/device/heartbeat -H "Content-Type: application/json" -d "{\"device_id\":\"esp32-freezer-01\",\"state\":\"OPEN\"}"
```

## Configuration (.env)

```
FROSTGUARD_HOST=127.0.0.1
FROSTGUARD_PORT=8000
FROSTGUARD_TCP_HOST=0.0.0.0
FROSTGUARD_TCP_PORT=8081
FROSTGUARD_OFFLINE_AFTER=10
```

## Notes

- Full loop: firmware → TCP/HTTP ingest → SQLite → WebSocket fan-out → web + mobile
- Dedupe by event_id, offline detection, config versioning for flaky WiFi
- Minimal industrial UI, no extra deps on the ESP32 side

## Roadmap

- [ ] FCM push notifications
- [ ] Multi-device support
- [ ] Docker + HTTPS deploy
- [ ] Play Store release for Android app
