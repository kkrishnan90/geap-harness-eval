"""Drive an interactive TUI in a real pseudo-terminal: screen emulation, asciicast recording, live fan-out."""

from __future__ import annotations

import asyncio
import json
import os
import re
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import ptyprocess
import pyte

BRACKET_START, BRACKET_END = "\x1b[200~", "\x1b[201~"
KEYS = {"enter": "\r", "esc": "\x1b", "tab": "\t", "up": "\x1b[A", "down": "\x1b[B", "ctrl_c": "\x03",
        "ctrl_d": "\x04", "space": " ", "y": "y", "1": "1", "2": "2", "shift_tab": "\x1b[Z"}


@dataclass
class DialogRule:
    name: str
    pattern: re.Pattern
    keys: list[str]
    max_times: int = 5
    used: int = 0
    last: float = 0.0


@dataclass
class PtySession:
    argv: list[str]
    cwd: Path
    env: dict[str, str]
    cast_path: Path
    cols: int = 220
    rows: int = 60
    dialogs: list[DialogRule] = field(default_factory=list)
    on_bytes: Callable[[bytes], None] | None = None
    on_dialog: Callable[[str], None] | None = None

    def __post_init__(self):
        self.screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.ByteStream(self.screen)
        self.last_change = time.time()
        self.t_start = 0.0
        self.proc: ptyprocess.PtyProcess | None = None
        self._cast = None
        self._closed = asyncio.Event()
        self.subscribers: set[asyncio.Queue] = set()

    # ---------------------------------------------------------- lifecycle
    async def start(self) -> None:
        self.cast_path.parent.mkdir(parents=True, exist_ok=True)
        self._cast = self.cast_path.open("w")
        self._cast.write(json.dumps({"version": 2, "width": self.cols, "height": self.rows,
                                     "timestamp": int(time.time()), "env": {"TERM": "xterm-256color"},
                                     "title": " ".join(self.argv)[:120]}) + "\n")
        self.proc = ptyprocess.PtyProcess.spawn(self.argv, cwd=str(self.cwd), env=self.env,
                                                dimensions=(self.rows, self.cols))
        self.t_start = time.time()
        loop = asyncio.get_running_loop()
        os.set_blocking(self.proc.fd, False)
        loop.add_reader(self.proc.fd, self._on_readable)

    def _on_readable(self) -> None:
        try:
            data = os.read(self.proc.fd, 65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            asyncio.get_running_loop().remove_reader(self.proc.fd)
            self._closed.set()
            return
        self.stream.feed(data)
        self.last_change = time.time()
        if self._cast:
            self._cast.write(json.dumps([round(self.last_change - self.t_start, 4), "o", data.decode("utf-8", "replace")]) + "\n")
        for q in list(self.subscribers):
            if q.qsize() < 2000:
                q.put_nowait(data)
        if self.on_bytes:
            self.on_bytes(data)
        self._check_dialogs()

    def _check_dialogs(self) -> None:
        text = self.text()
        now = time.time()
        for d in self.dialogs:
            if d.used < d.max_times and now - d.last > 1.5 and d.pattern.search(text):
                d.used += 1
                d.last = now
                for k in d.keys:
                    self.write(KEYS.get(k, k))
                if self.on_dialog:
                    self.on_dialog(d.name)

    @property
    def alive(self) -> bool:
        return bool(self.proc and self.proc.isalive())

    async def close(self, quit_keys: list[str] | None = None, grace_s: float = 5.0) -> int | None:
        if self.proc is None:
            return None
        if quit_keys and self.alive:
            for k in quit_keys:
                self.write(KEYS.get(k, k))
                await asyncio.sleep(0.4)
        t = time.time()
        while self.alive and time.time() - t < grace_s:
            await asyncio.sleep(0.2)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if not self.alive:
                break
            try:
                os.killpg(os.getpgid(self.proc.pid), sig)
            except (ProcessLookupError, PermissionError):
                pass
            await asyncio.sleep(1.5)
        try:
            asyncio.get_running_loop().remove_reader(self.proc.fd)
        except (ValueError, OSError):
            pass
        if self._cast:
            self._cast.close()
            self._cast = None
        self._closed.set()
        for q in list(self.subscribers):
            q.put_nowait(b"")
        return self.proc.exitstatus

    # ---------------------------------------------------------- io
    def write(self, s: str | bytes) -> None:
        """Non-blocking-fd safe write: wait for writability while draining the child's output (no deadlock)."""
        if not (self.proc and self.alive):
            return
        import select

        data = s.encode() if isinstance(s, str) else s
        fd = self.proc.fd
        deadline = time.time() + 30
        while data and time.time() < deadline:
            try:
                n = os.write(fd, data[:4096])
                data = data[n:]
            except BlockingIOError:
                r, _, _ = select.select([fd], [fd], [], 0.05)
                if r:
                    self._on_readable()
            except OSError:
                return

    async def paste(self, text: str, submit: bool = True, bracketed: bool = True) -> float:
        """Paste text (bracketed) and press Enter. Returns the time Enter was written (t0)."""
        if bracketed:
            self.write(BRACKET_START + text + BRACKET_END)
        else:
            for chunk in [text[i:i + 512] for i in range(0, len(text), 512)]:
                self.write(chunk)
                await asyncio.sleep(0.05)
        await asyncio.sleep(0.6)
        t0 = time.time()
        if submit:
            self.write("\r")
        return t0

    def text(self) -> str:
        return "\n".join(self.screen.display)

    async def wait_for(self, pattern: re.Pattern | str, timeout: float) -> re.Match | None:
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        end = time.time() + timeout
        while time.time() < end and self.alive:
            m = rx.search(self.text())
            if m:
                return m
            await asyncio.sleep(0.2)
        return rx.search(self.text())

    async def wait_stable(self, seconds: float, timeout: float) -> bool:
        end = time.time() + timeout
        while time.time() < end and self.alive:
            if time.time() - self.last_change >= seconds:
                return True
            await asyncio.sleep(0.2)
        return False

    def idle_for(self) -> float:
        return time.time() - self.last_change

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        self.subscribers.discard(q)
