import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Trial } from '@/lib/types'
import { harnessKey, cn } from '@/lib/utils'
import { harnessColor, harnessLabelKey } from '@/lib/labels'
import { statusColor } from './domain'
import { Tip } from './ui/tooltip'

/**
 * The tape: every trial in the run as one cell, one lane per harness × profile.
 * Reads left-to-right in task order; repeats stack as adjacent cells.
 */
export function TrialTape({ trials, compact, className, maxAttempts = 4 }: { trials: Trial[]; compact?: boolean; className?: string; maxAttempts?: number }) {
  const nav = useNavigate()
  const lanes = useMemo(() => {
    const m = new Map<string, Trial[]>()
    for (const t of trials) {
      const k = `${harnessKey(t)}|${t.profile_id}`
      if (!m.has(k)) m.set(k, [])
      m.get(k)!.push(t)
    }
    for (const v of m.values()) v.sort((a, b) => a.task_id.localeCompare(b.task_id) || a.repeat_idx - b.repeat_idx)
    return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]))
  }, [trials])
  const cellH = compact ? 11 : 14
  const naLanes = lanes.filter(([, ts]) => ts.every((t) => t.status === 'na'))
  const shown = lanes.filter(([, ts]) => !ts.every((t) => t.status === 'na'))
  const cols = Math.max(1, ...shown.map(([, ts]) => ts.length))
  return (
    <div className={cn('flex flex-col gap-[5px]', className)}>
      {shown.map(([k, ts]) => {
        const [h, p] = k.split('|')
        const na = ts.every((t) => t.status === 'na')
        const done = ts.filter((t) => t.status === 'passed' || t.status === 'failed').length
        const pass = ts.filter((t) => t.status === 'passed').length
        return (
          <div key={k} className={cn('flex items-center gap-3', na && 'opacity-40')}>
            <div className="flex w-[112px] shrink-0 items-center gap-2 text-[11.5px] sm:w-[218px]">
              <span className="h-3 w-[3px] rounded-full" style={{ background: harnessColor(h) }} />
              <span className="truncate font-medium text-fg-2">{harnessLabelKey(h)}</span>
              <span className="hidden truncate font-mono text-[10.5px] text-muted sm:inline">{p}</span>
            </div>
            <div className="grid min-w-0 flex-1 gap-[2px]" style={{ gridTemplateColumns: `repeat(${cols}, minmax(2px, ${cols < 24 ? '18px' : '1fr'}))` }}>
              {ts.map((t) => {
                const c = statusColor(t.status)
                const firstTry = t.status === 'passed' && t.passed_on_attempt === 1
                return (
                  <Tip
                    key={t.id}
                    content={
                      <div className="space-y-0.5">
                        <div className="font-medium">{t.task_id}</div>
                        <div className="font-mono text-[10.5px] text-muted">
                          {harnessLabelKey(h)} · {p} · rep {t.repeat_idx + 1}
                        </div>
                        <div className="text-[11px]">
                          <span style={{ color: c }} className="capitalize">
                            {t.status.replace('_', ' ')}
                          </span>
                          {t.status === 'passed' && <span className="text-muted"> on attempt {t.passed_on_attempt}</span>}
                          {t.status === 'failed' && <span className="text-muted"> after {t.attempts_used} attempts</span>}
                          {t.status === 'running' && <span className="text-muted"> · attempt {t.attempts_used}/{maxAttempts}</span>}
                          {t.status === 'na' && t.na_reason && <div className="mt-0.5 max-w-[280px] text-muted">{t.na_reason}</div>}
                          {(t.infra_retries ?? 0) > 0 && <span className="text-warn"> · {t.infra_retries} infra retries</span>}
                        </div>
                      </div>
                    }
                  >
                    <button
                      aria-label={`${t.task_id} ${t.status}`}
                      onClick={() => t.status !== 'na' && t.status !== 'queued' && nav(`/inspect/${t.id}`)}
                      className={cn('w-full rounded-[2px] transition-transform hover:scale-y-[1.3] focus-visible:scale-y-[1.3]', t.status === 'running' && 'tape-running')}
                      style={{
                        height: cellH,
                        background: t.status === 'queued' ? 'transparent' : t.status === 'na' ? 'repeating-linear-gradient(135deg, var(--line) 0 2px, transparent 2px 4px)' : c,
                        boxShadow: t.status === 'queued' ? 'inset 0 0 0 1px var(--line-strong)' : undefined,
                        opacity: t.status === 'passed' && !firstTry ? 0.6 : 1,
                      }}
                    />
                  </Tip>
                )
              })}
            </div>
            <div className="hidden w-[64px] shrink-0 text-right font-mono text-[10.5px] text-muted num sm:block">{na ? 'n/a' : `${pass}/${done || 0}`}</div>
          </div>
        )
      })}
      {naLanes.length > 0 && (
        <Tip
          content={
            <div className="space-y-0.5 font-mono text-[10.5px]">
              {naLanes.map(([k, ts]) => (
                <div key={k}>
                  {harnessLabelKey(k.split('|')[0])} · {k.split('|')[1]}
                  {ts[0]?.na_reason && <div className="pl-3 font-sans text-muted">{ts[0].na_reason}</div>}
                </div>
              ))}
            </div>
          }
        >
          <div className="mt-1 w-fit cursor-default pl-[14px] text-[11px] text-muted">
            + {naLanes.length} harness × profile lanes not applicable (hover for reasons)
          </div>
        </Tip>
      )}
    </div>
  )
}

export function TapeLegend() {
  const items: [string, string, number?][] = [
    ['Passed first try', 'var(--pass)'],
    ['Passed on retry', 'var(--pass)', 0.6],
    ['Failed', 'var(--fail)'],
    ['Running', 'var(--run)'],
  ]
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted">
      {items.map(([l, c, o]) => (
        <span key={l} className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-[7px] rounded-[1.5px]" style={{ background: c, opacity: o ?? 1 }} />
          {l}
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-[7px] rounded-[1.5px] shadow-[inset_0_0_0_1px_var(--line-strong)]" />
        Queued
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-[7px] rounded-[1.5px]" style={{ background: 'repeating-linear-gradient(135deg, var(--line-strong) 0 2px, transparent 2px 4px)' }} />
        N/A
      </span>
    </div>
  )
}
