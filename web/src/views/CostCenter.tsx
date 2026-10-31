import { useMemo, useState } from 'react'
import { PriceValidation, PromotionsPanel } from '@/components/Pricing'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { useRun } from '@/lib/run'
import type { CostStatus, GroupSummary, Trial } from '@/lib/types'
import { harnessColor, modelShort } from '@/lib/labels'
import { fmtDateTime, fmtPct, fmtTok, fmtUsd, ago } from '@/lib/format'
import { bootstrapCI } from '@/lib/stats'
import { Chart, axis, baseOption, useChartTokens } from '@/components/Chart'
import { CIBar, CostDot, CostLegend, Kpi, Money, PromoChip, costMeta } from '@/components/domain'
import { Panel, Skeleton, Empty, Chip, Segmented } from '@/components/ui/misc'
import { Tip } from '@/components/ui/tooltip'
import { gkey, glabel } from './Compare'

const CAT_LABEL: Record<string, string> = {
  input: 'Uncached input',
  cache_read: 'Cache read',
  cache_write: 'Cache write',
  cache_write_5m: 'Cache write 5m',
  cache_write_1h: 'Cache write 1h',
  output: 'Output',
  thinking: 'Thinking',
  tool_prompt: 'Tool-use prompt',
  tool_use_prompt: 'Tool-use prompt',
}

export default function CostCenter() {
  const { runId, current } = useRun()
  const live = current?.status === 'running'
  const sumQ = useQuery({ queryKey: ['summary', runId], queryFn: () => api.summary(runId!), enabled: !!runId, refetchInterval: live ? 15_000 : false })
  const trialsQ = useQuery({ queryKey: ['trials', runId], queryFn: () => api.trials(runId!), enabled: !!runId, refetchInterval: live ? 15_000 : false })
  const priceQ = useQuery({ queryKey: ['pricing'], queryFn: api.pricing })
  const s = sumQ.data
  const trials = trialsQ.data ?? []
  const spend = s?.spend

  const solved = trials.filter((t) => t.status === 'passed')
  const doneT = trials.filter((t) => t.status === 'passed' || t.status === 'failed')
  const totalCost = spend?.total_usd ?? doneT.reduce((a, t) => a + (t.cost_usd ?? 0), 0)
  const totalEff = spend?.total_effective_usd ?? doneT.reduce((a, t) => a + (t.cost_effective_usd ?? t.cost_usd ?? 0), 0)
  const cps = solved.length ? totalCost / solved.length : null
  const cpsEff = solved.length ? totalEff / solved.length : null
  const promoIds = priceQ.data?.promotions?.map((p) => p.id)
  // server value when reported; otherwise derive from per-model cache-read spend and global SKU rates
  const cacheSavings = useMemo(() => {
    if (spend?.cache_savings_usd != null) return { usd: spend.cache_savings_usd, derived: false }
    const book = priceQ.data?.models ?? []
    let usd = 0
    let any = false
    for (const r of spend?.by_model_category ?? []) {
      if (r.category !== 'cache_read' || !r.usd) continue
      const rates = (book.find((m) => m.model === r.model && m.location === 'global') ?? book.find((m) => m.model === r.model))?.rates
      if (!rates?.input || !rates?.cache_read) continue
      usd += r.usd * (rates.input / rates.cache_read - 1)
      any = true
    }
    return { usd: any ? usd : null, derived: any }
  }, [spend, priceQ.data])
  const cpsCI = useMemo(() => {
    // bootstrap the ratio over trials: resample trial costs/outcomes
    if (doneT.length < 2) return null
    const costs = doneT.map((t) => t.cost_usd ?? 0)
    const ci = bootstrapCI(costs, 300, 11)
    const pr = solved.length / doneT.length
    return pr ? ([ci[0] / pr, ci[1] / pr] as [number, number]) : null
  }, [doneT, solved.length])
  const badge = spend?.badge_share ?? {}

  if (sumQ.isLoading) return <Skeleton className="h-96" />
  if (!s) return <Empty title="No cost data" />

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Kpi
          label="Total spend · effective"
          value={<Money usd={totalEff} status="verified" />}
          sub={
            <span className="inline-flex flex-wrap items-center gap-1.5">
              {fmtUsd(totalCost)} list{totalCost - totalEff > 1e-6 && <PromoChip promos={promoIds} />}
              <span className="text-faint">·</span> <BadgeShareText share={badge} />
            </span>
          }
        >
          <BadgeShareBar share={badge} className="mt-1.5" />
        </Kpi>
        <Kpi label="Cost per solved · effective" value={fmtUsd(cpsEff)} sub={`${fmtUsd(cps)} list` + (cpsCI ? ` · list 95% CI ${fmtUsd(cpsCI[0])} – ${fmtUsd(cpsCI[1])}` : '')} />
        <Kpi label="Cache savings" value={fmtUsd(cacheSavings.usd)} accent="var(--tok-cache-read)" sub={cacheSavings.derived ? 'derived: cache-read spend × (input ÷ cache-read rate − 1)' : 'cache reads vs. same tokens uncached'} />
        <Kpi
          label="Waste"
          value={fmtUsd(spend?.waste_usd)}
          accent="var(--warn)"
          sub={spend ? `${fmtPct((spend.waste_usd ?? 0) / Math.max(totalCost, 1e-9))} of spend · failed attempts + retried calls` : undefined}
        />
        <Kpi label="Price book" value={<span className="truncate text-[15px]">{priceQ.data?.snapshot_id ?? '—'}</span>} sub={priceQ.data ? `Billing Catalog · synced ${ago(priceQ.data.fetched_at)}` : undefined} />
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1.25fr_1fr]">
        <SpendByModel rows={spend?.by_model_category ?? []} />
        <SpendOverTime trials={trials} />
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1.25fr_1fr]">
        <CostPerSolved groups={s.groups} />
        <div className="flex flex-col gap-4">
          <WastePanel spend={spend} total={totalCost} />
          <BadgePanel share={badge} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1.25fr_1fr]">
        <PriceValidation />
        <PromotionsPanel />
      </div>
      <PriceBook />
    </div>
  )
}

function BadgeShareText({ share }: { share: Partial<Record<CostStatus, number>> }) {
  const parts = (['verified', 'check', 'unpriced', 'reconciled', 'pt'] as CostStatus[]).filter((k) => (share[k] ?? 0) > 0.0005)
  if (!parts.length) return <>no attempts costed yet</>
  return <>{parts.map((k) => `${fmtPct(share[k], (share[k] ?? 0) < 0.1 ? 1 : 0)} ${k === 'verified' ? 'catalog-verified' : k}`).join(', ')}</>
}

function BadgeShareBar({ share, className }: { share: Partial<Record<CostStatus, number>>; className?: string }) {
  return (
    <div className={`flex h-1.5 overflow-hidden rounded-full bg-sunken ${className ?? ''}`}>
      {(['verified', 'reconciled', 'pt', 'check', 'unpriced'] as CostStatus[]).map((k) => (
        <div key={k} style={{ width: `${(share[k] ?? 0) * 100}%`, background: costMeta[k].color }} />
      ))}
    </div>
  )
}

function SpendByModel({ rows: raw }: { rows: { model: string; category: string; usd: number; usd_effective?: number; tokens: number }[] }) {
  const k = useChartTokens()
  const hasEff = raw.some((r) => r.usd_effective != null)
  const [basis, setBasis] = useState<'effective' | 'list'>('effective')
  const rows = raw.map((r) => ({ ...r, usd: basis === 'effective' && r.usd_effective != null ? r.usd_effective : r.usd }))
  if (!rows.length)
    return (
      <Panel eyebrow="Where the money goes" title="Spend by model × token category">
        <Empty title="Not reported" hint="The summary endpoint did not include spend.by_model_category." />
      </Panel>
    )
  const models = [...new Set(rows.map((r) => r.model))].sort((a, b) => sumBy(rows, b) - sumBy(rows, a))
  const cats = ['input', 'cache_read', 'cache_write', 'output', 'thinking', 'tool_prompt'].filter((c) => rows.some((r) => r.category === c))
  const color: Record<string, string> = { ...k.tok, tool_prompt: k.faint }
  const option = {
    ...baseOption(k),
    legend: { top: 0, left: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 8, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 112, right: 70, top: 34, bottom: 24 },
    tooltip: {
      ...baseOption(k).tooltip,
      trigger: 'item',
      formatter: (p: { seriesName: string; name: string; value: number; data: { tokens: number } }) => `<b>${p.name}</b> · ${p.seriesName}<br/>${fmtUsd(p.value)} · ${fmtTok(p.data.tokens)} tokens`,
    },
    xAxis: { type: 'value', ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => '$' + v } },
    yAxis: { type: 'category', data: models.map(modelShort), ...axis(k, { splitLine: { show: false }, axisLabel: { color: k.fg2, fontSize: 11.5, width: 104, overflow: 'truncate' } }) },
    series: cats.map((c, i) => ({
      type: 'bar',
      name: CAT_LABEL[c] ?? c,
      stack: 's',
      barWidth: 18,
      itemStyle: { color: color[c] ?? k.faint, borderRadius: i === cats.length - 1 ? [0, 3, 3, 0] : 0 },
      label: i === cats.length - 1 ? { show: true, position: 'right', color: k.fg2, fontFamily: k.mono, fontSize: 11, formatter: (p: { dataIndex: number }) => fmtUsd(sumBy(rows, models[p.dataIndex])) } : undefined,
      data: models.map((m) => {
        const r = rows.find((x) => x.model === m && x.category === c)
        return { value: +(r?.usd ?? 0).toFixed(4), tokens: r?.tokens ?? 0 }
      }),
    })),
  }
  return (
    <Panel
      eyebrow="Where the money goes"
      title="Spend by model × token category"
      actions={hasEff ? <Segmented size="sm" value={basis} onChange={setBasis} options={[{ value: 'effective', label: 'Effective' }, { value: 'list', label: 'List' }]} /> : <CostLegend />}
    >
      <Chart option={option} height={Math.max(220, models.length * 46 + 70)} />
      <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 border-t border-line pt-3 md:grid-cols-4">
        {models.map((m) => {
          const out = rows.filter((r) => r.model === m && (r.category === 'output' || r.category === 'thinking')).reduce((a, r) => a + r.usd, 0)
          return (
            <div key={m} className="text-[11.5px]">
              <div className="text-muted">{modelShort(m)}</div>
              <div className="font-mono num">
                {fmtPct(out / Math.max(1e-9, sumBy(rows, m)))} <span className="text-muted">on output + thinking</span>
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}
const sumBy = (rows: { model: string; usd: number }[], m: string) => rows.filter((r) => r.model === m).reduce((a, r) => a + r.usd, 0)

function SpendOverTime({ trials }: { trials: Trial[] }) {
  const k = useChartTokens()
  const data = useMemo(() => {
    const ts = trials.filter((t) => t.cost_usd != null && (t.status === 'passed' || t.status === 'failed')).sort((a, b) => a.updated_at - b.updated_at)
    let acc = 0
    let waste = 0
    return ts.map((t) => {
      acc += t.cost_usd ?? 0
      if (t.status === 'failed') waste += t.cost_usd ?? 0
      return [t.updated_at * 1000, +acc.toFixed(3), +waste.toFixed(3)]
    })
  }, [trials])
  const option = {
    ...baseOption(k),
    legend: { top: 0, right: 0, icon: 'roundRect', itemWidth: 10, itemHeight: 3, textStyle: { color: k.muted, fontSize: 11 } },
    grid: { left: 54, right: 16, top: 30, bottom: 28 },
    tooltip: { ...baseOption(k).tooltip, trigger: 'axis', valueFormatter: (v: number) => fmtUsd(v) },
    xAxis: { type: 'time', ...axis(k, { splitLine: { show: false } }) },
    yAxis: { type: 'value', ...axis(k), axisLabel: { color: k.muted, fontFamily: k.mono, fontSize: 10.5, formatter: (v: number) => '$' + v } },
    series: [
      { type: 'line', name: 'Cumulative spend', data: data.map((d) => [d[0], d[1]]), showSymbol: false, lineStyle: { color: k.verified, width: 2 }, areaStyle: { color: k.verified, opacity: 0.08 } },
      { type: 'line', name: 'Spent on failed trials', data: data.map((d) => [d[0], d[2]]), showSymbol: false, lineStyle: { color: k.warn, width: 1.5, type: [4, 3] } },
    ],
  }
  return (
    <Panel eyebrow="Run timeline" title="Cumulative spend">
      {data.length ? <Chart option={option} height={260} /> : <Empty title="No finished trials yet" />}
    </Panel>
  )
}

function CostPerSolved({ groups }: { groups: GroupSummary[] }) {
  const gs = [...groups].filter((g) => g.cost_per_success != null).sort((a, b) => (a.cost_per_success_effective ?? a.cost_per_success ?? 0) - (b.cost_per_success_effective ?? b.cost_per_success ?? 0))
  const max = Math.max(...gs.map((g) => (g.cost_ci ? g.cost_ci[1] / Math.max(0.05, g.pass_at_1 || 0.05) : g.cost_per_success ?? 0)), 0.01)
  const maxCps = Math.max(...gs.map((g) => g.cost_per_success ?? 0), 0.01)
  return (
    <Panel eyebrow="Efficiency" title="Cost per solved task" bodyClass="p-0" actions={<span className="text-[11px] text-muted">bar = effective $/solved · whiskers = per-trial list-cost CI</span>}>
      <div className="divide-y divide-line/60">
        {gs.map((g) => {
          const k = gkey(g) === 'dsh' ? 'dsh/ptc' : gkey(g)
          const w = ((g.cost_per_success_effective ?? g.cost_per_success ?? 0) / maxCps) * 100
          return (
            <div key={glabel(g)} className="grid grid-cols-[minmax(0,220px)_1fr_auto] items-center gap-4 px-4 py-2 text-[12px]">
              <div className="flex min-w-0 items-center gap-2">
                <span className="h-3.5 w-[3px] shrink-0 rounded-full" style={{ background: harnessColor(k) }} />
                <span className="truncate">{glabel(g)}</span>
              </div>
              <div className="relative h-2 rounded-full bg-sunken">
                <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${w}%`, background: harnessColor(k), opacity: 0.8 }} />
              </div>
              <div className="flex items-center gap-3">
                {g.cost_ci && (
                  <Tip content={`Per-trial cost 95% CI ${fmtUsd(g.cost_ci[0])} – ${fmtUsd(g.cost_ci[1])}`}>
                    <span className="hidden md:inline">
                      <CIBar v={g.cost_mean ?? 0} lo={g.cost_ci[0]} hi={g.cost_ci[1]} max={max} color="var(--cost-verified)" width={70} />
                    </span>
                  </Tip>
                )}
                <Money dot={false} usd={g.cost_per_success} effective={g.cost_per_success_effective} compact className="min-w-[64px] justify-end text-right" />
              </div>
            </div>
          )
        })}
      </div>
    </Panel>
  )
}

function WastePanel({ spend, total }: { spend?: import('@/lib/types').RunAggregate['spend']; total: number }) {
  const b = spend?.waste_breakdown
  // total = agent failures + infra failures (waste_usd); retried LLM calls are shown but not added (they sit inside attempts)
  const parts = b
    ? [
        { label: 'Failed attempts', hint: 'agent failures', v: b.failed_attempts_usd, c: 'var(--fail)' },
        { label: 'Infra failures', hint: 'quota · auth · boot · engine errors — not the agent', v: b.infra_usd, c: 'var(--warn)' },
      ]
    : []
  const sum = spend?.waste_usd ?? parts.reduce((a, p) => a + (p.v ?? 0), 0)
  return (
    <Panel eyebrow="Spent without a pass" title="Waste">
      {!b ? (
        <Empty title="Waste breakdown not reported" />
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[22px] num">{fmtUsd(sum)}</span>
            <span className="text-[12px] text-muted">{fmtPct(sum / Math.max(total, 1e-9), 1)} of total spend</span>
          </div>
          <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-sunken">
            {parts.map((p) => (
              <div key={p.label} style={{ width: `${((p.v ?? 0) / Math.max(sum, 1e-9)) * 100}%`, background: p.c }} />
            ))}
          </div>
          <div className="mt-3 space-y-1.5">
            {parts.map((p) => (
              <div key={p.label} className="flex items-center gap-2 text-[12px]">
                <span className="size-2 rounded-[2px]" style={{ background: p.c }} />
                <span className="text-fg-2">{p.label}</span>
                <span className="text-[11px] text-muted">{p.hint}</span>
                <span className="ml-auto font-mono num">{fmtUsd(p.v)}</span>
              </div>
            ))}
            <div className="flex items-center gap-2 border-t border-line pt-1.5 text-[12px]">
              <span className="size-2 rounded-[2px] border border-line-strong" />
              <span className="text-fg-2">Retried LLM calls</span>
              <span className="text-[11px] text-muted">inside attempts · not added</span>
              <span className="ml-auto font-mono num">{fmtUsd(b.retried_calls_usd)}</span>
            </div>
          </div>
          {b.partial && <div className="mt-2 text-[11px] text-warn">This server does not split infra failures out yet; "Failed attempts" may include quota/auth retries.</div>}
        </>
      )}
    </Panel>
  )
}

function BadgePanel({ share }: { share: Partial<Record<CostStatus, number>> }) {
  const all: CostStatus[] = ['reconciled', 'verified', 'pt', 'check', 'unpriced']
  return (
    <Panel eyebrow="Confidence in every dollar" title="Cost badge distribution">
      <div className="space-y-2.5">
        {all.map((s) => (
          <div key={s} className="grid grid-cols-[170px_1fr_52px] items-center gap-3 text-[12px]">
            <span className="flex items-center gap-2">
              <CostDot status={s} />
              <span className="whitespace-nowrap">{costMeta[s].label}</span>
              {s === 'reconciled' && <Chip tone="muted">next rev.</Chip>}
            </span>
            <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
              <div className="h-full rounded-full" style={{ width: `${(share[s] ?? 0) * 100}%`, background: costMeta[s].color }} />
            </div>
            <span className="text-right font-mono num">{fmtPct(share[s] ?? 0, 1)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 text-[11px] text-muted">Unpriced usage is shown as "—" and is never counted as $0. Share is by dollars costed; unpriced share is by attempts.</div>
    </Panel>
  )
}

export function PriceBook() {
  const q = useQuery({ queryKey: ['pricing'], queryFn: api.pricing })
  const p = q.data
  const cats = useMemo(() => [...new Set((p?.models ?? []).flatMap((m) => Object.keys(m.rates ?? {}).filter((k) => !k.includes('>'))))], [p])
  const order = ['input', 'cache_read', 'cache_write_5m', 'cache_write_1h', 'output', 'thinking', 'tool_use_prompt']
  const sorted = cats.sort((a, b) => (order.indexOf(a) + 99) % 99 - ((order.indexOf(b) + 99) % 99))
  return (
    <Panel
      eyebrow="GET /api/pricing · USD per 1M tokens"
      title="Price book snapshot"
      bodyClass="p-0"
      actions={p ? <span className="font-mono text-[11px] text-muted">{p.snapshot_id} · {fmtDateTime(p.fetched_at)}</span> : null}
    >
      {!p ? (
        <Skeleton className="m-4 h-32" />
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="border-b border-line text-[11px] text-muted">
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                  <th className="px-3 py-2 text-left font-medium">Location</th>
                  {sorted.map((c) => (
                    <th key={c} className="whitespace-nowrap px-3 py-2 text-right font-medium">
                      {CAT_LABEL[c] ?? c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {p.models.map((m) => (
                  <tr key={m.model + m.location} className="border-b border-line/60 last:border-0 hover:bg-hover">
                    <td className="px-4 py-2 font-mono">{m.model}</td>
                    <td className="px-3 py-2 font-mono text-muted">{m.location}</td>
                    {sorted.map((c) => (
                      <td key={c} className="px-3 py-2 text-right font-mono num">
                        {m.rates?.[c] != null ? `$${Number(m.rates[c]).toFixed(2)}` : <span className="text-faint">—</span>}
                        {m.rates?.[`${c}>200k`] != null && m.rates[`${c}>200k`] !== m.rates[c] && (
                          <div className="text-[10px] text-muted">${Number(m.rates[`${c}>200k`]).toFixed(2)} &gt;200k</div>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {p.issues.length > 0 && (
            <div className="border-t border-line px-4 py-2.5">
              {p.issues.map((i) => (
                <div key={i} className="flex items-center gap-2 text-[11.5px] text-warn">
                  <CostDot status="check" /> {i}
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Panel>
  )
}
