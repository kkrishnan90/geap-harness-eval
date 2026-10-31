# Internal contracts (v1)

These contracts are shared by the engine (`src/geap_eval`), the dashboard (`web/`) and the task suite (`tasks/`). Change them only together.

## 1. Task package format

```
tasks/<industry>/<slug>/
  task.toml          # metadata (below)
  instruction.md     # the ONLY text the agent receives (realistic ticket with acceptance criteria)
  repo/              # seed workspace; copied verbatim into the attempt workspace (agent sees this)
  tests/             # HIDDEN from the agent; used only by the verifier
    run.sh           # entrypoint (bash): run.sh <workdir> <results_json_path>
    ...              # hidden test files, overlaid into <workdir> by run.sh itself
  solution/
    files/           # oracle: overlay these files onto repo/ to get a correct solution
```

`task.toml`:
```toml
id = "banking/iban-checksum-bug"     # == path under tasks/
version = "1"                        # bump when anything in the task changes
title = "Fix IBAN mod-97 validation for lowercase and spaced input"
industry = "banking"                 # banking|telecom|retail|oem-devices|healthcare|insurance|logistics|energy
tier = "simple"                      # simple|medium|complex
sdlc_type = "bug-fix"                # bug-fix|feature|refactor|test-authoring|upgrade|security|performance|ci-repair
languages = ["python"]
timeout_s = 600
requires = ["python3"]               # host tools the verifier needs (python3|node|go|cargo|javac|clang|make|sqlite3)
```

The verifier contract is implemented by `tests/run.sh`:
- It is called as `bash tests/run.sh <workdir> <results_json>`, where `<workdir>` is a **throwaway copy** of the agent's final workspace.
- It must overlay its hidden test files into `<workdir>`, run them **offline** with **stdlib-only** test frameworks (`python3 -m unittest`, `node --test`, `go test`, `cargo test --offline` with no deps, plain `javac` + main-based harness, `clang` + assert harness), and write:

```json
{ "fail_to_pass": {"passed": 3, "total": 3, "failed": []},
  "pass_to_pass": {"passed": 5, "total": 5, "failed": []},
  "log_tail": "last ~4KB of test output" }
```
- Exit code is ignored; the JSON is authoritative. A missing or invalid JSON means a verifier error.
- **Validity rule:** for the seed `repo/`, F2P must be all-fail and P2P all-pass. For `repo/` + `solution/files/`, everything passes.

## 2. Run config
See `PLAN.md` §6.1. The schema is `geap_eval.config.RunConfig`.

## 3. Store (SQLite, `runs/geap-eval.db`, WAL)

| table | key columns |
|---|---|
| `runs` | `id`, `name`, `status` (queued/running/paused/completed/cancelled/failed), `config_json`, `config_hash`, `lock_json`, `created_at`, `started_at`, `finished_at` |
| `trials` | `id`, `run_id`, `task_id`, `task_version`, `tier`, `industry`, `sdlc_type`, `harness`, `harness_version`, `variant`, `profile_id`, `profile_json`, `repeat_idx`, `status` (queued/running/passed/failed/infra_failed/invalid_routing/na), `attempts_used`, `passed_on_attempt`, `time_to_success_s`, `cost_usd`, `cost_status`, `updated_at` |
| `attempts` | `id`, `trial_id`, `run_id`, `idx` (1..), `status` (queued/admitted/preparing/running/verifying/passed/failed/backoff/interrupted/error), `exit_class` (ok/agent_error/timeout/infra_quota/infra_auth/crash/invalid_routing/budget), `t_queued`, `t0`, `t_end`, `t_verified`, `wall_s`, `llm_s`, `tool_s`, `overhead_s`, `ttft_ms`, `prompt_submissions`, `nudges`, `llm_turns`, `llm_calls`, `llm_retries`, `tool_calls`, `tool_ok`, `tool_fail`, `tool_retry`, `subagents`, `tok_input`, `tok_cache_read`, `tok_cache_write_5m`, `tok_cache_write_1h`, `tok_output`, `tok_thinking`, `tok_tool_prompt`, `cost_usd`, `cost_status`, `passed`, `f2p_passed`, `f2p_total`, `p2p_passed`, `p2p_total`, `diff_files`, `diff_lines`, `completion_signal`, `artifacts_dir`, `error` |
| `llm_calls` | `id`, `attempt_id`, `seq`, `t_start`, `t_first_byte`, `t_end`, `http_status`, `error_kind`, `provider` (google/anthropic), `model`, `model_version`, `location`, `role`, `traffic_type`, `stream`, `tok_input`, `tok_cache_read`, `tok_cache_write_5m`, `tok_cache_write_1h`, `tok_output`, `tok_thinking`, `tok_tool_prompt`, `tok_total`, `prompt_size`, `tools_defined`, `tool_calls_emitted`, `stop_reason`, `thinking_requested`, `request_hash`, `is_retry`, `cost_usd`, `cost_status`, `usage_raw` (JSON) |
| `tool_calls` | `id`, `attempt_id`, `call_id`, `parent_id` (PTC nesting), `name`, `args_hash`, `status` (ok/error/denied), `error_code`, `t_start`, `t_end`, `is_retry`, `source` (native/meter) |
| `events` | `id`, `run_id`, `trial_id`, `attempt_id`, `ts`, `type`, `data` (JSON) |

Token semantics (normalized across providers):
- `tok_input`: **uncached** input.
- `tok_cache_read`: cached-input reads.
- `tok_cache_write_5m` / `tok_cache_write_1h`: cache creation by TTL.
- `tok_output`: visible output, excluding thinking.
- `tok_thinking`: thinking/thoughts tokens.
- `tok_tool_prompt`: Gemini `toolUsePromptTokenCount`.

`cost_status` is one of `verified` (🔵), `check` (🟠), `unpriced` (🔴) or `reconciled` (🟢, future).

All timestamps are epoch seconds as floats (UTC).

## 4. HTTP API (FastAPI, default `http://127.0.0.1:8787`)

| Method | Path | Returns |
|---|---|---|
| GET | `/api/health` | `{ok, version}` |
| GET | `/api/preflight` | `{credentials:{ok, identity, project, adc_type, expires_in, issues[]}, models:{ok, availability:[{model, location, status, thinking_levels[]}]}, pricing:{ok, snapshot_id, fetched_at, issues[]}, harnesses:[{name, version, installed, latest}]}` |
| GET | `/api/models` | `[{id, family, provider, locations[], thinking_levels[], priced: bool, enabled: bool}]` |
| GET | `/api/harnesses` | `[{name, variant, version, capabilities:{roles[], native_multi_model, pipeline, thinking_control, meter_mode, driver}}]` |
| GET | `/api/tasks` | `[{id, version, title, industry, tier, sdlc_type, languages[]}]` |
| GET | `/api/runs` | `[run summary]` |
| POST | `/api/runs` | body = RunConfig JSON → `{run_id}`; `?dry_run=1` → `{matrix:[{task, harness, profile, status:"ok"\|"na", reason}], estimate}` |
| GET | `/api/runs/{id}` | run + progress counts + spend |
| POST | `/api/runs/{id}/pause\|resume\|cancel` | `{ok}` |
| GET | `/api/runs/{id}/trials` | `[trial rows]` |
| GET | `/api/runs/{id}/summary` | aggregates: `{groups:[{harness, variant, profile_id, n, pass_at_1, pass_at_1_ci:[lo,hi], pass_k, pass_hat_k, cost_mean, cost_ci, cost_per_success, tokens:{...means}, time_mean, time_ci, tool_calls_mean, tool_fail_rate, cache_hit_ratio}], by_tier:[...], by_industry:[...]}` |
| GET | `/api/trials/{id}` | trial + attempts[] |
| GET | `/api/attempts/{id}` | attempt + `llm_calls[]` + `tool_calls[]` + `events[]` |
| GET | `/api/attempts/{id}/cast` | asciicast v2 (text/plain) |
| GET | `/api/pricing` | `{snapshot_id, fetched_at, models:[{model, location, rates:{category: usd_per_1m}}], issues[]}` |
| GET | `/api/stream?run_id=` | **SSE**; event names below |
| WS | `/api/attempts/{id}/pty` | live raw terminal bytes (binary frames) for xterm.js |

**SSE events** (`event:` name, JSON `data:`):
- `run` `{run_id, status, progress:{total, done, running, passed, failed}, spend_usd, burn_usd_per_min}`
- `trial` `{trial row}`
- `attempt` `{attempt row}`
- `llm_call` `{llm_calls row}`
- `tool_call` `{tool_calls row}`
- `tick` `{attempt_id, elapsed_s, tokens:{input, cache_read, cache_write, output, thinking}, cost_usd, tool:{ok, fail, retry}, state}`, about 1 per second per running attempt
- `infra` `{kind: "429"|"backoff"|"breaker_open"|"breaker_close"|"aimd", model, location, detail}`
- `budget` `{spent_usd, cap_usd, pct, action}`
- `log` `{level, msg}`
