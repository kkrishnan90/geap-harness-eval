import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { createColumnHelper, flexRender, getCoreRowModel, getSortedRowModel, useReactTable, type SortingState } from '@tanstack/react-table'
import { ArrowDown, ArrowUp, AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import { useMaxAttempts, useRun } from '@/lib/run'
import type { GroupSummary, Trial } from '@/lib/types'
import { harnessColor, harnessLabelKey, INDUSTRY_LABEL } from '@/lib/labels'
import { cn, harnessKey } from '@/lib/utils'
import { fmtDur, fmtPct, fmtTok, fmtUsd } from '@/lib/format'
import { wilson } from '@/lib/stats'
import { Chart, axis, baseOption, mix, useChartTokens } from '@/components/Chart'
import { CIBar, Money, TokenLegend, TOKEN_CATS } from '@/components/domain'
import { Panel, Segmented, Skeleton, Empty } from '@/components/ui/misc'
import { Tip } from '@/components/ui/tooltip'

export const gkey = (g: { harness: string; variant: string }) => harnessKey(g)
export const glabel = (g: GroupSummary) => `${harnessLabelKey(gkey(g) === 'dsh' ? 'dsh/ptc' : gkey(g))} · ${g.profile_id}`

export default function Compare() {
  const { runId, current } = useRun()
  const sumQ = useQuery({ queryKey: ['summary', runId], queryFn: () => api.summary(runId!), enabled: !!runId, refetchInterval: current?.status === 'running' ? 15_000 : false })
  const trialsQ = useQuery({ queryKey: ['trials', runId], queryFn: () => api.trials(runId!), enabled: !!runId, refetchInterval: current?.status === 'running' ? 15_000 : false })
  const groups = sumQ.data?.groups ?? []
  const maxAttemptsCfg = useMaxAttempts()
  const trials = trialsQ.data ?? []

  if (sumQ.isLoading) return <LoadingGrid />
  if (!groups.length) return <div className="panel"><Empty title="No finished trials yet" hint="Comparisons appear once trials in this run complete." /></div>

  return (
    <div className="flex flex-col gap-4">
      <Leaderboard groups={groups} trials={trials} k={sumQ.data?.k ?? null} maxAttempts={sumQ.data?.max_attempts ?? maxAttemptsCfg} />
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <Heatmap trials={trials} />
        <Pareto groups={groups} />
      </div>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-2">
        <TokenComposition groups={groups} />
        <TimeWaterfall groups={groups} />
      </div>
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1fr_1.3fr]">
        <Survival trials={trials} maxAttempts={sumQ.data?.max_attempts ?? maxAttemptsCfg} />
        <ToolSankey groups={groups} />
      </div>
    </div>
  )
}

function LoadingGrid() {
  return (
    <div className="grid gap-4">
      <Skeleton className="h-80" />
      <div className="grid grid-cols-2 gap-4">
        <Skeleton className="h-72" />
        <Skeleton className="h-72" />
      </div>
    </div>
  )
}

// ---------------- leaderboard ----------------
const col = createColumnHelper<GroupSummary>()

function Leaderboard({ groups, trials, k: kRep, maxAttempts }: { groups: GroupSummary[]; trials: Trial[]; k: number | null; maxAttempts: number }) {
  const [sorting, setSorting] = useState<SortingState>([{ id: 'pass_at_1', desc: true }])
  const versions = useMemo(() => {
    const m = new Map<string, Set<string>>()
    for (const t of trials) {
      if (t.status === 'na') continue
      const k = t.harness
      if (!m.has(k)) m.set(k, new Set())
      m.get(k)!.add(t.harness_version)
    }
    return m
  }, [trials])
  const maxCost = Math.max(...groups.map((g) => g.cost_ci?.[1] ?? g.cost_mean ?? 0), 0.01)
  const columns = useMemo(
    () => [
      col.display({
        id: 'rank',
        header: '#',
        cell: (c) => <span className="font-mono text-muted num">{c.table.getRowModel().rows.findIndex((r) => r.id === c.row.id) + 1}</span>,
        enableSorting: false,
      }),
      col.accessor((g) => gkey(g), {
        id: 'harness',
        header: 'Harness',
        cell: (c) => {
          const g = c.row.original
          const k = gkey(g) === 'dsh' ? 'dsh/ptc' : gkey(g)
          const vs = versions.get(g.harness)
          return (
            <div className="flex items-center gap-2">
              <span className="h-4 w-[3px] rounded-full" style={{ background: harnessColor(k) }} />
              <span className="whitespace-nowrap font-medium">{harnessLabelKey(k)}</span>
              {vs && vs.size > 1 && (
                <Tip content={`Version changed within this run: ${[...vs].join(', ')}`}>
                  <AlertTriangle className="size-3.5 text-warn" />
                </Tip>
              )}
            </div>
          )
        },
      }),
      col.accessor('profile_id', { header: 'Profile', cell: (c) => <span className="font-mono text-[11.5px] text-fg-2">{c.getValue()}</span> }),
      col.accessor('n', { header: 'n', cell: (c) => <span className="font-mono text-muted num">{c.getValue()}</span> }),
      col.accessor('pass_at_1', {
        header: 'pass@1 · 95% CI',
        cell: (c) => {
          const g = c.row.original
          const ciP = g.pass_at_1_ci
          const wide = (g as { needs_more_repeats?: boolean }).needs_more_repeats ?? (g.n < 10 || (ciP != null && ciP[1] - ciP[0] > 0.45))
          return (
            <div className="flex items-center gap-2.5">
              <span className="w-[42px] text-right font-mono font-medium num">{fmtPct(g.pass_at_1)}</span>
              {ciP ? (
                <Tip content={`${fmtPct(ciP[0], 1)} – ${fmtPct(ciP[1], 1)}`}>
                  <span>
                    <CIBar v={g.pass_at_1} lo={ciP[0]} hi={ciP[1]} color="var(--pass)" width={110} />
                  </span>
                </Tip>
              ) : (
                <Tip content="No CI reported (too few samples)">
                  <span className="inline-block w-[110px] text-center font-mono text-[10.5px] text-faint">n too small</span>
                </Tip>
              )}
              {wide && (
                <Tip content="Needs more repeats: n < 10 or the CI is wider than 45 points">
                  <AlertTriangle className="size-3.5 text-warn" aria-label="Needs more repeats" />
                </Tip>
              )}
            </div>
          )
        },
      }),
      col.accessor((g) => g.solved_within_retries ?? -1, {
        id: 'solved',
        header: () => (
          <Tip content={`Share of trials solved within ${maxAttempts} attempt${maxAttempts > 1 ? 's' : ''} (1 + ${maxAttempts - 1} task retries). Not pass@k: retries are of the same trial.`}>
            <span>solved ≤{maxAttempts}</span>
          </Tip>
        ),
        cell: (c) => <span className="font-mono num">{fmtPct(c.row.original.solved_within_retries)}</span>,
      }),
      col.accessor((g) => g.pass_k ?? -1, {
        id: 'pass_k',
        header: () => (
          <Tip content={kRep ? `Unbiased pass@${kRep} over independent repeats (k = min(repeats, 5))` : 'pass@k needs repeats; k not reported'}>
            <span>pass@{kRep ?? 'k'}</span>
          </Tip>
        ),
        cell: (c) =>
          c.row.original.pass_k == null ? (
            <Tip content={`Needs ≥${kRep ?? 'k'} repeats (n = ${c.row.original.n})`}>
              <span className="font-mono text-faint">—</span>
            </Tip>
          ) : (
            <span className="font-mono num">{fmtPct(c.row.original.pass_k)}</span>
          ),
      }),
      col.accessor((g) => g.pass_hat_k ?? -1, {
        id: 'pass_hat_k',
        header: () => (
          <Tip content={`pass^${kRep ?? 'k'}: probability all ${kRep ?? 'k'} independent repeats pass (consistency)`}>
            <span>pass^{kRep ?? 'k'}</span>
          </Tip>
        ),
        cell: (c) =>
          c.row.original.pass_hat_k == null ? (
            <Tip content={`Needs ≥${kRep ?? 'k'} repeats (n = ${c.row.original.n})`}>
              <span className="font-mono text-faint">—</span>
            </Tip>
          ) : (
            <span className="font-mono text-fg-2 num">{fmtPct(c.row.original.pass_hat_k)}</span>
          ),
      }),
      col.accessor((g) => g.cost_mean ?? -1, {
        id: 'cost',
        header: () => <Tip content="Effective cost (after reviewed promotional credits) with list price beside it when they differ. CI is on list cost."><span>Cost / trial · CI</span></Tip>,
        cell: (c) => {
          const g = c.row.original
          const share = g.cost_status_share
          const st = share && (share.unpriced ?? 0) > 0.5 ? 'unpriced' : share && (share.check ?? 0) > 0.05 ? 'check' : 'verified'
          return (
            <div className="flex items-center gap-2.5">
              <Money usd={g.cost_mean} effective={g.cost_effective_mean} status={st} compact className="min-w-[72px] justify-end" />
              {g.cost_ci && <CIBar v={g.cost_mean ?? 0} lo={g.cost_ci[0]} hi={g.cost_ci[1]} max={maxCost} color="var(--cost-verified)" width={80} />}
            </div>
          )
        },
      }),
      col.accessor((g) => g.cost_per_success_effective ?? g.cost_per_success ?? Infinity, { id: 'cps', header: '$ / solved', cell: (c) => <Money dot={false} usd={c.row.original.cost_per_success} effective={c.row.original.cost_per_success_effective} compact /> }),
      col.accessor('time_mean', {
        header: 'Time · CI',
        cell: (c) => (
          <Tip content={c.row.original.time_ci ? `95% CI ${fmtDur(c.row.original.time_ci[0])} – ${fmtDur(c.row.original.time_ci[1])}` : 'No CI reported'}>
            <span className="font-mono num">{fmtDur(c.getValue())}</span>
          </Tip>
        ),
      }),
      col.accessor('tool_calls_mean', { header: 'Tools', cell: (c) => <span className="font-mono num">{c.getValue().toFixed(1)}</span> }),
      col.accessor('tool_fail_rate', { header: 'Tool fail', cell: (c) => <span className={cn('font-mono num', c.getValue() > 0.15 && 'text-warn')}>{fmtPct(c.getValue(), 1)}</span> }),
      col.accessor('cache_hit_ratio', { header: 'Cache hit', cell: (c) => <span className="font-mono num">{fmtPct(c.getValue())}</span> }),
    ],
    [versions, maxCost, kRep, maxAttempts],
  )
  const table = useReactTable({ data: groups, columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() })
  return (
    <Panel eyebrow="Leaderboard" title="Harness × variant × profile" bodyClass="p-0" actions={<span className="text-[11px] text-muted">pass@1 uses first attempts only · Wilson 95% CI · costs bootstrap 95% CI</span>}>
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id} className="border-b border-line">
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    onClick={h.column.getToggleSortingHandler()}
                    className={cn('whitespace-nowrap px-3 py-2 text-left text-[11px] font-medium text-muted first:pl-4', h.column.getCanSort() && 'cursor-pointer select-none hover:text-fg')}
                  >
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
              <tr key={r.id} className="border-b border-line/60 transition-colors last:border-0 hover:bg-hover">
                {r.getVisibleCells().map((c) => (
                  <td key={c.id} className="whitespace-nowrap px-3 py-2 first:pl-4">
                    {flexRender(c.column.columnDef.cell, c.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

// ---------------- heatmap ----------------
function Heatmap({ trials }: { trials: Trial[] }) {
  const k = useChartTokens()
  const [dim, setDim] = useState<'industry' | 'tier' | 'both'>('industry')
  const data = useMemo(() => {
    const done = trials.filter((t) => t.status === 'passed' || t.status === 'failed')
    const hs = [...new Set(done.map((t) => harnessKey(t)))].sort()
    const xKey = (t: Trial) => (dim === 'industry' ? t.industry : dim === 'tier' ? t.tier : `${t.industry}·${t.tier[0]}`)
    const order = dim === 'tier' ? ['simple', 'medium', 'complex'] : null
    const xs = order ?? [...new Set(done.map(xKey))].sort()
    const cells: [number, number, number, number, number][] = []
    hs.forEach((h, yi) =>
      xs.forEach((x, xi) => {
        const ts = done.filter((t) => harnessKey(t) === h && xKey(t) === x)
        if (!ts.length) {
          cells.push([xi, yi, -1, 0, 0]) // no finished trials: rendered as an empty "no data" cell
          return
        }
        const p = ts.filter((t) => t.passed_on_attempt === 1).length
        cells.push([xi, yi, +(p / ts.length).toFixed(3), ts.length, p])
      }),
    )
    return { hs, xs, cells }
  }, [trials, dim])
  const option = {
    ...baseOption(k),
    grid: { left: 96, right: 16, top: 8, bottom: dim === 'both' ? 64 : 30 },
    tooltip: {
      ...baseOption(k).tooltip,
      formatter: (p: { data: number[] }) => {
        const [xi, yi, v, n, c] = p.data
        if (v < 0) return `<b>${harnessLabelKey(data.hs[yi])}</b> · ${data.xs[xi]}<br/><span style="opacity:.7">No data: no finished trials for this cell (not in the task selection, N/A for this harness, or still running)</span>`
        const ci = wilson(c, n)
        return `<b>${harnessLabelKey(data.hs[yi] === 'dsh' ? 'dsh/ptc' : data.hs[yi])}</b> · ${data.xs[xi]}<br/>pass@1 <b>${fmtPct(v)}</b> (${c}/${n})<br/><span style="opacity:.7">95% CI ${fmtPct(ci[0])}–${fmtPct(ci[1])}</span>`
      },
    },
    xAxis: { type: 'category', data: data.xs.map((x) => (dim === 'industry' ? INDUSTRY_LABEL[x] ?? x : x)), ...axis(k, { splitLine: { show: false }, axisLabel: { color: k.muted, fontSize: 10.5, rotate: dim === 'both' ? 40 : 0, interval: 0 } }) },
    yAxis: { type: 'category', data: data.hs.map((h) => harnessLabelKey(h === 'dsh' ? 'dsh/ptc' : h)), ...axis(k, { splitLine: { show: false }, axisLabel: { color: k.fg2, fontSize: 11 } }) },
    visualMap: { min: 0, max: 1, show: false, dimension: 2, inRange: { color: [k.sunken, mix(k.sunken, k.pass, 0.45), k.pass] }, outOfRange: { color: [mix(k.panel, k.line, 0.5)] } },
    series: [
      {
        type: 'heatmap',
        data: data.cells,
        label: { show: dim !== 'both', color: k.fg, fontFamily: k.mono, fontSize: 10.5, formatter: (p: { data: number[] }) => (p.data[2] < 0 ? '·' : Math.round(p.data[2] * 100)) },
        itemStyle: { borderColor: k.panel, borderWidth: 2, borderRadius: 3 },
        emphasis: { itemStyle: { borderColor: k.fg, borderWidth: 1 } },
      },
    ],
  }
  return (
    <Panel
      eyebrow="Where each harness wins"
      title="pass@1 heatmap"
      actions={<Segmented size="sm" value={dim} onChange={setDim} options={[{ value: 'industry', label: 'Industry' }, { value: 'tier', label: 'Tier' }, { value: 'both', label: 'Industry × tier' }]} />}
    >
      <Chart option={option} height={300} />
    </Panel>
  )
}

// ---------------- pareto ----------------
function Pareto({ groups }: { groups: GroupSummary[] }) {
  const k = useChartTokens()
  const pts = groups.filter((g) => g.cost_mean != null).map((g) => ({ g, x: g.cost_effective_mean ?? g.cost_mean!, y: g.pass_at_1 }))
  const frontier = [...pts].sort((a, b) => a.x - b.x).reduce<typeof pts>((acc, p) => (acc.length === 0 || p.y > acc[acc.length - 1].y ? [...acc, p] : acc), [])
  const fset = new Set(frontier.map((f) => f.g))
  const option = {
    ...baseOption(k),
    grid: { left: 48, right: 20, top: 16, bottom: 40 },
    tooltip: {
      ...baseOption(k).tooltip,
      formatter: (p: { data: { g: GroupSummary } }) => {
        const g = p.data.g
        return g ? `<b>${glabel(g)}</b><br/>pass@1 ${fmtPct(g.pass_at_1)} · ${fmtUsd(g.cost_effective_mean ?? g.cost_mean)} effective / trial (${fmtUsd(g.cost_mean)} list)<br/>${fmtUsd(g.cost_per_success_effective ?? g.cost_per_success)} effective per solved${fset.has(g) ? '<br/><b>On the frontier</b>' : ''}` : ''
      },
    },
    xAxis: { type: 'log', name: 'mean effective cost per trial (USD, log)', nameLocation: 'middle', nameGap: 26, ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => '$' + (v < 1 ? v.toFixed(2) : v.toFixed(0)) } },
    yAxis: { type: 'value', min: 0, max: 1, name: 'pass@1', ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => Math.round(v * 100) + '%' } },
    series: [
      {
        type: 'line',
        data: frontier.map((p) => [p.x, p.y]),
        lineStyle: { color: k.accent, width: 1.5, type: [4, 4] },
        symbol: 'none',
        z: 1,
        silent: true,
      },
      {
        type: 'scatter',
        data: pts.map((p) => {
          const hk = gkey(p.g) === 'dsh' ? 'dsh/ptc' : gkey(p.g)
          return {
            value: [p.x, p.y],
            g: p.g,
            symbolSize: fset.has(p.g) ? 13 : 9,
            itemStyle: { color: harnessColor(hk), borderColor: fset.has(p.g) ? k.fg : 'transparent', borderWidth: 1.5, opacity: fset.has(p.g) ? 1 : 0.75 },
            label: { show: fset.has(p.g), formatter: glabel(p.g), position: 'right', color: k.fg2, fontSize: 10.5 },
          }
        }),
        z: 2,
      },
    ],
  }
  return (
    <Panel eyebrow="Cost vs. pass" title="Pareto frontier" actions={<span className="text-[11px] text-muted">dashed = non-dominated configurations</span>}>
      <Chart option={option} height={300} />
    </Panel>
  )
}

// ---------------- token composition ----------------
function TokenComposition({ groups }: { groups: GroupSummary[] }) {
  const k = useChartTokens()
  const [mode, setMode] = useState<'abs' | 'pct'>('abs')
  const gs = [...groups].sort((a, b) => sumTok(a) - sumTok(b))
  const option = {
    ...baseOption(k),
    grid: { left: 190, right: 24, top: 8, bottom: 24 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => (mode === 'pct' ? fmtPct(v, 1) : fmtTok(v)) },
    xAxis: { type: 'value', max: mode === 'pct' ? 1 : undefined, ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => (mode === 'pct' ? Math.round(v * 100) + '%' : fmtTok(v)) } },
    yAxis: { type: 'category', data: gs.map(glabel), ...axis(k, { splitLine: { show: false }, axisLabel: { color: k.fg2, fontSize: 10.5, width: 180, overflow: 'truncate' } }) },
    series: TOKEN_CATS.map((c) => ({
      type: 'bar',
      name: c.label,
      stack: 't',
      barWidth: 10,
      itemStyle: { color: k.tok[c.key] },
      data: gs.map((g) => {
        const v = tokOf(g, c.key)
        return mode === 'pct' ? v / Math.max(1, sumTok(g)) : v
      }),
    })),
  }
  return (
    <Panel eyebrow="Mean tokens per attempt" title="Token composition" actions={<Segmented size="sm" value={mode} onChange={setMode} options={[{ value: 'abs', label: 'Tokens' }, { value: 'pct', label: 'Share' }]} />}>
      <TokenLegend className="mb-2" />
      <Chart option={option} height={Math.max(260, gs.length * 20 + 40)} />
    </Panel>
  )
}

function tokOf(g: GroupSummary, key: string): number {
  const t = g.tokens as Record<string, number | undefined>
  if (key === 'cache_write') return t.cache_write ?? (t.cache_write_5m ?? 0) + (t.cache_write_1h ?? 0)
  return t[key] ?? 0
}
const sumTok = (g: GroupSummary) => TOKEN_CATS.reduce((s, c) => s + tokOf(g, c.key), 0)

// ---------------- time waterfall ----------------
function TimeWaterfall({ groups }: { groups: GroupSummary[] }) {
  const k = useChartTokens()
  const gs = groups.filter((g) => g.time_split).sort((a, b) => tot(a) - tot(b))
  if (!gs.length)
    return (
      <Panel eyebrow="Where time goes" title="Time waterfall">
        <Empty title="Time split not reported" hint="The summary endpoint did not include time_split for these groups." />
      </Panel>
    )
  const parts = [
    { key: 'llm_s', label: 'LLM', color: k.accent },
    { key: 'tool_s', label: 'Tools', color: k.tok.cache_read },
    { key: 'overhead_s', label: 'Harness overhead', color: k.faint },
    { key: 'verify_s', label: 'Verify', color: k.verified },
  ] as const
  const option = {
    ...baseOption(k),
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 8, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 190, right: 24, top: 30, bottom: 24 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: number) => fmtDur(v) },
    xAxis: { type: 'value', ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => fmtDur(v) } },
    yAxis: { type: 'category', data: gs.map(glabel), ...axis(k, { splitLine: { show: false }, axisLabel: { color: k.fg2, fontSize: 10.5, width: 180, overflow: 'truncate' } }) },
    series: parts.map((p) => ({ type: 'bar', name: p.label, stack: 't', barWidth: 10, itemStyle: { color: p.color }, data: gs.map((g) => g.time_split![p.key]) })),
  }
  return (
    <Panel eyebrow="Mean seconds per attempt: t0 → turn complete → verified" title="Time waterfall">
      <Chart option={option} height={Math.max(260, gs.length * 20 + 60)} />
    </Panel>
  )
}
const tot = (g: GroupSummary) => (g.time_split ? g.time_split.llm_s + g.time_split.tool_s + g.time_split.overhead_s + g.time_split.verify_s : 0)

// ---------------- survival ----------------
function Survival({ trials, maxAttempts }: { trials: Trial[]; maxAttempts: number }) {
  const k = useChartTokens()
  const series = useMemo(() => {
    const done = trials.filter((t) => t.status === 'passed' || t.status === 'failed')
    const hs = [...new Set(done.map((t) => harnessKey(t)))].sort()
    return hs.map((h) => {
      const ts = done.filter((t) => harnessKey(t) === h)
      const pts = Array.from({ length: maxAttempts }, (_, i) => i + 1).map((a) => [a, ts.filter((t) => !(t.status === 'passed' && (t.passed_on_attempt ?? 99) <= a)).length / ts.length])
      return { h, pts, n: ts.length }
    })
  }, [trials, maxAttempts])
  const option = {
    ...baseOption(k),
    legend: { bottom: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 3, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 44, right: 16, top: 16, bottom: 56 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis', valueFormatter: (v: number) => fmtPct(v, 1) },
    xAxis: { type: 'value', min: 1, max: Math.max(2, maxAttempts), interval: 1, name: `after attempt k (max ${maxAttempts})`, nameLocation: 'middle', nameGap: 24, ...axis(k) },
    yAxis: { type: 'value', min: 0, max: 1, ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => Math.round(v * 100) + '%' } },
    series: series.map((s) => {
      const hk = s.h === 'dsh' ? 'dsh/ptc' : s.h
      return { type: 'line', name: harnessLabelKey(hk), step: 'end', data: s.pts, symbol: 'circle', symbolSize: 5, lineStyle: { width: 2, color: harnessColor(hk) }, itemStyle: { color: harnessColor(hk) } }
    }),
  }
  return (
    <Panel eyebrow="Share of trials still unsolved after k attempts" title="Pass-by-attempt survival">
      <Chart option={option} height={300} />
    </Panel>
  )
}

// ---------------- sankey ----------------
function toolKind(name: string): string {
  const n = name.toLowerCase()
  if (n === 'run_code') return 'run_code (PTC)'
  if (/read|view|cat|open/.test(n)) return 'read'
  if (/edit|replace|write|patch/.test(n)) return 'edit / write'
  if (/bash|shell|command|exec|run/.test(n)) return 'shell'
  if (/grep|search|find|glob|list|lsp/.test(n)) return 'search / nav'
  return 'other'
}

function ToolSankey({ groups }: { groups: GroupSummary[] }) {
  const k = useChartTokens()
  const { nodes, links } = useMemo(() => {
    const L = new Map<string, number>()
    const add = (a: string, b: string, v: number) => v > 0 && L.set(a + '\u0000' + b, (L.get(a + '\u0000' + b) ?? 0) + v)
    for (const g of groups) {
      const h = harnessLabelKey(gkey(g) === 'dsh' ? 'dsh/ptc' : gkey(g))
      for (const t of g.tools_by_name ?? []) {
        const kind = toolKind(t.name)
        add(h, kind, t.ok + t.fail + t.retry + t.denied)
        add(kind, 'ok', t.ok)
        add(kind, 'failed', t.fail)
        add(kind, 'retried', t.retry)
        add(kind, 'denied', t.denied)
      }
    }
    const names = new Set<string>()
    const links = [...L].map(([key, v]) => {
      const [s, t] = key.split('\u0000')
      names.add(s)
      names.add(t)
      return { source: s, target: t, value: v }
    })
    return { nodes: [...names].map((n) => ({ name: n })), links }
  }, [groups])
  if (!links.length)
    return (
      <Panel eyebrow="Tool outcomes" title="Tool-outcome flow">
        <Empty title="Per-tool counts not reported" hint="The summary endpoint did not include tools_by_name." />
      </Panel>
    )
  const outcomeColor: Record<string, string> = { ok: k.pass, failed: k.fail, retried: k.warn, denied: k.check }
  const option = {
    ...baseOption(k),
    tooltip: { ...baseOption(k).tooltip, trigger: 'item' },
    series: [
      {
        type: 'sankey',
        left: 8,
        right: 70,
        top: 8,
        bottom: 8,
        nodeWidth: 8,
        nodeGap: 7,
        layoutIterations: 64,
        emphasis: { focus: 'adjacency' },
        data: nodes.map((n) => {
          const hkey = ['claude_code', 'pi', 'omp', 'dsh/web-ptc', 'dsh/web-native', 'dsh/acp-ptc', 'agy'].find((h) => harnessLabelKey(h) === n.name)
          return { ...n, itemStyle: { color: outcomeColor[n.name] ?? (hkey ? harnessColor(hkey) : k.fg2), borderWidth: 0 } }
        }),
        links,
        lineStyle: { color: 'gradient', opacity: 0.22, curveness: 0.5 },
        label: { color: k.fg2, fontSize: 11, fontFamily: k.sans },
      },
    ],
  }
  return (
    <Panel eyebrow="Harness → tool kind → outcome" title="Tool-outcome flow" actions={<span className="text-[11px] text-muted">top-level calls; PTC nested sub-calls in Trial Inspector</span>}>
      <Chart option={option} height={340} />
    </Panel>
  )
}
