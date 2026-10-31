import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function harnessKey(h: { harness?: string; name?: string; variant?: string | null }): string {
  const name = h.harness ?? h.name ?? '?'
  const v = h.variant
  return v && v !== 'default' ? `${name}/${v}` : name
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim()
}
