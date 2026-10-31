import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from '@tanstack/react-table'
import { Pause, Play, RotateCcw, Search, ArrowDown, ArrowUp, FileDown } from 'lucide-react'
import { api } from '@/lib/api'
import { useMaxAttempts, useRun } from '@/lib/run'
import type { Attempt, AttemptDetail, LlmCall, ToolCall, Trial } from '@/lib/types'
import { harnessColor, harnessLabel, isDshWeb, MODEL_SHORT } from '@/lib/labels'
import { cn, harnessKey } from '@/lib/utils'
import { fmtClock, fmtDur, fmtInt, fmtTok, fmtUsd, thinkingLabel } from '@/lib/format'
import { AttemptPips, Money, StatusPill, ThinkingBadge, TokenBar, TokenLegend, statusColor, statusLabel } from '@/components/domain'
import { XtermView, type TermHandle } from '@/components/Terminal'
import { Panel, Segmented, Input, Empty, Skeleton, Chip } from '@/components/ui/misc'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import { useLive } from '@/lib/live'

export default function TrialInspector() {
  const { trialId, attemptId } = useParams()
  const { runId, current } = useRun()
  const nav = useNavigate()
  const trialsQ = useQuery({ queryKey: ['trials', runId], queryFn: () => api.trials(runId!), enabled: !!runId, refetchInterval: current?.status === 'running' ? 10_000 : false })
  const trials = trialsQ.data ?? []
  const firstDone = trials.find((t) => t.status === 'failed' && t.attempts_used > 1) ?? trials.find((t) => t.status === 'passed')
  const tid = trialId ?? firstDone?.id

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[340px_minmax(0,1fr)]">
      <TrialList trials={trials} loading={trialsQ.isLoading} selected={tid} onSelect={(id) => nav(`/inspect/${id}`)} />
      {tid ? <TrialDetailView trialId={tid} attemptId={attemptId} /> : <div className="panel"><Empty title="Select a trial" hint="Pick a finished or running trial on the left." /></div>}
    </div>
  )
}

function TrialList({ trials, loading, selected, onSelect }: { trials: Trial[]; loading: boolean; selected?: string; onSelect: (id: string) => void }) {
  const [q, setQ] = useState('')
  const [st, setSt] = useState<'all' | 'passed' | 'failed' | 'running'>('all')
  const rows = trials.filter((t) => t.status !== 'na' && t.status !== 'queued' && (st === 'all' || t.status === st) && (!q || q.toLowerCase().split(/\s+/).filter(Boolean).every((tok) => `${t.task_id} ${t.harness} ${t.variant} ${t.profile_id} ${harnessLabel(t.harness, t.variant)}`.toLowerCase().includes(tok))))
  return (
    <section className="panel flex max-h-[calc(100vh-96px)] min-h-[420px] flex-col xl:sticky xl:top-[72px]">
      <div className="space-y-2 border-b border-line p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by task, harness, profile" className="w-full pl-8" aria-label="Filter trials" />
        </div>
        <Segmented size="sm" value={st} onChange={setSt} className="w-full [&>button]:flex-1" options={[{ value: 'all', label: 'All' }, { value: 'passed', label: 'Passed' }, { value: 'failed', label: 'Failed' }, { value: 'running', label: 'Running' }]} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && <Skeleton className="m-3 h-40" />}
        {rows.slice(0, 400).map((t) => {
          const hk = harnessKey(t)
          return (
            <button
              key={t.id}
              data-trial-item
              onClick={() => onSelect(t.id)}
              className={cn('flex w-full items-center gap-2.5 border-b border-line/50 px-3 py-2 text-left transition-colors hover:bg-hover', selected === t.id && 'bg-accent-soft hover:bg-accent-soft')}
            >
              <span className="h-7 w-[3px] shrink-0 rounded-full" style={{ background: harnessColor(hk === 'dsh' ? 'dsh/ptc' : hk) }} />
              <div className="min-w-0 flex-1">
                <div className="truncate text-[12px] font-medium">{t.task_id.split('/')[1]}</div>
                <div className="truncate font-mono text-[10.5px] text-muted">
                  {harnessLabel(t.harness, t.variant === 'default' ? undefined : t.variant)} · {t.profile_id} · r{t.repeat_idx + 1}
                </div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1">
                <span className="flex gap-[2px]">
                  {Array.from({ length: t.attempts_used }, (_, i) => (
                    <span key={i} className="h-2 w-1.5 rounded-[1px]" style={{ background: i === t.attempts_used - 1 ? statusColor(t.status) : 'var(--fail)', opacity: i === t.attempts_used - 1 ? 1 : 0.5 }} />
                  ))}
                </span>
                <span className="font-mono text-[10.5px] text-muted num">{fmtUsd(t.cost_effective_usd ?? t.cost_usd, t.cost_status)}</span>
              </div>
            </button>
          )
        })}
        {!loading && rows.length === 0 && <Empty title="No trials match" />}
      </div>
      <div className="border-t border-line px-3 py-1.5 font-mono text-[10.5px] text-muted">{rows.length} trials</div>
    </section>
  )
}

function TrialDetailView({ trialId, attemptId }: { trialId: string; attemptId?: string }) {
  const nav = useNavigate()
  const liveVersion = useLive((s) => (s.trials[trialId]?.updated_at ?? 0) + (s.trials[trialId]?.attempts_used ?? 0))
  const tq = useQuery({ queryKey: ['trial', trialId, liveVersion], queryFn: () => api.trial(trialId), placeholderData: (p) => p })
  const t = tq.data
  const aid = attemptId ?? t?.attempts[t.attempts.length - 1]?.id
  if (!t) return <Skeleton className="h-[600px]" />
  const hk = harnessKey(t)
  const prof = t.profile_json as { roles?: Record<string, { model: string; thinking: string }>; stages?: { role: string; model: string; thinking?: string }[] } | undefined
  const roles = prof?.roles ? Object.entries(prof.roles).map(([r, s]) => `${r}: ${MODEL_SHORT[s.model] ?? s.model}/${s.thinking}`) : (prof?.stages ?? []).map((s) => `${s.role}: ${MODEL_SHORT[s.model] ?? s.model}`)
  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="panel flex flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3">
        <div className="flex min-w-0 items-center gap-3">
          <span className="h-9 w-1 rounded-full" style={{ background: harnessColor(hk === 'dsh' ? 'dsh/ptc' : hk) }} />
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold tracking-[-0.01em]">{t.task_id}</div>
            <div className="truncate font-mono text-[11px] text-muted">
              {harnessLabel(t.harness, t.variant === 'default' ? undefined : t.variant)} {t.harness_version} · {t.profile_id} · {roles.join(' · ')} · repeat {t.repeat_idx + 1}
            </div>
          </div>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-5">
          <Stat label="Outcome">
            <StatusPill status={t.status} />
          </Stat>
          <Stat label="Passed on">{t.passed_on_attempt ? `attempt ${t.passed_on_attempt}` : '—'}</Stat>
          <Stat label="Time to success">{fmtDur(t.time_to_success_s)}</Stat>
          <Stat label="Infra retries">{t.infra_retries ?? 0}</Stat>
          <Stat label="Trial cost">
            <Money usd={t.cost_usd} effective={t.cost_effective_usd} status={t.cost_status} />
          </Stat>
          <Chip>{t.tier}</Chip>
          <Chip>{t.sdlc_type}</Chip>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <span className="eyebrow mr-1">Attempts</span>
        {t.attempts.map((a) => (
          <button
            key={a.id}
            onClick={() => nav(`/inspect/${t.id}/${a.id}`)}
            className={cn('flex h-8 items-center gap-2 rounded-md border px-3 text-[12px] transition-colors', a.id === aid ? 'border-accent-line bg-accent-soft text-fg' : 'border-line bg-raised text-fg-2 hover:border-line-strong')}
          >
            <span className="size-1.5 rounded-full" style={{ background: isInfraRetry(a) ? 'var(--warn)' : statusColor(a.status) }} />
            Attempt {a.idx}
            <span className={cn('font-mono text-[10.5px]', isInfraRetry(a) ? 'text-warn' : 'text-muted')}>{isInfraRetry(a) ? 'infra retry' : statusLabel(a.status)}</span>
          </button>
        ))}
      </div>
      {aid && <AttemptView key={aid} attemptId={aid} webDriven={isDshWeb(t.harness, t.variant)} />}
    </div>
  )
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div className="mt-0.5 font-mono text-[13px] num">{children}</div>
    </div>
  )
}

// ---------------- attempt ----------------
interface Cast {
  width: number
  height: number
  start: number
  events: [number, string][]
  duration: number
}

function parseCast(text: string): Cast {
  const lines = text.split('\n').filter(Boolean)
  const head = JSON.parse(lines[0] ?? '{}') as { timestamp?: number; width?: number; height?: number; term?: { cols?: number; rows?: number } }
  const events: [number, string][] = []
  for (const l of lines.slice(1)) {
    try {
      const [t, k, d] = JSON.parse(l) as [number, string, string]
      if (k === 'o') events.push([t, d])
    } catch {
      /* skip */
    }
  }
  return { width: head.width ?? head.term?.cols ?? 220, height: head.height ?? head.term?.rows ?? 60, start: head.timestamp ?? 0, events, duration: events.length ? events[events.length - 1][0] : 0 }
}

function AttemptView({ attemptId, webDriven }: { attemptId: string; webDriven?: boolean }) {
  const aq = useQuery({ queryKey: ['attempt', attemptId], queryFn: () => api.attempt(attemptId) })
  // dsh web attempts are driven through the browser: there is no terminal cast to fetch
  const cq = useQuery({ queryKey: ['cast', attemptId], queryFn: () => api.cast(attemptId), retry: 0, enabled: !webDriven })
  const a = aq.data
  const cast = useMemo(() => (cq.data ? parseCast(cq.data) : null), [cq.data])
  if (!a) return <Skeleton className="h-[520px]" />
  return (
    <>
      {a.status === 'engine_error' && (
        <div className="panel flex items-center gap-3 border-dashed px-4 py-3 text-[12px]">
          <StatusPill status="engine_error" />
          <span className="text-fg-2">Engine-side failure; not counted against the agent and does not consume a task retry.</span>
          {a.error && <span className="truncate font-mono text-[11px] text-muted">{a.error}</span>}
        </div>
      )}
      <AttemptStats a={a} />
      <Replay a={a} cast={cast} castError={cq.isError} webDriven={webDriven} />
      <Tabs defaultValue="llm" className="flex flex-col gap-3">
        <TabsList className="self-start">
          <TabsTrigger value="llm">LLM calls · {a.llm_calls.length}</TabsTrigger>
          <TabsTrigger value="tools">Tool calls · {a.tool_calls.filter((t) => !t.parent_id).length}</TabsTrigger>
          <TabsTrigger value="verify">Verifier</TabsTrigger>
          <TabsTrigger value="diff">Diff</TabsTrigger>
          <TabsTrigger value="events">Events · {a.events.length}</TabsTrigger>
        </TabsList>
        <TabsContent value="llm">
          <LlmTable calls={a.llm_calls} />
        </TabsContent>
        <TabsContent value="tools">
          <ToolTable tools={a.tool_calls} t0={attemptT0(a)} />
        </TabsContent>
        <TabsContent value="verify">
          <Verifier a={a} />
        </TabsContent>
        <TabsContent value="diff">
          <DiffView attemptId={a.id} />
        </TabsContent>
        <TabsContent value="events">
          <EventsTable a={a} />
        </TabsContent>
      </Tabs>
    </>
  )
}

function AttemptStats({ a }: { a: AttemptDetail }) {
  const maxA = useMaxAttempts()
  const tok = { input: a.tok_input, cache_read: a.tok_cache_read, cache_write: a.tok_cache_write_5m + a.tok_cache_write_1h, output: a.tok_output, thinking: a.tok_thinking }
  const wall = a.wall_s ?? 0
  const split = [
    { l: 'LLM', v: a.llm_s ?? 0, c: 'var(--accent)' },
    { l: 'Tools', v: a.tool_s ?? 0, c: 'var(--tok-cache-read)' },
    { l: 'Overhead', v: a.overhead_s ?? 0, c: 'var(--faint)' },
  ]
  const topTools = a.tool_calls.filter((t) => !t.parent_id)
  const ok = topTools.filter((t) => t.status === 'ok').length
  const fail = topTools.filter((t) => t.status !== 'ok').length
  const retry = topTools.filter((t) => t.is_retry).length
  const nested = a.tool_calls.filter((t) => t.parent_id).length
  const turns = a.llm_calls.filter((c) => c.role !== 'aux' && c.http_status === 200).length
  const aux = a.llm_calls.filter((c) => c.role === 'aux').length
  const thinkRaw = [...new Set(a.llm_calls.filter((c) => c.role !== 'aux').map((c) => c.thinking_requested).filter(Boolean) as string[])]
  const thinkingCfg = [...new Set(thinkRaw.map(thinkingLabel))].join(' / ')
  const promoIds = [...new Set(a.llm_calls.flatMap((c) => (c.promotions ?? '').split(',').filter(Boolean)))]
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4 2xl:grid-cols-6">
      <div className="panel col-span-2 p-3.5">
        <div className="flex items-center justify-between gap-2">
          <span className="eyebrow">Tokens · {fmtTok(Object.values(tok).reduce((x, y) => x + y, 0))}</span>
          <AttemptPips idx={a.idx} max={Math.max(maxA, a.idx)} status={a.status} />
        </div>
        <TokenBar t={tok} height={8} className="mt-2.5" />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <TokenLegend />
          <ThinkingBadge configured={thinkingCfg || null} verified={a.thinking_verified} raw={thinkRaw.join('\n')} />
        </div>
      </div>
      <div className="panel col-span-2 p-3.5">
        <div className="eyebrow">Wall time · {fmtDur(wall)}</div>
        <div className="mt-2.5 flex h-2 overflow-hidden rounded-full bg-sunken">
          {split.map((s) => (
            <div key={s.l} style={{ width: `${(s.v / Math.max(wall, 1e-9)) * 100}%`, background: s.c }} />
          ))}
        </div>
        <div className="mt-2 flex gap-4 text-[11px] text-muted">
          {split.map((s) => (
            <span key={s.l} className="inline-flex items-center gap-1.5">
              <span className="size-2 rounded-[2px]" style={{ background: s.c }} />
              {s.l} <span className="font-mono text-fg-2 num">{fmtDur(s.v)}</span>
            </span>
          ))}
          <span>
            TTFT <span className="font-mono text-fg-2 num">{a.ttft_ms != null ? `${(a.ttft_ms / 1000).toFixed(2)}s` : '—'}</span>
          </span>
        </div>
      </div>
      <div className="panel p-3.5">
        <div className="eyebrow">Steps</div>
        <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[11.5px] num">
          <span className="text-muted">turns</span>
          <span className="text-right">
            {turns}
            {aux > 0 && <span className="text-faint"> +{aux} aux</span>}
          </span>
          <span className="text-muted">retries</span>
          <span className="text-right">{a.llm_calls.filter((c) => c.is_retry || c.http_status !== 200).length}</span>
          <span className="text-muted">tools</span>
          <span className="text-right">
            <span className="text-pass">{ok}</span>/<span className="text-fail">{fail}</span>/<span className="text-warn">{retry}</span>
          </span>
          {nested > 0 && (
            <>
              <span className="text-muted">programs/sub</span>
              <span className="text-right">
                {topTools.length}/{nested}
              </span>
            </>
          )}
          <Tip content={nested > 0 ? 'Tools per LLM turn, counting PTC sub-calls (programs per turn in brackets)' : 'Top-level tool calls per successful LLM turn'}>
            <span className="text-muted underline decoration-dotted underline-offset-2">tools/turn</span>
          </Tip>
          <span className="text-right">
            {turns ? ((topTools.length + nested) / turns).toFixed(2) : '—'}
            {nested > 0 && turns ? <span className="text-faint"> ({(topTools.length / turns).toFixed(2)})</span> : null}
          </span>
          {(a.dialogs ?? 0) > 0 && (
            <>
              <span className="text-muted">dialogs</span>
              <span className="text-right">{a.dialogs}</span>
            </>
          )}
        </div>
      </div>
      <div className="panel p-3.5">
        <div className="eyebrow">Cost · outcome</div>
        <Money usd={a.cost_usd} effective={a.cost_effective_usd} promos={promoIds} status={a.cost_status} className="mt-1.5 text-[16px]" />
        <div className="mt-1 font-mono text-[11px] text-muted">
          {a.exit_class ?? '—'} · diff {a.diff_files ?? '—'}f / {a.diff_lines ?? '—'}l
        </div>
      </div>
    </div>
  )
}

// ---------------- replay + timeline ----------------
const SPEEDS = ['1', '2', '4', '8', '16'] as const

function Replay({ a, cast, castError, webDriven }: { a: AttemptDetail; cast: Cast | null; castError: boolean; webDriven?: boolean }) {
  const term = useRef<TermHandle>(null)
  const t0 = attemptT0(a)
  const offset = cast && cast.start ? cast.start - t0 : 0 // cast time → attempt-relative time
  const lastCall = a.llm_calls.filter((c) => c.role !== 'aux').reduce((m, c) => Math.max(m, (c.t_end ?? c.t_start) - t0), 0)
  const lastEv = a.events.reduce((m, e) => Math.max(m, e.ts - t0), 0)
  const dur = Math.max(a.wall_s ?? 0, cast ? cast.duration + offset : 0, lastCall, lastEv + 1, 1)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>('4')
  const written = useRef(0) // index of next cast event to write
  const [sel, setSel] = useState<{ kind: 'llm'; c: LlmCall } | { kind: 'tool'; c: ToolCall } | null>(null)

  const seek = useCallback(
    (nt: number) => {
      if (!cast) return setT(nt)
      term.current?.reset()
      let i = 0
      let buf = ''
      while (i < cast.events.length && cast.events[i][0] + offset <= nt) buf += cast.events[i++][1]
      term.current?.write(buf)
      written.current = i
      setT(nt)
    },
    [cast, offset],
  )

  // initial render: show the screen at the last model response (TUIs often clear the screen on exit)
  useEffect(() => {
    if (cast) setTimeout(() => seek(lastCall > 0 ? Math.min(dur, lastCall + 0.5) : dur), 30)
  }, [cast, dur, seek, lastCall])

  useEffect(() => {
    if (!playing || !cast) return
    let raf = 0
    let last = performance.now()
    let cur = t
    const tick = (now: number) => {
      cur = Math.min(dur, cur + ((now - last) / 1000) * Number(speed))
      last = now
      let buf = ''
      while (written.current < cast.events.length && cast.events[written.current][0] + offset <= cur) buf += cast.events[written.current++][1]
      if (buf) term.current?.write(buf)
      setT(cur)
      if (cur >= dur) setPlaying(false)
      else raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, speed, cast])

  return (
    <Panel
      eyebrow="Terminal replay · asciicast v2"
      title="Replay synced to the step timeline"
      bodyClass="p-0"
      actions={
        <div className="flex items-center gap-2">
          <Button size="sm" variant="ghost" asChild>
            <a href={`/api/attempts/${a.id}/cast`} download={`${a.id}.cast`}>
              <FileDown /> .cast
            </a>
          </Button>
        </div>
      }
    >
      <div className="grid grid-cols-1 min-[1900px]:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0">
          <div className="aspect-[220/68] max-h-[620px] min-h-[300px] border-b border-line">
            {webDriven ? <div className="flex h-full items-center justify-center bg-term"><Empty title="Browser-driven attempt" hint="dsh web runs in the Web UI via Playwright, so there is no terminal recording; the step timeline below is from the Meter and session records." /></div> : castError ? <div className="flex h-full items-center justify-center bg-term"><Empty title="No recording for this attempt" hint="The cast endpoint returned an error." /></div> : <XtermView key={`${cast?.width}x${cast?.height}`} ref={term} cols={cast?.width ?? 220} rows={cast?.height ?? 60} />}
          </div>
          <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-2">
            <Button
              size="icon-sm"
              variant="secondary"
              aria-label={playing ? 'Pause' : 'Play'}
              onClick={() => {
                if (!playing && t >= dur - 0.01) seek(0)
                setPlaying((p) => !p)
              }}
            >
              {playing ? <Pause /> : <Play />}
            </Button>
            <Button size="icon-sm" variant="ghost" aria-label="Restart" onClick={() => { setPlaying(false); seek(0) }}>
              <RotateCcw />
            </Button>
            <span className="w-[92px] font-mono text-[11.5px] text-fg-2 num">
              {fmtClock(t)} / {fmtClock(dur)}
            </span>
            <input
              type="range"
              min={0}
              max={dur}
              step={0.1}
              value={t}
              onChange={(e) => {
                setPlaying(false)
                seek(+e.target.value)
              }}
              aria-label="Seek"
              className="h-1 min-w-[120px] flex-1 cursor-pointer accent-[var(--accent)]"
            />
            <Segmented size="sm" value={speed} onChange={setSpeed} options={SPEEDS.map((s) => ({ value: s, label: `${s}×` }))} />
          </div>
          <Timeline a={a} dur={dur} t={t} onSeek={(nt) => { setPlaying(false); seek(nt) }} onSelect={setSel} />
        </div>
        <StepDetail sel={sel} t0={t0} />
      </div>
    </Panel>
  )
}

const ROLE_COLOR: Record<string, string> = { default: 'var(--accent)', plan: 'var(--tok-thinking)', subagent: 'var(--tok-cache-write)', execute: 'var(--accent)' }

function Timeline({ a, dur, t, onSeek, onSelect }: { a: AttemptDetail; dur: number; t: number; onSeek: (t: number) => void; onSelect: (s: { kind: 'llm'; c: LlmCall } | { kind: 'tool'; c: ToolCall }) => void }) {
  const t0 = attemptT0(a)
  const ref = useRef<HTMLDivElement>(null)
  const pct = (s: number) => (Number.isFinite(s) ? Math.min(100, (Math.max(0, s) / dur) * 100) : 0)
  const x = (s: number) => `${pct(s)}%`
  const w = (s: number) => `max(2px, ${pct(s)}%)`
  const top = a.tool_calls.filter((c) => !c.parent_id)
  const nested = a.tool_calls.filter((c) => c.parent_id)
  const timed = a.llm_calls.filter((c) => c.role !== 'aux') // aux (harness-internal) calls are excluded from timing views
  const maxTok = Math.max(...timed.map((c) => c.tok_output + c.tok_thinking), 1)
  const ticks = Array.from({ length: 6 }, (_, i) => (dur * i) / 5)
  const lane = (label: string, children: React.ReactNode, h = 22) => (
    <div className="flex items-center">
      <div className="w-[86px] shrink-0 pr-2 text-right text-[10.5px] text-muted">{label}</div>
      <div className="relative flex-1" style={{ height: h }}>
        {children}
      </div>
    </div>
  )
  return (
    <div
      ref={ref}
      className="relative select-none px-4 pb-3 pt-2"
      onClick={(e) => {
        const r = ref.current!.getBoundingClientRect()
        const left = r.left + 16 + 86
        const width = r.width - 32 - 86
        const p = (e.clientX - left) / width
        if (p >= 0 && p <= 1) onSeek(p * dur)
      }}
    >
      {lane(
        '',
        ticks.map((tk) => (
          <span key={tk} className="absolute top-0 -translate-x-1/2 font-mono text-[9.5px] text-faint num" style={{ left: x(tk) }}>
            {fmtClock(tk)}
          </span>
        )),
        14,
      )}
      {lane(
        'LLM calls',
        timed.map((c) => {
          const s = c.t_start - t0
          const e = (c.t_end ?? c.t_start) - t0
          const fb = (c.t_first_byte ?? c.t_start) - t0
          const hgt = 6 + ((c.tok_output + c.tok_thinking) / maxTok) * 14
          const err = c.http_status !== 200
          return (
            <Tip
              key={c.id}
              content={
                <div className="font-mono text-[11px]">
                  #{c.seq} {c.model} · {c.role} {err && <span className="text-fail">HTTP {c.http_status}</span>}
                  <br />
                  {fmtTok(c.tok_total)} tok · {((e - s) || 0).toFixed(1)}s · {fmtUsd(c.cost_usd, c.cost_status)}
                </div>
              }
            >
              <button
                onClick={(ev) => {
                  ev.stopPropagation()
                  onSelect({ kind: 'llm', c })
                  onSeek(e)
                }}
                className="absolute bottom-0 overflow-hidden rounded-[2px] hover:brightness-125"
                style={{ left: x(s), width: w(e - s), height: err ? 22 : hgt, background: err ? 'var(--fail)' : ROLE_COLOR[c.role] ?? 'var(--accent)', opacity: 0.9 }}
              >
                <span className="absolute inset-y-0 left-0 bg-black/30" style={{ width: `${((fb - s) / Math.max(e - s, 1e-6)) * 100}%` }} />
              </button>
            </Tip>
          )
        }),
      )}
      {lane(
        'Tool calls',
        top.map((c) => {
          const point = c.t_start == null || c.t_end == null // only one timestamp reported: draw a marker, not a span
          const e = ((c.t_end ?? c.t_start) as number) - t0
          const s = point ? e : (c.t_start as number) - t0
          const col = c.is_retry ? 'var(--warn)' : c.status === 'ok' ? 'var(--pass)' : 'var(--fail)'
          return (
            <Tip key={c.id} content={<span className="font-mono text-[11px]">{c.name} · {c.is_retry ? 'retry' : c.status}{c.error_code ? ` · ${c.error_code}` : ''} · {point ? 'end time only' : `${(e - s).toFixed(2)}s`}</span>}>
              <button
                onClick={(ev) => {
                  ev.stopPropagation()
                  onSelect({ kind: 'tool', c })
                  onSeek(e)
                }}
                className={cn('absolute top-1/2 -translate-y-1/2 hover:brightness-125', point ? 'size-2 -translate-x-1/2 rotate-45 rounded-[1px]' : 'h-3 rounded-[2px]')}
                style={point ? { left: x(e), background: col, opacity: 0.9 } : { left: x(s), width: w(e - s), background: col, opacity: 0.85 }}
              />
            </Tip>
          )
        }),
      )}
      {nested.length > 0 &&
        lane(
          'PTC nested',
          nested.map((c) => {
            const point = c.t_start == null || c.t_end == null
            const e = ((c.t_end ?? c.t_start) as number) - t0
            const s = point ? e : (c.t_start as number) - t0
            const bg = c.status === 'ok' ? 'var(--tok-cache-read)' : 'var(--fail)'
            return point ? (
              <span key={c.id} title={`${c.name} · ${c.status} · end time only`} className="absolute top-1/2 size-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full" style={{ left: x(e), background: bg, opacity: 0.85 }} />
            ) : (
              <span key={c.id} title={`${c.name} · ${c.status}`} className="absolute top-1/2 h-2 -translate-y-1/2 rounded-[1px]" style={{ left: x(s), width: w(e - s), background: bg, opacity: 0.7 }} />
            )
          }),
          14,
        )}
      {lane(
        'Events',
        a.events.map((e) => (
          <Tip key={e.id} content={<span className="font-mono text-[11px]">{e.type}</span>}>
            <span className="absolute top-1/2 size-2 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[1px] bg-fg-2" style={{ left: x(e.ts - t0) }} />
          </Tip>
        )),
        16,
      )}
      {/* playhead */}
      <div className="pointer-events-none absolute bottom-2 top-2 flex" style={{ left: `calc(16px + 86px + (100% - 32px - 86px) * ${Math.min(1, t / dur)})` }}>
        <div className="w-px bg-accent" />
        <div className="absolute -left-[3px] top-0 size-[7px] rounded-full bg-accent" />
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 pl-[86px] text-[10.5px] text-muted">
        {Object.entries({ default: 'default role', plan: 'plan role', subagent: 'subagent' }).map(([k, l]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="size-2 rounded-[2px]" style={{ background: ROLE_COLOR[k] }} />
            {l}
          </span>
        ))}
        <span>bar height = output + thinking tokens · dark head = time to first byte · click to seek</span>
      </div>
    </div>
  )
}

function StepDetail({ sel, t0 }: { sel: { kind: 'llm'; c: LlmCall } | { kind: 'tool'; c: ToolCall } | null; t0: number }) {
  return (
    <aside className="border-t border-line p-4 min-[1900px]:border-l min-[1900px]:border-t-0">
      <div className="eyebrow mb-2">Step detail</div>
      {!sel && <div className="text-[12px] text-muted">Click a bar on the timeline to see tokens, latency and cost for that step.</div>}
      {sel?.kind === 'llm' && (
        <div className="space-y-3">
          <div>
            <div className="font-mono text-[12.5px]">
              LLM call #{sel.c.seq} · <span className="text-muted">{sel.c.role}</span>
            </div>
            <div className="font-mono text-[11px] text-muted">
              {sel.c.model} @ {sel.c.location}
            </div>
            <div className="truncate font-mono text-[11px] text-muted" title={sel.c.thinking_requested ?? ''}>
              {thinkingLabel(sel.c.thinking_requested)}
            </div>
          </div>
          <KV
            rows={[
              ['HTTP', sel.c.http_status === 200 ? '200' : <span className="text-fail">{sel.c.http_status} {sel.c.error_kind}</span>],
              ['Start', `+${fmtClock(sel.c.t_start - t0)}`],
              ['TTFB', sel.c.t_first_byte ? `${(sel.c.t_first_byte - sel.c.t_start).toFixed(2)}s` : '—'],
              ['Latency', sel.c.t_end ? `${(sel.c.t_end - sel.c.t_start).toFixed(2)}s` : '—'],
              ['Prompt size', fmtTok(sel.c.prompt_size)],
              ['Uncached in', fmtInt(sel.c.tok_input)],
              ['Cache read', fmtInt(sel.c.tok_cache_read)],
              ['Cache write', fmtInt(sel.c.tok_cache_write_5m + sel.c.tok_cache_write_1h)],
              ['Output', fmtInt(sel.c.tok_output)],
              ['Thinking', fmtInt(sel.c.tok_thinking)],
              ['Tool prompt', fmtInt(sel.c.tok_tool_prompt)],
              ['Stop', sel.c.stop_reason ?? '—'],
              ['Tools emitted', String(sel.c.tool_calls_emitted ?? '—')],
              ['Traffic', sel.c.traffic_type ?? '—'],
              ['Cost', <Money key="m" usd={sel.c.cost_usd} effective={sel.c.cost_effective_usd} promos={sel.c.promotions} status={sel.c.cost_status} compact />],
              ['Promotions', sel.c.promotions ?? '—'],
            ]}
          />
        </div>
      )}
      {sel?.kind === 'tool' && (
        <div className="space-y-3">
          <div className="font-mono text-[12.5px]">
            {sel.c.name} <span className="text-muted">· {sel.c.source}</span>
          </div>
          <KV
            rows={[
              ['Status', <span key="s" className={sel.c.status === 'ok' ? 'text-pass' : 'text-fail'}>{sel.c.status}{sel.c.is_retry ? ' (retry)' : ''}</span>],
              ['Error', sel.c.error_code ?? '—'],
              ['Start', sel.c.t_start != null ? `+${fmtClock(sel.c.t_start - t0)}` : 'not reported'],
              ['End', sel.c.t_end != null ? `+${fmtClock(sel.c.t_end - t0)}` : '—'],
              ['Duration', sel.c.t_end != null && sel.c.t_start != null ? `${(sel.c.t_end - sel.c.t_start).toFixed(2)}s` : '—'],
              ['Call id', <span key="c" className="break-all">{sel.c.call_id}</span>],
              ['Args hash', sel.c.args_hash ?? '—'],
            ]}
          />
        </div>
      )}
    </aside>
  )
}

function KV({ rows }: { rows: [string, React.ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[100px_1fr] gap-x-3 gap-y-1 text-[11.5px]">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-mono num">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

// ---------------- tables ----------------
const lc = createColumnHelper<LlmCall>()
function LlmTable({ calls }: { calls: LlmCall[] }) {
  const [sorting, setSorting] = useState<SortingState>([])
  const cols = useMemo(
    () => [
      lc.accessor('seq', { header: '#', cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
      lc.accessor('role', { header: 'Role' }),
      lc.accessor('model', { header: 'Model', cell: (c) => MODEL_SHORT[c.getValue()] ?? c.getValue() }),
      lc.accessor('http_status', { header: 'HTTP', cell: (c) => <span className={c.getValue() !== 200 ? 'text-fail' : 'text-muted'}>{c.getValue()}</span> }),
      lc.accessor((c) => (c.t_first_byte ? c.t_first_byte - c.t_start : null), { id: 'ttfb', header: 'TTFB', cell: (c) => (c.getValue() != null ? `${(c.getValue() as number).toFixed(2)}s` : '—') }),
      lc.accessor((c) => (c.t_end ? c.t_end - c.t_start : null), { id: 'lat', header: 'Latency', cell: (c) => (c.getValue() != null ? `${(c.getValue() as number).toFixed(2)}s` : '—') }),
      lc.accessor('prompt_size', { header: 'Prompt', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor('tok_input', { header: 'Uncached', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor('tok_cache_read', { header: 'Cache rd', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor((c) => c.tok_cache_write_5m + c.tok_cache_write_1h, { id: 'cw', header: 'Cache wr', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor('tok_output', { header: 'Output', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor('tok_thinking', { header: 'Thinking', cell: (c) => fmtTok(c.getValue()) }),
      lc.accessor('stop_reason', { header: 'Stop', cell: (c) => <span className="text-muted">{c.getValue() ?? '—'}</span> }),
      lc.accessor((c) => c.cost_effective_usd ?? c.cost_usd ?? -1, { id: 'cost', header: 'Cost (eff · list)', cell: (c) => <Money usd={c.row.original.cost_usd} effective={c.row.original.cost_effective_usd} promos={c.row.original.promotions} status={c.row.original.cost_status} compact /> }),
      lc.accessor('thinking_requested', { header: 'Thinking', cell: (c) => <span className="block max-w-[160px] truncate text-muted" title={c.getValue() ?? ''}>{c.row.original.role === 'aux' ? '—' : thinkingLabel(c.getValue())}</span> }),
      lc.accessor('request_hash', { header: 'Request', cell: (c) => <span className="text-faint">{c.getValue()?.slice(0, 8) ?? '—'}</span> }),
    ],
    [],
  )
  const table = useReactTable({ data: calls, columns: cols, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() })
  return <DataTable table={table} dimRow={(r) => (r as LlmCall).role === 'aux'} note="Raw Meter records (redacted: no prompt or response bodies). Dimmed rows are harness-internal aux calls: counted in spend and tokens, excluded from timing." />
}

const tc = createColumnHelper<ToolCall & { rel: number }>()
function ToolTable({ tools, t0 }: { tools: ToolCall[]; t0: number }) {
  const [sorting, setSorting] = useState<SortingState>([])
  const hasNested = tools.some((t) => t.parent_id)
  const [view, setView] = useState<'tree' | 'programs' | 'sub'>('tree')
  const data = useMemo(() => {
    // two-level tree: each top-level call followed by its nested sub-calls (PTC)
    const kids = new Map<string, ToolCall[]>()
    for (const t of tools) if (t.parent_id) kids.set(t.parent_id, [...(kids.get(t.parent_id) ?? []), t])
    const at = (t: ToolCall) => t.t_start ?? t.t_end ?? 0
    const tops = tools.filter((t) => !t.parent_id).sort((x, y) => at(x) - at(y))
    const rows = view === 'programs' ? tops : view === 'sub' ? tools.filter((t) => t.parent_id) : tops.flatMap((t) => [t, ...(kids.get(t.call_id) ?? []).sort((x, y) => at(x) - at(y))])
    return rows.map((t) => ({ ...t, rel: ((t.t_start ?? t.t_end ?? t0) as number) - t0 }))
  }, [tools, t0, view])
  const cols = useMemo(
    () => [
      tc.accessor('rel', { header: 'At', cell: (c) => `+${fmtClock(c.getValue())}` }),
      tc.accessor('name', { header: 'Tool', cell: (c) => <span className={c.row.original.parent_id ? 'pl-4 text-muted' : 'text-fg'}>{c.row.original.parent_id ? '↳ ' : ''}{c.getValue()}</span> }),
      tc.accessor('status', { header: 'Status', cell: (c) => <span className={c.getValue() === 'ok' ? 'text-pass' : 'text-fail'}>{c.getValue()}</span> }),
      tc.accessor('is_retry', { header: 'Retry', cell: (c) => (c.getValue() ? <span className="text-warn">↻</span> : '') }),
      tc.accessor('error_code', { header: 'Error', cell: (c) => <span className="text-muted">{c.getValue() ?? ''}</span> }),
      tc.accessor((t) => (t.t_end != null && t.t_start != null ? t.t_end - t.t_start : -1), { id: 'dur', header: 'Duration', cell: (c) => ((c.getValue() as number) < 0 ? <span className="text-faint">end only</span> : `${(c.getValue() as number).toFixed(2)}s`) }),
      tc.accessor('source', { header: 'Source', cell: (c) => <span className="text-muted">{c.getValue()}</span> }),
      tc.accessor('call_id', { header: 'Call id', cell: (c) => <span className="text-faint">{c.getValue().slice(-14)}</span> }),
    ],
    [],
  )
  const table = useReactTable({ data, columns: cols, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() })
  return (
    <div className="flex flex-col gap-2">
      {hasNested && (
        <Segmented
          size="sm"
          className="self-start"
          value={view}
          onChange={setView}
          options={[
            { value: 'tree', label: 'Tree' },
            { value: 'programs', label: `Programs · ${tools.filter((t) => !t.parent_id).length}` },
            { value: 'sub', label: `Sub-calls · ${tools.filter((t) => t.parent_id).length}` },
          ]}
        />
      )}
      <DataTable table={table} note={hasNested ? 'PTC: run_code programs are top-level; sub-calls (<parent>:ptc:<n>) are nested under them.' : undefined} />
    </div>
  )
}

function DataTable<T>({ table, note, dimRow }: { table: ReturnType<typeof useReactTable<T>>; note?: string; dimRow?: (r: T) => boolean }) {
  return (
    <div className="panel overflow-hidden">
      <div className="max-h-[440px] overflow-auto">
        <table className="w-full font-mono text-[11.5px] num">
          <thead className="sticky top-0 z-10 bg-panel">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-line">
                {hg.headers.map((h) => (
                  <th key={h.id} onClick={h.column.getToggleSortingHandler()} className="cursor-pointer whitespace-nowrap px-3 py-2 text-left font-sans text-[11px] font-medium text-muted first:pl-4 hover:text-fg">
                    <span className="inline-flex items-center gap-1">
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {h.column.getIsSorted() === 'asc' ? <ArrowUp className="size-3" /> : h.column.getIsSorted() === 'desc' ? <ArrowDown className="size-3" /> : null}
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((r) => (
              <tr key={r.id} className={cn('border-b border-line/50 last:border-0 hover:bg-hover', dimRow?.(r.original) && 'opacity-45')}>
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="whitespace-nowrap px-3 py-1.5 first:pl-4">
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {table.getRowModel().rows.length === 0 && <Empty title="Nothing recorded yet" />}
      </div>
      {note && <div className="border-t border-line px-4 py-1.5 text-[11px] text-muted">{note}</div>}
    </div>
  )
}

function Verifier({ a }: { a: AttemptDetail }) {
  const ev = a.events.find((e) => e.type === 'verifier')
  const d = ev?.data as { fail_to_pass?: { passed: number; total: number; failed: string[] }; pass_to_pass?: { passed: number; total: number; failed: string[] }; log_tail?: string; verify_s?: number } | undefined
  const f2p = d?.fail_to_pass ?? (a.f2p_total != null ? { passed: a.f2p_passed ?? 0, total: a.f2p_total, failed: [] } : null)
  const p2p = d?.pass_to_pass ?? (a.p2p_total != null ? { passed: a.p2p_passed ?? 0, total: a.p2p_total, failed: [] } : null)
  if (!f2p && !p2p) return <div className="panel"><Empty title="Not verified yet" hint="Hidden tests run in a clean container after the agent's turn completes." /></div>
  const Box = ({ label, hint, v }: { label: string; hint: string; v: { passed: number; total: number; failed: string[] } | null }) => {
    const ok = v && v.passed === v.total
    return (
      <div className="panel p-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-[12.5px] font-semibold">{label}</div>
            <div className="text-[11px] text-muted">{hint}</div>
          </div>
          <span className={cn('font-mono text-[20px] num', ok ? 'text-pass' : 'text-fail')}>
            {v ? `${v.passed}/${v.total}` : '—'}
          </span>
        </div>
        {v && (
          <div className="mt-3 flex gap-[3px]">
            {Array.from({ length: v.total }, (_, i) => (
              <span key={i} className="h-2 flex-1 rounded-[2px]" style={{ background: i < v.passed ? 'var(--pass)' : 'var(--fail)' }} />
            ))}
          </div>
        )}
        {v?.failed?.length ? (
          <div className="mt-3 space-y-0.5 font-mono text-[11px] text-fail">
            {v.failed.map((f) => (
              <div key={f}>✗ {f}</div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }
  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      <Box label="FAIL_TO_PASS" hint="Tests the fix must make pass" v={f2p} />
      <Box label="PASS_TO_PASS" hint="Regression guard: must stay green" v={p2p} />
      {d?.log_tail && (
        <div className="panel overflow-hidden lg:col-span-2">
          <div className="flex items-center justify-between border-b border-line px-4 py-2">
            <span className="eyebrow">log_tail</span>
            {d.verify_s != null && <span className="font-mono text-[11px] text-muted">verify {d.verify_s.toFixed(1)}s</span>}
          </div>
          <pre className="max-h-[260px] overflow-auto bg-term px-4 py-3 font-mono text-[11.5px] leading-relaxed text-[#d7dae0]">
            {d.log_tail.split('\n').map((l, i) => (
              <div key={i} className={/FAIL|Error/.test(l) ? 'text-[#ff7b80]' : /^OK$/.test(l) ? 'text-[#6ee7b0]' : undefined}>
                {l}
              </div>
            ))}
          </pre>
        </div>
      )}
    </div>
  )
}

function EventsTable({ a }: { a: AttemptDetail }) {
  const egress = a.events.filter((e) => e.type === 'egress')
  const byHost = new Map<string, { forwarded: number; denied: number }>()
  for (const e of egress) {
    const d = e.data as { host?: string; action?: string }
    const h = d.host ?? '?'
    const r = byHost.get(h) ?? { forwarded: 0, denied: 0 }
    if (d.action === 'denied') r.denied++
    else r.forwarded++
    byHost.set(h, r)
  }
  return (
    <div className="flex flex-col gap-3">
      {byHost.size > 0 && <EgressTable rows={[...byHost].map(([host, r]) => ({ host, ...r }))} note="Meter egress for this attempt: only GEAP and auth endpoints should be forwarded." />}
      <div className="panel divide-y divide-line/60">
        {a.events.map((e) => {
          const d = e.data as { host?: string; action?: string; path?: string }
          return (
            <div key={e.id} className="grid grid-cols-[80px_120px_1fr] gap-3 px-4 py-2 font-mono text-[11.5px]">
              <span className="text-muted num">+{fmtClock(e.ts - attemptT0(a))}</span>
              <span className={cn(e.type === 'egress' ? (d.action === 'denied' ? 'text-fail' : 'text-pass') : e.type === 'engine_error' ? 'text-idle' : 'text-fg')}>{e.type === 'egress' ? `egress ${d.action}` : e.type}</span>
              <span className="truncate text-muted">{e.type === 'egress' ? `${d.host}${d.path ?? ''}` : JSON.stringify(e.data).slice(0, 200)}</span>
            </div>
          )
        })}
        {a.events.length === 0 && <Empty title="No events" />}
      </div>
    </div>
  )
}

export function EgressTable({ rows, note }: { rows: { host: string; forwarded: number; denied: number }[]; note?: string }) {
  const sorted = [...rows].sort((x, y) => y.forwarded + y.denied - (x.forwarded + x.denied))
  const max = Math.max(1, ...sorted.map((r) => r.forwarded + r.denied))
  return (
    <div className="panel overflow-hidden">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="border-b border-line text-[11px] text-muted">
            <th className="px-4 py-2 text-left font-medium">Host</th>
            <th className="px-3 py-2 text-right font-medium">Forwarded</th>
            <th className="px-3 py-2 text-right font-medium">Denied</th>
            <th className="hidden w-[40%] px-4 py-2 md:table-cell" />
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.host} className="border-b border-line/50 last:border-0">
              <td className="px-4 py-1.5 font-mono">{r.host}</td>
              <td className="px-3 py-1.5 text-right font-mono text-pass num">{r.forwarded || ''}</td>
              <td className="px-3 py-1.5 text-right font-mono text-fail num">{r.denied || ''}</td>
              <td className="hidden px-4 py-1.5 md:table-cell">
                <div className="flex h-1.5 overflow-hidden rounded-full bg-sunken" style={{ width: `${((r.forwarded + r.denied) / max) * 100}%` }}>
                  <div style={{ width: `${(r.forwarded / Math.max(1, r.forwarded + r.denied)) * 100}%`, background: 'var(--pass)' }} />
                  <div className="flex-1" style={{ background: 'var(--fail)' }} />
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {note && <div className="border-t border-line px-4 py-1.5 text-[11px] text-muted">{note}</div>}
    </div>
  )
}

export type { Attempt }

function DiffView({ attemptId }: { attemptId: string }) {
  const q = useQuery({ queryKey: ['diff', attemptId], queryFn: () => api.diff(attemptId), retry: 0 })
  if (q.isLoading) return <Skeleton className="h-40" />
  if (q.isError || !q.data) return <div className="panel"><Empty title="No diff available" hint="GET /api/attempts/{id}/diff returned nothing for this attempt." /></div>
  const lines = q.data.split('\n')
  const add = lines.filter((l) => l.startsWith('+') && !l.startsWith('+++')).length
  const del = lines.filter((l) => l.startsWith('-') && !l.startsWith('---')).length
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center gap-3 border-b border-line px-4 py-2 font-mono text-[11.5px]">
        <span className="eyebrow">unified diff</span>
        <span className="text-pass">+{add}</span>
        <span className="text-fail">−{del}</span>
      </div>
      <pre className="max-h-[480px] overflow-auto py-2 font-mono text-[11.5px] leading-[1.65]">
        {lines.map((l, i) => {
          const cls = l.startsWith('diff --git') ? 'text-fg font-semibold mt-2' : l.startsWith('@@') ? 'text-accent' : l.startsWith('+++') || l.startsWith('---') || l.startsWith('index') ? 'text-muted' : l.startsWith('+') ? 'bg-[color-mix(in_oklab,var(--pass)_12%,transparent)] text-pass' : l.startsWith('-') ? 'bg-[color-mix(in_oklab,var(--fail)_12%,transparent)] text-fail' : 'text-fg-2'
          return (
            <div key={i} className={cn('px-4', cls)}>
              {l || ' '}
            </div>
          )
        })}
      </pre>
    </div>
  )
}

/** Attempt origin for relative times: t0, else the earliest recorded step (running attempts may not have t0 yet). */
export function attemptT0(a: AttemptDetail): number {
  if (a.t0) return a.t0
  const ts = [...a.llm_calls.map((c) => c.t_start), ...a.tool_calls.map((t) => t.t_start ?? t.t_end), ...a.events.map((e) => e.ts)].filter((v): v is number => v != null && Number.isFinite(v) && v > 0)
  return ts.length ? Math.min(...ts) : 0
}

/** Infra retries (quota/auth/boot) are attempts the engine re-runs; they are not agent failures. */
export function isInfraRetry(a: { status: string; exit_class?: string | null }): boolean {
  return !!a.exit_class && a.exit_class.startsWith('infra') && a.status !== 'passed'
}
