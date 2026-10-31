"""Credential Guard: ADC-only, locked-project-only, fixed identity; per-attempt env isolation."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass, field
from pathlib import Path

import google.auth
import google.auth.transport.requests
import httpx

from .config import IDENTITY, IDENTITY_MODE, PROJECT, SA_IDENTITY

ADC_PATH = Path.home() / ".config/gcloud/application_default_credentials.json"
ALLOWED_ADC_TYPES = {"authorized_user"}

SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"), "private key PEM"),
    (re.compile(r'"type"\s*:\s*"service_account"'), "service-account key JSON"),
    (re.compile(r"\b[A-Z0-9_]*API_KEY\b\s*[:=]\s*\S+"), "API key assignment"),
    (re.compile(r"\bapiKey\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"), "apiKey value"),
    (re.compile(r"AIza[0-9A-Za-z_\-]{35}"), "Google API key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "Anthropic API key"),
]
SECRET_FILENAMES = re.compile(r"(service[-_]?account.*\.json|antigravity-oauth-token|oauth_creds\.json)$", re.I)

# Never forwarded to harness processes.
ENV_DENY_PREFIXES = ("CLAUDE_CODE_", "ANTHROPIC_", "CLAUDECODE", "GEMINI_", "GOOGLE_API_KEY", "OPENAI_", "DEEPSEEK_")


@dataclass
class Posture:
    ok: bool
    identity: str | None = None
    project: str = PROJECT
    adc_type: str | None = None
    expires_in: int | None = None
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _token() -> tuple[str, str]:
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(google.auth.transport.requests.Request())
    return creds.token, type(creds).__module__ + "." + type(creds).__name__


def access_token() -> str:
    return _token()[0]


def check_posture() -> Posture:
    if IDENTITY_MODE == "service_account":
        return _check_sa_posture()
    issues: list[str] = []
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        issues.append("GOOGLE_APPLICATION_CREDENTIALS is set; only user ADC is allowed")
    if not ADC_PATH.exists():
        return Posture(False, issues=issues + [f"ADC file missing: {ADC_PATH} (run gcloud auth application-default login)"])
    adc = json.loads(ADC_PATH.read_text())
    adc_type = adc.get("type")
    if adc_type not in ALLOWED_ADC_TYPES:
        issues.append(f"ADC type {adc_type!r} not allowed (need authorized_user)")
    if adc.get("quota_project_id") not in (None, PROJECT):
        issues.append(f"ADC quota_project_id is {adc.get('quota_project_id')!r}, expected {PROJECT}")
    try:
        tok, _ = _token()
        info = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": tok}, timeout=15).json()
    except Exception as e:  # noqa: BLE001
        return Posture(False, adc_type=adc_type, issues=issues + [f"token mint failed: {e}"])
    email = info.get("email")
    exp = int(info.get("expires_in", 0))
    if email != IDENTITY:
        issues.append(f"ADC identity is {email!r}, expected {IDENTITY}")
    if exp > 3600:
        issues.append(f"token lifetime {exp}s exceeds 1h; not a short-lived credential")
    return Posture(not issues, identity=email, adc_type=adc_type, expires_in=exp, issues=issues)


def _check_sa_posture() -> Posture:
    """Cloud Run: ADC from the metadata server for the attached service account (short-lived tokens, no key file)."""
    issues: list[str] = []
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        issues.append("GOOGLE_APPLICATION_CREDENTIALS is set; Cloud Run must use the metadata-server identity")
    try:
        tok, kind = _token()
        info = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": tok}, timeout=15).json()
        # metadata tokens carry no email claim (no userinfo scope): ask the metadata server who we are
        email = info.get("email") or httpx.get(
            "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email",
            headers={"Metadata-Flavor": "Google"}, timeout=5).text.strip()
    except Exception as e:  # noqa: BLE001
        return Posture(False, adc_type="service_account(metadata)", issues=issues + [f"token mint failed: {e}"])
    if "compute_engine" not in kind:
        issues.append(f"credential source {kind} is not the metadata server")
    exp = int(info.get("expires_in", 0))
    if email != SA_IDENTITY:
        issues.append(f"identity is {email!r}, expected {SA_IDENTITY}")
    if exp > 3600:
        issues.append(f"token lifetime {exp}s exceeds 1h")
    return Posture(not issues, identity=email, adc_type="service_account(metadata)", expires_in=exp, issues=issues)


def scan_secrets(root: Path) -> list[str]:
    """Scan a generated config tree for anything that is not ADC."""
    found: list[str] = []
    for p in root.rglob("*"):
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.as_posix() == ".config/gcloud/application_default_credentials.json":
            continue
        if SECRET_FILENAMES.search(p.name):
            found.append(f"{rel}: forbidden credential file")
            continue
        if p.stat().st_size > 2_000_000:
            continue
        try:
            text = p.read_text(errors="ignore")
        except OSError:
            continue
        for rx, label in SECRET_PATTERNS:
            if rx.search(text):
                found.append(f"{rel}: {label}")
    return found


def make_isolated_home(home: Path) -> Path:
    """Create an empty HOME containing only a 0600 copy of the user ADC."""
    gc = home / ".config/gcloud"
    gc.mkdir(parents=True, exist_ok=True)
    if IDENTITY_MODE == "service_account":
        return home  # no credential file: harness auth libraries fall back to the metadata server (ADC)
    dst = gc / "application_default_credentials.json"
    shutil.copyfile(ADC_PATH, dst)
    dst.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return home


def base_env(home: Path, extra: dict[str, str] | None = None, path_prepend: list[str] | None = None) -> dict[str, str]:
    """Empty env + allowlist. Harness-specific GEAP vars come in via `extra`."""
    path = os.environ.get("PATH", "/usr/bin:/bin")
    path = ":".join(p for p in path.split(":") if ".claude" not in p and "claude-code" not in p)
    if path_prepend:
        path = ":".join(path_prepend) + ":" + path
    env = {
        "PATH": path,
        "HOME": str(home),
        "TMPDIR": str(home / "tmp"),
        "LANG": os.environ.get("LANG", "en_US.UTF-8"),
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "USER": os.environ.get("USER", "eval"),
        "SHELL": "/bin/bash",
        "GOOGLE_CLOUD_PROJECT": PROJECT,
        "GOOGLE_CLOUD_QUOTA_PROJECT": PROJECT,
        "CLOUDSDK_CORE_PROJECT": PROJECT,
        "NO_UPDATE_NOTIFIER": "1",
    }
    (home / "tmp").mkdir(parents=True, exist_ok=True)
    for k, v in (extra or {}).items():
        if k.startswith(ENV_DENY_PREFIXES) and k not in _HARNESS_ALLOWED_OVERRIDES:
            raise ValueError(f"env var {k} not allowed for harness processes")
        env[k] = v
    return env


# Harness adapters may set these specific vars (they configure Vertex, not keys).
_HARNESS_ALLOWED_OVERRIDES = {
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "ANTHROPIC_VERTEX_BASE_URL",
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
    "CLAUDE_CODE_USE_VERTEX",
    "CLAUDE_CODE_SUBAGENT_MODEL",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL",
}


def wait_token_fresh(min_remaining_s: int = 300) -> None:
    """ADC tokens are minted by each harness itself; this just ensures refresh works now."""
    t0 = time.time()
    _token()
    if time.time() - t0 > 30:
        raise RuntimeError("ADC token refresh is slow; check network")
