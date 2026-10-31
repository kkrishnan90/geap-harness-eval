import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { RunConfig } from '@/lib/types'
import { Link } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Maximize2, Minimize2, ExternalLink, Globe, Lock } from 'lucide-react'
import { useLive } from '@/lib/live'
import { useRun } from '@/lib/run'
import { getMode } from '@/lib/api'
import type { Attempt, CostStatus, ToolCall } from '@/lib/types'
import { fmtClock, fmtPct, fmtUsd, fmtTime } from '@/lib/format'
import { harnessColor, harnessLabel, isDshWeb, MODEL_SHORT } from '@/lib/labels'
import { usePricing } from '@/lib/promos'
import { cn, harnessKey } from '@/lib/utils'
import { wilson } from '@/lib/stats'
import { AttemptPips, CostDot, Kpi, Meter, Money, PromoChip, Spark, StatusPill, ThinkingBadge, TokenBar, TokenLegend, ToolTicker, type TokVec } from '@/components/domain'
import { TrialTape, TapeLegend } from '@/components/TrialTape'
import { LiveTerminal } from '@/components/Terminal'
import { Panel, Segmented, Empty, Chip } from '@/components/ui/misc'
import { Tip } from '@/components/ui/tooltip'
import { Button } from '@/components/ui/button'
import { useNow } from '@/components/Shell'
import { ErrorBoundary } from '@/components/ErrorBoundary'

const ACTIVE = new Set(['admitted', 'preparing', 'running', 'verifying', 'backoff'])
const MaxAttempts = createContext(4)
const WORST: Record<string, number> = { unpriced: 4, pending: 3, check: 2, verified: 1, reconciled: 0, pt: 0 }

export default function MissionControl() {
  const { current, runId } = useRun()
  const runQ = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId!), enabled: !!runId, refetchInterval: 15_000 })
  const cfg = (runQ.data?.config_json ?? null) as RunConfig | null
  const maxAttempts = (cfg?.run?.max_task_retries ?? 3) + 1
  const run = useLive((s) => s.run)
  const attempts = useLive((s) => s.attempts)
  const trialsMap = useLive((s) => s.trials)
  const budget = useLive((s) => s.budget)
  const spend = useLive((s) => s.spend)
  const infra = useLive((s) => s.infra)
  const [filter, setFilter] = useState('all')
  const [focus, setFocus] = useState<string | null>(null)
  const now = useNow(1000) / 1000

  // Keep finished attempts on the wall for a few seconds so the outcome is visible.
  const endedAt = useRef<Record<string, number>>({})
  const wall = useMemo(() => {
    const out: Attempt[] = []
    for (const a of Object.values(attempts)) {
      if (ACTIVE.has(a.status)) {
        delete endedAt.current[a.id]
        out.push(a)
      } else {
        endedAt.current[a.id] ??= now
        if (now - endedAt.current[a.id] < 6) out.push(a)
      }
    }
    return out.sort((x, y) => (x.t_queued ?? 0) - (y.t_queued ?? 0))
  }, [attempts, now])

  const trials = useMemo(() => Object.values(trialsMap), [trialsMap])
  const harnesses = useMemo(() => [...new Set(trials.filter((t) => t.status !== 'na').map((t) => harnessKey(t)))].sort(), [trials])
  const shown = wall.filter((a) => filter === 'all' || harnessKey({ harness: a.harness ?? trialsMap[a.trial_id]?.harness, variant: a.variant ?? trialsMap[a.trial_id]?.variant }) === filter)

  const p = run?.progress
  const passRate = p && p.done ? p.passed / p.done : null
  const ci = p ? wilson(p.passed, p.done) : [0, 0]
  const recent429 = infra.filter((e) => e.kind === '429' && e.ts > now - 600).length
  // burn: server value, else derived from the spend series over the last 10 minutes
  const burn = useMemo(() => {
    if (run?.burn_usd_per_min != null) return run.burn_usd_per_min // server: trailing 10-min spend / 10
    const pts = spend.filter((x) => x[0] > now - 600)
    if (pts.length < 2) return 0
    const [t0, s0] = pts[0]
    const [t1, s1] = pts[pts.length - 1]
    return t1 - t0 > 30 ? Math.max(0, (s1 - s0) / ((t1 - t0) / 60)) : 0
  }, [run?.burn_usd_per_min, spend, now])
  const costShare = useMemo(() => {
    // badge share over trials that have started costing; null status = pending (no priced call yet)
    const counts: Record<string, number> = {}
    let n = 0
    for (const t of trials) {
      if (t.status === 'na' || t.status === 'queued') continue
      const st = t.cost_status ?? 'pending'
      counts[st] = (counts[st] ?? 0) + 1
      n++
    }
    // worst *cost badge*; pending (not priced yet) only counts if nothing is priced
    const badges = Object.keys(counts).filter((st) => st !== 'pending')
    let worst = badges.length ? 'verified' : 'pending'
    for (const st of badges) if ((WORST[st] ?? 2) > (WORST[worst] ?? 0)) worst = st
    const parts = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .map(([st, c]) => `${Math.round((c / Math.max(1, n)) * 100)}% ${st === 'verified' ? 'verified' : st}`)
    return { worst, parts, anyPriced: trials.some((t) => t.cost_usd != null && t.cost_status !== 'unpriced') }
  }, [trials])
  const cap = budget?.cap_usd ?? (cfg?.budget?.enabled ? cfg.budget.max_usd_total : null)
  const capPct = budget?.cap_usd ? budget.pct : cap ? (run?.spend_usd ?? 0) / cap : 0
  const remaining = p ? p.total - p.done : 0
  const perTrial = p && p.done ? (run?.spend_usd ?? 0) / p.done : 0
  const projected = (run?.spend_usd ?? 0) + remaining * perTrial
  const spendSeries = spend.slice(-120).map((x) => x[1])

  const focused = focus ? wall.find((a) => a.id === focus) : null
  const { data: pb } = usePricing()
  const allPromos = pb?.promotions?.map((x) => x.id)

  if (!current) return <Empty title="No run selected" hint="Launch one from the Run Builder." />

  return (
    <div className="flex flex-col gap-4">
      {/* KPI band */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Progress" value={p ? <>{p.done}<span className="text-[14px] text-muted">/{p.total}</span></> : '—'} sub={p ? `${p.running} attempts in flight · ${remaining} trials left` : undefined}>
          <Meter pct={p && p.total ? p.done / p.total : 0} warnAt={2} className="mt-1.5" />
        </Kpi>
        <Kpi
          label="Pass rate"
          value={p && p.done > 0 ? fmtPct(passRate, 1) : <span className="text-muted">—</span>}
          accent={p && p.done > 0 ? 'var(--pass)' : undefined}
          sub={p && p.done > 0 ? `within ${maxAttempts} attempt${maxAttempts > 1 ? 's' : ''} · 95% CI ${fmtPct(ci[0])}–${fmtPct(ci[1])}` : 'no finished trials yet'}
        />
        <Kpi
          label="Spend · effective"
          value={
            <span className="inline-flex items-center gap-1.5 font-mono num">
              <CostDot status={costShare.worst as CostStatus} />
              {costShare.anyPriced || (run?.spend_usd ?? 0) > 0 ? fmtUsd(run?.spend_effective_usd ?? run?.spend_usd) : '—'}
            </span>
          }
          sub={
            <span className="inline-flex items-center gap-1.5">
              {fmtUsd(run?.spend_usd)} list
              {run?.spend_effective_usd != null && run.spend_usd - run.spend_effective_usd > 1e-6 && <PromoChip promos={allPromos} />}
              {costShare.parts.length > 0 && <span className="text-faint">· {costShare.parts.join(' · ')}</span>}
            </span>
          }
        >
          <Spark data={spendSeries} color="var(--cost-verified)" height={22} className="mt-1" />
        </Kpi>
        <Kpi label="Burn rate · list" value={<>{fmtUsd(burn, 'verified', 2)}<span className="text-[13px] text-muted">/min</span></>} sub={<>projected total {fmtUsd(projected)} <span className="text-faint">· estimate</span></>} />
        <Kpi label="429 rate" value={<>{(recent429 / 10).toFixed(1)}<span className="text-[13px] text-muted">/min</span></>} accent={recent429 > 20 ? 'var(--warn)' : undefined} sub={`${recent429} in the last 10 min · AIMD active`} />
        <Kpi
          label="Budget"
          value={cap ? fmtPct(capPct) : <span className="text-muted">Off</span>}
          accent={cap && capPct >= 0.8 ? 'var(--warn)' : undefined}
          sub={cap ? `${fmtUsd(budget?.spent_usd ?? run?.spend_usd)} of ${fmtUsd(cap)} · ${cfg?.budget?.on_exceed ?? 'pause'}s at 100%` : 'No guardrail on this run'}
        >
          {cap ? <Meter pct={capPct} color="var(--cost-verified)" className="mt-1.5" /> : null}
        </Kpi>
      </div>

      {/* The tape */}
      <Panel eyebrow="Trial tape" title={`${current.name} — every trial, one lane per harness × profile`} actions={<TapeLegend />} bodyClass="py-3">
        <TrialTape trials={trials} maxAttempts={maxAttempts} />
      </Panel>

      {/* Wall */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-baseline gap-3">
          <h2 className="text-[13px] font-semibold">Live attempts</h2>
          <span className="font-mono text-[11px] text-muted num">{wall.filter((a) => ACTIVE.has(a.status)).length} in flight</span>
        </div>
        <div className="flex min-w-0 max-w-full flex-wrap items-center gap-3">
          <TokenLegend className="hidden lg:flex" />
          <Segmented size="sm" className="max-w-full overflow-x-auto" value={filter} onChange={setFilter} options={[{ value: 'all', label: 'All' }, ...harnesses.map((h) => ({ value: h, label: harnessLabel(h.split('/')[0], h.split('/')[1]) }))]} />
        </div>
      </div>

      {shown.length === 0 ? (
        <div className="panel">
          <Empty title={run?.status === 'running' ? 'Waiting for the scheduler to admit attempts…' : `This run is ${run?.status ?? current.status}`} hint={run?.status === 'running' ? undefined : 'Pick a running run from the selector, or open a finished trial in the Trial Inspector.'} />
        </div>
      ) : (
        <MaxAttempts.Provider value={maxAttempts}>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2 2xl:grid-cols-3">
          <AnimatePresence initial={false}>
            {shown.map((a) => (
              <motion.div key={a.id} layout="position" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.98 }} transition={{ duration: 0.25 }}>
                <ErrorBoundary compact label={`Attempt ${a.id}`}>
                  <AttemptCard a={a} onFocus={() => setFocus(a.id)} />
                </ErrorBoundary>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
        </MaxAttempts.Provider>
      )}

      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[1fr_380px]">
        <EventLog />
        <InfraFeed />
      </div>

      <AnimatePresence>
        {focused && (
          <motion.div className="fixed inset-0 z-40 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm md:p-10" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setFocus(null)}>
            <motion.div className="h-full max-h-[860px] w-full max-w-[1400px]" initial={{ scale: 0.97 }} animate={{ scale: 1 }} onClick={(e) => e.stopPropagation()}>
              <AttemptCard a={focused} big onFocus={() => setFocus(null)} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function AttemptCard({ a, big, onFocus }: { a: Attempt; big?: boolean; onFocus: () => void }) {
  const maxA = useContext(MaxAttempts)
  const tick = useLive((s) => s.ticks[a.id])
  const tools = useLive((s) => s.tools[a.id]) ?? []
  const trial = useLive((s) => s.trials[a.trial_id])
  const harness = a.harness ?? trial?.harness ?? '?'
  const variant = a.variant ?? trial?.variant ?? 'default'
  const profile = (trial?.profile_json ?? null) as { roles?: Record<string, { model: string; thinking: string }> } | null
  const roles = profile?.roles ? Object.entries(profile.roles) : []
  const hk = harnessKey({ harness, variant })
  const color = harnessColor(hk)
  const tok: TokVec = tick
    ? { input: tick.tokens.input, cache_read: tick.tokens.cache_read, cache_write: tick.tokens.cache_write, output: tick.tokens.output, thinking: tick.tokens.thinking }
    : { input: a.tok_input, cache_read: a.tok_cache_read, cache_write: a.tok_cache_write_5m + a.tok_cache_write_1h, output: a.tok_output, thinking: a.tok_thinking }
  const counts = tick?.tool ?? { ok: a.tool_ok, fail: a.tool_fail, retry: a.tool_retry }
  const cost = tick ? tick.cost_usd : a.cost_usd
  const costEff = tick && tick.cost_effective_usd !== undefined ? tick.cost_effective_usd : a.cost_effective_usd
  const cstatus = (tick?.cost_status ?? a.cost_status) as CostStatus
  const state = a.status
  const backoff = state === 'backoff' ? tick?.backoff_remaining_s : undefined
  const isDsh = isDshWeb(harness, variant)
  const done = state === 'passed' || state === 'failed'

  return (
    <article
      className={cn('panel group flex flex-col overflow-hidden', big ? 'h-full' : '', done && (state === 'passed' ? 'ring-1 ring-[color-mix(in_oklab,var(--pass)_45%,transparent)]' : 'ring-1 ring-[color-mix(in_oklab,var(--fail)_45%,transparent)]'))}
    >
      <header className="flex items-center gap-2.5 border-b border-line px-3 py-2">
        <span className="h-6 w-[3px] shrink-0 rounded-full" style={{ background: color }} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="whitespace-nowrap text-[12.5px] font-semibold">{harnessLabel(harness, variant)}</span>
            <span className="truncate font-mono text-[11px] text-muted">{a.task_id ?? trial?.task_id}</span>
          </div>
          <div className="flex items-center gap-1.5 truncate font-mono text-[10.5px] text-muted">
            <span className="text-fg-2">{a.profile_id ?? trial?.profile_id}</span>
            {roles.map(([r, s]) => (
              <span key={r} className="truncate">
                · {roles.length > 1 ? `${r}:` : ''}
                {MODEL_SHORT[s.model] ?? s.model}/{s.thinking}
              </span>
            ))}
          </div>
        </div>
        {a.thinking_verified && <span className="hidden xl:inline-flex"><ThinkingBadge verified={a.thinking_verified} /></span>}
        <AttemptPips idx={a.idx} max={Math.max(maxA, a.idx)} status={state} />
        <StatusPill status={state} />
        <Tip content={big ? 'Close' : 'Expand terminal'}>
          <Button size="icon-sm" variant="ghost" onClick={onFocus} aria-label={big ? 'Close' : 'Expand'}>
            {big ? <Minimize2 /> : <Maximize2 />}
          </Button>
        </Tip>
      </header>
      <div className={cn('relative', big ? 'min-h-0 flex-1' : 'h-[232px]')}>
        <LiveTerminal attemptId={a.id} fallback={isDsh && getMode() === 'mock' ? <DshScreencast a={a} tools={tools} variant={variant} /> : undefined} />
        {state === 'backoff' && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-center gap-2 bg-gradient-to-t from-black/80 to-transparent px-3 pb-2 pt-6 font-mono text-[11px] text-[#f5b83d]">
            <span className="tape-running">●</span> 429 RESOURCE_EXHAUSTED — retrying in {backoff != null ? `${backoff.toFixed(0)}s` : '…'} (does not consume a task retry)
          </div>
        )}
      </div>
      <footer className="grid grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 border-t border-line px-3 py-2.5">
        <TokenBar t={tok} showTotal />
        <div className="flex items-center gap-3">
          <Money usd={cost} effective={costEff} status={cstatus} compact className="text-[12px]" />
          <span className={cn('w-[52px] text-right font-mono text-[12px] num', state === 'backoff' ? 'text-warn' : 'text-fg-2')}>
            {state === 'backoff' && backoff != null ? `−${fmtClock(backoff)}` : fmtClock(tick?.elapsed_s ?? (a.wall_s ?? 0))}
          </span>
        </div>
        <ToolTicker tools={tools} counts={counts} />
        <Link to={`/inspect/${a.trial_id}/${a.id}`} className="flex items-center justify-end gap-1 text-[11px] text-muted hover:text-fg">
          Inspect <ExternalLink className="size-3" />
        </Link>
      </footer>
    </article>
  )
}

/** Mock stand-in for the dsh web screencast (real mode receives JPEG frames over the PTY socket). */
function DshScreencast({ a, tools, variant }: { a: Attempt; tools: ToolCall[]; variant: string }) {
  const trial = useLive((s) => s.trials[a.trial_id])
  const ptc = !String(variant).includes('native')
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (el) el.scrollTop = el.scrollHeight
  }, [tools.length])
  return (
    <div className="flex h-full flex-col bg-[#f6f7f9] text-[#1b1d22]">
      <div className="flex h-7 shrink-0 items-center gap-2 border-b border-[#e3e5ea] bg-[#eceef2] px-2">
        <span className="flex gap-1">
          <span className="size-2 rounded-full bg-[#f0585e]" />
          <span className="size-2 rounded-full bg-[#f5b83d]" />
          <span className="size-2 rounded-full bg-[#3ccf8e]" />
        </span>
        <span className="flex h-[18px] flex-1 items-center gap-1 rounded bg-white px-2 font-mono text-[10px] text-[#646b77]">
          <Lock className="size-2.5" /> 127.0.0.1:41{a.id.charCodeAt(a.id.length - 1) % 90 + 10}/chat
        </span>
        <span className="flex items-center gap-1 font-mono text-[9.5px] text-[#646b77]">
          <Globe className="size-2.5" /> CDP screencast
        </span>
      </div>
      <div ref={box} className="min-h-0 flex-1 space-y-2 overflow-y-auto p-3 text-[11px]">
        <div className="ml-auto max-w-[80%] rounded-lg rounded-br-sm bg-[#5b4bf0] px-2.5 py-1.5 text-white">{trial?.task_id ? `Ticket: ${trial.task_id}` : 'Ticket'}</div>
        {tools.slice(-6).map((t) => (
          <div key={t.id} className="rounded-md border border-[#e3e5ea] bg-white">
            <div className="flex items-center justify-between border-b border-[#eef0f3] px-2 py-1 font-mono text-[10px] text-[#646b77]">
              <span>{ptc ? 'run_code · TypeScript' : t.name}</span>
              <span style={{ color: t.status === 'ok' ? '#13a26b' : '#d93a42' }}>{t.status === 'ok' ? '✓ ok' : `✗ ${t.error_code ?? 'error'}`}</span>
            </div>
            {ptc && (
              <pre className="overflow-hidden px-2 py-1 font-mono text-[10px] leading-relaxed text-[#3b414b]">
                {`const src = await tools.read({ path: "src/…" })\nawait tools.edit({ path, patch })\nconst r = await tools.bash({ cmd: "test" })`}
              </pre>
            )}
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-[10px] text-[#646b77]">
          <span className="tape-running">●</span> dsh is working · {fmtTime(Date.now() / 1000)}
        </div>
      </div>
    </div>
  )
}

function EventLog() {
  const live = useLive((s) => s.logs)
  const trialsMap = useLive((s) => s.trials)
  const logSource = useLive((s) => s.logSource)
  // runs that are not live have no stream history: synthesize lines from persisted trial outcomes
  const backfill = useMemo(() => {
    if (live.length || logSource !== 'unavailable') return []
    return Object.values(trialsMap)
      .filter((t) => ['passed', 'failed', 'infra_failed', 'invalid_routing'].includes(t.status))
      .sort((a, b) => a.updated_at - b.updated_at)
      .map((t) => ({
        ts: t.updated_at,
        level: (t.status === 'passed' ? 'info' : 'warn') as 'info' | 'warn',
        msg: `${t.task_id} · ${harnessLabel(t.harness, t.variant)} · ${t.profile_id} → ${t.status === 'passed' ? `passed on attempt ${t.passed_on_attempt ?? '?'}` : `${t.status.replace('_', ' ')} after ${t.attempts_used} attempt${t.attempts_used === 1 ? '' : 's'}`}`,
      }))
  }, [live.length, trialsMap, logSource])
  const logs = live.length ? live : backfill
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.scrollTo({ top: ref.current.scrollHeight })
  }, [logs.length])
  return (
    <Panel eyebrow={backfill.length && !live.length ? 'Scheduler · from persisted trials' : 'Scheduler'} title="Event log" bodyClass="p-0">
      <div ref={ref} className="h-[220px] overflow-y-auto px-4 py-2 font-mono text-[11px] leading-[1.7]">
        {logs.length === 0 && <div className="py-8 text-center font-sans text-muted">Events appear here as attempts start, retry and finish.</div>}
        {logs.map((l, i) => (
          <div key={i} className="flex gap-3">
            <span className="shrink-0 text-faint num">{fmtTime(l.ts)}</span>
            <span className={cn('w-10 shrink-0 uppercase', l.level === 'warn' ? 'text-warn' : l.level === 'error' ? 'text-fail' : 'text-muted')}>{l.level}</span>
            <span className="text-fg-2">{l.msg}</span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function InfraFeed() {
  const infra = useLive((s) => s.infra)
  const items = infra.slice(-40).reverse()
  const breakers = useMemo(() => {
    const m = new Map<string, boolean>()
    for (const e of infra) {
      if (e.kind === 'breaker_open') m.set(e.model, true)
      if (e.kind === 'breaker_close') m.set(e.model, false)
    }
    return m
  }, [infra])
  return (
    <Panel
      eyebrow="Rate governor"
      title="Infra signals"
      bodyClass="p-0"
      actions={
        <Link to="/quota" className="text-[11px] text-muted hover:text-fg">
          Quota & Health →
        </Link>
      }
    >
      <div className="flex flex-wrap gap-1.5 border-b border-line px-4 py-2">
        {[...breakers.entries()].map(([m, open]) => (
          <Chip key={m} tone={open ? 'fail' : 'default'}>
            {MODEL_SHORT[m] ?? m} · breaker {open ? 'open' : 'closed'}
          </Chip>
        ))}
        {breakers.size === 0 && <span className="text-[11px] text-muted">All breakers closed</span>}
      </div>
      <div className="h-[178px] overflow-y-auto px-4 py-1.5 font-mono text-[11px] leading-[1.7]">
        {items.map((e, i) => (
          <div key={i} className="flex gap-2">
            <span className="shrink-0 text-faint num">{fmtTime(e.ts)}</span>
            <span className={cn('w-[86px] shrink-0', e.kind === '429' ? 'text-warn' : e.kind === 'breaker_open' ? 'text-fail' : e.kind === 'breaker_close' ? 'text-pass' : 'text-muted')}>{e.kind}</span>
            <span className="truncate text-fg-2">
              {MODEL_SHORT[e.model] ?? e.model}@{e.location}
              {e.detail && typeof e.detail === 'object' && 'limit' in e.detail ? ` → limit ${String(e.detail.limit)}` : ''}
              {e.detail && typeof e.detail === 'object' && 'wait_s' in e.detail ? ` · wait ${String(e.detail.wait_s)}s` : ''}
            </span>
          </div>
        ))}
      </div>
    </Panel>
  )
}

