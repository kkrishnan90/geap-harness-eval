"""Per (model, location) admission control: AIMD concurrency + circuit breaker + jittered backoff."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

from .bus import BUS as _BUS


class _Pub:
    """BUS.publish + optional persistence of infra signals."""

    gov = None

    def publish(self, ev, data, run_id=None):
        _BUS.publish(ev, data, run_id)
        if ev == "infra" and self.gov is not None and self.gov.on_event:
            self.gov.on_event(data)


BUS = _Pub()


@dataclass
class Lane:
    key: str
    limit: float
    max_limit: int
    inflight: int = 0
    consecutive_failures: int = 0
    open_until: float = 0.0
    last_429: float = 0.0
    daily_exhausted: bool = False
    n429: int = 0


class Governor:
    def __init__(self, max_per_lane: int = 4, breaker_threshold: int = 4, cooldown_s: float = 120.0, on_event=None):
        self.on_event = on_event  # persistence hook: (payload) -> None
        self.lanes: dict[str, Lane] = {}
        self.max_per_lane = max_per_lane
        self.breaker_threshold = breaker_threshold
        self.cooldown_s = cooldown_s
        self.cond = asyncio.Condition()
        self._task: asyncio.Task | None = None
        BUS.gov = self

    def lane(self, model: str, location: str) -> Lane:
        k = f"{model}@{location}"
        if k not in self.lanes:
            self.lanes[k] = Lane(k, float(self.max_per_lane), self.max_per_lane)
        return self.lanes[k]

    async def acquire(self, keys: list[tuple[str, str]]) -> None:
        lanes = [self.lane(m, l) for m, l in keys]
        async with self.cond:
            while True:
                now = time.time()
                blocked = [ln for ln in lanes if ln.daily_exhausted or ln.open_until > now or ln.inflight >= max(1, int(ln.limit))]
                if not blocked:
                    for ln in lanes:
                        ln.inflight += 1
                    return
                try:
                    await asyncio.wait_for(self.cond.wait(), timeout=5)
                except TimeoutError:
                    pass  # re-check breaker cooldowns

    async def release(self, keys: list[tuple[str, str]], infra_failure: bool = False) -> None:
        async with self.cond:
            for m, l in keys:
                ln = self.lane(m, l)
                ln.inflight = max(0, ln.inflight - 1)
                if infra_failure:
                    ln.consecutive_failures += 1
                    if ln.consecutive_failures >= self.breaker_threshold:
                        ln.open_until = time.time() + self.cooldown_s
                        BUS.publish("infra", {"kind": "breaker_open", "model": m, "location": l, "detail": f"{self.cooldown_s:.0f}s"})
                else:
                    if ln.consecutive_failures and ln.open_until:
                        BUS.publish("infra", {"kind": "breaker_close", "model": m, "location": l, "detail": ""})
                    ln.consecutive_failures = 0
                    ln.open_until = 0
            self.cond.notify_all()

    def on_llm_error(self, model: str, location: str, kind: str) -> None:
        ln = self.lane(model, location)
        if kind == "quota_daily":
            ln.daily_exhausted = True
            BUS.publish("infra", {"kind": "breaker_open", "model": model, "location": location, "detail": "daily quota exhausted"})
        if kind in ("quota", "quota_daily", "overloaded"):
            ln.n429 += 1
            ln.last_429 = time.time()
            old = ln.limit
            ln.limit = max(1.0, ln.limit / 2)
            BUS.publish("infra", {"kind": "429", "model": model, "location": location, "detail": kind})
            if old != ln.limit:
                BUS.publish("infra", {"kind": "aimd", "model": model, "location": location, "detail": f"limit {old:.0f}->{ln.limit:.0f}"})

    async def recover_loop(self) -> None:
        """Additive increase: +1 per quiet minute."""
        while True:
            await asyncio.sleep(60)
            async with self.cond:
                for ln in self.lanes.values():
                    if ln.limit < ln.max_limit and time.time() - ln.last_429 > 60:
                        ln.limit += 1
                        m, l = ln.key.split("@")
                        BUS.publish("infra", {"kind": "aimd", "model": m, "location": l, "detail": f"limit ->{ln.limit:.0f}"})
                self.cond.notify_all()

    def snapshot(self) -> list[dict]:
        return [{"lane": ln.key, "limit": ln.limit, "inflight": ln.inflight, "n429": ln.n429,
                 "breaker": "open" if ln.open_until > time.time() or ln.daily_exhausted else "closed"}
                for ln in self.lanes.values()]


def backoff_delay(n: int, base: float = 2.0, cap: float = 120.0, retry_after: float | None = None) -> float:
    """Full jitter: random(0, min(cap, base*2^n)), never below Retry-After."""
    d = random.uniform(0, min(cap, base * (2 ** n)))
    return max(d, retry_after or 0.0)
