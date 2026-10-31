// Types mirror docs/CONTRACTS.md (v1). Fields marked "ext" are optional
// extensions the dashboard uses when present and degrades without.

export type CostStatus = 'verified' | 'check' | 'unpriced' | 'reconciled' | 'pt'
export type Thinking = 'off' | 'low' | 'medium' | 'high' | 'xhigh' | 'max'
export type ProfileMode = 'single' | 'native_roles' | 'pipeline'
export type RetryMode = 'fresh' | 'feedback'

export type RunStatus = 'queued' | 'running' | 'paused' | 'completed' | 'cancelled' | 'failed'
export type TrialStatus = 'queued' | 'running' | 'passed' | 'failed' | 'infra_failed' | 'invalid_routing' | 'na'
export type AttemptStatus =
  | 'queued'
  | 'admitted'
  | 'preparing'
  | 'running'
  | 'verifying'
  | 'passed'
  | 'failed'
  | 'backoff'
  | 'interrupted'
  | 'error'
  | 'engine_error'
export type ExitClass = 'ok' | 'agent_error' | 'timeout' | 'infra_quota' | 'infra_auth' | 'crash' | 'invalid_routing' | 'budget'

export interface Health {
  ok: boolean
  version: string
}

export interface Preflight {
  credentials: { ok: boolean; identity: string; project: string; adc_type: string; expires_in: number; issues: string[] }
  models: { ok: boolean; availability: { model: string; location: string; status: string; thinking_levels: Thinking[] }[] }
  pricing: { ok: boolean; snapshot_id: string; fetched_at: number; issues: string[] }
  harnesses: { name: string; version: string; installed: string | boolean | null; latest: string | null }[]
}

export interface ModelInfo {
  id: string
  family: string
  provider: 'google' | 'anthropic'
  locations: string[]
  thinking_levels: Thinking[]
  priced: boolean
  enabled: boolean
}

export interface HarnessInfo {
  name: string
  variant: string
  version: string
  installed?: string | null
  latest?: string | null
  capabilities: {
    tools_mode?: string // dsh: ptc | native
    roles: string[]
    native_multi_model: boolean
    pipeline: boolean
    thinking_control: boolean | string
    meter_mode: string
    driver: string
  }
}

export interface TaskInfo {
  id: string
  version: string
  title: string
  industry: string
  tier: 'simple' | 'medium' | 'complex'
  sdlc_type: string
  languages: string[]
  timeout_s?: number
}

export interface TaskDetail extends TaskInfo {
  instruction_md: string
  repo_files: string[]
  repo_file_count: number
  hidden_tests: { fail_to_pass: number; pass_to_pass: number } | null
  history: { n: number; passed: number } | null
}

export interface RoleSpec {
  model: string
  thinking: Thinking
}

export interface ModelProfile {
  id: string
  mode: ProfileMode
  roles?: Record<string, RoleSpec>
  stages?: { role: string; model: string; thinking?: Thinking }[]
}

export interface RunConfig {
  run: { name: string; repeats: number; max_task_retries: number; retry_mode: RetryMode }
  geap: { project: string; identity: string; location: string }
  versions: 'latest'
  tasks: string[]
  harnesses: string[]
  model_profiles: ModelProfile[]
  limits: { attempt_timeout_s: { simple: number; medium: number; complex: number }; max_nudges: number }
  budget: { enabled: boolean; max_usd_total: number | null; max_usd_per_attempt: number | null; on_exceed: 'pause' | 'stop' }
  concurrency: { global: number; per_harness: number }
}

export interface DryRunCell {
  task: string
  harness: string
  profile: string
  status: 'ok' | 'na'
  reason: string | null
}

export interface DryRunResult {
  matrix: DryRunCell[]
  estimate: { with_history?: number | null; note?: string; usd_total?: number | null; usd_low?: number | null; usd_high?: number | null; minutes?: number | null; trials?: number; label?: string } | number | null
}

export interface Progress {
  total: number
  done: number
  running: number
  passed: number
  failed: number
}

export interface RunSummaryRow {
  id: string
  name: string
  status: RunStatus
  created_at: number
  started_at: number | null
  finished_at: number | null
  progress?: Progress
  spend_usd?: number
  config_hash?: string
}

export interface RunDetail extends RunSummaryRow {
  config_json?: RunConfig | string
  lock_json?: unknown
  progress: Progress
  spend_usd: number
  burn_usd_per_min?: number
  cost_status?: CostStatus
  spend_effective_usd?: number // ext
}

export interface Trial {
  id: string
  run_id: string
  task_id: string
  task_version: string
  tier: string
  industry: string
  sdlc_type: string
  harness: string
  harness_version: string
  variant: string
  profile_id: string
  profile_json?: unknown
  repeat_idx: number
  status: TrialStatus
  attempts_used: number
  passed_on_attempt: number | null
  time_to_success_s: number | null
  cost_usd: number | null
  cost_effective_usd?: number | null
  cost_status: CostStatus
  updated_at: number
  na_reason?: string | null
  infra_retries?: number
}

export interface Attempt {
  id: string
  trial_id: string
  run_id: string
  idx: number
  status: AttemptStatus
  exit_class: ExitClass | null
  t_queued: number | null
  t0: number | null
  t_end: number | null
  t_verified: number | null
  wall_s: number | null
  llm_s: number | null
  tool_s: number | null
  overhead_s: number | null
  ttft_ms: number | null
  prompt_submissions: number
  nudges: number
  llm_turns: number
  llm_calls: number
  llm_retries: number
  tool_calls: number
  tool_ok: number
  tool_fail: number
  tool_retry: number
  subagents: number
  tok_input: number
  tok_cache_read: number
  tok_cache_write_5m: number
  tok_cache_write_1h: number
  tok_output: number
  tok_thinking: number
  tok_tool_prompt: number
  cost_usd: number | null
  cost_effective_usd?: number | null
  cost_status: CostStatus
  passed: boolean | null
  f2p_passed: number | null
  f2p_total: number | null
  p2p_passed: number | null
  p2p_total: number | null
  diff_files: number | null
  diff_lines: number | null
  completion_signal: string | null
  artifacts_dir: string | null
  error: string | null
  // addendum columns
  dialogs?: number
  llm_errors?: number
  verify_s?: number | null
  thinking_verified?: string | null // match|mismatch|absent|partial|unknown, may be joined by '+'
  // ext: the SSE attempt row may carry trial context; the dashboard fills it from trials otherwise
  harness?: string
  variant?: string
  profile_id?: string
  task_id?: string
}

export interface LlmCall {
  id: string
  attempt_id: string
  seq: number
  t_start: number
  t_first_byte: number | null
  t_end: number | null
  http_status: number
  error_kind: string | null
  provider: 'google' | 'anthropic'
  model: string
  model_version: string | null
  location: string
  role: string
  traffic_type: string | null
  stream: boolean
  tok_input: number
  tok_cache_read: number
  tok_cache_write_5m: number
  tok_cache_write_1h: number
  tok_output: number
  tok_thinking: number
  tok_tool_prompt: number
  tok_total: number
  prompt_size: number | null
  tools_defined: number | null
  tool_calls_emitted: number | null
  stop_reason: string | null
  thinking_requested: string | null
  request_hash: string | null
  is_retry: boolean
  cost_usd: number | null
  cost_effective_usd?: number | null
  promotions?: string | null // comma list of promo ids
  cost_status: CostStatus
}

export interface ToolCall {
  id: string
  attempt_id: string
  call_id: string
  parent_id: string | null
  name: string
  args_hash: string | null
  status: 'ok' | 'error' | 'denied'
  error_code: string | null
  t_start: number | null // some harnesses report only t_end for nested calls
  t_end: number | null
  is_retry: boolean
  source: 'native' | 'meter'
}

export interface EventRow {
  id: string
  run_id: string
  trial_id: string | null
  attempt_id: string | null
  ts: number
  type: string
  data: Record<string, unknown>
}

/** NB: the contract reuses `llm_calls` / `tool_calls` (counts on the row) as arrays here; arrays win. */
export interface AttemptDetail extends Omit<Attempt, 'llm_calls' | 'tool_calls'> {
  llm_calls: LlmCall[]
  tool_calls: ToolCall[]
  events: EventRow[]
}

export interface TrialDetail extends Trial {
  attempts: Attempt[]
}

export interface GroupSummary {
  harness: string
  variant: string
  profile_id: string
  n: number
  pass_at_1: number
  pass_at_1_ci: [number, number] | null
  pass_k: number | null
  pass_hat_k: number | null
  cost_mean: number | null
  cost_ci: [number, number] | null
  cost_per_success: number | null
  solved_within_retries?: number | null // share solved within max_attempts
  attempt_survival?: number[] // unsolved share after attempt 1..max_attempts
  needs_more_repeats?: boolean
  // ext: effective (after reviewed promotions)
  cost_effective_mean?: number | null
  cost_per_success_effective?: number | null
  tokens: Partial<Record<'input' | 'cache_read' | 'cache_write' | 'cache_write_5m' | 'cache_write_1h' | 'output' | 'thinking' | 'tool_prompt', number>>
  time_mean: number
  time_ci: [number, number] | null
  tool_calls_mean: number
  tool_fail_rate: number
  cache_hit_ratio: number
  // ext (optional)
  time_split?: { llm_s: number; tool_s: number; overhead_s: number; verify_s: number }
  tools?: { ok: number; fail: number; retry: number; denied: number }
  tools_by_name?: { name: string; ok: number; fail: number; retry: number; denied: number }[]
  cost_status_share?: Partial<Record<CostStatus, number>>
}

export interface SliceSummary {
  key?: string
  tier?: string
  industry?: string
  harness?: string
  n: number
  pass_at_1: number
  pass_at_1_ci?: [number, number]
  cost_mean?: number | null
}

export interface RunAggregate {
  k?: number // pass@k / pass^k k = min(repeats, 5)
  max_attempts?: number // 1 + max_task_retries
  groups: GroupSummary[]
  by_tier: SliceSummary[]
  by_industry: SliceSummary[]
  // ext
  spend?: {
    total_usd: number
    total_effective_usd?: number
    by_model_category: { model: string; category: string; usd: number; usd_effective?: number; tokens: number }[]
    cache_savings_usd: number
    waste_usd: number
    waste_breakdown?: { failed_attempts_usd: number; retried_calls_usd: number | null; infra_usd: number | null; partial?: boolean }
    badge_share: Partial<Record<CostStatus, number>>
  }
}

export interface EgressRow {
  host: string
  action: 'forwarded' | 'denied'
  n: number
}

export interface GovernorLane {
  lane: string // model@location
  limit: number
  inflight: number
  n429: number
  breaker: 'open' | 'closed'
}

export interface Promotion {
  id: string
  models: string[]
  locality: string
  until: string | number // ISO date or epoch seconds
  factor: { input?: number; cache_read?: number; output?: number }
  mechanism: string
  quote: string
  source: string
}

export interface Layer4Check {
  model: string
  category: string
  catalog_per_1m: number | null
  page_per_1m: number | null
  ok: boolean
  quote: string | null
}

export interface PricingBook {
  snapshot_id: string
  fetched_at: number
  models: { model: string; location: string; rates: Record<string, number> }[]
  issues: string[]
  reviewed?: boolean
  layer4?: { ok: boolean | null; fetched_at: number | null; url: string | null; checks: Layer4Check[]; failed: unknown[] }
  promotions?: Promotion[]
  promotions_reviewed?: boolean
}

// ---- SSE payloads ----
export interface RunEvt {
  run_id: string
  status: RunStatus
  progress: Progress
  spend_usd: number
  burn_usd_per_min?: number | null // absent on older servers
  spend_effective_usd?: number // ext
}
export interface TickEvt {
  attempt_id: string
  elapsed_s: number
  tokens: { input: number; cache_read: number; cache_write: number; output: number; thinking: number }
  cost_usd: number | null
  cost_effective_usd?: number | null // ext
  tool: { ok: number; fail: number; retry: number }
  state: string
  // ext: present while in backoff
  backoff_remaining_s?: number
  cost_status?: CostStatus
}
export interface InfraEvt {
  kind: '429' | 'backoff' | 'breaker_open' | 'breaker_close' | 'aimd'
  model: string
  location: string
  detail: Record<string, unknown> | string | null
  ts?: number
}
export interface BudgetEvt {
  spent_usd: number
  cap_usd: number | null
  pct: number
  action: string | null
}
export interface LogEvt {
  level: 'debug' | 'info' | 'warn' | 'error'
  msg: string
  ts?: number
}

export type StreamEvent =
  | { type: 'run'; data: RunEvt }
  | { type: 'trial'; data: Trial }
  | { type: 'attempt'; data: Attempt }
  | { type: 'llm_call'; data: LlmCall }
  | { type: 'tool_call'; data: ToolCall }
  | { type: 'tick'; data: TickEvt }
  | { type: 'infra'; data: InfraEvt }
  | { type: 'budget'; data: BudgetEvt }
  | { type: 'log'; data: LogEvt }
