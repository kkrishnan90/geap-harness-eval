# Phase-0 spike: Oh My Pi (omp) in native interactive mode on GEAP

Status: 2026-10-31. omp **18.14.0** (`@oh-my-pi/pi-coding-agent`), bun **1.4.4**, macOS arm64. Project `your-gcp-project`, location `global`, user ADC (`you@example.com`).
Reference driver: `docs/spikes/omp_drive.py`. Fixtures: `tests/fixtures/omp/`.

**VERIFIED** means it was run unattended in a PTY (ptyprocess + pyte, 220x60) and checked against the Meter log or session file. **UNVERIFIED** means it was read from source or docs only.

## 1. Install and version ("latest")

```bash
npm view @oh-my-pi/pi-coding-agent version            # resolve latest -> 18.14.0
npm install --prefix tools/omp @oh-my-pi/pi-coding-agent@latest
npm install --prefix tools/omp bun@latest             # REQUIRED: omp declares engines.bun >=1.4.4; ~/.bun/bin/bun is 1.3.8
tools/omp/node_modules/.bin/omp --version             # "omp/18.14.0"
```
- VERIFIED: `dist/cli.js` has the shebang `#!/usr/bin/env bun`. Put `tools/omp/node_modules/.bin` first on `PATH` so that both `omp` and the npm `bun` (1.4.4) resolve there. npm warns that postinstall scripts were skipped (`bun`, `onnxruntime-node`, `protobufjs`). omp and bun still worked without them.
- Freeze the version in the run lock with `omp --version`, `bun --version`, and the `runtime.version` that every session-jsonl record carries.
- Auto-update: `startup.checkUpdate: false`. In the Meter logs omp made no update calls.

## 2. Launch: argv, env, config (VERIFIED)

```text
argv: tools/omp/node_modules/.bin/omp -e <attempt>/geap-marker.ts --model google-vertex/<model-id>:<thinking>
cwd : task workspace
env : (empty env +) PATH=<tools/omp/node_modules/.bin>:/usr/bin:/bin:/usr/sbin:/sbin  HOME=<isolated>  LANG=en_US.UTF-8
      TERM=xterm-256color  TMPDIR=<attempt>/tmp
      GOOGLE_CLOUD_PROJECT=your-gcp-project  GOOGLE_CLOUD_QUOTA_PROJECT=your-gcp-project  GOOGLE_CLOUD_LOCATION=global
      PI_PROXY_GOOGLE_VERTEX=http://<attempt_token>:x@127.0.0.1:<meter_port>    # Meter routing (section 7)
      NODE_EXTRA_CA_CERTS=<attempt>/ca/ca.pem                                   # Meter MITM CA (omp shims this into Bun fetch)
      GEAP_MARKER_FILE=<attempt>/marker.jsonl                                   # completion extension (section 4)
HOME: only .config/gcloud/application_default_credentials.json (0600) + .omp/agent/config.yml
```
- Auth: the built-in `google-vertex` provider reads `~/.config/gcloud/application_default_credentials.json` (`authorized_user`), refreshes it at `https://oauth2.googleapis.com/token`, and sends `Authorization: Bearer`. It needs project and location from the env (`GOOGLE_CLOUD_PROJECT` or `GCP_PROJECT`/`GCLOUD_PROJECT`, and `GOOGLE_VERTEX_LOCATION` or `GOOGLE_CLOUD_LOCATION`/`VERTEX_LOCATION`). **No `models.yml` is needed.** omp sends no `x-goog-user-project` header. Quota and billing go to the project in the URL path, which is `your-gcp-project`.
- Upstream paths (VERIFIED in the Meter):
  - Gemini: `POST https://aiplatform.googleapis.com/v1/projects/your-gcp-project/locations/global/publishers/google/models/<id>:streamGenerateContent?alt=sse`
  - Claude: `POST https://aiplatform.googleapis.com/v1/projects/your-gcp-project/locations/global/publishers/anthropic/models/claude-opus-5-5@default:streamRawPredict`. The body has `anthropic_version: "vertex-2023-10-16"` and no `model`.
  - Token refresh: `POST https://oauth2.googleapis.com/token`.
- Model ids: Gemini `google-vertex/gemini-3.8-flash` and `google-vertex/gemini-4-argon`. Claude `google-vertex/claude-opus-5-5@default`; the `@default` revision suffix is omp's catalog id. **Claude on Vertex works out of the box** (VERIFIED: Opus 5.5 returned 200 with usage). `claude-sonnet-5-5@default` is in the catalog but not enabled on your-gcp-project.
- `config.yml`, written to `$HOME/.omp/agent/config.yml` (exact contents in `tests/fixtures/omp/*/config.yml`):
```yaml
startup: {setupWizard: false, checkUpdate: false, changelogMode: hidden, quiet: true}
telemetry: {otlpExportEnabled: false}
marketplace: {autoUpdate: "off"}
tools: {approvalMode: yolo}
enabledProviders: [google-vertex]
modelRoles:
  default: google-vertex/gemini-3.8-flash:low
  slow: google-vertex/claude-opus-5-5@default:high     # optional extra roles
```
- Hazard (VERIFIED): `--model` overrides `modelRoles.default` for the run. Keep the two consistent.
- Hazard (VERIFIED): at startup omp runs "model refresh" catalog discovery. With a blanket `PI_PROXY` it CONNECTs to third-party hosts (`api.venice.ai`, `zenmux.ai`, `catalog.stencil.so`, `api.kilo.ai`, `hyper.charm.land`, `api.commandcode.ai`, `coding-intl.dashscope.aliyuncs.com`) even with `enabledProviders: [google-vertex]`. With `PI_PROXY_GOOGLE_VERTEX`, those calls leave on the process's normal egress (in the container that is "deny"), which is harmless. omp falls back to its bundled catalog.

## 3. First run, dialogs, permissions

- VERIFIED: a fresh HOME without config shows a blocking wizard: `Setup step 1 of 5 / Sign in to your providers / ❯ ChatGPT Plus/Pro (Codex Subscription) …` (`tests/fixtures/omp/screens/first_run_setup_wizard.txt`). `startup.setupWizard: false` skips it completely.
- VERIFIED: there is no folder-trust prompt and no tool-permission prompt. `tools.approvalMode` defaults to `yolo`. We pin it in config; the run-scoped equivalents are `--auto-approve` and `--approval-mode yolo`. In the write and bash runs nothing was asked.
- Dialog patterns the driver must treat as failures: `Setup step \d+ of \d+`, `Select provider to login`.

## 4. Ready signature, submit, completion

- **Ready** (VERIFIED): `^ π > .*▶─`, then 1.5 s of screen stability. The composer is an inline box whose top border is the status line (` π > ◔ Gemini 3.8 Flash > 🗑 <cwd> ▶─0.8%─…`) and whose bottom border is `╰─`. omp renders inline, not on the alternate screen.
- **Busy**: the leading `π` becomes a spinner plus elapsed time (`⠹ 19s > …`), and `⎋ Working…` appears above the composer.
- **Submit** (VERIFIED): bracketed paste `ESC[200~ … ESC[201~`, a 0.4 s pause, then `\r`.
- **Slash commands must be typed character by character, not pasted.** VERIFIED: a pasted `/model …` was sent to the model as a user message. A typed `/model <selector>` was also sent to the model as a message. A typed `/exit` works.
- **Completion signal** (VERIFIED): an extension loaded with `-e` (`geap-marker.ts`, embedded in the driver and also in `tests/fixtures/omp/*/geap-marker.ts`):
  - It writes JSONL to `$GEAP_MARKER_FILE` on `session_start` (which includes `sessionFile`), `agent_start`, `turn_end`, `agent_end` (with the last message's `stopReason`, `model`, `usage`) and `session_shutdown`.
  - Rule: the latest `agent_end` comes after the latest `agent_start`, no newer `agent_start` follows for 3 s, the Meter has nothing in flight, and no spinner shows.
  - Why the 3 s guard: on a provider error omp shows `error; retried` and **starts a new agent loop** (agent_end with `stopReason:"error"`, then agent_start). VERIFIED with ETIMEDOUT errors through a dead proxy.
  - The extension loads lazily, after the composer accepts input. Its `session_start` still fires and the first prompt waits for it.
  - `t_end` comes from the Meter's last `t_end`, not from the detection time.

## 5. Exit (VERIFIED)
Type `/exit` and press `\r`. The process exited in about 0.2 s and the session file records `{"type":"custom","customType":"session_exit"}`. Fall back to SIGTERM, then SIGKILL of the process group; SIGTERM is recorded as `session_exit` `reason:"sigterm"`.

## 6. Session files (Plane A, VERIFIED)
- Path: `$HOME/.omp/agent/sessions/--<cwd with / replaced by ->--/<ISO-ts>_<sessionId>.jsonl`. The marker's `session_start.sessionFile` gives the exact path. There are also `agent.db`, `history.db` and `models.db` (sqlite) and logs in `$HOME/.omp/logs/omp.<date>.<pid>.log` (JSON lines, debug level, including proxy, ADC and retry decisions).
- Record types: `title`, `session` (`version:3`, `cwd`), `model_change` (`model`), `thinking_level_change` (`thinkingLevel`), `message`, `custom` (`system-prompt-digest`, `tool_execution_start`, `session_exit`), `title_change`. Every record carries `id`, `parentId`, `timestamp`, `runtime.version`.
- `message.message`:
  - `role:"user"`: `content[{type:"text"}]`.
  - `role:"assistant"`:
    - Content blocks are `text` or `toolCall` (`id`, `name`, `arguments`), plus thinking blocks when present.
    - Other fields: `api`, `provider`, `model`, `stopReason` (`stop` / `toolUse` / `error` / `aborted`), `duration`, `ttft`, `completedAt`.
    - `contextSnapshot` holds `promptTokens`, `nonMessageTokens`, `toolSchemaTokens`.
    - `usage` is `{input, output, cacheRead, cacheWrite, totalTokens, cost{…}}`.
  - `role:"toolResult"`: `toolCallId`, `toolName`, `isError` (bool), `content`.
- Usage semantics (VERIFIED against the Meter): `input` is **uncached** input (Gemini `promptTokenCount - cachedContentTokenCount`). `cacheRead` is `cachedContentTokenCount` or Claude `cache_read_input_tokens`. **There is no thinking-token field.** Use the Meter (`thoughtsTokenCount`, `output_tokens_details.thinking_tokens`). `cost` is omp's own catalog estimate and is not authoritative.
- Fixture: `tests/fixtures/omp/run_flash_tool_then_ctrlp_opus_high/sessions/**.jsonl` (write and bash tool calls, toolResult `isError:false`, model switch).

## 7. Meter routing (VERIFIED)
- **Gemini ignores `baseUrl`.** VERIFIED: `models.yml providers.google-vertex.baseUrl` did not reroute Gemini. In `pi-ai/src/providers/google-vertex.ts` the URL is built from `resolveVertexEndpointHost(location)`. `modelOverrides` has no `baseUrl` field (schema).
- Claude does honour a provider-level `baseUrl` that ends in `…/claude-opus-5-5@default:streamRawPredict`. `{project}`/`{location}` placeholders are allowed. It is provider-wide, so only one Claude model can be used per provider. VERIFIED, but not needed.
- **Chosen route, for both families: `PI_PROXY_GOOGLE_VERTEX=http://<token>:x@127.0.0.1:<port>` + `NODE_EXTRA_CA_CERTS=<ca.pem>`.** The Meter is an HTTP CONNECT proxy that terminates TLS for `*.googleapis.com` with a throwaway CA and denies every other CONNECT.
  - The proxy userinfo arrives as `Proxy-Authorization: Basic`, which gives per-attempt attribution. VERIFIED: `attempt_token` is set on every Meter record.
  - Use the provider-scoped variable, not `PI_PROXY`. With global `PI_PROXY` the early token refreshes sometimes failed with `ETIMEDOUT`. The root cause was most likely a Meter that was not listening yet: `uv run` start-up was about 20–30 s while the venv was being synced. Start the Meter with `.venv/bin/python` and wait for the port. Even so, `PI_PROXY_GOOGLE_VERTEX` is the minimal, deterministic choice. It also sends the token refresh through the Meter, where the body is never saved.
  - `HTTPS_PROXY` alone is **not** used by omp's provider fetch. The log shows `provider proxy resolved … source:"none"`. omp only uses `PI_PROXY*` (`pi-ai/src/utils/proxy.ts`).
  - The Meter must keep a big listen backlog and use daemon threads. It must forward `Authorization` unchanged and redact it in logs. It must answer chunked SSE. Python 3.13 rejects a leaf without AKI/SKI, so give the cert those extensions.
- Fixture: `tests/fixtures/omp/*/meter/meter.jsonl`, plus `NNNN.req.json` / `NNNN.resp.txt` (raw SSE).

## 8. Thinking control (VERIFIED from request bodies)
| selector | wire |
|---|---|
| `gemini-3.8-flash:low` | `generationConfig.thinkingConfig = {includeThoughts:true, thinkingLevel:"LOW"}` |
| `gemini-4-argon:low/medium/high` | `thinkingLevel: LOW/MEDIUM/HIGH`. **No `thinkingBudget`** is ever sent, so Argon works. |
| `claude-opus-5-5@default:high` (any level) | `thinking:{type:"adaptive", display:"summarized"}`, **no `output_config.effort`** |
| `claude-opus-5-5@default:off` | no `thinking` field |
- **Caveat:** omp cannot express Claude effort levels on Vertex. Its catalog rule `google-vertex.kdl` says `supports-output-effort #false` ("Vertex rejects output_config.effort"), and the `models.yml` compat schema has no override. agy does send `output_config.effort` to the same endpoint and gets 200 (see agy.md). Run Builder cells: omp × Opus = `adaptive` or `off` only. low/medium/xhigh/max are N/A with that reason.
- Catalog thinking ladders (`omp models google-vertex --json`): Gemini `low|medium|high`; Opus/Sonnet 5.5 `low|medium|high|xhigh|max`. `minimal` is not offered for these Gemini models (UNVERIFIED how it clamps). Other controls: `--thinking <level>`, `defaultThinkingLevel` (default `high`), Shift+Tab in the TUI.
- Verify the level from the Meter: Gemini `thinkingConfig` in the request plus `thoughtsTokenCount` in `usageMetadata`. Claude `thinking`/`output_config` plus `output_tokens_details.thinking_tokens`.

## 9. Multi-model roles and in-session switching (VERIFIED)
- Roles live in `config.yml` `modelRoles` (`default`, `smol`, `slow`, `plan`, `task`, `commit`, `tiny`, `memory`, `advisor`, …), plus CLI `--smol/--slow/--plan` (or env `PI_SMOL_MODEL`, `PI_SLOW_MODEL`, `PI_PLAN_MODEL`). Values are `provider/id[:thinking]`.
- **Switching in the session: Ctrl+P (`\x10`) cycles the assigned role models.** The footer shows `smol ┆ default  ◀ slow ▶` and the status line changes to the new model. VERIFIED: default Flash, Ctrl+P, slow Opus. The next request went to `claude-opus-5-5@default:streamRawPredict`.
- The `/model` picker also works but needs a key dance: type `/model`, `⏎`, type a search string, `⏎`, the role row (`default [smol] slow …`) `⏎`, the thinking row (`inherit off auto low medium high`) `⏎`. It writes the role to `config.yml` (screens in `tests/fixtures/omp/screens/`).
- **Hidden extra calls** (VERIFIED, they count as overhead): the first turn of a session triggers (a) a title "fork" request (full context plus `<title-request>`, same model and thinking) and (b) a small title-namer request (`You name coding-agent sessions…`, `max_tokens:1024` or Gemini `maxOutputTokens:5120`). So one user prompt gives about 3 model calls. They can be turned off with `--no-title`; that is not vanilla, so record the choice.

## 10. Caveats and open risks
- Bun runtime: Bun 1.4.4 must come from `tools/omp` (npm `bun`). PATH order matters.
- omp auto-retries provider errors silently (`error; retried`). Count retries from the Meter, not from the session file.
- Startup discovery egress to third-party catalogs. Container egress through the Meter only is fine, because the calls fail and omp falls back to its bundled catalog.
- `before_provider_request` (extension) is a second way to capture exact payloads if the MITM ever breaks.
- Not tested: `task` subagents (role `task`), compaction, very long runs, Linux container (CA and `NODE_EXTRA_CA_CERTS` should behave the same).
