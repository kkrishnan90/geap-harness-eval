"""Antigravity CLI — native interactive TUI; Agent Platform auth via ADC (AGY_ADC_AUTH=1); Meter via HTTPS_PROXY (MITM).

Recipe: docs/spikes/agy.md (agy 1.4.11). Note: pre-seeding cache/onboarding.json accepts the GCP ToS screen.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from ..config import PROJECT
from ..guard import base_env
from ..pty_driver import DialogRule
from .base import Adapter, AttemptContext, LaunchSpec, PlaneA, ResolvedRole

READY = re.compile(r"^\? for shortcuts", re.M)
BUSY = re.compile(r"^esc to cancel|Loading\.\.\.", re.M)
LABELS = {"gemini-3.8-flash": "Gemini 3.8 Flash", "gemini-4-argon": "Gemini 4 Argon", "claude-opus-5-5": "Claude Opus 5.5",
          "claude-sonnet-5-5": "Claude Sonnet 5.5"}
LEVEL_LABEL = {"low": "Low", "medium": "Medium", "high": "High", "max": "Max"}

HOOK_SH = r"""#!/bin/sh
# geap_hook.sh <event>: append {ev, ts, payload} to the marker file, answer with a no-op decision
MARKER="__MARKER__"
EV="$1"
P=$(cat | tr -d '\n')
printf '{"ev":"%s","ts":%s,"payload":%s}\n' "$EV" "$(date +%s)" "${P:-null}" >> "$MARKER"
if [ "$EV" = "Stop" ]; then echo '{"decision":"stop"}'; else echo '{}'; fi
"""


def label(rr: ResolvedRole) -> str:
    return f"{LABELS[rr.model]} ({LEVEL_LABEL[rr.thinking]})"


def read_marker(marker: Path) -> list[dict]:
    out = []
    if marker.exists():
        for ln in marker.read_text().splitlines():
            try:
                out.append(json.loads(ln))
            except ValueError:
                pass
    return out


class Agy(Adapter):
    name = "agy"
    bin_name = "agy"
    pipeline_switch = True
    thinking_control = "model label (Low/Medium/High/Max): Argon thinkingLevel; Flash thinkingBudget 1000/4000/-1; Opus effort"
    meter_mode = "forward proxy (HTTPS_PROXY + SSL_CERT_FILE)"

    def bin_path(self) -> Path:
        return self.prefix / "bin/agy"

    def installed_version(self) -> str | None:
        if not self.bin_path().exists():
            return None
        r = subprocess.run([str(self.bin_path()), "--version"], capture_output=True, text=True, timeout=60)
        return r.stdout.strip().split()[-1] if r.stdout.strip() else None

    UPDATER = "https://antigravity-cli-auto-updater-974169037036.us-central1.run.app"

    def _manifest(self) -> dict:
        """Official release manifest (same source and SHA-512 check as Google's install.sh)."""
        import platform as _pf

        import httpx

        os_ = {"Darwin": "darwin", "Linux": "linux"}[_pf.system()]
        arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64", "aarch64": "arm64"}[_pf.machine().lower()]
        r = httpx.get(f"{self.UPDATER}/manifests/{os_}_{arch}.json", timeout=60)
        r.raise_for_status()
        return r.json()

    def latest_version(self) -> str | None:
        try:
            return self._manifest().get("version")
        except Exception:  # noqa: BLE001
            return None

    def install_latest(self) -> str:
        import hashlib
        import io
        import tarfile

        import httpx

        m = self._manifest()
        if self.installed_version() == m.get("version"):
            return m["version"]
        data = httpx.get(m["url"], timeout=600, follow_redirects=True).content
        if hashlib.sha512(data).hexdigest() != m["sha512"]:
            raise RuntimeError("agy download checksum mismatch: aborted")
        if ".tar.gz" in m["url"]:
            with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                data = tf.extractfile("antigravity").read()
        b = self.bin_path()
        b.parent.mkdir(parents=True, exist_ok=True)
        tmp = b.with_suffix(".new")
        tmp.write_bytes(data)
        tmp.chmod(0o755)
        tmp.replace(b)
        v = self.installed_version()
        if not v:
            raise RuntimeError("agy install failed")
        return v

    def model_reason(self, rr: ResolvedRole) -> str | None:
        if rr.model not in LABELS:
            return f"agy has no label for {rr.model}"
        if rr.thinking not in LEVEL_LABEL:
            return f"agy has no {rr.thinking!r} label (Low/Medium/High{'/Max' if rr.provider == 'anthropic' else ''})"
        if rr.thinking == "max" and rr.provider != "anthropic":
            return "agy Gemini labels stop at High"
        return None

    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        rr = ctx.roles.get("default") or next(iter(ctx.roles.values()))
        cli = ctx.home / ".gemini/antigravity-cli"
        (cli / "cache").mkdir(parents=True, exist_ok=True)
        cfgd = ctx.home / ".gemini/config"
        cfgd.mkdir(parents=True, exist_ok=True)
        ws = str(ctx.workspace)
        (cli / "settings.json").write_text(json.dumps({
            "gcp": {"project": PROJECT, "location": rr.location}, "colorScheme": "terminal", "showTips": False,
            "showFeedbackSurvey": False, "trustedWorkspaces": sorted({ws, os.path.realpath(ws)}),
            "artifactReviewPolicy": "always-proceed", "enableTelemetry": False}, indent=1))
        # accepts the Google Cloud ToS screen on the user's behalf (recorded in the run lock / attempt events)
        (cli / "cache/onboarding.json").write_text(json.dumps(
            {"consumerOnboardingComplete": False, "enterpriseOnboardingComplete": True, "onboardingComplete": False}))
        marker = ctx.artifacts / "agy_marker.jsonl"
        hook = cfgd / "geap_hook.sh"
        hook.write_text(HOOK_SH.replace("__MARKER__", str(marker)))
        hook.chmod(0o755)
        h = str(hook)
        (cfgd / "hooks.json").write_text(json.dumps({"geap-marker": {
            "SessionStart": [{"command": f"{h} SessionStart", "timeout": 10}],
            "PostToolUse": [{"matcher": "*", "hooks": [{"command": f"{h} PostToolUse", "timeout": 10}]}],
            "Stop": [{"command": f"{h} Stop", "timeout": 10}]}}, indent=1))
        env = base_env(ctx.home, {
            "GOOGLE_CLOUD_LOCATION": rr.location,
            "AGY_ADC_AUTH": "1",
            "AGY_CLI_DISABLE_AUTO_UPDATE": "1",
            "HTTPS_PROXY": ctx.meter_proxy,
            "SSL_CERT_FILE": str(ctx.meter_ca),
        }, path_prepend=[str(self.bin_path().parent)])
        argv = [str(self.bin_path()), "--dangerously-skip-permissions", "--model", label(rr)]
        dialogs = [DialogRule("trust-project", re.compile(r"Do you trust the contents of this project"), ["enter"], max_times=1)]

        def stops() -> int:
            return sum(1 for e in read_marker(marker) if e.get("ev") == "Stop" and (e.get("payload") or {}).get("fullyIdle"))

        return LaunchSpec(argv=argv, env=env, cwd=ctx.workspace.resolve(), ready=READY, busy=BUSY, dialogs=dialogs,
                          quit_keys=["/exit", "enter"], marker=marker, boot_timeout_s=120, done_counter=stops,
                          # start-up availability probes are non-streaming rawPredict; the agent loop always streams
                          aux_call=lambda c: c.get("method") in ("rawPredict", "predict"))

    def switch_model_keys(self, ctx: AttemptContext, role: str) -> list[str] | None:
        return [f"/model {label(ctx.roles[role])}", "\r"]

    def collect(self, ctx: AttemptContext) -> PlaneA:
        pa = PlaneA()
        out = ctx.artifacts / "plane_a"
        out.mkdir(exist_ok=True)
        cli = ctx.home / ".gemini/antigravity-cli"
        usage = {"tok_cache_read": 0}
        steps = 0
        for f in sorted(cli.glob("brain/*/.system_generated/logs/transcript_full.jsonl")):
            dst = out / f"{f.parts[-4]}-transcript_full.jsonl"
            dst.write_bytes(f.read_bytes())
            pa.session_files.append(dst)
            for ln in f.read_text().splitlines():
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("type") == "PLANNER_RESPONSE":
                    steps += 1
                    usage["tok_cache_read"] += r.get("cache_read_tokens") or 0
        for e in read_marker(ctx.artifacts / "agy_marker.jsonl"):
            if e.get("ev") != "PostToolUse":
                continue
            p = e.get("payload") or {}
            tc = p.get("toolCall") or {}
            err = p.get("error")
            pa.tool_calls.append({"call_id": f"step-{p.get('stepIdx')}", "parent_id": None, "name": tc.get("name"),
                                  "args_hash": hashlib.sha256(json.dumps(tc.get("args"), sort_keys=True, default=str).encode()).hexdigest()[:12],
                                  "status": "error" if err else "ok", "error_code": str(err)[:80] if err else None,
                                  "t_start": None, "t_end": float(e.get("ts") or 0)})
        pa.usage = usage
        pa.llm_turns = steps or None
        return pa


ADAPTER = Agy
