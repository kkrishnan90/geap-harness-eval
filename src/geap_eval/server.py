"""FastAPI server: REST + SSE + PTY WebSocket per docs/CONTRACTS.md §4; serves web/dist."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from . import __version__, analytics, pricing
from .artifacts import ensure_local
from .authz import require_admin, whoami
from .adapters import ADAPTERS, get_adapter
from .bus import BUS
from .config import ROOT, RunConfig
from .guard import check_posture
from .models import load_availability, registry
from .runner import Engine
from .tasks import load_tasks

WEB = ROOT / "web/dist"


def create_app(engine: Engine | None = None) -> FastAPI:
    app = FastAPI(title="GEAP Harness Eval", version=__version__)
    eng = engine or Engine()
    app.state.engine = eng
    running: dict[str, asyncio.Task] = {}

    @app.get("/api/health")
    def health():
        return {"ok": True, "version": __version__}

    @app.get("/api/me")
    def me(request: Request):
        return whoami(request)

    @app.get("/api/preflight")
    def preflight():
        p = check_posture()
        av = load_availability()
        book = eng.book
        hs = []
        for name, variants in ADAPTERS.items():
            ad = get_adapter(name, variants[0])
            hs.append({"name": name, "version": ad.installed_version(), "installed": ad.installed_version() is not None,
                       "latest": None})
        return {"credentials": p.as_dict(),
                "models": {"ok": bool(av), "probed_at": (av or {}).get("probed_at"),
                           "availability": [{"model": k.split("@")[0], "location": k.split("@")[1], "status": v["status"],
                                             "thinking_levels": (av or {}).get("thinking", {}).get(k.split("@")[0], [])}
                                            for k, v in (av or {}).get("availability", {}).items()]},
                "pricing": book.summary() if book else {"ok": False, "issues": ["no price book; run `geap-eval prices sync`"]},
                "harnesses": hs}

    @app.get("/api/models")
    def models():
        return registry(load_availability(), eng.book)

    @app.get("/api/harnesses")
    def harnesses():
        lock = eng.store.one("SELECT lock_json FROM runs ORDER BY created_at DESC LIMIT 1")
        latest_locked = (json.loads(lock["lock_json"]) if lock and lock["lock_json"] else {}).get("harnesses", {})
        out = []
        for name, variants in ADAPTERS.items():
            for v in variants:
                ad = get_adapter(name, v)
                inst = ad.installed_version()
                out.append({"name": name, "variant": v, "version": inst, "installed": inst,
                            "latest": latest_locked.get(f"{name}/{v}") or latest_locked.get(f"{name}/default") or inst,
                            "capabilities": ad.capabilities()})
        return out

    @app.get("/api/tasks")
    def tasks():
        return [t.as_dict() for t in load_tasks()]

    @app.get("/api/tasks/{task_id:path}")
    def task_detail(task_id: str):
        """Public-safe task view: ticket + seed-repo file list + hidden-test COUNTS. Never tests/ or solution/ content."""
        t = next((x for x in load_tasks() if x.id == task_id), None)
        if t is None:
            raise HTTPException(404, "unknown task")
        files = sorted(p.relative_to(t.path / "repo").as_posix() for p in (t.path / "repo").rglob("*")
                       if p.is_file() and "__pycache__" not in p.parts)
        counts = eng.store.one("SELECT f2p_total, p2p_total FROM attempts a JOIN trials tr ON a.trial_id=tr.id "
                               "WHERE tr.task_id=? AND a.f2p_total IS NOT NULL ORDER BY a.t_verified DESC LIMIT 1", task_id)
        stats = eng.store.one("SELECT COUNT(*) n, SUM(CASE WHEN status='passed' THEN 1 ELSE 0 END) passed FROM trials "
                              "WHERE task_id=? AND status IN ('passed','failed')", task_id)
        return {**t.as_dict(), "instruction_md": t.instruction, "repo_files": files[:500], "repo_file_count": len(files),
                "hidden_tests": {"fail_to_pass": counts["f2p_total"], "pass_to_pass": counts["p2p_total"]} if counts else None,
                "history": stats}

    @app.get("/api/runs")
    def runs():
        rows = eng.store.q("SELECT id, name, status, config_hash, created_at, started_at, finished_at FROM runs ORDER BY created_at DESC")
        for r in rows:
            c = eng.store.q("SELECT status, COUNT(*) n FROM trials WHERE run_id=? GROUP BY status", r["id"])
            r["counts"] = {x["status"]: x["n"] for x in c}
            r["spend_usd"] = eng.store.one("SELECT COALESCE(SUM(c.cost_usd),0) s FROM llm_calls c JOIN attempts a "
                                           "ON c.attempt_id=a.id WHERE a.run_id=?", r["id"])["s"]
        return rows

    @app.post("/api/admin/runs")
    async def create_run_admin(req: Request, dry_run: int = 0):
        require_admin(req)
        return await _create_run(req, dry_run)

    @app.post("/api/runs")
    async def create_run(req: Request, dry_run: int = 0):
        if not dry_run:
            require_admin(req)  # public read-only: launching needs /api/admin (IAP)
        return await _create_run(req, dry_run)

    async def _create_run(req: Request, dry_run: int):  # internal: callers have already authorised
        body = await req.json()
        try:
            cfg = RunConfig.model_validate(body)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, str(e))
        if dry_run:
            plan = eng.plan(cfg, install=False)
            return {"matrix": [{"task": m["task_id"], "harness": f"{m['harness']}/{m['variant']}", "profile": m["profile_id"],
                                "repeat": m["repeat_idx"], "status": "ok" if m["status"] == "queued" else "na",
                                "reason": m["na_reason"]} for m in plan["matrix"]],
                    "estimate": eng.estimate(plan["matrix"]), "lock": plan["lock"]}
        run_id = await asyncio.to_thread(eng.create_run, cfg)
        if run_id not in running or running[run_id].done():
            running[run_id] = asyncio.create_task(eng.execute(run_id))
        return {"run_id": run_id}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        r = eng.store.one("SELECT * FROM runs WHERE id=?", run_id)
        if not r:
            raise HTTPException(404)
        r["config"] = json.loads(r.pop("config_json"))
        r["lock"] = json.loads(r.pop("lock_json") or "{}")
        c = eng.store.q("SELECT status, COUNT(*) n FROM trials WHERE run_id=? GROUP BY status", run_id)
        r["counts"] = {x["status"]: x["n"] for x in c}
        live = eng.store.one("SELECT COALESCE(SUM(c.cost_usd),0) s, COALESCE(SUM(COALESCE(c.cost_effective_usd, c.cost_usd)),0) e "
                             "FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=?", run_id)
        r["spend_usd"], r["spend_effective_usd"] = live["s"], live["e"]  # live: per model call, not per finished attempt
        r["governor"] = eng.gov.snapshot()
        r["burn_usd_per_min"] = eng.store.one(
            "SELECT COALESCE(SUM(c.cost_usd),0)/10.0 s FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id "
            "WHERE a.run_id=? AND c.t_end > ?", run_id, __import__("time").time() - 600)["s"]
        return r

    @app.post("/api/admin/runs/{run_id}/{action}")
    async def control_admin(run_id: str, action: str, request: Request):
        require_admin(request)
        return await _control(run_id, action)

    @app.post("/api/runs/{run_id}/{action}")
    async def control(run_id: str, action: str, request: Request):
        require_admin(request)
        return await _control(run_id, action)

    async def _control(run_id: str, action: str):  # internal: callers have already authorised
        if action == "pause":
            eng.control[run_id] = "paused"
        elif action == "cancel":
            eng.control[run_id] = "cancelled"
        elif action == "resume":
            if run_id not in running or running[run_id].done():
                running[run_id] = asyncio.create_task(eng.execute(run_id))
        else:
            raise HTTPException(400, "unknown action")
        return {"ok": True}

    @app.get("/api/runs/{run_id}/log")
    def run_log(run_id: str, limit: int = 500):
        """Persisted scheduler log lines (started / passed on attempt N / failed / infra backoff), oldest first."""
        rows = eng.store.q("SELECT ts, data FROM events WHERE run_id=? AND type='log' ORDER BY id DESC LIMIT ?", run_id, limit)
        return [{"ts": r["ts"], **json.loads(r["data"])} for r in reversed(rows)]

    @app.get("/api/runs/{run_id}/infra")
    def infra(run_id: str):
        """Persisted rate-governor history for a run: model-call 429/503s (from the Meter) + backoff/AIMD/breaker events."""
        calls = eng.store.q("SELECT c.t_end ts, c.model, c.location, c.http_status, c.error_kind, c.role FROM llm_calls c "
                            "JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=? AND (c.error_kind LIKE 'quota%' "
                            "OR c.error_kind='overloaded') ORDER BY c.t_end", run_id)
        out = [{"ts": c["ts"], "kind": "429" if c["http_status"] == 429 else str(c["http_status"]), "model": c["model"],
                "location": c["location"], "detail": c["error_kind"], "aux": c["role"] == "aux"} for c in calls]
        run = eng.store.one("SELECT started_at, finished_at FROM runs WHERE id=?", run_id) or {}
        for e in eng.store.q("SELECT ts, data FROM events WHERE type='infra' AND (run_id=? OR (run_id IS NULL AND ts BETWEEN ? AND ?)) "
                             "ORDER BY ts", run_id, run.get("started_at") or 0, run.get("finished_at") or 1e12):
            d = json.loads(e["data"])
            if d.get("kind") == "429":
                continue  # already represented by the Meter call record
            out.append({"ts": e["ts"], **{k: d.get(k) for k in ("kind", "model", "location", "detail", "attempt_id")}})
        return sorted(out, key=lambda x: x["ts"] or 0)

    @app.get("/api/runs/{run_id}/egress")
    def egress(run_id: str):
        """Meter egress decisions for the whole run: per host, forwarded vs denied."""
        return eng.store.q("SELECT json_extract(data,'$.host') host, json_extract(data,'$.action') action, COUNT(*) n "
                           "FROM events WHERE run_id=? AND type='egress' GROUP BY 1,2 ORDER BY n DESC", run_id)

    @app.get("/api/runs/{run_id}/trials")
    def trials(run_id: str):
        return eng.store.q("SELECT * FROM trials WHERE run_id=? ORDER BY task_id, harness, profile_id, repeat_idx", run_id)

    @app.get("/api/runs/{run_id}/summary")
    def summary(run_id: str, k: int | None = None):
        return analytics.summarize(eng.store, run_id, k)

    @app.get("/api/trials/{trial_id}")
    def trial(trial_id: str):
        t = eng.store.one("SELECT * FROM trials WHERE id=?", trial_id)
        if not t:
            raise HTTPException(404)
        t["attempts"] = eng.store.q("SELECT * FROM attempts WHERE trial_id=? ORDER BY idx", trial_id)
        return t

    @app.get("/api/attempts/{aid}")
    def attempt(aid: str):
        a = eng.store.one("SELECT * FROM attempts WHERE id=?", aid)
        if not a:
            raise HTTPException(404)
        a["llm_calls"] = eng.store.q("SELECT * FROM llm_calls WHERE attempt_id=? ORDER BY t_start", aid)
        a["tool_calls"] = eng.store.q("SELECT * FROM tool_calls WHERE attempt_id=? ORDER BY COALESCE(t_start, t_end)", aid)
        a["events"] = eng.store.q("SELECT * FROM events WHERE attempt_id=? ORDER BY id", aid)
        d = Path(a["artifacts_dir"] or "")
        vj = ensure_local(d / "verifier.json")
        a["verifier"] = json.loads(vj.read_text()) if vj.exists() else None
        return a

    @app.get("/api/attempts/{aid}/cast")
    def cast(aid: str):
        a = eng.store.one("SELECT artifacts_dir FROM attempts WHERE id=?", aid)
        p = ensure_local(Path(a["artifacts_dir"]) / "session.cast") if a else None
        if not p or not p.exists():
            raise HTTPException(404)
        return PlainTextResponse(p.read_text())

    @app.get("/api/attempts/{aid}/diff")
    def diff(aid: str):
        a = eng.store.one("SELECT artifacts_dir FROM attempts WHERE id=?", aid)
        p = ensure_local(Path(a["artifacts_dir"]) / "diff.patch") if a else None
        return PlainTextResponse(p.read_text() if p and p.exists() else "")

    @app.get("/api/pricing")
    def get_pricing():
        b = pricing.load_price_book()
        return b.summary() if b else {"ok": False, "issues": ["no price book"], "models": []}

    @app.get("/api/governor")
    def governor():
        return eng.gov.snapshot()

    @app.get("/api/stream")
    async def stream(request: Request, run_id: str | None = None):
        q, key = BUS.subscribe(run_id)

        async def gen():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        ev, data = await asyncio.wait_for(q.get(), timeout=15)
                        yield {"event": ev, "data": data}
                    except asyncio.TimeoutError:
                        yield {"event": "ping", "data": "{}"}
            finally:
                BUS.unsubscribe(key)

        return EventSourceResponse(gen())

    @app.websocket("/api/attempts/{aid}/pty")
    async def pty_ws(ws: WebSocket, aid: str):
        await ws.accept()
        sess = BUS.ptys.get(aid)
        if sess is None:
            a = eng.store.one("SELECT artifacts_dir FROM attempts WHERE id=?", aid)
            p = ensure_local(Path(a["artifacts_dir"]) / "session.cast") if a else None
            if p and p.exists():  # replay finished session instantly
                for line in p.read_text().splitlines()[1:]:
                    try:
                        await ws.send_bytes(json.loads(line)[2].encode())
                    except Exception:  # noqa: BLE001
                        break
            await ws.close()
            return
        # send current screen state first, then live bytes
        try:
            if hasattr(sess, "cast_path") and sess.cast_path.exists():
                for line in sess.cast_path.read_text().splitlines()[1:]:
                    try:
                        await ws.send_bytes(json.loads(line)[2].encode())
                    except ValueError:
                        continue
            q = sess.subscribe()
            while True:
                data = await q.get()
                if not data:
                    break
                await ws.send_bytes(data)
        except WebSocketDisconnect:
            pass
        finally:
            try:
                sess.unsubscribe(q)
            except Exception:  # noqa: BLE001
                pass

    if WEB.exists():
        app.mount("/assets", StaticFiles(directory=WEB / "assets"), name="assets")

        @app.get("/{full:path}")
        def spa(full: str):
            if full.startswith("api/"):
                raise HTTPException(404, f"no such endpoint: /{full}")
            if full == "admin" or full.startswith("admin/"):
                full = full[6:]  # the same SPA, served under the IAP-protected prefix
            f = WEB / full
            if full and f.is_file():
                return FileResponse(f)
            return FileResponse(WEB / "index.html")
    else:
        @app.get("/")
        def no_ui():
            return JSONResponse({"msg": "dashboard not built: pnpm -C web build"})

    return app
