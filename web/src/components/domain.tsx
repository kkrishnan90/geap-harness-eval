import type { ReactNode } from 'react'
import { motion } from 'framer-motion'
import type { AttemptStatus, CostStatus, ToolCall, TrialStatus } from '@/lib/types'
import { cn } from '@/lib/utils'
import { fmtTok, fmtUsd } from '@/lib/format'
import { Tip } from './ui/tooltip'
import { findPromos, usePricing } from '@/lib/promos'

// ---------- cost ----------
type CostMeta = { label: string; color: string; desc: string }
const COST_META: Record<CostStatus | 'pending', CostMeta> = {
  pending: { label: 'Pending', color: 'var(--idle)', desc: 'Not priced yet: no completed, priced model call for this figure.' },
  verified: { label: 'Catalog-verified', color: 'var(--cost-verified)', desc: 'Token integrity, SKU map, arithmetic and second-source checks passed.' },
  check: { label: 'Check', color: 'var(--cost-check)', desc: 'Token mismatch between planes or a price change not yet acknowledged.' },
  unpriced: { label: 'Unpriced', color: 'var(--cost-unpriced)', desc: 'No valid SKU for this usage. Shown as "—", never as $0.' },
  reconciled: { label: 'Billed-reconciled', color: 'var(--cost-reconciled)', desc: 'Within ±1% of the billing export.' },
  pt: { label: 'Provisioned throughput', color: 'var(--faint)', desc: 'Served from provisioned throughput: $0 marginal cost, never mixed into on-demand totals.' },
}

/** Total lookup: null / unknown statuses map to a neutral "Pending" meta. */
export function costMetaOf(status: unknown): CostMeta {
  if (status == null || status === '') return COST_META.pending
  return (COST_META as Record<string, CostMeta>)[String(status)] ?? { label: String(status), color: 'var(--idle)', desc: `Unrecognised cost status "${String(status)}".` }
}

export function CostDot({ status, className }: { status: CostStatus | string | null | undefined; className?: string }) {
  const m = costMetaOf(status)
  return (
    <Tip content={<><b>{m.label}.</b> {m.desc}</>}>
      <span
        aria-label={m.label}
        className={cn('inline-block size-[7px] shrink-0 rounded-full', className)}
        style={{ background: m.color, boxShadow: `0 0 0 2.5px color-mix(in oklab, ${m.color} 22%, transparent)` }}
      />
    </Tip>
  )
}

/**
 * A cost figure. With `effective` given, shows effective (after reviewed promotions) as primary and
 * list (what is billed before credits) as secondary, plus a "promo" chip when they differ.
 * `compact` hides the labels and the list value when both are equal (tables, cards).
 */
export function Money({
  usd,
  status = 'verified',
  className,
  digits,
  dot = true,
  effective,
  promos,
  compact,
}: {
  usd: number | null | undefined
  status?: CostStatus | string | null
  className?: string
  digits?: number
  dot?: boolean
  effective?: number | null
  promos?: string | string[] | null
  compact?: boolean
}) {
  status = status ?? 'pending'
  const list = status === 'pt' ? 0 : usd
  if (effective === undefined)
    return (
      <span className={cn('inline-flex items-center gap-1.5 font-mono num', className)}>
        {dot && <CostDot status={status} />}
        <span className={status === 'unpriced' ? 'text-muted' : undefined}>{fmtUsd(list, status, digits)}</span>
        {status === 'pt' && <span className="rounded border border-line-strong px-1 text-[9.5px] font-semibold text-muted">PT</span>}
      </span>
    )
  const eff = status === 'pt' ? 0 : effective
  const differ = list != null && eff != null && Number.isFinite(list) && Number.isFinite(eff) && Math.abs(list - eff) > 1e-7
  return (
    <span className={cn('inline-flex items-baseline gap-x-1.5 gap-y-0.5 font-mono num', compact ? 'whitespace-nowrap' : 'flex-wrap', className)}>
      {dot && <span className="self-center"><CostDot status={status} /></span>}
      <span className={status === 'unpriced' ? 'text-muted' : undefined}>{fmtUsd(eff ?? list, status, digits)}</span>
      {(!compact || differ) && <span className="font-sans text-[0.72em] text-muted">{compact ? 'eff' : 'effective'}</span>}
      {(!compact || differ) && status !== 'unpriced' && (
        <span className="text-[0.82em] text-muted">
          · {fmtUsd(list, status, digits)} <span className="font-sans text-[0.88em]">list</span>
        </span>
      )}
      {differ && <PromoChip promos={promos} />}
      {!compact && !differ && <PendingHint />}
      {status === 'pt' && <span className="rounded border border-line-strong px-1 text-[9.5px] font-semibold text-muted">PT</span>}
    </span>
  )
}

export function PromoChip({ promos }: { promos?: string | string[] | null }) {
  const { data } = usePricing()
  const items = findPromos(data?.promotions, promos)
  return (
    <Tip
      content={
        <div className="max-w-[300px] space-y-1.5">
          <div className="font-medium">Promotional credits applied</div>
          {items.length === 0 && <div className="text-muted">Promotion ids not reported for this figure.</div>}
          {items.map(({ id, p }) => (
            <div key={id}>
              <div className="font-mono text-[10.5px]">{id}</div>
              {p && <div className="text-muted">{p.mechanism}{p.until ? ` · until ${String(p.until)}` : ''}</div>}
            </div>
          ))}
          <div className="border-t border-line pt-1 text-muted">Promotions are credits: usage is billed at list price and the discount is credited back. The list figure is what the invoice line shows before credits.</div>
        </div>
      }
    >
      <span className="inline-flex h-[15px] items-center self-center rounded-[4px] border border-accent-line bg-accent-soft px-1 font-sans text-[9.5px] font-semibold uppercase tracking-wide text-accent">promo</span>
    </Tip>
  )
}

function PendingHint() {
  const { data } = usePricing()
  if (!data || data.promotions_reviewed !== false) return null
  return (
    <Tip content="Promotions published on the pricing page have not been reviewed yet, so the engine applies none: effective = list until a human signs them off.">
      <span className="self-center font-sans text-[10px] text-warn">promotions pending review</span>
    </Tip>
  )
}

export function CostLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
      {(['verified', 'check', 'unpriced'] as CostStatus[]).map((s) => (
        <span key={s} className="inline-flex items-center gap-1.5">
          <CostDot status={s} /> {COST_META[s].label}
        </span>
      ))}
    </div>
  )
}

export const costMeta = COST_META as Record<string, CostMeta>

// ---------- status ----------
type AnyStatus = AttemptStatus | TrialStatus | string

const STATUS_COLOR: Record<string, string> = {
  passed: 'var(--pass)',
  failed: 'var(--fail)',
  running: 'var(--run)',
  verifying: 'var(--cost-verified)',
  preparing: 'var(--idle)',
  admitted: 'var(--idle)',
  queued: 'var(--idle)',
  backoff: 'var(--warn)',
  interrupted: 'var(--warn)',
  error: 'var(--fail)',
  engine_error: 'var(--idle)',
  infra_failed: 'var(--warn)',
  invalid_routing: 'var(--fail)',
  na: 'var(--line-strong)',
  completed: 'var(--pass)',
  paused: 'var(--warn)',
  cancelled: 'var(--idle)',
}
export const statusColor = (s: AnyStatus | null | undefined) => (s != null && STATUS_COLOR[String(s)]) || 'var(--idle)'
export const statusLabel = (s: AnyStatus | null | undefined) => (s == null || s === '' ? 'pending' : s === 'na' ? 'N/A' : String(s).replace(/_/g, ' '))

export function StatusPill({ status, className }: { status: AnyStatus | null | undefined; className?: string }) {
  const c = statusColor(status)
  const live = status === 'running' || status === 'verifying'
  return (
    <span
      className={cn('inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-full border px-2 text-[11px] font-medium leading-none first-letter:uppercase', className)}
      style={{ color: c, borderColor: `color-mix(in oklab, ${c} 35%, transparent)`, background: `color-mix(in oklab, ${c} 10%, transparent)` }}
    >
      <span className={cn('size-1.5 rounded-full', live && 'tape-running')} style={{ background: c }} />
      {statusLabel(status)}
    </span>
  )
}

// ---------- tokens ----------
export const TOKEN_CATS = [
  { key: 'input', label: 'Uncached input', color: 'var(--tok-input)' },
  { key: 'cache_read', label: 'Cache read', color: 'var(--tok-cache-read)' },
  { key: 'cache_write', label: 'Cache write', color: 'var(--tok-cache-write)' },
  { key: 'output', label: 'Output', color: 'var(--tok-output)' },
  { key: 'thinking', label: 'Thinking', color: 'var(--tok-thinking)' },
] as const
export type TokKey = (typeof TOKEN_CATS)[number]['key']
export type TokVec = Record<TokKey, number>

export function TokenBar({ t, height = 6, className, showTotal }: { t: TokVec; height?: number; className?: string; showTotal?: boolean }) {
  const total = TOKEN_CATS.reduce((s, c) => s + (Number(t[c.key]) || 0), 0)
  return (
    <div className={cn('flex items-center gap-2', className)}>
      <Tip
        content={
          <div className="grid grid-cols-[auto_auto_auto] gap-x-3 gap-y-0.5 font-mono text-[11px]">
            {TOKEN_CATS.map((c) => (
              <div key={c.key} className="contents">
                <span className="flex items-center gap-1.5 font-sans">
                  <span className="size-2 rounded-[2px]" style={{ background: c.color }} />
                  {c.label}
                </span>
                <span className="text-right num">{fmtTok(t[c.key])}</span>
                <span className="text-right text-muted num">{total ? (((Number(t[c.key]) || 0) / total) * 100).toFixed(0) : 0}%</span>
              </div>
            ))}
          </div>
        }
      >
        <div className="flex w-full overflow-hidden rounded-full bg-sunken" style={{ height }}>
          {TOKEN_CATS.map((c) => {
            const w = total ? ((Number(t[c.key]) || 0) / total) * 100 : 0
            return <motion.div key={c.key} className="h-full" style={{ background: c.color }} initial={false} animate={{ width: `${w}%` }} transition={{ duration: 0.6, ease: [0.2, 0.8, 0.2, 1] }} />
          })}
        </div>
      </Tip>
      {showTotal && <span className="shrink-0 font-mono text-[11px] text-fg-2 num">{fmtTok(total)}</span>}
    </div>
  )
}

export function TokenLegend({ className }: { className?: string }) {
  return (
    <div className={cn('flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted', className)}>
      {TOKEN_CATS.map((c) => (
        <span key={c.key} className="inline-flex items-center gap-1.5">
          <span className="size-2 rounded-[2px]" style={{ background: c.color }} />
          {c.label}
        </span>
      ))}
    </div>
  )
}

// ---------- tools ----------
export function ToolTicker({ tools, counts, className }: { tools: ToolCall[]; counts: { ok: number; fail: number; retry: number }; className?: string }) {
  const recent = tools.slice(-14)
  return (
    <div className={cn('flex min-w-0 items-center gap-2', className)}>
      <div className="flex shrink-0 items-center gap-2 font-mono text-[11px] num">
        <span className="text-pass">✓{counts.ok}</span>
        <span className="text-fail">✗{counts.fail}</span>
        <span className="text-warn">↻{counts.retry}</span>
      </div>
      <div className="flex min-w-0 flex-1 items-center justify-end gap-[3px] overflow-hidden">
        {recent.map((t) => {
          const c = t.is_retry ? 'var(--warn)' : t.status === 'ok' ? 'var(--pass)' : 'var(--fail)'
          return (
            <Tip key={t.id} content={<span className="font-mono">{t.name} · {t.is_retry ? 'retry' : t.status}{t.error_code ? ` · ${t.error_code}` : ''}</span>}>
              <motion.span
                initial={{ opacity: 0, scaleY: 0.2 }}
                animate={{ opacity: 1, scaleY: 1 }}
                className="block h-3 w-[5px] shrink-0 origin-bottom rounded-[1.5px]"
                style={{ background: `color-mix(in oklab, ${c} 85%, transparent)` }}
              />
            </Tip>
          )
        })}
      </div>
    </div>
  )
}

// ---------- attempts ----------
export function AttemptPips({ idx, max = 4, status }: { idx: number; max?: number; status: AttemptStatus | string }) {
  return (
    <Tip content={`Attempt ${idx} of ${max} (1 + ${max - 1} task retries)`}>
      <span className="inline-flex items-center gap-1.5">
        <span className="flex gap-[3px]">
          {Array.from({ length: max }, (_, i) => {
            const n = i + 1
            const bg = n < idx ? 'var(--fail)' : n === idx ? statusColor(status) : 'var(--line-strong)'
            return <span key={i} className={cn('h-2.5 w-1.5 rounded-[1.5px]', n === idx && (status === 'running' || status === 'verifying') && 'tape-running')} style={{ background: bg, opacity: n < idx ? 0.55 : 1 }} />
          })}
        </span>
        <span className="font-mono text-[11px] text-muted num">
          {idx}/{max}
        </span>
      </span>
    </Tip>
  )
}

// ---------- KPI ----------
export function Kpi({ label, value, sub, accent, children, className }: { label: ReactNode; value: ReactNode; sub?: ReactNode; accent?: string; children?: ReactNode; className?: string }) {
  return (
    <div className={cn('panel relative flex min-w-0 flex-col gap-1 overflow-hidden px-4 py-3', className)}>
      <div className="eyebrow">{label}</div>
      <div className="flex items-baseline gap-2 font-mono text-[22px] font-medium tracking-[-0.02em] num" style={accent ? { color: accent } : undefined}>
        {value}
      </div>
      {sub && <div className="truncate text-[11.5px] text-muted">{sub}</div>}
      {children}
    </div>
  )
}

export function Spark({ data, color = 'var(--accent)', height = 28, className, fill = true }: { data: number[]; color?: string; height?: number; className?: string; fill?: boolean }) {
  if (data.length < 2) return <div style={{ height }} className={className} />
  const w = 120
  const min = Math.min(...data)
  const max = Math.max(...data)
  const sx = (i: number) => (i / (data.length - 1)) * w
  const sy = (v: number) => height - 2 - ((v - min) / (max - min || 1)) * (height - 4)
  const d = data.map((v, i) => `${i ? 'L' : 'M'}${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join('')
  return (
    <svg viewBox={`0 0 ${w} ${height}`} preserveAspectRatio="none" className={cn('w-full', className)} style={{ height }} aria-hidden>
      {fill && <path d={`${d}L${w},${height}L0,${height}Z`} fill={color} opacity={0.12} />}
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

/** Horizontal CI bar for leaderboards: domain 0..max, point + whiskers. */
export function CIBar({ v, lo, hi, max = 1, color = 'var(--accent)', width = 120 }: { v: number; lo: number; hi: number; max?: number; color?: string; width?: number }) {
  const x = (n: number) => Math.max(0, Math.min(width, (n / max) * width))
  return (
    <svg width={width} height={14} aria-hidden className="overflow-visible">
      <line x1={0} x2={width} y1={7} y2={7} stroke="var(--line)" strokeWidth={1} />
      <rect x={x(lo)} y={4} width={Math.max(1, x(hi) - x(lo))} height={6} rx={3} fill={color} opacity={0.22} />
      <circle cx={x(v)} cy={7} r={3.5} fill={color} />
    </svg>
  )
}

export function Meter({ pct, color = 'var(--accent)', warnAt = 0.8, className }: { pct: number; color?: string; warnAt?: number; className?: string }) {
  const c = pct >= 1 ? 'var(--fail)' : pct >= warnAt ? 'var(--warn)' : color
  return (
    <div className={cn('relative h-1.5 w-full overflow-hidden rounded-full bg-sunken', className)}>
      <motion.div className="h-full rounded-full" style={{ background: c }} initial={false} animate={{ width: `${Math.min(100, pct * 100)}%` }} transition={{ duration: 0.5 }} />
      <span className="absolute top-0 h-full w-px bg-[var(--warn)] opacity-60" style={{ left: `${warnAt * 100}%` }} />
    </div>
  )
}

/** thinking_verified badge: green on "match", amber otherwise. */
export function ThinkingBadge({ configured, verified, raw }: { configured?: string | null; verified?: string | null; raw?: string | null }) {
  if (!verified)
    return configured ? (
      <Tip content={raw ? <pre className="whitespace-pre-wrap font-mono text-[10.5px]">{raw}</pre> : configured}>
        <span className="block max-w-[220px] truncate font-mono text-[10.5px] text-muted">{configured}</span>
      </Tip>
    ) : null
  const ok = verified === 'match'
  const c = ok ? 'var(--pass)' : 'var(--warn)'
  return (
    <Tip
      content={
        <div className="space-y-1">
          <div>{ok ? 'Thinking level confirmed from the Meter (request fields + thoughts tokens).' : `Thinking verification: ${verified.split('+').join(', ')}. The harness may have ignored or altered the configured level.`}</div>
          {raw && <pre className="max-w-[320px] whitespace-pre-wrap break-all font-mono text-[10.5px] text-muted">{raw}</pre>}
        </div>
      }
    >
      <span className="inline-flex h-[18px] items-center gap-1 whitespace-nowrap rounded border px-1.5 font-mono text-[10px]" style={{ color: c, borderColor: `color-mix(in oklab, ${c} 35%, transparent)`, background: `color-mix(in oklab, ${c} 9%, transparent)` }}>
        {configured && <span className="max-w-[180px] truncate text-fg-2">{configured}</span>}
        {ok ? '✓' : '⚠'} {verified}
      </span>
    </Tip>
  )
}
