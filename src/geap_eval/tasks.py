"""Task loading, workspace preparation, hidden-test verification."""

from __future__ import annotations

import asyncio
import difflib
import fnmatch
import hashlib
import json
import shutil
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import TASKS_DIR, TaskSelect

IGNORE = shutil.ignore_patterns(".git", "node_modules", "target", "__pycache__", "*.class", ".DS_Store", "build", "out")


@dataclass
class Task:
    id: str
    version: str
    title: str
    industry: str
    tier: str
    sdlc_type: str
    languages: list[str]
    timeout_s: int
    path: Path

    @property
    def instruction(self) -> str:
        return (self.path / "instruction.md").read_text()

    def content_hash(self) -> str:
        h = hashlib.sha256()
        for p in sorted(self.path.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                h.update(p.relative_to(self.path).as_posix().encode())
                h.update(p.read_bytes())
        return h.hexdigest()[:12]

    def as_dict(self) -> dict:
        return {k: getattr(self, k) for k in ("id", "version", "title", "industry", "tier", "sdlc_type", "languages", "timeout_s")}


def load_tasks(root: Path = TASKS_DIR) -> list[Task]:
    out = []
    for toml in sorted(root.glob("*/*/task.toml")):
        d = tomllib.loads(toml.read_text())
        out.append(Task(d["id"], str(d["version"]), d["title"], d["industry"], d["tier"], d["sdlc_type"],
                        d.get("languages", []), int(d.get("timeout_s", 600)), toml.parent))
    return out


def select_tasks(sel: TaskSelect) -> list[Task]:
    out = []
    for t in load_tasks():
        if not any(fnmatch.fnmatch(t.id, pat) for pat in sel.include):
            continue
        if t.tier not in sel.tiers:
            continue
        if sel.industries and t.industry not in sel.industries:
            continue
        out.append(t)
    return out


def prepare_workspace(task: Task, dest: Path) -> Path:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(task.path / "repo", dest, ignore=IGNORE)
    return dest


async def verify(task: Task, workspace: Path, out_dir: Path, timeout_s: int = 900) -> dict:
    t0 = time.time()
    with tempfile.TemporaryDirectory(prefix="verify-") as td:
        work = Path(td) / "work"
        shutil.copytree(workspace, work, ignore=IGNORE)
        results = Path(td) / "results.json"
        proc = await asyncio.create_subprocess_exec(
            "bash", str(task.path / "tests/run.sh"), str(work), str(results),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, start_new_session=True)
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout_s)
        except asyncio.TimeoutError:
            import os, signal
            os.killpg(proc.pid, signal.SIGKILL)
            out = b"verifier timeout"
        (out_dir / "verifier.log").write_bytes(out[-200_000:])
        try:
            r = json.loads(results.read_text())
            f, p = r["fail_to_pass"], r["pass_to_pass"]
            res = {"ok": True, "f2p_passed": f["passed"], "f2p_total": f["total"], "p2p_passed": p["passed"],
                   "p2p_total": p["total"], "failed": f.get("failed", []) + p.get("failed", []),
                   "log_tail": r.get("log_tail", "")}
            res["passed"] = f["total"] > 0 and f["passed"] == f["total"] and p["passed"] == p["total"]
        except Exception as e:  # noqa: BLE001
            res = {"ok": False, "passed": False, "error": f"verifier produced no valid results.json: {e}",
                   "log_tail": out[-4000:].decode(errors="replace")}
    res["verify_s"] = time.time() - t0
    (out_dir / "verifier.json").write_text(json.dumps(res, indent=1))
    return res


def diff_stats(seed: Path, ws: Path) -> dict:
    def files(root: Path) -> dict[str, Path]:
        return {p.relative_to(root).as_posix(): p for p in root.rglob("*")
                if p.is_file() and not any(x in p.parts for x in (".git", "node_modules", "target", "__pycache__", "build", "out"))
                and not p.name.endswith(".class")}
    a, b = files(seed), files(ws)
    changed, lines, patch = 0, 0, []
    for rel in sorted(set(a) | set(b)):
        ta = a[rel].read_text(errors="replace").splitlines(keepends=True) if rel in a else []
        tb = b[rel].read_text(errors="replace").splitlines(keepends=True) if rel in b else []
        if ta == tb:
            continue
        changed += 1
        d = list(difflib.unified_diff(ta, tb, f"a/{rel}", f"b/{rel}"))
        lines += sum(1 for x in d if x[:1] in "+-" and not x.startswith(("+++", "---")))
        patch += d
    return {"diff_files": changed, "diff_lines": lines, "patch": "".join(patch)}
