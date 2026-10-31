"""Phase-0 reference: drive Pi's NATIVE INTERACTIVE TUI unattended against GEAP (Vertex AI) with ADC.

Standalone (needs only ptyprocess + pyte from the project venv):

    uv run python docs/spikes/pi_drive.py --out /tmp/x/run1 --model gemini-3.8-flash:low --meter \
        --prompt "Create hello.txt containing hi, then reply DONE."

Verified on Pi 1.4.0 (2026-10-30), see docs/spikes/pi.md:
  1. Fresh isolated HOME (only a 0600 copy of the user ADC file) + empty env + allowlist.
  2. Isolated agent dir (PI_CODING_AGENT_DIR) holding settings.json, optional models.json (Meter baseUrl) and a
     completion-marker extension in <agent-dir>/extensions/ (personal extensions need no project trust).
  3. Optional in-process Meter forwarder on 127.0.0.1 (google-vertex provider baseUrl override).
  4. `pi --provider google-vertex --model <id>:<level> --session-dir <out>/sessions` in a 220x60 PTY.
  5. Bracketed paste + Enter; t0 = the Enter write.
  6. Completion = extension `agent_settled` marker + idle screen (no "Working" spinner).
  7. `/quit`, then SIGTERM/SIGKILL; collects the session JSONL, marker log, cast and Meter log.
"""
from __future__ import annotations

import argparse, http.client, json, os, re, shutil, signal, ssl, subprocess, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import ptyprocess, pyte

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PI = os.path.join(ROOT, "tools/pi/node_modules/.bin/pi")
ADC = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
PROJECT, LOCATION = "your-gcp-project", "global"
COLS, ROWS = 220, 60

LEVELS = "off|minimal|low|medium|high|xhigh|max"
READY_RX = re.compile(rf"\S+ • ({LEVELS})\s*$", re.M)     # footer: "<model> • <thinking level>" (right-aligned)
BUSY_RX = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Working|Working\.\.\.|Retrying")

MARKER_EXT = r'''// geap-eval completion marker: one JSON line per lifecycle event -> $GEAP_MARKER_FILE
import { appendFileSync } from "node:fs";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
export default function (pi: ExtensionAPI) {
  const file = process.env.GEAP_MARKER_FILE;
  if (!file) return;
  const mark = (event: string, extra: Record<string, unknown> = {}) =>
    appendFileSync(file, JSON.stringify({ event, ts: Date.now() / 1000, ...extra }) + "\n");
  pi.on("session_start", async (_e, ctx) => mark("session_start", { sessionFile: ctx.sessionManager?.getSessionFile?.() }));
  pi.on("agent_start", async () => mark("agent_start"));
  pi.on("turn_end", async () => mark("turn_end"));
  pi.on("agent_end", async () => mark("agent_end"));          // NOT final: retries/compaction can start another run
  pi.on("agent_settled", async () => mark("agent_settled"));  // final idle: no automatic continuation remains
  pi.on("session_shutdown", async () => mark("session_shutdown"));
}
'''

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
            conn.request(self.command, self.path, body=body, headers=hdrs)
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

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


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

    def text(self):
        with self.lock:
            return "\n".join(self.screen.display)

    def write(self, b: bytes):
        with self.lock:
            self.cast.write(json.dumps([round(time.time() - self.t0, 4), "i", b.decode("utf-8", "replace")]) + "\n")
        self.p.write(b)

    def quiet_for(self):
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


def count(marker, ev):
    return sum(1 for l in open(marker) if f'"event":"{ev}"' in l) if os.path.exists(marker) else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--workspace")
    ap.add_argument("--prompt", default="Create a file hello.txt containing exactly: hi\nThen reply with the single word DONE.")
    ap.add_argument("--model", default="gemini-3.8-flash:low", help="<id>:<thinking>, e.g. gemini-4-argon:high")
    ap.add_argument("--meter", action="store_true")
    ap.add_argument("--fd-cache", help="path to an fd binary to pre-seed into <agent-dir>/bin (avoids a GitHub download)")
    ap.add_argument("--timeout", type=float, default=600)
    a = ap.parse_args()

    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    scratch = tempfile.mkdtemp(prefix="pi-attempt-")
    home, ws = os.path.join(scratch, "home"), os.path.join(scratch, "ws")
    os.makedirs(os.path.join(home, ".config/gcloud")); os.makedirs(os.path.join(home, "tmp"))
    shutil.copytree(a.workspace, ws) if a.workspace else os.makedirs(ws)
    ws = os.path.realpath(ws)
    shutil.copy(ADC, os.path.join(home, ".config/gcloud/application_default_credentials.json"))
    os.chmod(os.path.join(home, ".config/gcloud/application_default_credentials.json"), 0o600)

    agent = os.path.join(home, ".pi/agent")
    os.makedirs(os.path.join(agent, "extensions"))
    open(os.path.join(agent, "extensions/geap-marker.ts"), "w").write(MARKER_EXT)
    version = subprocess.run([PI, "--version"], capture_output=True, text=True,
                             env={"PATH": "/opt/homebrew/bin:/usr/bin:/bin", "HOME": home}).stdout.strip()
    # lastChangelogVersion suppresses the post-update changelog; nothing else is needed (Pi shows no first-run dialog).
    json.dump({"lastChangelogVersion": version}, open(os.path.join(agent, "settings.json"), "w"), indent=2)
    if a.fd_cache:
        os.makedirs(os.path.join(agent, "bin"))
        shutil.copy(a.fd_cache, os.path.join(agent, "bin/fd"))
    marker = os.path.join(out, "pi_marker.jsonl")
    env = {
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "TERM": "xterm-256color",
        "HOME": home, "TMPDIR": os.path.join(home, "tmp"),
        "GOOGLE_CLOUD_PROJECT": PROJECT, "GOOGLE_CLOUD_QUOTA_PROJECT": PROJECT, "GOOGLE_CLOUD_LOCATION": LOCATION,
        "PI_CODING_AGENT_DIR": agent, "PI_SKIP_VERSION_CHECK": "1", "PI_TELEMETRY": "0", "PI_OFFLINE": "1",
        "GEAP_MARKER_FILE": marker,
    }
    meter_log = os.path.join(out, "meter.jsonl")
    if a.meter:
        port = start_meter(meter_log)
        # The google-genai SDK does NOT add projects/<p>/locations/<l> to a custom baseUrl; include it (and /v1).
        json.dump({"providers": {"google-vertex": {
            "baseUrl": f"http://127.0.0.1:{port}/v1/projects/{PROJECT}/locations/{LOCATION}"}}},
            open(os.path.join(agent, "models.json"), "w"), indent=2)
    sessdir = os.path.join(out, "sessions")
    argv = [PI, "--provider", "google-vertex", "--model", a.model, "--session-dir", sessdir]
    json.dump({"argv": argv, "env": env, "version": version}, open(os.path.join(out, "launch.json"), "w"), indent=2)

    events = []
    pty = Pty(argv, env, ws, os.path.join(out, "session.cast"))
    end = time.time() + 60
    ok = False
    while time.time() < end and pty.p.isalive():
        t = pty.text()
        if READY_RX.search(t) and not BUSY_RX.search(t) and count(marker, "session_start") and pty.quiet_for() >= 1.5:
            ok = True
            break
        time.sleep(0.1)
    events.append({"ts": time.time(), "type": "ready" if ok else "not_ready"})
    done = False
    if ok:
        n0 = count(marker, "agent_settled")
        pty.write(b"\x1b[200~" + a.prompt.encode() + b"\x1b[201~"); time.sleep(0.3); pty.write(b"\r")
        t0 = time.time(); events.append({"ts": t0, "type": "t0_enter"})
        while time.time() < t0 + a.timeout:
            settled = count(marker, "agent_settled") > n0
            if settled and not BUSY_RX.search(pty.text()) and pty.quiet_for() >= 1.5:
                done = True
                events.append({"ts": time.time(), "type": "complete", "signal": "agent_settled+screen_idle"})
                break
            time.sleep(0.2)
    open(os.path.join(out, "screen_final.txt"), "w").write(pty.text())
    pty.write(b"\x1b[200~/quit\x1b[201~"); time.sleep(0.3); pty.write(b"\r")
    rc = pty.close()
    events.append({"ts": time.time(), "type": "exit", "rc": rc})
    json.dump(events, open(os.path.join(out, "events.json"), "w"), indent=2)
    print(json.dumps({"ready": ok, "completed": done, "rc": rc, "workspace_files": sorted(os.listdir(ws)),
                      "fd_downloaded": "fd not found. Downloading" in open(os.path.join(out, "session.cast")).read(),
                      "out": out}, indent=2))
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
