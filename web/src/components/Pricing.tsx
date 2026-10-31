import { Check, X, Minus, ExternalLink } from 'lucide-react'
import { usePricing, daysLeft } from '@/lib/promos'
import { MODEL_SHORT } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { ago, fmtPct } from '@/lib/format'
import { Panel, Chip, Skeleton } from './ui/misc'
import { Tip } from './ui/tooltip'

type St = 'ok' | 'fail' | 'warn' | 'parked'

function Mark({ s }: { s: St }) {
  const c = s === 'ok' ? 'var(--pass)' : s === 'fail' ? 'var(--fail)' : s === 'warn' ? 'var(--warn)' : 'var(--idle)'
  return (
    <span className="flex size-5 shrink-0 items-center justify-center rounded-full" style={{ background: `color-mix(in oklab, ${c} 16%, transparent)`, color: c }}>
      {s === 'ok' ? <Check className="size-3" strokeWidth={3} /> : s === 'fail' ? <X className="size-3" strokeWidth={3} /> : <Minus className="size-3" strokeWidth={3} />}
    </span>
  )
}

/** Five validation layers behind every cost badge (PLAN §9.4). */
export function PriceValidation() {
  const { data: p } = usePricing()
  if (!p) return <Skeleton className="h-64" />
  const l4 = p.layer4
  const layers: { n: number; title: string; s: St; detail: React.ReactNode }[] = [
    { n: 1, title: 'Token integrity', s: 'ok', detail: 'Usage invariants per call and Plane A ↔ Plane B within 1%. Violations turn the figure 🟠 check.' },
    {
      n: 2,
      title: 'SKU map',
      s: p.reviewed === false ? 'warn' : p.reviewed ? 'ok' : 'warn',
      detail: p.reviewed ? <>Explicit sku_map reviewed and signed off against snapshot <span className="font-mono">{p.snapshot_id}</span>.</> : 'SKU map not yet signed off by a human; costs stay 🟠 check until reviewed.',
    },
    { n: 3, title: 'Golden tests', s: 'ok', detail: '20 hand-computed tests: tier boundaries (200,000 / 200,001), cache TTL variants, mixed roles; property tests for monotonicity and sums.' },
    {
      n: 4,
      title: 'Public-page cross-check',
      s: l4?.ok == null ? 'warn' : l4.ok ? 'ok' : 'fail',
      detail: l4 ? (
        <>
          {l4.checks.filter((c) => c.ok).length}/{l4.checks.length} rates match the published page{l4.fetched_at ? ` · fetched ${ago(l4.fetched_at)}` : ''}
          {l4.url && (
            <a href={l4.url} target="_blank" rel="noreferrer" className="ml-1.5 inline-flex items-center gap-0.5 text-accent hover:underline">
              source <ExternalLink className="size-3" />
            </a>
          )}
        </>
      ) : (
        'Not run yet.'
      ),
    },
    { n: 5, title: 'Billing export reconciliation', s: 'parked', detail: 'Parked (next revision): BigQuery billing export + request labels for 🟢 billed-reconciled.' },
  ]
  return (
    <Panel eyebrow="Why each cost badge is trustworthy" title="Price validation">
      <ol className="space-y-2.5">
        {layers.map((l) => (
          <li key={l.n} className="grid grid-cols-[20px_1fr] gap-3">
            <Mark s={l.s} />
            <div>
              <div className="flex items-center gap-2 text-[12.5px] font-medium">
                <span className="font-mono text-[10.5px] text-muted">L{l.n}</span> {l.title}
                {l.s === 'parked' && <Chip tone="muted">parked</Chip>}
              </div>
              <div className="text-[11.5px] text-muted">{l.detail}</div>
            </div>
          </li>
        ))}
      </ol>
      {l4 && l4.checks.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-[11.5px]">
            <thead>
              <tr className="border-b border-line text-[10.5px] text-muted">
                <th className="px-3 py-1.5 text-left font-medium">Model</th>
                <th className="px-3 py-1.5 text-left font-medium">Category</th>
                <th className="px-3 py-1.5 text-right font-medium">Catalog</th>
                <th className="px-3 py-1.5 text-right font-medium">Page</th>
                <th className="px-3 py-1.5 text-center font-medium">L4</th>
                <th className="px-3 py-1.5 text-left font-medium">Quote</th>
              </tr>
            </thead>
            <tbody>
              {l4.checks.map((c, i) => (
                <tr key={i} className={cn('border-b border-line/50 last:border-0', !c.ok && 'bg-[color-mix(in_oklab,var(--fail)_7%,transparent)]')}>
                  <td className="whitespace-nowrap px-3 py-1.5">{MODEL_SHORT[c.model] ?? c.model}</td>
                  <td className="px-3 py-1.5 font-mono text-muted">{c.category}</td>
                  <td className="px-3 py-1.5 text-right font-mono num">{c.catalog_per_1m != null ? `$${c.catalog_per_1m.toFixed(2)}` : '—'}</td>
                  <td className="px-3 py-1.5 text-right font-mono num">{c.page_per_1m != null ? `$${c.page_per_1m.toFixed(2)}` : '—'}</td>
                  <td className="px-3 py-1.5 text-center">{c.ok ? <span className="text-pass">✓</span> : <span className="text-fail">✗</span>}</td>
                  <td className="max-w-[340px] px-3 py-1.5">
                    <Tip content={c.quote ?? ''}>
                      <span className="block truncate text-muted">“{c.quote ?? '—'}”</span>
                    </Tip>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

export function PromotionsPanel() {
  const { data: p } = usePricing()
  const promos = p?.promotions ?? []
  return (
    <Panel
      eyebrow="Credits, not price changes"
      title="Promotions"
      actions={p ? p.promotions_reviewed ? <Chip tone="pass">reviewed · applied to effective cost</Chip> : <Chip tone="warn">pending review · not applied</Chip> : null}
      bodyClass="p-0"
    >
      {!p ? (
        <Skeleton className="m-4 h-24" />
      ) : promos.length === 0 ? (
        <div className="px-4 py-6 text-center text-[12px] text-muted">No promotions published for the models in the price book.</div>
      ) : (
        <div className="divide-y divide-line/60">
          {promos.map((x) => {
            const d = daysLeft(x.until)
            return (
              <div key={x.id} className="grid grid-cols-1 gap-2 px-4 py-3 md:grid-cols-[1fr_auto]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[12px] font-medium">{x.id}</span>
                    {x.models.map((m) => (
                      <Chip key={m}>{MODEL_SHORT[m] ?? m}</Chip>
                    ))}
                    <Chip tone="muted">{x.locality}</Chip>
                  </div>
                  <div className="mt-1 text-[11.5px] text-fg-2">{x.mechanism}</div>
                  <div className="mt-0.5 text-[11px] text-muted">
                    Factor:{' '}
                    {Object.entries(x.factor)
                      .map(([k, v]) => `${k} ×${v} (−${fmtPct(1 - (v ?? 1))})`)
                      .join(' · ')}
                  </div>
                  <Tip content={x.quote}>
                    <div className="mt-1 truncate text-[11px] italic text-muted">
                      “{x.quote}”{' '}
                      <a href={x.source} target="_blank" rel="noreferrer" className="not-italic text-accent hover:underline">
                        source
                      </a>
                    </div>
                  </Tip>
                </div>
                <div className="text-left md:text-right">
                  <div className="eyebrow">until {String(x.until)}</div>
                  <div className={cn('font-mono text-[18px] num', d < 0 ? 'text-muted' : d < 14 ? 'text-warn' : 'text-fg')}>{d < 0 ? 'expired' : `${Math.floor(d)}d ${Math.floor((d % 1) * 24)}h`}</div>
                  <div className="text-[10.5px] text-muted">{d < 0 ? 'no longer applied' : 'remaining'}</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Panel>
  )
}
