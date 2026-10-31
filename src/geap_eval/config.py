"""Run configuration schema (single source of truth for CLI and UI)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Literal

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[2]
# Deployment-specific values live in a git-ignored .env (see .env.example); override=True so the project's .env
# wins over stray shell exports.
if os.environ.get("GEAP_SKIP_DOTENV") != "1":  # tests pin their own neutral values
    load_dotenv(ROOT / ".env", override=True)
PROJECT = os.environ.get("GEAP_PROJECT", "")     # the ONLY GCP project the app may touch (locked)
IDENTITY = os.environ.get("GEAP_IDENTITY", "")   # the only user ADC identity accepted locally
# Every location is overridable for the container (Cloud Run): data on local disk replicated to GCS.
RUNS_DIR = Path(os.environ.get("GEAP_RUNS_DIR", ROOT / "runs"))
TASKS_DIR = Path(os.environ.get("GEAP_TASKS_DIR", ROOT / "tasks"))
TOOLS_DIR = Path(os.environ.get("GEAP_TOOLS_DIR", ROOT / "tools"))
PRICING_DIR = Path(os.environ.get("GEAP_PRICING_DIR", ROOT / "pricing"))
# Workspaces + isolated HOMEs live OUTSIDE /Users/<user>: coding CLIs walk parent dirs for AGENTS.md/CLAUDE.md
# (a user-level AGENTS.md would leak into every benchmark agent). Realpath avoids /var -> /private/var trust-key mismatches.
WORK_ROOT = Path(os.environ.get("GEAP_WORK_ROOT", "/private/var/tmp/geap-eval-work" if sys.platform == "darwin"
                               else "/var/tmp/geap-eval-work"))

# Identity: locally the user's ADC (authorized_user, fixed email). On Cloud Run the attached service account's
# metadata-server ADC (short-lived tokens, no key files) — approved for the deployment only.
IDENTITY_MODE = os.environ.get("GEAP_IDENTITY_MODE", "user")  # user | service_account
SA_IDENTITY = os.environ.get("GEAP_SA_IDENTITY", f"geap-eval-runner@{PROJECT}.iam.gserviceaccount.com")

Thinking = Literal["off", "low", "medium", "high", "xhigh", "max"]
HARNESSES = ("claude_code", "pi", "omp", "dsh", "agy")


class RoleSpec(BaseModel):
    model: str
    thinking: Thinking = "medium"


class Sweep(BaseModel):
    model: str
    thinking: Literal["all_valid"] | list[Thinking] = "all_valid"


class ModelProfile(BaseModel):
    id: str
    mode: Literal["single", "native_roles", "pipeline"] = "single"
    roles: dict[str, RoleSpec] = Field(default_factory=dict)
    stages: list[dict] = Field(default_factory=list)  # pipeline: [{role, model, thinking}]
    sweep: Sweep | None = None

    @model_validator(mode="after")
    def _check(self) -> "ModelProfile":
        if self.sweep is None and self.mode != "pipeline" and "default" not in self.roles:
            raise ValueError(f"profile {self.id}: roles.default is required")
        if self.mode == "pipeline" and len(self.stages) < 2:
            raise ValueError(f"profile {self.id}: pipeline needs >= 2 stages")
        return self

    def models(self) -> set[str]:
        ms = {r.model for r in self.roles.values()} | {s["model"] for s in self.stages}
        if self.sweep:
            ms.add(self.sweep.model)
        return ms


class Geap(BaseModel):
    project: str = PROJECT
    identity: str = IDENTITY
    location: str = "auto"  # auto = per model from the availability probe

    @field_validator("project")
    @classmethod
    def _only_locked_project(cls, v: str) -> str:
        if not PROJECT:
            raise ValueError("GEAP_PROJECT is not set (copy .env.example to .env)")
        if v != PROJECT:
            raise ValueError(f"only project {PROJECT!r} is allowed, got {v!r}")
        return v

    @field_validator("identity")
    @classmethod
    def _only_identity(cls, v: str) -> str:
        if IDENTITY_MODE == "user" and v != IDENTITY:
            raise ValueError(f"only identity {IDENTITY!r} is allowed")
        return v


class RunSpec(BaseModel):
    name: str = "run"
    repeats: int = Field(3, ge=1, le=50)
    max_task_retries: int = Field(3, ge=0, le=10)
    retry_mode: Literal["fresh", "feedback"] = "fresh"
    max_infra_retries: int = Field(6, ge=0, le=20)


class TaskSelect(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["*"])
    tiers: list[Literal["simple", "medium", "complex"]] = Field(
        default_factory=lambda: ["simple", "medium", "complex"]
    )
    industries: list[str] = Field(default_factory=list)  # empty = all


class Limits(BaseModel):
    attempt_timeout_s: dict[str, int] = Field(
        default_factory=lambda: {"simple": 600, "medium": 1500, "complex": 3600}
    )
    max_nudges: int = 2
    quiescence_s: float = 10.0


class Budget(BaseModel):
    enabled: bool = False
    max_usd_total: float | None = None
    max_usd_per_attempt: float | None = None
    on_exceed: Literal["pause", "stop"] = "pause"


class Concurrency(BaseModel):
    global_: int = Field(4, alias="global", ge=1)
    per_harness: int = Field(2, ge=1)

    model_config = {"populate_by_name": True}


class HarnessSel(BaseModel):
    name: Literal["claude_code", "pi", "omp", "dsh", "agy"]
    variant: str = "default"  # dsh: "web-ptc" (default) | "web-native" (PTC-off control) | "acp-ptc"


class RunConfig(BaseModel):
    run: RunSpec = Field(default_factory=RunSpec)
    geap: Geap = Field(default_factory=Geap)
    versions: Literal["latest"] = "latest"
    harnesses: list[HarnessSel]
    model_profiles: list[ModelProfile]
    tasks: TaskSelect = Field(default_factory=TaskSelect)
    limits: Limits = Field(default_factory=Limits)
    budget: Budget = Field(default_factory=Budget)
    concurrency: Concurrency = Field(default_factory=Concurrency)

    @field_validator("harnesses", mode="before")
    @classmethod
    def _harness_shorthand(cls, v):
        alias = {"native": "web-native", "ptc": "web-ptc", "acp": "acp-ptc", "default": "web-ptc"}
        out = []
        for h in v:
            if isinstance(h, str):
                name, _, variant = h.partition("/")
                h = {"name": name, "variant": variant or "default"}
            if h.get("name") == "dsh":
                h["variant"] = alias.get(h.get("variant", "default"), h.get("variant", "default"))
            out.append(h)
        return out

    @field_validator("tasks", mode="before")
    @classmethod
    def _task_list(cls, v):
        return {"include": v} if isinstance(v, list) else v

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json", by_alias=True), sort_keys=True)

    def hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()[:16]


def load_config(path: str | Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(Path(path).read_text()))


def scan_for_foreign_projects(obj, path: str = "") -> list[str]:
    """Return paths of any string mentioning a GCP project other than the locked project."""
    import re

    bad: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            bad += scan_for_foreign_projects(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad += scan_for_foreign_projects(v, f"{path}[{i}]")
    elif isinstance(obj, str):
        for m in re.finditer(r"projects/([a-z][a-z0-9-]{4,28}[a-z0-9])", obj):
            if m.group(1) != PROJECT:
                bad.append(f"{path}: {m.group(0)}")
    return bad
