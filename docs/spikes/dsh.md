# Phase-0 spike: DeepSeek Harness (dsh), vanilla, Web UI, PTC mode

Date: 2026-10-30/31 · dsh **0.2.1-rc.5** (npm `latest`) · pi-ai 1.4.0 · @google/genai 2.21.0 · Node 24.20.0 · macOS · Playwright Chromium headless shell 156
Driver: [`docs/spikes/dsh_drive.py`](dsh_drive.py) · Fixtures: [`tests/fixtures/dsh/`](../../tests/fixtures/dsh/)

Legend: **VERIFIED** = observed in an unattended run in this spike. **VERIFIED (source)** = read in the shipped code or docs, not exercised at runtime. **UNVERIFIED** = not tested.

## TL;DR

- Vanilla dsh drives GEAP **Gemini** models through pi-ai's built-in `google-vertex` provider with **user ADC**, `your-gcp-project`, `global`. It works unattended from the Web UI under Playwright. **VERIFIED** with gemini-3.8-flash (low/high) and gemini-4-argon (low/medium).
- **Claude on Vertex is not possible in vanilla dsh.** pi-ai 1.4.0 has no Vertex-Anthropic route. **VERIFIED (source)**
- **Argon is safe.** For every Gemini 3+/4 model, dsh/pi-ai sends `thinkingConfig.thinkingLevel` and never `thinkingBudget`. That includes the "off" path, which becomes `LOW`. **VERIFIED** for LOW/MEDIUM on the wire; all other paths **VERIFIED (source)**.
- **Meter routing:** a provider `baseURL` override pointing at a local forwarder works. dsh then calls `POST {baseURL}/publishers/google/models/<model>:streamGenerateContent?alt=sse` with the ADC `Authorization: Bearer` header and `x-goog-user-project: your-gcp-project`. **VERIFIED**
- **Completion:** use the `turn/end` record in `$DSH_HOME/sessions/**/session.v4.jsonl.zstd`, together with "no open turn in any child session, no open job" and Meter quiescence. **VERIFIED**
- **Hazard found:** the Web app's first-use "Default workspace" is `<macOS Documents>/deepseek-harness/default-workspace`. dsh resolves it with **osascript, which ignores `$HOME`**. My first run created files in the user's real `~/Documents` (removed again). The fix is `workspace-controller.documentsDirectory`. **VERIFIED**
- **Fallback driver:** ACP (`dsh --profile acp`) ran a full session over stdio: initialize → session/new → session/prompt → request_permission (answered Reject) → end_turn → close → exit 0. **VERIFIED**

## 1. Install and version (§10)

```sh
mkdir -p tools/dsh
# npm 11 REJECTS `--allow-scripts` for project-scoped installs (EALLOWSCRIPTS). Put the allowlist in package.json:
cat > tools/dsh/package.json <<'EOF'
{ "private": true,
  "allowScripts": { "@deepseek-ai/dsh-subprocess-local": true, "koffi": true, "node-pty": true,
                    "@google/genai": true, "protobufjs": true } }
EOF
npm install --prefix tools/dsh @deepseek-ai/dsh@latest        # VERIFIED (616 packages, ~36 s)
tools/dsh/node_modules/.bin/dsh --version                       # -> 0.2.1-rc.5   VERIFIED
npm view @deepseek-ai/dsh dist-tags --json                      # latest=next=0.2.1-rc.5, alpha=0.2.2-alpha.2
```

- "Latest" means the `latest` dist-tag. `alpha` (0.2.2-alpha.2) is numerically newer but not used.
- The version is also in every model request's User-Agent: `google-genai-sdk/2.21.0 gl-node/v24.20.0, deepseek-harness/0.2.1-rc.5 (+https://github.com/deepseek-ai/deepseek-harness)`. The Meter can therefore confirm the version in use. **VERIFIED**
- The user's global `/opt/homebrew/bin/dsh`, its `:3080` LaunchAgent and `~/.dsh` were never used or touched.

## 2. Isolation (env, homes)

| Var | Value | Why |
|---|---|---|
| `DSH_HOME` | `<att>/dsh_home` | All dsh state: profiles, sessions, storages, `.credentials.yaml`. Precedence: configured path > `$DSH_HOME` > `~/.dsh` (`dsh-home-paths`). **VERIFIED** |
| `DSH_AGENTS_HOME` | `<att>/agents_home` | Shared `AGENTS.md`/skills root, which defaults to `~/.agents`. **VERIFIED (source)** |
| `HOME` | `<att>/home` | Contains only `.config/gcloud/application_default_credentials.json` (0600 copy). pi-ai checks `~/.config/gcloud/application_default_credentials.json` exists before using ADC. **VERIFIED** |
| `TMPDIR` | `<att>/tmp` | |
| `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_QUOTA_PROJECT` | `your-gcp-project` | pi-ai Vertex ADC needs project + location env. **VERIFIED** |
| `GOOGLE_CLOUD_LOCATION` | `global` | |
| `DSH_TELEMETRY_DISABLED` | `1` | Telemetry opt-out (session-telemetry-otel defaults to `FEEDBACK_ONLY`). |
| `PATH`, `LANG` | minimal | |

Start the process with `env -i` plus exactly this allowlist. No `CLAUDE_*`, `ANTHROPIC_*` or `*_API_KEY` variables are passed. The agent's bash tool inherits this environment.

Egress check: I ran one attempt with `HTTPS_PROXY` set to a CONNECT-logging proxy (§6). The dsh process opened tunnels only to `oauth2.googleapis.com:443` (ADC token refresh) and `aiplatform.googleapis.com:443`. There was no DeepSeek, OTel or plugin-market traffic. **VERIFIED** for that run. Browser-side requests were not audited (**UNVERIFIED**).

## 3. Profile setup and exact config (§1)

- Profiles live at `$DSH_HOME/profiles/<name>/`. The shipped `web` profile auto-initializes on first use: `dsh --profile web --dump-config` creates it without booting. **VERIFIED**
- Its `package.json` bundles are `@deepseek-ai/dsh-base` and `@deepseek-ai/dsh-web-app`.
- The user layer is `cordis.patch.yml`: a top-level YAML list of id-targeted entries.
- **A patch `config` replaces the whole entry config** (no deep merge). A patch for an unknown id only prints a warning.
- Layer order: bundles → profile `cordis.patch.yml` → `$DSH_HOME/cordis.patch.yml` → `--patch` overlays.
- Inspect with `dsh --profile web --dump-config` (composed YAML, annotated per layer) and `--dump-config-schema` (JSON Schema, with `$defs.patchList`). The schema dump exits 1 with "unrecognized Loader tree carrier" errors for the preset groups, but the JSON is still emitted. **VERIFIED**
- Web has HMR enabled, so do not edit the patch mid-attempt.

`$DSH_HOME/profiles/web/cordis.patch.yml`, exactly as generated by the driver. **VERIFIED** (fixture: `web-ptc-flash-low/cordis.patch.yml`):

```yaml
- id: llm-pi-ai                      # @deepseek-ai/dsh-llm-pi-ai (pi-ai provider routes)
  config:
    providers:
      google-vertex:                 # pi-ai catalog route; ADC auth because apiKeyEnv is omitted
        displayName: GEAP (your-gcp-project, global)
        baseURL: http://127.0.0.1:<meterPort>/t/<attemptToken>/v1/projects/your-gcp-project/locations/global   # Meter (§6); omit for direct
        reasoning: low               # route default effort
        models:                      # replaces the catalog list: only these two appear in the picker
          - id: gemini-3.8-flash
          - id: gemini-4-argon
- id: agent-default-model            # default for new sessions (what the picker shows)
  config:
    provider: google-vertex
    model: gemini-3.8-flash
    reasoningEffort: low             # low | medium | high
- id: tools                          # @deepseek-ai/dsh-tools
  config:
    mode: ptc                        # native | ptc   (shipped default: !!js process.env.DSH_TOOLS_MODE -> native)
- id: sandbox-policy
  config:
    mode: workspace-write
    workspaceRoot: <att>/documents/deepseek-harness/default-workspace
- id: approval                       # @deepseek-ai/dsh-user-approval
  config:
    policy: never                    # never = reject every approval request deterministically (no UI prompt)
- id: permission                     # @deepseek-ai/dsh-permission-presets: the session default is applied from a PRESET
  config:
    presets:
      unattended: {sandbox: workspace-write, approval: never, name: unattended, description: ...}
      workspace-write: {sandbox: workspace-write, approval: ask}
      danger-full-access: {sandbox: danger-full-access, approval: never}
    defaultPreset: unattended        # REQUIRED: without a preset matching (workspace-write, never) the session gets ask
- id: workspace-controller           # @deepseek-ai/dsh-api-workspace-controller
  config:
    documentsDirectory: <att>/documents   # pins the Web "Default workspace" (see hazard below)
```

### Permissions (VERIFIED)

- Each new session records `permission/preset {preset: unattended}`, `sandbox/mode {mode: workspace-write}` and `approval/policy {policy: never}`. The composer shows **"Unattended"**.
- The model is told in its runtime context: "Approval prompts are disabled in this session: actions that require approval are rejected automatically".
- The macOS sandbox is enforced: `echo > /Users/Shared/...` failed with `Operation not permitted` and `"sandbox": {"mode": "workspace-write", "denied": true, "enforcement": "full"}`.
- Writes under `/private/tmp`, and therefore under the attempt dir, are allowed ("platform temporary areas").
- `danger-full-access` with `never` is the no-sandbox alternative. The shipped `DSH_PERMISSION_MODE` env var only switches the base sandbox/approval defaults, so the preset table above is still needed for (workspace-write, never).

### Workspace root (VERIFIED, hazard)

- `sandbox-policy.workspaceRoot` is only a fallback. A session's writable root is its **cwd**, and in the Web app the cwd comes from the **Workspace registry**.
- On a fresh `DSH_HOME`, the Web client initializes a "Default workspace" at `<Documents>/deepseek-harness/default-workspace`.
- On macOS, `<Documents>` comes from `osascript 'path to documents folder'`, which **ignores `$HOME`**. My first run therefore wrote `calc.py`/`test_calc.py` into the real `~/Documents/deepseek-harness/default-workspace`. I deleted that directory, which I had created. The parent `~/Documents/deepseek-harness` already existed before the run and was left in place, empty.
- On Linux, `<Documents>` is resolved with `xdg-user-dir DOCUMENTS` and fails if that is unavailable.
- **Recipe:**
  1. Set `workspace-controller.documentsDirectory: <att>/documents`.
  2. Copy the task repo to `<att>/documents/deepseek-harness/default-workspace` before boot. dsh reuses an existing directory.
  3. Check that the session header `cwd` equals that path.
- Initialization happens only on an empty registry with no session history, so every attempt needs a fresh `DSH_HOME`.

### Agent preset vs `tools.mode`

- The composer's mode menu offers the presets **Standard / PTC / Minimal / Creator**.
- The plan's `dsh-tools mode: ptc` uses the **Standard** preset plus the global `tools.mode: ptc`. The session header records `agentPreset: "standard"`, and the model sees only `run_code`. **VERIFIED**
- The shipped "PTC mode" preset (`preset-ptc`) is slightly different. It uses `dsh-agent-tool-presentation mode: ptc` and **disables `workflow-ptc`/`tool-workflow`**.
- **Open decision:** which of the two counts as "dsh PTC" for the benchmark. Both are vanilla. This spike used `tools.mode: ptc`.
- Control variant `--tools-mode native`: about 31 function declarations are sent: `ask_user_question, bash, create_goal, edit, exit_plan_mode, get_goal, glob, grep, interrupt_agent, job_*, list_agents, present, read, read_image, schedule_*, send_message, skill, subagent, subagent_fork, todo_write, update_goal, web_fetch, web_search, workflow, working_directory, write`. **VERIFIED** (fixture `web-native-control`)
- `web_search` is DeepSeek-backed and would fail without a DeepSeek key.

## 4. Boot and authentication (§2)

```sh
cd <workspace> && env -i <allowlist> tools/dsh/node_modules/.bin/dsh web --port <free port ≠ 3080> --no-open
```

- **`--no-open` is mandatory.** Without it, dsh opens the user's default browser.
- `--host` defaults to `127.0.0.1`. `--port 0` lets the OS pick a port; that is untested (**UNVERIFIED**), so the driver pre-picks a free port.
- Stdout prints exactly one line: `dsh web: http://127.0.0.1:<port>/?token=<43-char base64url>`. It appears about 2–3 s after start. Stderr then prints an `ExperimentalWarning: stripTypeScriptTypes`. **VERIFIED**
- Auth flow: `page.goto(<token URL>)` sets an **HttpOnly cookie `dsh-auth-<id>`** (path `/`) and redirects to `/`. The browser session grant is stored in `$DSH_HOME/.credentials.yaml` (`client-connection/browser-session`). **VERIFIED**
- The driver starts the Playwright trace only after this navigation, so the token URL is not in the trace.

**Shutdown.** Send SIGTERM to the process group (spawn with `start_new_session=True`). dsh exited with rc=0 in about 1 s in every run, and a group SIGKILL afterwards reaps stragglers. A `session.lock` file stays next to each session log (harmless). **VERIFIED**

## 5. DOM recipe (§3), all via ARIA roles/names (EN locale)

| Purpose | Locator (Playwright) | Notes |
|---|---|---|
| First-run notice | `get_by_role("dialog", name="Preview Notice")` → `get_by_role("button", name="Continue")` | Appears on every fresh browser context. |
| Composer | `get_by_role("textbox", name=/^(Describe what you want to build\|Message or run a task)/)` | A `contenteditable` DIV. `fill()` works. The placeholder changes after the first turn. |
| Send | `get_by_role("button", name="Send message")` | `[disabled]` while empty or running. **t0 = click.** |
| Running | `get_by_role("button", name="Stop generating")` present; `role=status` text such as "Deep diving" | Appeared within ~1 s of send. |
| Turn complete (DOM) | "Stop generating" gone, "Send message" back; `role=status` = **"Completed"**; a button "Completed in Ns"; per-turn buttons "Usage 25.1K tok", "1 turns 2 steps · 424 tok/s" | This is a cross-check only. The durable record (§6) is authoritative. |
| Model picker | `get_by_role("button", name=/^Select model, current /)`, e.g. aria-label `Select model, current Gemini 4 Argon, reasoning effort Medium` | Opens `menu "Model and reasoning effort"` with `menuitem "Model <name>"` and `menuitem "Effort <level>"`. Clicking Model shows the route group "GEAP (your-gcp-project, global)" with Gemini 3.8 Flash / Gemini 4 Argon. Clicking Effort shows `menuitemradio` Low/Medium/High (no Off, no Minimal). The driver asserts the label instead of clicking. |
| Access mode | `get_by_role("button", name=/^Access mode, current: /)` → `menuitem` "Unattended" / "Workspace Write" / "Full access" | |
| Workspace | `get_by_role("button", name="Choose workspace")` (text "Default workspace") | |
| Agent preset | `get_by_role("button", name="Standard mode")` | |
| Approval prompt | `group "Approval details"` + text "Waiting for approval"; buttons **"Reject"** / **"Allow once"** | Only appears with `approval: ask`. Captured by switching Access mode to "Workspace Write" and forcing an escalation (fixture `web-approval-dialog`). |
| ask_user_question card | buttons "Dismiss all questions", textbox "Type your answer"; countdown "Continuing in {n}s" | Labels from the client locale (**VERIFIED (source)**). The card never appeared in the runs. The driver dismisses it if seen. |
| Session list | `tree "Sessions"` → `treeitem "<LLM title> 1min"` | |

Fixtures: `web-ptc-flash-low/{shots/*.png, trace.zip (DOM snapshots, 200 KB), video.webm, final.aria.txt}`, `ui-explore/*.png`, `web-approval-dialog/{dialog-approval-*.aria.txt, shots/}`.

## 6. Completion signal and Meter routing (§4, §6)

### Session store layout (VERIFIED)

```
$DSH_HOME/sessions/--<cwd with / replaced by ->--/<session-id>/session.v4.jsonl.zstd   (+ session.lock)
  root session id:      session-<uuid>
  subagent child:       <uuid>/   (sibling dir in the same project dir)
```

- The file is **multi-frame zstd** (16 frames for a 54-row session). `zstd -dcq` decodes all of it. Node's `zstdDecompressSync` returned **only the first frame** (1 line = the header). **VERIFIED**
- Row 0 is the header frame: `{"type":"session","version":4,"id","createdAt"(ms),"cwd","isSeeded","delegationDepth":0,"agentPreset":"standard"}`. A child header adds `parentSession`, `origin:"subagent"` and `delegationDepth:1`.
- An option exists to write plain JSONL instead: `session-persistence-jsonl.compression: none` (**VERIFIED (source)**, not used).

### Durable completion rule (driver `work_state()`)

The attempt is done when all of these hold for `--settle` seconds (3 s), and the Meter has nothing in flight:

- the root session has at least one `{"type":"turn/end","data":{"turn":N,"reason":{"kind":"completed"|"aborted"|"error"|"max-tokens"|"blocked"|"interrupted"}}}`;
- no session file (root or child) has a `turn/start` without a later `turn/end`;
- every `job/registered` has a matching `job/settled`.

Why the extra conditions:

- dsh tells the model to end its turn rather than poll subagents. Child results can then wake the root in a new turn (`agent/inbox/spliced target:"next-turn"`).
- My first implementation took the first file in sort order, which was a child. It declared the attempt done 4 s early in the subagent run. That is fixed now. **VERIFIED**
- `turn/end` is not flushed synchronously, but in every run it was on disk before the DOM showed Completed.

### Session-title call

- Every Web session makes one extra LLM call: the session title, `session/title-llm-request`, at `reasoningEffort: low` and `maxOutputTokens: 4096`, with no tools.
- It runs concurrently with the first step and can finish **after** `turn/end`: once 31 s on Flash, 14 s after the turn ended.
- Its usage is **not** recorded in the session. Only the Meter sees it.
- How to recognize it: a request with no `tools`, `maxOutputTokens: 4096`, and a system instruction starting with `Create a concise title`.
- Count it under role `title`, and take `t_end` from the last non-title response. ACP sessions made no title call.

### Meter via provider baseURL (VERIFIED)

- pi-ai's catalog `baseUrl` is `https://{location}-aiplatform.googleapis.com`.
- When `baseURL` is set without `{location}`, the genai SDK is configured with `baseUrlResourceScope: COLLECTION`. It then omits the `projects/<p>/locations/<l>` prefix, and also omits `/v1` if the URL already contains `/vN`.
- So the override must include the resource path: `baseURL: http://127.0.0.1:<port>/t/<token>/v1/projects/your-gcp-project/locations/global`.
- The resulting upstream calls are all **`POST /v1/projects/your-gcp-project/locations/global/publishers/google/models/{gemini-3.8-flash|gemini-4-argon}:streamGenerateContent?alt=sse`**. The forwarder maps `/t/<tok>/…` to `https://aiplatform.googleapis.com/…`, preserving the query and headers.
- Request headers seen (Authorization REDACTED in logs): `authorization: Bearer <ADC user token>`, `x-goog-user-project: your-gcp-project`, `x-goog-api-client: google-genai-sdk/2.21.0 gl-node/v24.20.0`, `Content-Type: application/json`, `accept-encoding: gzip, deflate`.
- In this spike, all 50 metered calls (web and ACP) returned 200.
- Responses are SSE `data:` events. The last one carries `usageMetadata{promptTokenCount, candidatesTokenCount, thoughtsTokenCount?, cachedContentTokenCount?, totalTokenCount, trafficType:"ON_DEMAND", *TokensDetails}`, plus `modelVersion` and `finishReason`.
- The ADC token refresh (`oauth2.googleapis.com`) bypasses the Meter. That is expected.

### Alternative: HTTPS_PROXY (VERIFIED, host-level only)

- `HTTPS_PROXY=http://127.0.0.1:<p> NODE_USE_ENV_PROXY=1 NO_PROXY=127.0.0.1,localhost` with no baseURL also worked: CONNECT tunnels to `aiplatform.googleapis.com:443` (fixture `web-https-proxy/connect-proxy.jsonl`).
- Without TLS interception this gives hosts only, no usage data. Use the baseURL Meter.

## 7. Session record format → metrics (§5)

Types seen in a PTC web turn (fixture `web-ptc-flash-low/session-0.decoded.jsonl`):

`session`, `permission/preset`, `sandbox/mode`, `approval/policy`, `agent/inbox/spliced`, `turn/start`, `step/start`, `system/message`, `user/message` (task + runtime-context + time-context snapshots), `request/header` (`{config:{provider,model,reasoningEffort}, tools:[{name:"run_code",…}]}`), `request/context` (`contextWindow`), `session/title`, `session/title-llm-request`, `assistant/message`, `tool/call`, `tool/ptc-dispatch-start`, `tool/ptc-dispatch`, `job/registered`, `job/settled`, `tool/result`, `step/end`, `workspace/changes`, `turn/end`. Others seen: `todo/write`, `approval/asked`, `approval/decided`, `subagent/catalog`, `subagent/descriptor`, `subagent/model-selection-policy`.

Every row has `type`, `seq` and `time` (epoch **ms**), plus `data`.

| Metric | Source | Notes |
|---|---|---|
| LLM steps | `step/start`/`step/end` `{turn, step}` | One `assistant/message` per step. |
| Usage per step | `assistant/message.data.usage = {inputTokens, outputTokens, totalTokens, cacheReadTokens?, cacheWriteTokens?}` | `inputTokens` = **uncached** (prompt − cached). `cacheReadTokens` = `cachedContentTokenCount`. `outputTokens` = **candidates + thoughts** (thinking folded in). `reasoningTokens` is in dsh's `TokenUsage` type but the pi-ai adapter **does not populate it**, so `tok_thinking` must come from the Meter's `thoughtsTokenCount`. `toolUsePromptTokenCount` is not recorded. `cacheWriteTokens` never appears for Gemini. **VERIFIED** (Flash HIGH: 575 = 271 + 304 thoughts) |
| Timed stream | `assistant/message.data.stream[]`: `chunk` events (`block-start`, `usage`, `finish{reason:{kind:"tool-calls"\|"stop"…}}`) and `text-chunks`/`reasoning-chunks` with `time0` + `dt[]` | Gives TTFT and stream timing per step. `message.content[]` blocks: `reasoning`, `tool-call{id,name,arguments}`, `text`. `source.replayState.response.stopReason` = `toolUse`/`stop`. |
| Outer tool call | `tool/call {turn, step, callId:"call_<n>", name:"run_code", arguments:"{code,description}"}` → `tool/result {message:{toolCallId, isError, content}, error?:{name, code, reason?}, meta?}` | Timing = the two `time` values. |
| Nested PTC sub-call | `tool/ptc-dispatch-start {rootCallId, parentCallId, subCallId:"<parent>:ptc:<n>", name, arguments}` → `tool/ptc-dispatch {…, isError, content, meta?, error?:{name, code}}` | Example: `{"name":"FsError","code":"FS_NOT_FOUND"}` for `read` of a missing file. A sub-call failure that the program catches does not fail `run_code`. **VERIFIED** |
| run_code failure | `tool/result.message.isError=true`, `error={"name":"CodeRunFailedError","code":"CODE_RUN_FAILED"}`; the **kind is only in the text**: `Error: code run failed (<kind>): …` | Parse it with `/code run failed \(([a-z-]+)\)/`. Kinds: exception, timeout, abort, worker-exit, invalid-output, output-limit, protocol, sandbox-unavailable (**VERIFIED (source)**). `exception` was **VERIFIED** for both an uncaught `ToolCallError` and `throw new Error("boom")`. |
| Rejected escalation | `approval/asked {id, toolName:"run_code", callId, reason}` → `approval/decided {id, outcome:"rejected"}`; `tool/result` isError with no structured error; text "the user rejected escalating…" | With `approval: never` there is no prompt and the request is rejected deterministically. |
| Sandbox denial | in the bash result JSON: `"sandbox":{"mode":"workspace-write","denied":true,"enforcement":"full"}` | |
| Bash/job timing | `job/registered`/`job/settled {jobId, kind:"bash", toolCall:{callId, rootCallId}, status, detail:"exit code: 0"}` | |
| Native mode | Same `tool/call`/`tool/result` with real tool names; no ptc events | Fixture `web-native-control`. |
| Turn result | `turn/end.reason.kind` | |

The `<parent>:ptc:<n>` ids are opaque; correlate them by exact string match. Note from the dsh docs: nested dispatches inside **workflow** runs are not durably recorded, so count them as partial.

## 8. Thinking control per model (§7)

| Model | dsh/UI efforts | Wire (`generationConfig.thinkingConfig`) | Result |
|---|---|---|---|
| gemini-3.8-flash | low / medium / high (catalog `thinkingLevelMap`: off & minimal null) | `{"includeThoughts":true,"thinkingLevel":"LOW"\|"HIGH"}` | **VERIFIED** LOW (0 thoughts) and HIGH (1235 thoughts over 5 calls) |
| gemini-4-argon | low / medium / high | `{"includeThoughts":true,"thinkingLevel":"LOW"\|"MEDIUM"}` | **VERIFIED** LOW and MEDIUM → 200; HIGH **VERIFIED (source)** (same code path) |

- `pi-ai/api/google-shared.usesGoogleThinkingLevel()` matches `gemini-3.x-flash|pro` and `gemini-[4-9]…`, so these models never receive `thinkingBudget`.
- Disabled or "off" thinking goes through `getDisabledGoogleThinkingConfig()`, which returns `{thinkingLevel:"LOW"}` for both models (evaluated against the installed package).
- The route's `thinkingBudgets` config only applies to budget-style models.
- **Argon does not hit the "thinkingBudget not supported" rejection in vanilla dsh.** No patch is needed.
- The title call always uses `thinkingLevel: LOW`, whatever the session effort is.
- Verify the effort from the Meter's request `thinkingConfig` and response `thoughtsTokenCount`. The session only records the requested `request/header.config.reasoningEffort`.
- Effort can be set in config (`agent-default-model.reasoningEffort`, route `reasoning`) or in the UI (Effort submenu). In ACP it is a `session/set_config_option` `reasoning_effort` option.

### Claude (claude-opus-5-5)

**Not supported by vanilla dsh. VERIFIED (source)**

- pi-ai 1.4.0's `google-vertex` catalog contains only Gemini models.
- The `anthropic` route speaks Anthropic's own API (`/v1/messages`, `x-api-key`). Nothing in pi-ai or dsh maps it to Vertex `:rawPredict` with an ADC bearer token.
- A custom `anthropic-messages` route at a Vertex URL would need a translating proxy. That is a custom adapter, which is out of scope.
- So dsh's model column = **Gemini only**.

## 9. Multi-model: subagents and workflows (§8)

- **Subagent model chosen by the main model. VERIFIED** (fixture `web-subagent-multimodel`). Add this patch:

  ```yaml
  - id: subagent-model-selection-settings
    config:
      enabled: true
      allowedModels:
        - {provider: google-vertex, model: gemini-3.8-flash}
        - {provider: google-vertex, model: gemini-4-argon}
  ```

  - The Standard preset's `tool-subagent` already has `modelSelectionSettings: true`.
  - With this patch, the model sees `provider`/`model`/`reasoning_effort` on `subagent` and a `list_subagent_models` tool.
  - In the run, Argon was the main model and called `tools.list_subagent_models()` then `tools.subagent({provider, model:"gemini-3.8-flash", reasoning_effort:"low"})` inside `run_code`.
  - The child session header recorded `subagent/descriptor {agentProvider, agentModel:"gemini-3.8-flash", agentReasoningEffort:"low"}`.
  - The Meter showed the child's calls hitting `models/gemini-3.8-flash`.
  - The child reports back with `send_message`, which shows up in the root as `agent/inbox/spliced`.
- **Fixed subagent model:** use `tool-subagent.config.agentOptions: {provider, model, reasoningEffort, maxTokens}`. **VERIFIED (source)**, not run.
  - `tool-subagent` sits inside the `preset-standard` entry's `plugins` list, and patches replace a whole config.
  - Setting it therefore means re-stating the full `preset-standard` config, copied from `--dump-config`.
- **Workflows:** a script's `agent()` call may pass an optional `model`; otherwise children use the spawn provider's route. There is no deployment-level workflow-model key. **VERIFIED (source)** only.
- Workflow nested PTC dispatches are not durably recorded.

## 10. ACP fallback (§9), VERIFIED

- Profile: `dsh --profile acp` auto-initializes at `$DSH_HOME/profiles/acp` (bundles: dsh-base + dsh-acp-app).
- The patch is the same as for web, minus `permission`/`workspace-controller`, plus a provider/model override on the ACP plugin (the shipped default is `deepseek-official`/`deepseek-v4-flash`):

  ```yaml
  - id: acp
    config: {provider: google-vertex, model: gemini-3.8-flash}
  ```

  With no approval override, the policy stays `ask`, which is what makes permission requests reach the client.
- **Transport:** newline-delimited JSON-RPC 2.0 on stdin/stdout. Stdout carries protocol traffic only. Start it with cwd = workspace and the same env allowlist.
- **Sequence I ran** (fixture `acp/acp-transcript.jsonl`, client `acp/acp_client.py`):
  1. `initialize {protocolVersion:1, clientCapabilities:{fs:{readTextFile:false, writeTextFile:false}, terminal:false}}` returned `agentInfo {name:"deepseek-harness-acp"}`, with sessionCapabilities close/list/resume and no auth.
  2. `session/new {cwd, mcpServers:[]}` returned `sessionId` and `configOptions`: `model` (values like `["google-vertex","gemini-3.8-flash"]`, both models listed) and `reasoning_effort` (low/medium/high).
  3. `session/prompt {sessionId, prompt:[{type:"text", text}]}` streamed `session/update` notifications: `tool_call` (title `run_code`, `rawInput {code, description}`), `tool_call_update` (`completed`/`failed`), `agent_message_chunk` and `usage_update {used, size}`.
  4. **`session/request_permission`** arrived for the escalated **PTC sub-call** (`toolCall.toolCallId:"call_…:ptc:1"`) with options `allow-once` (allow_once) and `reject-once` (reject_once). The client answered `{outcome:{outcome:"selected", optionId:"reject-once"}}`.
  5. The prompt resolved with `{stopReason:"end_turn"}` after 50.6 s and 6 Meter calls, with no title call.
  6. `session/close` returned `{}`. Closing stdin made the process exit with rc 0 immediately.
- Sessions persist under `$DSH_HOME/sessions` in the same format.

## 11. Fixture index (`tests/fixtures/dsh/`)

| Dir | Run | Contents |
|---|---|---|
| `web-ptc-flash-low/` | Flash LOW, bug-fix task, 3 `run_code` | raw `session.v4.jsonl.zstd` (16 frames) + `session-0.decoded.jsonl`, `meter.jsonl` (Authorization REDACTED), `request-0002.body.json` (main step), `request-0001-title.body.json`, `cordis.patch.yml`, `events.jsonl`, `result.json`, `final.aria.txt`, `shots/`, `trace.zip` (DOM snapshots), `video.webm`, `dsh.log` (token REDACTED) |
| `web-ptc-flash-high/` | Flash HIGH | thoughts tokens in the Meter; `todo/write` records; HIGH request body |
| `web-ptc-argon-low/`, `web-ptc-argon-medium/` | Argon LOW/MEDIUM | `thinkingLevel` on the wire, 200s; FS_NOT_FOUND sub-call error |
| `web-ptc-errors/` | forced failures | ptc sub-call `FsError/FS_NOT_FOUND`; `run_code` `CODE_RUN_FAILED (exception)` ×2 |
| `web-approval-dialog/` | Access mode "Workspace Write", escalation | approval DOM (aria + png), `approval/asked`/`approval/decided`, sandbox denial |
| `web-native-control/` | `tools.mode: native` | full native tool list in the request |
| `web-subagent-multimodel/` | Argon root → Flash child | root + child decoded sessions, `extra-patch.yml`, Meter showing both models |
| `web-https-proxy/` | HTTPS_PROXY, no baseURL | CONNECT targets (egress audit) |
| `acp/` | ACP stdio | patch, transcript, Meter log, decoded session, `acp_client.py` |
| `ui-explore/` | | landing, model/effort menus, completed-turn aria |

## 12. Caveats and open risks

1. **Default-workspace leak (fixed by config).** Any dsh/web launch without `workspace-controller.documentsDirectory` writes to the real `~/Documents` on macOS. Assert that the session header `cwd` is inside the attempt dir before trusting a run.
2. **Linux container:** **UNVERIFIED.**
   - The sandbox (`dsh-sandbox-local`/`bash-sandbox`) has a different confinement backend there.
   - `xdg-user-dir` must not be relied on (the override above covers it).
   - Headed Chromium needs a virtual display; I used headless only.
3. **PTC definition:** decide between `tools.mode: ptc` with the Standard preset (used here; workflow tool stays available) and the shipped "PTC mode" preset (workflow disabled).
4. **Claude:** no vanilla path. In the Run Builder, dsh × Claude = N/A ("pi-ai has no Vertex-Anthropic route").
5. **Thinking tokens** are not in Plane A (folded into `outputTokens`). Plane B is required for `tok_thinking`.
6. **Title call** adds one hidden LLM call per Web session. It can outlive the turn, so the Meter t_end/quiescence logic must classify it.
7. **"Latest" volatility:** UI labels, ARIA names and record types are tied to 0.2.1-rc.5. The session-format catalog migrates v0→v4 on read, but the driver reads files directly.
   - Pin the parser to `version: 4` and fail loud on others.
   - Keep the ACP driver ready.
8. **Preview Notice** appears on every fresh browser context and must be dismissed. Other first-run dialogs may appear in future releases; the driver logs unknown dialogs only through screenshots.
9. **Patch semantics:** a patch replaces the whole config. Re-check `--dump-config` after each upgrade, since bundle defaults (e.g. `permission.presets`) can change.
10. **HMR** is on in the web profile. The runner must not rewrite `cordis.patch.yml` while dsh is running.
11. The trace contains the auth cookie name and requests to the (dead after shutdown) local server. The one-time token is excluded because tracing starts after sign-in. Full screencast traces are 15–55 MB, so the default is `--trace dom`.
12. Spend for the whole spike was 50 metered calls plus about 3 unmetered calls in the HTTPS_PROXY run: ~490k prompt tokens (~230k of them cached) and ~7.3k output including thoughts. That is well under $1.

## 13. Reference driver

```sh
uv venv /tmp/x/venv && VIRTUAL_ENV=/tmp/x/venv uv pip install playwright && /tmp/x/venv/bin/playwright install chromium
/tmp/x/venv/bin/python docs/spikes/dsh_drive.py --dsh tools/dsh/node_modules/.bin/dsh \
  --repo <seed repo> --task-file <instruction.md> --attempt-dir <scratch>/att1 \
  --model gemini-4-argon --effort medium            # [--tools-mode native] [--meter none|builtin|http://host:port/t/<tok>]
                                                    # [--extra-patch subagents.yml] [--access-mode-ui "Workspace Write" --on-approval reject]
                                                    # [--env HTTPS_PROXY=... --env NODE_USE_ENV_PROXY=1] [--trace dom|full|off]
```

What the driver does:

1. Prepares an isolated attempt dir.
2. Starts the built-in streaming Meter (Authorization redacted; rejects any path outside `projects/your-gcp-project`).
3. Initializes the web profile and writes the patch.
4. Boots `dsh web --port <p> --no-open` and captures the token URL.
5. Runs Playwright: dismisses the notice, asserts the model, effort, access and workspace labels, fills the composer, and sets t0 at the Send click.
6. Polls: dialog responder, durable `work_state()` plus Meter quiescence, DOM idle as a cross-check.
7. Saves the screenshots, trace, video and aria.
8. SIGTERMs the process group.
9. Decodes every session with `zstd -dcq` and writes `result.json` (completion, usage, run_code and ptc sub-calls with errors, Meter summary).
