"""DeepSeek Harness (vanilla) — Web app driven by Playwright; PTC (`tools.mode: ptc`) by default.

Recipe verified in docs/spikes/dsh.md (dsh 0.2.1-rc.5). Variants:
  web-ptc    : Web UI, tools.mode=ptc (benchmark default)
  web-native : Web UI, tools.mode=native (PTC-off control)
  acp-ptc    : ACP stdio fallback driver (not wired yet -> N/A)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

from ..config import PROJECT
from ..guard import base_env
from .base import Adapter, AttemptContext, LaunchSpec, PlaneA, ResolvedRole

MODEL_LABELS = {"gemini-3.8-flash": "Gemini 3.8 Flash", "gemini-4-argon": "Gemini 4 Argon"}
ALLOW_SCRIPTS = ["@deepseek-ai/dsh-subprocess-local", "koffi", "node-pty", "@google/genai", "protobufjs"]


def _patch(base_url: str, model: str, effort: str, workspace: Path, documents: Path, tools_mode: str, location: str) -> str:
    return f"""# geap-eval dsh attempt patch (vanilla dsh; Vertex via ADC; project {PROJECT})
- id: llm-pi-ai
  config:
    providers:
      google-vertex:
        displayName: GEAP ({PROJECT}, {location})
        baseURL: {base_url}
        reasoning: {effort}
        models:
          - id: gemini-3.8-flash
          - id: gemini-4-argon
- id: agent-default-model
  config:
    provider: google-vertex
    model: {model}
    reasoningEffort: {effort}
- id: tools
  config:
    mode: {tools_mode}
- id: sandbox-policy
  config:
    mode: workspace-write
    workspaceRoot: {workspace}
- id: approval
  config:
    policy: never
- id: permission
  config:
    presets:
      unattended:
        sandbox: workspace-write
        approval: never
        name: unattended
        description: workspace-write sandbox; approval prompts disabled (escalations auto-rejected)
      workspace-write:
        sandbox: workspace-write
        approval: ask
      danger-full-access:
        sandbox: danger-full-access
        approval: never
    defaultPreset: unattended
- id: workspace-controller
  config:
    documentsDirectory: {documents}
"""


def read_session(path: Path) -> list[dict]:
    """dsh sessions are multi-frame zstd JSONL: only the zstd CLI reads every frame."""
    raw = subprocess.run(["zstd", "-dcq", str(path)], capture_output=True).stdout if path.suffix == ".zstd" else path.read_bytes()
    rows = []
    for ln in raw.decode("utf-8", "replace").splitlines():
        try:
            rows.append(json.loads(ln))
        except ValueError:
            pass  # torn tail while dsh is writing
    return rows


def session_files(dsh_home: Path) -> list[Path]:
    return sorted((dsh_home / "sessions").glob("*/*/session.v*.jsonl*"))


def work_state(dsh_home: Path) -> dict:
    root, open_turns, open_jobs = None, [], set()
    for f in session_files(dsh_home):
        rows = read_session(f)
        if not rows:
            continue
        hdr = rows[0]
        ls = max((i for i, r in enumerate(rows) if r.get("type") == "turn/start"), default=-1)
        le = max((i for i, r in enumerate(rows) if r.get("type") == "turn/end"), default=-1)
        if ls > le:
            open_turns.append(hdr.get("id"))
        for r in rows:
            if r.get("type") == "job/registered":
                open_jobs.add(r["data"]["jobId"])
            elif r.get("type") == "job/settled":
                open_jobs.discard(r["data"]["jobId"])
        if hdr.get("delegationDepth", 0) == 0 and not hdr.get("parentSession"):
            ends = [r for r in rows if r.get("type") == "turn/end"]
            root = {"turns_ended": len(ends), "cwd": hdr.get("cwd")}
    return {"idle": bool(root and root["turns_ended"] and not open_turns and not open_jobs), "root": root}


class DshWebSession:
    """Session interface used by the runner (same surface as PtySession)."""

    def __init__(self, dsh_bin: Path, ctx: AttemptContext, env: dict, model: str, effort: str, out: Path):
        self.dsh_bin, self.ctx, self.env, self.model, self.effort, self.out = dsh_bin, ctx, env, model, effort, out
        self.proc: asyncio.subprocess.Process | None = None
        self.subscribers: set[asyncio.Queue] = set()
        self.on_dialog = None
        self.running = False
        self.idle_since = time.time()
        self.cast_path = out / "session.cast"  # not produced for web; replay is video + trace
        self._pw = self._browser = self._bctx = self.page = None
        self._poll: asyncio.Task | None = None
        self._log = None
        self.turns_seen = 0

    async def start(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        self._log = (self.out / "dsh.log").open("wb")
        port = _free_port()
        self.proc = await asyncio.create_subprocess_exec(
            str(self.dsh_bin), "web", "--port", str(port), "--no-open", cwd=str(self.ctx.workspace), env=self.env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        url = None
        deadline = time.time() + 90
        while time.time() < deadline:
            line = await asyncio.wait_for(self.proc.stdout.readline(), timeout=max(1, deadline - time.time()))
            if not line:
                break
            self._log.write(line)
            m = re.search(rb"dsh web: (http://\S+\?token=\S+)", line)
            if m:
                url = m.group(1).decode()
                break
        if not url:
            raise RuntimeError("dsh web did not print a sign-in URL")
        asyncio.create_task(self._pump())
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        # containers (Cloud Run gen2) lack the user namespaces Chromium's sandbox needs; the attempt is already isolated
        self._browser = await self._pw.chromium.launch(headless=True,
                                                       chromium_sandbox=os.environ.get("GEAP_CHROMIUM_NO_SANDBOX") != "1")
        self._bctx = await self._browser.new_context(viewport={"width": 1400, "height": 900},
                                                     record_video_dir=str(self.out / "video"),
                                                     record_video_size={"width": 1400, "height": 900})
        self.page = await self._bctx.new_page()
        await self.page.goto(url)  # token -> HttpOnly cookie; trace starts after so the token is not recorded
        await self._bctx.tracing.start(screenshots=False, snapshots=True)
        self.composer = self.page.get_by_role("textbox", name=re.compile(r"^(Describe what you want to build|Message or run a task)"))
        await self.composer.wait_for(timeout=60_000)
        notice = self.page.get_by_role("dialog", name="Preview Notice")
        if await notice.count():
            await notice.get_by_role("button", name="Continue").click()
            self._dialog("Preview Notice")
        label = await self.page.get_by_role("button", name=re.compile(r"^Select model, current ")).get_attribute("aria-label")
        want = f"{MODEL_LABELS[self.model]}, reasoning effort {self.effort.capitalize()}"
        if want not in (label or ""):
            raise RuntimeError(f"dsh model picker shows {label!r}, expected {want!r}")
        self._poll = asyncio.create_task(self._poll_loop())

    async def _pump(self):
        async for ln in self.proc.stdout:
            self._log.write(ln)

    def _dialog(self, name: str):
        if self.on_dialog:
            self.on_dialog(name)

    async def _poll_loop(self):
        stop_btn = self.page.get_by_role("button", name="Stop generating")
        while True:
            try:
                running = await stop_btn.count() > 0
                if running != self.running:
                    self.running = running
                    self.idle_since = time.time()
                if await self.page.get_by_role("button", name="Allow once").count():
                    await self.page.get_by_role("button", name="Reject").first.click()  # approval=never: escalations rejected
                    self._dialog("approval:reject")
                if await self.page.get_by_role("button", name="Dismiss all questions").count():
                    await self.page.get_by_role("button", name="Dismiss all questions").first.click()
                    self._dialog("ask_user_question:dismiss")
                if self.subscribers:
                    jpg = await self.page.screenshot(type="jpeg", quality=55)
                    for q in list(self.subscribers):
                        if q.qsize() < 20:
                            q.put_nowait(jpg)
            except Exception:  # noqa: BLE001 - page closing
                return
            await asyncio.sleep(1.0)

    # ---- runner surface
    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def wait_for(self, pattern, timeout: float):
        return True if self.page is not None else None

    async def wait_stable(self, seconds: float, timeout: float) -> bool:
        await asyncio.sleep(min(seconds, 2))
        return True

    def idle_for(self) -> float:
        return 0.0 if self.running else time.time() - self.idle_since

    def text(self) -> str:
        return "RUNNING" if self.running else "IDLE"

    def write(self, s) -> None:
        pass

    async def submit(self, text: str) -> float:
        await self.composer.click()
        await self.composer.fill(text)
        send = self.page.get_by_role("button", name="Send message")
        await send.wait_for()
        t0 = time.time()
        await send.click()
        self.running, self.idle_since = True, t0
        return t0

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q) -> None:
        self.subscribers.discard(q)

    async def close(self, quit_keys=None, grace_s: float = 10.0):
        if self._poll:
            self._poll.cancel()
        try:
            if self._bctx:
                await self._bctx.tracing.stop(path=str(self.out / "trace.zip"))
                await self.page.screenshot(path=str(self.out / "final.png"), full_page=True)
                await self._bctx.close()
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:  # noqa: BLE001
            pass
        self._bctx = self._browser = self._pw = None
        if self.proc and self.proc.returncode is None:
            pg = os.getpgid(self.proc.pid)
            os.killpg(pg, signal.SIGTERM)
            try:
                await asyncio.wait_for(self.proc.wait(), grace_s)
            except asyncio.TimeoutError:
                os.killpg(pg, signal.SIGKILL)
            try:
                os.killpg(pg, signal.SIGKILL)  # PTC workers / bash jobs in the group
            except ProcessLookupError:
                pass
        for q in list(self.subscribers):
            q.put_nowait(b"")
        if self._log:
            self._log.close()
        return self.proc.returncode if self.proc else None


class DshAcpSession:
    """dsh over ACP (Agent Client Protocol, JSON-RPC on stdio): the protocol editors use for interactive sessions."""

    def __init__(self, dsh_bin: Path, ctx: AttemptContext, env: dict, effort: str, out: Path):
        self.dsh_bin, self.ctx, self.env, self.effort, self.out = dsh_bin, ctx, env, effort, out
        self.proc: asyncio.subprocess.Process | None = None
        self.subscribers: set[asyncio.Queue] = set()
        self.on_dialog = None
        self.running = False
        self.idle_since = time.time()
        self.turns_done = 0
        self.cast_path = out / "session.cast"
        self._id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._log = None
        self._cast = None
        self._t0 = time.time()
        self.session_id = None

    def _emit(self, text: str) -> None:
        data = text.replace("\n", "\r\n").encode()
        if self._cast:
            self._cast.write(json.dumps([round(time.time() - self._t0, 4), "o", data.decode()]) + "\n")
            self._cast.flush()
        for q in list(self.subscribers):
            if q.qsize() < 2000:
                q.put_nowait(data)

    async def start(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        self._log = (self.out / "acp-transcript.jsonl").open("w")
        self._cast = self.cast_path.open("w")
        self._cast.write(json.dumps({"version": 2, "width": 160, "height": 50, "timestamp": int(self._t0),
                                     "title": "dsh --profile acp"}) + "\n")
        self.proc = await asyncio.create_subprocess_exec(
            str(self.dsh_bin), "--profile", "acp", cwd=str(self.ctx.workspace), env=self.env,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=(self.out / "acp.stderr").open("wb"), start_new_session=True, limit=16 * 1024 * 1024)
        asyncio.create_task(self._reader())
        r = await self._call("initialize", {"protocolVersion": 1, "clientCapabilities": {
            "fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}}, 180)
        self._emit(f"\x1b[2m{r.get('agentInfo', {}).get('name')} (ACP) ready\x1b[0m\n")
        r = await self._call("session/new", {"cwd": str(self.ctx.workspace), "mcpServers": []}, 180)
        self.session_id = r["sessionId"]
        cur = {o["id"]: o.get("currentValue") for o in r.get("configOptions", [])}
        self._emit(f"\x1b[2msession {self.session_id} model={cur.get('model')} effort={cur.get('reasoning_effort')}\x1b[0m\n")
        if cur.get("reasoning_effort") not in (None, self.effort):
            await self._call("session/set_config_option", {"sessionId": self.session_id, "configId": "reasoning_effort",
                                                            "value": self.effort}, 60)

    async def _send(self, m: dict) -> None:
        self._log.write(json.dumps({"dir": "out", "t": time.time(), "msg": m}) + "\n")
        self._log.flush()
        self.proc.stdin.write((json.dumps(m) + "\n").encode())
        await self.proc.stdin.drain()

    async def _call(self, method: str, params: dict, timeout: float | None = None):
        self._id += 1
        fut = asyncio.get_running_loop().create_future()
        self._pending[self._id] = fut
        await self._send({"jsonrpc": "2.0", "id": self._id, "method": method, "params": params})
        r = await (asyncio.wait_for(fut, timeout) if timeout else fut)
        if "error" in r:
            raise RuntimeError(f"ACP {method} error: {r['error']}")
        return r.get("result") or {}

    async def _reader(self):
        async for ln in self.proc.stdout:
            try:
                m = json.loads(ln)
            except ValueError:
                continue
            self._log.write(json.dumps({"dir": "in", "t": time.time(), "msg": m}) + "\n")
            self._log.flush()
            meth = m.get("method")
            if "id" in m and not meth and m["id"] in self._pending:
                self._pending.pop(m["id"]).set_result(m)
            elif meth == "session/update":
                u = m["params"]["update"]
                k = u.get("sessionUpdate")
                if k == "agent_message_chunk":
                    self._emit((u.get("content") or {}).get("text", ""))
                elif k == "tool_call":
                    desc = (u.get("rawInput") or {}).get("description") or ""
                    self._emit(f"\n\x1b[36m● {u.get('title')}\x1b[0m {desc}\n")
                elif k == "tool_call_update" and u.get("status") in ("completed", "failed"):
                    ok = u["status"] == "completed"
                    self._emit(f"  {'\x1b[32m✓' if ok else '\x1b[31m✗'} {u['status']}\x1b[0m\n")
            elif meth == "session/request_permission":
                opts = m["params"]["options"]
                rej = [o for o in opts if o["kind"].startswith("reject")] or opts
                await self._send({"jsonrpc": "2.0", "id": m["id"],
                                  "result": {"outcome": {"outcome": "selected", "optionId": rej[0]["optionId"]}}})
                self._emit("\x1b[33m[permission request auto-rejected]\x1b[0m\n")
                if self.on_dialog:
                    self.on_dialog("acp:request_permission:reject")
            elif "id" in m and meth:
                await self._send({"jsonrpc": "2.0", "id": m["id"], "error": {"code": -32601, "message": "not supported"}})

    async def _prompt(self, text: str):
        try:
            r = await self._call("session/prompt", {"sessionId": self.session_id, "prompt": [{"type": "text", "text": text}]})
            self._emit(f"\n\x1b[2m[turn ended: {r.get('stopReason')}]\x1b[0m\n")
        except Exception as e:  # noqa: BLE001
            self._emit(f"\n\x1b[31m[prompt failed: {e}]\x1b[0m\n")
        finally:
            self.turns_done += 1
            self.running = False
            self.idle_since = time.time()

    # ---- runner surface (same as PtySession / DshWebSession)
    @property
    def alive(self) -> bool:
        return self.proc is not None and self.proc.returncode is None

    async def wait_for(self, pattern, timeout: float):
        return True if self.session_id else None

    async def wait_stable(self, seconds: float, timeout: float) -> bool:
        return True

    def idle_for(self) -> float:
        return 0.0 if self.running else time.time() - self.idle_since

    def text(self) -> str:
        return "RUNNING" if self.running else "IDLE"

    def write(self, s) -> None:
        pass

    async def submit(self, text: str) -> float:
        t0 = time.time()
        self.running, self.idle_since = True, t0
        self._emit(f"\n\x1b[1m> {text[:300]}{'…' if len(text) > 300 else ''}\x1b[0m\n")
        asyncio.create_task(self._prompt(text))
        return t0

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q) -> None:
        self.subscribers.discard(q)

    async def close(self, quit_keys=None, grace_s: float = 10.0):
        try:
            if self.session_id and self.alive:
                await self._call("session/close", {"sessionId": self.session_id}, 20)
            if self.proc and self.proc.stdin:
                self.proc.stdin.close()
            await asyncio.wait_for(self.proc.wait(), grace_s)
        except Exception:  # noqa: BLE001
            pass
        if self.proc and self.proc.returncode is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
        for f in (self._log, self._cast):
            if f:
                f.close()
        for q in list(self.subscribers):
            q.put_nowait(b"")
        return self.proc.returncode if self.proc else None


def _free_port() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Dsh(Adapter):
    name = "dsh"
    driver = "browser"
    npm_package = "@deepseek-ai/dsh"
    bin_name = "dsh"
    thinking_control = "profile reasoningEffort -> thinkingLevel (LOW/MEDIUM/HIGH)"
    roles_supported = ("default", "subagent")
    native_multi_model = True  # subagent-model-selection-settings with an allow-list of exactly the subagent model
    meter_mode = "base_url (llm-pi-ai google-vertex baseURL)"

    def install_latest(self) -> str:
        self.prefix.mkdir(parents=True, exist_ok=True)
        pj = self.prefix / "package.json"
        d = json.loads(pj.read_text()) if pj.exists() else {"name": "geap-eval-dsh", "private": True}
        d["allowScripts"] = {k: True for k in ALLOW_SCRIPTS} if not isinstance(d.get("allowScripts"), (dict, list)) else d["allowScripts"]
        pj.write_text(json.dumps(d, indent=2))
        return super().install_latest()

    def capabilities(self) -> dict:
        c = super().capabilities()
        c["driver"] = "acp (JSON-RPC stdio)" if self.variant.startswith("acp") else "browser (Playwright, Web UI)"
        c["tools_mode"] = "native" if self.variant == "web-native" else "ptc"
        return c

    def supports(self, profile, roles):
        if profile.mode == "pipeline":
            return "dsh in-session model switching (pipeline) not wired; use native_roles (subagent model)"
        return super().supports(profile, roles)

    def model_reason(self, rr: ResolvedRole) -> str | None:
        if rr.provider != "google":
            return "vanilla dsh has no Claude-on-Vertex route (pi-ai google-vertex is Gemini only)"
        if rr.model not in MODEL_LABELS:
            return f"dsh profile does not list {rr.model}"
        if rr.thinking not in ("low", "medium", "high"):
            return f"dsh reasoning effort supports low/medium/high, not {rr.thinking}"
        return None

    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        rr = ctx.roles["default"]
        att = ctx.workdir
        documents = att / "documents"
        acp = self.variant.startswith("acp")
        if acp:
            ws = ctx.workspace  # ACP takes the cwd from session/new
        else:
            ws = documents / "deepseek-harness" / "default-workspace"  # dsh web's fixed first-use workspace
            ws.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ctx.workspace), str(ws))
            ctx.workspace = ws
        dsh_home = att / "dsh_home"
        env = base_env(ctx.home, {"DSH_HOME": str(dsh_home), "DSH_AGENTS_HOME": str(att / "agents_home"),
                                  "DSH_TELEMETRY_DISABLED": "1", "GOOGLE_CLOUD_LOCATION": rr.location})
        profile = "acp" if acp else "web"
        subprocess.run([str(self.bin_path()), "--profile", profile, "--dump-config"], cwd=ws, env=env, check=True,
                       capture_output=True, timeout=180)
        base_url = f"{ctx.meter_base}/v1/projects/{PROJECT}/locations/{rr.location}"
        mode = "native" if self.variant == "web-native" else "ptc"
        patch = _patch(base_url, rr.model, rr.thinking, ws, documents, mode, rr.location)
        sub = ctx.roles.get("subagent")
        if sub:  # vanilla: main model may delegate; the allow-list pins which model subagents run on
            patch += ("- id: subagent-model-selection-settings\n  config:\n    enabled: true\n    allowedModels:\n"
                      f"      - {{provider: google-vertex, model: {sub.model}}}\n")
        if acp:
            patch += f"- id: acp\n  config:\n    provider: google-vertex\n    model: {rr.model}\n"
        (dsh_home / f"profiles/{profile}/cordis.patch.yml").write_text(patch)
        (ctx.artifacts / "dsh.cordis.patch.yml").write_text(patch)
        self._ctx_env = env

        def done() -> int:
            """Root turn/end count while everything (root, subagents, jobs) is idle; -1 while busy."""
            st = work_state(dsh_home)
            cwd = (st.get("root") or {}).get("cwd")
            if cwd and not str(Path(cwd).resolve()).startswith(str(att.resolve())):
                raise RuntimeError(f"dsh session cwd {cwd} escaped the attempt dir")
            return st["root"]["turns_ended"] if st["idle"] else (0 if st["root"] is None else -1)

        return LaunchSpec(argv=[], env=env, cwd=ws, ready=re.compile("IDLE"), busy=re.compile("RUNNING"),
                          done_counter=done, aux_call=lambda c: (c.get("tools_defined") or 0) == 0,
                          quit_keys=[], boot_timeout_s=120)

    def open_session(self, ctx: AttemptContext, spec: LaunchSpec, cast_path: Path):
        rr = ctx.roles["default"]
        if self.variant.startswith("acp"):
            sess = DshAcpSession(self.bin_path(), ctx, spec.env, rr.thinking, ctx.artifacts)
            self._acp = sess
            return sess
        return DshWebSession(self.bin_path(), ctx, spec.env, rr.model, rr.thinking, ctx.artifacts)

    def collect(self, ctx: AttemptContext) -> PlaneA:
        pa = PlaneA()
        dsh_home = ctx.workdir / "dsh_home"
        out = ctx.artifacts / "plane_a"
        out.mkdir(exist_ok=True)
        usage = {"tok_input": 0, "tok_cache_read": 0, "tok_output_incl_thinking": 0}
        steps = 0
        for i, f in enumerate(session_files(dsh_home)):
            rows = read_session(f)
            (out / f"session-{i}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
            pa.session_files.append(out / f"session-{i}.jsonl")
            if rows and rows[0].get("delegationDepth", 0) > 0:
                pa.subagents += 1
            results = {}
            for r in rows:
                t, d = r.get("type"), r.get("data") or {}
                if t == "step/start":
                    steps += 1
                elif t == "assistant/message":
                    u = d.get("usage") or {}
                    usage["tok_input"] += u.get("inputTokens", 0)
                    usage["tok_cache_read"] += u.get("cacheReadTokens", 0)
                    usage["tok_output_incl_thinking"] += u.get("outputTokens", 0)
                elif t == "tool/result":
                    m = d.get("message") or {}
                    results[m.get("toolCallId")] = (m.get("isError"), d.get("error"), r.get("time", 0) / 1000)
                elif t == "tool/ptc-dispatch":
                    err = d.get("error") or {}
                    pa.tool_calls.append({"call_id": d.get("subCallId"), "parent_id": d.get("parentCallId"), "name": d.get("name"),
                                          "status": "error" if d.get("isError") else "ok", "error_code": err.get("code"),
                                          "t_start": None, "t_end": r.get("time", 0) / 1000, "args_hash": None})
            for r in rows:
                if r.get("type") == "tool/call":
                    d = r["data"]
                    is_err, err, t_end = results.get(d["callId"], (None, None, None))
                    err = err or {}
                    pa.tool_calls.append({"call_id": d["callId"], "parent_id": None, "name": d["name"],
                                          "status": "error" if is_err else ("ok" if t_end else "error"),
                                          "error_code": err.get("code"), "t_start": r.get("time", 0) / 1000, "t_end": t_end,
                                          "args_hash": _h(d.get("arguments") or d.get("args"))})
        pa.usage = usage
        pa.llm_turns = steps or None
        pa.tool_calls.sort(key=lambda t: t.get("t_start") or t.get("t_end") or 0)
        return pa


def _h(x) -> str | None:
    if x is None:
        return None
    import hashlib

    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:12]


ADAPTER = Dsh
