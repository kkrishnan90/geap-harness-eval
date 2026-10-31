"""Reference driver: one unattended dsh/web attempt (vanilla dsh, PTC, GEAP via ADC).

Phase-0 spike artifact (see docs/spikes/dsh.md). It is self-contained on purpose:
it builds an isolated attempt directory, starts an optional built-in Meter
forwarder, boots `dsh web` with an isolated DSH_HOME/HOME and an allowlisted env,
drives the Web UI with Playwright Chromium, detects completion from the durable
session log (turn/end) + DOM, collects artifacts and shuts everything down.

Run (Python via uv; Playwright + `playwright install chromium` in the venv):

    uv run --with playwright python docs/spikes/dsh_drive.py \
        --dsh tools/dsh/node_modules/.bin/dsh \
        --repo path/to/seed_repo --task-file path/to/instruction.md \
        --attempt-dir /tmp/.../attempt-1 --model gemini-3.8-flash --effort low

Nothing under the user's ~/.dsh, ~/Documents or the :3080 service is touched:
DSH_HOME, DSH_AGENTS_HOME, HOME and TMPDIR live inside --attempt-dir, and the
Web "Default workspace" is pinned inside it via workspace-controller.documentsDirectory
(otherwise dsh asks macOS osascript for the REAL ~/Documents, ignoring $HOME).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import shutil
import signal
import socket
import ssl
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT = "your-gcp-project"
LOCATION = "global"
ADC_SRC = Path.home() / ".config/gcloud/application_default_credentials.json"
MODEL_LABELS = {"gemini-3.8-flash": "Gemini 3.8 Flash", "gemini-4-argon": "Gemini 4 Argon"}
EFFORTS = ("low", "medium", "high")  # what dsh's pi-ai catalog offers for these models

# ----------------------------------------------------------------------------- meter


class _Meter:
    """Minimal streaming forwarder: /t/<token>/<rest> -> https://aiplatform.googleapis.com/<rest>."""

    HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "upgrade", "te",
           "trailer", "host", "content-length", "accept-encoding"}

    def __init__(self, port: int, log_path: Path, bodies_dir: Path | None):
        self.port, self.log_path, self.bodies = port, log_path, bodies_dir
        self.lock, self.seq = threading.Lock(), 0
        self.inflight = 0
        self.last_end = 0.0
        self.last_record: dict | None = None
        meter = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *a):
                pass

            def do_POST(self):
                meter.handle(self)

            do_GET = do_POST

        self.srv = ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def close(self):
        self.srv.shutdown()

    def _log(self, rec):
        with self.lock:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            self.last_record = rec

    def handle(self, h: BaseHTTPRequestHandler):
        t0 = time.time()
        with self.lock:
            self.seq += 1
            seq = self.seq
            self.inflight += 1
        try:
            n = int(h.headers.get("content-length") or 0)
            body = h.rfile.read(n) if n else b""
            hdr_log = {k: ("REDACTED" if k.lower() in ("authorization", "x-goog-api-key", "cookie") else v)
                       for k, v in h.headers.items()}
            rec = {"seq": seq, "t_start": t0, "method": h.command, "path_in": h.path, "req_headers": hdr_log}
            m = re.match(r"^/t/([^/]+)(/.*)$", h.path)
            if not m or not re.match(rf"^/v1(beta1)?/projects/{PROJECT}/", m.group(2)):
                rec.update(status=403, error="rejected path (must be /t/<tok>/v1/projects/your-gcp-project/...)", t_end=time.time())
                h.send_response(403); h.send_header("Content-Length", "0"); h.end_headers()
                return self._log(rec)
            rest = m.group(2)
            rec.update(attempt_token=m.group(1), upstream_path=rest, request=_summarize_req(body))
            if self.bodies and body:
                (self.bodies / f"req-{seq:04d}.json").write_bytes(body)
            hdrs = {k: v for k, v in h.headers.items() if k.lower() not in self.HOP}
            hdrs["Host"] = "aiplatform.googleapis.com"
            conn = http.client.HTTPSConnection("aiplatform.googleapis.com", 443,
                                               context=ssl.create_default_context(), timeout=900)
            conn.request(h.command, rest, body=body or None, headers=hdrs)
            resp = conn.getresponse()
            rec["status"] = resp.status
            h.send_response(resp.status)
            for k, v in resp.getheaders():
                if k.lower() not in self.HOP:
                    h.send_header(k, v)
            h.send_header("Transfer-Encoding", "chunked")
            h.send_header("Connection", "close")
            h.end_headers()
            buf, first = bytearray(), None
            while chunk := resp.read1(65536):
                first = first or time.time()
                buf += chunk
                h.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n")
                h.wfile.flush()
            h.wfile.write(b"0\r\n\r\n")
            h.wfile.flush()
            conn.close()
            h.close_connection = True
            rec.update(t_first_byte=first, t_end=time.time(), resp_bytes=len(buf), **_parse_gemini_sse(bytes(buf)))
            self._log(rec)
        finally:
            with self.lock:
                self.inflight -= 1
                self.last_end = time.time()


def _summarize_req(body: bytes) -> dict | None:
    if not body:
        return None
    try:
        j = json.loads(body)
    except ValueError:
        return {"bytes": len(body)}
    cfg = j.get("generationConfig") or {}
    return {"thinkingConfig": cfg.get("thinkingConfig"), "maxOutputTokens": cfg.get("maxOutputTokens"),
            "n_contents": len(j.get("contents") or []), "bytes": len(body),
            "function_declarations": [f.get("name") for t in j.get("tools") or [] for f in t.get("functionDeclarations") or []]}


def _parse_gemini_sse(raw: bytes) -> dict:
    usage = finish = model_version = None
    fcalls: list[str] = []
    err = None
    lines = [ln[5:].strip() for ln in raw.decode("utf-8", "replace").splitlines() if ln.startswith("data:")]
    for ev in lines or [raw.decode("utf-8", "replace")]:
        try:
            o = json.loads(ev)
        except ValueError:
            continue
        for x in o if isinstance(o, list) else [o]:
            if not isinstance(x, dict):
                continue
            usage = x.get("usageMetadata") or usage
            model_version = x.get("modelVersion", model_version)
            err = x.get("error", err)
            for c in x.get("candidates") or []:
                finish = c.get("finishReason", finish)
                fcalls += [p["functionCall"].get("name") for p in (c.get("content") or {}).get("parts") or [] if "functionCall" in p]
    return {"usage": usage, "finish_reason": finish, "model_version": model_version, "function_calls": fcalls,
            "error_body": err}


# ----------------------------------------------------------------------------- setup


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def profile_patch(*, base_url: str | None, model: str, effort: str, workspace: Path, documents: Path,
                  sandbox: str, tools_mode: str) -> str:
    """The profile's cordis.patch.yml (a top-level list of id-targeted overrides; config replaces whole)."""
    base = f"        baseURL: {base_url}\n" if base_url else ""
    return f"""# geap-eval dsh/web attempt patch (vanilla dsh {''}; Vertex via ADC; PTC)
- id: llm-pi-ai
  config:
    providers:
      google-vertex:
        displayName: GEAP ({PROJECT}, {LOCATION})
{base}        reasoning: {effort}
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
    mode: {sandbox}
    workspaceRoot: {workspace}
- id: approval
  config:
    policy: never
- id: permission
  config:
    presets:
      unattended:
        sandbox: {sandbox}
        approval: never
        name: unattended
        description: {sandbox} sandbox; approval prompts disabled (escalations auto-rejected)
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


def isolated_env(att: Path) -> dict:
    env = {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "HOME": str(att / "home"),
        "TMPDIR": str(att / "tmp"),
        "DSH_HOME": str(att / "dsh_home"),
        "DSH_AGENTS_HOME": str(att / "agents_home"),
        "DSH_TELEMETRY_DISABLED": "1",
        "GOOGLE_CLOUD_PROJECT": PROJECT,
        "GOOGLE_CLOUD_QUOTA_PROJECT": PROJECT,
        "GOOGLE_CLOUD_LOCATION": LOCATION,
    }
    for k in env:  # paranoia: allowlist only
        assert not k.startswith(("CLAUDE", "ANTHROPIC")) and not k.endswith("_API_KEY")
    return env


def prepare_attempt(args) -> dict:
    att = Path(args.attempt_dir).resolve()
    if att.exists():
        shutil.rmtree(att)
    for d in ("home/.config/gcloud", "dsh_home", "agents_home", "tmp", "out/bodies", "out/shots"):
        (att / d).mkdir(parents=True, exist_ok=True)
    adc = att / "home/.config/gcloud/application_default_credentials.json"
    shutil.copyfile(ADC_SRC, adc)
    os.chmod(adc, 0o600)
    if json.loads(adc.read_text()).get("type") != "authorized_user":
        sys.exit("ADC is not authorized_user")
    documents = att / "documents"
    workspace = documents / "deepseek-harness" / "default-workspace"  # dsh's fixed first-use path
    workspace.parent.mkdir(parents=True)
    if args.repo:
        shutil.copytree(args.repo, workspace, symlinks=True)
    else:
        workspace.mkdir()
    env = isolated_env(att)
    for kv in args.env or []:  # explicit extra allowlisted vars, e.g. HTTPS_PROXY / NODE_USE_ENV_PROXY
        k, _, v = kv.partition("=")
        env[k] = v
    return {"att": att, "documents": documents, "workspace": workspace, "env": env}


# ----------------------------------------------------------------------------- session store


def find_session_files(dsh_home: Path) -> list[Path]:
    return sorted((dsh_home / "sessions").glob("*/*/session.v*.jsonl*"))


def read_session(path: Path) -> list[dict]:
    """Multi-frame zstd: use the zstd CLI (Node's zstdDecompressSync stops after frame 1)."""
    if path.suffix == ".zstd":
        raw = subprocess.run(["zstd", "-dcq", str(path)], capture_output=True, check=False).stdout
    else:
        raw = path.read_bytes()
    rows = []
    for ln in raw.decode("utf-8", "replace").splitlines():
        try:
            rows.append(json.loads(ln))
        except ValueError:
            pass  # torn tail while dsh is still writing
    return rows


def work_state(dsh_home: Path) -> dict:
    """Idle = the root session (header delegationDepth 0, no parentSession) has >=1 turn/end, no session
    (root or subagent child) has a turn/start without a later turn/end, and every job/registered has settled.
    Subagent children live as sibling dirs (`<uuid>/session.v4.jsonl.zstd`) under the same project dir."""
    root = None
    open_turns, open_jobs, n = [], set(), 0
    for f in find_session_files(dsh_home):
        rows = read_session(f)
        if not rows:
            continue
        n += 1
        hdr = rows[0]
        last_start = max((i for i, r in enumerate(rows) if r.get("type") == "turn/start"), default=-1)
        last_end = max((i for i, r in enumerate(rows) if r.get("type") == "turn/end"), default=-1)
        if last_start > last_end:
            open_turns.append(hdr.get("id"))
        for r in rows:
            if r.get("type") == "job/registered":
                open_jobs.add(r["data"]["jobId"])
            elif r.get("type") == "job/settled":
                open_jobs.discard(r["data"]["jobId"])
        if hdr.get("delegationDepth", 0) == 0 and not hdr.get("parentSession"):
            ends = [r for r in rows if r.get("type") == "turn/end"]
            root = {"id": hdr.get("id"), "turns_ended": len(ends),
                    "last_reason": ends[-1]["data"]["reason"] if ends else None,
                    "t_end_record": ends[-1]["time"] / 1000 if ends else None}
    idle = bool(root and root["turns_ended"] and not open_turns and not open_jobs)
    return {"idle": idle, "root": root, "sessions": n, "open_turns": open_turns, "open_jobs": sorted(open_jobs)}


def summarize_session(rows: list[dict]) -> dict:
    s = {"steps": 0, "assistant_messages": 0, "usage": {"input": 0, "output_incl_thinking": 0, "cache_read": 0, "cache_write": 0},
         "run_code": [], "ptc_subcalls": [], "native_tool_calls": [], "turn_end": None, "title_calls": 0}
    results = {}
    for r in rows:
        t, d = r.get("type"), r.get("data") or {}
        if t == "step/start":
            s["steps"] += 1
        elif t == "assistant/message":
            s["assistant_messages"] += 1
            u = d.get("usage") or {}
            s["usage"]["input"] += u.get("inputTokens", 0)
            s["usage"]["output_incl_thinking"] += u.get("outputTokens", 0)
            s["usage"]["cache_read"] += u.get("cacheReadTokens", 0)
            s["usage"]["cache_write"] += u.get("cacheWriteTokens", 0)
        elif t == "tool/result":
            results[d["message"]["toolCallId"]] = {"isError": d["message"].get("isError"), "error": d.get("error")}
        elif t == "tool/ptc-dispatch":
            s["ptc_subcalls"].append({"id": d["subCallId"], "parent": d["parentCallId"], "name": d["name"],
                                      "isError": d.get("isError"), "error": d.get("error"), "t_end": r["time"] / 1000})
        elif t == "session/title-llm-request":
            s["title_calls"] += 1
        elif t == "turn/end":
            s["turn_end"] = {"turn": d.get("turn"), "reason": d.get("reason"), "time": r["time"] / 1000}
    for r in rows:
        if r.get("type") == "tool/call":
            d = r["data"]
            target = s["run_code"] if d["name"] == "run_code" else s["native_tool_calls"]
            target.append({"id": d["callId"], "name": d["name"], "t_start": r["time"] / 1000, **results.get(d["callId"], {})})
    return s


# ----------------------------------------------------------------------------- driver


def boot_dsh(args, ctx) -> tuple[subprocess.Popen, str]:
    env, ws = ctx["env"], ctx["workspace"]
    dsh = str(Path(args.dsh).resolve())
    # 1) auto-initialize the shipped `web` profile under the isolated DSH_HOME, then write our patch layer
    subprocess.run([dsh, "--profile", "web", "--dump-config"], cwd=ws, env=env, check=True, capture_output=True)
    patch = profile_patch(base_url=ctx.get("base_url"), model=args.model, effort=args.effort, workspace=ws,
                          documents=ctx["documents"], sandbox=args.sandbox, tools_mode=args.tools_mode)
    if args.extra_patch:  # more id-targeted overrides, e.g. subagent model selection (see dsh.md §8)
        patch += Path(args.extra_patch).read_text()
    (ctx["att"] / "dsh_home/profiles/web/cordis.patch.yml").write_text(patch)
    (ctx["att"] / "out/cordis.patch.yml").write_text(patch)
    # 2) boot; the one-time sign-in URL is printed on stdout: "dsh web: http://127.0.0.1:<port>/?token=<tok>"
    port = free_port()
    assert port != 3080
    log = open(ctx["att"] / "out/dsh.log", "wb")
    proc = subprocess.Popen([dsh, "web", "--port", str(port), "--no-open"], cwd=ws, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    deadline = time.time() + 60
    url = None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                raise RuntimeError(f"dsh exited rc={proc.returncode}")
            continue
        log.write(line); log.flush()
        m = re.search(rb"dsh web: (http://\S+\?token=\S+)", line)
        if m:
            url = m.group(1).decode()
            break
    if not url:
        raise RuntimeError("no token URL from dsh web")

    def pump():
        for ln in proc.stdout:
            log.write(ln); log.flush()
    threading.Thread(target=pump, daemon=True).start()
    return proc, url


def stop_dsh(proc: subprocess.Popen, grace: float = 10.0) -> str:
    if proc.poll() is not None:
        return f"already-exited rc={proc.returncode}"
    pgid = os.getpgid(proc.pid)
    os.killpg(pgid, signal.SIGTERM)
    try:
        proc.wait(grace)
        how = f"SIGTERM rc={proc.returncode}"
    except subprocess.TimeoutExpired:
        os.killpg(pgid, signal.SIGKILL)
        proc.wait(5)
        how = "SIGKILL"
    try:  # reap stragglers (PTC workers, bash jobs) in the group
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return how


def drive(args, ctx, url: str, events: list) -> dict:
    from playwright.sync_api import sync_playwright

    out = ctx["att"] / "out"
    task = Path(args.task_file).read_text() if args.task_file else args.task
    res: dict = {}

    def ev(kind, **kw):
        events.append({"ts": time.time(), "type": kind, **kw})

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        bctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                   record_video_dir=str(out / "video"), record_video_size={"width": 1400, "height": 900})
        page = bctx.new_page()
        page.goto(url)  # ?token= is exchanged for an HttpOnly dsh-auth-* cookie, then redirected to /
        if args.trace != "off":  # started after sign-in so the one-time ?token= URL is not in the trace
            bctx.tracing.start(screenshots=args.trace == "full", snapshots=True)
        composer = page.get_by_role("textbox", name=re.compile(r"^(Describe what you want to build|Message or run a task)"))
        composer.wait_for(timeout=60_000)
        notice = page.get_by_role("dialog", name="Preview Notice")
        if notice.count():
            notice.get_by_role("button", name="Continue").click()
            ev("dialog_answered", dialog="Preview Notice", choice="Continue")
        # sanity: model picker + access mode + workspace reflect the patch
        model_btn = page.get_by_role("button", name=re.compile(r"^Select model, current "))
        res["model_button"] = model_btn.get_attribute("aria-label")
        res["access_button"] = page.get_by_role("button", name=re.compile(r"^Access mode, current: ")).get_attribute("aria-label")
        res["workspace_button"] = page.get_by_role("button", name="Choose workspace").inner_text()
        want = f"{MODEL_LABELS.get(args.model, args.model)}, reasoning effort {args.effort.capitalize()}"
        if want not in (res["model_button"] or ""):
            raise RuntimeError(f"model picker shows {res['model_button']!r}, want {want!r}")
        if args.access_mode_ui:  # optional: switch the session's permission preset through the UI menu
            page.get_by_role("button", name=re.compile(r"^Access mode, current: ")).click()
            page.get_by_role("menuitem", name=args.access_mode_ui, exact=True).click()
            res["access_button"] = page.get_by_role("button", name=re.compile(r"^Access mode, current: ")).get_attribute("aria-label")
        page.screenshot(path=str(out / "shots/00-ready.png"))
        composer.click()
        composer.fill(task)
        send = page.get_by_role("button", name="Send message")
        send.wait_for()
        t0 = time.time()
        send.click()
        ev("prompt_submitted", t0=t0)
        res["t0"] = t0
        stop_btn = page.get_by_role("button", name="Stop generating")
        deadline = t0 + args.timeout
        seen_running = False
        done_reason = None
        quiet_since = None
        last_shot = 0.0
        while time.time() < deadline:
            page.wait_for_timeout(1000)
            running = stop_btn.count() > 0
            seen_running |= running
            # dialog responder (approval / ask_user); with approval=never these should not appear
            if page.get_by_role("button", name="Allow once").count():
                choice = "Allow once" if args.on_approval == "allow" else "Reject"
                page.screenshot(path=str(out / f"shots/dialog-approval-{int(time.time()-t0):04d}.png"))
                (out / f"dialog-approval-{int(time.time()-t0):04d}.aria.txt").write_text(page.locator("body").aria_snapshot())
                page.get_by_role("button", name=choice).first.click()
                ev("dialog_answered", dialog="approval", choice=choice)
            if page.get_by_role("button", name="Dismiss all questions").count():
                page.screenshot(path=str(out / f"shots/dialog-question-{int(time.time()-t0):04d}.png"))
                page.get_by_role("button", name="Dismiss all questions").first.click()
                ev("dialog_answered", dialog="ask_user_question", choice="Dismiss all questions")
            if time.time() - last_shot > 15:
                page.screenshot(path=str(out / f"shots/run-{int(time.time()-t0):04d}.png"))
                last_shot = time.time()
            # (a) durable turn records: root closed its turn, no child session has an open turn, no job running
            st = work_state(ctx["att"] / "dsh_home")
            meter = ctx.get("meter")
            meter_quiet = meter is None or (meter.inflight == 0 and time.time() - meter.last_end > 2)
            dom_idle = seen_running and not running
            if st["idle"] and meter_quiet:
                quiet_since = quiet_since or time.time()
                if time.time() - quiet_since >= args.settle:
                    done_reason = {"signal": "session:turn/end", **st, "dom_idle": dom_idle}
                    break
            else:
                quiet_since = None
            # (c) DOM idle is recorded only as a cross-check; the durable record is authoritative
            if dom_idle and not st["idle"] and page.get_by_role("status").filter(has_text=re.compile("Completed|Failed|Stopped|Error")).count():
                ev("dom_idle_without_turn_end")
        res["completion"] = done_reason or {"signal": "timeout"}
        ev("completion_detected", **res["completion"])
        page.wait_for_timeout(1500)
        page.screenshot(path=str(out / "shots/99-final.png"), full_page=True)
        (out / "final.aria.txt").write_text(page.locator("body").aria_snapshot())
        if args.trace != "off":
            bctx.tracing.stop(path=str(out / "trace.zip"))
        bctx.close()
        browser.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsh", default="tools/dsh/node_modules/.bin/dsh")
    ap.add_argument("--repo", help="seed repo copied into the workspace")
    ap.add_argument("--task", default="Say hello.")
    ap.add_argument("--task-file")
    ap.add_argument("--attempt-dir", required=True)
    ap.add_argument("--model", default="gemini-3.8-flash", choices=sorted(MODEL_LABELS))
    ap.add_argument("--effort", default="low", choices=EFFORTS)
    ap.add_argument("--tools-mode", default="ptc", choices=("ptc", "native"))
    ap.add_argument("--sandbox", default="workspace-write", choices=("workspace-write", "danger-full-access"))
    ap.add_argument("--on-approval", default="reject", choices=("reject", "allow"))
    ap.add_argument("--env", action="append", help="extra KEY=VALUE for the dsh process (allowlist addition)")
    ap.add_argument("--extra-patch", help="YAML list appended to the generated profile patch")
    ap.add_argument("--access-mode-ui", help="pick this Access mode menu item before sending (e.g. 'Workspace Write')")
    ap.add_argument("--meter", default="builtin", help="'builtin', 'none', or an external base URL prefix http://host:port/t/<tok>")
    ap.add_argument("--timeout", type=float, default=600)
    ap.add_argument("--settle", type=float, default=3.0, help="seconds the idle state must hold before declaring done")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--trace", default="dom", choices=("full", "dom", "off"),
                    help="Playwright trace: full = DOM snapshots + screencast (~15-50 MB), dom = snapshots only")
    args = ap.parse_args()

    ctx = prepare_attempt(args)
    out = ctx["att"] / "out"
    meter = None
    tok = ctx["att"].name
    vpath = f"/v1/projects/{PROJECT}/locations/{LOCATION}"
    if args.meter == "builtin":
        mport = free_port()
        meter = _Meter(mport, out / "meter.jsonl", out / "bodies")
        ctx["base_url"] = f"http://127.0.0.1:{mport}/t/{tok}{vpath}"
        ctx["meter"] = meter
    elif args.meter != "none":
        ctx["base_url"] = args.meter.rstrip("/") + vpath
    events: list = []
    proc = None
    res: dict = {}
    try:
        proc, url = boot_dsh(args, ctx)
        events.append({"ts": time.time(), "type": "dsh_ready", "url": re.sub(r"token=\S+", "token=REDACTED", url)})
        res = drive(args, ctx, url, events)
        if meter:  # Meter quiescence: give in-flight calls (e.g. the title call) time to land
            q = time.time() + 15
            while time.time() < q and (meter.inflight or time.time() - meter.last_end < 2):
                time.sleep(0.5)
    finally:
        if proc:
            res["shutdown"] = stop_dsh(proc)
        if meter:
            meter.close()
    files = find_session_files(ctx["att"] / "dsh_home")
    res["session_files"] = [str(f) for f in files]
    for i, f in enumerate(files):
        rows = read_session(f)
        (out / f"session-{i}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        res.setdefault("sessions", []).append(summarize_session(rows))
    if meter and (out / "meter.jsonl").exists():
        calls = [json.loads(ln) for ln in (out / "meter.jsonl").open()]
        res["meter"] = {"calls": len(calls), "statuses": sorted({c["status"] for c in calls}),
                        "thinking_configs": sorted({json.dumps((c.get("request") or {}).get("thinkingConfig")) for c in calls}),
                        "t_end_last": max((c.get("t_end") or 0) for c in calls) if calls else None,
                        "thoughts_tokens": sum(((c.get("usage") or {}).get("thoughtsTokenCount") or 0) for c in calls)}
    (out / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (out / "result.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
