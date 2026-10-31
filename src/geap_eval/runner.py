"""Run engine: matrix expansion, idempotent scheduling, interactive attempt lifecycle, retries, metrics."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import shutil
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import pricing
from .adapters import get_adapter
from .adapters.base import AttemptContext, ResolvedRole
from .bus import BUS
from .config import PROJECT, RUNS_DIR, WORK_ROOT, ModelProfile, RoleSpec, RunConfig
from .governor import Governor, backoff_delay
from .guard import check_posture, make_isolated_home, scan_secrets
from .meter import Meter
from .models import MODELS, load_availability, pick_location
from .pty_driver import PtySession
from .store import Store
from .tasks import Task, diff_stats, prepare_workspace, select_tasks, verify

TERMINAL_TRIAL = {"passed", "failed", "infra_failed", "invalid_routing", "na", "error"}
COUNTED_ATTEMPT = {"passed", "failed", "error"}
STATUS_RANK = {"verified": 0, "pt": 0, "check": 1, "unpriced": 2}


def run_id_for(cfg: RunConfig) -> str:
    return f"{cfg.run.name}-{cfg.hash()[:8]}"


def sha(*parts: str, n: int = 16) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:n]


def expand_profiles(profiles: list[ModelProfile], avail: dict | None) -> list[ModelProfile]:
    out = []
    for p in profiles:
        if p.sweep is None:
            out.append(p)
            continue
        levels = p.sweep.thinking
        if levels == "all_valid":
            levels = (avail or {}).get("thinking", {}).get(p.sweep.model, [])
        for lv in levels:
            out.append(ModelProfile(id=f"{p.id}:{lv}", mode="single", roles={"default": RoleSpec(model=p.sweep.model, thinking=lv)}))
    return out


def resolve_roles(p: ModelProfile, avail: dict | None, preferred: str) -> tuple[dict[str, ResolvedRole], str | None]:
    specs = dict(p.roles)
    if p.mode == "pipeline":
        specs = {s["role"]: RoleSpec(model=s["model"], thinking=s.get("thinking", "medium")) for s in p.stages}
    out = {}
    for role, rs in specs.items():
        if rs.model not in MODELS:
            return {}, f"unknown model {rs.model}"
        if avail is None:
            return {}, "no availability probe (run `geap-eval preflight`)"
        loc = pick_location(rs.model, avail, preferred)
        if not loc:
            return {}, f"{rs.model} not available on {PROJECT} ({'any location' if preferred == 'auto' else preferred})"
        levels = avail.get("thinking", {}).get(rs.model, [])
        if rs.thinking not in levels:
            return {}, f"{rs.model} does not accept thinking={rs.thinking} (valid: {levels})"
        out[role] = ResolvedRole(rs.model, rs.thinking, loc, MODELS[rs.model]["provider"])
    return out, None


@dataclass
class Live:
    session: object | None = None
    spec: object | None = None
    token: str | None = None
    ctx: object | None = None


class Engine:
    def __init__(self, store: Store | None = None):
        self.store = store or Store()
        self.gov = Governor(on_event=lambda d: self.store.event("infra", d, run_id=d.get("run_id")))
        self.book = pricing.load_price_book()
        self.promos = pricing.load_promotions()
        self.avail = load_availability()
        self.meter: Meter | None = None
        self.attempt_calls: dict[str, list[dict]] = {}
        self.attempt_meter_tools: dict[str, list[dict]] = {}
        self.attempt_cost: dict[str, Decimal] = {}
        self.run_spend: dict[str, Decimal] = {}
        self.attempt_run: dict[str, str] = {}
        self.attempt_roles: dict[str, dict[str, ResolvedRole]] = {}
        self.attempt_aux: dict[str, object] = {}
        self.control: dict[str, str] = {}  # run_id -> running|paused|cancelled
        self._bg: list[asyncio.Task] = []

    # ---------------------------------------------------------- meter sink
    async def _sink(self, kind: str, rec: dict) -> None:
        aid = rec.get("attempt_id")
        run_id = self.attempt_run.get(aid)
        if kind == "tool_call":
            self.attempt_meter_tools.setdefault(aid, []).append(rec)
            return
        if kind == "egress":
            self.store.event("egress", rec, run_id=run_id, attempt_id=aid)
            return
        roles = self.attempt_roles.get(aid, {})
        names = [r for r, rr in roles.items() if rr.model == rec.get("model")]
        rec["role"] = ",".join(names) if names else None
        aux = self.attempt_aux.get(aid)
        if rec.get("provider") and (not names or (aux and aux(rec))):
            rec["role"] = "aux"  # harness-internal (titles, availability probes, other models): billed, not timed
        if rec.get("http_status", 0) < 400 and rec.get("provider"):
            c = pricing.cost_call(rec, self.book)
            rec["cost_usd"] = float(c.usd) if c.usd is not None else None
            rec["cost_status"] = c.status
            rec["cost_breakdown"] = c.breakdown
            eff, used = pricing.effective_cost(rec, c, self.promos)
            rec["cost_effective_usd"] = float(eff) if eff is not None else None
            rec["promotions"] = ",".join(used) or None
            if c.usd is not None:
                self.attempt_cost[aid] = self.attempt_cost.get(aid, Decimal(0)) + c.usd
                self.run_spend[run_id] = self.run_spend.get(run_id, Decimal(0)) + c.usd
        elif rec.get("error_kind") and rec.get("model") and rec.get("role") != "aux":
            self.gov.on_llm_error(rec["model"], rec.get("location") or "global", rec["error_kind"])
        self.attempt_calls.setdefault(aid, []).append(rec)
        row = {k: v for k, v in rec.items() if not k.startswith("_")}
        self.store.insert("llm_calls", row)
        BUS.publish("llm_call", {k: v for k, v in row.items() if k not in ("usage_raw", "cost_breakdown", "text_tail")}, run_id)

    async def ensure_meter(self) -> Meter:
        if self.meter is None:
            self.meter = Meter(self._sink)
            await self.meter.start()
            await self.meter.start_mitm(WORK_ROOT / ".meter-ca")
            self._bg.append(asyncio.create_task(self.gov.recover_loop()))
        return self.meter

    # ---------------------------------------------------------- planning
    def plan(self, cfg: RunConfig, install: bool = True) -> dict:
        """Build (and persist unless dry) the trial matrix + lock. Idempotent on config hash."""
        tasks = select_tasks(cfg.tasks)
        profiles = expand_profiles(cfg.model_profiles, self.avail)
        run_id = run_id_for(cfg)  # trial ids are content hashes scoped to the run (idempotent resume, no cross-run collisions)
        lock = {"created_at": time.time(), "project": PROJECT, "harnesses": {}, "tasks": {},
                "price_book": self.book.snapshot_sha if self.book else None,
                "availability_probed_at": (self.avail or {}).get("probed_at")}
        for h in cfg.harnesses:
            ad = get_adapter(h.name, h.variant)
            v = ad.install_latest() if install else (ad.installed_version() or "uninstalled")
            lock["harnesses"][f"{h.name}/{h.variant}"] = v
        for t in tasks:
            lock["tasks"][t.id] = {"version": t.version, "hash": t.content_hash()}
        matrix = []
        for t in tasks:
            for h in cfg.harnesses:
                ad = get_adapter(h.name, h.variant)
                hv = lock["harnesses"][f"{h.name}/{h.variant}"]
                for p in profiles:
                    roles, reason = resolve_roles(p, self.avail, cfg.geap.location)
                    if not reason:
                        reason = ad.supports(p, roles)
                    pj = p.model_dump_json()
                    for r in range(cfg.run.repeats):
                        tid = sha(run_id, t.id, t.version, lock["tasks"][t.id]["hash"], h.name, hv, h.variant, pj, str(r), PROJECT)
                        matrix.append({"id": tid, "task_id": t.id, "task_version": t.version, "tier": t.tier,
                                       "industry": t.industry, "sdlc_type": t.sdlc_type, "harness": h.name,
                                       "harness_version": hv, "variant": h.variant, "profile_id": p.id,
                                       "profile_json": pj, "repeat_idx": r,
                                       "status": "na" if reason else "queued", "na_reason": reason,
                                       "roles": {k: v.__dict__ for k, v in roles.items()}})
        return {"lock": lock, "matrix": matrix, "tasks": tasks}

    def estimate(self, matrix: list[dict]) -> dict:
        rows = self.store.q("SELECT t.task_id, t.harness, t.profile_id, a.cost_usd, a.wall_s FROM attempts a JOIN trials t ON a.trial_id=t.id WHERE a.cost_usd IS NOT NULL")
        hist: dict[tuple, list] = {}
        for r in rows:
            hist.setdefault((r["task_id"], r["harness"], r["profile_id"]), []).append((r["cost_usd"], r["wall_s"] or 0))
        cost = known = 0.0
        for m in matrix:
            if m["status"] != "queued":
                continue
            h = hist.get((m["task_id"], m["harness"], m["profile_id"]))
            if h:
                known += 1
                cost += sorted(x[0] for x in h)[len(h) // 2]
        n = sum(1 for m in matrix if m["status"] == "queued")
        return {"trials": n, "with_history": int(known), "cost_usd_estimate": round(cost, 4) if known else None,
                "note": "median of past attempts for identical task×harness×profile; others unknown"}

    def create_run(self, cfg: RunConfig, force_new: bool = False) -> str:
        run_id = run_id_for(cfg)
        existing = self.store.one("SELECT * FROM runs WHERE id=?", run_id)
        if existing and not force_new:
            return run_id  # idempotent: resume uses its lock
        plan = self.plan(cfg, install=True)
        self.store.upsert("runs", {"id": run_id, "name": cfg.run.name, "status": "queued",
                                   "config_json": cfg.model_dump(mode="json", by_alias=True),
                                   "config_hash": cfg.hash(), "lock_json": plan["lock"], "created_at": time.time()})
        for m in plan["matrix"]:
            if not self.store.one("SELECT id FROM trials WHERE id=?", m["id"]):
                row = {k: v for k, v in m.items() if k != "roles"}
                row.update(run_id=run_id, updated_at=time.time())
                self.store.upsert("trials", row)
        (RUNS_DIR / run_id).mkdir(parents=True, exist_ok=True)
        (RUNS_DIR / run_id / "lock.json").write_text(json.dumps(plan["lock"], indent=1))
        from .artifacts import upload_file
        upload_file(RUNS_DIR / run_id / "lock.json")
        return run_id

    # ---------------------------------------------------------- execution
    async def execute(self, run_id: str) -> None:
        run = self.store.one("SELECT * FROM runs WHERE id=?", run_id)
        cfg = RunConfig.model_validate(json.loads(run["config_json"]))
        posture = check_posture()
        if not posture.ok:
            self.store.update("runs", run_id, status="failed")
            self._log(f"credential posture failed: {posture.issues}", "error", run_id)
            raise RuntimeError(f"credential posture failed: {posture.issues}")
        await self.ensure_meter()
        # resume hygiene: orphaned running attempts -> interrupted (not counted)
        for a in self.store.q("SELECT id FROM attempts WHERE run_id=? AND status IN ('queued','admitted','preparing','running','verifying','backoff')", run_id):
            self.store.update("attempts", a["id"], status="interrupted", exit_class="interrupted", updated_at=time.time())
        self.control[run_id] = "running"
        self.store.update("runs", run_id, status="running", started_at=run["started_at"] or time.time())
        spent = self.store.one("SELECT COALESCE(SUM(c.cost_usd),0) s FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=?", run_id)["s"]
        self.run_spend[run_id] = Decimal(str(spent))
        trials = self.store.q("SELECT * FROM trials WHERE run_id=? AND status NOT IN ('passed','failed','infra_failed','invalid_routing','na','error') ORDER BY task_id, harness, profile_id, repeat_idx", run_id)
        gsem = asyncio.Semaphore(cfg.concurrency.global_)
        hsem: dict[str, asyncio.Semaphore] = {}
        self._publish_run(run_id)

        async def one(tr):
            hs = hsem.setdefault(tr["harness"], asyncio.Semaphore(cfg.concurrency.per_harness))
            async with gsem, hs:
                if self.control.get(run_id) == "cancelled":
                    return
                await self.run_trial(run_id, cfg, tr)
                self._publish_run(run_id)

        async def heartbeat():
            while True:
                await asyncio.sleep(5)
                self._publish_run(run_id)

        hb = asyncio.create_task(heartbeat())
        try:
            await asyncio.gather(*[one(t) for t in trials], return_exceptions=False)
        finally:
            hb.cancel()
        st = self.control.get(run_id)
        final = "cancelled" if st == "cancelled" else ("paused" if st == "paused" else "completed")
        self.store.update("runs", run_id, status=final, finished_at=time.time() if final == "completed" else None)
        self._publish_run(run_id)

    def _publish_run(self, run_id: str) -> None:
        r = self.store.one("SELECT status FROM runs WHERE id=?", run_id)
        c = {x["status"]: x["n"] for x in self.store.q("SELECT status, COUNT(*) n FROM trials WHERE run_id=? GROUP BY status", run_id)}
        total = sum(c.values())
        done = sum(v for k, v in c.items() if k in TERMINAL_TRIAL)
        spend = float(self.run_spend.get(run_id, 0))
        eff = self.store.one("SELECT COALESCE(SUM(COALESCE(c.cost_effective_usd, c.cost_usd)),0) e FROM llm_calls c "
                             "JOIN attempts a ON c.attempt_id=a.id WHERE a.run_id=?", run_id)["e"]
        recent = self.store.one("SELECT COALESCE(SUM(c.cost_usd),0) s FROM llm_calls c JOIN attempts a ON c.attempt_id=a.id "
                                "WHERE a.run_id=? AND c.t_end > ?", run_id, time.time() - 600)["s"]
        BUS.publish("run", {"run_id": run_id, "status": r["status"] if r else None, "burn_usd_per_min": recent / 10.0,
                            "progress": {"total": total, "done": done, "running": c.get("running", 0),
                                         "passed": c.get("passed", 0), "failed": c.get("failed", 0) + c.get("infra_failed", 0),
                                         "na": c.get("na", 0)},
                            "spend_usd": spend, "spend_effective_usd": eff}, run_id)

    def _budget_block(self, run_id: str, cfg: RunConfig) -> str | None:
        b = cfg.budget
        if not b.enabled or b.max_usd_total is None:
            return None
        spent = float(self.run_spend.get(run_id, 0))
        pct = spent / b.max_usd_total * 100 if b.max_usd_total else 0
        if pct >= 80:
            BUS.publish("budget", {"spent_usd": spent, "cap_usd": b.max_usd_total, "pct": pct,
                                   "action": b.on_exceed if pct >= 100 else "warn"}, run_id)
        if spent >= b.max_usd_total:
            self.control[run_id] = "paused" if b.on_exceed == "pause" else "cancelled"
            return b.on_exceed
        return None

    async def run_trial(self, run_id: str, cfg: RunConfig, tr: dict) -> None:
        tasks = {t.id: t for t in select_tasks(cfg.tasks)}
        task = tasks.get(tr["task_id"])
        if not task:
            self.store.update("trials", tr["id"], status="error", na_reason="task missing")
            return
        ad = get_adapter(tr["harness"], tr["variant"])
        profile = ModelProfile.model_validate_json(tr["profile_json"])
        roles, reason = resolve_roles(profile, self.avail, cfg.geap.location)
        if reason:
            self.store.update("trials", tr["id"], status="na", na_reason=reason)
            return
        prev = self.store.q("SELECT * FROM attempts WHERE trial_id=? ORDER BY idx", tr["id"])
        counted = [a for a in prev if a["status"] in COUNTED_ATTEMPT]
        infra_n = tr["infra_retries"] or 0
        idx = (max((a["idx"] for a in prev), default=0)) + 1
        max_attempts = 1 + cfg.run.max_task_retries
        live = Live()
        backoff_total = 0.0
        last_ver: dict | None = None
        self.store.update("trials", tr["id"], status="running", updated_at=time.time())
        self._log(f"{tr['task_id']} · {tr['harness']}/{tr['variant']} · {tr['profile_id']} → started", "info", run_id)
        BUS.publish("trial", self.store.one("SELECT * FROM trials WHERE id=?", tr["id"]), run_id)
        try:
            while len(counted) < max_attempts:
                if self.control.get(run_id) in ("paused", "cancelled"):
                    self.store.update("trials", tr["id"], status="queued")
                    return
                blocked = self._budget_block(run_id, cfg)
                if blocked:
                    self._log(f"budget cap reached -> {blocked}", "warn", run_id)
                    self.store.update("trials", tr["id"], status="queued")
                    return
                feedback = cfg.run.retry_mode == "feedback" and counted and last_ver is not None and live.session is not None
                a = await self.run_attempt(run_id, cfg, tr, task, ad, profile, roles, idx, live, feedback, last_ver)
                idx += 1
                if a["status"] == "engine_error":
                    self.store.update("trials", tr["id"], status="error", na_reason=(a.get("error") or "")[:300])
                    return
                if a["status"] == "invalid_routing":
                    self.store.update("trials", tr["id"], status="invalid_routing", attempts_used=len(counted))
                    return
                if a["exit_class"] in ("infra_quota", "infra_auth", "crash_boot"):
                    infra_n += 1
                    self.store.update("trials", tr["id"], infra_retries=infra_n)
                    await live_close(live, ad)
                    if infra_n > cfg.run.max_infra_retries:
                        self.store.update("trials", tr["id"], status="infra_failed", attempts_used=len(counted))
                        return
                    d = backoff_delay(infra_n)
                    backoff_total += d
                    self.store.update("attempts", a["id"], status="backoff")
                    payload = {"kind": "backoff", "model": next(iter(roles.values())).model,
                               "location": next(iter(roles.values())).location, "run_id": run_id,
                               "detail": f"{d:.1f}s (infra retry {infra_n})", "attempt_id": a["id"]}
                    BUS.publish("infra", payload, run_id)
                    self.store.event("infra", payload, run_id=run_id, trial_id=tr["id"], attempt_id=a["id"])
                    self._log(f"{tr['task_id']} · {tr['harness']} · infra {a['exit_class']} — backing off {d:.0f}s "
                            f"(infra retry {infra_n}, task retries untouched)", "warn", run_id)
                    await asyncio.sleep(d)
                    self.store.update("attempts", a["id"], status="error")  # backoff finished: final state, not counted
                    continue
                counted.append(a)
                last_ver = a.get("_verifier")
                if a["status"] == "passed":
                    first = self.store.one("SELECT MIN(t0) t FROM attempts WHERE trial_id=? AND status IN ('passed','failed','error')", tr["id"])["t"]
                    tts = (a["t_verified"] - (first or a["t0"])) - backoff_total
                    self._finish_trial(tr["id"], "passed", len(counted), len(counted), tts)
                    return
                if cfg.run.retry_mode == "fresh":
                    await live_close(live, ad)
            self._finish_trial(tr["id"], "failed", len(counted), None, None)
        finally:
            await live_close(live, ad)
            BUS.publish("trial", self.store.one("SELECT * FROM trials WHERE id=?", tr["id"]), run_id)

    def _finish_trial(self, trial_id: str, status: str, used: int, passed_on: int | None, tts: float | None) -> None:
        t = self.store.one("SELECT run_id, task_id, harness, variant, profile_id FROM trials WHERE id=?", trial_id)
        if t:
            msg = f"passed on attempt {passed_on}" if status == "passed" else f"{status} after {used} attempt(s)"
            self._log(f"{t['task_id']} · {t['harness']}/{t['variant']} · {t['profile_id']} → {msg}",
                    "info" if status == "passed" else "warn", t["run_id"])
        agg = self.store.one("SELECT SUM(cost_usd) c, SUM(cost_effective_usd) e, MAX(CASE cost_status WHEN 'unpriced' THEN 2 WHEN 'check' THEN 1 ELSE 0 END) s FROM attempts WHERE trial_id=?", trial_id)
        cs = {0: "verified", 1: "check", 2: "unpriced"}.get(agg["s"] or 0)
        self.store.update("trials", trial_id, status=status, attempts_used=used, passed_on_attempt=passed_on,
                          time_to_success_s=tts, cost_usd=agg["c"], cost_effective_usd=agg["e"], cost_status=cs,
                          updated_at=time.time())

    # ---------------------------------------------------------- attempt
    async def run_attempt(self, run_id, cfg, tr, task: Task, ad, profile, roles, idx, live: Live, feedback: bool, last_ver):
        aid = f"{tr['id']}-a{idx}"
        adir = RUNS_DIR / run_id / tr["id"] / f"attempt-{idx}"
        adir.mkdir(parents=True, exist_ok=True)
        self.attempt_run[aid] = run_id
        self.attempt_roles[aid] = roles
        row = {"id": aid, "trial_id": tr["id"], "run_id": run_id, "idx": idx, "kind": "task", "status": "queued",
               "t_queued": time.time(), "artifacts_dir": str(adir), "prompt_submissions": 0, "nudges": 0, "dialogs": 0}
        self.store.upsert("attempts", row)
        self._pub_attempt(aid, run_id)
        lanes = sorted({(r.model, r.location) for r in roles.values()})
        await self.gov.acquire(lanes)
        infra_failure = False
        try:
            self.store.update("attempts", aid, status="preparing")
            if not feedback:
                work = WORK_ROOT / run_id / tr["id"] / f"attempt-{idx}"
                if work.exists():
                    shutil.rmtree(work)
                work.mkdir(parents=True)
                work = work.resolve()
                ws = prepare_workspace(task, work / "workspace")
                home = make_isolated_home(work / "home")
                token = secrets.token_hex(12)
                base = self.meter.register(token, aid)
                ctx = AttemptContext(aid, tr["id"], task, ws, home, adir, base, roles, profile, tr["variant"],
                                     task.instruction, workdir=work)
                ctx.meter_proxy = self.meter.proxy_url(token)
                ctx.meter_ca = self.meter.ca_pem
                spec = ad.prepare(ctx)
                self.attempt_aux[aid] = spec.aux_call
                leaks = scan_secrets(home)
                if leaks:
                    raise RuntimeError(f"secret scan failed: {leaks[:3]}")
                sess = ad.open_session(ctx, spec, adir / "session.cast") if hasattr(ad, "open_session") else \
                    PtySession(spec.argv, spec.cwd, spec.env, adir / "session.cast", dialogs=spec.dialogs)
                sess.on_dialog = lambda name: self._dialog(aid, run_id, name)
                await sess.start()
                BUS.ptys[aid] = sess
                live.session, live.spec, live.token, live.ctx = sess, spec, token, ctx
                ok = await sess.wait_for(spec.ready, spec.boot_timeout_s)
                if not ok:
                    raise BootError(f"ready signature not seen in {spec.boot_timeout_s}s; screen tail: {sess.text()[-600:]}")
                await sess.wait_stable(1.5, 15)
            else:
                # continue same session: re-point meter attribution to this attempt
                self.meter.tokens[live.token].attempt_id = aid
                BUS.ptys[aid] = live.session
                ctx = live.ctx
                ctx.attempt_id = aid
            sess, spec = live.session, live.spec
            prompt = feedback_prompt(last_ver) if feedback else task.instruction
            self.store.update("attempts", aid, status="running")
            self._pub_attempt(aid, run_id)
            res = await self.agent_phase(run_id, cfg, aid, task, ad, ctx, sess, spec, live.token, prompt, profile)
            # plane A + verification
            plane_a = ad.collect(ctx)
            self.store.update("attempts", aid, status="verifying")
            self._pub_attempt(aid, run_id)
            if cfg.run.retry_mode == "fresh":
                await live_close(live, ad)
            ver = await verify(task, ctx.workspace, adir)
            self.store.event("verifier", {"fail_to_pass": {"passed": ver.get("f2p_passed"), "total": ver.get("f2p_total")},
                                          "pass_to_pass": {"passed": ver.get("p2p_passed"), "total": ver.get("p2p_total")},
                                          "failed": ver.get("failed", []), "log_tail": ver.get("log_tail", ""),
                                          "verify_s": ver.get("verify_s"), "ok": ver.get("ok"), "error": ver.get("error")},
                             run_id=run_id, trial_id=tr["id"], attempt_id=aid)
            ds = diff_stats(task.path / "repo", ctx.workspace)
            shutil.copytree(ctx.workspace, adir / "workspace-final", dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", "node_modules", "target", "__pycache__", "*.class", "build", "out"))
            (adir / "diff.patch").write_text(ds.pop("patch"))
            metrics = self.compute_metrics(aid, res, plane_a, roles)
            status = "passed" if ver.get("passed") else ("error" if not ver.get("ok") else "failed")
            exit_class = res["exit_class"]
            if exit_class == "invalid_routing":
                status = "invalid_routing"
            elif exit_class in ("infra_quota", "infra_auth") and not ver.get("passed"):
                status, infra_failure = "error", True
            upd = dict(metrics, status=status, exit_class=exit_class, t_verified=time.time(), verify_s=ver.get("verify_s"),
                       passed=bool(ver.get("passed")), f2p_passed=ver.get("f2p_passed"), f2p_total=ver.get("f2p_total"),
                       p2p_passed=ver.get("p2p_passed"), p2p_total=ver.get("p2p_total"), **ds, updated_at=time.time(),
                       error=ver.get("error") or res.get("error"))
            self.store.update("attempts", aid, **upd)
            a = self.store.one("SELECT * FROM attempts WHERE id=?", aid)
            a["_verifier"] = ver
            return a
        except BootError as e:
            infra_failure = True
            self.store.update("attempts", aid, status="error", exit_class="crash_boot", error=str(e)[:2000], updated_at=time.time())
            await live_close(live, ad)
            return self.store.one("SELECT * FROM attempts WHERE id=?", aid)
        except Exception as e:  # noqa: BLE001 - engine-side failure: not the agent's fault, don't burn its retries
            import traceback
            self.store.update("attempts", aid, status="engine_error", exit_class="engine_error",
                              error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-1500:]}"[:3000], updated_at=time.time())
            await live_close(live, ad)
            self._log(f"attempt {aid} crashed: {e}", "error", run_id)
            return self.store.one("SELECT * FROM attempts WHERE id=?", aid)
        finally:
            await self.gov.release(lanes, infra_failure=infra_failure)
            if live.session is None and live.token:
                self.meter.unregister(live.token)
            from .artifacts import bucket_name, upload_dir
            if bucket_name():
                asyncio.create_task(asyncio.to_thread(upload_dir, adir))  # persist off the event loop
            work = WORK_ROOT / run_id / tr["id"] / f"attempt-{idx}"
            if live.session is None and work.exists():
                shutil.rmtree(work, ignore_errors=True)  # removes the ADC copy; final workspace is archived above
            self._pub_attempt(aid, run_id)

    def _log(self, msg: str, level: str = "info", run_id: str | None = None) -> None:
        """Scheduler log line: persisted (history for late-joining dashboards) + live over SSE."""
        self.store.event("log", {"level": level, "msg": msg}, run_id=run_id)
        BUS.log(msg, level, run_id)

    def _dialog(self, aid, run_id, name):
        a = self.store.one("SELECT dialogs FROM attempts WHERE id=?", aid)
        self.store.update("attempts", aid, dialogs=(a["dialogs"] or 0) + 1)
        self.store.event("dialog_answered", {"dialog": name}, run_id=run_id, attempt_id=aid)

    def _pub_attempt(self, aid, run_id):
        a = self.store.one("SELECT a.*, t.harness, t.variant, t.profile_id, t.task_id FROM attempts a JOIN trials t ON a.trial_id=t.id WHERE a.id=?", aid)
        if a:
            BUS.publish("attempt", a, run_id)

    async def agent_phase(self, run_id, cfg, aid, task, ad, ctx, sess, spec, token, prompt, profile) -> dict:
        st = self.meter.state(token)
        q = cfg.limits.quiescence_s
        timeout = cfg.limits.attempt_timeout_s.get(task.tier, task.timeout_s)
        prompts = [prompt]
        if profile.mode == "pipeline":
            prompts = pipeline_prompts(prompt)
        def counter() -> int:
            return spec.done_counter() if spec.done_counter else count_lines(spec.marker)

        marker_lines = await asyncio.to_thread(counter)
        calls_at_start = st.calls_ok
        t0 = None
        submissions = nudges = 0
        exit_class, signal_used, err = "ok", None, None
        for stage_i, ptxt in enumerate(prompts):
            if profile.mode == "pipeline":
                role = profile.stages[stage_i]["role"]
                keys = ad.switch_model_keys(ctx, role)
                if keys:
                    for k in keys:
                        sess.write(k)
                        await asyncio.sleep(0.5)
                    await sess.wait_stable(1.5, 20)
            ts = await sess.submit(ptxt) if hasattr(sess, "submit") else await sess.paste(ptxt, bracketed=spec.bracketed_paste)
            if not hasattr(sess, "submit"):
                ts = await self._confirm_submit(run_id, aid, sess, spec, st, ts, counter)
            t0 = t0 or ts
            submissions += 1
            self.store.update("attempts", aid, t0=t0, prompt_submissions=submissions)
            self.store.event("prompt_submitted", {"stage": stage_i, "chars": len(ptxt)}, run_id=run_id, attempt_id=aid)
            deadline = t0 + timeout
            last_tick = 0.0
            last_check = 0.0
            done_ct = marker_lines
            while True:
                await asyncio.sleep(0.5)
                now = time.time()
                if now - last_tick >= 1.0:
                    last_tick = now
                    self._tick(run_id, aid, t0)
                per_cap = cfg.budget.max_usd_per_attempt if cfg.budget.enabled else None
                if per_cap and float(self.attempt_cost.get(aid, 0)) >= per_cap:
                    exit_class, err = "budget", f"per-attempt budget ${per_cap} reached"
                    break
                if self.control.get(run_id) == "cancelled":
                    exit_class, err = "agent_error", "run cancelled"
                    break
                if now > deadline:
                    exit_class, err = "timeout", f"attempt timeout {timeout}s"
                    break
                if not sess.alive:
                    exit_class, err = "crash", "harness process exited"
                    break
                if now - last_check >= (2.0 if spec.done_counter else 0.5):
                    last_check = now
                    done_ct = await asyncio.to_thread(counter)
                new_marker = done_ct > marker_lines
                quiet = st.inflight == 0 and now - max(st.last_end, ts) >= q and sess.idle_for() >= 2.0
                busy = bool(spec.busy and spec.busy.search(sess.text()))
                done = None
                if new_marker and st.inflight == 0 and sess.idle_for() >= 1.5 and not busy:
                    done = "hook"
                elif spec.plane_b and st.calls_ok > calls_at_start and quiet and st.last_done and not busy:
                    done = "meter"
                elif not spec.plane_b and quiet and now - ts > 5 and spec.ready.search(sess.text()) and not busy:
                    done = "screen"
                elif spec.plane_b and st.inflight == 0 and st.last_failed and any(c.get("role") != "aux" and c.get("http_status", 0) >= 400 for c in self.attempt_calls.get(aid, [])[-1:]) and now - st.last_end >= max(q, 45) and sess.idle_for() >= q:
                    last = ([c for c in self.attempt_calls.get(aid, []) if c.get("role") != "aux"] or [{}])[-1]
                    kind = last.get("error_kind") or ""
                    exit_class = "infra_quota" if kind.startswith(("quota", "overloaded")) else ("infra_auth" if kind == "auth" else "agent_error")
                    err = f"harness stalled after model error {kind}: {str(last.get('error'))[:300]}"
                    break
                if done:
                    if st.last_text.strip().endswith("?") and nudges < cfg.limits.max_nudges and stage_i == len(prompts) - 1:
                        nudges += 1
                        submissions += 1
                        marker_lines = done_ct = await asyncio.to_thread(counter)
                        await sess.submit(NUDGE) if hasattr(sess, "submit") else await sess.paste(NUDGE, bracketed=spec.bracketed_paste)
                        self.store.update("attempts", aid, nudges=nudges, prompt_submissions=submissions)
                        self.store.event("nudge", {"n": nudges, "after": st.last_text[-200:]}, run_id=run_id, attempt_id=aid)
                        continue
                    signal_used = done
                    marker_lines = done_ct
                    break
            if exit_class != "ok":
                break
        core = [c for c in self.attempt_calls.get(aid, []) if c.get("provider") and c.get("role") != "aux"]
        if exit_class == "ok" and core and core[-1].get("http_status", 0) >= 400:
            kind = core[-1].get("error_kind") or ""
            if kind.startswith(("quota", "overloaded")):  # turn ended on a provider quota error: infra, not the agent
                exit_class, err = "infra_quota", f"turn ended after model {kind} error: {str(core[-1].get('error'))[:300]}"
            elif kind == "auth":
                exit_class, err = "infra_auth", f"turn ended after auth error: {str(core[-1].get('error'))[:300]}"
        calls = [c for c in self.attempt_calls.get(aid, []) if c.get("http_status", 0) < 400 and c.get("provider")]
        if spec.aux_call:
            for c in calls:
                if spec.aux_call(c):
                    c["role"] = "aux"
                    self.store.db.execute("UPDATE llm_calls SET role='aux' WHERE attempt_id=? AND seq=?", (aid, c["seq"]))
        timed = [c for c in calls if c.get("role") != "aux"]
        t_end = max((c["t_end"] for c in timed), default=time.time())
        if spec.plane_b and not calls and exit_class == "ok":
            exit_class, err = "invalid_routing", "no model call reached GEAP through the Meter"
        self.store.update("attempts", aid, t_end=t_end, completion_signal=signal_used)
        return {"t0": t0, "t_end": t_end, "exit_class": exit_class, "signal": signal_used, "error": err,
                "nudges": nudges, "submissions": submissions}

    async def _confirm_submit(self, run_id, aid, sess, spec, st, ts, counter, tries: int = 3, wait_s: float = 8.0) -> float:
        """TUIs may swallow Enter while they digest a large paste (omp turns it into an attachment chip).
        Confirm the agent actually started (model call, busy marker or lifecycle event); else press Enter again."""
        calls0, ct0, text0 = st.seq, await asyncio.to_thread(counter), sess.text()
        for attempt in range(tries + 1):
            end = time.time() + wait_s
            while time.time() < end:
                await asyncio.sleep(0.5)
                if st.seq > calls0 or st.inflight > 0:
                    return ts
                if spec.busy and spec.busy.search(sess.text()):
                    return ts
                if await asyncio.to_thread(counter) != ct0:
                    return ts
            if attempt == tries:
                break
            ts = time.time()
            sess.write("\r")
            self.store.event("submit_retry", {"n": attempt + 1, "screen_changed": sess.text() != text0}, run_id=run_id, attempt_id=aid)
        self.store.event("submit_unconfirmed", {}, run_id=run_id, attempt_id=aid)
        return ts

    def _tick(self, run_id, aid, t0):
        calls = self.attempt_calls.get(aid, [])
        tok = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "thinking": 0}
        for c in calls:
            tok["input"] += c.get("tok_input") or 0
            tok["cache_read"] += c.get("tok_cache_read") or 0
            tok["cache_write"] += (c.get("tok_cache_write_5m") or 0) + (c.get("tok_cache_write_1h") or 0)
            tok["output"] += c.get("tok_output") or 0
            tok["thinking"] += c.get("tok_thinking") or 0
        mt = self.attempt_meter_tools.get(aid, [])
        BUS.publish("tick", {"attempt_id": aid, "elapsed_s": time.time() - t0, "tokens": tok,
                             "cost_usd": float(self.attempt_cost.get(aid, 0)),
                             "cost_status": worst_status([c.get("cost_status") for c in calls if c.get("cost_status")]),
                             "llm_calls": len(calls),
                             "tool": {"ok": sum(1 for t in mt if t["status"] == "ok"), "fail": sum(1 for t in mt if t["status"] == "error"), "retry": 0},
                             "state": "running"}, run_id)

    def compute_metrics(self, aid: str, res: dict, pa, roles: dict[str, ResolvedRole]) -> dict:
        calls = self.attempt_calls.get(aid, [])
        ok = [c for c in calls if c.get("http_status", 0) < 400 and c.get("provider")]
        t0, t_end = res["t0"] or time.time(), res["t_end"]
        llm_iv = sorted((max(c["t_start"], t0), min(c["t_end"], t_end)) for c in ok if c["t_end"] > t0 and c.get("role") != "aux")
        llm_s = union_len(llm_iv)
        # tools: Plane A preferred (native statuses), else Meter-derived
        tools = pa.tool_calls if pa.tool_calls else [dict(t, args_hash=None) for t in self.attempt_meter_tools.get(aid, [])]
        source = "native" if pa.tool_calls else "meter"
        mark_retries(tools)
        for t in tools:
            self.store.insert("tool_calls", dict(t, attempt_id=aid, source=t.get("source", source)))
        tool_iv = sorted((t["t_start"], t["t_end"]) for t in tools if t.get("t_start") and t.get("t_end"))
        if tool_iv:
            tool_s = union_len(tool_iv)
        else:  # gaps after model calls that emitted tool calls
            tool_s = 0.0
            for a, b in zip(ok, ok[1:]):
                if a.get("tool_calls_emitted"):
                    tool_s += max(0.0, b["t_start"] - a["t_end"])
        wall = max(0.0, t_end - t0)
        first = min(ok, key=lambda c: c["t_start"], default=None)
        tok = {k: sum(c.get(k) or 0 for c in ok) for k in ("tok_input", "tok_cache_read", "tok_cache_write_5m", "tok_cache_write_1h", "tok_output", "tok_thinking", "tok_tool_prompt")}
        statuses = [c.get("cost_status") or "unpriced" for c in ok]
        # no successful model call => nothing billable (non-200 responses are not charged): a known $0, not "unpriced"
        cost_status = worst_status(statuses) if ok else ("check" if (self.book is None or self.book.issues) else "verified")
        # Plane A vs B reconciliation
        if pa.usage:
            core = [c for c in ok if c.get("role") != "aux"]
            b_tok = {k: sum(c.get(k) or 0 for c in core) for k in ("tok_input", "tok_cache_read", "tok_output", "tok_thinking")}
            b_tok["tok_output_incl_thinking"] = b_tok["tok_output"] + b_tok["tok_thinking"]
            for k in ("tok_output", "tok_output_incl_thinking", "tok_input", "tok_cache_read"):
                a, b = pa.usage.get(k), b_tok.get(k)
                if a is not None and b and abs(a - b) / b > 0.02:
                    cost_status = worst_status([cost_status, "check"])
                    self.store.event("reconcile_mismatch", {"field": k, "plane_a": a, "plane_b": b}, attempt_id=aid)
        thinking = verify_thinking(ok, roles)
        return {**tok, "wall_s": wall, "llm_s": llm_s, "tool_s": min(tool_s, wall), "overhead_s": max(0.0, wall - llm_s - min(tool_s, wall)),
                "ttft_ms": ((first["t_first_byte"] or first["t_end"]) - first["t_start"]) * 1000 if first else None,
                "llm_turns": pa.llm_turns if pa.llm_turns is not None else len(ok), "llm_calls": len(calls),
                "llm_retries": sum(1 for c in calls if c.get("is_retry") and c.get("role") != "aux"),
                "llm_errors": sum(1 for c in calls if c.get("http_status", 0) >= 400 and c.get("role") != "aux"),
                "tool_calls": len(tools), "tool_ok": sum(1 for t in tools if t["status"] == "ok"),
                "tool_fail": sum(1 for t in tools if t["status"] == "error"), "tool_retry": sum(1 for t in tools if t.get("is_retry")),
                "subagents": pa.subagents, "cost_usd": float(sum((Decimal(str(c["cost_usd"])) for c in ok if c.get("cost_usd") is not None), Decimal(0))),
                "cost_effective_usd": float(sum((Decimal(str(c["cost_effective_usd"])) for c in ok if c.get("cost_effective_usd") is not None), Decimal(0))),
                "cost_status": cost_status, "thinking_verified": thinking,
                "nudges": res["nudges"], "prompt_submissions": res["submissions"]}


class BootError(RuntimeError):
    pass


NUDGE = "Proceed autonomously using your best judgment. Do not ask further questions; complete the task."


def feedback_prompt(ver: dict | None) -> str:
    failed = ", ".join((ver or {}).get("failed", [])[:15]) or "(unnamed)"
    tail = ((ver or {}).get("log_tail") or "")[-1500:]
    return ("The acceptance tests for this ticket failed. Failing tests: " + failed +
            "\n\nTest output (tail):\n" + tail + "\n\nPlease fix the implementation so all acceptance criteria pass.")


def pipeline_prompts(instruction: str) -> list[str]:
    return [
        "PLANNING STAGE. Read the ticket below and the repository, then write a concise implementation plan to PLAN.md. "
        "Do not modify any other file in this stage.\n\n" + instruction,
        "EXECUTION STAGE. Implement the plan in PLAN.md to complete the ticket. Run the existing tests. "
        "Delete PLAN.md when done.",
    ]


def count_lines(p: Path | None) -> int:
    if p is None or not p.exists():
        return 0
    return len(p.read_text().splitlines())


def union_len(iv: list[tuple[float, float]]) -> float:
    tot, cur_s, cur_e = 0.0, None, None
    for s, e in sorted(iv):
        if e <= s:
            continue
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                tot += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        tot += cur_e - cur_s
    return tot


def mark_retries(tools: list[dict]) -> None:
    """A retry = same tool name (+args hash when known) re-invoked within the next 3 calls after a failure."""
    for i, t in enumerate(tools):
        t.setdefault("is_retry", False)
        for j in range(max(0, i - 3), i):
            p = tools[j]
            same_args = p.get("args_hash") is None or t.get("args_hash") is None or p["args_hash"] == t["args_hash"]
            if p["status"] == "error" and p.get("name") == t.get("name") and same_args:
                t["is_retry"] = True
                break


def worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "unpriced"
    return max(statuses, key=lambda s: STATUS_RANK.get(s, 2))


def verify_thinking(calls: list[dict], roles: dict[str, ResolvedRole]) -> str:
    """Compare the thinking level each call actually requested with the configured level for that model."""
    want = {r.model: r.thinking for r in roles.values()}
    verdicts = set()
    for c in calls:
        w = want.get(c.get("model"))
        if w is None:
            continue
        tr = (c.get("thinking_requested") or "").lower()
        if c["provider"] == "google":
            if not tr:
                verdicts.add("absent")
            elif "thinkingbudget" in tr.replace("_", "") and "thinkinglevel" not in tr.replace("_", ""):
                verdicts.add("budget")  # harness expresses Gemini thinking as a token budget (e.g. agy Flash)
            else:
                verdicts.add("match" if w in tr else "mismatch")
        else:
            if w == "off":
                verdicts.add("match" if not tr or "disabled" in tr else "mismatch")
            elif not tr:
                verdicts.add("absent")
            elif w == "high" and "adaptive" in tr and "effort" not in tr:
                verdicts.add("match")  # adaptive thinking with API-default effort (= high)
            else:
                verdicts.add("match" if (f'"effort": "{w}"' in tr or (w in tr and "effort" in tr)) else ("partial" if "adaptive" in tr or "enabled" in tr else "mismatch"))
    if not verdicts:
        return "unknown"
    if verdicts == {"match"}:
        return "match"
    return "+".join(sorted(verdicts))


async def live_close(live: Live, ad) -> None:
    if live.session is not None:
        try:
            await live.session.close(quit_keys=getattr(live.spec, "quit_keys", None))
        except Exception:  # noqa: BLE001
            pass
        live.session = None
