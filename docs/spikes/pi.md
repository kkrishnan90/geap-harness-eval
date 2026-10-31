# Spike: Pi, native interactive TUI on GEAP (Vertex AI) with ADC

Phase 0, 2026-10-30. Pi **1.4.0** (`@earendil-works/pi-coding-agent`), Node v24.20.0, macOS arm64. Every model call went to `your-gcp-project` / `global` through user ADC (quota project `your-gcp-project`).

Status labels: **VERIFIED** means a programmatic PTY run (ptyprocess + pyte, no human) showed it. **UNVERIFIED** means it comes from docs, source or inference and was not exercised.

Reference script: `docs/spikes/pi_drive.py`. Fixtures: `tests/fixtures/pi/`.

---

## 1. Install, version, "latest"

| Fact | Status |
|---|---|
| `npm install --prefix tools/pi @earendil-works/pi-coding-agent@latest`. Binary: `tools/pi/node_modules/.bin/pi`. npm warns about un-allowlisted install scripts (`@google/genai` preinstall no-op, `protobufjs` postinstall); Pi works regardless. | VERIFIED |
| `pi --version` prints `1.4.0`. | VERIFIED |
| `npm view @earendil-works/pi-coding-agent version dist-tags --json` returns `latest: 1.4.0` (`legacy-node20: 0.74.2` also exists). Use `dist-tags.latest`. | VERIFIED |
| `PI_SKIP_VERSION_CHECK=1` disables the pi.dev latest-version request, `PI_TELEMETRY=0` disables install telemetry and attribution headers, `PI_OFFLINE=1` disables automatic network activity, including catalog refreshes. All three were set in the final run, which worked. | VERIFIED (that they work; their egress effect UNVERIFIED) |

## 2. Launch recipe

**argv** (VERIFIED):
```
tools/pi/node_modules/.bin/pi --provider google-vertex --model <id>:<thinking> --session-dir <out>/sessions
```
Examples: `--model gemini-3.8-flash:low`, `--model gemini-4-argon:high`. With stdin and stdout on a PTY, Pi opens the full-screen TUI (`tuiMode: fullscreen` default). No `-p` or `--mode` is used. cwd = the workspace realpath. Pi loads `AGENTS.md`/`CLAUDE.md` from the cwd **and its parent directories**, so never place workspaces under `~/` (it has an `AGENTS.md`).

**env** (empty env + allowlist, VERIFIED):
```
PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
LANG=en_US.UTF-8
TERM=xterm-256color
HOME=<attempt>/home                      # only .config/gcloud/application_default_credentials.json (0600)
TMPDIR=<attempt>/home/tmp
GOOGLE_CLOUD_PROJECT=your-gcp-project
GOOGLE_CLOUD_QUOTA_PROJECT=your-gcp-project
GOOGLE_CLOUD_LOCATION=global
PI_CODING_AGENT_DIR=<attempt>/home/.pi/agent
PI_SKIP_VERSION_CHECK=1
PI_TELEMETRY=0
PI_OFFLINE=1
GEAP_MARKER_FILE=<out>/pi_marker.jsonl   # read by our marker extension
```
- ADC detection: the `google-vertex` provider counts as authenticated when `~/.config/gcloud/application_default_credentials.json` exists **and** `GOOGLE_CLOUD_PROJECT` and `GOOGLE_CLOUD_LOCATION` are set. No `/login` and no `auth.json` entry are needed (VERIFIED: `auth.json` stays `{}`). Requests carried `x-goog-user-project: your-gcp-project` (VERIFIED).
- No API key anywhere. `GOOGLE_CLOUD_API_KEY` must **not** be set, because it takes precedence over ADC.

**Agent dir files:**
- `settings.json`: `{"lastChangelogVersion": "1.4.0"}`. Pi writes this itself on first run; seeding it avoids a changelog notice after updates.
- `models.json` (Meter mode only, see §7).
- `extensions/geap-marker.ts` (completion marker, see §4). Personal extensions in `<agent-dir>/extensions/` load without project trust (VERIFIED: the startup listing shows `[Extensions] geap-marker.ts`).
- `bin/fd`: see the first-run hazard below.

## 3. First-run dialogs

**There are none** (VERIFIED, fixture `first_run_unseeded/`, completely unseeded agent dir). Pi shows the header (`▀▀█ v1.4.0`, key hints) and goes straight to the editor. Project-trust prompts appear only if the workspace contains `.pi/settings.json` or other trust-protected resources (docs; seed tasks must not ship `.pi/`). `defaultProjectTrust` (`ask|always|never`, agent-dir settings only) can force it (UNVERIFIED).

**Hazard: first-run `fd` download** (VERIFIED). On a fresh agent dir Pi prints `fd not found. Downloading...` and fetches `fd` from GitHub into `<agent-dir>/bin/fd` (fd 10.5.0). Pre-seeding a cached `fd` binary at `<agent-dir>/bin/fd` stops the download (VERIFIED, `fd_downloaded: false`). `rg` is taken from PATH (`/opt/homebrew/bin/rg`). In a Linux container, cache the matching Linux `fd` once per run.

Mid-session: `/model <provider>/<id>` and `/thinking <level>` with arguments switch immediately with no dialog (VERIFIED). Without arguments they open selectors (UNVERIFIED for unattended use, not needed).

## 4. Ready signature, submission, completion

- **Ready** (VERIFIED): footer regex `\S+ • (off|minimal|low|medium|high|xhigh|max)\s*$` (e.g. `gemini-3.8-flash • low`, right-aligned on the last row), plus no busy marker, plus marker `session_start` written, plus 1.5s with no screen change. Ready time was about 2 to 3s after spawn.
- **Busy** (VERIFIED): `⠸ Working` (braille spinner) in the top border of the editor box. Regex: `[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏] Working`. Errors are rendered inline (`Error: …`). After the turn, the footer shows usage `↑2.7k ↓88 $0.002 0.1%/1.0M (auto)`.
- **Submit** (VERIFIED): bracketed paste `ESC[200~…ESC[201~`, 0.3s, then `\r`. Multi-line prompts arrive as one user message.
- **Completion: marker extension** (VERIFIED). `geap-marker.ts` (embedded in `pi_drive.py`) appends JSON lines for `session_start` (includes `sessionFile`), `agent_start`, `turn_end`, `agent_end`, `agent_settled` and `session_shutdown`. Use **`agent_settled`**, not `agent_end`. Pi docs warn that retries, compaction and queued messages start another run after `agent_end`. VERIFIED with the wrong-base-URL run: four `agent_start`/`agent_end` pairs (3 retries) and only one `agent_settled`. The final driver needs `agent_settled` count +1, no `Working`, and 1.5s quiet.
  ```
  {"event":"agent_start","ts":…} {"event":"turn_end",…} {"event":"turn_end",…} {"event":"agent_end",…} {"event":"agent_settled",…}
  ```
- Screen-idle fallback: ready regex with no `Working` for 10s.

## 5. Exit

Paste `/quit`, then `\r`. Pi prints `To resume this session: pi --session-dir <dir> --session <id>` and exits **rc 0** in under 1s (VERIFIED). The marker logs `session_shutdown`. (`ctrl+c`/`ctrl+d` clear the editor or exit, per the header hint; not used.)

## 6. Session files (Plane A)

- Path (VERIFIED): `<--session-dir>/<ISO timestamp with ':' and '.' → '-'>Z_<uuidv7>.jsonl`, e.g. `2026-10-30T16-16-49-796Z_01a18d99-8084-7347-bbdf-350b49be16cf.jsonl`. The marker's `session_start.sessionFile` gives the exact path. Without `--session-dir`: `<agent-dir>/sessions/--<cwd path>--/…` (docs, UNVERIFIED).
- Format: JSONL session **v3**, a tree linked by `id`/`parentId`. Entry types seen: `session` (header with cwd), `model_change` (`provider`, `modelId`), `thinking_level_change`, and `message` with roles `system` (prompt `sections` plus `toolsAdded`), `user`, `assistant` and `toolResult`.

Field mapping (VERIFIED against Meter `usageMetadata`, fixture `argon_high_tool_error_model_and_thinking_switch/`):

| Metric | Pi session (`assistant.message.usage`) | Meter (Gemini `usageMetadata`) |
|---|---|---|
| uncached input | `input` | `promptTokenCount − cachedContentTokenCount` (subtraction per Pi changelog; caching was never non-zero here) |
| cache read | `cacheRead` | `cachedContentTokenCount` (UNVERIFIED: no cache hit observed) |
| cache write | `cacheWrite` (always 0 for Gemini) | n/a |
| output **incl. thinking** | `output` = candidates + thoughts (196 = 29 + 167) | `candidatesTokenCount` |
| thinking | `reasoning` | `thoughtsTokenCount` |
| total | `totalTokens` | `totalTokenCount` |
| cost (Pi's catalog, not authoritative) | `usage.cost.{input,output,cacheRead,cacheWrite,total}` | — |
| model / level | `model`, `thinkingLevel` per assistant message | `modelVersion` |
| stop | `stopReason` (`toolUse`, `stop`, `error`), `rawStopReason` (`STOP`), `errorMessage` | `finishReason` |
| latency | `durationMs` | — |
| tool call | `content[].type=="toolCall"` → `{id, name, arguments, thoughtSignature}` | `functionCall` part |
| tool result | `role=="toolResult"` → `{toolCallId, toolName, content, isError, durationMs}` | `functionResponse` in the next request |
| tool error | `isError: true`, e.g. bash `cat: nonexistent_file_xyz: …\n\nCommand exited with code 1` | |
| traffic type | — | `trafficType: ON_DEMAND` |

Built-in tools declared: `read`, `bash`, `edit`, `write` (default). Pi's system prompt is small (about 1.3k tokens, versus about 18.7k for Claude Code).

## 7. Meter / base-URL override

`<agent-dir>/models.json` (VERIFIED):
```json
{"providers": {"google-vertex": {"baseUrl": "http://127.0.0.1:<port>/v1/projects/your-gcp-project/locations/global"}}}
```
- **Caveat** (VERIFIED, fixture `wrong_baseurl_400_error/`): with a bare `baseUrl` of `http://127.0.0.1:<port>`, the google-genai SDK (custom base URL, `ResourceScope.COLLECTION`) sends `POST /v1/publishers/google/models/gemini-3.8-flash:streamGenerateContent` **without** `projects/…/locations/…`. Vertex answers `400 INVALID_ARGUMENT RESOURCE_PROJECT_INVALID`. The project and location must be in the baseUrl. A `/vN` segment in the baseUrl makes Pi set `apiVersion: ""`.
- Upstream path (VERIFIED): `POST /v1/projects/your-gcp-project/locations/global/publishers/google/models/<model>:streamGenerateContent?alt=sse` to `aiplatform.googleapis.com`. Headers: `authorization: Bearer <ADC token>` (forwarded unchanged), `x-goog-user-project: your-gcp-project`, `x-goog-api-client: google-genai-sdk/2.21.0 gl-node/v24.20.0`, `User-Agent: pi/1.4.0 (darwin; node/v24.20.0; arm64)`.
- Request body: `contents`, `systemInstruction`, `tools[].functionDeclarations`, `toolConfig`, `generationConfig {maxOutputTokens: 65536, thinkingConfig {includeThoughts: true, thinkingLevel}}`.
- Direct (no Meter) traffic was not exercised separately. Every Pi model call in this spike went through the Meter.
- Latency note: one `gemini-3.8-flash` first call had a 36s time to first byte at the upstream (`createTime` was immediate). The second call took 1.2 to 1.7s. Model-side queueing.

## 8. Thinking control

| Control | Sent (`generationConfig.thinkingConfig`) | Status |
|---|---|---|
| `--model gemini-3.8-flash:low` | `{includeThoughts: true, thinkingLevel: "LOW"}` | VERIFIED |
| `--model gemini-4-argon:high` | `thinkingLevel: "HIGH"`, **never `thinkingBudget`** (Argon-safe) | VERIFIED |
| `/thinking medium` (in session) | `thinkingLevel: "MEDIUM"`; screen `Thinking level: medium`; session `thinking_level_change` | VERIFIED |
| `--thinking <level>` flag | overrides the `:level` suffix | UNVERIFIED |
| `minimal`/`xhigh`/`max` on 3.8 Flash / Argon | catalog `thinkingLevelMap` marks them `null` (unsupported), so Pi clamps | UNVERIFIED (from catalog JSON) |

Verify from the Meter request body (`generationConfig.thinkingConfig.thinkingLevel`), cross-check with `thoughtsTokenCount` in the response, and with `assistant.message.thinkingLevel` in the session.

## 9. Model switching, multi-model, Claude

- `/model google-vertex/gemini-3.8-flash` switches immediately (screen `Model: gemini-3.8-flash`). It keeps the current thinking level (`high`), writes `model_change`, and the next request goes to the new model path (VERIFIED).
- `ctrl+p` cycles models in `--models` scope; `shift+tab` cycles thinking (docs, UNVERIFIED).
- **Subagents:** Pi has no built-in subagent tool. The package ships `examples/extensions/subagent/` (spawns separate `pi` processes, agents in `~/.pi/agent/agents/*.md` with per-agent model frontmatter, plus workflow prompts). UNVERIFIED; it would be a non-vanilla add-on.
- **Claude on Vertex.**
  - **First-party: does not exist.** The built-in `google-vertex` provider has only Gemini models (catalog: 2.5 → 3.8-flash, `gemini-4-argon`) and only the `publishers/google` API. The built-in `anthropic` provider talks to the Anthropic API with API-key or OAuth credentials, not Vertex. No `rawPredict` code exists in pi-ai.
  - **Third-party, VERIFIED working:** npm `@pgilad/pi-vertex-anthropic@0.9.0` (MIT, deps `@anthropic-ai/vertex-sdk ^0.20.4`, `google-auth-library`; registers provider `vertex-anthropic`, models include `claude-opus-5-5`). Fixture: `claude_via_community_vertex_anthropic_ext/`. Recipe:
    - install into an isolated prefix with `npm install --prefix <dir> --ignore-scripts @pgilad/pi-vertex-anthropic@0.9.0`;
    - launch with `pi -e <dir>/node_modules/@pgilad/pi-vertex-anthropic --provider vertex-anthropic --model claude-opus-5-5:low …`;
    - env: `ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project`, `CLOUD_ML_REGION=global`, and `ANTHROPIC_VERTEX_BASE_URL=http://127.0.0.1:<port>/v1` for Meter mode;
    - seed `<agent-dir>/auth.json` with the extension's sentinel, which skips its `/login`: `{"vertex-anthropic":{"type":"oauth","access":"adc","refresh":"adc","expires":<now+24h ms>,"projectId":"your-gcp-project","region":"global"}}`.
    - Upstream: `…/publishers/anthropic/models/claude-opus-5-5:streamRawPredict` with 200.
    - **Effort caveat:** the top-level `output_config.effort` is always `"high"`. The requested level is sent as a **mid-conversation system message** `{"role":"system","content":[],"output_config":{"effort":"low"}}` (beta `mid-conversation-output-config-2026-07-01`). The Meter must read the last such message to know the effective effort.
    - Its session usage has `cacheWrite` but no TTL split (the Meter shows `ephemeral_5m`).
    - This is not vanilla. Use it only if the plan accepts a pinned community provider.

## 10. Fixtures (`tests/fixtures/pi/`)

| Dir | Content |
|---|---|
| `basic_drive_script/` | `pi_drive.py --meter --fd-cache …`: cast, events, marker log, session JSONL, 2 meter records, no fd download |
| `first_run_unseeded/` | first launch with an empty agent dir: no dialogs, fd download message |
| `argon_high_tool_error_model_and_thinking_switch/` | Argon `:high`, bash `isError: true`, `/model` → 3.8 Flash, `/thinking medium`; 4 meter records with thinkingConfig + usageMetadata; raw PTY bytes |
| `wrong_baseurl_400_error/` | bare-host baseUrl → 400 `RESOURCE_PROJECT_INVALID`, retries, `agent_end`×4 vs `agent_settled`×1 |
| `claude_via_community_vertex_anthropic_ext/` | Pi + `@pgilad/pi-vertex-anthropic` on `claude-opus-5-5`, meter records with the mid-conversation effort message |

`Authorization` is `REDACTED` in all meter logs; the secret scan is clean.

## 11. Open risks

1. The `fd` download needs GitHub egress unless it is pre-seeded. The container needs a Linux `fd` cache.
2. Claude through Pi depends on a third-party extension, and it encodes effort unusually. The Meter parser must handle the mid-conversation `output_config`.
3. The Pi TUI footer and spinner strings are version-specific. Keep them in a per-version pattern file.
4. `cacheWarming` defaults to `"streaming"`. No warm calls were seen for Gemini (no `promptCache` in the Vertex catalog), but they may occur for the Claude extension (it sets `promptCache`) and would show up as extra Meter calls and `usage` entries with `kind: cache_warm`. UNVERIFIED.
5. Pi retries provider failures automatically. In `wrong_baseurl_400_error/` it made 3 attempts that never connected (`fetch failed`: the spike Meter was not listening yet; our startup race, since fixed by the in-process Meter) and then showed `Retry failed after 3 attempts: <400 body>`. Each attempt is its own `agent_start`/`agent_end` pair and, when it connects, its own Meter call. Count retries from the Meter. Whether a plain 400 by itself is retried is UNVERIFIED.
6. PI_OFFLINE's exact network coverage (fd download, models-store refresh) is unverified. It was set together with the fd pre-seed.
