"""Phase-0 reference: drive Claude Code's NATIVE INTERACTIVE TUI unattended against GEAP (Vertex AI) with ADC.

Standalone (needs only ptyprocess + pyte from the project venv):

    uv run python docs/spikes/claude_code_drive.py --out /tmp/x/run1 \
        --prompt "Create hello.txt containing hi, then reply DONE." --effort low --meter

What it does (every step verified on Claude Code 2.1.314, 2026-10-30; see docs/spikes/claude_code.md):
  1. Fresh isolated HOME (only a 0600 copy of the user ADC file) + empty env + allowlist.
  2. Pre-seeds CLAUDE_CONFIG_DIR so no first-run dialog appears (theme, security notes, trust, bypass consent).
  3. Optional in-process "Meter" forwarder on 127.0.0.1 (ANTHROPIC_VERTEX_BASE_URL) logging every model call.
  4. Launches `claude --dangerously-skip-permissions` in a 220x60 PTY, waits for the ready signature.
  5. Bracketed-paste + Enter; t0 = the moment Enter is written.
  6. Completion = Stop-hook marker line + idle screen (no "esc to interrupt", no "Waiting for N background agent").
  7. `/exit`, then SIGTERM/SIGKILL; collects transcript, subagent transcripts, hook payloads, cast, meter log.
"""
from __future__ import annotations

import argparse, http.client, json, os, re, shutil, signal, socket, ssl, subprocess, sys, tempfile, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ptyprocess, pyte

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CLAUDE = os.path.join(ROOT, "tools/claude_code/node_modules/.bin/claude")
ADC = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
PROJECT, LOCATION = "your-gcp-project", "global"
COLS, ROWS = 220, 60

# Screen signatures (pyte display text) -----------------------------------------------------------------
READY_RX = re.compile(r"^❯(\s|$)", re.M)                 # input-box prompt glyph at column 0
BYPASS_FOOTER_RX = re.compile(r"bypass permissions on")    # footer once the TUI is interactive
BUSY_RX = re.compile(r"esc to interrupt|Waiting for \d+ background agent|Retrying in \d+s")
DIALOGS = [  # (regex, keys) -- only reached if pre-seeding failed or a mid-session confirmation appears
    (re.compile(r"Choose the text style that looks best"), b"\r"),
    (re.compile(r"Press Enter to continue"), b"\r"),
    (re.compile(r"Yes, I trust this folder"), b"\x1b[B\r"),        # default is "No, exit": Down then Enter
    (re.compile(r"Change effort level\?"), b"1"),                   # "1. Yes, switch to <level>"
]


# Meter (minimal logging forwarder) ---------------------------------------------------------------------
HOP = {"connection", "keep-alive", "proxy-connection", "transfer-encoding", "upgrade", "host", "te", "trailer",
       "content-length", "accept-encoding"}


def start_meter(log_path: str, upstream_host: str = "aiplatform.googleapis.com") -> int:
    lock = threading.Lock()

    class H(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _do(self):
            t0 = time.time()
            n = int(self.headers.get("content-length") or 0)
            body = self.rfile.read(n) if n else b""
            hdrs = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            hdrs["Accept-Encoding"] = "identity"
            conn = http.client.HTTPSConnection(upstream_host, context=ssl.create_default_context(), timeout=900)
            conn.request(self.command, self.path, body=body, headers=hdrs)   # path + query preserved
            r = conn.getresponse()
            tfb = time.time()
            self.send_response(r.status)
            for k, v in r.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            chunks = []
            while True:
                c = r.read1(65536)
                if not c:
                    break
                chunks.append(c)
                self.wfile.write(b"%x\r\n%s\r\n" % (len(c), c)); self.wfile.flush()
            self.wfile.write(b"0\r\n\r\n"); self.wfile.flush()
            conn.close()
            red = {k: ("REDACTED" if k.lower() in ("authorization", "x-goog-api-key", "x-api-key") else v)
                   for k, v in self.headers.items()}
            rec = {"t_start": t0, "t_first_byte": tfb, "t_end": time.time(), "method": self.command,
                   "host": upstream_host, "path": self.path, "status": r.status, "req_headers": red,
                   "resp_headers": dict(r.getheaders()), "req_body": body.decode("utf-8", "replace"),
                   "resp_body": b"".join(chunks).decode("utf-8", "replace")}
            with lock, open(log_path, "a") as f:
                f.write(json.dumps(rec) + "\n")

        do_GET = do_POST = _do

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)          # listening BEFORE the CLI starts (no startup race)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


# PTY driver ---------------------------------------------------------------------------------------------
class Pty:
    def __init__(self, argv, env, cwd, cast_path):
        self.screen = pyte.Screen(COLS, ROWS)
        self.stream = pyte.ByteStream(self.screen)
        self.lock = threading.Lock()
        self.t0 = time.time()
        self.last_change = self.t0
        self.cast = open(cast_path, "w")
        self.cast.write(json.dumps({"version": 2, "width": COLS, "height": ROWS, "timestamp": int(self.t0)}) + "\n")
        self.p = ptyprocess.PtyProcess.spawn(argv, env=env, cwd=cwd, dimensions=(ROWS, COLS))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            try:
                data = self.p.read(65536)
            except (EOFError, OSError):
                return
            with self.lock:
                self.cast.write(json.dumps([round(time.time() - self.t0, 4), "o", data.decode("utf-8", "replace")]) + "\n")
                self.stream.feed(data)
                self.last_change = time.time()

    def text(self) -> str:
        with self.lock:
            return "\n".join(self.screen.display)

    def write(self, b: bytes):
        with self.lock:
            self.cast.write(json.dumps([round(time.time() - self.t0, 4), "i", b.decode("utf-8", "replace")]) + "\n")
        self.p.write(b)

    def quiet_for(self) -> float:
        return time.time() - self.last_change

    def close(self, grace=8.0):
        end = time.time() + grace
        while self.p.isalive() and time.time() < end:
            time.sleep(0.1)
        for sig in (signal.SIGTERM, signal.SIGKILL):
            if self.p.isalive():
                try:
                    os.killpg(os.getpgid(self.p.pid), sig)
                except ProcessLookupError:
                    pass
                time.sleep(1.0)
        with self.lock:
            self.cast.close()
        return self.p.exitstatus


def answer_dialogs(pty: Pty, events: list):
    t = pty.text()
    for rx, keys in DIALOGS:
        if rx.search(t):
            pty.write(keys)
            events.append({"ts": time.time(), "type": "dialog_answered", "pattern": rx.pattern})
            time.sleep(0.5)
            return True
    return False


def wait_ready(pty: Pty, events: list, timeout=90.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if not pty.p.isalive():
            return False
        if answer_dialogs(pty, events):
            continue
        t = pty.text()
        if READY_RX.search(t) and BYPASS_FOOTER_RX.search(t) and not BUSY_RX.search(t) and pty.quiet_for() >= 1.5:
            return True
        time.sleep(0.1)
    return False


def count_lines(p):
    return sum(1 for l in open(p) if l.strip()) if os.path.exists(p) else 0


def submit_and_wait(pty: Pty, text: str, marker: str, events: list, timeout: float):
    n0 = count_lines(marker)
    pty.write(b"\x1b[200~" + text.encode() + b"\x1b[201~")
    time.sleep(0.3)
    pty.write(b"\r")
    t0 = time.time()
    events.append({"ts": t0, "type": "t0_enter"})
    end = t0 + timeout
    hook_seen = None
    while time.time() < end:
        answer_dialogs(pty, events)
        n = count_lines(marker)
        if n > n0 and hook_seen is None:
            hook_seen = time.time()
            events.append({"ts": hook_seen, "type": "stop_hook", "count": n})
        t = pty.text()
        idle = READY_RX.search(t) and not BUSY_RX.search(t)
        # Stop fires also when the main turn parks waiting for a background subagent, so require an idle screen too.
        if hook_seen and idle and pty.quiet_for() >= 3.0 and count_lines(marker) == n:
            events.append({"ts": time.time(), "type": "complete", "signal": "stop_hook+screen_idle"})
            return True
        if not hook_seen and idle and time.time() - t0 > 15 and pty.quiet_for() >= 10.0:
            events.append({"ts": time.time(), "type": "complete", "signal": "screen_idle_10s"})
            return True
        time.sleep(0.2)
    events.append({"ts": time.time(), "type": "timeout"})
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workspace", help="copied into the attempt workspace (default: empty dir)")
    ap.add_argument("--prompt", default="Create a file hello.txt containing exactly: hi\nThen reply with the single word DONE.")
    ap.add_argument("--model", default="claude-opus-5-5")
    ap.add_argument("--effort", choices=["low", "medium", "high", "xhigh", "max"], default="low")
    ap.add_argument("--meter", action="store_true", help="route model traffic through an in-process logging forwarder")
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="cc-attempt-")
    home, ws = os.path.join(scratch, "home"), os.path.join(scratch, "ws")
    os.makedirs(os.path.join(home, ".config/gcloud")); os.makedirs(os.path.join(home, "tmp"))
    if a.workspace:
        shutil.copytree(a.workspace, ws)
    else:
        os.makedirs(ws)
    ws = os.path.realpath(ws)                                    # trust key must be the realpath (/private/tmp/...)
    shutil.copy(ADC, os.path.join(home, ".config/gcloud/application_default_credentials.json"))
    os.chmod(os.path.join(home, ".config/gcloud/application_default_credentials.json"), 0o600)

    version = subprocess.run([CLAUDE, "--version"], capture_output=True, text=True,
                             env={"PATH": "/usr/bin:/bin", "HOME": home}).stdout.split()[0]
    cfg = os.path.join(home, ".claude")
    os.makedirs(cfg)
    marker = os.path.join(out, "stop_hook.jsonl")
    settings = {
        "theme": "dark",                                         # skips the theme picker
        "skipDangerousModePermissionPrompt": True,               # skips the bypass-permissions consent dialog
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": f"cat >> '{marker}'; echo >> '{marker}'"}]}]},
    }
    if a.effort != "max":                                        # effortLevel accepts low|medium|high|xhigh only
        settings["effortLevel"] = a.effort
    json.dump(settings, open(os.path.join(cfg, "settings.json"), "w"), indent=2)
    json.dump({"hasCompletedOnboarding": True, "lastOnboardingVersion": version,   # skips theme + security notes
               "projects": {ws: {"hasTrustDialogAccepted": True}}},             # skips the trust-folder dialog
              open(os.path.join(cfg, ".claude.json"), "w"), indent=2)

    env = {
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "TERM": "xterm-256color",
        "HOME": home, "TMPDIR": os.path.join(home, "tmp"),
        "CLAUDE_CODE_USE_VERTEX": "1", "ANTHROPIC_VERTEX_PROJECT_ID": PROJECT, "CLOUD_ML_REGION": LOCATION,
        "GOOGLE_CLOUD_QUOTA_PROJECT": PROJECT, "CLAUDE_CONFIG_DIR": cfg,
        "ANTHROPIC_MODEL": a.model,
        # Tier pins: a tier is "pinned" only by a model of the SAME family; otherwise Claude Code sends max_tokens=1
        # availability probes to claude-sonnet-4-5@20250929 / claude-haiku-4-5@20251001 at startup.
        "ANTHROPIC_DEFAULT_OPUS_MODEL": "claude-opus-5-5",
        "ANTHROPIC_DEFAULT_SONNET_MODEL": "claude-sonnet-5-5",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-5-5",
        "CLAUDE_CODE_SUBAGENT_MODEL": a.model,
        "DISABLE_AUTOUPDATER": "1", "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
    }
    meter_log = os.path.join(out, "meter.jsonl")
    if a.meter:
        port = start_meter(meter_log)
        env["ANTHROPIC_VERTEX_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
    session_id = str(uuid.uuid4())
    argv = [CLAUDE, "--dangerously-skip-permissions", "--session-id", session_id, "--effort", a.effort]
    json.dump({"argv": argv, "env": env, "version": version}, open(os.path.join(out, "launch.json"), "w"), indent=2)

    events: list = []
    pty = Pty(argv, env, ws, os.path.join(out, "session.cast"))
    ok = wait_ready(pty, events)
    events.append({"ts": time.time(), "type": "ready" if ok else "not_ready"})
    done = ok and submit_and_wait(pty, a.prompt, marker, events, a.timeout)
    open(os.path.join(out, "screen_final.txt"), "w").write(pty.text())
    pty.write(b"\x1b[200~/exit\x1b[201~"); time.sleep(0.3); pty.write(b"\r")
    rc = pty.close()
    events.append({"ts": time.time(), "type": "exit", "rc": rc})
    json.dump(events, open(os.path.join(out, "events.json"), "w"), indent=2)

    proj = os.path.join(cfg, "projects")
    if os.path.isdir(proj):
        shutil.copytree(proj, os.path.join(out, "projects"), dirs_exist_ok=True)
    print(json.dumps({"ready": ok, "completed": done, "rc": rc, "session_id": session_id,
                      "workspace_files": sorted(os.listdir(ws)), "out": out}, indent=2))
    shutil.rmtree(scratch, ignore_errors=True)                   # isolated HOME (with ADC copy) never archived


if __name__ == "__main__":
    main()
