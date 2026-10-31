import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import YAML from 'yaml'
import { motion } from 'framer-motion'
import { AlertTriangle, Check, CircleSlash, Lock, KeyRound, Layers, Plus, Rocket, ShieldCheck, Tag, Trash2, X, Copy, BookOpen } from 'lucide-react'
import { api } from '@/lib/api'
import type { HarnessInfo, ModelInfo, ModelProfile, Preflight, ProfileMode, RetryMode, RoleSpec, RunConfig, TaskInfo, Thinking } from '@/lib/types'
import { PRESET_PROFILES, ROLE_SETS } from '@/lib/presets'
import { useDebounced, useGcpTarget } from '@/lib/hooks'
import { useRun } from '@/lib/run'
import { adminHref, handleWriteError, useMe } from '@/lib/auth'
import { HARNESS_LABEL, INDUSTRY_LABEL, MODEL_SHORT, harnessColor, harnessLabelKey, harnessVersions } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { ago, fmtInt, fmtUsd } from '@/lib/format'
import { Panel, Segmented, Input, Select, Chip, Field, Skeleton, Empty } from '@/components/ui/misc'
import { Switch } from '@/components/ui/switch'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'

const TIERS = ['simple', 'medium', 'complex'] as const

interface ProfileDraft {
  id: string
  mode: ProfileMode
  roles: Record<string, RoleSpec>
}

function toDraft(p: ModelProfile): ProfileDraft {
  const roles: Record<string, RoleSpec> = { ...(p.roles ?? {}) }
  for (const s of p.stages ?? []) roles[s.role] = { model: s.model, thinking: s.thinking ?? 'high' }
  return { id: p.id, mode: p.mode, roles }
}

function fromDraft(d: ProfileDraft): ModelProfile {
  const keys = ROLE_SETS[d.mode]
  if (d.mode === 'pipeline') return { id: d.id, mode: d.mode, stages: keys.map((k) => ({ role: k, model: d.roles[k]?.model ?? 'gemini-3.8-flash', thinking: d.roles[k]?.thinking ?? 'medium' })) }
  return { id: d.id, mode: d.mode, roles: Object.fromEntries(keys.map((k) => [k, d.roles[k] ?? d.roles.default ?? { model: 'gemini-3.8-flash', thinking: 'medium' }])) }
}

export default function RunBuilder() {
  const tasksQ = useQuery({ queryKey: ['tasks'], queryFn: api.tasks })
  const modelsQ = useQuery({ queryKey: ['models'], queryFn: api.models })
  const harnessQ = useQuery({ queryKey: ['harnesses'], queryFn: api.harnesses })
  const preQ = useQuery({ queryKey: ['preflight'], queryFn: api.preflight, refetchInterval: 60_000 })

  const gcp = useGcpTarget()
  const [name, setName] = useState('q4-baseline-2')
  const [repeats, setRepeats] = useState(3)
  const [retries, setRetries] = useState(3)
  const [retryMode, setRetryMode] = useState<RetryMode>('fresh')
  const [concGlobal, setConcGlobal] = useState(6)
  const [concHarness, setConcHarness] = useState(3)
  const [budgetOn, setBudgetOn] = useState(false)
  const [budgetTotal, setBudgetTotal] = useState(250)
  const [budgetAttempt, setBudgetAttempt] = useState(5)
  const [onExceed, setOnExceed] = useState<'pause' | 'stop'>('pause')
  const [selTasks, setSelTasks] = useState<Set<string> | null>(null)
  const [fInd, setFInd] = useState<string>('all')
  const [fTier, setFTier] = useState<string>('all')
  const [fSdlc, setFSdlc] = useState<string>('all')
  const [selH, setSelH] = useState<Set<string>>(new Set(['claude_code', 'pi', 'omp', 'dsh', 'agy']))
  const [dshNative, setDshNative] = useState(false)
  const [dshAcp, setDshAcp] = useState(false)
  const [profiles, setProfiles] = useState<ProfileDraft[]>(() => PRESET_PROFILES.map(toDraft))

  const tasks = tasksQ.data ?? []
  const chosenTasks = selTasks ?? new Set(tasks.filter((t) => t.tier !== 'complex').map((t) => t.id).slice(0, 12))
  const filtered = tasks.filter((t) => (fInd === 'all' || t.industry === fInd) && (fTier === 'all' || t.tier === fTier) && (fSdlc === 'all' || t.sdlc_type === fSdlc))

  const config: RunConfig = useMemo(
    () => ({
      run: { name, repeats, max_task_retries: retries, retry_mode: retryMode },
      geap: { project: gcp.project ?? '', identity: gcp.identity ?? '', location: 'auto' },
      versions: 'latest',
      tasks: [...chosenTasks].sort(),
      harnesses: [...[...selH].sort(), ...(dshNative && selH.has('dsh') ? ['dsh/web-native'] : []), ...(dshAcp && selH.has('dsh') ? ['dsh/acp-ptc'] : [])],
      model_profiles: profiles.map(fromDraft),
      limits: { attempt_timeout_s: { simple: 600, medium: 1500, complex: 3600 }, max_nudges: 2 },
      budget: { enabled: budgetOn, max_usd_total: budgetOn ? budgetTotal : null, max_usd_per_attempt: budgetOn ? budgetAttempt : null, on_exceed: onExceed },
      concurrency: { global: concGlobal, per_harness: concHarness },
    }),
    [gcp.project, gcp.identity, name, repeats, retries, retryMode, chosenTasks, selH, dshNative, dshAcp, profiles, budgetOn, budgetTotal, budgetAttempt, onExceed, concGlobal, concHarness],
  )
  const dCfg = useDebounced(config, 350)
  const dry = useQuery({ queryKey: ['dry', JSON.stringify(dCfg)], queryFn: () => api.dryRun(dCfg), enabled: !!dCfg.geap.project && dCfg.tasks.length > 0 && dCfg.harnesses.length > 0 && dCfg.model_profiles.length > 0, placeholderData: (p) => p })

  const me = useMe()
  const nav = useNavigate()
  const qc = useQueryClient()
  const { setRunId } = useRun()
  const launch = useMutation({
    mutationFn: () => api.launch(config),
    onError: (err) => {
      handleWriteError(err)
    },
    onSuccess: async ({ run_id }) => {
      await qc.invalidateQueries({ queryKey: ['runs'] })
      setRunId(run_id)
      nav('/live')
    },
  })

  const pre = preQ.data
  const blockers = [
    ...(pre && !pre.credentials.ok ? ['Credentials'] : []),
    ...(pre && !pre.pricing.ok ? ['Price book'] : []),
    ...(chosenTasks.size === 0 ? ['No tasks'] : []),
    ...(selH.size === 0 ? ['No harnesses'] : []),
    ...(profiles.length === 0 ? ['No profiles'] : []),
  ]
  const okCells = dry.data?.matrix.filter((c) => c.status === 'ok').length ?? 0

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_440px]">
      <div className="flex min-w-0 flex-col gap-4">
        <Preflights pre={pre} loading={preQ.isLoading} models={modelsQ.data} harnesses={harnessQ.data} />

        <Panel eyebrow="Step 1" title="Run settings">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Field label="Name" className="col-span-2">
              <Input value={name} onChange={(e) => setName(e.target.value.replace(/\s+/g, '-'))} />
            </Field>
            <Field label="Repeats" hint="per task × harness × profile">
              <Input type="number" min={1} max={20} value={repeats} onChange={(e) => setRepeats(Math.max(1, +e.target.value || 1))} className="font-mono" />
            </Field>
            <Field label="Task retries" hint={`up to ${retries + 1} attempts per trial`}>
              <Input type="number" min={0} max={6} value={retries} onChange={(e) => setRetries(Math.max(0, Math.min(6, +e.target.value || 0)))} className="font-mono" />
            </Field>
            <Field
              label="Retry mode"
              className="col-span-2"
              hint={
                retryMode === 'fresh'
                  ? 'Reset workspace, new session, same ticket. Measures reliability; pass@k is valid.'
                  : 'Same session, failing test names pasted back. Measures self-repair; reported separately as "solved with help".'
              }
            >
              <Segmented value={retryMode} onChange={setRetryMode} options={[{ value: 'fresh', label: 'Fresh (default)' }, { value: 'feedback', label: 'Feedback' }]} />
            </Field>
            <Field label="Concurrency" hint="global">
              <Input type="number" min={1} max={32} value={concGlobal} onChange={(e) => setConcGlobal(Math.max(1, +e.target.value || 1))} className="font-mono" />
            </Field>
            <Field label="Per harness" hint="max parallel">
              <Input type="number" min={1} max={16} value={concHarness} onChange={(e) => setConcHarness(Math.max(1, +e.target.value || 1))} className="font-mono" />
            </Field>
          </div>
          <div className="mt-4 rounded-lg border border-line bg-sunken/50 p-3">
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-[12.5px] font-medium">Budget guardrail</div>
                <div className="text-[11.5px] text-muted">Warns at 80%. At 100% no new attempts are admitted; in-flight attempts finish.</div>
              </div>
              <Switch checked={budgetOn} onCheckedChange={setBudgetOn} label="Budget guardrail" />
            </div>
            {budgetOn && (
              <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} className="mt-3 grid grid-cols-3 gap-3">
                <Field label="Run cap (USD)">
                  <Input type="number" min={1} value={budgetTotal} onChange={(e) => setBudgetTotal(+e.target.value || 0)} className="font-mono" />
                </Field>
                <Field label="Per attempt (USD)">
                  <Input type="number" min={0.1} step={0.5} value={budgetAttempt} onChange={(e) => setBudgetAttempt(+e.target.value || 0)} className="font-mono" />
                </Field>
                <Field label="On exceed">
                  <Segmented value={onExceed} onChange={setOnExceed} options={[{ value: 'pause', label: 'Pause' }, { value: 'stop', label: 'Stop' }]} />
                </Field>
              </motion.div>
            )}
          </div>
        </Panel>

        <Panel
          eyebrow="Step 2"
          title={`Tasks · ${chosenTasks.size} selected`}
          actions={
            <>
              <Button size="sm" variant="ghost" onClick={() => setSelTasks(new Set([...chosenTasks, ...filtered.map((t) => t.id)]))}>
                Select shown
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelTasks(new Set([...chosenTasks].filter((id) => !filtered.find((t) => t.id === id))))}>
                Clear shown
              </Button>
            </>
          }
          bodyClass="p-0"
        >
          <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
            <Select aria-label="Industry" value={fInd} onChange={(e) => setFInd(e.target.value)} className="w-[150px]">
              <option value="all">All industries</option>
              {Object.entries(INDUSTRY_LABEL).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </Select>
            <Segmented size="sm" value={fTier} onChange={setFTier} options={[{ value: 'all', label: 'All tiers' }, ...TIERS.map((t) => ({ value: t, label: t[0].toUpperCase() + t.slice(1) }))]} />
            <Select aria-label="SDLC type" value={fSdlc} onChange={(e) => setFSdlc(e.target.value)} className="w-[150px]">
              <option value="all">All SDLC types</option>
              {[...new Set(tasks.map((t) => t.sdlc_type))].sort().map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
            <span className="ml-auto font-mono text-[11px] text-muted">
              {filtered.length} shown · {tasks.length} total
            </span>
          </div>
          {tasksQ.isLoading ? (
            <div className="space-y-2 p-4">
              <Skeleton className="h-6" />
              <Skeleton className="h-6" />
              <Skeleton className="h-6" />
            </div>
          ) : (
            <div className="max-h-[320px] overflow-y-auto">
              <table className="w-full text-[12px]">
                <tbody>
                  {filtered.map((t) => (
                    <TaskRow
                      key={t.id}
                      t={t}
                      on={chosenTasks.has(t.id)}
                      toggle={() => {
                        const n = new Set(chosenTasks)
                        if (n.has(t.id)) n.delete(t.id)
                        else n.add(t.id)
                        setSelTasks(n)
                      }}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel eyebrow="Step 3" title="Harnesses" bodyClass="p-0">
          <div className="grid grid-cols-1 divide-y divide-line md:grid-cols-2 md:divide-y-0">
            {(harnessQ.data ?? [])
              .filter((h) => !(h.name === 'dsh' && h.variant !== 'web-ptc' && h.variant !== 'ptc'))
              .map((h, i) => (
                <HarnessRow
                  key={h.name + h.variant}
                  h={h}
                  all={harnessQ.data}
                  pre={pre}
                  on={selH.has(h.name)}
                  className={cn('md:border-line', i % 2 === 0 && 'md:border-r', i >= 2 && 'md:border-t')}
                  toggle={() => {
                    const n = new Set(selH)
                    if (n.has(h.name)) n.delete(h.name)
                    else n.add(h.name)
                    setSelH(n)
                  }}
                  extra={
                    h.name === 'dsh' ? (
                      <div className="mt-2 space-y-1.5">
                        <label className="flex items-center gap-2 text-[11.5px] text-fg-2">
                          <Switch checked={dshNative} onCheckedChange={setDshNative} disabled={!selH.has('dsh')} label="dsh native control" />
                          Add <span className="font-medium">dsh native (PTC off)</span> control variant
                        </label>
                        <label className="flex items-center gap-2 text-[11.5px] text-fg-2">
                          <Switch checked={dshAcp} onCheckedChange={setDshAcp} disabled={!selH.has('dsh')} label="dsh ACP variant" />
                          Add <span className="font-medium">dsh ACP</span> (stdio driver, PTC on)
                        </label>
                      </div>
                    ) : null
                  }
                />
              ))}
          </div>
        </Panel>

        <Panel
          eyebrow="Step 4"
          title={`Model profiles · ${profiles.length}`}
          actions={
            <Button
              size="sm"
              onClick={() =>
                setProfiles((p) => [...p, { id: `profile-${p.length + 1}`, mode: 'single', roles: { default: { model: 'gemini-3.8-flash', thinking: 'medium' } } }])
              }
            >
              <Plus /> Add profile
            </Button>
          }
        >
          <div className="flex flex-col gap-3">
            {profiles.map((p, i) => (
              <ProfileEditor
                key={i}
                p={p}
                models={modelsQ.data ?? []}
                onChange={(np) => setProfiles((ps) => ps.map((x, j) => (j === i ? np : x)))}
                onRemove={() => setProfiles((ps) => ps.filter((_, j) => j !== i))}
              />
            ))}
            {profiles.length === 0 && <Empty title="No profiles" hint="Add a profile to choose models and thinking levels per role." />}
          </div>
        </Panel>
      </div>

      {/* Right rail */}
      <div className="flex min-w-0 flex-col gap-4 xl:sticky xl:top-[72px] xl:max-h-[calc(100vh-88px)] xl:self-start xl:overflow-y-auto xl:pb-2">
        <Panel eyebrow="Dry run" title="Matrix" actions={dry.isFetching ? <span className="font-mono text-[10.5px] text-muted">updating…</span> : <span className="font-mono text-[10.5px] text-muted">POST /api/runs?dry_run=1</span>}>
          <Matrix cfg={dCfg} res={dry.data} />
        </Panel>
        <EstimateCard est={dry.data?.estimate} trials={okCells * repeats} retries={retries} />
        <YamlPreview cfg={config} />
        <div className="panel flex flex-col gap-2 p-4">
          {blockers.length > 0 && (
            <div className="flex items-center gap-2 text-[12px] text-warn">
              <AlertTriangle className="size-3.5" /> Resolve before launch: {blockers.join(', ')}
            </div>
          )}
          {launch.error && <div className="text-[12px] text-fail">Launch failed: {(launch.error as Error).message}</div>}
          {me.admin ? (
            <>
              <Button size="lg" variant="primary" disabled={blockers.length > 0 || launch.isPending || okCells === 0 || !gcp.project} onClick={() => launch.mutate()}>
                <Rocket /> {launch.isPending ? 'Launching…' : `Launch ${fmtInt(okCells * repeats)} trials`}
              </Button>
              <div className="text-center text-[11px] text-muted">CLIs resolve to latest and are frozen into the run lock file.</div>
            </>
          ) : (
            <>
              <Button size="lg" variant="secondary" asChild>
                <a href={adminHref('/build')}>
                  <Lock /> Sign in to launch
                </a>
              </Button>
              <div className="text-center text-[11px] text-muted">This is a public read-only view. Explore configurations and the dry-run matrix freely; launching requires admin sign-in.</div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

function TaskRow({ t, on, toggle }: { t: TaskInfo; on: boolean; toggle: () => void }) {
  return (
    <tr className={cn('cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-hover', on && 'bg-accent-soft/40')} onClick={toggle}>
      <td className="w-9 py-2 pl-4">
        <span role="checkbox" aria-checked={on} aria-label={t.id} className={cn('flex size-4 items-center justify-center rounded border', on ? 'border-accent bg-accent text-white' : 'border-line-strong')}>
          {on && <Check className="size-3" strokeWidth={3} />}
        </span>
      </td>
      <td className="py-2 pr-3">
        <div className="font-medium text-fg">{t.title}</div>
        <div className="font-mono text-[10.5px] text-muted">{t.id}</div>
      </td>
      <td className="hidden py-2 pr-3 md:table-cell">
        <Chip>{INDUSTRY_LABEL[t.industry] ?? t.industry}</Chip>
      </td>
      <td className="py-2 pr-3">
        <TierMark tier={t.tier} />
      </td>
      <td className="hidden py-2 pr-3 sm:table-cell">
        <span className="font-mono text-[11px] text-fg-2">{t.sdlc_type}</span>
      </td>
      <td className="hidden py-2 pr-4 text-right font-mono text-[11px] text-muted lg:table-cell">{t.languages.join(', ')}</td>
    </tr>
  )
}

export function TierMark({ tier }: { tier: string }) {
  const n = tier === 'simple' ? 1 : tier === 'medium' ? 2 : 3
  return (
    <span className="inline-flex items-center gap-1.5 text-[11.5px] text-fg-2">
      <span className="flex items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span key={i} className="w-[3px] rounded-[1px]" style={{ height: 4 + i * 3, background: i <= n ? 'var(--fg-2)' : 'var(--line-strong)' }} />
        ))}
      </span>
      {tier}
    </span>
  )
}

function HarnessRow({ h, on, toggle, pre, extra, className, all }: { h: HarnessInfo; on: boolean; toggle: () => void; pre?: Preflight; extra?: React.ReactNode; className?: string; all?: HarnessInfo[] }) {
  const v = harnessVersions(h.name, all, pre?.harnesses)
  const upgrade = v.upgrade
  return (
    <div className={cn('flex gap-3 p-4', className)}>
      <span className="mt-0.5 h-8 w-[3px] shrink-0 rounded-full" style={{ background: on ? harnessColor(h.name === 'dsh' ? 'dsh/ptc' : h.name) : 'var(--line-strong)' }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[13px] font-semibold">{HARNESS_LABEL[h.name] ?? h.name}</span>
          {h.name === 'dsh' && <Chip tone="accent">PTC · web</Chip>}
          <span className="truncate font-mono text-[10.5px] text-muted">{h.capabilities.driver === 'browser' ? 'Playwright driver' : h.capabilities.driver === 'pty' ? 'PTY driver' : h.capabilities.driver}</span>
        </div>
        <div className="mt-1 flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
          {upgrade ? (
            <Tip content="The run installs the latest release into tools/ and freezes it in lock.json">
              <span className="text-fg-2">
                <span className="text-muted line-through decoration-faint">{v.installed ?? 'not installed'}</span> → <span className="text-accent">{v.latest}</span>
              </span>
            </Tip>
          ) : (
            <span className="text-fg-2">
              {v.installed ?? '—'} <span className="text-muted">· {v.latest ? 'up to date' : 'latest unknown'}</span>
            </span>
          )}
        </div>
        <div className="mt-1.5 flex flex-wrap gap-1">
          {h.capabilities.native_multi_model && <Chip>native roles</Chip>}
          {h.capabilities.pipeline && <Chip>pipeline</Chip>}
          {h.capabilities.thinking_control && (
            <Tip content={typeof h.capabilities.thinking_control === 'string' ? h.capabilities.thinking_control : 'Thinking level is configurable'}>
              <span>
                <Chip>thinking control</Chip>
              </span>
            </Tip>
          )}
        </div>
        {extra}
      </div>
      <Switch checked={on} onCheckedChange={toggle} label={`Include ${h.name}`} />
    </div>
  )
}

function ProfileEditor({ p, models, onChange, onRemove }: { p: ProfileDraft; models: ModelInfo[]; onChange: (p: ProfileDraft) => void; onRemove: () => void }) {
  const roles = ROLE_SETS[p.mode]
  return (
    <div className="rounded-lg border border-line bg-sunken/40">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-3 py-2">
        <Tag className="size-3.5 text-muted" />
        <input aria-label="Profile id" value={p.id} onChange={(e) => onChange({ ...p, id: e.target.value.replace(/\s+/g, '-') })} className="w-[220px] bg-transparent font-mono text-[12.5px] font-medium text-fg outline-none" />
        <div className="ml-auto flex items-center gap-2">
          <Segmented
            size="sm"
            value={p.mode}
            onChange={(m) => {
              const nr = { ...p.roles }
              for (const r of ROLE_SETS[m]) nr[r] ??= p.roles.default ?? p.roles.execute ?? { model: 'gemini-3.8-flash', thinking: 'medium' }
              onChange({ ...p, mode: m, roles: nr })
            }}
            options={[
              { value: 'single', label: 'Single' },
              { value: 'native_roles', label: 'Native roles' },
              { value: 'pipeline', label: 'Pipeline' },
            ]}
          />
          <Button size="icon-sm" variant="ghost" onClick={onRemove} aria-label="Remove profile">
            <Trash2 />
          </Button>
        </div>
      </div>
      <div className="divide-y divide-line/60">
        {roles.map((r) => {
          const spec = p.roles[r] ?? { model: 'gemini-3.8-flash', thinking: 'medium' as Thinking }
          const m = models.find((x) => x.id === spec.model)
          const levels = m?.thinking_levels ?? []
          return (
            <div key={r} className="flex flex-wrap items-center gap-3 px-3 py-2">
              <span className="w-[64px] font-mono text-[11px] text-muted">{p.mode === 'pipeline' ? `${r}` : r}</span>
              <Select
                aria-label={`${r} model`}
                value={spec.model}
                onChange={(e) => {
                  const nm = models.find((x) => x.id === e.target.value)
                  const lv = nm?.thinking_levels ?? []
                  const th = lv.includes(spec.thinking) ? spec.thinking : (lv.includes('medium') ? 'medium' : lv[0]) ?? 'off'
                  onChange({ ...p, roles: { ...p.roles, [r]: { model: e.target.value, thinking: th } } })
                }}
                className="w-[200px]"
              >
                {models.map((x) => (
                  <option key={x.id} value={x.id} disabled={!x.enabled}>
                    {x.id}
                    {!x.enabled ? ' — not enabled' : ''}
                  </option>
                ))}
              </Select>
              {m && !m.enabled ? (
                <span className="flex items-center gap-1.5 text-[11.5px] text-fail">
                  <CircleSlash className="size-3.5" /> Not enabled for this project — accept terms in Model Garden
                </span>
              ) : (
                <Segmented
                  size="sm"
                  value={spec.thinking}
                  onChange={(t) => onChange({ ...p, roles: { ...p.roles, [r]: { ...spec, thinking: t } } })}
                  options={levels.map((l) => ({ value: l, label: l }))}
                />
              )}
              {m && (
                <span className="ml-auto hidden font-mono text-[10.5px] text-muted lg:inline">
                  {m.locations.length ? m.locations.join(' · ') : 'no location'}
                </span>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Preflights({ pre, loading, models, harnesses }: { pre?: Preflight; loading: boolean; models?: ModelInfo[]; harnesses?: HarnessInfo[] }) {
  if (loading || !pre)
    return (
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[118px]" />
        ))}
      </div>
    )
  const c = pre.credentials
  const avail = pre.models.availability
  const upgrades = pre.harnesses.filter((h) => harnessVersions(h.name, harnesses, pre.harnesses).upgrade)
  const Card = ({ ok, icon, title, children, warn }: { ok: boolean; icon: React.ReactNode; title: string; children: React.ReactNode; warn?: boolean }) => (
    <div className="panel relative overflow-hidden p-3.5">
      <div className="mb-2 flex items-center gap-2">
        <span className="text-muted">{icon}</span>
        <span className="text-[12px] font-semibold">{title}</span>
        <span className={cn('ml-auto flex size-4 items-center justify-center rounded-full', ok ? (warn ? 'bg-[color-mix(in_oklab,var(--warn)_18%,transparent)] text-warn' : 'bg-[color-mix(in_oklab,var(--pass)_18%,transparent)] text-pass') : 'bg-[color-mix(in_oklab,var(--fail)_18%,transparent)] text-fail')}>
          {ok ? warn ? <AlertTriangle className="size-2.5" /> : <Check className="size-2.5" strokeWidth={3} /> : <X className="size-2.5" strokeWidth={3} />}
        </span>
      </div>
      <div className="space-y-1 text-[11.5px] text-fg-2">{children}</div>
    </div>
  )
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
      <Card ok={c.ok} icon={<KeyRound className="size-3.5" />} title="Credentials">
        <div className="truncate font-mono text-[11px]">{c.identity}</div>
        <div className="flex justify-between font-mono text-[11px]">
          <span>{c.project}</span>
          <span className="text-muted">{c.adc_type}</span>
        </div>
        <div className="text-muted">ADC token valid {Math.round(c.expires_in / 60)} min · no API keys</div>
        {c.issues.map((i) => (
          <div key={i} className="text-fail">
            {i}
          </div>
        ))}
      </Card>
      <Card ok={pre.models.ok} warn={!!models?.some((m) => !m.enabled)} icon={<Layers className="size-3.5" />} title="Model availability">
        {(models ?? []).map((m) => {
          const ok = avail.filter((a) => a.model === m.id && a.status === 'ok').map((a) => a.location)
          return (
            <div key={m.id} className="flex items-center justify-between gap-2">
              <span className="truncate">{MODEL_SHORT[m.id] ?? m.id}</span>
              {m.enabled ? <span className="truncate font-mono text-[10.5px] text-muted">{ok.join(', ') || '—'}</span> : <span className="font-mono text-[10.5px] text-fail">not enabled</span>}
            </div>
          )
        })}
      </Card>
      <Card ok={pre.pricing.ok} warn={pre.pricing.issues.length > 0} icon={<BookOpen className="size-3.5" />} title="Price book">
        <div className="truncate font-mono text-[11px]">{pre.pricing.snapshot_id}</div>
        <div className="text-muted">Billing Catalog · synced {ago(pre.pricing.fetched_at)}</div>
        {pre.pricing.issues.slice(0, 1).map((i) => (
          <Tip key={i} content={i}>
            <div className="line-clamp-2 text-warn">{i}</div>
          </Tip>
        ))}
      </Card>
      <Card ok warn={upgrades.length > 0} icon={<ShieldCheck className="size-3.5" />} title="Harness versions">
        {pre.harnesses.map((h) => (
          <div key={h.name} className="flex items-center justify-between font-mono text-[11px]">
            <span className="font-sans">{HARNESS_LABEL[h.name] ?? h.name}</span>
            {(() => {
              const v = harnessVersions(h.name, harnesses, pre.harnesses)
              return v.upgrade ? (
                <span>
                  <span className="text-muted">{v.installed ?? '—'}</span> <span className="text-accent">→ {v.latest}</span>
                </span>
              ) : (
                <span className="text-muted">{v.installed ?? '—'}</span>
              )
            })()}
          </div>
        ))}
      </Card>
    </div>
  )
}

function Matrix({ cfg, res }: { cfg: RunConfig; res?: import('@/lib/types').DryRunResult }) {
  if (!res) return <Skeleton className="h-40" />
  const hs = [...new Set(res.matrix.map((c) => c.harness))]
  const ps = cfg.model_profiles.map((p) => p.id)
  const cell = (h: string, p: string) => res.matrix.filter((c) => c.harness === h && c.profile === p)
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-separate border-spacing-[3px] text-[11px]">
        <thead>
          <tr>
            <th />
            {ps.map((p) => (
              <th key={p} className="px-1 pb-1 text-left align-bottom font-mono text-[10px] font-normal text-muted">
                <div className="max-w-[86px] truncate" title={p}>
                  {p}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {hs.map((h) => (
            <tr key={h}>
              <td className="whitespace-nowrap pr-2 text-[11.5px] font-medium text-fg-2">
                <span className="mr-1.5 inline-block h-2.5 w-[3px] rounded-full align-middle" style={{ background: harnessColor(h === 'dsh' ? 'dsh/ptc' : h) }} />
                {harnessLabelKey(h)}
              </td>
              {ps.map((p) => {
                const cs = cell(h, p)
                const ok = cs.filter((c) => c.status === 'ok').length
                const reason = cs.find((c) => c.status === 'na')?.reason
                const na = ok === 0
                return (
                  <td key={p}>
                    <Tip content={na ? <><b>N/A.</b> {reason}</> : `${ok} tasks × ${cfg.run.repeats} repeats = ${ok * cfg.run.repeats} trials`}>
                      <div
                        className={cn('flex h-8 items-center justify-center rounded-md font-mono text-[11px] num', na ? 'text-faint' : 'text-fg')}
                        style={
                          na
                            ? { background: 'repeating-linear-gradient(135deg, var(--sunken) 0 4px, transparent 4px 8px)', boxShadow: 'inset 0 0 0 1px var(--line)' }
                            : { background: 'color-mix(in oklab, var(--accent) 14%, var(--raised))', boxShadow: 'inset 0 0 0 1px var(--accent-line)' }
                        }
                      >
                        {na ? 'N/A' : ok * cfg.run.repeats}
                      </div>
                    </Tip>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <NaReasons res={res} />
    </div>
  )
}

function NaReasons({ res }: { res: import('@/lib/types').DryRunResult }) {
  const reasons = new Map<string, number>()
  for (const c of res.matrix) if (c.status === 'na' && c.reason) reasons.set(c.reason, (reasons.get(c.reason) ?? 0) + 1)
  if (!reasons.size) return null
  return (
    <div className="mt-3 space-y-1.5 border-t border-line pt-3">
      <div className="eyebrow">Why cells are N/A</div>
      {[...reasons].map(([r, n]) => (
        <div key={r} className="flex gap-2 text-[11.5px] text-fg-2">
          <span className="shrink-0 font-mono text-muted num">{n}×</span>
          {r}
        </div>
      ))}
    </div>
  )
}

function EstimateCard({ est, trials, retries }: { est?: import('@/lib/types').DryRunResult['estimate']; trials: number; retries: number }) {
  const e = typeof est === 'number' ? { usd_total: est } : est ?? null
  return (
    <div className="panel p-4">
      <div className="flex items-center justify-between">
        <div className="eyebrow">Cost estimate</div>
        <Chip tone="muted">estimate · list prices</Chip>
      </div>
      {(() => {
        const total = e?.trials ?? trials
        const hist = e?.with_history
        if (hist === 0) return <div className="mt-1 text-[15px] font-medium text-muted">No history yet</div>
        const partial = hist != null && hist < total
        return (
          <>
            <div className="mt-1 font-mono text-[26px] font-medium tracking-[-0.02em] num">{e?.usd_total != null ? fmtUsd(e.usd_total) : '—'}</div>
            {partial && (
              <div className="text-[11.5px] text-warn">
                for {fmtInt(hist)} of {fmtInt(total)} trials with history · {fmtInt(total - hist)} unknown
              </div>
            )}
          </>
        )
      })()}
      {e?.usd_low != null && e?.usd_high != null && (
        <div className="font-mono text-[11.5px] text-muted num">
          range {fmtUsd(e.usd_low)} – {fmtUsd(e.usd_high)}
        </div>
      )}
      <div className="mt-3 grid grid-cols-3 gap-2 border-t border-line pt-3 text-[11px]">
        <div>
          <div className="text-muted">Trials</div>
          <div className="font-mono text-[13px] text-fg num">{fmtInt(e?.trials ?? trials)}</div>
        </div>
        <div>
          <div className="text-muted">Max attempts</div>
          <div className="font-mono text-[13px] text-fg num">{fmtInt((e?.trials ?? trials) * (retries + 1))}</div>
        </div>
        <div>
          <div className="text-muted">Wall time</div>
          <div className="font-mono text-[13px] text-fg num">{e?.minutes != null ? `${Math.round(e.minutes / 60)}h ${Math.round(e.minutes % 60)}m` : '—'}</div>
        </div>
      </div>
      <div className="mt-2 text-[11px] text-muted">{e?.label ?? e?.note ?? 'Historical medians per task, harness and model.'}</div>
    </div>
  )
}

function YamlPreview({ cfg }: { cfg: RunConfig }) {
  const text = useMemo(() => YAML.stringify(cfg, { lineWidth: 0, flowCollectionPadding: true, collectionStyle: 'block' }), [cfg])
  const [copied, setCopied] = useState(false)
  return (
    <Panel
      eyebrow="Config as code"
      title="run.yaml"
      bodyClass="p-0"
      actions={
        <Button
          size="sm"
          variant="ghost"
          onClick={() => {
            navigator.clipboard?.writeText(text).catch(() => {})
            setCopied(true)
            setTimeout(() => setCopied(false), 1200)
          }}
        >
          <Copy /> {copied ? 'Copied' : 'Copy'}
        </Button>
      }
    >
      <pre className="max-h-[300px] overflow-auto bg-sunken/60 px-4 py-3 font-mono text-[11px] leading-[1.6]">
        {text.split('\n').map((l, i) => {
          const m = l.match(/^(\s*-?\s*)([\w.]+)(:)(.*)$/)
          return (
            <div key={i}>
              {m ? (
                <>
                  <span>{m[1]}</span>
                  <span className="text-accent">{m[2]}</span>
                  <span className="text-muted">{m[3]}</span>
                  <span className={/^\s*\d/.test(m[4]) || /true|false|null/.test(m[4]) ? 'text-[var(--tok-cache-read)]' : 'text-fg-2'}>{m[4]}</span>
                </>
              ) : (
                <span className="text-fg-2">{l}</span>
              )}
            </div>
          )
        })}
      </pre>
    </Panel>
  )
}
