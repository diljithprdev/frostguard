import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, store, tcp_server, ws_hub
from .schemas import EventIn, SettingsUpdate, StatusIn

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)
log = logging.getLogger("frostguard.main")


def _on_device_message(payload: dict, source: str) -> None:
    msg_type = payload.get("type", "status")
    if msg_type == "event":
        result = store.add_event(payload, source)
        if result["duplicated"]:
            log.info("duplicate event ignored: %s", payload.get("event_id"))
            return
        ws_hub.push({"type": "event", "data": result, "raw": payload})
        log.info("event %s from %s", payload.get("event_type"), payload.get("device_id"))
        return
    snapshot = store.update_status(payload, source)
    ws_hub.push({"type": "state", "data": snapshot})


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    tcp_server.start_server(config.TCP_HOST, config.TCP_PORT, _on_device_message)
    pump_task = asyncio.create_task(ws_hub.pump())
    log.info("FROSTGUARD backend up | HTTP %s:%s | TCP %s:%s",
             config.HTTP_HOST, config.HTTP_PORT, config.TCP_HOST, config.TCP_PORT)
    yield
    pump_task.cancel()
    tcp_server.stop()


app = FastAPI(title="FROSTGUARD Backend", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "frostguard", "version": "0.1.0"}


@app.get("/api/device/status")
def device_status() -> dict:
    return store.get_latest()


@app.post("/api/device/heartbeat")
def device_heartbeat(body: StatusIn) -> dict:
    _on_device_message(body.model_dump(exclude_none=True), "http")
    return {"ok": True}


@app.post("/api/device/events")
def device_event(body: EventIn) -> dict:
    result = store.add_event(body.model_dump(exclude_none=True), "http")
    if not result["duplicated"]:
        ws_hub.push({"type": "event", "data": result, "raw": body.model_dump(exclude_none=True)})
    return {"ok": True, "duplicated": result["duplicated"]}


@app.get("/api/events")
def events(limit: int = 50, offset: int = 0, event_type: str | None = None) -> dict:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    if event_type and event_type not in (
        "DOOR_OPEN", "DOOR_CLOSED", "OVERDUE", "RECOVERY", "HEARTBEAT",
    ):
        return JSONResponse(status_code=422, content={"detail": "invalid event_type"})
    items, total = store.recent_events(limit, offset, event_type)
    return {"events": items, "total": total, "offset": offset, "limit": limit}


@app.get("/api/settings")
def get_settings() -> dict:
    return store.get_settings()


@app.put("/api/settings")
def put_settings(body: SettingsUpdate) -> dict:
    updated = store.update_settings(body.model_dump())
    log.info("settings updated -> config_version=%s", updated["config_version"])
    ws_hub.push({"type": "settings", "data": updated})
    return updated


@app.get("/api/device/config")
def device_config() -> dict:
    s = store.get_settings()
    return {
        "device_id": "esp32-freezer-01",
        "warning_threshold_seconds": s["warning_threshold_seconds"],
        "repeat_alert_seconds": s["repeat_alert_seconds"],
        "buzzer_enabled": s["buzzer_enabled"],
        "system_enabled": s["system_enabled"],
        "config_version": s["config_version"],
    }


@app.get("/api/debug/messages")
def debug_messages(limit: int = 20) -> dict:
    return {"messages": store.recent_messages(max(1, min(limit, 50)))}


@app.websocket("/ws/live")
async def ws_live(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        await ws_hub.register(websocket)
    except WebSocketDisconnect:
        pass


@app.exception_handler(Exception)
async def generic_error(request, exc):  # noqa: ANN001
    log.exception("unhandled error on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "internal server error"})

app.mount("/", StaticFiles(directory=str(config.FRONTEND_DIR), html=True), name="frontend")
