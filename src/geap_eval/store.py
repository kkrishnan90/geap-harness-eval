"""SQLite store (WAL) — schema per docs/CONTRACTS.md §3. Single-writer from the asyncio loop."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .config import RUNS_DIR

import os as _os

DB_PATH = Path(_os.environ.get("GEAP_DB_PATH", RUNS_DIR / "geap-eval.db"))

TOK = "tok_input INT, tok_cache_read INT, tok_cache_write_5m INT, tok_cache_write_1h INT, tok_output INT, tok_thinking INT, tok_tool_prompt INT"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, name TEXT, status TEXT, config_json TEXT, config_hash TEXT, lock_json TEXT,
  created_at REAL, started_at REAL, finished_at REAL);
CREATE TABLE IF NOT EXISTS trials (
  id TEXT PRIMARY KEY, run_id TEXT, task_id TEXT, task_version TEXT, tier TEXT, industry TEXT, sdlc_type TEXT,
  harness TEXT, harness_version TEXT, variant TEXT, profile_id TEXT, profile_json TEXT, repeat_idx INT,
  status TEXT, na_reason TEXT, attempts_used INT DEFAULT 0, infra_retries INT DEFAULT 0, passed_on_attempt INT,
  time_to_success_s REAL, cost_usd REAL, cost_status TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS attempts (
  id TEXT PRIMARY KEY, trial_id TEXT, run_id TEXT, idx INT, kind TEXT, status TEXT, exit_class TEXT,
  t_queued REAL, t0 REAL, t_end REAL, t_verified REAL, wall_s REAL, llm_s REAL, tool_s REAL, overhead_s REAL,
  verify_s REAL, ttft_ms REAL, prompt_submissions INT, nudges INT, dialogs INT, llm_turns INT, llm_calls INT,
  llm_retries INT, llm_errors INT, tool_calls INT, tool_ok INT, tool_fail INT, tool_retry INT, subagents INT,
  {TOK}, cost_usd REAL, cost_status TEXT, passed INT, f2p_passed INT, f2p_total INT, p2p_passed INT,
  p2p_total INT, diff_files INT, diff_lines INT, completion_signal TEXT, thinking_verified TEXT,
  artifacts_dir TEXT, error TEXT, updated_at REAL);
CREATE TABLE IF NOT EXISTS llm_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT, seq INT, t_start REAL, t_first_byte REAL, t_end REAL,
  http_status INT, error_kind TEXT, provider TEXT, model TEXT, model_version TEXT, location TEXT, role TEXT,
  method TEXT, traffic_type TEXT, stream INT, {TOK}, tok_total INT, prompt_size INT, tools_defined INT,
  tool_calls_emitted INT, stop_reason TEXT, thinking_requested TEXT, request_hash TEXT, is_retry INT,
  cost_usd REAL, cost_status TEXT, cost_breakdown TEXT, usage_raw TEXT);
CREATE TABLE IF NOT EXISTS tool_calls (
  id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT, call_id TEXT, parent_id TEXT, name TEXT, args_hash TEXT,
  status TEXT, error_code TEXT, t_start REAL, t_end REAL, is_retry INT, source TEXT);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, trial_id TEXT, attempt_id TEXT, ts REAL, type TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS ix_trials_run ON trials(run_id);
CREATE INDEX IF NOT EXISTS ix_att_trial ON attempts(trial_id);
CREATE INDEX IF NOT EXISTS ix_llm_att ON llm_calls(attempt_id);
CREATE INDEX IF NOT EXISTS ix_tool_att ON tool_calls(attempt_id);
CREATE INDEX IF NOT EXISTS ix_ev_run ON events(run_id, id);
"""


MIGRATIONS = [
    ("llm_calls", "cost_effective_usd", "REAL"), ("llm_calls", "promotions", "TEXT"),
    ("attempts", "cost_effective_usd", "REAL"), ("trials", "cost_effective_usd", "REAL"),
]


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        for table, col, typ in MIGRATIONS:
            if col not in {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        self.lock = threading.Lock()
        self._cols: dict[str, set[str]] = {}

    def cols(self, table: str) -> set[str]:
        if table not in self._cols:
            self._cols[table] = {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}
        return self._cols[table]

    def _clean(self, table: str, row: dict) -> dict:
        c = self.cols(table)
        out = {}
        for k, v in row.items():
            if k not in c:
                continue
            if isinstance(v, (dict, list)):
                v = json.dumps(v, default=str)
            elif isinstance(v, bool):
                v = int(v)
            out[k] = v
        return out

    def upsert(self, table: str, row: dict, key: str = "id") -> None:
        r = self._clean(table, row)
        cols = ",".join(r)
        qs = ",".join("?" * len(r))
        upd = ",".join(f"{k}=excluded.{k}" for k in r if k != key)
        sql = f"INSERT INTO {table} ({cols}) VALUES ({qs})"
        sql += f" ON CONFLICT({key}) DO UPDATE SET {upd}" if upd else f" ON CONFLICT({key}) DO NOTHING"
        with self.lock:
            self.db.execute(sql, list(r.values()))

    def insert(self, table: str, row: dict) -> int:
        r = self._clean(table, row)
        with self.lock:
            cur = self.db.execute(f"INSERT INTO {table} ({','.join(r)}) VALUES ({','.join('?' * len(r))})", list(r.values()))
            return cur.lastrowid

    def update(self, table: str, id_: str, **fields) -> None:
        r = self._clean(table, fields)
        if not r:
            return
        with self.lock:
            self.db.execute(f"UPDATE {table} SET {','.join(f'{k}=?' for k in r)} WHERE id=?", [*r.values(), id_])

    def q(self, sql: str, *args) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args)]

    def one(self, sql: str, *args) -> dict | None:
        r = self.q(sql, *args)
        return r[0] if r else None

    def event(self, type_: str, data: dict, run_id=None, trial_id=None, attempt_id=None) -> None:
        self.insert("events", {"run_id": run_id, "trial_id": trial_id, "attempt_id": attempt_id,
                               "ts": time.time(), "type": type_, "data": data})
