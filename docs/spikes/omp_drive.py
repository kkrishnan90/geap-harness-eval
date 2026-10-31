#!/usr/bin/env python3
"""Phase-0 reference driver: one unattended run of Oh My Pi (omp) in its NATIVE INTERACTIVE TUI on GEAP.

    uv run python docs/spikes/omp_drive.py --out /tmp/omp-run \
        --model google-vertex/gemini-3.8-flash:low --prompt "Create hello.txt ..." \
        [--slow google-vertex/claude-opus-5-5@default:high --then-role slow --then-prompt "..."] [--smol ...] [--plan ...]

What it does (see docs/spikes/omp.md for the verified facts behind every step):
  1. fresh isolated HOME (only a 0600 copy of user ADC + generated ~/.omp/agent/config.yml), fresh workspace
  2. starts an in-process spike Meter (HTTP CONNECT proxy; MITM of *.googleapis.com with a throwaway CA,
     everything else denied) and points omp at it with PI_PROXY_GOOGLE_VERTEX + NODE_EXTRA_CA_CERTS
  3. launches `omp -e <marker extension> --model <sel>` in a 220x60 PTY, empty env + allowlist
  4. waits for the ready signature, bracketed-pastes the prompt, presses Enter (t0)
  5. completion = extension `agent_end` marker with no further `agent_start` for 3s AND Meter idle
  6. optional in-session switch to another role model with Ctrl+P + second prompt
  7. `/exit` -> SIGTERM -> SIGKILL; collects session jsonl, marker, meter log, asciicast, screens into --out
Only the Python stdlib + ptyprocess + pyte + httpx (project venv) are needed. macOS/Linux.
"""
import argparse, base64, json, os, re, select, shutil, signal, socket, ssl, subprocess, sys, tempfile, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx, ptyprocess, pyte

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OMP_BIN = os.path.join(ROOT, "tools/omp/node_modules/.bin")  # contains omp AND bun>=1.4.4 (omp needs bun)
ADC = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
PROJECT, LOCATION = "your-gcp-project", "global"
COLS, ROWS = 220, 60

# ---- screen signatures (omp 18.14.0) ----
# The composer is a box whose top border is the status line: " π > ◔ Gemini 3.8 Flash > 🗑 <cwd> ▶─0.8%─..." and bottom "╰─".
# While a turn runs the leading "π" is replaced by a spinner + elapsed time ("⠹ 19s > ...") and "⎋ Working…" shows above.
READY_RX = re.compile(r"^ π > .*▶─", re.M)
BUSY_RX = re.compile(r"^ [⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] \d+s > |Working…", re.M)
DIALOG_RX = re.compile(r"Setup step \d+ of \d+|Select provider to login", re.M)  # must never appear with our config

CONFIG_YML = """\
# isolated ~/.omp/agent/config.yml for unattended GEAP runs
startup:
  setupWizard: false      # otherwise "Setup step 1 of 5 / Sign in to your providers" wizard blocks the TUI
  checkUpdate: false
  changelogMode: hidden
  quiet: true
telemetry:
  otlpExportEnabled: false
marketplace:
  autoUpdate: "off"
tools:
  approvalMode: yolo      # default already yolo; pinned so the policy is explicit (same as --auto-approve)
enabledProviders:
  - google-vertex
modelRoles:
{roles}
"""

MARKER_TS = r"""
import * as fs from "node:fs";
// GEAP completion marker: one JSON line per lifecycle event -> $GEAP_MARKER_FILE
export default function (pi: any) {
  const out = process.env.GEAP_MARKER_FILE;
  const w = (o: Record<string, unknown>) => { if (out) fs.appendFileSync(out, JSON.stringify({ ts: Date.now(), ...o }) + "\n"); };
  pi.on("session_start", async (_e: any, ctx: any) => w({ type: "session_start", sessionFile: ctx?.sessionManager?.getSessionFile?.() }));
  pi.on("agent_start", async () => w({ type: "agent_start" }));
  pi.on("turn_end", async () => w({ type: "turn_end" }));
  pi.on("agent_end", async (e: any) => {
    const msgs = Array.isArray(e?.messages) ? e.messages : [];
    const last = msgs[msgs.length - 1];
    w({ type: "agent_end", messages: msgs.length, stopReason: last?.stopReason, model: last?.model, usage: last?.usage });
  });
  pi.on("session_shutdown", async () => w({ type: "session_shutdown" }));
}
"""


# ------------------------------------------------------------------ spike Meter (CONNECT/MITM proxy)
class Meter:
    def __init__(self, logdir, ca_dir, mitm_suffix=(".googleapis.com",), deny_hosts=("play.googleapis.com",)):
        self.logdir, self.ca_dir, self.mitm_suffix, self.deny = logdir, ca_dir, tuple(mitm_suffix), set(deny_hosts)
        os.makedirs(logdir, exist_ok=True)
        self.lock = threading.Lock(); self.seq = 0; self.inflight = 0; self.last_end = 0.0
        self.client = httpx.Client(timeout=httpx.Timeout(900, connect=30))
        meter = self

        class H(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            mitm_host = None; token = None

            def log_message(self, *a):
                pass

            def do_CONNECT(self):
                host, _, port = self.path.partition(":")
                pa = self.headers.get("proxy-authorization", "")
                if pa.lower().startswith("basic "):
                    self.token = base64.b64decode(pa[6:]).decode(errors="replace").split(":")[0]
                if host in meter.deny or not host.endswith(meter.mitm_suffix):
                    meter.log({"t": time.time(), "method": "CONNECT", "host": host, "denied": True, "attempt_token": self.token})
                    self.send_response(403, "Forbidden by Meter"); self.send_header("content-length", "0"); self.end_headers()
                    self.close_connection = True
                    return
                self.send_response(200, "Connection Established"); self.end_headers(); self.wfile.flush()
                ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                ctx.load_cert_chain(f"{meter.ca_dir}/leaf.pem", f"{meter.ca_dir}/leaf.key")
                ctx.set_alpn_protocols(["http/1.1"])
                try:
                    conn = ctx.wrap_socket(self.connection, server_side=True)
                except Exception as e:
                    meter.log({"t": time.time(), "method": "CONNECT", "host": host, "tls_error": repr(e)})
                    self.close_connection = True
                    return
                self.connection, self.rfile, self.wfile = conn, conn.makefile("rb"), conn.makefile("wb")
                self.mitm_host = host; self.close_connection = False

            def _body(self):
                if self.headers.get("transfer-encoding", "").lower() == "chunked":
                    b = b""
                    while True:
                        size = int(self.rfile.readline().strip().split(b";")[0], 16)
                        if size == 0:
                            self.rfile.readline(); return b
                        b += self.rfile.read(size); self.rfile.readline()
                n = int(self.headers.get("content-length") or 0)
                return self.rfile.read(n) if n else b""

            def _do(self):
                with meter.lock:
                    meter.seq += 1; n = meter.seq; meter.inflight += 1
                try:
                    meter.forward(self, n)
                finally:
                    with meter.lock:
                        meter.inflight -= 1; meter.last_end = time.time()

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _do

        class Srv(ThreadingHTTPServer):
            request_queue_size = 256; daemon_threads = True

        self.srv = Srv(("127.0.0.1", 0), H)
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    HOP = {"host", "connection", "keep-alive", "proxy-connection", "proxy-authorization", "transfer-encoding",
           "upgrade", "te", "content-length", "accept-encoding"}

    def log(self, rec):
        with self.lock:
            with open(f"{self.logdir}/meter.jsonl", "a") as f:
                f.write(json.dumps(rec) + "\n")

    def forward(self, h, n):
        t0 = time.time(); body = h._body(); out = bytearray()
        hdrs = {k: v for k, v in h.headers.items() if k.lower() not in self.HOP}
        url = f"https://{h.mitm_host}{h.path}" if h.mitm_host else h.path
        secret = "oauth2.googleapis.com" in url or "/token" in url
        rec = {"seq": n, "attempt_token": h.token, "t_start": t0, "method": h.command, "url": url,
               "req_headers": {k: ("REDACTED" if k.lower() in ("authorization", "x-goog-api-key", "cookie") else v) for k, v in hdrs.items()},
               "req_bytes": len(body)}
        if not secret:
            open(f"{self.logdir}/{n:04d}.req.json", "wb").write(body)
        try:
            with self.client.stream(h.command, url, headers=hdrs, content=body) as r:
                rec["status"] = r.status_code
                h.send_response(r.status_code)
                for k, v in r.headers.items():
                    if k.lower() not in self.HOP and k.lower() != "content-encoding":
                        h.send_header(k, v)
                h.send_header("Transfer-Encoding", "chunked"); h.end_headers()
                for chunk in r.iter_bytes():
                    if chunk:
                        rec.setdefault("t_first_byte", time.time()); out += chunk
                        h.wfile.write(b"%x\r\n" % len(chunk) + chunk + b"\r\n"); h.wfile.flush()
                h.wfile.write(b"0\r\n\r\n"); h.wfile.flush()
        except Exception as e:
            rec["error"] = repr(e)  # e.g. BrokenPipe = client aborted mid-stream (the upstream call is still billed)
        finally:
            rec["resp_bytes"] = len(out)
            if not secret and out:
                open(f"{self.logdir}/{n:04d}.resp.txt", "wb").write(bytes(out))
        rec["t_end"] = time.time()
        self.log(rec)


def make_ca(d):
    """Throwaway CA + one leaf for *.googleapis.com (SAN + AKI/SKI: Python 3.13 and Go both require them)."""
    os.makedirs(d, exist_ok=True)
    run = lambda *a: subprocess.run(a, cwd=d, check=True, capture_output=True)
    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem", "-days", "2",
        "-subj", "/CN=GEAP Meter CA", "-addext", "basicConstraints=critical,CA:TRUE", "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", "/CN=googleapis.com")
    open(f"{d}/leaf.ext", "w").write("subjectAltName=DNS:*.googleapis.com,DNS:googleapis.com\nbasicConstraints=critical,CA:FALSE\n"
                                     "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
                                     "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
    run("openssl", "x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial", "-out", "leaf.pem",
        "-days", "1", "-extfile", "leaf.ext")


# ------------------------------------------------------------------ PTY + pyte
class Tui:
    def __init__(self, argv, env, cwd, cast):
        self.screen = pyte.Screen(COLS, ROWS); self.stream = pyte.ByteStream(self.screen)
        self.lock = threading.Lock(); self.t0 = time.time(); self.last_change = time.time()
        self.cast = open(cast, "w")
        self.cast.write(json.dumps({"version": 2, "width": COLS, "height": ROWS, "timestamp": int(self.t0)}) + "\n")
        self.p = ptyprocess.PtyProcess.spawn(argv, env=env, cwd=cwd, dimensions=(ROWS, COLS))
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            try:
                d = self.p.read(65536)
            except Exception:
                break
            if not d:
                break
            with self.lock:
                self.stream.feed(d); self.last_change = time.time()
                self.cast.write(json.dumps([round(time.time() - self.t0, 4), "o", d.decode("utf-8", "replace")]) + "\n")

    def send(self, b):
        if isinstance(b, str):
            b = b.encode()
        with self.lock:
            self.cast.write(json.dumps([round(time.time() - self.t0, 4), "i", b.decode("utf-8", "replace")]) + "\n")
        self.p.write(b)

    def text(self):
        with self.lock:
            return "\n".join(l.rstrip() for l in self.screen.display)

    def wait(self, rx, timeout, stable=0.0):
        end = time.time() + timeout
        while time.time() < end and self.p.isalive():
            if rx.search(self.text()) and time.time() - self.last_change >= stable:
                return True
            time.sleep(0.2)
        return False


def read_marker(path):
    try:
        return [json.loads(l) for l in open(path) if l.strip()]
    except FileNotFoundError:
        return []


def wait_done(tui, meter, marker, n_before, timeout):
    """Completion: an agent_end after our submission, no newer agent_start for 3s (omp auto-retries provider errors by
    starting a fresh agent loop), Meter has nothing in flight, and the composer is idle (no spinner)."""
    end = time.time() + timeout
    while time.time() < end:
        ev = read_marker(marker)[n_before:]
        ends = [i for i, e in enumerate(ev) if e["type"] == "agent_end"]
        starts = [i for i, e in enumerate(ev) if e["type"] == "agent_start"]
        if ends and (not starts or ends[-1] > starts[-1]):
            age = time.time() - ev[ends[-1]]["ts"] / 1000
            if age > 3 and meter.inflight == 0 and not BUSY_RX.search(tui.text()):
                return {"signal": "extension_agent_end", "agent_end": ev[ends[-1]], "detected_at": time.time()}
        if not tui.p.isalive():
            return {"signal": "process_exited"}
        time.sleep(0.25)
    return {"signal": "timeout"}


def type_cmd(tui, text):
    """Slash commands must be TYPED: a bracketed-paste "/model x" is submitted as an ordinary user message."""
    for ch in text:
        tui.send(ch); time.sleep(0.03)
    time.sleep(0.6)
    tui.send(b"\r")
    return time.time()


def submit(tui, text):
    tui.send(b"\x1b[200~" + text.encode() + b"\x1b[201~")
    time.sleep(0.4)
    tui.send(b"\r")
    return time.time()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="google-vertex/gemini-3.8-flash:low")
    ap.add_argument("--prompt", default="Create a file named hello.txt containing the single word hi, then run `cat hello.txt` with the shell, then reply DONE.")
    ap.add_argument("--then-role", help="role to Ctrl+P-cycle to before --then-prompt (e.g. slow; set it with --slow)")
    ap.add_argument("--then-prompt")
    ap.add_argument("--smol"); ap.add_argument("--slow"); ap.add_argument("--plan")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--keep-home", action="store_true")
    a = ap.parse_args()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="omp-attempt-")
    home, ws, tmp, ca = f"{work}/home", f"{work}/ws", f"{work}/tmp", f"{work}/ca"
    for d in (f"{home}/.config/gcloud", f"{home}/.omp/agent", ws, tmp):
        os.makedirs(d, exist_ok=True)
    shutil.copy(ADC, f"{home}/.config/gcloud/application_default_credentials.json")
    os.chmod(f"{home}/.config/gcloud/application_default_credentials.json", 0o600)
    roles = {"default": a.model}
    for r in ("smol", "slow", "plan"):
        if getattr(a, r):
            roles[r] = getattr(a, r)
    open(f"{home}/.omp/agent/config.yml", "w").write(CONFIG_YML.format(roles="\n".join(f"  {k}: {v}" for k, v in roles.items())))
    open(f"{work}/geap-marker.ts", "w").write(MARKER_TS)
    marker = f"{work}/marker.jsonl"
    make_ca(ca)
    meter = Meter(f"{out}/meter", ca)
    token = f"attempt-{int(time.time())}"
    env = {
        "PATH": f"{OMP_BIN}:/usr/bin:/bin:/usr/sbin:/sbin", "HOME": home, "LANG": "en_US.UTF-8", "TERM": "xterm-256color",
        "TMPDIR": tmp, "GOOGLE_CLOUD_PROJECT": PROJECT, "GOOGLE_CLOUD_QUOTA_PROJECT": PROJECT, "GOOGLE_CLOUD_LOCATION": LOCATION,
        # provider-scoped proxy: only google-vertex model traffic goes via the Meter (token refresh stays direct).
        "PI_PROXY_GOOGLE_VERTEX": f"http://{token}:x@127.0.0.1:{meter.port}",
        "NODE_EXTRA_CA_CERTS": f"{ca}/ca.pem", "GEAP_MARKER_FILE": marker,
    }
    argv = [f"{OMP_BIN}/omp", "-e", f"{work}/geap-marker.ts", "--model", a.model]
    rec = {"argv": argv, "env": {k: v for k, v in env.items()}, "work": work, "events": []}
    tui = Tui(argv, env, ws, f"{out}/session.cast")
    ok = tui.wait(READY_RX, 60, stable=1.5)
    rec["events"].append({"ev": "ready", "ok": ok, "t": time.time()})
    open(f"{out}/screen_ready.txt", "w").write(tui.text())
    if DIALOG_RX.search(tui.text()):
        rec["events"].append({"ev": "unexpected_dialog", "screen": tui.text()})
    prompts = [(None, a.prompt)] + ([(a.then_role, a.then_prompt)] if a.then_prompt else [])
    for i, (switch, text) in enumerate(prompts):
        if switch:
            # In-session switch = Ctrl+P (cycles the assigned role models: default -> slow -> ...). VERIFIED.
            # (`/model <selector>` typed in the TUI is NOT handled as a command in 18.14.0: it is sent to the model as
            #  a user message; the `/model` picker works but needs a multi-step key dance.)
            hit = False
            for _ in range(6):
                tui.send(b"\x10"); time.sleep(1.2)
                if re.search(rf"◀ {re.escape(switch)} ▶", tui.text()):
                    hit = True; break
            rec["events"].append({"ev": "model_switch", "to_role": switch, "ok": hit, "screen_tail": tui.text()[-600:]})
            tui.wait(READY_RX, 20, stable=1.0)
        n_before = len(read_marker(marker))
        t0 = submit(tui, text)
        rec["events"].append({"ev": "submit", "i": i, "t0": t0})
        done = wait_done(tui, meter, marker, n_before, a.timeout)
        done["t_end_meter"] = meter.last_end
        rec["events"].append({"ev": "done", "i": i, **done})
        open(f"{out}/screen_done_{i}.txt", "w").write(tui.text())
    # exit: /exit (bracketed paste + Enter), then SIGTERM, then SIGKILL on the process group
    type_cmd(tui, "/exit")
    t = time.time()
    while tui.p.isalive() and time.time() - t < 10:
        time.sleep(0.2)
    rec["events"].append({"ev": "exit", "clean": not tui.p.isalive(), "after_s": round(time.time() - t, 2)})
    for sig in (signal.SIGTERM, signal.SIGKILL):
        if tui.p.isalive():
            try:
                os.killpg(tui.p.pid, sig)
            except Exception:
                pass
            time.sleep(1.5)
    time.sleep(0.5)
    # collect Plane A: session jsonl(s) + marker
    sess = os.path.join(home, ".omp/agent/sessions")
    if os.path.isdir(sess):
        shutil.copytree(sess, f"{out}/sessions", dirs_exist_ok=True)
    if os.path.exists(marker):
        shutil.copy(marker, f"{out}/marker.jsonl")
    if os.path.isdir(f"{home}/.omp/logs"):
        shutil.copytree(f"{home}/.omp/logs", f"{out}/logs", dirs_exist_ok=True)
    shutil.copy(f"{home}/.omp/agent/config.yml", f"{out}/config.yml")
    shutil.copy(f"{work}/geap-marker.ts", f"{out}/geap-marker.ts")
    rec["env"]["PI_PROXY_GOOGLE_VERTEX"] = f"http://{token}:x@127.0.0.1:<port>"
    rec["workspace_files"] = sorted(os.listdir(ws))
    json.dump(rec, open(f"{out}/run.json", "w"), indent=1)
    if not a.keep_home:
        shutil.rmtree(home, ignore_errors=True)
    print(json.dumps({"out": out, "events": [{k: v for k, v in e.items() if k != "screen_tail"} for e in rec["events"]]}, indent=1, default=str))


if __name__ == "__main__":
    main()
