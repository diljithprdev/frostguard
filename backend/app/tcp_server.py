import json
import logging
import socket
import threading
from typing import Callable

log = logging.getLogger("frostguard.tcp")

_stop = threading.Event()


def handle_line(line: str, callback: Callable[[dict, str], None]) -> None:
    line = line.strip()
    if not line:
        return
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        log.warning("bad json from device: %s", line[:200])
        return
    if not isinstance(payload, dict):
        log.warning("json is not an object: %r", payload)
        return
    callback(payload, "tcp")


def _client_thread(conn: socket.socket, addr, callback: Callable[[dict, str], None]) -> None:
    log.info("device connected: %s", addr)
    buf = ""
    conn.settimeout(1.0)
    try:
        while not _stop.is_set():
            try:
                data = conn.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            if not data:
                break
            buf += data.decode("utf-8", errors="replace")
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                handle_line(line, callback)
        if buf.strip():
            handle_line(buf, callback)
    finally:
        try:
            conn.close()
        except OSError:
            pass
        log.info("device disconnected: %s", addr)


def start_server(host: str, port: int, callback: Callable[[dict, str], None]) -> threading.Thread:
    def run() -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((host, port))
        srv.listen(5)
        srv.settimeout(1.0)
        log.info("TCP device server listening on %s:%s", host, port)
        while not _stop.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=_client_thread, args=(conn, addr, callback), daemon=True
            ).start()
        srv.close()

    thread = threading.Thread(target=run, daemon=True, name="frostguard-tcp")
    thread.start()
    return thread


def stop() -> None:
    _stop.set()
