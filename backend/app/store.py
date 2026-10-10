import json
import sqlite3
import threading
import time
from typing import Any, Optional

from . import config

_lock = threading.Lock()
_latest: dict[str, Any] = {}
_last_tcp_seen: float = 0.0
_recent_messages: list[dict] = []

_conn: Optional[sqlite3.Connection] = None


def init_db() -> None:
    global _conn
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT UNIQUE,
            device_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            door_state TEXT,
            door_open_seconds REAL,
            payload TEXT,
            received_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )"""
    )
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS status_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            received_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )"""
    )
    _conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            warning_threshold_seconds INTEGER NOT NULL DEFAULT 30,
            repeat_alert_seconds INTEGER NOT NULL DEFAULT 0,
            push_enabled INTEGER NOT NULL DEFAULT 1,
            buzzer_enabled INTEGER NOT NULL DEFAULT 0,
            system_enabled INTEGER NOT NULL DEFAULT 1,
            config_version INTEGER NOT NULL DEFAULT 1
        )"""
    )
    _conn.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")
    # migrate older DBs created before system_enabled existed
    try:
        _conn.execute("ALTER TABLE settings ADD COLUMN system_enabled INTEGER NOT NULL DEFAULT 1")
    except Exception:
        pass
    _conn.commit()


def get_settings() -> dict:
    with _lock:
        cur = _conn.execute(
            "SELECT warning_threshold_seconds, repeat_alert_seconds,"
            " push_enabled, buzzer_enabled, config_version, system_enabled"
            " FROM settings WHERE id=1"
        )
        row = cur.fetchone()
    if row is None:
        return {
            "warning_threshold_seconds": 30,
            "repeat_alert_seconds": 0,
            "push_enabled": True,
            "buzzer_enabled": False,
            "config_version": 1,
            "system_enabled": True,
        }
    return {
        "warning_threshold_seconds": row[0],
        "repeat_alert_seconds": row[1],
        "push_enabled": bool(row[2]),
        "buzzer_enabled": bool(row[3]),
        "config_version": row[4],
        "system_enabled": bool(row[5]),
    }


def update_settings(fields: dict) -> dict:
    allowed = {
        "warning_threshold_seconds",
        "repeat_alert_seconds",
        "push_enabled",
        "buzzer_enabled",
        "system_enabled",
    }
    sets = {k: v for k, v in fields.items() if k in allowed and v is not None}
    with _lock:
        if sets:
            assign = ", ".join(f"{k} = ?" for k in sets)
            _conn.execute(
                f"UPDATE settings SET {assign}, config_version = config_version + 1 WHERE id=1",
                tuple(sets.values()),
            )
        else:
            _conn.execute("UPDATE settings SET config_version = config_version + 1 WHERE id=1")
        _conn.commit()
    return get_settings()


def update_status(payload: dict, source: str) -> dict:
    global _last_tcp_seen
    with _lock:
        now = time.time()
        _latest.update(payload)
        _latest["_source"] = source
        _latest["_received_at"] = now
        if source == "tcp":
            _last_tcp_seen = now
        _recent_messages.append(
            {"payload": payload, "source": source, "received_at": now}
        )
        del _recent_messages[:-50]
        snapshot = dict(_latest)
    if _conn is not None:
        with _lock:
            _conn.execute(
                "INSERT INTO status_history (device_id, payload) VALUES (?, ?)",
                (str(payload.get("device_id", "unknown")), json.dumps(payload)),
            )
            _conn.commit()
    return snapshot


def add_event(payload: dict, source: str) -> dict:
    event_id = payload.get("event_id")
    event_type = payload.get("event_type", "UNKNOWN")
    device_id = str(payload.get("device_id", "unknown"))
    duplicated = False
    if _conn is not None:
        with _lock:
            try:
                _conn.execute(
                    "INSERT INTO events (event_id, device_id, event_type, door_state, door_open_seconds, payload)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        event_id,
                        device_id,
                        event_type,
                        payload.get("door_state"),
                        payload.get("door_open_seconds"),
                        json.dumps(payload),
                    ),
                )
                _conn.commit()
            except sqlite3.IntegrityError:
                duplicated = True
    return {
        "event_id": event_id,
        "event_type": event_type,
        "device_id": device_id,
        "duplicated": duplicated,
        "source": source,
    }


def get_latest() -> dict:
    with _lock:
        snap = dict(_latest)
        last_seen = _last_tcp_seen
    if not snap:
        return {"connected": False, "message": "no device data received yet"}
    offline_after = config.DEVICE_OFFLINE_AFTER
    tcp_connected = last_seen and (time.time() - last_seen) < offline_after
    snap["connected"] = bool(tcp_connected)
    snap["last_seen_age_seconds"] = round(time.time() - last_seen, 1) if last_seen else None
    return snap


def recent_messages(limit: int = 20) -> list[dict]:
    with _lock:
        return list(_recent_messages[-limit:])


def recent_events(
    limit: int = 50,
    offset: int = 0,
    event_type: str | None = None,
) -> tuple[list[dict], int]:
    if _conn is None:
        return [], 0
    where = ""
    params: list = []
    if event_type:
        where = " WHERE event_type = ?"
        params = [event_type]
    with _lock:
        total = _conn.execute(
            f"SELECT COUNT(*) FROM events{where}", params
        ).fetchone()[0]
        cur = _conn.execute(
            "SELECT event_id, device_id, event_type, door_state, door_open_seconds, received_at"
            f" FROM events{where} ORDER BY id DESC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        )
        rows = cur.fetchall()
    return (
        [
            {
                "event_id": r[0],
                "device_id": r[1],
                "event_type": r[2],
                "door_state": r[3],
                "door_open_seconds": r[4],
                "received_at": r[5],
            }
            for r in rows
        ],
        total,
    )
