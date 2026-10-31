import type { CostStatus } from './types'

export function fmtUsd(v: number | null | undefined, status?: CostStatus | string | null, digits?: number): string {
  if (status === 'unpriced' || v == null || !Number.isFinite(Number(v))) return '—'
  v = Number(v)
  const d = digits ?? (v === 0 ? 2 : Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 1 ? 2 : Math.abs(v) >= 0.01 ? 3 : 4)
  return '$' + v.toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}

export function fmtTok(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  v = Number(v)
  const a = Math.abs(v)
  if (a >= 1e9) return (v / 1e9).toFixed(2) + 'B'
  if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 1 : 2) + 'M'
  if (a >= 1e3) return (v / 1e3).toFixed(a >= 1e4 ? 0 : 1) + 'k'
  return String(Math.round(v))
}

export function fmtInt(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(Number(v))) return '—'
  return Math.round(v).toLocaleString('en-US')
}

export function fmtPct(v: number | null | undefined, digits = 0): string {
  if (v == null || Number.isNaN(v)) return '—'
  return (v * 100).toFixed(digits) + '%'
}

export function fmtDur(s: number | null | undefined): string {
  if (s == null || Number.isNaN(s)) return '—'
  const t = Math.max(0, Math.round(s))
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const sec = t % 60
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`
  if (m) return `${m}:${String(sec).padStart(2, '0')}`
  return `${sec}s`
}

export function fmtClock(s: number | null | undefined): string {
  if (s == null || !Number.isFinite(s)) return '—'
  const t = Math.max(0, Math.floor(s))
  const m = Math.floor(t / 60)
  const sec = t % 60
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

export function fmtTime(epoch: number | null | undefined): string {
  if (!epoch) return '—'
  return new Date(epoch * 1000).toLocaleTimeString('en-GB', { hour12: false })
}

export function fmtDateTime(epoch: number | null | undefined): string {
  if (!epoch) return '—'
  const d = new Date(epoch * 1000)
  return d.toLocaleDateString('en-CA') + ' ' + d.toLocaleTimeString('en-GB', { hour12: false, hour: '2-digit', minute: '2-digit' })
}

export function ago(epoch: number | null | undefined): string {
  if (!epoch) return '—'
  const s = Date.now() / 1000 - epoch
  if (s < 60) return `${Math.round(s)}s ago`
  if (s < 3600) return `${Math.round(s / 60)}m ago`
  if (s < 86400) return `${Math.round(s / 3600)}h ago`
  return `${Math.round(s / 86400)}d ago`
}

/** Compact human label for a raw thinking request (Meter JSON or plain level). */
export function thinkingLabel(raw: string | null | undefined): string {
  if (!raw) return '—'
  let j: unknown
  try {
    j = JSON.parse(raw)
  } catch {
    return raw
  }
  if (typeof j !== 'object' || j === null) return String(j)
  const find = (o: unknown, key: string): unknown => {
    if (!o || typeof o !== 'object') return undefined
    const r = o as Record<string, unknown>
    if (key in r) return r[key]
    for (const v of Object.values(r)) {
      const f = find(v, key)
      if (f !== undefined) return f
    }
    return undefined
  }
  const level = find(j, 'thinkingLevel') ?? find(j, 'thinking_level')
  if (level != null) return `thinkingLevel ${String(level).toUpperCase()}`
  const budget = find(j, 'thinkingBudget') ?? find(j, 'thinking_budget') ?? find(j, 'budget_tokens')
  const thinking = find(j, 'thinking') as Record<string, unknown> | undefined
  const effort = find(j, 'effort')
  if (thinking && typeof thinking === 'object' && 'type' in thinking) {
    const t = String(thinking.type)
    if (t === 'disabled') return 'thinking off'
    return [t, effort != null ? `effort ${String(effort)}` : budget != null ? `budget ${String(budget)}` : null].filter(Boolean).join(' · ')
  }
  if (budget != null) return `thinkingBudget ${String(budget)}`
  if (effort != null) return `effort ${String(effort)}`
  return raw.length > 40 ? raw.slice(0, 40) + '…' : raw
}
