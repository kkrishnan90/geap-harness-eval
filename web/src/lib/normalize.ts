// Boundary adapters: accept every shape the engine has been seen to emit and
// produce the shapes the views expect. All functions are idempotent and total.
import type {
  DryRunCell,
  DryRunResult,
  Attempt,
  AttemptDetail,
  GroupSummary,
  LlmCall,
  PricingBook,
  Progress,
  RunAggregate,
  RunDetail,
  RunEvt,
  RunSummaryRow,
  ToolCall,
  Trial,
  TrialDetail,
} from './types'

type Any = Record<string, unknown>
const num = (v: unknown): number | null => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Number(v))
const bool = (v: unknown): boolean | null => (v == null ? null : v === true || v === 1 || v === '1' || v === 'true')

function parseJson<T>(v: unknown): T | undefined {
  if (v == null) return undefined
  if (typeof v === 'string') {
    try {
      return JSON.parse(v) as T
    } catch {
      return undefined
    }
  }
  return v as T
}

const DONE_FAIL = ['failed', 'infra_failed', 'invalid_routing']

export function progressFromCounts(counts: Any | undefined | null): Progress {
  const c = (k: string) => Number(counts?.[k] ?? 0)
  const passed = c('passed')
  const failed = DONE_FAIL.reduce((s, k) => s + c(k), 0)
  const all = Object.entries(counts ?? {}).reduce((s, [k, v]) => (k === 'na' ? s : s + Number(v ?? 0)), 0)
  return { total: all, done: passed + failed, running: c('running'), passed, failed }
}

export function normRunRow<T extends RunSummaryRow | RunDetail>(r: T & Any): T {
  const progress = (r.progress as Progress | undefined) ?? (r.counts ? progressFromCounts(r.counts as Any) : undefined)
  const cfg = r.config_json ?? r.config
  return { ...r, progress, config_json: parseJson(cfg), spend_usd: num(r.spend_usd) ?? 0 } as T
}

export function normRunEvt(e: RunEvt & Any): RunEvt {
  return {
    ...e,
    progress: e.progress ?? progressFromCounts(e.counts as Any),
    spend_usd: num(e.spend_usd) ?? 0,
    burn_usd_per_min: num(e.burn_usd_per_min),
    spend_effective_usd: num(e.spend_effective_usd) ?? undefined,
  }
}

export function normTrial<T extends Trial>(t: T & Any): T {
  return { ...t, profile_json: parseJson(t.profile_json), variant: (t.variant as string) ?? 'default' } as T
}

export function normAttempt<T extends Attempt | AttemptDetail>(a: T & Any): T {
  return { ...a, passed: bool(a.passed) } as T
}

export function normLlmCall(c: LlmCall & Any): LlmCall {
  const role = (c.role as string | undefined) ?? (c.hint_aux ? 'aux' : 'default')
  return { ...c, id: String(c.id ?? `${c.attempt_id}-${c.seq}`), role, is_retry: !!bool(c.is_retry), stream: !!bool(c.stream) }
}

export function normToolCall(t: ToolCall & Any): ToolCall {
  return { ...t, id: String(t.id ?? t.call_id), is_retry: !!bool(t.is_retry) }
}

export function normAttemptDetail(d: AttemptDetail & Any): AttemptDetail {
  return {
    ...normAttempt(d),
    llm_calls: ((d.llm_calls as LlmCall[] | undefined) ?? []).map((c) => normLlmCall(c as LlmCall & Any)),
    tool_calls: ((d.tool_calls as ToolCall[] | undefined) ?? []).map((t) => normToolCall(t as ToolCall & Any)),
    events: ((d.events as AttemptDetail['events'] | undefined) ?? []).map((e) => ({ ...e, id: String(e.id), data: (parseJson(e.data) ?? {}) as Record<string, unknown> })),
  }
}

export function normTrialDetail(t: TrialDetail & Any): TrialDetail {
  return { ...normTrial(t), attempts: ((t.attempts as Attempt[] | undefined) ?? []).map((a) => normAttempt(a as Attempt & Any)) }
}

function normTokens(t: Any | undefined): GroupSummary['tokens'] {
  const g = (a: string, b: string) => num(t?.[a]) ?? num(t?.[b]) ?? 0
  return {
    input: g('input', 'tok_input'),
    cache_read: g('cache_read', 'tok_cache_read'),
    cache_write: num(t?.cache_write) ?? g('cache_write_5m', 'tok_cache_write_5m') + g('cache_write_1h', 'tok_cache_write_1h'),
    output: g('output', 'tok_output'),
    thinking: g('thinking', 'tok_thinking'),
    tool_prompt: g('tool_prompt', 'tok_tool_prompt'),
  }
}

const ci = (v: unknown): [number, number] | null => (Array.isArray(v) && v.length === 2 && v.every((x) => x != null) ? [Number(v[0]), Number(v[1])] : null)

export function normSummary(s: RunAggregate & Any): RunAggregate {
  const flatTools = Array.isArray(s.tools_by_name) ? (s.tools_by_name as Any[]) : []
  const groups = ((s.groups as unknown as Any[] | undefined) ?? []).map((g) => {
    const gTools = (g.tools_by_name as GroupSummary['tools_by_name']) ?? aggregateFlatTools(flatTools.filter((x) => x.harness === g.harness && (x.variant == null || x.variant === g.variant) && !x.nested))
    const p1 = num(g.pass_at_1) ?? 0
    return {
      ...g,
      variant: (g.variant as string) ?? 'default',
      n: num(g.n) ?? 0,
      pass_at_1: p1,
      pass_at_1_ci: ci(g.pass_at_1_ci),
      pass_k: num(g.pass_k),
      solved_within_retries: num(g.solved_within_retries),
      attempt_survival: Array.isArray(g.attempt_survival) ? (g.attempt_survival as unknown[]).map((x) => Number(x)) : undefined,
      pass_hat_k: num(g.pass_hat_k),
      cost_mean: num(g.cost_mean),
      cost_ci: ci(g.cost_ci),
      time_mean: num(g.time_mean) ?? 0,
      time_ci: ci(g.time_ci),
      tool_calls_mean: num(g.tool_calls_mean) ?? 0,
      tool_fail_rate: num(g.tool_fail_rate) ?? 0,
      cache_hit_ratio: num(g.cache_hit_ratio) ?? 0,
      tokens: normTokens(g.tokens as Any),
      tools_by_name: gTools,
    } as unknown as GroupSummary
  })
  const sp = s.spend as Any | undefined
  let spend: RunAggregate['spend'] = undefined
  if (sp) {
    const bmc = sp.by_model_category
    const rows: NonNullable<RunAggregate['spend']>['by_model_category'] = Array.isArray(bmc)
      ? (bmc as NonNullable<RunAggregate['spend']>['by_model_category'])
      : Object.entries((bmc as Record<string, Record<string, unknown>>) ?? {}).flatMap(([model, cats]) =>
          Object.entries(cats ?? {}).map(([category, v]) => {
            const o = typeof v === 'object' && v ? (v as Any) : { usd: v }
            const cat = category === 'cache_write_5m' || category === 'cache_write_1h' ? 'cache_write' : category === 'tool_use_prompt' ? 'tool_prompt' : category
            return { model, category: cat, usd: num(o.usd) ?? 0, usd_effective: num(o.usd_effective) ?? undefined, tokens: num(o.tokens) ?? 0 }
          }),
        )
    // merge duplicate (model, category) after cache_write folding
    const merged = new Map<string, (typeof rows)[number]>()
    for (const r of rows) {
      const k = r.model + '|' + r.category
      const m = merged.get(k)
      if (m) {
        m.usd += r.usd
        m.tokens += r.tokens
        if (r.usd_effective != null) m.usd_effective = (m.usd_effective ?? 0) + r.usd_effective
      } else merged.set(k, { ...r })
    }
    const failed = num(sp.failed_attempts_usd)
    const infra = num(sp.infra_failures_usd) ?? num(sp.infra_usd)
    const retried = num(sp.retried_llm_usd) ?? num(sp.retried_calls_usd)
    spend = {
      ...(sp as object),
      total_usd: num(sp.total_usd) ?? 0,
      total_effective_usd: num(sp.total_effective_usd) ?? undefined,
      by_model_category: [...merged.values()],
      cache_savings_usd: num(sp.cache_savings_usd) as number,
      waste_usd: num(sp.waste_usd) ?? (failed != null ? failed + (infra ?? 0) : (null as unknown as number)),
      waste_breakdown: (sp.waste_breakdown as NonNullable<RunAggregate['spend']>['waste_breakdown']) ?? (failed != null ? { failed_attempts_usd: failed, retried_calls_usd: retried, infra_usd: infra, partial: infra == null } : undefined),
      badge_share: (sp.badge_share as NonNullable<RunAggregate['spend']>['badge_share']) ?? (s.cost_status_share as NonNullable<RunAggregate['spend']>['badge_share']) ?? {},
    }
  }
  return { ...s, k: num(s.k) ?? undefined, max_attempts: num(s.max_attempts) ?? undefined, groups, by_tier: (s.by_tier as RunAggregate['by_tier']) ?? [], by_industry: (s.by_industry as RunAggregate['by_industry']) ?? [], spend }
}

function aggregateFlatTools(rows: Any[]): GroupSummary['tools_by_name'] {
  if (!rows.length) return undefined
  const m = new Map<string, { name: string; ok: number; fail: number; retry: number; denied: number }>()
  for (const r of rows) {
    const name = String(r.name)
    const e = m.get(name) ?? { name, ok: 0, fail: 0, retry: 0, denied: 0 }
    const n = num(r.n) ?? 1
    if (r.status === 'ok') e.ok += n
    else if (r.status === 'denied') e.denied += n
    else if (r.status === 'retry') e.retry += n
    else e.fail += n
    m.set(name, e)
  }
  return [...m.values()]
}

export function normPricing(p: PricingBook & Any): PricingBook {
  return {
    ...p,
    models: ((p.models as Any[] | undefined) ?? []).map((m) => ({ model: String(m.model), location: String(m.location ?? 'global'), rates: ((m.rates ?? m.rates_per_1m ?? {}) as Record<string, number>) })),
    issues: (p.issues as string[]) ?? [],
    promotions: ((p.promotions as Any[] | undefined) ?? []).map((x) => ({ ...x, models: (x.models as string[]) ?? [], locality: Array.isArray(x.locality) ? (x.locality as string[]).join(' · ') : String(x.locality ?? '') })) as PricingBook['promotions'],
  }
}

/** Dry-run: collapse per-repeat rows, strip "/default" variants, map estimate field names. */
export function normDryRun(d: DryRunResult & Any): DryRunResult {
  const seen = new Set<string>()
  const matrix: DryRunCell[] = []
  for (const c of (d.matrix as (DryRunCell & Any)[] | undefined) ?? []) {
    const harness = String(c.harness).replace(/\/default$/, '')
    const k = `${c.task}|${harness}|${c.profile}`
    if (seen.has(k)) continue
    seen.add(k)
    matrix.push({ task: String(c.task), harness, profile: String(c.profile), status: c.status === 'ok' ? 'ok' : 'na', reason: (c.reason as string) ?? null })
  }
  const e = d.estimate as Any | number | null
  const estimate =
    e && typeof e === 'object'
      ? { ...e, usd_total: num(e.usd_total) ?? num(e.cost_usd_estimate), label: (e.label as string) ?? (e.note as string) ?? undefined, trials: num(e.trials) ?? undefined }
      : e
  return { ...d, matrix, estimate: estimate as DryRunResult['estimate'] }
}
