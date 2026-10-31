import { useMemo } from 'react'
import { useQueries, useQuery } from '@tanstack/react-query'
import { EgressTable } from './TrialInspector'
import { useRun } from '@/lib/run'
import { api } from '@/lib/api'
import { useLive } from '@/lib/live'
import type { GovernorLane, InfraEvt } from '@/lib/types'
import { MODEL_SHORT } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { fmtTime } from '@/lib/format'
import { Chart, axis, baseOption, useChartTokens } from '@/components/Chart'
import { Kpi, Spark } from '@/components/domain'
import { Panel, Empty, Chip, Skeleton } from '@/components/ui/misc'
import { useNow } from '@/components/Shell'

type Ev = InfraEvt & { ts: number }
const MODEL_COLOR: Record<string, string> = { 'gemini-4-argon': '#7c6cff', 'gemini-3.8-flash': '#2cc1b0', 'claude-opus-5-5': '#d9825b', 'claude-sonnet-5-5': '#e3b341' }

export default function Quota() {
  const { runId, current } = useRun()
  const liveInfra = useLive((s) => s.infra)
  const calls = useLive((s) => [s.callsTotal, s.calls429] as const)
  const now = useNow(5000) / 1000
  const running = current?.status === 'running'
  const histQ = useQuery({ queryKey: ['infra', runId], queryFn: () => api.runInfra(runId!), enabled: !!runId, refetchInterval: running ? 15_000 : false })
  const govQ = useQuery({ queryKey: ['governor'], queryFn: api.governor, refetchInterval: 5000, retry: 0 })
  const gov = govQ.data ?? []
  // persisted history first, live SSE events merged on top (deduped)
  const infra = useMemo(() => {
    const seen = new Set<string>()
    const out: Ev[] = []
    for (const e of [...(histQ.data ?? []), ...liveInfra] as Ev[]) {
      const k = `${Math.round(e.ts * 10)}|${e.kind}|${e.model}|${e.location}`
      if (seen.has(k)) continue
      seen.add(k)
      out.push(e)
    }
    return out.sort((a, b) => a.ts - b.ts)
  }, [histQ.data, liveInfra])
  const pools = useMemo(() => {
    const m = new Map<string, { model: string; location: string; ev: Ev[] }>()
    for (const g of gov) {
      const [model, location] = g.lane.split('@')
      m.set(g.lane, { model, location: location ?? 'global', ev: [] })
    }
    for (const e of infra) {
      const k = `${e.model}@${e.location}`
      if (!m.has(k)) m.set(k, { model: e.model, location: e.location, ev: [] })
      m.get(k)!.ev.push(e)
    }
    return [...m.values()].sort((a, b) => a.model.localeCompare(b.model))
  }, [infra, gov])
  const total429 = infra.filter((e) => e.kind === '429')
  const last10 = total429.filter((e) => e.ts > now - 600).length
  const backoffs = infra.filter((e) => e.kind === 'backoff' || e.kind === ('503' as Ev['kind'])).length
  const govOf = (p: { model: string; location: string }) => gov.find((g) => g.lane === `${p.model}@${p.location}`)
  const openNow = gov.filter((g) => g.breaker === 'open').length
  const end = running || !infra.length ? now : Math.max(infra[infra.length - 1].ts + 300, current?.finished_at ?? 0)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Kpi label="429s · this run" value={total429.length} accent={total429.length ? 'var(--warn)' : undefined} sub={total429.length ? `last at ${fmtTime(total429[total429.length - 1].ts)} · ${(last10 / 10).toFixed(1)}/min now` : 'none recorded'} />
        <Kpi label="503s + backoffs" value={backoffs} sub="infra retries do not consume task retries" />
        <Kpi label="429 share of live calls" value={calls[0] ? `${((calls[1] / calls[0]) * 100).toFixed(1)}%` : '—'} sub={`${calls[1]} of ${calls[0]} Meter calls seen this session`} />
        <Kpi label="Breakers open" value={gov.length ? openNow : '—'} accent={gov.length ? (openNow ? 'var(--fail)' : 'var(--pass)') : undefined} sub={gov.length ? (openNow ? 'admission paused for those pools' : 'all live lanes admitting') : 'no live lanes (server idle)'} />
      </div>

      <Panel eyebrow="GET /api/governor · live in-memory state" title="Rate governor lanes" bodyClass="p-3">
        {gov.length === 0 && (
          <div className="mb-3 px-1 text-[12px] text-muted">
            No live lanes (server idle).{pools.length ? ' Showing per model × location history from this run.' : ''}
          </div>
        )}
        {pools.length === 0 ? (
          <Empty title="No lanes and no infra history for this run" />
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 2xl:grid-cols-4">
            {pools.map((p) => (
              <PoolCard key={p.model + p.location} p={p} now={now} gov={govOf(p)} />
            ))}
          </div>
        )}
      </Panel>

      {infra.length ? <Timeline429 pools={pools} now={end} /> : <Panel eyebrow="GET /api/runs/{id}/infra" title="429 timeline"><Empty title="No 429s, backoffs or breaker events recorded for this run" /></Panel>}
      <AimdChart pools={pools} />

      <EgressPanel />

      <Panel eyebrow="Persisted history + live SSE" title="Recent signals" bodyClass="p-0">
        {infra.length === 0 ? (
          <Empty title="No infra signals for this run" />
        ) : (
          <div className="max-h-[320px] overflow-y-auto">
            {infra
              .slice(-120)
              .reverse()
              .map((e, i) => (
                <div key={i} className="grid grid-cols-[64px_84px_1fr] gap-3 border-b border-line/50 px-4 py-1.5 font-mono text-[11.5px] last:border-0 md:grid-cols-[80px_110px_200px_1fr]">
                  <span className="text-muted num">{fmtTime(e.ts)}</span>
                  <span className={kindClass(e.kind)}>{e.kind}</span>
                  <span className="truncate text-fg-2">
                    {e.model}@{e.location}
                  </span>
                  <span className="hidden truncate text-muted md:block">{typeof e.detail === 'string' ? e.detail : e.detail ? JSON.stringify(e.detail) : ''}</span>
                </div>
              ))}
          </div>
        )}
      </Panel>
    </div>
  )
}

const kindClass = (k: string) => (k === '429' ? 'text-warn' : k === 'breaker_open' ? 'text-fail' : k === 'breaker_close' ? 'text-pass' : k === 'aimd' ? 'text-accent' : 'text-muted')

function breakerOpen(ev: Ev[]) {
  let open = false
  for (const e of ev) {
    if (e.kind === 'breaker_open') open = true
    if (e.kind === 'breaker_close') open = false
  }
  return open
}

function lastLimit(ev: Ev[]): number | null {
  for (let i = ev.length - 1; i >= 0; i--) {
    const d = ev[i].detail
    if (ev[i].kind === 'aimd' && d && typeof d === 'object' && 'limit' in d) return Number(d.limit)
  }
  return null
}

function PoolCard({ p, now, gov }: { p: { model: string; location: string; ev: Ev[] }; now: number; gov?: GovernorLane }) {
  const open = gov ? gov.breaker === 'open' : breakerOpen(p.ev)
  const lim = gov?.limit ?? lastLimit(p.ev)
  const buckets = Array.from({ length: 30 }, (_, i) => p.ev.filter((e) => e.kind === '429' && e.ts > now - (30 - i) * 120 && e.ts <= now - (29 - i) * 120).length)
  const c429 = gov?.n429 ?? p.ev.filter((e) => e.kind === '429' && e.ts > now - 3600).length
  return (
    <div className={cn('panel p-4', open && 'ring-1 ring-[color-mix(in_oklab,var(--fail)_50%,transparent)]')}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[13px] font-semibold">{MODEL_SHORT[p.model] ?? p.model}</div>
          <div className="font-mono text-[10.5px] text-muted">
            {p.model} @ {p.location}
          </div>
        </div>
        <Chip tone={open ? 'fail' : 'pass'}>breaker {open ? 'open' : 'closed'}</Chip>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <div>
          <div className="eyebrow">In flight / limit</div>
          <div className="font-mono text-[20px] num">
            {gov ? gov.inflight : '—'}
            <span className="text-[13px] text-muted">/{lim ?? '—'}</span>
          </div>
          <div className="mt-1 flex gap-[3px]">
            {Array.from({ length: 8 }, (_, i) => (
              <span key={i} className="h-1.5 flex-1 rounded-full" style={{ background: lim != null && i < lim ? MODEL_COLOR[p.model] ?? 'var(--accent)' : 'var(--line)', opacity: gov && i >= gov.inflight && lim != null && i < lim ? 0.35 : 1 }} />
            ))}
          </div>
        </div>
        <div>
          <div className="eyebrow">429s · 1h</div>
          <div className="font-mono text-[20px] num">{c429}</div>
          <Spark data={buckets} color="var(--warn)" height={18} />
        </div>
      </div>
    </div>
  )
}

function Timeline429({ pools, now }: { pools: { model: string; location: string; ev: Ev[] }[]; now: number }) {
  const k = useChartTokens()
  const start = Math.min(...pools.flatMap((p) => p.ev.map((e) => e.ts)), now - 3600)
  const bucket = 60
  const n = Math.ceil((now - start) / bucket)
  const option = {
    ...baseOption(k),
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 8, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 40, right: 16, top: 34, bottom: 50 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 14, bottom: 8, borderColor: k.line, backgroundColor: k.sunken, fillerColor: 'rgba(124,108,255,0.15)', handleStyle: { color: k.accent }, textStyle: { color: k.muted, fontSize: 10 }, dataBackground: { lineStyle: { color: k.line }, areaStyle: { color: k.line } } }],
    xAxis: { type: 'time', ...axis(k, { splitLine: { show: false } }) },
    yAxis: { type: 'value', minInterval: 1, name: '429s / min', ...axis(k) },
    series: pools.map((p) => {
      const counts = new Array(n).fill(0)
      for (const e of p.ev) if (e.kind === '429') counts[Math.min(n - 1, Math.floor((e.ts - start) / bucket))]++
      // breaker windows
      const areas: [{ xAxis: number }, { xAxis: number }][] = []
      let openAt: number | null = null
      for (const e of p.ev) {
        if (e.kind === 'breaker_open') openAt = e.ts
        if (e.kind === 'breaker_close' && openAt != null) {
          areas.push([{ xAxis: openAt * 1000 }, { xAxis: e.ts * 1000 }])
          openAt = null
        }
      }
      if (openAt != null) areas.push([{ xAxis: openAt * 1000 }, { xAxis: now * 1000 }])
      return {
        type: 'bar',
        stack: '429',
        name: `${MODEL_SHORT[p.model] ?? p.model}@${p.location}`,
        barMaxWidth: 8,
        itemStyle: { color: MODEL_COLOR[p.model] ?? k.accent },
        data: counts.map((c, i) => [(start + i * bucket) * 1000, c]),
        markArea: areas.length ? { silent: true, itemStyle: { color: 'rgba(240,88,94,0.10)' }, data: areas } : undefined,
      }
    }),
  }
  return (
    <Panel eyebrow="Per model × location · shaded = breaker open" title="429 timeline">
      <Chart option={option} height={280} />
    </Panel>
  )
}

function AimdChart({ pools }: { pools: { model: string; location: string; ev: Ev[] }[] }) {
  const k = useChartTokens()
  const series = pools
    .map((p) => ({
      p,
      pts: p.ev.filter((e) => e.kind === 'aimd' && e.detail && typeof e.detail === 'object' && 'limit' in e.detail).map((e) => [e.ts * 1000, Number((e.detail as { limit: number }).limit)]),
    }))
    .filter((s) => s.pts.length)
  if (!series.length) return null
  const option = {
    ...baseOption(k),
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 3, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 40, right: 16, top: 34, bottom: 28 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis' },
    xAxis: { type: 'time', ...axis(k, { splitLine: { show: false } }) },
    yAxis: { type: 'value', minInterval: 1, name: 'concurrency', ...axis(k) },
    series: series.map((s) => ({ type: 'line', step: 'end', name: `${MODEL_SHORT[s.p.model] ?? s.p.model}@${s.p.location}`, data: s.pts, showSymbol: false, lineStyle: { width: 1.75, color: MODEL_COLOR[s.p.model] ?? k.accent }, itemStyle: { color: MODEL_COLOR[s.p.model] ?? k.accent } })),
  }
  return (
    <Panel eyebrow="Halve on 429, +1 per quiet minute" title="AIMD concurrency limits">
      <Chart option={option} height={220} />
    </Panel>
  )
}

/** Meter egress per host, aggregated from the attempts this session has seen (no per-run endpoint exists). */
function EgressPanel() {
  const { runId } = useRun()
  const runQ = useQuery({ queryKey: ['egress', runId], queryFn: () => api.egress(runId!), enabled: !!runId, refetchInterval: 15_000, retry: false })
  if (runQ.data) {
    const m = new Map<string, { host: string; forwarded: number; denied: number }>()
    for (const r of runQ.data) {
      const e = m.get(r.host) ?? { host: r.host, forwarded: 0, denied: 0 }
      if (r.action === 'denied') e.denied += Number(r.n) || 0
      else e.forwarded += Number(r.n) || 0
      m.set(r.host, e)
    }
    return (
      <Panel eyebrow="GET /api/runs/{id}/egress · whole run" title="Egress (Meter)" bodyClass="p-0">
        {m.size === 0 ? (
          <Empty title="No egress recorded for this run yet" />
        ) : (
          <div className="p-3">
            <EgressTable rows={[...m.values()]} note="Only GEAP and auth endpoints should be forwarded; everything else is denied by the Meter." />
          </div>
        )}
      </Panel>
    )
  }
  if (!runQ.isError) return <Panel eyebrow="Meter egress" title="Egress (Meter)"><Skeleton className="h-24" /></Panel>
  // older servers (404): sample the attempts seen this session
  return <SampledEgress />
}

function SampledEgress() {
  const ids = useLive((s) =>
    Object.values(s.attempts)
      .sort((a, b) => (b.t_queued ?? 0) - (a.t_queued ?? 0))
      .slice(0, 24)
      .map((a) => a.id),
  )
  const qs = useQueries({ queries: ids.map((id) => ({ queryKey: ['attempt', id], queryFn: () => api.attempt(id), staleTime: 30_000 })) })
  const rows = useMemo(() => {
    const m = new Map<string, { host: string; forwarded: number; denied: number }>()
    for (const q of qs) {
      for (const e of q.data?.events ?? []) {
        if (e.type !== 'egress') continue
        const d = e.data as { host?: string; action?: string }
        const r = m.get(d.host ?? '?') ?? { host: d.host ?? '?', forwarded: 0, denied: 0 }
        if (d.action === 'denied') r.denied++
        else r.forwarded++
        m.set(r.host, r)
      }
    }
    return [...m.values()]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qs.map((q) => q.dataUpdatedAt).join()])
  const loaded = qs.filter((q) => q.data).length
  return (
    <Panel eyebrow={`Meter egress · ${loaded} recent attempts sampled`} title="Egress (Meter)" bodyClass="p-0">
      {rows.length === 0 ? (
        <Empty title="No egress records yet" hint="Egress events (forwarded / denied per host) appear in attempt event logs; this panel samples the attempts seen this session." />
      ) : (
        <div className="p-3">
          <EgressTable rows={rows} note="Per-run totals need a server-side aggregate; this samples up to 24 recent attempts. Per-attempt detail is in the Trial Inspector events tab." />
        </div>
      )}
    </Panel>
  )
}
