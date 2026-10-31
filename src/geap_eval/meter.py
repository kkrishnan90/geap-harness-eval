"""GEAP Meter: transparent streaming reverse proxy that records every model call.

URL shapes (base-URL override mode):
  /t/<token>/h/<upstream-host>/<path>   -> https://<upstream-host>/<path>
  /t/<token>/<path>                     -> https://<default host for token>/<path>
It forwards the caller's own Authorization header unchanged (credentials never handled here),
redacts it from logs, and refuses any upstream that is not *aiplatform.googleapis.com or any
path naming a project other than the locked project.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import httpx
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import Route

from .config import PROJECT

HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te", "trailers",
       "transfer-encoding", "upgrade", "host", "content-length", "accept-encoding"}
_MODEL_RX = re.compile(r"/locations/(?P<loc>[^/]+)/publishers/(?P<pub>google|anthropic)/models/(?P<model>[^:/]+):(?P<method>\w+)")
_PROJ_RX = re.compile(r"projects/([^/]+)/")


@dataclass
class TokenState:
    attempt_id: str
    default_host: str = "aiplatform.googleapis.com"
    seq: int = 0
    inflight: int = 0
    last_end: float = 0.0
    last_done: bool = False  # last response ended the turn with no tool calls
    last_hash: str | None = None
    last_failed: bool = False
    calls_ok: int = 0
    pending_tool_ids: dict = field(default_factory=dict)  # tool_use id -> name (anthropic)
    last_text: str = ""


Sink = Callable[[str, dict], Awaitable[None]]  # (kind, payload) kind in {"llm_call","tool_call"}


class Meter:
    def __init__(self, sink: Sink, host: str = "127.0.0.1", port: int = 0):
        self.sink = sink
        self.host, self.port = host, port
        self.tokens: dict[str, TokenState] = {}
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=30), http2=False)
        self.app = Starlette(routes=[
            Route("/t/{token}/{path:path}", self.handle, methods=["GET", "POST", "PUT", "DELETE", "PATCH"]),
            Route("/healthz", lambda r: JSONResponse({"ok": True})),
        ])
        self._server = None

    # ---------------------------------------------------------- lifecycle
    async def start(self) -> int:
        import uvicorn
        cfg = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning", lifespan="off")
        self._server = uvicorn.Server(cfg)
        self._task = asyncio.create_task(self._server.serve())
        while not self._server.started:
            await asyncio.sleep(0.05)
        self.port = self._server.servers[0].sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        srv = getattr(self, "_mitm_srv", None)
        if srv is not None:
            srv.close()  # don't wait_closed(): lingering TLS client sockets would block shutdown
        if self._server:
            self._server.should_exit = True
            try:
                await asyncio.wait_for(self._task, 10)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                self._task.cancel()
        await self.client.aclose()

    def register(self, token: str, attempt_id: str, default_host: str = "aiplatform.googleapis.com") -> str:
        self.tokens[token] = TokenState(attempt_id, default_host)
        return f"http://{self.host}:{self.port}/t/{token}"

    def unregister(self, token: str) -> None:
        self.tokens.pop(token, None)

    def state(self, token: str) -> TokenState | None:
        return self.tokens.get(token)

    # ---------------------------------------------------------- proxy
    async def handle(self, req: Request) -> Response:
        token = req.path_params["token"]
        st = self.tokens.get(token)
        if st is None:
            return JSONResponse({"error": "unknown meter token"}, status_code=403)
        path = req.path_params["path"]
        host = st.default_host
        if path.startswith("h/"):
            _, host, path = path.split("/", 2)
        if not (host == "aiplatform.googleapis.com" or host.endswith("-aiplatform.googleapis.com")):
            return JSONResponse({"error": f"upstream {host} not allowed"}, status_code=403)
        for p in _PROJ_RX.findall("/" + path):
            if p != PROJECT:
                return JSONResponse({"error": f"project {p} not allowed; only {PROJECT}"}, status_code=403)
        body = await req.body()
        headers = {k: v for k, v in req.headers.items() if k.lower() not in HOP}
        headers["accept-encoding"] = "identity"
        query = req.url.query
        url = f"https://{host}/{path}"
        if query:
            url += "?" + query
        st.seq += 1
        seq = st.seq
        st.inflight += 1
        t_start = time.time()
        rec = self._request_info(path, body)
        rec.update(seq=seq, t_start=t_start, attempt_id=st.attempt_id, url_path="/" + path)
        rhash = hashlib.sha256(body).hexdigest()[:16]
        rec["request_hash"] = rhash
        rec["is_retry"] = bool(st.last_failed and st.last_hash == rhash)
        await self._emit_tool_results(st, rec.pop("_tool_results", []))
        try:
            up = await self.client.send(
                self.client.build_request(req.method, url, headers=headers, content=body), stream=True)
        except Exception as e:  # network error
            st.inflight -= 1
            rec.update(t_end=time.time(), http_status=0, error_kind="network", error=str(e)[:300])
            st.last_failed, st.last_hash = True, rhash
            await self.sink("llm_call", rec)
            return JSONResponse({"error": f"meter upstream error: {e}"}, status_code=502)

        resp_headers = {k: v for k, v in up.headers.items() if k.lower() not in HOP | {"content-encoding"}}
        chunks: list[bytes] = []
        first = [None]

        async def gen():
            try:
                async for ch in up.aiter_bytes():
                    if first[0] is None:
                        first[0] = time.time()
                    chunks.append(ch)
                    yield ch
            finally:
                await up.aclose()
                st.inflight -= 1
                await self._finish(st, rec, up.status_code, b"".join(chunks), first[0])

        return StreamingResponse(gen(), status_code=up.status_code, headers=resp_headers)

    # ---------------------------------------------------------- parsing
    def _request_info(self, path: str, body: bytes) -> dict:
        m = _MODEL_RX.search("/" + path)
        info: dict = {"provider": None, "model": None, "location": None, "method": None, "stream": False,
                      "tools_defined": 0, "thinking_requested": None, "_tool_results": []}
        if m:
            info.update(provider="google" if m["pub"] == "google" else "anthropic",
                        model=m["model"].split("@")[0], location=m["loc"], method=m["method"],
                        stream=m["method"].startswith("stream"))
        info["hint_aux"] = any(m in body for m in (b"<title-request>", b"You name coding-agent sessions"))
        try:
            j = json.loads(body) if body else {}
        except ValueError:
            return info
        if not isinstance(j, dict):
            return info
        if info["provider"] == "google":
            info["tools_defined"] = sum(len(t.get("functionDeclarations") or t.get("function_declarations") or []) for t in j.get("tools") or [])
            gc = j.get("generationConfig") or j.get("generation_config") or {}
            tc = gc.get("thinkingConfig") or gc.get("thinking_config")
            info["thinking_requested"] = json.dumps(tc, sort_keys=True) if tc else None
            contents = j.get("contents") or []
            if contents:
                for part in contents[-1].get("parts") or []:
                    fr = part.get("functionResponse") or part.get("function_response")
                    if fr:
                        resp = fr.get("response") or {}
                        err = isinstance(resp, dict) and ("error" in resp or resp.get("isError") is True)
                        info["_tool_results"].append({"call_id": fr.get("id") or fr.get("name"), "name": fr.get("name"), "status": "error" if err else "ok"})
        elif info["provider"] == "anthropic":
            info["stream"] = info["stream"] or bool(j.get("stream"))
            info["tools_defined"] = len(j.get("tools") or [])
            th = {k: j[k] for k in ("thinking", "output_config") if k in j}
            # Vertex mid-conversation config: a per-message output_config overrides the top-level effort
            # (pi-ai supportsMidConvoEffort). The latest one is the effective effort for this request.
            mid = [m["output_config"].get("effort") for m in (j.get("messages") or [])
                   if isinstance(m, dict) and isinstance(m.get("output_config"), dict) and m["output_config"].get("effort")]
            if mid:
                th["effective_effort"] = mid[-1]
            info["thinking_requested"] = json.dumps(th, sort_keys=True) if th else None
            msgs = j.get("messages") or []
            if msgs and msgs[-1].get("role") == "user" and isinstance(msgs[-1].get("content"), list):
                for b in msgs[-1]["content"]:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        info["_tool_results"].append({"call_id": b.get("tool_use_id"), "status": "error" if b.get("is_error") else "ok"})
        return info

    async def _emit_tool_results(self, st: TokenState, results: list[dict]) -> None:
        for r in results:
            name = r.get("name") or st.pending_tool_ids.pop(r["call_id"], None)
            await self.sink("tool_call", {"attempt_id": st.attempt_id, "call_id": r["call_id"], "name": name,
                                          "status": r["status"], "source": "meter", "t_end": time.time()})

    async def _finish(self, st: TokenState, rec: dict, status: int, raw: bytes, t_first: float | None) -> None:
        rec.update(t_end=time.time(), t_first_byte=t_first, http_status=status)
        st.last_end = rec["t_end"]
        if status >= 400:
            rec["error_kind"] = classify_error(status, raw)
            rec["error"] = raw[:500].decode(errors="replace")
            st.last_failed, st.last_hash, st.last_done = True, rec["request_hash"], False
            await self.sink("llm_call", rec)
            return
        st.last_failed, st.last_hash = False, rec["request_hash"]
        if rec["provider"] == "google":
            parse_gemini(raw, rec)
        elif rec["provider"] == "anthropic":
            parse_anthropic(raw, rec)
            for tid, name in rec.pop("_tool_uses", []):
                st.pending_tool_ids[tid] = name
        if rec["provider"]:
            st.calls_ok += 1
            st.last_text = rec.get("text_tail") or ""
            st.last_done = rec.get("tool_calls_emitted", 0) == 0 and rec.get("stop_reason") in ("end_turn", "STOP", "stop_sequence", "MAX_TOKENS", "max_tokens")
        await self.sink("llm_call", rec)


def classify_error(status: int, raw: bytes) -> str:
    text = raw[:2000].decode(errors="ignore")
    if status == 429 or "RESOURCE_EXHAUSTED" in text:
        return "quota_daily" if re.search(r"per day|daily", text, re.I) else "quota"
    if status in (503, 529) or "overloaded" in text.lower():
        return "overloaded"
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "not_found"
    if status == 400:
        return "bad_request"
    return f"http_{status}"


def _iter_json_objects(raw: bytes):
    """Yield JSON objects from SSE (`data: ...`), a JSON array stream, or a single JSON body."""
    text = raw.decode(errors="replace").strip()
    if not text:
        return
    if "data:" in text[:200] or text.startswith("event:"):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload and payload != "[DONE]":
                    try:
                        yield json.loads(payload)
                    except ValueError:
                        continue
        return
    try:
        obj = json.loads(text)
    except ValueError:
        return
    if isinstance(obj, list):
        yield from (o for o in obj if isinstance(o, dict))
    elif isinstance(obj, dict):
        yield obj


def parse_gemini(raw: bytes, rec: dict) -> None:
    usage, fcalls, finish, version, traffic = None, 0, None, None, None
    texts: list[str] = []
    for o in _iter_json_objects(raw):
        if o.get("usageMetadata"):
            usage = o["usageMetadata"]
        version = o.get("modelVersion") or version
        for c in o.get("candidates") or []:
            finish = c.get("finishReason") or finish
            for p in (c.get("content") or {}).get("parts") or []:
                if "functionCall" in p:
                    fcalls += 1
                elif p.get("text") and not p.get("thought"):
                    texts.append(p["text"])
    u = usage or {}
    prompt = u.get("promptTokenCount", 0)
    cached = u.get("cachedContentTokenCount", 0)
    traffic = u.get("trafficType")
    rec.update(
        model_version=version, stop_reason=finish, tool_calls_emitted=fcalls, traffic_type=traffic,
        tok_input=prompt - cached, tok_cache_read=cached, tok_cache_write_5m=0, tok_cache_write_1h=0,
        tok_output=u.get("candidatesTokenCount", 0), tok_thinking=u.get("thoughtsTokenCount", 0),
        tok_tool_prompt=u.get("toolUsePromptTokenCount", 0), tok_total=u.get("totalTokenCount"),
        prompt_size=prompt, usage_raw=usage, usage_missing=usage is None, text_tail="".join(texts)[-400:],
    )


def parse_anthropic(raw: bytes, rec: dict) -> None:
    usage: dict = {}
    tool_uses: list[tuple[str, str]] = []
    stop, model_version, tier = None, None, None
    texts: list[str] = []
    for o in _iter_json_objects(raw):
        t = o.get("type")
        if t == "content_block_delta" and (o.get("delta") or {}).get("type") == "text_delta":
            texts.append(o["delta"].get("text", ""))
        if t == "message_start":
            m = o.get("message") or {}
            usage.update(m.get("usage") or {})
            model_version = m.get("model")
        elif t == "content_block_start":
            b = o.get("content_block") or {}
            if b.get("type") == "tool_use":
                tool_uses.append((b.get("id"), b.get("name")))
        elif t == "message_delta":
            for k, v in (o.get("usage") or {}).items():
                usage[k] = v  # cumulative counts in deltas
            stop = (o.get("delta") or {}).get("stop_reason") or stop
        elif t == "message" or ("usage" in o and "content" in o):
            usage.update(o.get("usage") or {})
            stop = o.get("stop_reason")
            model_version = o.get("model")
            for b in o.get("content") or []:
                if b.get("type") == "tool_use":
                    tool_uses.append((b.get("id"), b.get("name")))
                elif b.get("type") == "text":
                    texts.append(b.get("text", ""))
    cc = usage.get("cache_creation") or {}
    cw_total = usage.get("cache_creation_input_tokens", 0) or 0
    cw5 = cc.get("ephemeral_5m_input_tokens")
    cw1 = cc.get("ephemeral_1h_input_tokens")
    if cw5 is None and cw1 is None:
        cw5, cw1 = cw_total, 0  # default TTL is 5m
    tier = usage.get("service_tier")
    inp = usage.get("input_tokens", 0) or 0
    rd = usage.get("cache_read_input_tokens", 0) or 0
    rec.update(
        model_version=model_version, stop_reason=stop, tool_calls_emitted=len(tool_uses), traffic_type=tier,
        tok_input=inp, tok_cache_read=rd, tok_cache_write_5m=cw5 or 0, tok_cache_write_1h=cw1 or 0,
        tok_output=usage.get("output_tokens", 0) or 0, tok_thinking=0, tok_tool_prompt=0,
        tok_total=None, prompt_size=inp + rd + (cw5 or 0) + (cw1 or 0), usage_raw=usage or None,
        usage_missing=not usage, _tool_uses=tool_uses, text_tail="".join(texts)[-400:],
    )


# ====================================================================== forward proxy (MITM) mode
# For harnesses with no usable base-URL override (omp Gemini, agy): HTTP CONNECT proxy that terminates TLS for
# *.googleapis.com with a throwaway per-Meter CA and denies every other CONNECT. Model traffic (aiplatform) is replayed
# into the reverse-proxy path above (same parsing, project lock, attribution); auth/userinfo calls are forwarded
# without recording bodies. The attempt token arrives as proxy userinfo (Proxy-Authorization: Basic token:x).

import base64
import ssl
import subprocess
from pathlib import Path

import logging as _logging


class _QuietTLSClose(_logging.Filter):
    """MITM clients routinely drop TLS sockets mid-keepalive; asyncio logs each as noise."""

    def filter(self, rec: _logging.LogRecord) -> bool:
        return "SSL connection is closed" not in rec.getMessage()


_logging.getLogger("asyncio").addFilter(_QuietTLSClose())

MITM_DENY = {"play.googleapis.com"}  # Clearcut telemetry (401 under ADC anyway)
_HOP_RESP = {"connection", "keep-alive", "transfer-encoding", "content-length", "content-encoding", "proxy-authenticate"}


def make_ca(d: Path) -> Path:
    """Throwaway CA + one leaf for *.googleapis.com (SAN + SKI/AKI: Python 3.13 and Go require them)."""
    d.mkdir(parents=True, exist_ok=True)
    if (d / "leaf.pem").exists():
        return d

    def run(*a):
        subprocess.run(a, cwd=d, check=True, capture_output=True)

    run("openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", "ca.key", "-out", "ca.pem", "-days", "7",
        "-subj", "/CN=GEAP Meter CA (throwaway)", "-addext", "basicConstraints=critical,CA:TRUE",
        "-addext", "keyUsage=critical,keyCertSign,cRLSign")
    run("openssl", "req", "-newkey", "rsa:2048", "-nodes", "-keyout", "leaf.key", "-out", "leaf.csr", "-subj", "/CN=googleapis.com")
    (d / "leaf.ext").write_text("subjectAltName=DNS:*.googleapis.com,DNS:googleapis.com\nbasicConstraints=critical,CA:FALSE\n"
                                "keyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n"
                                "subjectKeyIdentifier=hash\nauthorityKeyIdentifier=keyid,issuer\n")
    run("openssl", "x509", "-req", "-in", "leaf.csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-CAcreateserial",
        "-out", "leaf.pem", "-days", "6", "-extfile", "leaf.ext")
    for f in ("ca.key", "leaf.key"):
        (d / f).chmod(0o600)
    return d


async def _read_headers(reader: asyncio.StreamReader) -> list[tuple[str, str]]:
    hs = []
    while True:
        ln = await reader.readline()
        if not ln or ln in (b"\r\n", b"\n"):
            return hs
        k, _, v = ln.decode("latin-1").partition(":")
        hs.append((k.strip(), v.strip()))


async def _read_body(reader: asyncio.StreamReader, hs: list[tuple[str, str]]) -> bytes:
    h = {k.lower(): v for k, v in hs}
    if h.get("transfer-encoding", "").lower() == "chunked":
        out = bytearray()
        while True:
            size = int((await reader.readline()).strip().split(b";")[0] or b"0", 16)
            if size == 0:
                await reader.readline()
                return bytes(out)
            out += await reader.readexactly(size)
            await reader.readline()
    n = int(h.get("content-length") or 0)
    return await reader.readexactly(n) if n else b""


class MitmMixin:
    """Mixed into Meter: start_mitm() + proxy_url(token)."""

    async def start_mitm(self, ca_dir: Path) -> int:
        self.ca_dir = make_ca(ca_dir)
        self.mitm_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.mitm_ctx.load_cert_chain(self.ca_dir / "leaf.pem", self.ca_dir / "leaf.key")
        self.mitm_ctx.set_alpn_protocols(["http/1.1"])
        self._mitm_srv = await asyncio.start_server(self._mitm_conn, "127.0.0.1", 0, backlog=512)
        self.mitm_port = self._mitm_srv.sockets[0].getsockname()[1]
        return self.mitm_port

    @property
    def ca_pem(self) -> Path:
        return self.ca_dir / "ca.pem"

    def proxy_url(self, token: str) -> str:
        return f"http://{token}:x@127.0.0.1:{self.mitm_port}"

    async def _mitm_conn(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        token = None
        try:
            line = await reader.readline()
            parts = line.decode("latin-1").split()
            hs = await _read_headers(reader)
            pa = next((v for k, v in hs if k.lower() == "proxy-authorization"), "")
            if pa.lower().startswith("basic "):
                token = base64.b64decode(pa[6:]).decode(errors="replace").split(":")[0]
            if len(parts) < 2 or parts[0] != "CONNECT":
                writer.write(b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n")
                return
            host = parts[1].rsplit(":", 1)[0]
            st = self.tokens.get(token or "")
            if st is None or host in MITM_DENY or not (host == "googleapis.com" or host.endswith(".googleapis.com")):
                if st is not None:
                    await self.sink("egress", {"attempt_id": st.attempt_id, "host": host, "action": "denied", "t": time.time()})
                writer.write(b"HTTP/1.1 403 Forbidden by GEAP Meter\r\nContent-Length: 0\r\n\r\n")
                return
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
            await writer.start_tls(self.mitm_ctx)
            while True:
                rl = await reader.readline()
                if not rl:
                    return
                method, path, _ = rl.decode("latin-1").split(" ", 2)
                rhs = await _read_headers(reader)
                body = await _read_body(reader, rhs)
                keep = await self._mitm_forward(st, token, host, method, path, rhs, body, writer)
                if not keep:
                    return
        except (ConnectionError, ssl.SSLError, asyncio.IncompleteReadError, ValueError, OSError):
            return
        finally:
            try:
                writer.close()
            except Exception:  # noqa: BLE001
                pass

    async def _mitm_forward(self, st, token, host, method, path, rhs, body, writer) -> bool:
        headers = {k: v for k, v in rhs if k.lower() not in HOP | {"proxy-connection", "proxy-authorization"}}
        model_host = host == "aiplatform.googleapis.com" or host.endswith("-aiplatform.googleapis.com")
        if model_host:  # replay into the recording reverse proxy
            url = f"http://127.0.0.1:{self.port}/t/{token}/h/{host}{path}"
        else:
            url = f"https://{host}{path}"
            await self.sink("egress", {"attempt_id": st.attempt_id, "host": host, "path": path.split("?")[0],
                                       "action": "forwarded", "t": time.time()})
        headers["accept-encoding"] = "identity"
        try:
            async with self.client.stream(method, url, headers=headers, content=body) as r:
                writer.write(f"HTTP/1.1 {r.status_code} {r.reason_phrase}\r\n".encode())
                for k, v in r.headers.items():
                    if k.lower() not in _HOP_RESP:
                        writer.write(f"{k}: {v}\r\n".encode("latin-1", "replace"))
                writer.write(b"Transfer-Encoding: chunked\r\n\r\n")
                async for ch in r.aiter_bytes():
                    if ch:
                        writer.write(b"%x\r\n" % len(ch) + ch + b"\r\n")
                        await writer.drain()
                writer.write(b"0\r\n\r\n")
                await writer.drain()
            return True
        except Exception:  # noqa: BLE001 - upstream/client abort
            return False


class _M(Meter, MitmMixin):
    pass


Meter = _M  # noqa: F811 - Meter with forward-proxy (MITM) capability
