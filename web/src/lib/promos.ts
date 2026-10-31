import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { Promotion } from './types'

export function usePricing() {
  return useQuery({ queryKey: ['pricing'], queryFn: api.pricing, staleTime: 60_000 })
}

export function untilEpoch(u: string | number): number {
  if (typeof u === 'number') return u
  const d = Date.parse(u.length <= 10 ? `${u}T23:59:59Z` : u)
  return Number.isNaN(d) ? 0 : d / 1000
}

export function daysLeft(u: string | number): number {
  return (untilEpoch(u) - Date.now() / 1000) / 86400
}

export function findPromos(all: Promotion[] | undefined, ids: string | string[] | null | undefined): { id: string; p?: Promotion }[] {
  const list = (Array.isArray(ids) ? ids : (ids ?? '').split(',')).map((x) => x.trim()).filter(Boolean)
  return list.map((id) => ({ id, p: all?.find((x) => x.id === id) }))
}

/** Promotions that apply to a model (used when a row carries no explicit promo ids, e.g. aggregates). */
export function promosForModels(all: Promotion[] | undefined, models: string[]): string[] {
  return (all ?? []).filter((p) => p.models.some((m) => models.includes(m))).map((p) => p.id)
}
