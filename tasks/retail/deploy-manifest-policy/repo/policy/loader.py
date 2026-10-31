"""Loads the manifests of one environment (deploy/<env>/*.json)."""

import json
from pathlib import Path

ENVIRONMENTS = ("dev", "staging", "prod")
KINDS = ("Deployment", "Service", "HorizontalPodAutoscaler")


class ManifestError(Exception):
    pass


def load_env(root, env):
    """Return {kind: [objects]} for every *.json file in root/env (sorted by file name)."""
    env_dir = Path(root) / env
    if not env_dir.is_dir():
        raise ManifestError(f"{env_dir} does not exist")
    found = {}
    for path in sorted(env_dir.glob("*.json")):
        try:
            obj = json.loads(path.read_text())
        except json.JSONDecodeError as e:
            raise ManifestError(f"{path}: invalid JSON: {e}") from e
        if not isinstance(obj, dict) or "kind" not in obj:
            raise ManifestError(f"{path}: not a manifest object")
        found.setdefault(obj["kind"], []).append(obj)
    return found


def load_lock(root):
    path = Path(root) / "images.lock.json"
    return json.loads(path.read_text())
