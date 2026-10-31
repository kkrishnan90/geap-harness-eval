"""In-process event bus feeding SSE subscribers; live PTY registry for WebSocket fan-out."""

from __future__ import annotations

import asyncio
import json
import time


class Bus:
    def __init__(self) -> None:
        self.subs: set[tuple[asyncio.Queue, str | None]] = set()
        self.ptys: dict[str, object] = {}  # attempt_id -> PtySession (or BrowserSession)

    def publish(self, event: str, data: dict, run_id: str | None = None) -> None:
        msg = (event, json.dumps(data, default=str))
        for q, rid in list(self.subs):
            if rid is None or run_id is None or rid == run_id:
                if q.qsize() < 5000:
                    q.put_nowait(msg)

    def subscribe(self, run_id: str | None = None) -> tuple[asyncio.Queue, tuple]:
        q: asyncio.Queue = asyncio.Queue()
        key = (q, run_id)
        self.subs.add(key)
        return q, key

    def unsubscribe(self, key: tuple) -> None:
        self.subs.discard(key)

    def log(self, msg: str, level: str = "info", run_id: str | None = None) -> None:
        self.publish("log", {"level": level, "msg": msg, "ts": time.time()}, run_id)


BUS = Bus()
