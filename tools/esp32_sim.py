"""FROSTGUARD ESP32 simulator — speaks the exact NDJSON TCP protocol the real firmware uses.

Usage:  python tools\esp32_sim.py            (loops forever)
        python tools\esp32_sim.py --once     (single open/close cycle then exits)
"""
import argparse
import json
import socket
import time
import uuid

HOST = "127.0.0.1"
PORT = 8081
DEVICE_ID = "esp32-freezer-01"
THRESHOLD = 30


def send(sock: socket.socket, obj: dict) -> None:
    obj["device_id"] = DEVICE_ID
    line = json.dumps(obj) + "\n"
    sock.sendall(line.encode("utf-8"))
    print(f"  -> {line.strip()}")


def status(sock, door_state, open_secs, alarm):
    send(sock, {
        "type": "status",
        "door_state": door_state,
        "door_open_seconds": open_secs,
        "alarm_active": alarm,
        "wifi_rssi": -55,
        "uptime_seconds": round(time.time() - START, 1),
        "firmware_version": "1.0.0-sim",
    })


def event(sock, event_type, door_state, open_secs):
    send(sock, {
        "type": "event",
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "door_state": door_state,
        "door_open_seconds": open_secs,
    })


def run_cycle(sock, open_seconds=40.0):
    print("--- door CLOSED ---")
    status(sock, "CLOSED", 0, False)
    time.sleep(2)

    print("--- door OPEN ---")
    event(sock, "DOOR_OPEN", "OPEN", 0)
    status(sock, "OPEN", 0, False)
    t0 = time.time()
    overdue_sent = False
    while True:
        elapsed = time.time() - t0
        if elapsed >= open_seconds:
            break
        alarm = elapsed >= THRESHOLD
        if alarm and not overdue_sent:
            event(sock, "OVERDUE", "OPEN", round(elapsed, 1))
            overdue_sent = True
        status(sock, "OPEN", round(elapsed, 1), alarm)
        time.sleep(1)

    print("--- door CLOSED (recovery) ---")
    event(sock, "DOOR_CLOSED", "CLOSED", open_seconds)
    status(sock, "CLOSED", 0, False)
    if overdue_sent:
        event(sock, "RECOVERY", "CLOSED", open_seconds)
    time.sleep(2)


def main():
    global START
    START = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="one cycle then exit")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()

    print(f"Connecting to {args.host}:{args.port} ...")
    sock = socket.create_connection((args.host, args.port), timeout=5)
    sock.settimeout(10)
    print("CONNECTED. Simulating door cycles (Ctrl+C to stop).")
    try:
        if args.once:
            run_cycle(sock)
        else:
            while True:
                run_cycle(sock)
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
    finally:
        sock.close()


if __name__ == "__main__":
    main()
