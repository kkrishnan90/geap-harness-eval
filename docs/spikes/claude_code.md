# Spike: Claude Code, native interactive TUI on GEAP (Vertex AI) with ADC

Phase 0, 2026-10-30. Claude Code **2.1.314**, macOS arm64, Node not needed (native binary). Every model call went to `your-gcp-project` / `global` through user ADC (`you@example.com`, quota project `your-gcp-project`).

Status labels: **VERIFIED** means a programmatic PTY run (ptyprocess + pyte, no human) in this spike showed it. **UNVERIFIED** means it comes from docs, binary strings or inference and was not exercised.

Reference script: `docs/spikes/claude_code_drive.py` (full unattended run, built-in Meter). Fixtures: `tests/fixtures/claude_code/`.

---

## 1. Install, version, "latest"

| Fact | Status |
|---|---|
| `npm install --prefix tools/claude_code @anthropic-ai/claude-code@latest`. The wrapper's postinstall hard-links the platform package `@anthropic-ai/claude-code-darwin-arm64` over `bin/claude.exe` (a 279 MB native Bun binary). Binary: `tools/claude_code/node_modules/.bin/claude`. npm warns that the postinstall script is "not yet covered by allowScripts", but the binary was in place and worked. | VERIFIED |
| `claude --version` prints `2.1.314 (Claude Code)`. Parse with `split()[0]`. | VERIFIED |
| Resolving "latest": `npm view @anthropic-ai/claude-code version dist-tags --json` returns `latest: 2.1.314`, `next: 2.1.314`, `stable: 2.1.308`. Use `dist-tags.latest`. | VERIFIED |
| `DISABLE_AUTOUPDATER=1` keeps the isolated install fixed for the run. | set; no auto-update seen |

## 2. Launch recipe (argv, env, config files)

**argv** (VERIFIED):
```
tools/claude_code/node_modules/.bin/claude --dangerously-skip-permissions --session-id <uuid4> --effort <low|medium|high|xhigh|max>
```
- `--dangerously-skip-permissions` works in interactive mode. The footer reads `⏵⏵ bypass permissions on (shift+tab to cycle)`, and transcript records show `permissionMode: bypassPermissions` and `permissionDecision.reasonType: "mode"`.
- `--session-id` makes the transcript file name deterministic (`<uuid>.jsonl`).
- cwd = the workspace **realpath**. On macOS, `/tmp/...` resolves to `/private/tmp/...`, and the trust key must match the realpath.
- Do **not** put workspaces under `~/`: Claude Code walks parent directories for `CLAUDE.md`/`AGENTS.md`, and `~/AGENTS.md` exists. (UNVERIFIED that it would load; it is avoided by construction.)

**env** (empty env + allowlist, VERIFIED working; nothing inherited from the parent Claude Code session):
```
PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin
LANG=en_US.UTF-8
TERM=xterm-256color
HOME=<attempt>/home                    # holds only .config/gcloud/application_default_credentials.json (0600)
TMPDIR=<attempt>/home/tmp
CLAUDE_CODE_USE_VERTEX=1
ANTHROPIC_VERTEX_PROJECT_ID=your-gcp-project
CLOUD_ML_REGION=global
GOOGLE_CLOUD_QUOTA_PROJECT=your-gcp-project
CLAUDE_CONFIG_DIR=<attempt>/home/.claude
ANTHROPIC_MODEL=claude-opus-5-5
ANTHROPIC_DEFAULT_OPUS_MODEL=claude-opus-5-5
ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-5-5     # see the tier-probe hazard below
ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-5-5       # see the tier-probe hazard below
CLAUDE_CODE_SUBAGENT_MODEL=claude-opus-5-5
DISABLE_AUTOUPDATER=1
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1
CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1
ANTHROPIC_VERTEX_BASE_URL=http://127.0.0.1:<meter-port>/v1   # Meter mode only
```
- ADC: the ADC file has `quota_project_id: your-gcp-project`, and every request carried `x-goog-user-project: your-gcp-project`. **VERIFIED** (`meter.jsonl` request headers).
- **Hazard: startup tier probes. VERIFIED.** If the sonnet or haiku tier is "unpinned", Claude Code (`[vertex-fallback] unpinnedTiers=2`) sends `max_tokens:1` probes at startup to `claude-sonnet-4-5@20250929:rawPredict` and `claude-haiku-4-5@20251001:rawPredict`. Both returned 200 on your-gcp-project, and the haiku probe answered as `claude-haiku-4-5-20251001`. Fixture: `startup_tier_probes_unpinned/`.
  - A tier counts as pinned only when its env var names a model **of the same family**. `ANTHROPIC_DEFAULT_SONNET_MODEL=claude-opus-5-5` does *not* pin it: the probes still ran.
  - Setting `ANTHROPIC_DEFAULT_SONNET_MODEL=claude-sonnet-5-5` and `ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-5-5` removed the probes (VERIFIED, zero startup calls). `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` also removes them (VERIFIED), but it changes how settings and auth are sourced, so it is not used.
  - Consequence: anything that resolves the sonnet or haiku tier now gets a 404, because Sonnet 5.5 is not enabled and Haiku 5.5 has no GEAP SKU. No such call happened in the runs here. The Meter should flag any non-allowed model path.
- `CLAUDE_CODE_DISABLE_OFFICIAL_MARKETPLACE_AUTOINSTALL=1`: without it, a fresh config dir clones `anthropics/claude-plugins-official` from GitHub into `CLAUDE_CONFIG_DIR/plugins/marketplaces/` (VERIFIED). No plugin from it is installed; only the 3 built-in plugins load. With the variable set, no `plugins/` directory is created (VERIFIED).

**`$CLAUDE_CONFIG_DIR/settings.json`** (VERIFIED):
```json
{
  "theme": "dark",
  "skipDangerousModePermissionPrompt": true,
  "effortLevel": "low",
  "hooks": {"Stop": [{"hooks": [{"type": "command",
     "command": "cat >> '<out>/stop_hook.jsonl'; echo >> '<out>/stop_hook.jsonl'"}]}]}
}
```
`effortLevel` accepts only `low|medium|high|xhigh` (schema in the binary). For `max`, use `--effort max`.

**`$CLAUDE_CONFIG_DIR/.claude.json`** (VERIFIED):
```json
{"hasCompletedOnboarding": true, "lastOnboardingVersion": "2.1.314",
 "projects": {"<workspace realpath>": {"hasTrustDialogAccepted": true}}}
```

## 3. First-run dialogs (unseeded) and how they are skipped

Fixture `first_run_unseeded_dialogs/` (screens 01 to 04, cast, raw bytes). Shown in this order with no seeding:

| # | Screen text (regex) | Skip by seeding | Auto-answer |
|---|---|---|---|
| 1 | `Choose the text style that looks best with your terminal` (theme list, `❯ ✔ Dark mode` preselected) | `settings.json theme` + `.claude.json hasCompletedOnboarding` | `\r` |
| 2 | `Security notes:` … `Press Enter to continue…` | `hasCompletedOnboarding` | `\r` |
| 3 | `Accessing workspace:` … `Quick safety check: Is this a project you created or one you trust?` with `❯ No, exit` / `Yes, I trust this folder` | `projects[<realpath>].hasTrustDialogAccepted` | `\x1b[B\r` (**default is "No, exit"**: Enter alone exits with rc 1, VERIFIED) |
| 4 | Bypass-permissions consent | `skipDangerousModePermissionPrompt: true` | never reached in unseeded run (exit at 3); text UNVERIFIED |

All four seeded together give **no dialogs** (VERIFIED in 9 runs). Mid-session confirmation dialogs seen:
- `/effort <level>` opens `Change effort level?` / `Your next response will be slower and use more tokens` / `This conversation is cached for the current effort level…` / `❯ 1. Yes, switch to high` / `2. No, go back`. Text typed into it is consumed (VERIFIED: a pasted prompt + Enter selected "Yes" and the prompt was lost). Answer with `1`.

## 4. Ready signature and prompt submission

- **Ready** (VERIFIED): regex `^❯(\s|$)` (multiline) on the pyte display, plus `bypass permissions on` in the footer, plus no busy marker, plus 1.5s with no screen change. The banner line 2 confirms routing: `Opus 5.5 with low effort · Google Vertex AI`. The ready time was 3 to 10s after spawn.
- **Busy markers** (VERIFIED): the footer contains `esc to interrupt`; the spinner line is `· <Verb>…` (e.g. `· Wandering…`); on retry `✻ API error · Retrying in 0s · attempt 1/10`; with background agents `✻ Waiting for 1 background agent to finish`. Regex: `esc to interrupt|Waiting for \d+ background agent|Retrying in \d+s`.
- **Idle** after a turn (VERIFIED): `✻ <Verb> for <N>s · done <time>` above the input box, an empty `❯` line, and a footer without `esc to interrupt`.
- **Submit** (VERIFIED): bracketed paste `ESC[200~<text>ESC[201~`, a 0.3s pause, then `\r`. Multi-line prompts arrive intact (one user message containing `\n`). `t0` = the `\r` write.

## 5. Completion signal

- **Stop hook** (VERIFIED): the command hook receives one JSON object on stdin, for example:
  ```json
  {"session_id":"…","transcript_path":"<CLAUDE_CONFIG_DIR>/projects/<slug>/<session>.jsonl","cwd":"…",
   "prompt_id":"…","permission_mode":"bypassPermissions","effort":{"level":"low"},"hook_event_name":"Stop",
   "stop_hook_active":false,"last_assistant_message":"DONE","background_tasks":[],"session_crons":[]}
  ```
  It fired 26ms after the final `message_delta` (`stop_hook_summary` in the transcript). `transcript_path` is the authoritative transcript location.
- **Caveat** (VERIFIED, fixture `effort_max_subagent_tool_error/`): the model launched the subagent as a *background* agent, and Stop **fired twice**: once when the main turn parked (`I've started the subagent and am waiting…`, with `background_tasks: []` even then), and again at the real end. Stop alone is therefore not final. The reference driver requires Stop plus an idle screen (no `esc to interrupt`, no `Waiting for N background agent`) plus 3s quiet, with Meter quiescence as the plan's layer (b).
- Screen-idle fallback: ready regex, no busy markers, quiet for 10s.

## 6. Exit

Paste `/exit`, then `\r` (the autocomplete row `❯ /exit  Exit the CLI` appears and Enter executes it). The process prints `Resume this session with:` / `claude --resume <session-id>` and exits **rc 0** within about 0.4s (VERIFIED, all runs). SIGTERM then SIGKILL of the process group is the fallback (not needed in practice).

## 7. Session/transcript files (Plane A)

Paths (VERIFIED):
- Main transcript: `$CLAUDE_CONFIG_DIR/projects/<slug>/<session-id>.jsonl`. The slug is the cwd realpath with `/` replaced by `-` (existing `-` kept, so `/-Users` becomes `--Users`). Prefer `transcript_path` from the Stop hook.
- Subagents: `$CLAUDE_CONFIG_DIR/projects/<slug>/<session-id>/subagents/agent-<agentId>.jsonl` plus `.meta.json` (`{"agentType":"general-purpose","description":…,"toolUseId":…,"requestShape":"background","finished":true}`). Subagent lines have `isSidechain: true` and `agentId`.
- Also written: `history.jsonl`, `sessions/`, `backups/.claude.json.backup.*`, `projects/<slug>/memory/`.

JSONL record `type`s seen: `mode`, `permission-mode`, `atis-latch`, `file-history-snapshot`, `user`, `attachment` (environment, model identity, deferred tools, agent listing, skill listing, date, `prompt_snapshot` with the full system prompt), `api-request-shape`, `api-request-blob`, `api-request` (params: model, betas, max_tokens, thinking, output_config.effort, cacheControl), `assistant`, `tools-used`, `system` (`stop_hook_summary`, `turn_duration` with `durationMs`), `last-prompt`, and `cost-state`.

Field mapping (VERIFIED from fixtures):

| Metric | Where |
|---|---|
| uncached input | `assistant.message.usage.input_tokens` |
| cache read | `usage.cache_read_input_tokens` |
| cache write by TTL | `usage.cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` (total in `cache_creation_input_tokens`) |
| output | `usage.output_tokens` (whether it includes thinking is UNVERIFIED; Anthropic bills thinking as output) |
| thinking | `usage.output_tokens_details.thinking_tokens` |
| tier / speed | `usage.service_tier` (`standard`), `usage.speed` |
| model, ids | `message.model`, `message.id` (`msg_vrtx_…`), `requestId` (`req_vrtx_…`), `requestRef` → `api-request.id` |
| stop reason | `message.stop_reason` (`tool_use`, `end_turn`) |
| tool call | `assistant.message.content[].type=="tool_use"` → `{id, name, input}` |
| tool result | the next `user` line, `message.content[].type=="tool_result"` → `{tool_use_id, content, is_error}` plus `toolUseResult` (stdout/stderr/interrupted) |
| tool error | `is_error: true`, e.g. `"Exit code 1\ncat: nonexistent_file_xyz: No such file or directory"` |
| turn time | `system.subtype=="turn_duration"` → `durationMs` |
| session totals | `cost-state.modelUsage[<model>]` → `inputTokens, outputTokens, thinkingTokens, cacheReadInputTokens, cacheCreationEphemeral5mInputTokens, cacheCreationEphemeral1hInputTokens, costUSD`, plus `totalAPIDuration` and `totalAPIDurationWithoutRetries` |

**Pitfall** (VERIFIED): one API response is written as **one `assistant` line per content block**, and each line repeats the same `message.id` and the same full `usage`. Dedupe by `message.id` before summing, or token counts are double-counted.

Observed cache behaviour: Claude Code puts `cache_control: ephemeral` (5m) on system blocks 1 and 2 and on the last message. On `global`, consecutive requests often **re-created** the cache (`cache_read_input_tokens: 0`, `cache_creation ≈ 18.7k` on calls 1 and 2 of the same turn), and only some later calls read it (19,354 read). The 1h TTL was never used (`ephemeral_1h_input_tokens: 0`).

## 8. Meter / base-URL override

- `ANTHROPIC_VERTEX_BASE_URL=http://127.0.0.1:<port>/v1` sends all model traffic to the local forwarder. The forwarder relays the same path and query to `https://aiplatform.googleapis.com` with all headers, including `Authorization: Bearer <ADC access token>`, and the CLI keeps working (**VERIFIED**, every run). The token is minted by the CLI from ADC; the proxy never sees the refresh token.
- Upstream paths (VERIFIED):
  - Main and subagent turns: `POST /v1/projects/your-gcp-project/locations/global/publishers/anthropic/models/claude-opus-5-5:streamRawPredict` (SSE).
  - Startup tier probes (unpinned only): `POST …/models/claude-sonnet-4-5@20250929:rawPredict`, `…/claude-haiku-4-5@20251001:rawPredict`, with `max_tokens: 1`.
  - `/model <id>` validation: `POST …/models/<id>:rawPredict` with `max_tokens: 1`, message `"Hi"`.
- Request headers: `anthropic-beta: claude-code-20250219,interleaved-thinking-2025-05-14,web-search-2025-03-05,thinking-token-count-2026-05-13,tool-search-tool-2025-10-19,effort-2025-11-24,thinking-display-updates-2026-08-18`, `anthropic-version: 2023-06-01`, `x-claude-code-session-id: <session-id>`, `x-goog-user-project: your-gcp-project`, `x-app: cli`. Body `anthropic_version: vertex-2023-10-16`, `max_tokens: 128000`.
- SSE usage is in `message_start.message.usage` and `message_delta.usage` (final: `output_tokens`, `output_tokens_details.thinking_tokens`, cache fields).
- **Startup race (our bug, fixed):** when the forwarder was not yet listening, the CLI showed `API error · Retrying in Ns · attempt k/10`, and those attempts never reached the log. The reference script starts the forwarder in-process before spawning the CLI.

## 9. Thinking / effort control (interactive)

| Control | Request body sent | Status |
|---|---|---|
| `--effort low` | `thinking: {type: "adaptive", display: "updates"}`, `output_config: {effort: "low"}` | VERIFIED |
| `--effort max` | `output_config: {effort: "max"}` (subagent requests too) | VERIFIED |
| `settings.json effortLevel: "medium"` (no flag) | `output_config: {effort: "medium"}`; banner `◐ medium · /effort` | VERIFIED |
| `/effort high` mid-session | confirmation dialog (§3), then the banner shows `with high effort` and the setting is saved as the default | dialog VERIFIED; request after the switch UNVERIFIED |
| `--effort xhigh`, `--effort medium`/`high` as flags | expected `output_config.effort` = value | UNVERIFIED |
| `CLAUDE_CODE_EFFORT_LEVEL` env | exists in binary | UNVERIFIED |
| thinking off (`CLAUDE_CODE_DISABLE_THINKING`) | exists in binary | UNVERIFIED |

Verify the level that was actually sent from the Meter request body: `json.loads(req_body)["output_config"]["effort"]` and `["thinking"]["type"]`. The Stop hook payload also carries `effort.level`, and transcript `api-request.params.output_config` mirrors it. `thinking_tokens > 0` appeared at `max` (76, 92, 49), and the `low` runs showed 0.

## 10. Model switching and multi-model

- `/model` (no args) opens the picker (VERIFIED, fixture `model_picker_and_model_switch_404/`):
  `1. Default (currently Opus 5.5)`, `2. Sonnet 5.5 Custom Sonnet model (claude-sonnet-5-5)`, `3. Fable · Fable 5.1 …`, `4. Opus 5.5 ✔`, `5. Haiku 5.5`, then an effort slider (`←/→`), then `Enter to set as default · s to use this session only · Esc to cancel`. Esc gives `Kept model as Opus 5.5`. **Hazard:** the picker offers Fable 5.1, which has no GEAP SKU.
- `/model claude-sonnet-5-5` validates with a `rawPredict` probe, gets 404, prints `Model 'claude-sonnet-5-5' not found. Try 'claude-sonnet-5' instead`, and keeps the model (VERIFIED). A successful switch to another enabled model could not be shown, because only Opus 5.5 is enabled.
- Subagents (VERIFIED): `CLAUDE_CODE_SUBAGENT_MODEL=claude-opus-5-5`. The general-purpose subagent request went to `claude-opus-5-5` with its own system prompt (`You are an agent for Claude Code…`), 8 tools instead of 13, and the session effort (`max`). It is recorded in `subagents/agent-*.jsonl`. Telling a subagent apart in the Meter: system text, or the tool count.
- Tier vars `ANTHROPIC_DEFAULT_{OPUS,SONNET,HAIKU,FABLE}_MODEL` and `.claude/agents/*.md` frontmatter `model:` exist (strings and docs). Frontmatter routing is UNVERIFIED.

## 11. Fixtures (`tests/fixtures/claude_code/`)

| Dir | Content |
|---|---|
| `basic_drive_script/` | output of `claude_code_drive.py --meter --effort low`: cast, events (ready → t0 → stop_hook → complete → exit), stop-hook payload, transcript, 2 meter records |
| `first_run_unseeded_dialogs/` | theme, security notes, trust dialog; raw PTY bytes |
| `startup_tier_probes_unpinned/` | 4 meter records: 2 startup probes plus 2 turns |
| `effort_medium_then_effort_dialog/` | settings `effortLevel=medium`, `/effort high` confirmation dialog screen |
| `effort_max_subagent_tool_error/` | `--effort max`, background subagent transcript plus meta, Stop firing twice, Bash `is_error: true`, 5 meter records |
| `model_picker_and_model_switch_404/` | `/model` picker screen, `/model claude-sonnet-5-5` 404 validation record |

Raw bytes are in `pty_raw.bin` (spike driver) or reconstructable from `session.cast` (asciicast v2 with `o` and `i` events). In meter logs `Authorization` is `REDACTED`; a secret scan (`ya29.`, `refresh_token`, `client_secret`, PEM) is clean.

## 12. Open risks

1. Tier pins point at models that are not enabled (`claude-sonnet-5-5`, `claude-haiku-5-5`). Any internal haiku- or sonnet-tier call would 404 instead of silently using an old model. Watch the Meter for those paths, or have the Meter reject non-allowed models explicitly.
2. A Stop hook firing while background agents run must not be read as completion. Combine it with the screen and Meter layers.
3. Weak prompt-cache reuse on `global` inflates cache-write cost. This needs a larger sample before drawing conclusions.
4. Egress outside the Meter (OAuth token refresh to `oauth2.googleapis.com`, and anything else) was not captured. Container egress rules should allow the token endpoint.
5. TUI strings (`esc to interrupt`, `bypass permissions on`, dialog texts) are version-specific. Keep a pattern file per version and re-check them on every "latest" bump.
