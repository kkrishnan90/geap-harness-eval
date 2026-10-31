import { useEffect, useState } from 'react'

export function useDebounced<T>(v: T, ms = 400): T {
  const [d, setD] = useState(v)
  useEffect(() => {
    const id = setTimeout(() => setD(v), ms)
    return () => clearTimeout(id)
  }, [v, ms])
  return d
}

import { useQuery } from '@tanstack/react-query'
import { api } from './api'

/** GCP project and identity come from the server at runtime (never hard-coded). */
export function useGcpTarget(): { project: string | null; identity: string | null } {
  const q = useQuery({ queryKey: ['preflight'], queryFn: api.preflight, staleTime: 60_000 })
  return { project: q.data?.credentials.project ?? null, identity: q.data?.credentials.identity ?? null }
}
