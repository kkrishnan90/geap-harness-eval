import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from './api'
import type { RunSummaryRow } from './types'
import { connectRun } from './live'

const Ctx = createContext<{ runId: string | null; setRunId: (id: string) => void; runs: RunSummaryRow[]; current: RunSummaryRow | null }>({ runId: null, setRunId: () => {}, runs: [], current: null })

export function RunProvider({ children }: { children: ReactNode }) {
  const { data: runs = [] } = useQuery({ queryKey: ['runs'], queryFn: api.runs, refetchInterval: 10_000 })
  const [runId, setRunIdState] = useState<string | null>(() => {
    const q = new URLSearchParams(location.search).get('run')
    if (q) return q
    try {
      return localStorage.getItem('geap.run')
    } catch {
      return null
    }
  })
  useEffect(() => {
    if (!runs.length) return
    if (!runId || !runs.find((r) => r.id === runId)) {
      const pick = runs.find((r) => r.status === 'running') ?? runs[0]
      setRunIdState(pick.id)
    }
  }, [runs, runId])
  useEffect(() => {
    connectRun(runId)
    if (runId)
      try {
        localStorage.setItem('geap.run', runId)
      } catch {
        /* storage blocked */
      }
  }, [runId])
  const current = useMemo(() => runs.find((r) => r.id === runId) ?? null, [runs, runId])
  return <Ctx.Provider value={{ runId, setRunId: setRunIdState, runs, current }}>{children}</Ctx.Provider>
}

export const useRun = () => useContext(Ctx)

/** 1 + max_task_retries from the selected run's config (defaults to 4). */
export function useMaxAttempts(): number {
  const { runId } = useRun()
  const q = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId!), enabled: !!runId, staleTime: 30_000 })
  const cfg = q.data?.config_json as { run?: { max_task_retries?: number } } | undefined
  return (cfg?.run?.max_task_retries ?? 3) + 1
}
