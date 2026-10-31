"""Model registry + availability/thinking probe (official SDKs, ADC, locked project)."""

from __future__ import annotations

import asyncio
import json
import random
import time

from .config import PROJECT, RUNS_DIR

AVAIL_PATH = RUNS_DIR / "availability.json"

MODELS = {
    "gemini-4-argon": {"family": "gemini", "provider": "google"},
    "gemini-3.8-flash": {"family": "gemini", "provider": "google"},
    "claude-opus-5-5": {"family": "claude", "provider": "anthropic"},
    "claude-sonnet-5-5": {"family": "claude", "provider": "anthropic"},
}
CANDIDATE_LOCATIONS = ["global", "us-central1", "us-east5", "us-east1", "europe-west1", "europe-west4", "asia-southeast1"]
# canonical thinking level -> provider request fragment
GEMINI_LEVELS = {"low": "LOW", "medium": "MEDIUM", "high": "HIGH"}
CLAUDE_LEVELS = {"off": None, "low": "low", "medium": "medium", "high": "high", "xhigh": "xhigh", "max": "max"}


def _code(e: Exception) -> str:
    s = str(e)
    for c in ("429", "404", "400", "403"):
        if c in s[:80]:
            return c
    return "error"


async def _call(model: str, loc: str, thinking: str | None, sem: asyncio.Semaphore) -> tuple[str, str]:
    from anthropic import AsyncAnthropicVertex
    from google import genai
    from google.genai import types

    for i in range(5):
        async with sem:
            try:
                if MODELS[model]["provider"] == "google":
                    cfg = None
                    if thinking:
                        cfg = types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level=GEMINI_LEVELS[thinking]))
                    c = genai.Client(vertexai=True, project=PROJECT, location=loc)
                    await c.aio.models.generate_content(model=model, contents="Reply OK", config=cfg)
                else:
                    c = AsyncAnthropicVertex(project_id=PROJECT, region=loc)
                    kw: dict = {}
                    if thinking and thinking != "off":
                        kw = {"thinking": {"type": "adaptive"}, "extra_body": {"output_config": {"effort": CLAUDE_LEVELS[thinking]}}}
                    await c.messages.create(model=model, max_tokens=1024, messages=[{"role": "user", "content": "Reply OK"}], **kw)
                return "ok", ""
            except Exception as e:  # noqa: BLE001
                code = _code(e)
                if code == "429":
                    await asyncio.sleep(2 ** i + random.random())
                    continue
                return code, str(e)[:200]
    return "no_quota", "persistent 429"


async def probe(models: list[str] | None = None, locations: list[str] | None = None) -> dict:
    models = models or list(MODELS)
    locations = locations or CANDIDATE_LOCATIONS
    sem = asyncio.Semaphore(4)
    keys = [(m, l) for m in models for l in locations]
    res = await asyncio.gather(*[_call(m, l, None, sem) for m, l in keys])
    avail = {f"{m}@{l}": {"status": s, "detail": d} for (m, l), (s, d) in zip(keys, res)}
    thinking: dict[str, list[str]] = {}
    for m in models:
        loc = next((l for l in locations if avail[f"{m}@{l}"]["status"] == "ok"), None)
        if not loc:
            thinking[m] = []
            continue
        levels = list(GEMINI_LEVELS) if MODELS[m]["provider"] == "google" else list(CLAUDE_LEVELS)
        r = await asyncio.gather(*[_call(m, loc, lv, sem) for lv in levels])
        thinking[m] = [lv for lv, (s, _) in zip(levels, r) if s == "ok"]
    out = {"probed_at": time.time(), "project": PROJECT, "availability": avail, "thinking": thinking}
    AVAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    AVAIL_PATH.write_text(json.dumps(out, indent=1))
    from .artifacts import upload_file
    upload_file(AVAIL_PATH)
    return out


def load_availability() -> dict | None:
    from .artifacts import ensure_local
    ensure_local(AVAIL_PATH)
    return json.loads(AVAIL_PATH.read_text()) if AVAIL_PATH.exists() else None


def locations_for(model: str, avail: dict) -> list[str]:
    return [k.split("@")[1] for k, v in avail["availability"].items() if k.split("@")[0] == model and v["status"] == "ok"]


def pick_location(model: str, avail: dict, preferred: str = "auto") -> str | None:
    locs = locations_for(model, avail)
    if preferred != "auto":
        return preferred if preferred in locs else None
    return "global" if "global" in locs else (locs[0] if locs else None)


def registry(avail: dict | None, book=None) -> list[dict]:
    out = []
    for m, meta in MODELS.items():
        locs = locations_for(m, avail) if avail else []
        priced = bool(book) and not book.complete_for(m, "global")
        out.append({"id": m, "family": meta["family"], "provider": meta["provider"], "locations": locs,
                    "thinking_levels": (avail or {}).get("thinking", {}).get(m, []), "priced": priced,
                    "enabled": bool(locs)})
    return out
