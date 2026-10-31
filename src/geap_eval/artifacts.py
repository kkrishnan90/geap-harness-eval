"""Artifact persistence for ephemeral containers: local RUNS_DIR mirrored to gs://<bucket>/runs/ (Cloud Run).

Attempt artifacts (casts, diffs, verifier output, session files) are uploaded once an attempt finishes; reads fall
back to downloading from the bucket when the local copy is gone (e.g. after an instance restart).
Disabled when GEAP_ARTIFACT_BUCKET is unset (local use).
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import PROJECT, RUNS_DIR

_SKIP = ("/home/", "/workspace/", "/documents/", "/dsh_home/", "/agents_home/")


def bucket_name() -> str | None:
    return os.environ.get("GEAP_ARTIFACT_BUCKET") or None


def _bucket():
    from google.cloud import storage

    return storage.Client(project=PROJECT).bucket(bucket_name())


def _key(local: Path) -> str:
    return "runs/" + local.resolve().relative_to(RUNS_DIR.resolve()).as_posix()


def upload_dir(local_dir: Path) -> int:
    """Upload every file under local_dir (never credential homes or scratch workspaces). Returns count."""
    if not bucket_name() or not local_dir.exists():
        return 0
    b, n = _bucket(), 0
    for p in local_dir.rglob("*"):
        if p.is_file() and not any(s in p.as_posix() for s in _SKIP) and p.name != "application_default_credentials.json":
            b.blob(_key(p)).upload_from_filename(str(p))
            n += 1
    return n


def upload_file(p: Path) -> None:
    if bucket_name() and p.exists():
        _bucket().blob(_key(p)).upload_from_filename(str(p))


def ensure_local(p: Path) -> Path:
    """Return p, downloading it from the bucket first if it is missing locally."""
    if p.exists() or not bucket_name():
        return p
    try:
        blob = _bucket().blob(_key(p))
        if blob.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(str(p))
    except Exception:  # noqa: BLE001 - best effort; caller handles a missing file
        pass
    return p
