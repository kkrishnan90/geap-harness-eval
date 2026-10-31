# GEAP Harness Eval — Implementation Plan

**Status:** Draft v2 · 2026-10-30. Revised for: your-gcp-project only, latest CLIs, native interactive mode only, dsh vanilla + PTC, cost monitoring with validation, optional budget.
**Goal:** A reproducible, idempotent benchmark that runs real-world enterprise SDLC tasks through coding-agent CLIs **in their native interactive mode**. Every model call goes to the Gemini Enterprise Agent Platform (GEAP) using ADC short-lived credentials only. Dense metrics and **validated cost** are shown on a premium live dashboard.

Harnesses: **Claude Code**, **Pi**, **Oh My Pi (omp)**, **DeepSeek Harness (dsh, vanilla, PTC mode)**, **Antigravity CLI (agy)**. Codex is out of scope.

---

## 0. Fixed constraints

| Constraint | Rule |
|---|---|
| GCP project | **`your-gcp-project` only.** It is used for the project, quota project (`x-goog-user-project`), billing lookups and every harness config. No other project is read, inherited or referenced, and the gcloud active-project setting is ignored. |
| Identity | **`you@example.com`** through user ADC (`authorized_user`, verified: tokeninfo email matches, `expires_in` 3599s). The Credential Guard asserts this exact email before every run. |
| Credentials | **ADC only, for every harness.** No API keys, no service-account key files (the old SA key is unusable and ignored), no consumer OAuth logins. |
| CLI versions | **Always latest.** At run start each CLI is installed or updated to its newest release in an isolated `tools/` prefix, and the resolved versions are frozen in the run lock file (§6.4). |
| Mode | **Native interactive mode only. No headless/print/JSON modes** (`claude -p`, `pi -p`, `omp -p`, `dsh headless`, `agy -p` are not used). Each harness runs in the interactive UI a developer would use. |
| dsh | **Vanilla**, as shipped by the `deepseek-ai/deepseek-harness` repo / npm `@deepseek-ai/dsh`, with **PTC mode** enabled. No custom adapters and no existing local dsh state. |
| Budget | Optional overall guardrail (off by default). |
| Models | Latest GEAP models only, discovered at run time (below). |

**Current GEAP models (verified 2026-10-30 on your-gcp-project, global, ADC):**

| Family | Model ID | Status | Catalog list price (global, standard on-demand, per 1M tokens) |
|---|---|---|---|
| Gemini flagship | **`gemini-4-argon`** | GA 2026-10-13; first Gemini 4 model; live call OK | input $4.00 · cached input $0.20 · output $20.00 |
| Gemini fast | **`gemini-3.8-flash`** | GA; live call OK (reports `thoughts_token_count`) | input $1.50 · cached input $0.15 · output $7.50 (*introductory pricing through 2026-12-31*) |
| Claude | `claude-opus-5-5`, `claude-sonnet-5-5` | SKUs present (global/us/eu, ≤200k and >200k tiers, cache write 5m and 1h) | from catalog at run time (Sonnet 5.5: input $2.00 · cache write 5m $2.50 · 1h $4.00 · cache read $0.10 · output $10.00) |

**Where each model is available, and its thinking modes** (probed 2026-10-30 with the official SDKs on your-gcp-project via ADC; 429s were retried with backoff so they aren't mistaken for absence):

| Model | global | us-central1 | us-east5 | us-east1 | us-south1 | europe-west1 | europe-west4 | asia-southeast1 | asia-south1 | asia-northeast1 |
|---|---|---|---|---|---|---|---|---|---|---|
| `gemini-4-argon` | ✅ | 404 | 404 | 404 | 404 | 404 | 404 | ✅ | 404 | 404 |
| `gemini-3.8-flash` | ✅ | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 404 |
| `claude-opus-5-5` | ✅ | 429* | 429* | 429* | 429* | 429* | 429* | 429* | 404 | 400 |
| `claude-sonnet-5-5` | 404† | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 404 | 404 |

\* A persistent 429 after 5 backoff retries means the endpoint exists but this project has **no usable quota** there, so it is treated as unavailable.
† "Publisher model … not found or your project does not have access". The SKU exists in the billing catalog, but the model is **not enabled for your-gcp-project**. It must be enabled in Model Garden (accept the Anthropic terms) before Sonnet can be used. The availability probe re-checks it every run.

→ **Every model is routed to `global`**, the only location where all available models answer. Regional endpoints are used only when the availability matrix says so and the user picks them.

| Model | Thinking control | Accepted values | Rejected |
|---|---|---|---|
| `gemini-4-argon` | `thinkingConfig.thinkingLevel` | `LOW`, `MEDIUM`, `HIGH` | `MINIMAL`; `thinkingBudget` ("not supported for this model. Use thinking level instead") |
| `gemini-3.8-flash` | `thinkingConfig.thinkingLevel` (preferred) | `LOW`, `MEDIUM`, `HIGH`; `thinkingBudget` also accepted | `MINIMAL` |
| `claude-opus-5-5` | `thinking: {type: adaptive}` + effort | effort `low`, `medium`, `high`, `xhigh`, `max`; thinking off | `thinking.type: enabled` + `budget_tokens` |
| `claude-sonnet-5-5` | (expected to match Opus; verify once enabled) | — | — |

**Thinking is a first-class benchmark dimension.** Every model profile names a thinking level per role, and that level is part of the trial ID. Each harness maps canonical levels to its own control:
- Claude Code: effort setting in the isolated settings.
- Pi and omp: `--model <id>:<level>`.
- agy: the model label suffix, such as "(High)".
- dsh: the provider thinking option in the profile.

The Run Builder offers only levels the model accepts (from the probe) **and** the harness can express. Other cells show N/A with the reason. For example, a harness that always sends `thinkingBudget` cannot run Argon. The thinking level actually used is verified from the Meter, using `thoughtsTokenCount` and the request's `thinkingConfig` / `thinking` / effort fields, so a harness that silently ignores the setting is caught and flagged.

Not used: `gemini-3.6-flash` and `gemini-3.7-flash` (superseded; 3.6 reportedly retires 2026-11-19). The "Cyber Permissive" Argon and 3.8 Flash variants are US-only, special-purpose SKUs and are excluded unless asked. Haiku 5.5 has no GEAP SKU. The prices above are a snapshot for orientation; the cost engine always reads the live catalog (§9).

Latest versions as of 2026-10-30, re-resolved on every run:

| Harness | Package | Latest |
|---|---|---|
| Claude Code | `@anthropic-ai/claude-code` | 2.1.314 |
| Pi | `@earendil-works/pi-coding-agent` (renamed from `@mariozechner/…`) | 1.4.0 |
| omp | `@oh-my-pi/pi-coding-agent` | 18.14.0 |
| dsh | `@deepseek-ai/dsh` | 0.2.1-rc.5 |
| agy | self-updating binary (`agy update`) | resolved in Phase 0 |

---

## 1. Key decisions

1. **Python 3.12+ with `uv`** (venv only, `load_dotenv(override=True)`).
2. **Interactive driving through a real pseudo-terminal.** Each TUI runs in a PTY (`ptyprocess`) with a server-side terminal emulator (`pyte`) that tracks the screen. The prompt is typed in as a human would, by bracketed paste followed by Enter. dsh, which has no terminal UI, is the exception (§5.3).
3. **Two measurement planes, cross-reconciled** (unchanged in spirit, adapted for interactive mode):
   - **Plane A, native session records:** the transcript or session files every harness writes during an interactive session. They give tool calls with status, turns and reported usage.
   - **Plane B, GEAP Meter proxy:** ground truth for every model HTTP call (raw usage, 429s, latency). It is also the main **turn-completion signal** in interactive mode (§5.2).
4. **Success is decided by hidden tests** that run after the agent finishes, in a clean container.
5. **Cost is computed only from authoritative, machine-readable GEAP prices**, the Cloud Billing Catalog API read through ADC, and validated in layers before it is shown (§9). An unvalidated number is never displayed as fact.
6. **Content-addressed, append-only, resumable runs.** Config-as-code YAML is the single source of truth; the UI edits the same YAML.

---

## 2. Architecture

```
┌──────────────────────── Dashboard (React/Vite + xterm.js, served by FastAPI) ────────────────────────┐
│ Run Builder · Mission Control (live terminals) · Compare · Cost Center · Trial Inspector · Quota · Settings │
└─────────▲ REST                                   ▲ SSE (events) + WebSocket (live PTY byte stream) ────┘
┌─────────┴──────────────────────────── geap-eval server ───────────────────────────────────────────────┐
│ Config ─ Scheduler ─ Rate Governor ─ Event Bus ─ Store (SQLite WAL + blobs) ─ Analytics (DuckDB)      │
│ Credential Guard (ADC, your-gcp-project, identity)     Pricing Service (Billing Catalog → validated price book) │
│                                                                                                        │
│ Trial Runner ──► Interactive Driver ──► PTY ──► harness TUI (claude | pi | omp | agy)                  │
│                       │   (pyte screen, asciicast recorder,          └─► dsh web UI via Playwright     │
│                       │    ready/idle/dialog detectors, nudges)                                        │
│                       ▼                                                                                │
│               Session-file collector (Plane A)        GEAP Meter proxy (Plane B) ──► GEAP endpoints    │
│                       ▼                                                                                │
│               Verifier (hidden tests, clean container) → pass/fail                                     │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Repository layout
```
harness-eval-geap/
  pyproject.toml
  geap_eval/
    cli.py                 # run, resume, preflight, prices sync|verify, tasks validate, serve, export
    config/                # pydantic schemas
    auth/guard.py          # ADC + identity + project assertions, env scrubber
    meter/                 # reverse proxy + usage parsers (gemini.py, anthropic.py)
    pricing/               # catalog sync, sku_map.yaml, cost engine, validators, billing reconciliation
    drivers/               # pty.py, screen.py (pyte), asciicast.py, browser.py (Playwright for dsh web)
    adapters/              # claude_code.py, pi.py, omp.py, dsh.py, agy.py
    collectors/            # per-harness session-file parsers (Plane A)
    sandbox/ runner/ verify/ store/ analytics/ server/
  web/                     # dashboard
  tasks/                   # suite (§7)
  tools/                   # isolated latest-version installs (npm prefix + agy binary); never touches global installs
  configs/                 # smoke.yaml, full-matrix.yaml, multi-model.yaml
  runs/                    # per run/trial/attempt artifacts
```

---

## 3. Credentials: ADC only, your-gcp-project only

### 3.1 Credential Guard (before each run, re-checked per attempt)
- `google.auth.default()` must return `authorized_user`. **Reject anything else**, including a `service_account` key and any `GOOGLE_APPLICATION_CREDENTIALS`.
- Call tokeninfo: the email must equal `you@example.com` and the token must expire in ≤ 3600s.
- The project must equal `your-gcp-project` in every place we write it: harness configs, Meter upstream, billing queries. A config-time validator rejects any other project string anywhere in the run config or generated harness configs.
- **Availability probe** (`geap-eval preflight models`): for each configured model × candidate location, send one tiny SDK call. 429s get backoff retries; a persistent 429 means no quota. Classify each result as ✅ / 404 (absent or not enabled) / no-quota / 400. Then probe each model's valid thinking levels.
  - The result is stored as `availability.json` in the run lock. It drives automatic location routing and the Run Builder's valid-cell matrix.
  - Total probe cost is a few cents, shown in the Cost Center under "preflight".
- **Secret scan** of every generated harness config: fail on `apiKey`, `*_API_KEY`, private-key PEM, `*service-account*.json`, or OAuth token files.
- The dashboard shows a "Credential posture" card. A run cannot start while it is red.

### 3.2 Isolated environment per attempt
- Start from an empty env plus an allowlist: `PATH`, `LANG`, `TERM=xterm-256color`, isolated `HOME`, `TMPDIR`, `GOOGLE_CLOUD_PROJECT=your-gcp-project`, `GOOGLE_CLOUD_QUOTA_PROJECT=your-gcp-project`, `GOOGLE_CLOUD_LOCATION`, plus per-harness GEAP variables.
- Never inherit `CLAUDE_CODE_*`, `ANTHROPIC_*`, `*_API_KEY`, or the user's `~/.claude`, `~/.pi`, `~/.omp`, `~/.dsh`, `~/.gemini`.
- The isolated `HOME` holds only a 0600 copy of the ADC file plus generated harness config. It is deleted at attempt end and never archived. Each harness therefore starts like a fresh vanilla install, with no consumer logins (for example agy's `antigravity-oauth-token`) and no stale settings.

### 3.3 Proof of GEAP routing
Each attempt must show at least one Meter-recorded 2xx call to `aiplatform.googleapis.com` for `projects/your-gcp-project/…`. Otherwise the attempt is `INVALID_ROUTING`, not pass or fail. Container egress is allowed only through the Meter.

---

## 4. GEAP Meter (ground truth + turn-completion signal)

- A streaming reverse proxy on `127.0.0.1`; the path `/t/<attempt_token>/…` gives per-attempt attribution. It forwards the harness's own bearer token unchanged and redacts it from logs. It rejects any upstream path that is not `projects/your-gcp-project/…`, which enforces the project rule in code.
- **Routing per harness** (resolved in Phase 0): base-URL override where supported (Claude Code `ANTHROPIC_VERTEX_BASE_URL`; pi, omp and dsh provider `baseUrl`). Otherwise `HTTPS_PROXY` with a per-run CA inside the Linux container (Node `NODE_EXTRA_CA_CERTS` + `NODE_USE_ENV_PROXY=1`; Go/agy `SSL_CERT_FILE`).
- **What it parses:**
  - *Gemini* `usageMetadata`: `promptTokenCount`, `candidatesTokenCount`, `cachedContentTokenCount`, `thoughtsTokenCount`, `toolUsePromptTokenCount`, `totalTokenCount`, modality details, **`trafficType`** (standard / priority / flex / provisioned, which drives the price SKU), `modelVersion`, `finishReason`.
  - *Claude* `message_start`/`message_delta` usage: `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens`, `cache_read_input_tokens`, `service_tier`, `stop_reason`.
  - *Per call:* status, 429 / `RESOURCE_EXHAUSTED` / 503 / 529, `Retry-After`, TTFT, latency, **endpoint locality (global vs regional, which also drives price)**, prompt size (which selects the ≤200k vs >200k context-window SKU tier), tool definitions sent, tool calls emitted, and tool results in the next request (`is_error` for Claude, `functionResponse` for Gemini).
  - Unknown usage fields are kept verbatim in `usage_raw`.
- **Turn-state machine:** in-flight count, plus the last response's stop reason (`end_turn`/`STOP` with no tool calls means "model done"). This feeds the completion detector (§5.2).

---

## 5. Native interactive driving

### 5.1 Interactive Driver (common to all TUIs)
1. **Launch** the TUI in a PTY at a fixed 220×60 size, in the task workspace (in the container), with the harness's documented auto-approve flag where it exists in interactive mode. That approval policy is recorded as part of the harness config.
2. **Ready detection:** wait for a harness-specific screen signature (the input box or prompt glyph, from a pattern file per harness version) and 1.5s of screen stability.
3. **Submit:** bracketed paste (`ESC[200~ … ESC[201~`) of `instruction.md`, then Enter. **`t0` = the moment Enter is written to the PTY** (the start marker).
4. **While running:**
   - A **dialog responder** recognizes permission, trust and update prompts by screen pattern and answers with the policy choice. Every auto-answer is logged as a `dialog_answered` event.
   - **Nudges:** if the model ends a turn asking the user something, the driver sends a configured nudge ("Proceed autonomously using your best judgment"). The limit is `max_nudges` (default 2), and each nudge counts as a `prompt_submission`.
5. **Completion detection** (layered, the first that fires wins, all recorded):
   - (a) A native hook or extension marker, where the harness supports it: Claude Code `Stop` hook in the isolated settings writes a marker file; pi and omp extension on `agent_end`; dsh session `final`-style turn record.
   - (b) **Meter quiescence:** the last response ended with no tool calls, nothing is in flight, and no new request arrives for 10s.
   - (c) **Screen quiescence:** the input box is visible and idle, with no spinner, for 10s.
   - **End marker `t_end` = completion time of the final model response, taken from the Meter**, not the detection time. Detection delay therefore never inflates measured time.
6. **Exit:** send the harness's quit command (`/exit` or the equivalent), then SIGTERM, then SIGKILL the process group. All deadlines are in-process `asyncio`; macOS has no `timeout`.
7. **Recording:** the raw PTY byte stream is saved as **asciicast v2** for replay in the Trial Inspector and streamed live over WebSocket to xterm.js in Mission Control.

### 5.2 Per-harness configuration (interactive)

| | Claude Code | Pi | omp | agy | dsh (vanilla, PTC) |
|---|---|---|---|---|---|
| Launch | `claude --dangerously-skip-permissions` (TUI) | `pi --provider google-vertex --model <id>:<thinking> --session-dir <attempt>` (TUI) | `omp` (TUI) with role config in isolated `~/.omp/agent/config.yml` | `agy --dangerously-skip-permissions --model "<label>"` (TUI) | `dsh web` with isolated `DSH_HOME` and a per-attempt port; driven by Playwright (§5.3) |
| GEAP + ADC | `CLAUDE_CODE_USE_VERTEX=1`, `ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project`, `CLOUD_ML_REGION`, isolated `CLAUDE_CONFIG_DIR`, telemetry and autoupdater off | `GOOGLE_CLOUD_PROJECT=your-gcp-project`, `GOOGLE_CLOUD_LOCATION`, ADC (built-in Vertex provider). Claude through a pinned public Vertex-Anthropic provider package if one is verified in Phase 0 | `google-vertex` provider + ADC in isolated `models.yml` | isolated `settings.json {"gcp":{"project":"your-gcp-project","location":…}}` + ADC ("Agent Platform authentication"); no OAuth token present | profile `cordis.patch.yml`: Vertex provider via ADC (`project: your-gcp-project`); `dsh-tools` **`mode: ptc`** |
| Models on GEAP | Claude | Gemini (+ Claude if provider verified) | Gemini + Claude | Gemini + Claude (display labels with effort) | whatever vanilla dsh's Vertex provider supports (Phase 0) |
| Native multi-model | main model, `ANTHROPIC_DEFAULT_*` model vars in isolated settings, `CLAUDE_CODE_SUBAGENT_MODEL`, `.claude/agents/*.md` `model:` | subagent extension (Phase 0) | **`modelRoles`**: default / plan / slow / smol / task / … | Phase 0 | dsh subagent and workflow model config (Phase 0) |
| Plane A source | `CLAUDE_CONFIG_DIR/projects/<slug>/<session>.jsonl` (per-message usage, tool_use / tool_result) | session `.jsonl` (usage incl. `cacheRead`/`cacheWrite`) | session store in isolated `~/.omp` | `~/.gemini/antigravity-cli/conversations/` (format mapped in Phase 0) | `DSH_HOME/sessions/**/session.jsonl.zstd` (**multi-frame zstd: decode with the `zstd -dc` CLI**, never Node `zstdDecompressSync`) |
| Completion hook | `Stop` hook → marker | extension `agent_end` | extension hook | Meter/screen fallback | durable turn record + Meter |

Model IDs come from **runtime discovery on your-gcp-project, cross-checked against the Billing Catalog SKUs** (§9), never from memory. Example: the catalog has Claude Opus 5.5 and Sonnet 5.5 SKUs but **no Haiku 5.5**, so Haiku is not offered.

### 5.3 dsh specifics
- **Interactive surface:** vanilla dsh ships `web`, `headless`, `sdk`, `sdk-minimal` and `acp` profiles (plus Electron `desktop`), and **no terminal UI**. Its native interactive coding surface is the **Web app**.
- **Running the Web app with no human in the loop** (default driver, `drivers/browser.py`):
  1. The runner boots `dsh web --port <free port>` with an isolated `DSH_HOME` (vanilla profile + ADC + PTC patch), and reads the one-time `?token=` sign-in URL that dsh prints to its output.
  2. **Playwright** opens that URL in an automated Chromium. It is headed in a virtual display inside the container, so it is the real UI; headless Chromium is also possible. The browser gets the auth cookie exactly as a person's would.
  3. It types the ticket into the chat composer and sends it. **`t0` = the send click.**
  4. Permission dialogs are avoided by the profile's permission preset. Any dialog that still appears is answered by Playwright using its accessible role and label, and is logged as `dialog_answered`.
  5. Completion uses the same layered detector as the TUIs: the durable turn record in the dsh session store, Meter quiescence (last response finished with no tool calls, nothing in flight), then DOM idle (composer enabled, no running indicator).
  6. The runner collects session files and the Meter log, closes the browser, and stops the process group.

  The live view is a page screencast through CDP, streamed to Mission Control and recorded as video plus a Playwright trace for replay. The user's own `:3080` service and `~/.dsh` are never touched.
- **Fallback driver: dsh's built-in ACP profile** (`dsh --profile acp`). ACP (Agent Client Protocol) is how editors such as Zed run dsh's normal interactive multi-turn sessions, with prompts and permission requests over stdio. It is more robust than page automation, and is used if the Web UI selectors prove unstable across "latest" releases. It is labeled `dsh/acp` so its results are never confused with `dsh/web`.
- **PTC mode:** in `dsh-tools`, `mode: native | ptc | both`. The default is **`ptc`**. The Run Builder also offers **"dsh native (PTC off) control"**, which adds a `dsh/native` variant to the matrix so the PTC effect can be measured on the same tasks. The model then sees only `run_code` (a TypeScript program run by `dsh-ptc-runtime-node`, default 120s, max 600s) and calls tools as `await tools.name(args)` inside it. A model-direct call to any other tool resolves to `UNKNOWN_TOOL`.
- **Metric implications for PTC:**
  - Tool calls are counted on two levels: **`run_code` programs** (outer) and **nested sub-calls** (ids `<parent>:ptc:<n>`).
  - Each sub-call keeps its own status and structured error `{name, code, reason}`.
  - Program-level failures are categorized by kind: `exception`, `timeout`, `abort`, `worker-exit`, `invalid-output`, `output-limit`, `protocol`, `sandbox-unavailable`.
  - Fewer LLM round-trips per tool call is the expected PTC effect, so the dashboard shows **tools per LLM turn** for dsh specifically.
- Note from the dsh docs: nested PTC dispatches inside **workflow** runs are not durably recorded. Workflow-internal tool counts are therefore marked "partial" when the workflow tool is used.

---

## 6. Orchestration, retries, idempotency

### 6.1 Run config
```yaml
run: { name: q4-baseline, repeats: 5, max_task_retries: 3, retry_mode: fresh }   # see §6.2
geap: { project: your-gcp-project, identity: you@example.com, location: auto }   # auto = per-model from the availability probe (today: global for all)
versions: latest            # resolved + frozen into runs/<run_id>/lock.json at run start
harnesses: [claude_code, pi, omp, dsh, agy]
model_profiles:
  # each role = { model, thinking }; thinking is canonical (off|low|medium|high|xhigh|max) and validated per model + harness
  - { id: opus-high,   mode: single, roles: { default: { model: claude-opus-5-5,   thinking: high } } }
  - { id: sonnet-high, mode: single, roles: { default: { model: claude-sonnet-5-5, thinking: high } } }   # needs Model Garden enablement
  - { id: flash-med,   mode: single, roles: { default: { model: gemini-3.8-flash,  thinking: medium } } }
  - { id: argon-high,  mode: single, roles: { default: { model: gemini-4-argon,    thinking: high } } }
  - id: argon-plans-flash-codes
    mode: native_roles
    roles: { plan: { model: gemini-4-argon, thinking: high }, default: { model: gemini-3.8-flash, thinking: medium }, subagent: { model: gemini-3.8-flash, thinking: low } }
  - id: opus-plans-flash-codes
    mode: native_roles
    roles: { plan: { model: claude-opus-5-5, thinking: max }, default: { model: gemini-3.8-flash, thinking: medium }, subagent: { model: gemini-3.8-flash, thinking: low } }
  # sweep helper: expands one model across all valid thinking levels, e.g. argon × {low, medium, high}
  - { id: argon-thinking-sweep, mode: single, sweep: { model: gemini-4-argon, thinking: all_valid } }
  - id: pipeline-opus-then-sonnet
    mode: pipeline          # same session: turn 1 plan-only with planner model → turn 2 execute with executor model
    stages: [{ role: plan, model: claude-opus-5-5 }, { role: execute, model: claude-sonnet-5-5 }]
limits: { attempt_timeout_s: { simple: 600, medium: 1500, complex: 3600 }, max_nudges: 2 }
budget: { enabled: false, max_usd_total: null, max_usd_per_attempt: null, on_exceed: pause }   # optional guardrail
concurrency: { global: 6, per_harness: 3 }
```
In interactive `pipeline` mode, the stage switch is done the way a user would do it: the in-TUI model switch (`/model …`) between turns, where the harness supports it. Harnesses without in-session switching are N/A for pipeline, as validated in the Run Builder.

### 6.2 Retry modes: fresh vs feedback
A trial gets up to **1 + 3 attempts**. The two modes differ only in **what the agent knows when it tries again**.

| | **fresh** | **feedback** |
|---|---|---|
| Workspace | Reset to the original task snapshot; the failed attempt's edits are thrown away | Kept as the agent left it |
| Session | New TUI session; the agent has no memory of the failed try | Same session; full conversation history kept |
| What we send | The original task prompt, unchanged | A follow-up message such as *"The acceptance tests failed: `test_iban_mod97_lowercase` expected True, got False. Please fix."* |
| Real-world analogue | Giving the ticket to the agent again from scratch | CI goes red and the developer pastes the failure back to the agent |
| What it measures | **Reliability**: chance of solving it unaided on any one try. Attempts are statistically independent, so pass@k is valid | **Self-repair**: can the agent fix its own mistake given a hint. Attempts are dependent |
| Token/cost profile | Each attempt pays the full context again (some prompt-cache reuse possible) | Later attempts carry the growing history (high cache reads, larger context) |
| Caveat | None for comparability | Leaks information from the hidden tests (failing test names and messages), so a pass after feedback is "solved with help" and is reported separately |

**Example** (banking IBAN task): with **fresh**, attempt 2 starts in a clean repo with the same ticket. With **feedback**, attempt 2 continues in the same chat with "test X failed…".

**Decision: `fresh` is the default.** `feedback` stays available as an opt-in per run or per profile, and its results are always reported separately.

**Infra retries** do not consume task retries. They cover 429 `RESOURCE_EXHAUSTED`, 503/529, harness crash at boot, and container errors. They use exponential backoff with full jitter (base 2s, cap 120s), honor `Retry-After`, have their own cap (6), and use a per-model circuit breaker; daily-quota exhaustion alerts instead of looping. **Every attempt is fully recorded whatever the outcome.** After all retries are exhausted, the trial is marked `FAILED` with all metrics kept.

### 6.3 Rate governor
Per model × location: a token bucket (RPM/TPM), **AIMD** concurrency (halve on 429, +1 per quiet minute), and a circuit breaker, fed live by Meter 429s including the harness's own internal retries. Claude and Gemini use separate pools.

### 6.4 Idempotency with "always latest"
- At run start, resolve the latest version of each CLI, install it into `tools/<harness>/<version>/`, and write `runs/<run_id>/lock.json` (versions, image digests, task hashes, price-book hash).
- **`resume` always uses the lock file**, so a resumed run never mixes CLI versions even if a newer release ships mid-run. A new `run` picks up the newest versions, and the dashboard flags version changes between runs being compared.
- `trial_id = sha256(task@version, harness@locked_version, profile_hash, repeat_idx, "your-gcp-project")`.
- SQLite WAL state machine: orphaned `RUNNING` attempts become `INTERRUPTED` (partial data kept) and are re-queued without consuming a task retry; completed trials are skipped; writes are atomic; the append-only event log can rebuild the DB.

---

## 7. Task suite
Unchanged from v1, summarized:
- **Format:** Harbor/Terminal-Bench style (`task.toml`, `instruction.md`, `environment/`, hidden `tests/` with FAIL_TO_PASS / PASS_TO_PASS, oracle `solution/`), checked by `geap-eval tasks validate`.
- **Tiers:** simple (≤1 file), medium (2–5 files), complex (5+ files, 5–30k LoC repos).
- **Scope:** 36 tasks across banking, telecom, retail, OEM/devices, healthcare, insurance, logistics and energy, plus cross-cutting SDLC types (bug fix, feature, refactor, tests, upgrade, security, performance, IaC, CI repair). 12 ★ tasks form the MVP.
- See the v1 catalog table (kept in `tasks/CATALOG.md` during Phase 3).

---

## 8. Metrics (per call → attempt → trial → aggregate)
- **Tokens (per call, model, role and subagent):** `input_uncached`, `cache_read`, `cache_write_5m`, `cache_write_1h`, `output`, `thinking`, `tool_use_prompt`; cache hit ratio; context-growth curve; Plane A vs Plane B reconciliation.
- **Tool calls:** total and by tool, succeeded / failed / retried (same tool with near-identical args after a failure) / denied / auto-approved dialogs. For dsh PTC: programs and nested sub-calls (§5.3).
- **Steps:** prompt submissions (initial + nudges + feedback), LLM turns, assistant messages, tool calls, subagent spawns, harness-internal LLM retries; ordered step sequence for trajectory views.
- **Time:** `t0` (Enter written) → `t_end` (final model response completed, from the Meter), split into LLM time, tool time and harness overhead. TTFT. Queue and backoff waits are excluded. Verify time is separate. **time_to_success** runs across attempts.
- **Outcome:** pass/fail, FAIL_TO_PASS and PASS_TO_PASS counts, regressions, diff size, `exit_class`.
- **Aggregates:** pass@1, pass@k (unbiased estimator), pass^k, success-within-R-retries, mean/median/p90/stdev with **95% bootstrap CIs**, paired-bootstrap and Mann-Whitney comparisons with Holm correction, and "needs more repeats" badges.

---

## 9. Cost monitoring and validation

Cost is a critical output, so every cost figure has a traceable source, a validated computation and a visible confidence level.

### 9.1 Authoritative price source
- **Cloud Billing Catalog API**, read with ADC + `x-goog-user-project: your-gcp-project`: service **Vertex AI `C7E2-9256-1C43`**, `currencyCode=USD` (or a configured currency). Verified 2026-10-30: it lists 9,517 SKUs, including both families:
  - Gemini, for example `Gemini 4 Argon Global Text Input - Online Predictions`, `Gemini 3.8 Flash Global Text Output - Predictions`, `… Input Caching`, and the Priority / Flex / Offpeak / Deferred / Batch variants. Naming is **not uniform across families** (Argon says "Online Predictions", 3.8 Flash says "Predictions"), which is exactly why the SKU map is explicit and reviewed rather than pattern-matched at run time.
  - Claude, for example `Claude Sonnet 5 5 — Input Tokens — global — Context Window Size from 0 to 200000 Tokens`, `… Input Cache Write Tokens (TTL 300 seconds)`, `… (TTL 3600 seconds)`, `… Input Cache Read Tokens`, `… Output Tokens`, by locality (global/us/eu) and context tier.
- **Price book snapshot:** each run syncs the catalog and stores the snapshot (SKU id, description, unit, tiered rates, `effectiveTime`, fetch time, sha256). Each attempt references the snapshot hash it was costed with, so historical costs stay reproducible and never change silently.

### 9.2 Explicit SKU mapping (no fuzzy matching at cost time)
- `pricing/sku_map.yaml` maps each `(model, token_category, locality, context_tier, traffic_type)` to **exactly one SKU id**.
- It is **generated** by a strict parser over catalog descriptions, then **reviewed and committed**. At run time only the reviewed map is used. Example token categories: input, output, thinking (billed as output for Gemini), cache_read, cache_write_5m, cache_write_1h, tool_use_prompt.
- **Map validation** (fails the preflight if any check fails):
  - Every model in the run config has a complete category set.
  - Every mapped SKU id exists in the current snapshot, with unit `count` (per token) and the expected currency.
  - A rate changed since the last reviewed map raises an alert with a diff, and the change must be acknowledged in the UI.
  - A model missing from the catalog (for example Haiku 5.5 today) is **not runnable for costed runs**.

### 9.3 Cost computation (per call, from Meter usage)
- `cost = Σ_category tokens × rate(SKU)`.
- **Context tier** is chosen per request from that request's prompt size (≤200k vs >200k).
- **Locality** comes from the endpoint actually called (global vs regional).
- **Traffic type** comes from the response `trafficType` / `service_tier` (standard, priority, flex, provisioned throughput). Provisioned-throughput calls are shown as $0 marginal and flagged "PT", never mixed into on-demand cost.
- Money uses `Decimal` with no float accumulation; rounding happens only at display time.

### 9.4 Validation layers (each produces a status on every cost figure)
1. **Token integrity:** usage invariants hold (non-negative; cache read and write ≤ total input; Gemini `total = prompt + candidates + thoughts + toolUse`), and Plane A matches Plane B within 1%. A violation turns the cost amber.
2. **Price integrity:** the SKU map validates against the snapshot (§9.2).
3. **Arithmetic integrity:** golden tests with hand-computed costs for every model and category, covering tier boundaries (exactly 200,000 / 200,001 tokens), cache TTL variants and mixed-role attempts. Property tests check that cost is monotonic in tokens and that the sum over calls equals the attempt total equals the trial total.
4. **Independent second source:** a nightly job compares the price book with the public GEAP pricing pages (Gemini and partner-model pages). Any disagreement is flagged for review. The catalog stays authoritative; the page is a cross-check.
5. **Billing ground truth: parked for the next revision.** Billing export to BigQuery is not set up yet. When it is, the plan is to reconcile computed cost with billed cost per SKU per day, optionally attributing exactly with request labels. Until then, layers 1–4 are the validation and the 🟢 badge is not used.

**Badges shown on every cost figure:**
- 🟢 **Billed-reconciled:** within ±1% of the billing export (*next revision*).
- 🔵 **Catalog-verified:** layers 1–4 passed.
- 🟠 **Check:** token mismatch or price change not yet acknowledged.
- 🔴 **Unpriced:** no valid SKU. It is shown as "—", **never as $0 or an estimate**.

Totals show the share of each badge (for example "$412.30 — 97% catalog-verified, 3% unpriced").

### 9.5 Live cost monitoring
- Running spend per attempt, trial, harness, model, role and run, updated per Meter call, with a burn rate in $/min and projected run total.
- **Cost Center view:** spend by model × category (where the money goes: uncached input vs cache vs output vs thinking), cache savings ("cache reads saved $X vs uncached"), cost per solved task with CI, cost–success Pareto frontier, and cost of failed attempts and retries (the "waste").
- **Optional budget guardrail:** `budget.enabled` with an overall and/or per-attempt cap. At 80% the dashboard warns; at 100% the run **pauses** (or stops, if configured). In-flight attempts finish, but no new attempts are admitted. Enforcement uses catalog-verified live cost, and the UI shows the cap's confidence badge.
- A pre-run estimate in the Run Builder uses historical medians per task, harness and model, labeled as an *estimate*.

---

## 10. Dashboard

**Stack:** React 19 + Vite + TypeScript, Tailwind v4 + shadcn/ui, Apache ECharts, TanStack Query/Table, Framer Motion, **xterm.js** (live and replayed terminals) and **asciinema-player**-compatible replay. Live data arrives over SSE for events and WebSocket for PTY bytes.

**Visual language:** dark-first graphite surfaces with matching light mode; one signature accent plus semantic status colors; Geist/Inter for UI and JetBrains Mono for numbers and terminals; tabular numerals; calm density; ⌘K command palette.

**Views:**
1. **Run Builder:** tasks × harnesses × profiles matrix with N/A reasons; YAML preview; latest-version preview (what will be installed); cost estimate; optional budget; preflight status covering credentials, your-gcp-project, identity and price book.
2. **Mission Control:** a wall of **live terminals** (the actual Claude Code / pi / omp / agy TUIs, and the dsh web screencast), each overlaid with state, attempt n/4, live token meter by category, tool ticker (✓ ✗ ↻), live $ with badge, and elapsed or backoff timer. Run KPIs: progress, pass rate, spend, burn rate, 429 rate, budget gauge.
3. **Compare:** leaderboard with CIs, harness × industry × tier heatmap, token composition bars, tool-outcome sankey, time waterfall, pass-by-attempt survival curve, version-change flags.
4. **Cost Center:** §9.5, plus price-book version, SKU map diff, reconciliation status and badge distribution.
5. **Trial Inspector:** terminal replay synced to a step timeline (tokens, latency and $ per step), Plane A/B reconciliation, diff, verifier output, raw Meter calls (redacted), ATIF export.
6. **Quota and Health:** RPM/TPM, AIMD limits, breaker states, 429 timeline per model × location.
7. **Settings:** GEAP target (locked to your-gcp-project), model discovery, harness versions (latest + lock), price book sync and review, concurrency and backoff policy, budget.

---

## 11. Phased delivery

| Phase | Scope | Exit criteria |
|---|---|---|
| **0. Spikes (3–4 days)** | For each harness at latest version: interactive launch in PTY with isolated HOME + ADC on your-gcp-project; ready, dialog and completion signatures; Plane A file formats; Meter routing; in-session model switching; native multi-role support. dsh: vanilla `dsh web` + Playwright, Vertex ADC provider config, `mode: ptc`. agy: confirm Agent Platform auth with no OAuth token, and how to install the latest into `tools/`. Pricing: catalog sync + SKU map generation; check billing export availability and request-label support | Capability matrix fully resolved, plus a fixture library (asciicasts, session files, Meter logs) per harness |
| **1. Core engine** | Guard, Meter, Interactive Driver, Claude Code + pi adapters, verifier, store, retries, governor, **pricing service with validation layers 1–3** | Smoke run end to end; kill -9 then resume with no duplicates; forced-429 test; cost golden tests green |
| **2. All harnesses + model modes** | omp, agy, dsh (web + PTC) adapters; native_roles + pipeline; reconciliation | 5/5 harnesses pass smoke; per-role usage and cost recorded |
| **3. Task suite** | 12 ★ then 36 tasks; images; validation | All tasks pass the oracle/seed check |
| **4. Dashboard** | All views including live terminals and Cost Center | Full live run watchable; every metric visible |
| **5. Stats + billing reconciliation** | CIs, significance, Pareto; layer 4–5 cost validation; budget guardrail hardening | Full matrix (`repeats: 5`) report; cost badges ≥95% green or blue |

**Testing:** parser tests against recorded fixtures for every harness (interactive UIs change often, so screen-signature tests per CLI version run in CI); Meter tests against a fake GEAP server (usage, 429s, stream cuts); pricing golden and property tests; scheduler kill and resume property tests; nightly smoke run.

---

## 12. Hazards and mitigations
1. **Interactive UIs change with every "latest" release** and can break ready, dialog or completion detection. Signatures are versioned per CLI version; an unknown version falls back to Meter- and screen-quiescence detection with an amber "unverified driver" badge; the CI fixture tests catch drift.
2. **dsh has no TUI.** Drive the vanilla web UI with Playwright; never touch the user's running `:3080` service or `~/.dsh`.
3. **dsh session logs are multi-frame zstd:** decode with the `zstd` CLI.
4. **Consumer-auth fallback (agy):** the isolated HOME has no OAuth token, and the routing check marks such attempts `INVALID_ROUTING`.
5. **Parent-session env leakage** (`CLAUDE_CODE_*`, `ANTHROPIC_DEFAULT_OPUS_MODEL=…[1m]`): empty env + allowlist.
6. **"Latest" mid-run upgrades:** resume uses the lock file.
7. **Wrong cost from mismapped SKUs, tiers or locality:** explicit reviewed map, per-request tier and locality, golden tests, billing reconciliation, never-$0-when-unknown rule.
8. **Model not on GEAP** (for example Haiku 5.5 has no SKU): discovery + catalog cross-check before offering a model.
9. **Quota storms:** separate pools, AIMD, breaker, daily-quota detection.
10. **No `timeout` on macOS:** asyncio deadlines and process-group kill.
11. **Disk growth:** `--rm` containers, deleted HOMEs, image pruning; asciicasts are compressed.
12. **Gemini 4 Argon rejects `thinkingBudget`** and needs `thinkingLevel`. Some harness provider libraries (for example pi-ai-based ones) may still send `thinkingBudget` for unknown Gemini models. Phase 0 checks each harness's latest version against Argon. If one fails, the cell is shown as harness-incompatible; it is not patched, so the harness stays vanilla.
13. **Prices change by date:** Gemini 3.8 Flash has introductory pricing through 2026-12-31. Each run's catalog snapshot plus price-change alerts (§9.2) keep costs correct across the switch. Costs of past runs are never recomputed with new prices unless explicitly requested.
14. **Prompt-token overhead is provider-side:** Argon billed 33 prompt tokens for a 2-token message. Cost always uses **provider-reported usage** from the Meter, never local tokenization.
15. **Model churn:** GEAP can retire IDs about 45 days after a successor ships (3.6 Flash). Preflight discovery plus a liveness call per model blocks runs on retired IDs.
16. **Raw REST URL shapes return HTML 404s:** observed with hand-built URLs, while the SDK worked. The Meter must forward the harness's exact request path and query and never reconstruct URLs.

---

## 13. Decisions and open items
**Decided:**
- Retry default `fresh` (feedback opt-in).
- Other harnesses run in their default native tool-calling mode; dsh runs PTC, with an optional `dsh/native` control.
- dsh is driven through its Web app with Playwright (ACP as fallback).
- Billing reconciliation is parked.
- Location is chosen per model from the availability probe.
- Model lineup is Argon, 3.8 Flash, Opus 5.5 and Sonnet 5.5, each with thinking modes.

**Open:**
1. **Enable Claude Sonnet 5.5** in Model Garden for your-gcp-project. It returns 404 "not found or no access" in every location today.

**Next revision:** set up Billing export to BigQuery and request-label attribution for 🟢 billed-reconciled cost (§9.4, layer 5).

---

## 14. References
- Harbor / Terminal-Bench (task format, ATIF) — https://github.com/laude-institute/harbor · https://github.com/laude-institute/terminal-bench
- SWE-bench (FAIL_TO_PASS / PASS_TO_PASS) — https://github.com/SWE-bench/SWE-bench
- Inspect AI (eval logs, sandboxes, viewer) — https://github.com/UKGovernmentBEIS/inspect_ai
- Aider benchmark (retry with test feedback) — https://github.com/Aider-AI/aider/tree/main/benchmark
- τ-bench (pass^k) — https://github.com/sierra-research/tau-bench
- OpenTelemetry GenAI semantic conventions — https://opentelemetry.io/docs/specs/semconv/gen-ai/
- asciicast v2 format — https://docs.asciinema.org/manual/asciicast/v2/ · xterm.js — https://github.com/xtermjs/xterm.js · pyte — https://github.com/selectel/pyte
- Cloud Billing Catalog API — https://cloud.google.com/billing/docs/reference/rest/v1/services.skus/list
- Exponential backoff with full jitter — https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/
- dsh (vanilla) — https://github.com/deepseek-ai/deepseek-harness (CLI profiles, `dsh-tools` PTC mode, `dsh-ptc-runtime`)
- Pi — https://github.com/badlogic/pi-mono · oh-my-pi — https://github.com/can1357/oh-my-pi · Claude Code monitoring — https://docs.anthropic.com/en/docs/claude-code/monitoring-usage

---

## 15. Implementation status (2026-10-31)

**Built:** engine (`src/geap_eval`), dashboard (`web/`), 12-task MVP suite (`tasks/`), Phase-0 spike reports (`docs/spikes/*.md` with fixtures in `tests/fixtures/`).

**Verified end to end** (real GEAP calls on your-gcp-project, banking/iban-checksum-bug, hidden tests 13/13 + 20/20):

| Harness | Model / thinking | Result | Wall | Turns | Tools ok/fail | Cost (catalog, pending review) | Thinking on the wire |
|---|---|---|---|---|---|---|---|
| Claude Code 2.1.314 | Opus 5.5 / low | pass | 35 s | 6 | 5/0 | $0.326 | match (effort low) |
| Pi 1.4.0 | Flash 3.8 / low | pass (timeout at 600 s, still working) | 589 s | 16 | 15/1 | $0.438 | match |
| omp 18.14.0 | Flash 3.8 / low | pass | 75 s | 25 | 23/1 | $0.236 | match |
| omp 18.14.0 | Opus 5.5 / high (adaptive) | pass | 89 s | 11 | 7/5 | $0.558 | match |
| agy 1.4.11 | Flash 3.8 / Low label | pass | 563 s | 25 | 24/0 | $0.351 | **budget** (agy sends thinkingBudget for Flash) |
| agy 1.4.11 | Opus 5.5 / High label | pass | 73 s | 7 | 10/0 | $0.429 | match |
| dsh 0.2.1-rc.5 (web, PTC) | Flash 3.8 / low | pass | 181 s | 17 | 40/0 (16 run_code + 24 nested) | $0.236 | match |

**Deviations from the plan (and why):**
- **Sandbox:** Docker is not used yet; the daemon was not running. Attempts run on the host in an isolated workspace + HOME under `/private/var/tmp/geap-eval-work`, which is outside `/Users/<user>` so no parent `AGENTS.md`/`CLAUDE.md` leaks in. Verification is local, with stdlib-only test runners.
- **Meter routing:** base URL for Claude Code, Pi and dsh. For omp and agy, a **forward proxy with TLS interception** for `*.googleapis.com` only, using a throwaway per-Meter CA. Every other host is denied, which also blocks agy's self-updater and telemetry.
- **Auxiliary model calls** are tagged `aux`: billed but excluded from timing and error counts. Examples: dsh, omp and agy session titles (agy uses `gemini-3.1-flash-lite`), and agy's start-up availability probes.
- **agy's onboarding** is skipped by pre-seeding `cache/onboarding.json`, which **accepts the Google Cloud ToS screen on the user's behalf**.
- **Capability gaps, shown as N/A with reasons:**
  - Pi and dsh have no vanilla Claude route.
  - omp can't send Claude effort on Vertex (adaptive only).
  - agy expresses Flash thinking as a budget.
  - dsh is single-model only for now; the ACP driver is not wired yet.
- **Billing reconciliation (layer 5):** parked, as decided.

**Open items:**
1. Run `uv run geap-eval prices show`, then `prices review --yes` (human sign-off). Until then every cost carries the 🟠 "check" badge, by design.
2. Enable Claude Sonnet 5.5 in Model Garden for your-gcp-project.
3. Docker sandbox backend, the dsh ACP driver, and a Gemini latency investigation: Flash calls took 20–45 s each at low thinking on `global`, which drives Pi's and agy's long wall times.

## 16. Completion and dashboard verification (2026-10-31)

**Run `verify-final-967104b3`:** 26/26 trials passed. It covered 7 harness variants (Claude Code, Pi, omp, agy, dsh PTC, dsh native, dsh ACP), 3 profiles (Flash low, Opus high, Argon + Flash subagent) and 2 tasks (simple + medium); 16 cells were N/A, each with a reason. It cost $10.24 at list price, with no task retries used. Two Argon 429s were classed `infra_quota` and retried with backoff. A follow-up live run (`live-check`, 3/3 passed) and a one-trial run (`log-check`) verified live mode.

**Dashboard verification:**
- `scripts/verify_dashboard.py` covers every view (Run Builder, Mission Control, Compare, Cost Center, Trial Inspector plus its 5 tabs, Quota & Health, Settings) in dark and light. The result is zero console errors, zero failed API calls and no NaN/undefined.
- Every screenshot was reviewed by hand against the database.
- Mission Control was also checked live during runs.

**Implemented in this round:**
- **Tasks:** the full 36-task suite, 36/36 valid on 3 consecutive validator runs.
- **dsh:** ACP driver (`dsh/acp`), PTC-off control (`dsh/native`), and native subagent-model roles.
- **Cost validation layer 4:** `geap-eval prices crosscheck` checks catalog list prices against the public pricing page (5/5 match) and derives dated promotions from quoted text: Argon 50% credits to 2026-11-30, Flash 3.8 introductory pricing to 2026-12-31. Promotions apply only after review. Cost is stored as **list** (catalog) and **effective** (after promotions).
- **New endpoints:** `/api/runs/{id}/infra|egress|log`; live spend and burn rate; persisted infra and scheduler events.

**Engine bugs found by real runs and fixed:**
1. **Swallowed submissions:** TUIs could swallow Enter while digesting a large paste (omp). Every submission is now confirmed, with Enter retried if nothing starts.
2. **Trial-id collisions across runs:** trial ids are now scoped to the run.
3. **Quota errors burned task retries:** a turn that ends on a 429 is now `infra_quota`, which uses infra backoff instead.
4. **Zero-call attempts labelled "unpriced":** they are now a known $0.
5. **Attempts left in `backoff`:** they are now finalised after the backoff.
6. **Aux probes counted as LLM retries:** they are now excluded.
7. **Meter shutdown hang and TLS-close log noise:** both fixed.
8. **Unknown `/api/*` paths returned the SPA with 200:** they now return 404.

**Still open, needs your decision:**
- **Price sign-off:** run `geap-eval prices show`, then `prices review --yes`. That signs off the SKU map and the promotions; until then costs carry the 🟠 badge and effective cost equals list.
- **Sonnet 5.5:** enable it in Model Garden for your-gcp-project.
- **Docker:** a Docker sandbox needs Docker Desktop running; it is installed but stopped.
- **Billing export:** BigQuery reconciliation (layer 5) is parked.


## 17. Capability fixes (Vertex AI mode only)
Claude is always called in Vertex AI mode (`rawPredict` / `streamRawPredict`), never through the first-party Anthropic API. An earlier experiment with an Anthropic-protocol bridge was removed at the user's request.

| Gap | Fix | Verified on the wire |
|---|---|---|
| Pi had no Claude | Community Vertex extension `@pgilad/pi-vertex-anthropic` (Vertex SDK + ADC; reviewed: deps are Anthropic SDK, Vertex SDK and google-auth; network goes to aiplatform only). Installed at its latest version under tools/ | Effective effort low and max match (mid-conversation `output_config`) |
| omp couldn't send Claude effort | omp extension `before_provider_request` re-attaches omp's own thinking level as `output_config.effort` (omp's catalog rule is outdated for Opus 5.5) | effort low and max present; all 200s |
| agy sends a budget for Flash | No documented control. `--effort` makes agy ignore `--model` (it ran Argon or 3.7 Flash instead), so it is never passed. Cells stay runnable, labelled "budget" | n/a |
| dsh has no Claude | Remains N/A: vanilla dsh has only a first-party Anthropic route; custom plugins are out of scope | n/a |

New safeguard: an attempt whose calls never reach the configured model is marked `invalid_model`.
