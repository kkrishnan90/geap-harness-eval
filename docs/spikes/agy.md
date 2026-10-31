# Phase-0 spike: Antigravity CLI (agy) in native interactive mode on GEAP

Status: 2026-10-31. agy **1.4.11** (Go, Mach-O arm64), macOS. Project `your-gcp-project`, location `global`, user ADC (`you@example.com`).
Reference driver: `docs/spikes/agy_drive.py`. Fixtures: `tests/fixtures/agy/`.

**VERIFIED** means it was run unattended in a PTY (ptyprocess + pyte, 220x60) and checked against the Meter log, hook output or transcript. **UNVERIFIED** means it was read from strings, changelog or docs only.

## 1. Install and version ("latest") (VERIFIED)

```bash
mkdir -p tools/agy/bin && cp ~/.local/bin/agy tools/agy/bin/agy          # seed once from any copy
env -i PATH=tools/agy/bin:/usr/bin:/bin HOME=<scratch> tools/agy/bin/agy update
#  -> "⟳ Checking for updates... (current version 1.4.11)  ✓ You are already on the latest version."
tools/agy/bin/agy --version                                              # 1.4.11
```
- The updater replaces **the binary it runs from**. The user's earlier global update left `~/.local/bin/agy.<ts>.old` next to it. So running `tools/agy/bin/agy update` updates only `tools/agy`. VERIFIED: the sha256 of `~/.local/bin/agy` was unchanged after the spike.
- The update service is `https://antigravity-cli-auto-updater-974169037036.us-central1.run.app`. The interactive TUI also spawns a background updater at start (`auto_updater.go: Spawned background update process`). `AGY_CLI_DISABLE_AUTO_UPDATE=1` did **not** stop that spawn (VERIFIED in the log). The Meter's deny-by-default CONNECT policy blocked it (VERIFIED: `CONNECT antigravity-cli-auto-updater-… DENIED`).
- Recipe: run `agy update` explicitly at run start, freeze `agy --version` into the lock, and keep egress through the Meter so mid-run self-updates cannot happen. The changelog (`agy changelog`) is saved as `tests/fixtures/agy/agy_changelog_1.4.11.txt`.

## 2. Launch: argv, env, config files (VERIFIED)

```text
argv: tools/agy/bin/agy --dangerously-skip-permissions --model "<label>"
cwd : task workspace (must be listed in settings.trustedWorkspaces)
env : (empty env +) PATH=<tools/agy/bin>:/usr/bin:/bin:/usr/sbin:/sbin  HOME=<isolated>  LANG=en_US.UTF-8  TERM=xterm-256color
      TMPDIR=<attempt>/tmp  SHELL=/bin/bash
      GOOGLE_CLOUD_PROJECT=your-gcp-project  GOOGLE_CLOUD_QUOTA_PROJECT=your-gcp-project  GOOGLE_CLOUD_LOCATION=global
      AGY_ADC_AUTH=1                                   # <- the switch for "Agent Platform authentication" via ADC
      AGY_CLI_DISABLE_AUTO_UPDATE=1                    # harmless; see section 1
      HTTPS_PROXY=http://<attempt_token>:x@127.0.0.1:<meter_port>   SSL_CERT_FILE=<attempt>/ca/ca.pem   # Meter (section 7)
```
Files in the isolated HOME. **There is no `antigravity-oauth-token`.**
```text
~/.config/gcloud/application_default_credentials.json        (0600 copy of user ADC)
~/.gemini/antigravity-cli/settings.json:
  {"gcp": {"project": "your-gcp-project", "location": "global"},
   "colorScheme": "terminal", "showTips": false, "showFeedbackSurvey": false,
   "trustedWorkspaces": ["<ws>", "<realpath(ws)>"], "artifactReviewPolicy": "always-proceed"}
~/.gemini/antigravity-cli/cache/onboarding.json:
  {"consumerOnboardingComplete": false, "enterpriseOnboardingComplete": true, "onboardingComplete": false}
~/.gemini/config/hooks.json  +  ~/.gemini/config/geap_hook.sh                (section 4)
```
- **`AGY_ADC_AUTH=1` is required.** Without it, the gcp block plus ADC alone still shows `Select login method: 1. Google OAuth / 2. Use a Google Cloud project` (VERIFIED). Option 2, then "Continue with Google Cloud", starts a **browser OAuth flow** (an `accounts.google.com` URL with the Antigravity client id; caught by a fake `open` on PATH). That flow is not allowed here.
- With `AGY_ADC_AUTH=1` the banner shows `ADC: you@example.com (Agent Platform) / GCP Project: your-gcp-project`. The log shows `applyAuthResult: … authMethod=adc, quotaProject=your-gcp-project`. Requests carry `X-Goog-User-Project: your-gcp-project` and the User-Agent `antigravity/cli/1.4.11 (aidev_client; …; auth_method=adc)`.
- `GOOGLE_VERTEX_BASE_URL` (a genai-SDK string in the binary) is **ignored** by agy. VERIFIED: traffic still went to aiplatform.googleapis.com. `GOOGLE_GEMINI_BASE_URL` only applies with `modelProvider:"gemini"` and an API key, which is not allowed here. `AGY_LLM_GATEWAY_*` is a separate enterprise-gateway auth mode (UNVERIFIED, not used).
- `SHELL=/bin/bash` matters. Without `SHELL`, one `run_command` (`cat hello.txt`) took **70 s**; with it, about 2 s (VERIFIED in two runs; the root cause is not proven).

## 3. First-run dialogs and permissions (VERIFIED)
| screen (regex) | cause | pre-seed that removes it |
|---|---|---|
| `Select login method` | no `AGY_ADC_AUTH` | env `AGY_ADC_AUTH=1` |
| `Choose your color scheme:` → `Terms of Service & Data Use … [Previous] > Done` | first ADC onboarding | `cache/onboarding.json` with `enterpriseOnboardingComplete:true` (this is what agy writes after you press Done). `colorScheme` in settings alone is not enough. |
| `Do you trust the contents of this project?` | workspace not trusted | `settings.trustedWorkspaces` holding the cwd and its realpath (`/tmp` vs `/private/tmp`) |
| `ADC authentication failed. Please verify your Application Default Credentials` | token refresh failed. Seen when the proxy was not listening yet: `proxyconnect tcp: dial tcp 127.0.0.1:…: connect: operation timed out` | start the Meter before agy and wait for its port |
- Pre-seeding `onboarding.json` accepts the GCP Terms of Service screen on the user's behalf. Record that in the run config.
- Tool approval: `--dangerously-skip-permissions` works in the TUI. VERIFIED: `write_file` and `run_command` ran with no prompt. Settings equivalents (UNVERIFIED in isolation): `toolPermission:"always-proceed"`, `artifactReviewPolicy:"always-proceed"`.
- Screens: `tests/fixtures/agy/screens/*.txt`.

## 4. Ready, submit, completion (VERIFIED)
- **Ready:** `^\? for shortcuts` (footer), then 1.5 s of stability. The prompt row is `>` between two full-width `─` rules. The footer right side shows `<Model> · <effort>`, for example `Gemini 3.8 Flash · low`. pyte leaves stale fragments of the onboarding art (`Welcome … not signed in`) because agy relies on partial redraws, so do not match on those.
- **Busy:** `^esc to cancel` footer and/or a braille spinner with `Loading...`.
- **Submit:** bracketed paste of the prompt, a 0.4 s pause, then `\r`. **Type slash commands** character by character: `/model <label>` and `/exit` work when typed.
- **Completion: native hooks.** Global `~/.gemini/config/hooks.json` (hooks in `settings.json` are *not* loaded):
```json
{"geap-marker": {
  "SessionStart":  [{"command": "<home>/.gemini/config/geap_hook.sh SessionStart",  "timeout": 10}],
  "PreInvocation": [{"command": "<home>/.gemini/config/geap_hook.sh PreInvocation", "timeout": 10}],
  "PostInvocation":[{"command": "<home>/.gemini/config/geap_hook.sh PostInvocation","timeout": 10}],
  "PostToolUse":   [{"matcher": "*", "hooks": [{"command": "<home>/.gemini/config/geap_hook.sh PostToolUse", "timeout": 10}]}],
  "Stop":          [{"command": "<home>/.gemini/config/geap_hook.sh Stop", "timeout": 10}]}}
```
  - The hook reads a JSON payload on stdin and must print JSON on stdout. `Stop` needs `{"decision":"stop"}` (any value other than `continue` lets it stop). The others take `{}`.
  - Payload fields seen: `conversationId`, `modelName` (for example `gemini-3.8-flash-low`, `claude-opus-5-5-low`), `transcriptPath`, `artifactDirectoryPath`, `workspacePaths`, `lastUserInput`, `invocationNum`, `initialNumSteps`, `stepIdx`, `toolCall{name,args}`, `error`.
  - `Stop` adds `executionNum`, `terminationReason` (seen: `NO_TOOL_CALL`) and `fullyIdle` (`true`).
  - Completion rule: a `Stop` record after the submission with `fullyIdle:true`, the Meter has nothing in flight for 2 s, and no spinner. `t_end` comes from the Meter's last `t_end`.
  - The hook script runs without a shell wrapper, so give it an absolute path and an executable bit.

## 5. Exit (VERIFIED)
Type `/exit` and press `\r`. The process exits cleanly in under 1 s. Fall back to SIGTERM, then SIGKILL of the process group.

## 6. Session / transcript files (Plane A, VERIFIED)
The app data dir is `$HOME/.gemini/antigravity-cli/`:
- `brain/<conversationId>/.system_generated/logs/transcript.jsonl`: args are JSON-encoded strings.
- `transcript_full.jsonl`: the same steps with typed args. The hook's `transcriptPath` points here. Chunked copies are under `logs/chunks/…`; tool outputs are under `steps/<n>/output.txt`.
- Steps look like `{step_index, source: USER_EXPLICIT|MODEL, type: USER_INPUT|PLANNER_RESPONSE|GENERIC, status, created_at, content?, tool_calls?[{name,args}], input_tokens, cache_read_tokens, output_tokens}`.
  - Tool results are the following `GENERIC` steps (for example `Command exited with code 0.\n\nCommand output:\nhi`).
  - Tool error status: the `PostToolUse` hook `error` field. Changelog 1.4.11 says failed calls are now passed to the agent as errors.
  - Model switches show up as `<USER_SETTINGS_CHANGE>` text inside the next USER_INPUT.
- Usage caveats (VERIFIED against the Meter):
  - For Claude, `input_tokens` = `input_tokens + cache_creation_input_tokens` (11048 = 308 + 10740). Cache writes are therefore not separable from the transcript.
  - There is no thinking-token field. Use the Meter for both.
  - In these runs agy's Opus requests wrote the cache again on every turn (`cache_creation` > 0, `cache_read` 0). This is cost-relevant.
- `conversations/<conversationId>.db` (sqlite: `steps`, `gen_metadata`, `trajectory_meta`, …) holds protobuf blobs. `gen_metadata` field 4 = {2: input, 3: output, 11: responseId}, decoded with `protoc --decode_raw`. `conversation_summaries.db` holds title, step_count and status. `log/cli-<ts>.log` is a glog text log.
- Fixtures: `tests/fixtures/agy/run_*/brain/**`, `conversations/*.db`, `log/`, `marker.jsonl`.

## 7. Meter routing (VERIFIED)
- agy has no usable base-URL override in ADC mode (section 2). **Route: `HTTPS_PROXY` + `SSL_CERT_FILE`.**
  - Go on macOS **honours `SSL_CERT_FILE`** in this build. VERIFIED: without it, MITM handshakes fail with `SSLV3_ALERT_BAD_CERTIFICATE`; with it, every `*.googleapis.com` call succeeds through the Meter. The file *replaces* the root pool, so any host the Meter tunnels instead of terminating would fail TLS. Hence MITM `*.googleapis.com`, deny everything else.
  - Proxy userinfo arrives as `Proxy-Authorization`, which gives `attempt_token` attribution (VERIFIED).
- Upstream calls per session (VERIFIED):
  - `POST https://oauth2.googleapis.com/token` (ADC refresh) and `GET https://www.googleapis.com/oauth2/v2/userinfo`.
  - Start-up availability probes: `POST …/publishers/anthropic/models/claude-opus-5-5@default:rawPredict` returns **400** (body `{}`), and `…/claude-sonnet-5-5@default:rawPredict` returns **404**, which means not enabled. Both are cheap but are model calls.
  - Session title: `POST …/publishers/google/models/gemini-3.1-flash-lite:streamGenerateContent?alt=sse` (`thinkingBudget:-1`). **This is an extra model, not the selected one.** Price it separately.
  - Main loop: `POST https://aiplatform.googleapis.com/v1/projects/your-gcp-project/locations/global/publishers/google/models/<id>:streamGenerateContent?alt=sse` and `…/publishers/anthropic/models/claude-opus-5-5@default:streamRawPredict?alt=sse`.
  - Telemetry: `POST https://play.googleapis.com/log` (Clearcut) returns 401 under ADC. The driver denies it (403). Blocking it is harmless.
- Request bodies are sent with `Transfer-Encoding: chunked`, so the Meter must de-chunk them. Fixture: `tests/fixtures/agy/*/meter/`.

## 8. Thinking control: label → wire (VERIFIED from request bodies)
`agy models` (works with `AGY_ADC_AUTH=1`) lists `gemini-4-argon-{high,medium,low}`, `gemini-3.8-flash-{high,medium,low}`, `gemini-3.7/3.6/3.5-flash-*`, `gemini-3.1-pro-low-thinking`, `gemini-3.1-flash-lite-preview`, `gemini-3-flash-preview`, and `claude-opus-5-5-{max,high,medium,low}` with display labels such as `Gemini 4 Argon (High)` or `Claude Opus 5.5 (Max)`. Sonnet 5.5 is hidden because it is not enabled. `--model` takes the display label.
| label | request |
|---|---|
| Gemini 3.8 Flash (Low) | `thinkingConfig:{includeThoughts:true, thinkingBudget:1000}` |
| Gemini 3.8 Flash (Medium) | `thinkingBudget:4000` |
| Gemini 3.8 Flash (High) | `thinkingBudget:-1` (dynamic) |
| Gemini 4 Argon (Low/Medium/High) | `thinkingLevel:"LOW"/"MEDIUM"/"HIGH"` (no budget) |
| Claude Opus 5.5 (Low) | `thinking:{type:"adaptive",display:"summarized",block_binding:{…}}, output_config:{effort:"low"}`, `max_tokens:64000` |
| Claude Opus 5.5 (Max) | same, with `effort:"max"` |
- Not run: Opus (Medium)/(High), which should map to `effort:"medium"/"high"` (UNVERIFIED). There is no `xhigh` label. `--effort xhigh` exists as a flag (`low|medium|high|xhigh|max`) but was not tested.
- **agy expresses Flash thinking as a token budget, not `thinkingLevel`.** Report Flash cells as "budget 1000/4000/dynamic", not LOW/MEDIUM/HIGH. Verify from the Meter request body plus `thoughtsTokenCount` / `thinking_tokens`.

## 9. In-session switching and multi-model (VERIFIED)
- Typed `/model <label>` (for example `/model Gemini 4 Argon (Low)`) switches the model for later turns and persists it to `settings.json` `model`. VERIFIED: the next request went to `gemini-4-argon` with `thinkingLevel:"LOW"`. `/model <label> <prompt>` runs one prompt on another model (UNVERIFIED). `/effort <level>` and `--effort` change effort (UNVERIFIED).
- Native multi-model: subagents and custom agents (`--agent`, `/agents`, `invoke_subagent`), plus the fixed title model `gemini-3.1-flash-lite`. There are no role-based model slots like omp's.

## 10. Caveats and open risks
- The background self-updater is not disabled by `AGY_CLI_DISABLE_AUTO_UPDATE=1`. Rely on Meter egress denial (in the container it must be enforced).
- The onboarding and ToS skip uses an undocumented cache file (`cache/onboarding.json`) that may change between versions. The driver should detect `DIALOG_RX` and fail loudly.
- `trustedWorkspaces` must hold the cwd exactly as agy sees it. Write both the path and its realpath.
- Long first-token latency: one `gemini-3.8-flash` main request took 10–20 s TTFB, both direct and through the Meter (replay test). Don't use tight timeouts.
- Not tested: subagents, `/effort`, Opus Medium/High labels, sandbox mode, Linux container (`SSL_CERT_FILE` behaviour on Linux is standard Go, so it should work).
