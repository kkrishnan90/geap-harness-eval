// Public read-only vs admin (IAP-protected) mode.
import { useSyncExternalStore } from 'react'

export interface Me {
  admin: boolean
  email: string | null
  readonly: boolean
}

/** "/admin" when the SPA is served under the IAP-protected prefix, else "". */
export const BASE_PATH = typeof window !== 'undefined' && /^\/admin(\/|$)/.test(window.location.pathname) ? '/admin' : ''

/** Mutating API calls go through /api/admin/* when under the admin prefix. */
export const WRITE_API = BASE_PATH === '/admin' ? '/api/admin' : '/api'

let me: Me = { admin: true, email: null, readonly: false }
const subs = new Set<() => void>()

export async function initMe(mode: 'live' | 'mock'): Promise<Me> {
  if (mode === 'mock') {
    let pub = new URLSearchParams(location.search).get('admin') === '0'
    try {
      if (pub) sessionStorage.setItem('geap.mockPublic', '1')
      else if (new URLSearchParams(location.search).get('admin') === '1') sessionStorage.removeItem('geap.mockPublic')
      pub = pub || sessionStorage.getItem('geap.mockPublic') === '1'
    } catch {
      /* storage blocked */
    }
    me = pub ? { admin: false, email: null, readonly: true } : { admin: true, email: 'admin@example.com', readonly: false }
  } else {
    try {
      const r = await fetch('/api/me', { headers: { accept: 'application/json' } })
      const ct = r.headers.get('content-type') ?? ''
      if (r.ok && ct.includes('json')) {
        const j = (await r.json()) as Partial<Me>
        me = { admin: !!j.admin, email: j.email ?? null, readonly: j.readonly ?? !j.admin }
      } else me = { admin: true, email: null, readonly: false } // 404 / SPA fallback: local or dev server without auth
    } catch {
      me = { admin: true, email: null, readonly: false }
    }
  }
  subs.forEach((f) => f())
  return me
}

export const getMe = () => me
export function useMe(): Me {
  return useSyncExternalStore(
    (f) => {
      subs.add(f)
      return () => subs.delete(f)
    },
    () => me,
    () => me,
  )
}

/** Full-page URL to the admin (IAP) version of a path, so IAP can authenticate. */
export function adminHref(path = location.pathname.replace(/^\/admin/, '') || '/build'): string {
  return `/admin${path.startsWith('/') ? path : '/' + path}${location.search}`
}

// ---- tiny toast store ----
export interface Toast {
  id: number
  title: string
  body?: string
  href?: string
  hrefLabel?: string
}
let toasts: Toast[] = []
const tsubs = new Set<() => void>()
let tid = 0
export function toast(t: Omit<Toast, 'id'>) {
  const id = ++tid
  toasts = [...toasts, { ...t, id }]
  tsubs.forEach((f) => f())
  setTimeout(() => dismissToast(id), 8000)
}
export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id)
  tsubs.forEach((f) => f())
}
export function useToasts(): Toast[] {
  return useSyncExternalStore(
    (f) => {
      tsubs.add(f)
      return () => tsubs.delete(f)
    },
    () => toasts,
    () => toasts,
  )
}

/** Call after a failed write: shows the sign-in toast for 401/403 and returns true if handled. */
export function handleWriteError(err: unknown): boolean {
  const status = (err as { status?: number })?.status
  if (status === 401 || status === 403) {
    toast({ title: 'Admin sign-in required', body: 'Launching and controlling runs is limited to admins.', href: adminHref(), hrefLabel: 'Sign in as admin' })
    return true
  }
  return false
}
