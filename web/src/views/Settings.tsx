import { useQuery } from '@tanstack/react-query'
import { Lock, Check, X } from 'lucide-react'
import { api } from '@/lib/api'
import { useRun } from '@/lib/run'
import type { RunConfig } from '@/lib/types'
import { HARNESS_LABEL, harnessVersions } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { Panel, Skeleton, Chip } from '@/components/ui/misc'
import { Tip } from '@/components/ui/tooltip'
import { PriceBook } from './CostCenter'
import { PriceValidation, PromotionsPanel } from '@/components/Pricing'

const LOCS = ['global', 'us-central1', 'us-east5', 'us-east1', 'us-south1', 'europe-west1', 'europe-west4', 'asia-southeast1', 'asia-south1', 'asia-northeast1']

export default function Settings() {
  const pre = useQuery({ queryKey: ['preflight'], queryFn: api.preflight })
  const models = useQuery({ queryKey: ['models'], queryFn: api.models })
  const hs = useQuery({ queryKey: ['harnesses'], queryFn: api.harnesses })
  const { runId } = useRun()
  const run = useQuery({ queryKey: ['run', runId], queryFn: () => api.run(runId!), enabled: !!runId })
  const cfg: RunConfig | null = run.data?.config_json ? (typeof run.data.config_json === 'string' ? (JSON.parse(run.data.config_json) as RunConfig) : run.data.config_json) : null
  const avail = pre.data?.models.availability ?? []

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-2 text-[12px] text-muted">
        <Lock className="size-3.5" /> Read-only. Settings come from the server and the run config; edit them as YAML.
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.4fr]">
        <Panel eyebrow="GEAP target" title={pre.data ? `Locked to ${pre.data.credentials.project}` : 'GCP target'}>
          {!pre.data ? (
            <Skeleton className="h-32" />
          ) : (
            <dl className="grid grid-cols-[140px_1fr] gap-y-2 text-[12.5px]">
              <dt className="text-muted">Project</dt>
              <dd className="font-mono">{pre.data.credentials.project}</dd>
              <dt className="text-muted">Quota project</dt>
              <dd className="font-mono">{pre.data.credentials.project} <span className="text-muted">(x-goog-user-project)</span></dd>
              <dt className="text-muted">Identity</dt>
              <dd className="font-mono">{pre.data.credentials.identity}</dd>
              <dt className="text-muted">Credentials</dt>
              <dd className="font-mono">ADC · {pre.data.credentials.adc_type} · expires in {Math.round(pre.data.credentials.expires_in / 60)} min</dd>
              <dt className="text-muted">Location</dt>
              <dd className="font-mono">auto <span className="text-muted">— per model from the availability probe</span></dd>
              <dt className="text-muted">Disallowed</dt>
              <dd className="text-fg-2">API keys, service-account key files, consumer OAuth</dd>
            </dl>
          )}
        </Panel>
        <Panel eyebrow="GET /api/preflight · models.availability" title="Model discovery" bodyClass="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-[11.5px]">
              <thead>
                <tr className="border-b border-line text-muted">
                  <th className="px-4 py-2 text-left font-medium">Model</th>
                  <th className="px-2 py-2 text-left font-medium">Thinking</th>
                  {LOCS.map((l) => (
                    <th key={l} className="px-1 py-2 text-center font-mono text-[9.5px] font-normal">
                      <span className="inline-block max-w-[52px] truncate align-bottom" title={l}>{l.replace('-central', '-c').replace('europe-', 'eu-').replace('asia-', 'as-')}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(models.data ?? []).map((m) => (
                  <tr key={m.id} className="border-b border-line/60 last:border-0">
                    <td className="px-4 py-2">
                      <div className="font-mono">{m.id}</div>
                      <div className="flex gap-1 pt-0.5">
                        {!m.enabled && <Chip tone="fail">not enabled</Chip>}
                        {m.priced ? <Chip>priced</Chip> : <Chip tone="fail">no SKU</Chip>}
                      </div>
                    </td>
                    <td className="px-2 py-2"><div className="flex max-w-[150px] flex-wrap gap-1">{m.thinking_levels.length ? m.thinking_levels.map((l) => <span key={l} className="rounded border border-line px-1 font-mono text-[10px] text-fg-2">{l}</span>) : <span className="text-muted">—</span>}</div></td>
                    {LOCS.map((l) => {
                      const a = avail.find((x) => x.model === m.id && x.location === l)
                      const st = a?.status ?? '—'
                      return (
                        <td key={l} className="px-1 py-2 text-center">
                          <Tip content={`${m.id} @ ${l}: ${st === 'ok' ? 'available' : st === '429' ? 'persistent 429 — no usable quota' : st === '404' ? 'not found / no access' : st}`}>
                            <span className={cn('inline-flex h-5 min-w-[28px] items-center justify-center rounded font-mono text-[10px]', st === 'ok' ? 'bg-[color-mix(in_oklab,var(--pass)_16%,transparent)] text-pass' : st === '429' ? 'bg-[color-mix(in_oklab,var(--warn)_14%,transparent)] text-warn' : 'text-faint')}>
                              {st === 'ok' ? <Check className="size-3" strokeWidth={3} /> : st}
                            </span>
                          </Tip>
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel eyebrow="GET /api/harnesses" title="Harness versions" bodyClass="p-0 overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-line text-[11px] text-muted">
                <th className="px-4 py-2 text-left font-medium">Harness</th>
                <th className="px-3 py-2 text-left font-medium">Variant</th>
                <th className="px-3 py-2 text-left font-medium">Installed</th>
                <th className="px-3 py-2 text-left font-medium">Latest</th>
                <th className="px-3 py-2 text-left font-medium">Driver</th>
                <th className="px-3 py-2 text-left font-medium">Tools mode</th>
                <th className="px-3 py-2 text-left font-medium">Capabilities</th>
              </tr>
            </thead>
            <tbody>
              {(hs.data ?? []).map((h) => {
                const v = harnessVersions(h.name, [h], pre.data?.harnesses)
                return (
                  <tr key={h.name + h.variant} className="border-b border-line/60 last:border-0">
                    <td className="whitespace-nowrap px-4 py-2 font-medium">{HARNESS_LABEL[h.name] ?? h.name}</td>
                    <td className="px-3 py-2 font-mono text-muted">{h.variant}</td>
                    <td className="whitespace-nowrap px-3 py-2 font-mono">{v.installed ?? <span className="text-muted">—</span>}</td>
                    <td className={cn('whitespace-nowrap px-3 py-2 font-mono', v.upgrade && 'text-accent')}>{v.latest ?? <span className="text-muted">unknown</span>}</td>
                    <td className="px-3 py-2 font-mono text-muted">{h.capabilities.driver}</td>
                    <td className="px-3 py-2 font-mono text-muted">{h.capabilities.tools_mode ?? '—'}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-1">
                        {h.capabilities.roles.length > 1 && <Chip>roles: {h.capabilities.roles.join('/')}</Chip>}
                        {h.capabilities.pipeline ? <Chip>pipeline</Chip> : <Chip tone="muted"><X className="size-3" /> pipeline</Chip>}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Panel>
        <Panel eyebrow={`Run config · ${run.data?.name ?? '—'}`} title="Concurrency, limits and backoff">
          {!cfg ? (
            <div className="text-[12px] text-muted">The selected run did not expose config_json.</div>
          ) : (
            <dl className="grid grid-cols-[180px_1fr] gap-y-2 text-[12.5px]">
              <dt className="text-muted">Concurrency</dt>
              <dd className="font-mono">global {cfg.concurrency.global} · per harness {cfg.concurrency.per_harness}</dd>
              <dt className="text-muted">Attempt timeouts</dt>
              <dd className="font-mono">simple {cfg.limits.attempt_timeout_s.simple}s · medium {cfg.limits.attempt_timeout_s.medium}s · complex {cfg.limits.attempt_timeout_s.complex}s</dd>
              <dt className="text-muted">Nudges</dt>
              <dd className="font-mono">max {cfg.limits.max_nudges}</dd>
              <dt className="text-muted">Task retries</dt>
              <dd className="font-mono">{cfg.run.max_task_retries} · {cfg.run.retry_mode}</dd>
              <dt className="text-muted">Infra backoff</dt>
              <dd className="font-mono">exp. full jitter · base 2s · cap 120s · max 6 · honors Retry-After</dd>
              <dt className="text-muted">Rate governor</dt>
              <dd className="font-mono">per model × location · token bucket + AIMD + breaker</dd>
              <dt className="text-muted">Budget</dt>
              <dd className="font-mono">{cfg.budget.enabled ? `$${cfg.budget.max_usd_total} total · $${cfg.budget.max_usd_per_attempt}/attempt · ${cfg.budget.on_exceed} on exceed` : 'off'}</dd>
            </dl>
          )}
        </Panel>
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <PriceValidation />
        <PromotionsPanel />
      </div>
      <PriceBook />
    </div>
  )
}
