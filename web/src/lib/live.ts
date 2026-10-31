// Client-side accumulation of the SSE stream for one run. Mission Control, Quota & Health
// and the top bar read from here via useLive(selector).
import { useSyncExternalStore, useRef, useCallback } from 'react'
import type { Attempt, BudgetEvt, InfraEvt, LlmCall, LogEvt, RunEvt, StreamEvent, TickEvt, ToolCall, Trial } from './types'
import { api, subscribeStream } from './api'

export interface LiveState {
  runId: string | null
  connected: 'idle' | 'open' | 'error'
  run: RunEvt | null
  attempts: Record<string, Attempt>
  ticks: Record<string, TickEvt & { at: number }>
  tools: Record<string, ToolCall[]> // last N per attempt
  trials: Record<string, Trial>
  infra: (InfraEvt & { ts: number })[]
  budget: BudgetEvt | null
  logs: (LogEvt & { ts: number })[]
  spend: [number, number][]
  calls429: number
  callsTotal: number
  version: number
  runAt: number
  logSource: 'loading' | 'persisted' | 'unavailable'
}

const initial = (): LiveState => ({
  runId: null,
  connected: 'idle',
  run: null,
  attempts: {},
  ticks: {},
  tools: {},
  trials: {},
  infra: [],
  budget: null,
  logs: [],
  spend: [],
  calls429: 0,
  callsTotal: 0,
  version: 0,
  runAt: 0,
  logSource: 'loading',
})

let state: LiveState = initial()
const subs = new Set<() => void>()
let unsub: (() => void) | null = null
let runTimer: number | null = null
let pending = false
const hydrating = new Set<string>()

function notify() {
  if (pending) return
  pending = true
  // coalesce bursts into one render per frame
  requestAnimationFrame(() => {
    pending = false
    state = { ...state, version: state.version + 1 }
    subs.forEach((f) => f())
  })
}

function hydrateAttempt(id: string) {
  if (hydrating.has(id) || state.attempts[id]) return
  hydrating.add(id)
  api
    .attempt(id)
    .then((a) => {
      const { llm_calls, tool_calls, events: _e, ...row } = a
      void _e
      state.attempts = { ...state.attempts, [id]: { ...row, llm_calls: llm_calls.length, tool_calls: tool_calls.filter((t) => !t.parent_id).length } }
      state.tools = { ...state.tools, [id]: tool_calls.filter((t) => !t.parent_id).slice(-24) }
      notify()
    })
    .catch(() => {})
}

function onEvent(e: StreamEvent) {
  const s = state
  switch (e.type) {
    case 'run':
      s.run = e.data
      s.runAt = Date.now()
      s.spend = [...s.spend.slice(-1800), [Date.now() / 1000, e.data.spend_usd]]
      break
    case 'trial':
      s.trials = { ...s.trials, [e.data.id]: e.data }
      break
    case 'attempt': {
      const t = s.trials[e.data.trial_id]
      const row = { ...e.data, harness: e.data.harness ?? t?.harness, variant: e.data.variant ?? t?.variant, profile_id: e.data.profile_id ?? t?.profile_id, task_id: e.data.task_id ?? t?.task_id }
      s.attempts = { ...s.attempts, [e.data.id]: row }
      break
    }
    case 'tick':
      if (!s.attempts[e.data.attempt_id]) hydrateAttempt(e.data.attempt_id)
      s.ticks = { ...s.ticks, [e.data.attempt_id]: { ...e.data, at: Date.now() } }
      break
    case 'tool_call': {
      if (e.data.parent_id) break
      const arr = s.tools[e.data.attempt_id] ?? []
      s.tools = { ...s.tools, [e.data.attempt_id]: [...arr.slice(-23), e.data] }
      break
    }
    case 'llm_call': {
      const c = e.data as LlmCall
      s.callsTotal++
      if (c.http_status === 429) s.calls429++
      break
    }
    case 'infra':
      s.infra = [...s.infra.slice(-2999), { ...e.data, ts: e.data.ts ?? Date.now() / 1000 }]
      break
    case 'budget':
      s.budget = e.data
      break
    case 'log': {
      const line = { ...e.data, ts: e.data.ts ?? Date.now() / 1000 }
      if (s.logs.some((l) => l.msg === line.msg && Math.abs(l.ts - line.ts) < 1)) break
      s.logs = [...s.logs.slice(-499), line]
      break
    }
  }
  notify()
}

export function connectRun(runId: string | null) {
  if (state.runId === runId) return
  unsub?.()
  unsub = null
  if (runTimer != null) window.clearInterval(runTimer)
  runTimer = null
  state = { ...initial(), runId }
  notify()
  if (!runId) return
  // seed trials so attempt cards know their harness/profile/task
  api
    .trials(runId)
    .then((ts) => {
      const m: Record<string, Trial> = {}
      for (const t of ts) m[t.id] = t
      state.trials = { ...m, ...state.trials }
      notify()
    })
    .catch(() => {})
  import('./api').then(({ mockSpendHistory }) =>
    mockSpendHistory(runId).then((h) => {
      if (h.length) {
        state.spend = [...h.slice(-600), ...state.spend]
        notify()
      }
    }),
  )
  // seed / refresh run KPIs from the REST detail (the server emits `run` events only on change)
  const seedRun = () =>
    api
      .run(runId)
      .then((r) => {
        if (state.runId !== runId) return
        const fresh = !state.runAt || Date.now() - state.runAt > 8000
        if (fresh && r.progress) {
          state.run = { run_id: r.id, status: r.status, progress: r.progress, spend_usd: r.spend_usd ?? 0, burn_usd_per_min: r.burn_usd_per_min ?? state.run?.burn_usd_per_min ?? null, spend_effective_usd: r.spend_effective_usd }
          notify()
        }
      })
      .catch(() => {})
  seedRun()
  // persisted scheduler lines first, then live SSE `log` events append (deduped by ts + msg)
  api
    .runLog(runId)
    .then((lines) => {
      if (state.runId !== runId) return
      if (!lines) {
        state.logSource = 'unavailable'
      } else {
        const key = (l: { ts?: number; msg: string }) => `${Math.round(l.ts ?? 0)}|${l.msg}`
        const seen = new Set(lines.map(key))
        const extra = state.logs.filter((l) => !seen.has(key(l)))
        state.logs = [...lines.map((l) => ({ ...l, ts: l.ts ?? 0 })), ...extra].sort((a, b) => a.ts - b.ts).slice(-500)
        state.logSource = 'persisted'
      }
      notify()
    })
    .catch(() => {
      state.logSource = 'unavailable'
      notify()
    })
  runTimer = window.setInterval(seedRun, 10_000)
  unsub = subscribeStream(runId, onEvent, (st) => {
    state.connected = st
    notify()
  })
}

export function useLive<T>(sel: (s: LiveState) => T): T {
  const selRef = useRef(sel)
  selRef.current = sel
  const get = useCallback(() => selRef.current(state), [])
  const subscribe = useCallback((f: () => void) => {
    subs.add(f)
    return () => subs.delete(f)
  }, [])
  // selector results must be referentially stable per version; we compute on each version tick
  const cache = useRef<{ v: number; out: T } | null>(null)
  const getSnap = useCallback(() => {
    if (cache.current && cache.current.v === state.version) return cache.current.out
    const out = get()
    cache.current = { v: state.version, out }
    return out
  }, [get])
  return useSyncExternalStore(subscribe, getSnap, getSnap)
}

export const liveState = () => state
