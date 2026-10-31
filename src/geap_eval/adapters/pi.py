"""Pi — native interactive TUI, vanilla google-vertex provider via ADC. Recipe: docs/spikes/pi.md (1.4.0)."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from ..config import PROJECT, TOOLS_DIR
from ..guard import base_env
from .base import Adapter, AttemptContext, LaunchSpec, PlaneA, ResolvedRole

LEVELS = "off|minimal|low|medium|high|xhigh|max"
# Claude on Vertex (Vertex AI mode, rawPredict via @anthropic-ai/vertex-sdk + ADC): community Pi extension,
# reviewed (deps: Anthropic SDK / Vertex SDK / google-auth-library; network: aiplatform.googleapis.com only).
VERTEX_EXT = "@pgilad/pi-vertex-anthropic"
CLAUDE_LEVELS = ("low", "medium", "high", "xhigh", "max")
READY = re.compile(rf"\S+ • ({LEVELS})\s*$", re.M)
BUSY = re.compile(r"[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Working|Working\.\.\.|Retrying")

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


def _ts(v) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1000 if v > 1e11 else float(v)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


def _h(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:12]


def count_events(marker: Path, event: str) -> int:
    if not marker.exists():
        return 0
    n = 0
    for ln in marker.read_text().splitlines():
        try:
            n += json.loads(ln).get("event") == event
        except ValueError:
            pass
    return n


class Pi(Adapter):
    name = "pi"
    npm_package = "@earendil-works/pi-coding-agent"
    bin_name = "pi"
    pipeline_switch = True
    thinking_control = ("--model <id>:<level>: Gemini thinkingConfig.thinkingLevel; Claude (Vertex SDK extension) "
                        "adaptive thinking + output_config.effort, mid-conversation effort keeps the prompt cache")
    meter_mode = "base_url (models.json providers.google-vertex.baseUrl incl. /v1/projects/.../locations/...)"

    def install_latest(self) -> str:
        v = super().install_latest()
        subprocess.run(["npm", "install", "--prefix", str(self.prefix), f"{VERTEX_EXT}@latest", "--ignore-scripts",
                        "--no-fund", "--no-audit"], check=True, capture_output=True, timeout=600)
        return v

    def ext_path(self) -> Path:
        return self.prefix / "node_modules" / VERTEX_EXT

    def model_reason(self, rr: ResolvedRole) -> str | None:
        if rr.provider == "anthropic":
            if not self.ext_path().exists():
                return f"Pi Claude-on-Vertex extension {VERTEX_EXT} not installed (geap-eval install pi)"
            return None if rr.thinking in CLAUDE_LEVELS else f"Pi/Claude effort {rr.thinking!r} unsupported (low..max)"
        if rr.thinking not in ("low", "medium", "high"):
            return f"Pi/Gemini thinking {rr.thinking!r} unsupported (low|medium|high)"
        return None

    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        rr = ctx.roles.get("default") or next(iter(ctx.roles.values()))
        agent = ctx.home / ".pi/agent"
        (agent / "extensions").mkdir(parents=True, exist_ok=True)
        (agent / "bin").mkdir(exist_ok=True)
        (agent / "settings.json").write_text(json.dumps({"lastChangelogVersion": self.installed_version()}))
        (agent / "models.json").write_text(json.dumps({"providers": {"google-vertex": {
            "baseUrl": f"{ctx.meter_base}/v1/projects/{PROJECT}/locations/{rr.location}"}}}))
        (agent / "extensions/geap-marker.ts").write_text(MARKER_EXT)
        fd = TOOLS_DIR / "pi/cache/fd"
        if fd.exists():  # avoids a first-run GitHub download
            shutil.copy2(fd, agent / "bin/fd")
        marker = ctx.artifacts / "pi_marker.jsonl"
        self._sessions = ctx.home / "pi_sessions"
        extra_env: dict[str, str] = {}
        if rr.provider == "anthropic":
            # extension's ADC sentinel skips its /login prompt; the Vertex SDK then reads ADC itself
            (agent / "auth.json").write_text(json.dumps({"vertex-anthropic": {
                "type": "oauth", "access": "adc", "refresh": "adc", "expires": int(time.time() * 1000) + 86_400_000,
                "projectId": PROJECT, "region": rr.location}}))
            extra_env = {"ANTHROPIC_VERTEX_PROJECT_ID": PROJECT, "CLOUD_ML_REGION": rr.location,
                         "ANTHROPIC_VERTEX_BASE_URL": f"{ctx.meter_base}/v1"}
        env = base_env(ctx.home, {
            **extra_env,
            "GOOGLE_CLOUD_LOCATION": rr.location,
            "PI_CODING_AGENT_DIR": str(agent),
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "PI_OFFLINE": "1",
            "GEAP_MARKER_FILE": str(marker),
        })
        if rr.provider == "anthropic":
            argv = [str(self.bin_path()), "-e", str(self.ext_path()), "--provider", "vertex-anthropic",
                    "--model", f"{rr.model}:{rr.thinking}", "--session-dir", str(self._sessions)]
        else:
            argv = [str(self.bin_path()), "--provider", "google-vertex", "--model", f"{rr.model}:{rr.thinking}",
                    "--session-dir", str(self._sessions)]
        return LaunchSpec(argv=argv, env=env, cwd=ctx.workspace.resolve(), ready=READY, busy=BUSY,
                          quit_keys=["/quit", "enter"], marker=marker,
                          done_counter=lambda: count_events(marker, "agent_settled"))

    def switch_model_keys(self, ctx: AttemptContext, role: str) -> list[str] | None:
        rr = ctx.roles[role]
        provider = "vertex-anthropic" if rr.provider == "anthropic" else "google-vertex"
        return [f"/model {provider}/{rr.model}", "\r", f"/thinking {rr.thinking}", "\r"]

    def collect(self, ctx: AttemptContext) -> PlaneA:
        pa = PlaneA()
        out = ctx.artifacts / "plane_a"
        out.mkdir(exist_ok=True)
        usage = {"tok_input": 0, "tok_cache_read": 0, "tok_output_incl_thinking": 0}
        calls: dict[str, dict] = {}
        turns = 0
        for f in sorted(self._sessions.glob("*.jsonl")):
            dst = out / f.name
            dst.write_bytes(f.read_bytes())
            pa.session_files.append(dst)
            for ln in f.read_text().splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("type") != "message":
                    continue
                m = r.get("message") or {}
                ts = _ts(r.get("timestamp") or m.get("timestamp"))
                if m.get("role") == "assistant":
                    turns += 1
                    u = m.get("usage") or {}
                    usage["tok_input"] += u.get("input", 0)
                    usage["tok_cache_read"] += u.get("cacheRead", 0)
                    usage["tok_output_incl_thinking"] += u.get("output", 0)
                    for b in m.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "toolCall":
                            calls[b["id"]] = {"call_id": b["id"], "parent_id": None, "name": b.get("name"),
                                              "args_hash": _h(b.get("arguments")), "status": "error",
                                              "error_code": "no_result", "t_start": ts, "t_end": None}
                elif m.get("role") == "toolResult" and m.get("toolCallId") in calls:
                    c = calls[m["toolCallId"]]
                    c["status"] = "error" if m.get("isError") else "ok"
                    c["error_code"] = "isError" if m.get("isError") else None
                    dur = m.get("durationMs")
                    c["t_end"] = (c["t_start"] + dur / 1000) if (dur is not None and c["t_start"]) else ts
        pa.usage = usage
        pa.llm_turns = turns or None
        pa.tool_calls = sorted(calls.values(), key=lambda c: c["t_start"] or 0)
        return pa


ADAPTER = Pi
