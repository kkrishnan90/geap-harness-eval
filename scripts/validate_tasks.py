"""Validate benchmark task packages (docs/CONTRACTS.md §1).

Usage (from the project root):
    uv run python scripts/validate_tasks.py [task_id ...] [--keep] [--verbose]

For every task:
  * task.toml has every contract field with an allowed value, and id == path under tasks/
  * the package layout exists (instruction.md, repo/, tests/run.sh, solution/files/)
  * seed:   copy repo/ to a temp dir, run tests/run.sh -> F2P all fail, P2P all pass
  * oracle: copy repo/ + solution/files/ -> F2P and P2P all pass
  * instruction.md does not name hidden F2P tests

Prints a table and exits non-zero if any task is invalid. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = ROOT / "tasks"

INDUSTRIES = {"banking", "telecom", "retail", "oem-devices", "healthcare", "insurance", "logistics", "energy"}
TIERS = {"simple", "medium", "complex"}
SDLC_TYPES = {"bug-fix", "feature", "refactor", "test-authoring", "upgrade", "security", "performance", "ci-repair"}
TOOLS = {"python3", "node", "go", "cargo", "javac", "clang", "make", "sqlite3"}
REQUIRED_FIELDS = {
    "id": str, "version": str, "title": str, "industry": str, "tier": str,
    "sdlc_type": str, "languages": list, "timeout_s": int, "requires": list,
}


@dataclass
class Outcome:
    task_id: str
    tier: str = "?"
    lang: str = "?"
    seed: str = "-"
    oracle: str = "-"
    seconds: float = 0.0
    problems: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.problems


def discover(ids: list[str]) -> list[Path]:
    if ids:
        return [TASKS_DIR / i for i in ids]
    return sorted(p.parent for p in TASKS_DIR.glob("*/*/task.toml"))


def check_toml(task_dir: Path, out: Outcome) -> dict | None:
    path = task_dir / "task.toml"
    if not path.is_file():
        out.problems.append("task.toml missing")
        return None
    try:
        meta = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        out.problems.append(f"task.toml parse error: {e}")
        return None
    for key, typ in REQUIRED_FIELDS.items():
        if key not in meta:
            out.problems.append(f"task.toml: missing {key}")
        elif not isinstance(meta[key], typ) or (typ is int and isinstance(meta[key], bool)):
            out.problems.append(f"task.toml: {key} must be {typ.__name__}")
    if out.problems:
        return None
    rel = task_dir.relative_to(TASKS_DIR).as_posix()
    if meta["id"] != rel:
        out.problems.append(f"task.toml: id {meta['id']!r} != path {rel!r}")
    if meta["industry"] not in INDUSTRIES:
        out.problems.append(f"task.toml: bad industry {meta['industry']!r}")
    if rel.split("/")[0] != meta["industry"]:
        out.problems.append("task.toml: industry does not match directory")
    if meta["tier"] not in TIERS:
        out.problems.append(f"task.toml: bad tier {meta['tier']!r}")
    if meta["sdlc_type"] not in SDLC_TYPES:
        out.problems.append(f"task.toml: bad sdlc_type {meta['sdlc_type']!r}")
    if not meta["languages"] or not all(isinstance(x, str) and x for x in meta["languages"]):
        out.problems.append("task.toml: languages must be a non-empty list of strings")
    bad_tools = [t for t in meta["requires"] if t not in TOOLS]
    if bad_tools:
        out.problems.append(f"task.toml: unknown requires {bad_tools}")
    if meta["timeout_s"] <= 0:
        out.problems.append("task.toml: timeout_s must be > 0")
    if not meta["title"].strip() or not meta["version"].strip():
        out.problems.append("task.toml: empty title/version")
    missing = [t for t in meta["requires"] if shutil.which(t) is None]
    if missing:
        out.problems.append(f"host is missing required tools {missing}")
    out.tier = meta["tier"]
    out.lang = ",".join(meta["languages"])
    return meta


def check_layout(task_dir: Path, out: Outcome) -> bool:
    ok = True
    instr = task_dir / "instruction.md"
    if not instr.is_file() or not instr.read_text().strip():
        out.problems.append("instruction.md missing or empty")
        ok = False
    for d in ("repo", "tests", "solution/files"):
        if not (task_dir / d).is_dir():
            out.problems.append(f"{d}/ missing")
            ok = False
    if not (task_dir / "tests" / "run.sh").is_file():
        out.problems.append("tests/run.sh missing")
        ok = False
    junk = [p for p in (task_dir / "repo").rglob("*")
            if p.name in {"__pycache__", "target", ".DS_Store", "node_modules"} or p.suffix in {".class", ".o", ".pyc"}]
    if junk:
        out.problems.append(f"repo/ contains build artifacts: {[str(p.relative_to(task_dir)) for p in junk[:3]]}")
    shared = TASKS_DIR / "_shared" / "lib.sh"
    local = task_dir / "tests" / "lib.sh"
    if shared.is_file() and local.is_file() and shared.read_bytes() != local.read_bytes():
        out.problems.append("tests/lib.sh differs from tasks/_shared/lib.sh (re-copy it)")
    sol = task_dir / "solution" / "files"
    if sol.is_dir() and not any(p.is_file() for p in sol.rglob("*")):
        out.problems.append("solution/files/ is empty")
        ok = False
    return ok


def run_verifier(task_dir: Path, overlays: list[Path], timeout_s: int, keep: bool) -> tuple[dict | None, str]:
    tmp = Path(tempfile.mkdtemp(prefix="taskval-"))
    work = tmp / "work"
    try:
        shutil.copytree(overlays[0], work, symlinks=True)
        for extra in overlays[1:]:
            shutil.copytree(extra, work, symlinks=True, dirs_exist_ok=True)
        results = tmp / "results.json"
        try:
            proc = subprocess.run(
                ["bash", str(task_dir / "tests" / "run.sh"), str(work), str(results)],
                cwd=tmp, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=timeout_s,
            )
            output = proc.stdout.decode(errors="replace")
        except subprocess.TimeoutExpired:
            return None, f"run.sh exceeded {timeout_s}s"
        if not results.is_file():
            return None, "results JSON not written. " + output[-500:]
        try:
            data = json.loads(results.read_text())
        except json.JSONDecodeError as e:
            return None, f"invalid results JSON: {e}"
        return data, output
    finally:
        if keep:
            print(f"  kept {tmp}", file=sys.stderr)
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def shape_problems(data: dict) -> list[str]:
    probs = []
    for grp in ("fail_to_pass", "pass_to_pass"):
        g = data.get(grp)
        if not isinstance(g, dict):
            probs.append(f"results: {grp} missing")
            continue
        if not isinstance(g.get("passed"), int) or not isinstance(g.get("total"), int):
            probs.append(f"results: {grp}.passed/total not ints")
        if not isinstance(g.get("failed"), list):
            probs.append(f"results: {grp}.failed not a list")
        elif isinstance(g.get("passed"), int) and isinstance(g.get("total"), int):
            if g["total"] - g["passed"] != len(g["failed"]):
                probs.append(f"results: {grp} counts inconsistent")
    if not isinstance(data.get("log_tail"), str):
        probs.append("results: log_tail missing")
    return probs


def fmt(g: dict) -> str:
    return f"{g['passed']}/{g['total']}"


def check_leaks(task_dir: Path, out: Outcome) -> None:
    f2p = task_dir / "tests" / "expected_f2p.txt"
    instr = task_dir / "instruction.md"
    if not f2p.is_file() or not instr.is_file():
        return
    text = instr.read_text()
    for line in f2p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        leaf = line.replace("::", ".").replace("/", ".").split(".")[-1]
        if len(leaf) > 6 and leaf in text:
            out.problems.append(f"instruction.md names hidden test {leaf!r}")


def validate(task_dir: Path, keep: bool, verbose: bool) -> Outcome:
    rel = task_dir.relative_to(TASKS_DIR).as_posix() if task_dir.is_relative_to(TASKS_DIR) else str(task_dir)
    out = Outcome(rel)
    start = time.monotonic()
    meta = check_toml(task_dir, out)
    if not check_layout(task_dir, out) or meta is None:
        out.seconds = time.monotonic() - start
        return out
    check_leaks(task_dir, out)
    timeout = int(meta["timeout_s"])

    seed, log = run_verifier(task_dir, [task_dir / "repo"], timeout, keep)
    if seed is None:
        out.problems.append(f"seed: {log}")
    else:
        sp = shape_problems(seed)
        out.problems += [f"seed {p}" for p in sp]
        if not sp:
            f, p = seed["fail_to_pass"], seed["pass_to_pass"]
            out.seed = f"F2P {fmt(f)}  P2P {fmt(p)}"
            if f["total"] == 0:
                out.problems.append("seed: no F2P tests")
            if f["passed"] != 0:
                out.problems.append(f"seed: F2P should all fail, {f['passed']} passed")
            if p["total"] == 0:
                out.problems.append("seed: no P2P tests")
            if p["passed"] != p["total"]:
                out.problems.append(f"seed: P2P failing {p['failed'][:5]}")
        if verbose:
            print(f"--- {rel} seed log tail ---\n{seed.get('log_tail', '')[-1500:]}", file=sys.stderr)

    oracle, log = run_verifier(task_dir, [task_dir / "repo", task_dir / "solution" / "files"], timeout, keep)
    if oracle is None:
        out.problems.append(f"oracle: {log}")
    else:
        sp = shape_problems(oracle)
        out.problems += [f"oracle {p}" for p in sp]
        if not sp:
            f, p = oracle["fail_to_pass"], oracle["pass_to_pass"]
            out.oracle = f"F2P {fmt(f)}  P2P {fmt(p)}"
            if f["passed"] != f["total"] or f["total"] == 0:
                out.problems.append(f"oracle: F2P failing {f['failed'][:5]}")
            if p["passed"] != p["total"]:
                out.problems.append(f"oracle: P2P failing {p['failed'][:5]}")
        if verbose:
            print(f"--- {rel} oracle log tail ---\n{oracle.get('log_tail', '')[-1500:]}", file=sys.stderr)

    out.seconds = time.monotonic() - start
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("task_ids", nargs="*", help="task ids (path under tasks/); default: all")
    ap.add_argument("--keep", action="store_true", help="keep temp workdirs for debugging")
    ap.add_argument("--verbose", "-v", action="store_true", help="print verifier log tails")
    args = ap.parse_args()

    dirs = discover(args.task_ids)
    if not dirs:
        print("no tasks found", file=sys.stderr)
        return 2
    outcomes = []
    for d in dirs:
        print(f"validating {d.relative_to(ROOT) if d.is_relative_to(ROOT) else d} ...", file=sys.stderr, flush=True)
        outcomes.append(validate(d, args.keep, args.verbose))

    w = max(len(o.task_id) for o in outcomes)
    header = f"{'task':<{w}}  {'tier':<7}  {'lang':<10}  {'seed (want F2P 0/n, P2P n/n)':<30}  {'oracle (want all)':<26}  {'time':>6}  status"
    print(header)
    print("-" * len(header))
    for o in outcomes:
        status = "VALID" if o.valid else "INVALID"
        print(f"{o.task_id:<{w}}  {o.tier:<7}  {o.lang:<10}  {o.seed:<30}  {o.oracle:<26}  {o.seconds:>5.1f}s  {status}")
        for p in o.problems:
            print(f"{'':<{w}}    ! {p}")
    n_bad = sum(not o.valid for o in outcomes)
    print(f"\n{len(outcomes) - n_bad}/{len(outcomes)} tasks VALID")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
