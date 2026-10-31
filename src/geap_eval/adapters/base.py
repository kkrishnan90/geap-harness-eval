"""Harness adapter contract (native interactive mode only)."""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..config import TOOLS_DIR, ModelProfile
from ..pty_driver import DialogRule
from ..tasks import Task


@dataclass
class ResolvedRole:
    model: str
    thinking: str
    location: str
    provider: str


@dataclass
class AttemptContext:
    attempt_id: str
    trial_id: str
    task: Task
    workspace: Path
    home: Path
    artifacts: Path
    meter_base: str  # http://127.0.0.1:<port>/t/<token>
    roles: dict[str, ResolvedRole]
    profile: ModelProfile
    variant: str
    prompt: str
    workdir: Path | None = None  # per-attempt scratch root outside $HOME (holds workspace + home)
    meter_proxy: str | None = None  # http://<token>:x@127.0.0.1:<port> (forward/MITM mode)
    meter_ca: Path | None = None  # CA for MITM mode (NODE_EXTRA_CA_CERTS / SSL_CERT_FILE)


@dataclass
class LaunchSpec:
    argv: list[str]
    env: dict[str, str]
    cwd: Path
    ready: re.Pattern  # input box visible / idle prompt
    busy: re.Pattern | None = None  # spinner / "esc to interrupt" etc.
    dialogs: list[DialogRule] = field(default_factory=list)
    quit_keys: list[str] = field(default_factory=lambda: ["ctrl_c", "ctrl_c"])
    marker: Path | None = None  # completion hook marker file (appended per turn)
    bracketed_paste: bool = True
    boot_timeout_s: float = 90.0
    plane_b: bool = True  # model traffic routed through the Meter
    done_counter: "Callable[[], int] | None" = None  # monotonic native completion count (dsh turn/end, pi agent_settled)
    aux_call: "Callable[[dict], bool] | None" = None  # harness-internal calls (e.g. session titles): billed, not timed


@dataclass
class PlaneA:
    tool_calls: list[dict] = field(default_factory=list)  # {call_id,parent_id,name,args_hash,status,error_code,t_start,t_end}
    usage: dict = field(default_factory=dict)  # summed tok_* as self-reported by the harness
    llm_turns: int | None = None
    subagents: int = 0
    session_files: list[Path] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


class Adapter:
    name: str = "base"
    driver: str = "pty"  # pty | browser
    npm_package: str | None = None
    bin_name: str | None = None
    roles_supported: tuple[str, ...] = ("default",)
    native_multi_model: bool = False
    pipeline_switch: bool = False
    thinking_control: str = "none"
    meter_mode: str = "base_url"

    def __init__(self, variant: str = "default"):
        self.variant = variant

    # ---------------------------------------------------------- install / version
    @property
    def prefix(self) -> Path:
        return TOOLS_DIR / self.name

    def bin_path(self) -> Path:
        return self.prefix / "node_modules/.bin" / self.bin_name

    def latest_version(self) -> str | None:
        if not self.npm_package:
            return None
        r = subprocess.run(["npm", "view", self.npm_package, "version"], capture_output=True, text=True, timeout=60)
        return r.stdout.strip() or None

    def installed_version(self) -> str | None:
        pj = self.prefix / "node_modules" / self.npm_package / "package.json" if self.npm_package else None
        if pj and pj.exists():
            return json.loads(pj.read_text())["version"]
        return None

    def install_latest(self) -> str:
        latest = self.latest_version()
        if latest and latest != self.installed_version():
            self.prefix.mkdir(parents=True, exist_ok=True)
            cmd = ["npm", "install", "--prefix", str(self.prefix), f"{self.npm_package}@{latest}", "--no-fund", "--no-audit"]
            cmd += self.npm_extra_args()
            subprocess.run(cmd, check=True, capture_output=True, timeout=900)
        v = self.installed_version()
        if not v:
            raise RuntimeError(f"{self.name}: install failed")
        return v

    def npm_extra_args(self) -> list[str]:
        return []

    # ---------------------------------------------------------- capability checks
    def capabilities(self) -> dict:
        return {"roles": list(self.roles_supported), "native_multi_model": self.native_multi_model,
                "pipeline": self.pipeline_switch, "thinking_control": self.thinking_control,
                "meter_mode": self.meter_mode, "driver": self.driver}

    def supports(self, profile: ModelProfile, roles: dict[str, ResolvedRole]) -> str | None:
        """Return None if runnable, else the N/A reason."""
        if profile.mode == "native_roles":
            if not self.native_multi_model:
                return f"{self.name} has no native multi-model roles"
            extra = set(roles) - set(self.roles_supported)
            if extra:
                return f"{self.name} cannot express roles {sorted(extra)}"
        if profile.mode == "pipeline" and not self.pipeline_switch:
            return f"{self.name} cannot switch models in-session (pipeline)"
        for r, rr in roles.items():
            reason = self.model_reason(rr)
            if reason:
                return reason
        return None

    def model_reason(self, rr: ResolvedRole) -> str | None:
        return None

    # ---------------------------------------------------------- run
    def prepare(self, ctx: AttemptContext) -> LaunchSpec:
        raise NotImplementedError

    def switch_model_keys(self, ctx: AttemptContext, role: str) -> list[str] | None:
        return None

    def collect(self, ctx: AttemptContext) -> PlaneA:
        return PlaneA()


def copy_tree_into(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copytree(src, dst, dirs_exist_ok=True)


async def run_cmd(*argv: str, timeout: float = 60, **kw) -> tuple[int, str]:
    p = await asyncio.create_subprocess_exec(*argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, **kw)
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill()
        return -1, "timeout"
    return p.returncode, out.decode(errors="replace")
