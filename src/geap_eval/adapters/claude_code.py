"""Claude Code — native interactive TUI on GEAP (Vertex) with ADC. Recipe: docs/spikes/claude_code.md (2.1.314)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime

from ..config import PROJECT
from ..guard import base_env
from ..pty_driver import DialogRule
from .base import Adapter, AttemptContext, LaunchSpec, PlaneA, ResolvedRole

READY = re.compile(r"(?ms)^❯(?:\s|$).*bypass permissions on")
BUSY = re.compile(r"esc to interrupt|Waiting for \d+ background agent|Retrying in \d+s")
EFFORTS = ("low", "medium", "high", "xhigh", "max")


def _ts(s: str | None) -> float | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _h(x) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:12]


class ClaudeCode(Adapter):
    name = "claude_code"
    npm_package = "@anthropic-ai/claude-code"
    bin_name = "claude"
    roles_supported = ("default", "subagent")
    native_multi_model = True
    pipeline_switch = True
    thinking_control = "--effort low|medium|high|xhigh|max (adaptive thinking + output_config.effort)"
    meter_mode = "base_url (ANTHROPIC_VERTEX_BASE_URL)"

    def model_reason(self, rr: ResolvedRole) -> str | None:
        if rr.provider != "anthropic":
            return "Claude Code on Vertex runs Claude models only"
        if rr.thinking not in EFFORTS:
            return f"Claude Code effort {rr.thinking!r} not supported (use {', '.join(EFFORTS)})"
        return None

    def supports(self, profile, roles):
        if profile.mode == "pipeline":
            for rr in roles.values():
                if rr.thinking != next(iter(roles.values())).thinking:
                    return "Claude Code pipeline: in-session /effort switch opens a confirm dialog; use one effort for all stages"
        return super().supports(profile, roles)

    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        rr = ctx.roles.get("default") or next(iter(ctx.roles.values()))
        sub = ctx.roles.get("subagent", rr)
        cfg = ctx.home / ".claude"
        cfg.mkdir(parents=True, exist_ok=True)
        marker = ctx.artifacts / "stop_hook.jsonl"
        self._session_id = str(uuid.uuid4())
        settings = {
            "theme": "dark",
            "skipDangerousModePermissionPrompt": True,
            "hooks": {"Stop": [{"hooks": [{"type": "command",
                                           "command": f"cat >> '{marker}'; echo >> '{marker}'"}]}]},
        }
        if rr.thinking != "max":
            settings["effortLevel"] = rr.thinking
        (cfg / "settings.json").write_text(json.dumps(settings, indent=1))
        ws = str(ctx.workspace.resolve())
        version = self.installed_version() or ""
        (cfg / ".claude.json").write_text(json.dumps({
            "hasCompletedOnboarding": True, "lastOnboardingVersion": version,
            "projects": {ws: {"hasTrustDialogAccepted": True}}}))
        env = base_env(ctx.home, {
            "CLAUDE_CODE_USE_VERTEX": "1",
            "ANTHROPIC_VERTEX_PROJECT_ID": PROJECT,
            "CLOUD_ML_REGION": rr.location,
            "CLAUDE_CONFIG_DIR": str(cfg),
            "ANTHROPIC_MODEL": rr.model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": rr.model if "opus" in rr.model else "claude-opus-5-5",
            # same-family pins stop startup probes to older tiers (claude-*-4-5); see spike §2
            "ANTHROPIC_DEFAULT_SONNET_MODEL": rr.model if "sonnet" in rr.model else "claude-sonnet-5-5",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-5-5",
            "CLAUDE_CODE_SUBAGENT_MODEL": sub.model,
            "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL": "1",
            "ANTHROPIC_VERTEX_BASE_URL": f"{ctx.meter_base}/v1",
        })
        argv = [str(self.bin_path()), "--dangerously-skip-permissions", "--session-id", self._session_id,
                "--effort", rr.thinking]
        models = {r.model for r in ctx.roles.values()}
        dialogs = [  # should never appear with the seeded config; answered (and counted) if they do
            DialogRule("trust-folder", re.compile(r"Is this a project you created or one you trust"), ["down", "enter"]),
            DialogRule("theme", re.compile(r"Choose the text style that looks best"), ["enter"]),
            DialogRule("security-notes", re.compile(r"Security notes:.*Press Enter to continue", re.S), ["enter"]),
            DialogRule("effort-confirm", re.compile(r"Change effort level\?"), ["1"]),
        ]
        return LaunchSpec(argv=argv, env=env, cwd=ctx.workspace.resolve(), ready=READY, busy=BUSY, dialogs=dialogs,
                          quit_keys=["/exit", "enter"], marker=marker,
                          done_counter=lambda: sum(1 for ln in marker.read_text().splitlines() if ln.strip()) if marker.exists() else 0,
                          aux_call=lambda c: c.get("model") not in models)

    def switch_model_keys(self, ctx: AttemptContext, role: str) -> list[str] | None:
        rr = ctx.roles[role]
        return [f"/model {rr.model}", "\r"]

    def collect(self, ctx: AttemptContext) -> PlaneA:
        pa = PlaneA()
        root = ctx.home / ".claude/projects"
        out = ctx.artifacts / "plane_a"
        out.mkdir(exist_ok=True)
        files = sorted(root.glob(f"*/{self._session_id}.jsonl")) + sorted(root.glob(f"*/{self._session_id}/subagents/*.jsonl"))
        seen_msgs: set[str] = set()
        usage = {"tok_input": 0, "tok_cache_read": 0, "tok_cache_write_5m": 0, "tok_cache_write_1h": 0, "tok_output": 0}
        calls: dict[str, dict] = {}
        for f in files:
            dst = out / f.name
            dst.write_bytes(f.read_bytes())
            pa.session_files.append(dst)
            if "/subagents/" in str(f):
                pa.subagents += 1
            for ln in f.read_text().splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                msg = r.get("message") or {}
                ts = _ts(r.get("timestamp"))
                if r.get("type") == "assistant":
                    mid = msg.get("id")
                    if mid and mid not in seen_msgs:  # one line per content block repeats usage: dedupe
                        seen_msgs.add(mid)
                        u = msg.get("usage") or {}
                        cc = u.get("cache_creation") or {}
                        usage["tok_input"] += u.get("input_tokens", 0)
                        usage["tok_cache_read"] += u.get("cache_read_input_tokens", 0)
                        usage["tok_cache_write_5m"] += cc.get("ephemeral_5m_input_tokens", u.get("cache_creation_input_tokens", 0) if not cc else 0)
                        usage["tok_cache_write_1h"] += cc.get("ephemeral_1h_input_tokens", 0)
                        usage["tok_output"] += u.get("output_tokens", 0)
                    for b in msg.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id") not in calls:
                            calls[b["id"]] = {"call_id": b["id"], "parent_id": r.get("agentId"), "name": b.get("name"),
                                              "args_hash": _h(b.get("input")), "status": "error", "error_code": "no_result",
                                              "t_start": ts, "t_end": None}
                elif r.get("type") == "user" and isinstance(msg.get("content"), list):
                    for b in msg["content"]:
                        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id") in calls:
                            c = calls[b["tool_use_id"]]
                            c["status"] = "error" if b.get("is_error") else "ok"
                            c["error_code"] = "is_error" if b.get("is_error") else None
                            c["t_end"] = ts
        pa.usage = usage
        pa.llm_turns = len(seen_msgs) or None
        pa.tool_calls = sorted(calls.values(), key=lambda c: c["t_start"] or 0)
        return pa


ADAPTER = ClaudeCode
