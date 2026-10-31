// In-browser simulation of the geap-eval server: REST answers, SSE-like events and PTY streams.
import type {
  Attempt,
  AttemptDetail,
  CostStatus,
  DryRunResult,
  EventRow,
  GroupSummary,
  InfraEvt,
  LlmCall,
  ModelProfile,
  RunAggregate,
  RunConfig,
  RunDetail,
  StreamEvent,
  TaskInfo,
  ToolCall,
  Trial,
  TrialDetail,
} from '@/lib/types'
import { bootstrapCI, hashStr, mean, mulberry32, passAtK, wilson } from '@/lib/stats'
import { DEFAULT_PROFILES, HARNESSES, MVP_TASKS, PROMOTIONS, RATES, TASKS, naReason, profileModels } from './catalog'
import { genScript, scriptToCast, type Script } from './script'
import { canonKey } from '@/lib/labels'

const MAX_ATTEMPTS = 4
const now = () => Date.now() / 1000

const HARNESS_BONUS: Record<string, number> = { claude_code: 0.05, omp: 0.03, agy: 0.0, pi: -0.03, 'dsh/web-ptc': -0.01, 'dsh/web-native': -0.06, 'dsh/acp-ptc': 0.0 }
const PROFILE_BASE: Record<string, number> = { 'opus-high': 0.55, 'argon-high': 0.5, 'flash-med': 0.33, 'argon-plans-flash-codes': 0.46, 'argon-low': 0.36, 'argon-med': 0.43 }
const TIER_BONUS: Record<string, number> = { simple: 0.24, medium: 0.0, complex: -0.22 }

function passProb(h: string, p: string, task: TaskInfo): number {
  const v = (PROFILE_BASE[p] ?? 0.45) + (HARNESS_BONUS[h] ?? 0) + (TIER_BONUS[task.tier] ?? 0) + ((hashStr(task.id) % 13) - 6) / 100
  return Math.min(0.95, Math.max(0.05, v))
}

interface LiveAttempt {
  script: Script
  startReal: number // real epoch when running began
  scale: number // script seconds per real second
  progressT: number // script time reached
  emittedCalls: number
  emittedTools: number
  emittedPty: number
  phase: 'preparing' | 'running' | 'backoff' | 'verifying'
  phaseUntil: number
  backoffUntil: number
}

interface MockRun {
  detail: RunDetail
  config: RunConfig
  trials: Map<string, Trial>
  order: string[]
  attempts: Map<string, Attempt>
  trialAttempts: Map<string, string[]>
  scripts: Map<string, Script>
  queue: string[]
  live: Map<string, LiveAttempt>
  ptyBuf: Map<string, string[]>
  infra: (InfraEvt & { ts: number })[]
  spendHist: [number, number][]
  logs: { level: 'info' | 'warn' | 'error' | 'debug'; msg: string; ts: number }[]
  spendEff: number
  live_: boolean
}

type Listener = (e: StreamEvent) => void

function harnessVersion(h: string) {
  const [n, v] = h.split('/')
  return HARNESSES.find((x) => x.name === n && (v ? x.variant === v : true))?.version ?? '0'
}

function harnessKeysFrom(cfg: RunConfig): string[] {
  return cfg.harnesses.map((h) => canonKey(h))
}

function trialId(runId: string, task: string, h: string, p: string, rep: number) {
  return 't_' + (hashStr(`${runId}|${task}|${h}|${p}|${rep}`) >>> 0).toString(36)
}

function makeConfig(name: string, profiles: ModelProfile[], harnesses: string[], tasks: string[], repeats: number, budget: number | null): RunConfig {
  return {
    run: { name, repeats, max_task_retries: 3, retry_mode: 'fresh' },
    geap: { project: 'your-gcp-project', identity: 'you@example.com', location: 'auto' },
    versions: 'latest',
    tasks,
    harnesses,
    model_profiles: profiles,
    limits: { attempt_timeout_s: { simple: 600, medium: 1500, complex: 3600 }, max_nudges: 2 },
    budget: { enabled: budget != null, max_usd_total: budget, max_usd_per_attempt: budget != null ? 6 : null, on_exceed: 'pause' },
    concurrency: { global: 6, per_harness: 3 },
  }
}

function blankAttempt(id: string, trial: Trial, idx: number): Attempt {
  return {
    id,
    trial_id: trial.id,
    run_id: trial.run_id,
    idx,
    status: 'queued',
    exit_class: null,
    t_queued: now(),
    t0: null,
    t_end: null,
    t_verified: null,
    wall_s: null,
    llm_s: null,
    tool_s: null,
    overhead_s: null,
    ttft_ms: null,
    prompt_submissions: 1,
    nudges: 0,
    llm_turns: 0,
    llm_calls: 0,
    llm_retries: 0,
    tool_calls: 0,
    tool_ok: 0,
    tool_fail: 0,
    tool_retry: 0,
    subagents: 0,
    tok_input: 0,
    tok_cache_read: 0,
    tok_cache_write_5m: 0,
    tok_cache_write_1h: 0,
    tok_output: 0,
    tok_thinking: 0,
    tok_tool_prompt: 0,
    cost_usd: 0,
    cost_status: 'verified',
    passed: null,
    f2p_passed: null,
    f2p_total: null,
    p2p_passed: null,
    p2p_total: null,
    diff_files: null,
    diff_lines: null,
    completion_signal: null,
    artifacts_dir: `runs/${trial.run_id}/${trial.id}/a${idx}`,
    error: null,
    harness: trial.harness,
    variant: trial.variant,
    profile_id: trial.profile_id,
    task_id: trial.task_id,
  }
}

function applyTotals(a: Attempt, s: Script, upToT = Infinity) {
  const calls = s.calls.filter((c) => c.re <= upToT)
  const tools = s.tools.filter((x) => x.re <= upToT && !x.parent_id)
  a.llm_calls = calls.length
  a.llm_turns = calls.filter((c) => c.http_status === 200).length
  a.llm_retries = calls.filter((c) => c.is_retry).length
  a.tok_input = sum(calls, 'tok_input')
  a.tok_cache_read = sum(calls, 'tok_cache_read')
  a.tok_cache_write_5m = sum(calls, 'tok_cache_write_5m')
  a.tok_cache_write_1h = sum(calls, 'tok_cache_write_1h')
  a.tok_output = sum(calls, 'tok_output')
  a.tok_thinking = sum(calls, 'tok_thinking')
  a.tok_tool_prompt = sum(calls, 'tok_tool_prompt')
  a.cost_status = s.cost_status
  a.cost_usd = s.cost_status === 'unpriced' ? null : calls.reduce((x, c) => x + (c.cost_usd ?? 0), 0)
  a.cost_effective_usd = s.cost_status === 'unpriced' ? null : calls.reduce((x, c) => x + (c.cost_effective_usd ?? c.cost_usd ?? 0), 0)
  a.tool_calls = tools.length
  a.tool_ok = tools.filter((x) => x.status === 'ok').length
  a.tool_fail = tools.filter((x) => x.status !== 'ok').length
  a.tool_retry = tools.filter((x) => x.is_retry).length
}

function sum<T>(xs: T[], k: keyof T): number {
  let s = 0
  for (const x of xs) s += Number(x[k] ?? 0)
  return s
}

function finalizeAttempt(a: Attempt, s: Script, t0: number) {
  applyTotals(a, s)
  a.t0 = t0
  a.t_end = t0 + s.wall_s
  a.t_verified = a.t_end + s.verify_s
  a.wall_s = s.wall_s
  a.llm_s = s.llm_s
  a.tool_s = s.tool_s
  a.overhead_s = s.overhead_s
  a.ttft_ms = s.ttft_ms
  a.passed = s.passed
  a.status = s.passed ? 'passed' : 'failed'
  a.exit_class = s.passed ? 'ok' : 'agent_error'
  a.f2p_passed = s.f2p[0]
  a.f2p_total = s.f2p[1]
  a.p2p_passed = s.p2p[0]
  a.p2p_total = s.p2p[1]
  a.diff_files = s.diff_files
  a.diff_lines = s.diff_lines
  a.subagents = s.subagents
  a.completion_signal = 'meter_quiescent+session_record'
  a.verify_s = s.verify_s
  a.thinking_verified = s.thinking_verified
  a.dialogs = s.dialogs
  a.llm_errors = s.calls.filter((c) => c.http_status !== 200).length
}

class Engine {
  runs = new Map<string, MockRun>()
  listeners = new Map<string, Set<Listener>>()
  ptySubs = new Map<string, Set<(d: string) => void>>()
  timer: number | null = null

  constructor() {
    const tasks = MVP_TASKS
    const hs = ['claude_code', 'pi', 'omp', 'dsh', 'dsh/web-native', 'dsh/acp-ptc', 'agy']
    this.seedRun('r_q4baseline', 'q4-baseline', makeConfig('q4-baseline', DEFAULT_PROFILES, hs, tasks, 3, 2500), now() - 60 * 74, true, 0.62)
    this.seedRun(
      'r_argonsweep',
      'argon-thinking-sweep',
      makeConfig(
        'argon-thinking-sweep',
        [
          { id: 'argon-low', mode: 'single', roles: { default: { model: 'gemini-4-argon', thinking: 'low' } } },
          { id: 'argon-med', mode: 'single', roles: { default: { model: 'gemini-4-argon', thinking: 'medium' } } },
          { id: 'argon-high', mode: 'single', roles: { default: { model: 'gemini-4-argon', thinking: 'high' } } },
        ],
        ['omp', 'agy', 'dsh'],
        tasks,
        2,
        null,
      ),
      now() - 86400 * 1.3,
      false,
      1,
    )
    this.seedRun('r_smoke', 'smoke', makeConfig('smoke', DEFAULT_PROFILES.slice(0, 2), ['claude_code', 'pi'], tasks.slice(0, 4), 1, null), now() - 86400 * 2.8, false, 1)
  }

  // ---------- seeding ----------
  seedRun(id: string, name: string, cfg: RunConfig, created: number, live: boolean, doneFrac: number) {
    const run: MockRun = {
      detail: { id, name, status: live ? 'running' : 'completed', created_at: created, started_at: created + 20, finished_at: live ? null : created + 3600 * 3.1, progress: { total: 0, done: 0, running: 0, passed: 0, failed: 0 }, spend_usd: 0, config_json: cfg, config_hash: 'sha256:' + (hashStr(name) >>> 0).toString(16) + 'c9e1', burn_usd_per_min: 0, cost_status: 'verified' },
      config: cfg,
      trials: new Map(),
      order: [],
      attempts: new Map(),
      trialAttempts: new Map(),
      scripts: new Map(),
      queue: [],
      live: new Map(),
      ptyBuf: new Map(),
      infra: [],
      spendHist: [],
      logs: [],
      spendEff: 0,
      live_: live,
    }
    const hks = harnessKeysFrom(cfg)
    const r = mulberry32(hashStr(id))
    const all: Trial[] = []
    for (const taskId of cfg.tasks) {
      const task = TASKS.find((t) => t.id === taskId)!
      for (const h of hks) {
        for (const p of cfg.model_profiles) {
          const na = naReason(h, p)
          for (let rep = 0; rep < cfg.run.repeats; rep++) {
            const [hn, hv] = h.split('/')
            const tr: Trial = {
              id: trialId(id, taskId, h, p.id, rep),
              run_id: id,
              task_id: taskId,
              task_version: '1',
              tier: task.tier,
              industry: task.industry,
              sdlc_type: task.sdlc_type,
              harness: hn,
              harness_version: harnessVersion(h),
              variant: hv ?? 'default',
              profile_id: p.id,
              profile_json: p,
              repeat_idx: rep,
              status: na ? 'na' : 'queued',
              na_reason: na,
              infra_retries: na ? 0 : hashStr(taskId + h + rep) % 7 === 0 ? 1 + (hashStr(p.id + rep) % 3) : 0,
              attempts_used: 0,
              passed_on_attempt: null,
              time_to_success_s: null,
              cost_usd: null,
              cost_status: 'verified',
              updated_at: created,
            }
            all.push(tr)
          }
        }
      }
    }
    // shuffle runnable order deterministically (interleave repeats by rep index first)
    const runnable = all.filter((t) => t.status !== 'na').sort((a, b) => a.repeat_idx - b.repeat_idx || (hashStr(a.id) % 1000) - (hashStr(b.id) % 1000))
    for (const t of all) {
      run.trials.set(t.id, t)
      run.order.push(t.id)
    }
    const nDone = Math.floor(runnable.length * doneFrac)
    let clock = created + 30
    const span = (live ? now() - created - 40 : 3600 * 3) / Math.max(1, nDone)
    runnable.forEach((t, i) => {
      if (i < nDone) {
        this.completeTrialOffline(run, t, clock + r() * span * 3)
        clock += span
      } else run.queue.push(t.id)
    })
    // infra history
    const models = new Set(cfg.model_profiles.flatMap(profileModels))
    for (const m of models) {
      const n = m.startsWith('claude') ? 18 : m.includes('argon') ? 11 : 6
      for (let i = 0; i < n; i++) {
        const ts = created + r() * ((live ? now() : created + 3 * 3600) - created)
        run.infra.push({ kind: '429', model: m, location: 'global', detail: { retry_after_s: Math.round(2 + r() * 20) }, ts })
        if (r() < 0.4) run.infra.push({ kind: 'aimd', model: m, location: 'global', detail: { limit: Math.max(1, Math.round(1 + r() * 5)), reason: 'halve_on_429' }, ts: ts + 1 })
      }
    }
    run.infra.sort((a, b) => a.ts - b.ts)
    const fin = [...run.trials.values()].filter((t) => t.status === 'passed' || t.status === 'failed').sort((a, b) => a.updated_at - b.updated_at).slice(-24)
    for (const t of fin)
      run.logs.push({ level: t.status === 'passed' ? 'info' : 'warn', msg: `${t.task_id} · ${t.harness}${t.variant !== 'default' ? '/' + t.variant : ''} · ${t.profile_id} → ${t.status} ${t.status === 'passed' ? 'on attempt ' + t.passed_on_attempt : 'after ' + t.attempts_used + ' attempts'}`, ts: t.updated_at })
    for (const e of run.infra.filter((e) => e.kind === '429').slice(-6)) run.logs.push({ level: 'warn', msg: `429 RESOURCE_EXHAUSTED on ${e.model}@${e.location} — backing off`, ts: e.ts })
    run.logs.sort((a, b) => a.ts - b.ts)
    this.recount(run)
    // spend history
    const done = [...run.trials.values()].filter((t) => t.status === 'passed' || t.status === 'failed').sort((a, b) => a.updated_at - b.updated_at)
    let acc = 0
    for (const t of done) {
      acc += t.cost_usd ?? 0
      run.spendHist.push([t.updated_at, acc])
    }
    this.runs.set(id, run)
  }

  completeTrialOffline(run: MockRun, t: Trial, tEnd: number) {
    const task = TASKS.find((x) => x.id === t.task_id)!
    const hk = t.variant !== 'default' ? `${t.harness}/${t.variant}` : t.harness
    const prof = run.config.model_profiles.find((p) => p.id === t.profile_id)!
    const ids: string[] = []
    let cost = 0
    let costEff = 0
    let tts = 0
    let worst: CostStatus = 'verified'
    let start = tEnd
    const scripts: Script[] = []
    for (let idx = 1; idx <= MAX_ATTEMPTS; idx++) {
      const aid = `${t.id}_a${idx}`
      const s = genScript({ attemptId: aid, harnessKey: hk, harnessVersion: t.harness_version, profile: prof, task, idx, passProb: passProb(hk, t.profile_id, task) * Math.pow(0.62, idx - 1) })
      scripts.push(s)
      ids.push(aid)
      if (s.passed) break
    }
    const totalWall = scripts.reduce((x, s) => x + s.wall_s + s.verify_s, 0)
    start = tEnd - totalWall
    let tc = start
    const rowIds: string[] = []
    let rowIdx = 0
    scripts.forEach((s, i) => {
      // occasionally the engine itself fails before the agent runs (not counted against the agent)
      if (hashStr(ids[i] + 'ee') % 40 === 0) {
        const ee = blankAttempt(`${ids[i]}_ee`, t, ++rowIdx)
        ee.status = 'engine_error'
        ee.exit_class = null
        ee.error = 'engine: meter proxy failed to bind port (EADDRINUSE); attempt re-queued, task retry not consumed'
        ee.t0 = tc - 4
        ee.t_end = tc - 3.5
        ee.wall_s = 0.5
        ee.cost_usd = 0
        ee.cost_effective_usd = 0
        run.attempts.set(ee.id, ee)
        run.scripts.set(ee.id, { ...s, calls: [], tools: [], pty: [{ t: 0, data: '\x1b[2m[geap-eval] engine error: meter proxy failed to bind\x1b[0m\r\n' }], wall_s: 0.5 })
        rowIds.push(ee.id)
      }
      const a = blankAttempt(ids[i], t, ++rowIdx)
      a.t_queued = tc - 2
      finalizeAttempt(a, s, tc)
      tc += s.wall_s + s.verify_s
      run.attempts.set(a.id, a)
      run.scripts.set(a.id, s)
      rowIds.push(a.id)
      costEff += a.cost_effective_usd ?? 0
      cost += a.cost_usd ?? 0
      tts += s.wall_s
      if (a.cost_status === 'check' && worst === 'verified') worst = 'check'
    })
    const last = scripts[scripts.length - 1]
    t.attempts_used = scripts.length
    t.status = last.passed ? 'passed' : 'failed'
    t.passed_on_attempt = last.passed ? scripts.length : null
    t.time_to_success_s = last.passed ? tts : null
    t.cost_usd = cost
    t.cost_effective_usd = costEff
    t.cost_status = worst
    t.updated_at = tEnd
    run.trialAttempts.set(t.id, rowIds)
  }

  recount(run: MockRun) {
    let total = 0,
      done = 0,
      passed = 0,
      failed = 0,
      spend = 0
    for (const t of run.trials.values()) {
      if (t.status === 'na') continue
      total++
      if (t.status === 'passed') passed++
      if (t.status === 'failed' || t.status === 'infra_failed') failed++
      if (t.status === 'passed' || t.status === 'failed' || t.status === 'infra_failed') done++
    }
    let eff = 0
    for (const a of run.attempts.values()) {
      spend += a.cost_usd ?? 0
      eff += a.cost_effective_usd ?? a.cost_usd ?? 0
    }
    run.spendEff = eff
    run.detail.progress = { total, done, running: run.live.size, passed, failed }
    run.detail.spend_usd = spend
    const h = run.spendHist
    if (h.length > 1) {
      const cut = now() - 600
      const old = h.find((x) => x[0] >= cut) ?? h[0]
      const mins = Math.max(1, (now() - old[0]) / 60)
      run.detail.burn_usd_per_min = (spend - old[1]) / mins
    }
  }

  // ---------- live simulation ----------
  start() {
    if (this.timer != null) return
    this.timer = window.setInterval(() => this.step(), 1000)
  }

  emit(runId: string, e: StreamEvent) {
    if (e.type === 'log') {
      const r = this.runs.get(runId)
      if (r) {
        r.logs.push({ ...e.data, ts: e.data.ts ?? now() })
        if (r.logs.length > 300) r.logs.splice(0, 100)
      }
    }
    this.listeners.get(runId)?.forEach((l) => l(e))
  }

  pty(attemptId: string, data: string) {
    for (const run of this.runs.values()) {
      const b = run.ptyBuf.get(attemptId)
      if (b) {
        b.push(data)
        break
      }
    }
    this.ptySubs.get(attemptId)?.forEach((f) => f(data))
  }

  step() {
    for (const run of this.runs.values()) {
      if (!run.live_ || run.detail.status !== 'running') continue
      const t = now()
      // admit
      while (run.live.size < run.config.concurrency.global && run.queue.length) {
        this.admit(run, run.queue.shift()!)
      }
      for (const [aid, la] of run.live) this.advance(run, aid, la, t)
      this.recount(run)
      run.spendHist.push([t, run.detail.spend_usd])
      if (run.spendHist.length > 4000) run.spendHist.splice(0, 1000)
      const d = run.detail
      this.emit(run.detail.id, { type: 'run', data: { run_id: d.id, status: d.status, progress: d.progress, spend_usd: d.spend_usd, burn_usd_per_min: d.burn_usd_per_min ?? 0, spend_effective_usd: run.spendEff } })
      const cap = run.config.budget.max_usd_total
      if (run.config.budget.enabled && cap) {
        const pct = d.spend_usd / cap
        this.emit(d.id, { type: 'budget', data: { spent_usd: d.spend_usd, cap_usd: cap, pct, action: pct >= 1 ? 'pause' : pct >= 0.8 ? 'warn' : null } })
      }
      if (!run.queue.length && !run.live.size) {
        d.status = 'completed'
        d.finished_at = t
      }
    }
  }

  admit(run: MockRun, trialIdOrAttempt: string, idx = 1) {
    const t = run.trials.get(trialIdOrAttempt)!
    const task = TASKS.find((x) => x.id === t.task_id)!
    const hk = t.variant !== 'default' ? `${t.harness}/${t.variant}` : t.harness
    const prof = run.config.model_profiles.find((p) => p.id === t.profile_id)!
    const aid = `${t.id}_a${idx}`
    const s = genScript({ attemptId: aid, harnessKey: hk, harnessVersion: t.harness_version, profile: prof, task, idx, passProb: passProb(hk, t.profile_id, task) * Math.pow(0.62, idx - 1) })
    const a = blankAttempt(aid, t, idx)
    a.status = 'preparing'
    run.attempts.set(aid, a)
    run.scripts.set(aid, s)
    const ids = run.trialAttempts.get(t.id) ?? []
    ids.push(aid)
    run.trialAttempts.set(t.id, ids)
    const realDur = 30 + (hashStr(aid) % 50)
    run.live.set(aid, { script: s, startReal: 0, scale: s.wall_s / realDur, progressT: 0, emittedCalls: 0, emittedTools: 0, emittedPty: 0, phase: 'preparing', phaseUntil: now() + 2 + (hashStr(aid) % 3), backoffUntil: 0 })
    run.ptyBuf.set(aid, [])
    t.status = 'running'
    t.attempts_used = idx
    t.updated_at = now()
    this.emit(run.detail.id, { type: 'trial', data: { ...t } })
    this.emit(run.detail.id, { type: 'attempt', data: { ...a } })
    this.pty(aid, `\x1b[2m[geap-eval] preparing workspace · isolated HOME · meter on :${9100 + (hashStr(aid) % 800)}\x1b[0m\r\n`)
  }

  advance(run: MockRun, aid: string, la: LiveAttempt, t: number) {
    const a = run.attempts.get(aid)!
    const tr = run.trials.get(a.trial_id)!
    const rid = run.detail.id
    if (la.phase === 'preparing') {
      if (t >= la.phaseUntil) {
        la.phase = 'running'
        la.startReal = t
        a.status = 'running'
        a.t0 = t
        this.emit(rid, { type: 'attempt', data: { ...a } })
        this.pty(aid, '\x1b[2J\x1b[H')
      } else return
    }
    if (la.phase === 'backoff') {
      if (t >= la.backoffUntil) {
        la.phase = 'running'
        a.status = 'running'
        this.emit(rid, { type: 'attempt', data: { ...a } })
      } else {
        this.emitTick(rid, a, la, t)
        return
      }
    }
    if (la.phase === 'running') {
      la.progressT += la.scale
      const s = la.script
      while (la.emittedPty < s.pty.length && s.pty[la.emittedPty].t <= la.progressT) this.pty(aid, s.pty[la.emittedPty++].data)
      while (la.emittedCalls < s.calls.length && s.calls[la.emittedCalls].re <= la.progressT) {
        const c = s.calls[la.emittedCalls++]
        const row = this.callRow(c, a, a.t0!)
        this.emit(rid, { type: 'llm_call', data: row })
        if (c.http_status === 429) {
          const ev: InfraEvt & { ts: number } = { kind: '429', model: c.model, location: c.location, detail: { retry_after_s: 6 }, ts: t }
          run.infra.push(ev)
          this.emit(rid, { type: 'infra', data: ev })
        }
      }
      while (la.emittedTools < s.tools.length && s.tools[la.emittedTools].re <= la.progressT) {
        const x = s.tools[la.emittedTools++]
        this.emit(rid, { type: 'tool_call', data: this.toolRow(x, a, a.t0!) })
      }
      applyTotals(a, s, la.progressT)
      // occasional quota backoff on running attempts
      const r = (hashStr(aid + Math.floor(t)) % 1000) / 1000
      if (r < 0.012 && la.progressT < s.wall_s * 0.85) {
        la.phase = 'backoff'
        const wait = 4 + (hashStr(aid + 'b' + Math.floor(t)) % 9)
        la.backoffUntil = t + wait
        a.status = 'backoff'
        const model = s.calls[Math.min(la.emittedCalls, s.calls.length - 1)]?.model ?? 'gemini-3.8-flash'
        const e1: InfraEvt & { ts: number } = { kind: '429', model, location: 'global', detail: { retry_after_s: wait }, ts: t }
        const e2: InfraEvt & { ts: number } = { kind: 'backoff', model, location: 'global', detail: { attempt_id: aid, wait_s: wait }, ts: t }
        const lim = 1 + (hashStr(model + Math.floor(t / 60)) % 4)
        const e3: InfraEvt & { ts: number } = { kind: 'aimd', model, location: 'global', detail: { limit: lim, reason: 'halve_on_429' }, ts: t }
        run.infra.push(e1, e2, e3)
        this.emit(rid, { type: 'infra', data: e1 })
        this.emit(rid, { type: 'infra', data: e2 })
        this.emit(rid, { type: 'infra', data: e3 })
        const recent = run.infra.filter((e) => e.kind === '429' && e.model === model && e.ts > t - 30).length
        if (recent >= 3) {
          const bo: InfraEvt & { ts: number } = { kind: 'breaker_open', model, location: 'global', detail: { cooldown_s: 20 }, ts: t }
          run.infra.push(bo)
          this.emit(rid, { type: 'infra', data: bo })
          window.setTimeout(() => {
            const bc: InfraEvt & { ts: number } = { kind: 'breaker_close', model, location: 'global', detail: null, ts: now() }
            run.infra.push(bc)
            this.emit(rid, { type: 'infra', data: bc })
          }, 20000)
        }
        this.emit(rid, { type: 'log', data: { level: 'warn', msg: `429 RESOURCE_EXHAUSTED on ${model}@global — backing off ${wait}s (${aid.slice(-8)})`, ts: t } })
        this.emit(rid, { type: 'attempt', data: { ...a } })
      }
      if (la.progressT >= s.wall_s) {
        la.phase = 'verifying'
        la.phaseUntil = t + 3
        a.status = 'verifying'
        a.t_end = t
        this.emit(rid, { type: 'attempt', data: { ...a } })
        this.pty(aid, '\r\n\x1b[2m[geap-eval] turn complete (meter quiescent) · verifying in clean container…\x1b[0m\r\n')
      }
      this.emitTick(rid, a, la, t)
      return
    }
    if (la.phase === 'verifying' && t >= la.phaseUntil) {
      const s = la.script
      const t0 = a.t0!
      finalizeAttempt(a, s, t0)
      run.live.delete(aid)
      this.emit(rid, { type: 'attempt', data: { ...a } })
      this.pty(aid, s.passed ? '\x1b[32m✓ verifier: all tests passed\x1b[0m\r\n' : `\x1b[31m✗ verifier: ${s.failing.length || 1} failing\x1b[0m\r\n`)
      if (s.passed || a.idx >= MAX_ATTEMPTS) {
        const ids = run.trialAttempts.get(tr.id) ?? []
        const atts = ids.map((i) => run.attempts.get(i)!).filter(Boolean)
        tr.status = s.passed ? 'passed' : 'failed'
        tr.passed_on_attempt = s.passed ? a.idx : null
        tr.cost_usd = atts.reduce((x, y) => x + (y.cost_usd ?? 0), 0)
        tr.cost_effective_usd = atts.reduce((x, y) => x + (y.cost_effective_usd ?? 0), 0)
        tr.time_to_success_s = s.passed ? atts.reduce((x, y) => x + (y.wall_s ?? 0), 0) : null
        tr.updated_at = now()
        this.emit(rid, { type: 'trial', data: { ...tr } })
        this.emit(rid, { type: 'log', data: { level: s.passed ? 'info' : 'warn', msg: `${tr.task_id} · ${tr.harness}${tr.variant !== 'default' ? '/' + tr.variant : ''} · ${tr.profile_id} → ${tr.status} on attempt ${a.idx}`, ts: now() } })
      } else {
        this.emit(rid, { type: 'log', data: { level: 'info', msg: `${tr.task_id} attempt ${a.idx} failed; retrying fresh (${a.idx + 1}/${MAX_ATTEMPTS})`, ts: now() } })
        this.admit(run, tr.id, a.idx + 1)
      }
    }
  }

  emitTick(rid: string, a: Attempt, la: LiveAttempt, t: number) {
    this.emit(rid, {
      type: 'tick',
      data: {
        attempt_id: a.id,
        elapsed_s: t - la.startReal,
        tokens: { input: a.tok_input, cache_read: a.tok_cache_read, cache_write: a.tok_cache_write_5m + a.tok_cache_write_1h, output: a.tok_output, thinking: a.tok_thinking },
        cost_usd: a.cost_status === 'unpriced' ? null : a.cost_usd,
        cost_effective_usd: a.cost_status === 'unpriced' ? null : a.cost_effective_usd,
        tool: { ok: a.tool_ok, fail: a.tool_fail - 0, retry: a.tool_retry },
        state: la.phase,
        backoff_remaining_s: la.phase === 'backoff' ? Math.max(0, la.backoffUntil - t) : undefined,
        cost_status: a.cost_status,
      },
    })
  }

  callRow(c: Script['calls'][number], a: Attempt, t0: number): LlmCall {
    const { rs, rfb, re, ...rest } = c
    return { ...rest, attempt_id: a.id, t_start: t0 + rs, t_first_byte: t0 + rfb, t_end: t0 + re }
  }
  toolRow(x: Script['tools'][number], a: Attempt, t0: number): ToolCall {
    const { rs, re, label: _label, ...rest } = x
    void _label
    return { ...rest, attempt_id: a.id, t_start: t0 + rs, t_end: t0 + re }
  }

  // ---------- API ----------
  findAttempt(id: string): [MockRun, Attempt] | null {
    for (const run of this.runs.values()) {
      const a = run.attempts.get(id)
      if (a) return [run, a]
    }
    return null
  }

  listRuns() {
    return [...this.runs.values()]
      .map((r) => {
        this.recount(r)
        const { config_json: _c, ...rest } = r.detail
        void _c
        return { ...rest }
      })
      .sort((a, b) => b.created_at - a.created_at)
  }

  getRun(id: string): RunDetail {
    const r = this.mustRun(id)
    this.recount(r)
    return { ...r.detail, spend_effective_usd: r.spendEff }
  }

  mustRun(id: string): MockRun {
    const r = this.runs.get(id)
    if (!r) throw new Error(`run ${id} not found`)
    return r
  }

  trials(id: string): Trial[] {
    const r = this.mustRun(id)
    return r.order.map((t) => ({ ...r.trials.get(t)! }))
  }

  trial(id: string): TrialDetail {
    for (const run of this.runs.values()) {
      const t = run.trials.get(id)
      if (t) return { ...t, attempts: (run.trialAttempts.get(id) ?? []).map((a) => ({ ...run.attempts.get(a)! })) }
    }
    throw new Error('trial not found')
  }

  attempt(id: string): AttemptDetail {
    const f = this.findAttempt(id)
    if (!f) throw new Error('attempt not found')
    const [run, a] = f
    const s = run.scripts.get(id)!
    const t0 = a.t0 ?? now()
    const live = run.live.get(id)
    const upTo = live ? live.progressT : Infinity
    const calls = s.calls.filter((c) => c.re <= upTo).map((c) => this.callRow(c, a, t0))
    const tools = s.tools.filter((x) => x.re <= upTo).map((x) => this.toolRow(x, a, t0))
    const events: EventRow[] = [
      { id: id + '-e0', run_id: run.detail.id, trial_id: a.trial_id, attempt_id: id, ts: t0 - 2, type: 'workspace_ready', data: { snapshot: 'seed', retry_mode: run.config.run.retry_mode } },
      { id: id + '-e1', run_id: run.detail.id, trial_id: a.trial_id, attempt_id: id, ts: t0, type: 'prompt_submitted', data: { kind: 'initial', chars: 1840 } },
    ]
    const hosts: [string, 'forwarded' | 'denied', string | undefined][] = [
      ['aiplatform.googleapis.com', 'forwarded', '/v1/projects/your-gcp-project/locations/global/publishers/…:streamGenerateContent'],
      ['oauth2.googleapis.com', 'forwarded', '/token'],
      ['registry.npmjs.org', 'denied', '/-/v1/search'],
      [a.harness === 'claude_code' ? 'statsig.anthropic.com' : a.harness === 'agy' ? 'play.googleapis.com' : 'telemetry.dsh.dev', 'denied', undefined],
      ['sentry.io', 'denied', '/api/42/envelope/'],
    ]
    const nEg = 6 + (hashStr(id) % 8)
    for (let i = 0; i < nEg; i++) {
      const [host, action, path] = hosts[i < 2 ? i : 2 + (hashStr(id + i) % 3)]
      events.push({ id: `${id}-eg${i}`, run_id: run.detail.id, trial_id: a.trial_id, attempt_id: id, ts: t0 + (i / nEg) * (s.wall_s || 1), type: 'egress', data: path ? { host, action, path } : { host, action } })
    }
    if (a.status === 'engine_error') events.push({ id: id + '-ee', run_id: run.detail.id, trial_id: a.trial_id, attempt_id: id, ts: t0, type: 'engine_error', data: { error: a.error } })
    events.sort((x, y) => x.ts - y.ts)
    if (!live && a.status !== 'engine_error') {
      events.push({ id: id + '-e2', run_id: run.detail.id, trial_id: a.trial_id, attempt_id: id, ts: t0 + s.wall_s, type: 'turn_complete', data: { signal: 'meter_quiescent+session_record' } })
      events.push({
        id: id + '-e3',
        run_id: run.detail.id,
        trial_id: a.trial_id,
        attempt_id: id,
        ts: t0 + s.wall_s + s.verify_s,
        type: 'verifier',
        data: { fail_to_pass: { passed: s.f2p[0], total: s.f2p[1], failed: s.failing }, pass_to_pass: { passed: s.p2p[0], total: s.p2p[1], failed: [] }, log_tail: s.log_tail, verify_s: s.verify_s },
      })
    }
    const { llm_calls: _lc, tool_calls: _tc, ...row } = a
    void _lc
    void _tc
    return { ...row, llm_calls: calls, tool_calls: tools, events }
  }

  cast(id: string): string {
    const f = this.findAttempt(id)
    if (!f) throw new Error('attempt not found')
    const [run, a] = f
    const s = run.scripts.get(id)!
    return scriptToCast(s, a.t0 ?? now(), `${a.task_id} · ${a.harness}`)
  }

  summary(id: string): RunAggregate {
    const run = this.mustRun(id)
    const trials = [...run.trials.values()].filter((t) => t.status === 'passed' || t.status === 'failed')
    const groups = new Map<string, Trial[]>()
    for (const t of trials) {
      const k = `${t.harness}|${t.variant}|${t.profile_id}`
      if (!groups.has(k)) groups.set(k, [])
      groups.get(k)!.push(t)
    }
    const kRep = Math.min(run.config.run.repeats, 5)
    const maxA = run.config.run.max_task_retries + 1
    const atts = (t: Trial) => (run.trialAttempts.get(t.id) ?? []).map((a) => run.attempts.get(a)!).filter((a) => a && a.t_end)
    const out: GroupSummary[] = []
    for (const [k, ts] of groups) {
      const [harness, variant, profile_id] = k.split('|')
      const a1 = ts.map((t) => atts(t)[0]).filter(Boolean)
      const allA = ts.flatMap(atts)
      const firstPass = a1.filter((a) => a.passed).length
      const n = a1.length
      const costs = ts.map((t) => t.cost_usd ?? 0)
      const effs = ts.map((t) => t.cost_effective_usd ?? t.cost_usd ?? 0)
      const times = a1.map((a) => a.wall_s ?? 0)
      const solved = ts.filter((t) => t.status === 'passed').length
      const tokSum = (f: keyof Attempt) => mean(allA.map((a) => Number(a[f] ?? 0)))
      const toolsByName = new Map<string, { name: string; ok: number; fail: number; retry: number; denied: number }>()
      for (const a of allA) {
        for (const x of run.scripts.get(a.id)?.tools ?? []) {
          if (x.parent_id) continue
          const e = toolsByName.get(x.name) ?? { name: x.name, ok: 0, fail: 0, retry: 0, denied: 0 }
          if (x.is_retry) e.retry++
          else if (x.status === 'ok') e.ok++
          else if (x.status === 'denied') e.denied++
          else e.fail++
          toolsByName.set(x.name, e)
        }
      }
      const tb = [...toolsByName.values()]
      const share: Partial<Record<CostStatus, number>> = {}
      for (const a of allA) share[a.cost_status] = (share[a.cost_status] ?? 0) + 1
      for (const s of Object.keys(share) as CostStatus[]) share[s] = share[s]! / allA.length
      out.push({
        harness,
        variant,
        profile_id,
        n,
        pass_at_1: n ? firstPass / n : 0,
        pass_at_1_ci: wilson(firstPass, n),
        pass_k: n >= kRep ? passAtK(n, firstPass, kRep) : null,
        pass_hat_k: n >= kRep ? (firstPass / n) ** kRep : null,
        solved_within_retries: ts.length ? solved / ts.length : null,
        attempt_survival: Array.from({ length: maxA }, (_, i) => ts.filter((t) => !(t.status === 'passed' && (t.passed_on_attempt ?? 99) <= i + 1)).length / Math.max(1, ts.length)),
        needs_more_repeats: n < 10,
        cost_mean: mean(costs),
        cost_ci: bootstrapCI(costs, 300, hashStr(k)),
        cost_per_success: solved ? costs.reduce((x, y) => x + y, 0) / solved : null,
        cost_effective_mean: mean(effs),
        cost_per_success_effective: solved ? effs.reduce((x, y) => x + y, 0) / solved : null,
        tokens: {
          input: tokSum('tok_input'),
          cache_read: tokSum('tok_cache_read'),
          cache_write: tokSum('tok_cache_write_5m') + tokSum('tok_cache_write_1h'),
          output: tokSum('tok_output'),
          thinking: tokSum('tok_thinking'),
          tool_prompt: tokSum('tok_tool_prompt'),
        },
        time_mean: mean(times),
        time_ci: bootstrapCI(times, 300, hashStr(k) + 1),
        tool_calls_mean: mean(allA.map((a) => a.tool_calls)),
        tool_fail_rate: sum(allA, 'tool_fail') / Math.max(1, sum(allA, 'tool_calls')),
        cache_hit_ratio: sum(allA, 'tok_cache_read') / Math.max(1, sum(allA, 'tok_cache_read') + sum(allA, 'tok_input') + sum(allA, 'tok_cache_write_5m')),
        time_split: {
          llm_s: mean(allA.map((a) => a.llm_s ?? 0)),
          tool_s: mean(allA.map((a) => a.tool_s ?? 0)),
          overhead_s: mean(allA.map((a) => a.overhead_s ?? 0)),
          verify_s: mean(allA.map((a) => (a.t_verified ?? 0) - (a.t_end ?? 0))),
        },
        tools: { ok: tb.reduce((x, y) => x + y.ok, 0), fail: tb.reduce((x, y) => x + y.fail, 0), retry: tb.reduce((x, y) => x + y.retry, 0), denied: tb.reduce((x, y) => x + y.denied, 0) },
        tools_by_name: tb.sort((x, y) => y.ok + y.fail - (x.ok + x.fail)),
        cost_status_share: share,
      })
    }
    const slice = (key: 'tier' | 'industry') => {
      const m = new Map<string, Trial[]>()
      for (const t of trials) {
        const kk = `${t[key]}|${t.harness}${t.variant !== 'default' ? '/' + t.variant : ''}`
        if (!m.has(kk)) m.set(kk, [])
        m.get(kk)!.push(t)
      }
      return [...m].map(([kk, ts]) => {
        const [v, harness] = kk.split('|')
        const p1 = ts.filter((t) => t.passed_on_attempt === 1).length
        return { key: kk, [key]: v, harness, n: ts.length, pass_at_1: p1 / ts.length, pass_at_1_ci: wilson(p1, ts.length), cost_mean: mean(ts.map((t) => t.cost_usd ?? 0)) }
      })
    }
    // spend
    const bmc = new Map<string, { model: string; category: string; usd: number; usd_effective: number; tokens: number }>()
    let totalEff = 0
    let savings = 0
    let waste = 0
    let retriedCalls = 0
    let badge: Partial<Record<CostStatus, number>> = {}
    let totalUsd = 0
    for (const a of run.attempts.values()) {
      const s = run.scripts.get(a.id)
      if (!s) continue
      const live = run.live.get(a.id)
      const calls = live ? s.calls.filter((c) => c.re <= live.progressT) : s.calls
      for (const c of calls) {
        const R = RATES_LOOKUP(c.model)
        const cats: [string, number, number][] = [
          ['input', c.tok_input, R.input ?? 0],
          ['cache_read', c.tok_cache_read, R.cache_read ?? 0],
          ['cache_write', c.tok_cache_write_5m + c.tok_cache_write_1h, R.cache_write_5m ?? 0],
          ['output', c.tok_output, R.output ?? 0],
          ['thinking', c.tok_thinking, R.thinking ?? R.output ?? 0],
          ['tool_prompt', c.tok_tool_prompt, R.tool_use_prompt ?? 0],
        ]
        for (const [cat, tok, rate] of cats) {
          if (!tok) continue
          const key = c.model + '|' + cat
          const e = bmc.get(key) ?? { model: c.model, category: cat, usd: 0, usd_effective: 0, tokens: 0 }
          e.tokens += tok
          e.usd += (tok * rate) / 1e6
          e.usd_effective += ((tok * rate) / 1e6) * promoFactor(c.model, cat)
          bmc.set(key, e)
        }
        savings += (c.tok_cache_read * ((R.input ?? 0) - (R.cache_read ?? 0))) / 1e6
        if (c.is_retry) retriedCalls += c.cost_usd ?? 0
      }
      const cu = a.cost_usd ?? 0
      totalUsd += cu
      totalEff += a.cost_effective_usd ?? cu
      badge[a.cost_status] = (badge[a.cost_status] ?? 0) + (a.cost_status === 'unpriced' ? 1 : cu)
      if (a.status === 'failed') waste += cu
    }
    const bsum = Object.values(badge).reduce((x, y) => x + (y ?? 0), 0) || 1
    badge = Object.fromEntries(Object.entries(badge).map(([k, v]) => [k, (v ?? 0) / bsum]))
    return {
      k: kRep,
      max_attempts: maxA,
      groups: out.sort((a, b) => b.pass_at_1 - a.pass_at_1),
      by_tier: slice('tier'),
      by_industry: slice('industry'),
      spend: {
        total_usd: totalUsd,
        total_effective_usd: totalEff,
        by_model_category: [...bmc.values()],
        cache_savings_usd: savings,
        waste_usd: waste,
        waste_breakdown: { failed_attempts_usd: waste, retried_calls_usd: retriedCalls, infra_usd: 0 },
        badge_share: badge,
      },
    }
  }

  dryRun(cfg: RunConfig): DryRunResult {
    const matrix: DryRunResult['matrix'] = []
    const hks = harnessKeysFrom(cfg)
    let ok = 0
    let est = 0
    for (const task of cfg.tasks) {
      const ti = TASKS.find((t) => t.id === task)
      for (const h of hks) {
        for (const p of cfg.model_profiles) {
          const reason = naReason(h, p)
          matrix.push({ task, harness: h, profile: p.id, status: reason ? 'na' : 'ok', reason })
          if (!reason) {
            ok++
            const m = profileModels(p)
            const per = m.some((x) => x.includes('opus')) ? 1.9 : m.some((x) => x.includes('argon')) ? 1.1 : 0.32
            const tierM = ti?.tier === 'simple' ? 0.45 : ti?.tier === 'medium' ? 1 : 2.4
            est += per * tierM * 1.55 // expected attempts under fresh retries
          }
        }
      }
    }
    const reps = cfg.run.repeats
    return { matrix, estimate: { trials: ok * reps, with_history: ok * reps, usd_total: est * reps, usd_low: est * reps * 0.7, usd_high: est * reps * 1.45, minutes: (ok * reps * 9) / Math.max(1, cfg.concurrency.global), label: 'estimate · historical medians per task × harness × model' } }
  }

  createRun(cfg: RunConfig): string {
    const id = 'r_' + (hashStr(cfg.run.name + now()) >>> 0).toString(36)
    this.seedRun(id, cfg.run.name, cfg, now(), true, 0)
    return id
  }

  action(id: string, act: 'pause' | 'resume' | 'cancel') {
    const r = this.mustRun(id)
    if (act === 'pause') r.detail.status = 'paused'
    if (act === 'resume') r.detail.status = 'running'
    if (act === 'cancel') {
      r.detail.status = 'cancelled'
      r.queue = []
    }
    this.emit(id, { type: 'run', data: { run_id: id, status: r.detail.status, progress: r.detail.progress, spend_usd: r.detail.spend_usd, burn_usd_per_min: r.detail.burn_usd_per_min ?? 0, spend_effective_usd: r.spendEff } })
  }

  subscribe(runId: string, l: Listener): () => void {
    if (!this.listeners.has(runId)) this.listeners.set(runId, new Set())
    this.listeners.get(runId)!.add(l)
    const run = this.runs.get(runId)
    if (run) {
      // replay current state so a late subscriber can hydrate (assumed server behavior)
      queueMicrotask(() => {
        for (const e of run.infra.slice(-600)) l({ type: 'infra', data: e })
        for (const e of run.logs.slice(-60)) l({ type: 'log', data: e })
        for (const aid of run.live.keys()) {
          const a = run.attempts.get(aid)
          if (a) l({ type: 'attempt', data: { ...a } })
        }
        const d = run.detail
        l({ type: 'run', data: { run_id: d.id, status: d.status, progress: d.progress, spend_usd: d.spend_usd, burn_usd_per_min: d.burn_usd_per_min ?? 0, spend_effective_usd: run.spendEff } })
      })
    }
    return () => this.listeners.get(runId)?.delete(l)
  }

  openPty(attemptId: string, cb: (d: string) => void): () => void {
    const f = this.findAttempt(attemptId)
    if (f) {
      const buf = f[0].ptyBuf.get(attemptId)
      if (buf && buf.length) {
        // send screen history first (assumed: server replays current screen on connect)
        const lastClear = buf.lastIndexOf('\x1b[2J\x1b[H')
        cb(buf.slice(Math.max(0, lastClear)).join(''))
      }
    }
    if (!this.ptySubs.has(attemptId)) this.ptySubs.set(attemptId, new Set())
    this.ptySubs.get(attemptId)!.add(cb)
    return () => this.ptySubs.get(attemptId)?.delete(cb)
  }

  taskDetail(id: string) {
    const t = TASKS.find((x) => x.id === id)
    if (!t) return null
    const slug = id.split('/')[1]
    const mod = slug.split('-').slice(0, 2).join('_')
    const ext: Record<string, string> = { python: 'py', node: 'js', go: 'go', rust: 'rs', java: 'java', c: 'c', make: 'mk' }
    const e = ext[t.languages[0]] ?? 'txt'
    const files = [
      'README.md',
      `src/${mod}/__init__.${e}`,
      `src/${mod}/core.${e}`,
      `src/${mod}/models.${e}`,
      `src/${mod}/service.${e}`,
      `src/common/money.${e}`,
      `src/common/log.${e}`,
      `tests/test_${mod}_basic.${e}`,
      `tests/test_${mod}_service.${e}`,
      t.languages[0] === 'python' ? 'pyproject.toml' : t.languages[0] === 'go' ? 'go.mod' : t.languages[0] === 'rust' ? 'Cargo.toml' : 'Makefile',
    ]
    let n = 0
    let passed = 0
    for (const run of this.runs.values())
      for (const tr of run.trials.values())
        if (tr.task_id === id && (tr.status === 'passed' || tr.status === 'failed')) {
          n++
          if (tr.status === 'passed') passed++
        }
    const h = hashStr(id)
    const instruction_md = [
      `# ${t.title}`,
      '',
      `**Component:** \`src/${mod}\` · **Priority:** P${1 + (h % 3)} · **Reporter:** ${t.industry} platform team`,
      '',
      '## Context',
      `Customers reported incorrect behaviour in the ${mod.replace('_', ' ')} flow. The current implementation does not handle the edge cases described below, which causes downstream reconciliation errors.`,
      '',
      '## Acceptance criteria',
      '- Inputs with surrounding whitespace or mixed case are normalised before validation.',
      '- Invalid inputs raise a descriptive `ValueError` instead of returning `False` silently.',
      '- Existing public function signatures stay unchanged.',
      '- All existing tests keep passing.',
      '',
      '## Constraints',
      '- Standard library only; no new dependencies.',
      `- Run the tests with \`${t.languages[0] === 'python' ? 'python3 -m unittest' : 'make test'}\`.`,
      '',
      '```text',
      `$ ${t.languages[0] === 'python' ? 'python3 -m unittest -q' : 'make test'}`,
      'FAILED (failures=2)',
      '```',
    ].join('\n')
    return { ...t, instruction_md, repo_files: files, repo_file_count: files.length, hidden_tests: { fail_to_pass: 2 + (h % 5), pass_to_pass: 6 + (h % 18) }, history: n ? { n, passed } : null }
  }

  runLog(runId: string) {
    return this.mustRun(runId).logs.map((l) => ({ ...l }))
  }

  runInfra(runId: string) {
    return this.mustRun(runId).infra.map((e) => ({ ...e }))
  }

  runEgress(runId: string) {
    const run = this.mustRun(runId)
    const m = new Map<string, { host: string; action: 'forwarded' | 'denied'; n: number }>()
    for (const id of run.attempts.keys()) {
      for (const e of this.attempt(id).events) {
        if (e.type !== 'egress') continue
        const d = e.data as { host: string; action: 'forwarded' | 'denied' }
        const k = d.host + '|' + d.action
        const r = m.get(k) ?? { host: d.host, action: d.action, n: 0 }
        r.n++
        m.set(k, r)
      }
    }
    return [...m.values()]
  }

  governor() {
    const run = [...this.runs.values()].find((r) => r.live_ && r.detail.status === 'running') ?? [...this.runs.values()][0]
    const lanes = new Map<string, { lane: string; limit: number; inflight: number; n429: number; breaker: 'open' | 'closed' }>()
    const t = now()
    for (const e of run.infra) {
      const k = `${e.model}@${e.location}`
      const L = lanes.get(k) ?? { lane: k, limit: 4, inflight: 0, n429: 0, breaker: 'closed' as const }
      if (e.kind === '429' && e.ts > t - 3600) L.n429++
      if (e.kind === 'aimd' && e.detail && typeof e.detail === 'object' && 'limit' in e.detail) L.limit = Number(e.detail.limit)
      if (e.kind === 'breaker_open') L.breaker = 'open'
      if (e.kind === 'breaker_close') L.breaker = 'closed'
      lanes.set(k, L)
    }
    for (const [aid, la] of run.live) {
      if (la.phase === 'backoff') continue
      const c = la.script.calls[Math.min(la.emittedCalls, la.script.calls.length - 1)]
      const L = c && lanes.get(`${c.model}@${c.location}`)
      if (L) L.inflight = Math.min(L.limit, L.inflight + 1)
      void aid
    }
    return [...lanes.values()]
  }

  diff(id: string): string {
    const f = this.findAttempt(id)
    if (!f) throw new Error('attempt not found')
    const [, a] = f
    const slug = (a.task_id ?? 'task/x').split('/')[1].replace(/-/g, '_')
    const file = `src/${slug.split('_').slice(0, 2).join('_')}.py`
    return [
      `diff --git a/${file} b/${file}`,
      `index 3f2a91c..b81e0d4 100644`,
      `--- a/${file}`,
      `+++ b/${file}`,
      `@@ -41,12 +41,17 @@ def normalize(value: str) -> str:`,
      `     """Canonicalize user input before validation."""`,
      `-    return value`,
      `+    if value is None:`,
      `+        raise ValueError("value is required")`,
      `+    return "".join(value.split()).upper()`,
      ` `,
      ` `,
      ` def validate(value: str) -> bool:`,
      `-    v = value`,
      `+    v = normalize(value)`,
      `     if len(v) < 15 or len(v) > 34:`,
      `         return False`,
      `-    return int(_rearrange(v)) % 97 == 0`,
      `+    digits = _rearrange(v)`,
      `+    return int(digits) % 97 == 1`,
      ``,
      `diff --git a/tests/test_${slug}.py b/tests/test_${slug}.py`,
      `--- a/tests/test_${slug}.py`,
      `+++ b/tests/test_${slug}.py`,
      `@@ -88,3 +88,9 @@ class TestValidate(unittest.TestCase):`,
      `         self.assertFalse(validate("GB00 0000"))`,
      `+`,
      `+    def test_lowercase_and_spaces(self):`,
      `+        self.assertTrue(validate("gb82 west 1234 5698 7654 32"))`,
      ``,
    ].join('\n')
  }

  spendHistory(runId: string) {
    return this.runs.get(runId)?.spendHist ?? []
  }
}

function promoFactor(model: string, cat: string): number {
  let f = 1
  for (const p of PROMOTIONS) {
    if (!p.models.includes(model)) continue
    const k = cat === 'thinking' ? 'output' : cat === 'tool_prompt' ? 'input' : cat
    const v = (p.factor as Record<string, number | undefined>)[k]
    if (v != null) f *= v
  }
  return f
}

function RATES_LOOKUP(m: string): Record<string, number> {
  return RATES[m] ?? {}
}

let _engine: Engine | null = null
export function engine(): Engine {
  if (!_engine) {
    _engine = new Engine()
    _engine.start()
  }
  return _engine
}
