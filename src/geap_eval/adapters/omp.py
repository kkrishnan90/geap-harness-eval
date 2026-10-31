"""Oh My Pi — native interactive TUI; google-vertex provider via ADC; Meter via PI_PROXY_GOOGLE_VERTEX (MITM).

Recipe: docs/spikes/omp.md (omp 18.14.0, bun >= 1.4.4 from tools/omp).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from ..guard import base_env
from ..pty_driver import DialogRule
from .base import Adapter, AttemptContext, LaunchSpec, PlaneA, ResolvedRole

READY = re.compile(r"^ π > .*▶─", re.M)
BUSY = re.compile(r"^ [⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] \d+s > |Working…", re.M)

CONFIG_YML = """\
# isolated ~/.omp/agent/config.yml for unattended GEAP runs (geap-eval)
startup:
  setupWizard: false
  checkUpdate: false
  changelogMode: hidden
  quiet: true
telemetry:
  otlpExportEnabled: false
marketplace:
  autoUpdate: "off"
tools:
  approvalMode: yolo
enabledProviders:
  - google-vertex
modelRoles:
{roles}
"""

MARKER_TS = r"""
import * as fs from "node:fs";
// geap-eval completion marker: one JSON line per lifecycle event -> $GEAP_MARKER_FILE
export default function (pi: any) {
  const out = process.env.GEAP_MARKER_FILE;
  const w = (o: Record<string, unknown>) => { if (out) fs.appendFileSync(out, JSON.stringify({ ts: Date.now(), ...o }) + "\n"); };
  pi.on("session_start", async (_e: any, ctx: any) => w({ type: "session_start", sessionFile: ctx?.sessionManager?.getSessionFile?.() }));
  pi.on("agent_start", async () => w({ type: "agent_start" }));
  pi.on("turn_end", async () => w({ type: "turn_end" }));
  pi.on("agent_end", async (e: any) => {
    const msgs = Array.isArray(e?.messages) ? e.messages : [];
    const last = msgs[msgs.length - 1];
    w({ type: "agent_end", messages: msgs.length, stopReason: last?.stopReason, model: last?.model });
  });
  pi.on("session_shutdown", async () => w({ type: "session_shutdown" }));
  // Vertex AI mode effort: omp's catalog marks google-vertex as rejecting output_config.effort (outdated for
  // Claude 5.5 rawPredict), so omp drops the level. Re-attach omp's own thinking level to Vertex Claude requests.
  const EFFORTS = new Set(["low", "medium", "high", "xhigh", "max"]);
  pi.on("before_provider_request", async (e: any, ctx: any) => {
    const p = e?.payload;
    // Called with the Anthropic params before omp's Vertex wrapper adds anthropic_version.
    const model = String(p?.model ?? ctx?.model?.id ?? "");
    if (!p || typeof p !== "object" || !Array.isArray(p.messages) || !model.includes("claude")) return undefined;
    if (!p.thinking || p.thinking.type !== "adaptive" || p.output_config?.effort) {
      w({ type: "effort_skip", model, thinking: p.thinking?.type ?? null, has_effort: !!p.output_config?.effort });
      return undefined;
    }
    let lvl = ctx?.getThinkingLevel?.() ?? pi?.getThinkingLevel?.() ?? process.env.GEAP_CLAUDE_EFFORT;
    if (lvl === "minimal") lvl = "low";
    if (!EFFORTS.has(lvl)) return undefined;
    w({ type: "effort_attached", effort: lvl });
    return { ...p, output_config: { ...(p.output_config ?? {}), effort: lvl } };
  });
}
"""

ROLE_MAP = {"default": "default", "plan": "plan", "slow": "slow", "smol": "smol", "task": "task", "subagent": "task"}


def selector(rr: ResolvedRole) -> str:
    if rr.provider == "anthropic":  # Vertex AI mode (google-vertex rawPredict); effort re-attached by the extension
        return f"google-vertex/{rr.model}@default:{rr.thinking}"
    return f"google-vertex/{rr.model}:{rr.thinking}"


def settled_agent_ends(marker: Path) -> int:
    """#agent_end once settled (no newer agent_start, >=3s old: omp restarts the loop after provider errors); else -1."""
    if not marker.exists():
        return 0
    evs = []
    for ln in marker.read_text().splitlines():
        try:
            evs.append(json.loads(ln))
        except ValueError:
            pass
    loop = [e for e in evs if e.get("type") in ("agent_start", "agent_end")]
    ends = sum(1 for e in loop if e["type"] == "agent_end")
    if not loop:
        return 0
    last = loop[-1]
    if last["type"] == "agent_end" and time.time() - last["ts"] / 1000 >= 3:
        return ends
    return -1


def _ts(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v / 1000 if v > 1e11 else float(v)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()


class Omp(Adapter):
    name = "omp"
    npm_package = "@oh-my-pi/pi-coding-agent"
    bin_name = "omp"
    roles_supported = tuple(ROLE_MAP)
    native_multi_model = True
    thinking_control = ("selector :level: Gemini thinkingLevel; Claude (Vertex rawPredict) adaptive + output_config.effort "
                        "re-attached via omp before_provider_request extension")
    meter_mode = "forward proxy (PI_PROXY_GOOGLE_VERTEX + NODE_EXTRA_CA_CERTS)"

    def install_latest(self) -> str:
        v = super().install_latest()
        bun = self.prefix / "node_modules/.bin/bun"
        if not bun.exists():
            subprocess.run(["npm", "install", "--prefix", str(self.prefix), "bun@latest", "--no-fund", "--no-audit"],
                           check=True, capture_output=True, timeout=600)
        return v

    def model_reason(self, rr: ResolvedRole) -> str | None:
        if rr.provider == "google" and rr.thinking not in ("low", "medium", "high"):
            return f"omp Gemini thinking {rr.thinking!r} unsupported"
        if rr.provider == "anthropic" and rr.thinking not in ("off", "low", "medium", "high", "xhigh", "max"):
            return f"omp Claude effort {rr.thinking!r} unsupported"
        return None

    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        rr = ctx.roles.get("default") or next(iter(ctx.roles.values()))
        agent = ctx.home / ".omp/agent"
        agent.mkdir(parents=True, exist_ok=True)
        roles = {ROLE_MAP[r]: selector(x) for r, x in ctx.roles.items()}
        roles.setdefault("default", selector(rr))
        (agent / "config.yml").write_text(CONFIG_YML.format(roles="\n".join(f"  {k}: {v}" for k, v in roles.items())))
        ext = ctx.workdir / "geap-marker.ts"
        ext.write_text(MARKER_TS)
        marker = ctx.artifacts / "omp_marker.jsonl"
        bindir = self.prefix / "node_modules/.bin"
        env = base_env(ctx.home, {
            "GOOGLE_CLOUD_LOCATION": rr.location,
            "PI_PROXY_GOOGLE_VERTEX": ctx.meter_proxy,
            "NODE_EXTRA_CA_CERTS": str(ctx.meter_ca),
            "GEAP_MARKER_FILE": str(marker),
            "GEAP_CLAUDE_EFFORT": next((r.thinking for r in ctx.roles.values() if r.provider == "anthropic"), ""),
        }, path_prepend=[str(bindir)])
        argv = [str(self.bin_path()), "-e", str(ext), "--model", roles["default"]]
        dialogs = [DialogRule("setup-wizard(unexpected)", re.compile(r"Setup step \d+ of \d+"), ["esc"], max_times=1)]
        return LaunchSpec(argv=argv, env=env, cwd=ctx.workspace.resolve(), ready=READY, busy=BUSY, dialogs=dialogs,
                          quit_keys=["/exit", "enter"], marker=marker, boot_timeout_s=120,
                          done_counter=lambda: settled_agent_ends(marker),
                          aux_call=lambda c: bool(c.get("hint_aux")))

    def collect(self, ctx: AttemptContext) -> PlaneA:
        pa = PlaneA()
        out = ctx.artifacts / "plane_a"
        out.mkdir(exist_ok=True)
        usage = {"tok_input": 0, "tok_cache_read": 0}
        calls: dict[str, dict] = {}
        turns = 0
        for f in sorted((ctx.home / ".omp/agent/sessions").rglob("*.jsonl")):
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
                ts = _ts(r.get("timestamp"))
                if m.get("role") == "assistant":
                    turns += 1
                    u = m.get("usage") or {}
                    usage["tok_input"] += u.get("input", 0)
                    usage["tok_cache_read"] += u.get("cacheRead", 0)
                    for b in m.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "toolCall":
                            calls[b["id"]] = {"call_id": b["id"], "parent_id": None, "name": b.get("name"),
                                              "args_hash": hashlib.sha256(json.dumps(b.get("arguments"), sort_keys=True, default=str).encode()).hexdigest()[:12],
                                              "status": "error", "error_code": "no_result", "t_start": ts, "t_end": None}
                elif m.get("role") == "toolResult" and m.get("toolCallId") in calls:
                    c = calls[m["toolCallId"]]
                    c["status"] = "error" if m.get("isError") else "ok"
                    c["error_code"] = "isError" if m.get("isError") else None
                    c["t_end"] = ts
        pa.usage = usage
        pa.llm_turns = turns or None
        pa.tool_calls = sorted(calls.values(), key=lambda c: c["t_start"] or 0)
        return pa


ADAPTER = Omp
