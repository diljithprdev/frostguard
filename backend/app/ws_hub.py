import asyncio
import json
import queue
from typing import Any

OUT_Q: "queue.Queue[dict]" = queue.Queue(maxsize=1000)
_CLIENTS: set = set()


def push(message: dict[str, Any]) -> None:
    try:
        OUT_Q.put_nowait(message)
    except queue.Full:
        pass


async def register(websocket) -> None:
    _CLIENTS.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    finally:
        _CLIENTS.discard(websocket)


async def pump() -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            msg = await loop.run_in_executor(None, lambda: OUT_Q.get(timeout=0.1))
        except queue.Empty:
            await asyncio.sleep(0.05)
            continue
        dead = []
        for ws in list(_CLIENTS):
            try:
                await ws.send_text(json.dumps(msg, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            _CLIENTS.discard(ws)
