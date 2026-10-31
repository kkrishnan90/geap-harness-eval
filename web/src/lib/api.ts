import type {
  AttemptDetail,
  DryRunResult,
  HarnessInfo,
  Health,
  ModelInfo,
  Preflight,
  PricingBook,
  GovernorLane,
  TaskDetail,
  LogEvt,
  InfraEvt,
  EgressRow,
  RunAggregate,
  RunConfig,
  RunDetail,
  RunSummaryRow,
  StreamEvent,
  TaskInfo,
  Trial,
  TrialDetail,
} from './types'

import { WRITE_API } from './auth'
import { normDryRun, normAttemptDetail, normLlmCall, normPricing, normRunEvt, normRunRow, normSummary, normToolCall, normTrial, normTrialDetail, normAttempt } from './normalize'

export type DataMode = 'live' | 'mock'
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type AnyRec = any

let mode: DataMode | null = null
let modeReason = ''
type MockMod = typeof import('@/mock/engine')
let mockMod: MockMod | null = null

async function eng() {
  if (!mockMod) mockMod = await import('@/mock/engine')
  return mockMod.engine()
}

/** Decide once at boot: VITE_MOCK=1 forces mock; otherwise probe /api/health. */
export async function initMode(): Promise<DataMode> {
  if (mode) return mode
  const forced = import.meta.env.VITE_MOCK === '1' || new URLSearchParams(location.search).get('mock') === '1'
  if (forced) {
    mode = 'mock'
    modeReason = 'VITE_MOCK=1'
  } else {
    try {
      const ctl = new AbortController()
      const to = setTimeout(() => ctl.abort(), 1800)
      const r = await fetch('/api/health', { signal: ctl.signal })
      clearTimeout(to)
      const j = (await r.json()) as Health
      mode = r.ok && j.ok ? 'live' : 'mock'
      modeReason = mode === 'live' ? `server ${j.version}` : '/api/health not ok'
    } catch {
      mode = 'mock'
      modeReason = '/api/health unreachable'
    }
  }
  if (mode === 'mock') await eng()
  return mode
}

export const getMode = () => mode ?? 'mock'
export const getModeReason = () => modeReason

class ApiError extends Error {
  status: number
  constructor(status: number, msg: string) {
    super(msg)
    this.status = status
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, headers: { 'content-type': 'application/json', ...(init?.headers ?? {}) } })
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`
    try {
      const j = await r.json()
      msg = j.detail ?? j.error ?? msg
    } catch {
      /* not json */
    }
    throw new ApiError(r.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  const ct = r.headers.get('content-type') ?? ''
  // An SPA fallback can answer unknown /api/* paths with index.html (200); treat that as a missing endpoint.
  if (ct.includes('text/html') && path.startsWith('/api/')) throw new ApiError(404, `${path.split('?')[0]} is not available on this server`)
  return (ct.includes('json') ? r.json() : r.text()) as Promise<T>
}

const delay = <T,>(v: T, ms = 120) => new Promise<T>((res) => setTimeout(() => res(structuredClone(v)), ms))

async function viaMock<T>(fn: (e: Awaited<ReturnType<typeof eng>>) => T | Promise<T>): Promise<T> {
  const e = await eng()
  return delay(await fn(e))
}

async function cat() {
  return import('@/mock/catalog')
}

export const api = {
  health: (): Promise<Health> => (getMode() === 'mock' ? delay({ ok: true, version: 'mock-0.1' }) : http('/api/health')),
  preflight: async (): Promise<Preflight> => (getMode() === 'mock' ? delay((await cat()).PREFLIGHT, 400) : http('/api/preflight')),
  models: async (): Promise<ModelInfo[]> => (getMode() === 'mock' ? delay((await cat()).MODELS) : http('/api/models')),
  harnesses: async (): Promise<HarnessInfo[]> => (getMode() === 'mock' ? delay((await cat()).HARNESSES) : http('/api/harnesses')),
  tasks: async (): Promise<TaskInfo[]> => (getMode() === 'mock' ? delay((await cat()).TASKS) : http('/api/tasks')),
  /** Whole-run Meter egress; rejects with status 404 on servers that predate the endpoint. */
  egress: (runId: string): Promise<EgressRow[]> => (getMode() === 'mock' ? viaMock((e) => e.runEgress(runId)) : http(`/api/runs/${runId}/egress`)),
  /** Persisted infra history for a run (429/503/backoff/aimd/breaker). [] on servers without the endpoint. */
  runInfra: async (runId: string): Promise<InfraEvt[]> => {
    if (getMode() === 'mock') return viaMock((e) => e.runInfra(runId))
    try {
      const r = await http<AnyRec[]>(`/api/runs/${runId}/infra`)
      return Array.isArray(r) ? r.map((e: AnyRec) => ({ ...e, ts: Number(e.ts), location: e.location ?? 'global' })) : []
    } catch (err) {
      if ((err as ApiError).status === 404) return []
      throw err
    }
  },
  /** Persisted scheduler log lines, oldest first; null when the server has no /log endpoint. */
  runLog: async (runId: string): Promise<LogEvt[] | null> => {
    if (getMode() === 'mock') return viaMock((e) => e.runLog(runId))
    try {
      const r = await http<AnyRec[]>(`/api/runs/${runId}/log`)
      return Array.isArray(r) ? r.map((l: AnyRec) => ({ level: l.level ?? 'info', msg: String(l.msg ?? l.message ?? ''), ts: Number(l.ts) })) : null
    } catch (err) {
      if ((err as ApiError).status === 404) return null
      throw err
    }
  },
  /** Task detail (ticket markdown, seed-repo files, hidden-test counts, history). null when the endpoint is unavailable. */
  task: async (id: string): Promise<TaskDetail | null> => {
    if (getMode() === 'mock') return viaMock((e) => e.taskDetail(id))
    try {
      const r = await http<AnyRec>(`/api/tasks/${id.split('/').map(encodeURIComponent).join('/')}`)
      return r && typeof r === 'object' ? ({ ...r, repo_files: r.repo_files ?? [], repo_file_count: r.repo_file_count ?? (r.repo_files ?? []).length } as TaskDetail) : null
    } catch (err) {
      if ((err as ApiError).status === 404) return null
      throw err
    }
  },
  governor: (): Promise<GovernorLane[]> => (getMode() === 'mock' ? viaMock((e) => e.governor()) : http('/api/governor')),
  diff: (id: string): Promise<string> => (getMode() === 'mock' ? viaMock((e) => e.diff(id)) : http(`/api/attempts/${id}/diff`)),
  pricing: async (): Promise<PricingBook> => normPricing((getMode() === 'mock' ? await delay((await cat()).PRICING) : await http('/api/pricing')) as AnyRec),
  runs: async (): Promise<RunSummaryRow[]> => ((getMode() === 'mock' ? await viaMock((e) => e.listRuns()) : await http<AnyRec[]>('/api/runs')) ?? []).map((r: AnyRec) => normRunRow(r)),
  run: async (id: string): Promise<RunDetail> => normRunRow((getMode() === 'mock' ? await viaMock((e) => e.getRun(id)) : await http(`/api/runs/${id}`)) as AnyRec),
  trials: async (id: string): Promise<Trial[]> => ((getMode() === 'mock' ? await viaMock((e) => e.trials(id)) : await http<AnyRec[]>(`/api/runs/${id}/trials`)) ?? []).map((t: AnyRec) => normTrial(t)),
  summary: async (id: string): Promise<RunAggregate> => normSummary((getMode() === 'mock' ? await viaMock((e) => e.summary(id)) : await http(`/api/runs/${id}/summary`)) as AnyRec),
  trial: async (id: string): Promise<TrialDetail> => normTrialDetail((getMode() === 'mock' ? await viaMock((e) => e.trial(id)) : await http(`/api/trials/${id}`)) as AnyRec),
  attempt: async (id: string): Promise<AttemptDetail> => normAttemptDetail((getMode() === 'mock' ? await viaMock((e) => e.attempt(id)) : await http(`/api/attempts/${id}`)) as AnyRec),
  cast: (id: string): Promise<string> => (getMode() === 'mock' ? viaMock((e) => e.cast(id)) : http(`/api/attempts/${id}/cast`)),
  dryRun: async (cfg: RunConfig): Promise<DryRunResult> =>
    normDryRun((getMode() === 'mock' ? await viaMock((e) => e.dryRun(cfg)) : await http('/api/runs?dry_run=1', { method: 'POST', body: JSON.stringify(cfg) })) as AnyRec),
  launch: (cfg: RunConfig): Promise<{ run_id: string }> =>
    getMode() === 'mock' ? viaMock((e) => ({ run_id: e.createRun(cfg) })) : http(`${WRITE_API}/runs`, { method: 'POST', body: JSON.stringify(cfg) }),
  action: (id: string, act: 'pause' | 'resume' | 'cancel'): Promise<{ ok: boolean }> =>
    getMode() === 'mock' ? viaMock((e) => (e.action(id, act), { ok: true })) : http(`${WRITE_API}/runs/${id}/${act}`, { method: 'POST' }),
}

function normEvent(e: StreamEvent): StreamEvent {
  const d = e.data as AnyRec
  if (!d || typeof d !== 'object') return e
  switch (e.type) {
    case 'run':
      return { type: 'run', data: normRunEvt(d) }
    case 'trial':
      return { type: 'trial', data: normTrial(d) }
    case 'attempt':
      return { type: 'attempt', data: normAttempt(d) }
    case 'llm_call':
      return { type: 'llm_call', data: normLlmCall(d) }
    case 'tool_call':
      return { type: 'tool_call', data: normToolCall(d) }
    case 'log':
      return { type: 'log', data: { ...d, level: d.level ?? 'info', msg: String(d.msg ?? d.message ?? d.text ?? JSON.stringify(d)), ts: d.ts ?? d.t ?? undefined } }
    default:
      return e
  }
}

const SSE_EVENTS = ['run', 'trial', 'attempt', 'llm_call', 'tool_call', 'tick', 'infra', 'budget', 'log'] as const

/** Subscribe to the run event stream. Returns an unsubscribe function. */
export function subscribeStream(runId: string, onEvent: (e: StreamEvent) => void, onStatus?: (s: 'open' | 'error') => void): () => void {
  if (getMode() === 'mock') {
    let off = () => {}
    let dead = false
    eng().then((e) => {
      if (dead) return
      off = e.subscribe(runId, (ev) => onEvent(normEvent(ev)))
      onStatus?.('open')
    })
    return () => {
      dead = true
      off()
    }
  }
  const es = new EventSource(`/api/stream?run_id=${encodeURIComponent(runId)}`)
  es.onopen = () => onStatus?.('open')
  es.onerror = () => onStatus?.('error')
  for (const name of SSE_EVENTS) {
    es.addEventListener(name, (m) => {
      try {
        onEvent(normEvent({ type: name, data: JSON.parse((m as MessageEvent).data) } as StreamEvent))
      } catch {
        /* malformed frame */
      }
    })
  }
  return () => es.close()
}

export type PtyFrame = { kind: 'text'; data: string | Uint8Array } | { kind: 'image'; url: string }

const isImage = (b: Uint8Array) => (b[0] === 0xff && b[1] === 0xd8) || (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47)

/** Open the live PTY stream. Binary frames are terminal bytes; JPEG/PNG frames are a screencast (dsh web). */
export function openPty(attemptId: string, onFrame: (f: PtyFrame) => void, onStatus?: (s: 'open' | 'closed') => void): () => void {
  if (getMode() === 'mock') {
    let off = () => {}
    let dead = false
    eng().then((e) => {
      if (dead) return
      onStatus?.('open')
      off = e.openPty(attemptId, (d) => onFrame({ kind: 'text', data: d }))
    })
    return () => {
      dead = true
      off()
    }
  }
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${location.host}/api/attempts/${attemptId}/pty`)
  ws.binaryType = 'arraybuffer'
  let lastUrl: string | null = null
  ws.onopen = () => onStatus?.('open')
  ws.onclose = () => onStatus?.('closed')
  ws.onmessage = (m) => {
    if (typeof m.data === 'string') return onFrame({ kind: 'text', data: m.data })
    const b = new Uint8Array(m.data as ArrayBuffer)
    if (isImage(b)) {
      if (lastUrl) URL.revokeObjectURL(lastUrl)
      lastUrl = URL.createObjectURL(new Blob([b], { type: b[0] === 0xff ? 'image/jpeg' : 'image/png' }))
      onFrame({ kind: 'image', url: lastUrl })
    } else onFrame({ kind: 'text', data: b })
  }
  return () => {
    ws.close()
    if (lastUrl) URL.revokeObjectURL(lastUrl)
  }
}

export async function mockSpendHistory(runId: string): Promise<[number, number][]> {
  if (getMode() !== 'mock') return []
  return (await eng()).spendHistory(runId).slice()
}
