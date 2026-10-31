import { useMemo, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as Dialog from '@radix-ui/react-dialog'
import { ArrowRight, EyeOff, FileCode2, Folder, Search, ShieldCheck, X, AlertTriangle } from 'lucide-react'
import { api } from '@/lib/api'
import type { TaskInfo } from '@/lib/types'
import { INDUSTRY_LABEL } from '@/lib/labels'
import { cn } from '@/lib/utils'
import { fmtDur, fmtPct } from '@/lib/format'
import { wilson } from '@/lib/stats'
import { Panel, Segmented, Select, Input, Chip, Skeleton, Empty } from '@/components/ui/misc'
import { Markdown } from '@/components/Markdown'
import { TierMark } from './RunBuilder'

const TIERS = ['simple', 'medium', 'complex'] as const
const TIER_NOTE: Record<string, string> = { simple: '≤1 file', medium: '2–5 files', complex: '5+ files' }

export default function Method() {
  const tq = useQuery({ queryKey: ['tasks'], queryFn: api.tasks })
  const tasks = tq.data ?? []
  const [open, setOpen] = useState<string | null>(null)
  const industries = useMemo(() => [...new Set(tasks.map((t) => t.industry))].sort(), [tasks])
  const sdlc = useMemo(() => count(tasks.map((t) => t.sdlc_type)), [tasks])
  const langs = useMemo(() => count(tasks.flatMap((t) => t.languages)), [tasks])

  return (
    <div className="mx-auto flex max-w-[1320px] flex-col gap-6">
      {/* thesis */}
      <section className="panel relative overflow-hidden px-6 py-7 md:px-8 md:py-9">
        <div className="pointer-events-none absolute -right-24 -top-24 size-[340px] rounded-full opacity-[0.07]" style={{ background: 'radial-gradient(closest-side, var(--accent), transparent)' }} />
        <div className="eyebrow">Tasks & method</div>
        <h2 className="mt-2 max-w-[880px] text-[26px] font-semibold leading-[1.15] tracking-[-0.02em] md:text-[32px]">
          {tasks.length || 36} enterprise tickets. Five coding agents, driven exactly as a developer would drive them. Success decided only by hidden tests.
        </h2>
        <p className="mt-3 max-w-[760px] text-[13.5px] leading-relaxed text-fg-2">
          Every agent runs in its native interactive mode against the same seed repositories, on Google's Gemini Enterprise Agent Platform. Every model call is metered at the source, every dollar is
          validated against Google's own price catalog, and every pass is earned against tests the agent never sees.
        </p>
        <div className="mt-6 flex flex-wrap gap-x-8 gap-y-3">
          <Fact n={tasks.length} label="tasks" />
          <Fact n={industries.length} label="industries" />
          <Fact n={Object.keys(sdlc).length} label="SDLC types" />
          <Fact n={Object.keys(langs).length} label="languages" />
          <Fact n={5} label="harnesses" />
        </div>
        <nav className="mt-6 flex flex-wrap gap-2 text-[12px]" aria-label="On this page">
          {[
            ['#catalog', 'Task catalog'],
            ['#method', 'How the evaluation works'],
            ['#limits', 'Limitations'],
          ].map(([h, l]) => (
            <a key={h} href={h} className="inline-flex h-7 items-center gap-1.5 rounded-md border border-line bg-raised px-2.5 text-fg-2 transition-colors hover:border-line-strong hover:text-fg">
              {l} <ArrowRight className="size-3" />
            </a>
          ))}
        </nav>
      </section>

      {/* ------------------------ A. catalog ------------------------ */}
      <div id="catalog" className="scroll-mt-20">
        <SectionTitle n="A" title="Task catalog" sub="Realistic tickets with acceptance criteria, each backed by a seed repository and hidden tests." />
      </div>
      {tq.isLoading ? (
        <Skeleton className="h-64" />
      ) : tq.isError ? (
        <div className="panel">
          <Empty title="The task catalog could not be loaded" hint={(tq.error as Error).message} />
        </div>
      ) : (
        <>
          <Coverage tasks={tasks} industries={industries} sdlc={sdlc} langs={langs} />
          <Catalog tasks={tasks} industries={industries} onOpen={setOpen} />
        </>
      )}

      {/* ------------------------ B. method ------------------------ */}
      <div id="method" className="scroll-mt-20 pt-2">
        <SectionTitle n="B" title="How the evaluation works" sub="One pipeline per attempt, identical for every harness." />
      </div>
      <Pipeline />
      <Steps />

      <div id="limits" className="scroll-mt-20">
        <Limitations />
      </div>

      <TaskDrawer id={open} task={tasks.find((t) => t.id === open)} onClose={() => setOpen(null)} />
    </div>
  )
}

function count(xs: string[]): Record<string, number> {
  const m: Record<string, number> = {}
  for (const x of xs) m[x] = (m[x] ?? 0) + 1
  return Object.fromEntries(Object.entries(m).sort((a, b) => b[1] - a[1]))
}

function Fact({ n, label }: { n: number; label: string }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="font-mono text-[22px] font-medium tracking-[-0.02em] num">{n || '—'}</span>
      <span className="text-[12px] text-muted">{label}</span>
    </div>
  )
}

function SectionTitle({ n, title, sub }: { n: string; title: string; sub: string }) {
  return (
    <div className="flex items-end gap-3">
      <span className="flex size-7 items-center justify-center rounded-md border border-accent-line bg-accent-soft font-mono text-[12px] font-semibold text-accent">{n}</span>
      <div>
        <h2 className="text-[16px] font-semibold tracking-[-0.01em]">{title}</h2>
        <p className="text-[12.5px] text-muted">{sub}</p>
      </div>
    </div>
  )
}

// ---------------- coverage ----------------
function Coverage({ tasks, industries, sdlc, langs }: { tasks: TaskInfo[]; industries: string[]; sdlc: Record<string, number>; langs: Record<string, number> }) {
  const max = Math.max(1, ...industries.flatMap((i) => TIERS.map((t) => tasks.filter((x) => x.industry === i && x.tier === t).length)))
  const sdlcMax = Math.max(1, ...Object.values(sdlc))
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_1fr]">
      <Panel eyebrow="Coverage" title="Industries × difficulty tier">
        <div className="overflow-x-auto">
          <table className="w-full border-separate border-spacing-[3px] text-[12px]">
            <thead>
              <tr>
                <th />
                {TIERS.map((t) => (
                  <th key={t} className="px-2 pb-1 text-left font-normal">
                    <TierMark tier={t} />
                    <div className="font-mono text-[10px] text-faint">{TIER_NOTE[t]}</div>
                  </th>
                ))}
                <th className="px-2 pb-1 text-right font-mono text-[10.5px] font-normal text-muted">total</th>
              </tr>
            </thead>
            <tbody>
              {industries.map((i) => {
                const row = TIERS.map((t) => tasks.filter((x) => x.industry === i && x.tier === t).length)
                return (
                  <tr key={i}>
                    <td className="whitespace-nowrap pr-3 text-fg-2">{INDUSTRY_LABEL[i] ?? i}</td>
                    {row.map((n, j) => (
                      <td key={j}>
                        <div
                          className="flex h-8 items-center justify-center rounded-md font-mono text-[12px] num"
                          style={
                            n
                              ? { background: `color-mix(in oklab, var(--accent) ${10 + (n / max) * 38}%, var(--raised))`, color: 'var(--fg)' }
                              : { background: 'repeating-linear-gradient(135deg, var(--sunken) 0 4px, transparent 4px 8px)', boxShadow: 'inset 0 0 0 1px var(--line)', color: 'var(--faint)' }
                          }
                        >
                          {n || '·'}
                        </div>
                      </td>
                    ))}
                    <td className="pl-2 text-right font-mono text-muted num">{row.reduce((a, b) => a + b, 0)}</td>
                  </tr>
                )
              })}
              <tr>
                <td className="pr-3 pt-1 text-[11px] text-muted">total</td>
                {TIERS.map((t) => (
                  <td key={t} className="pt-1 text-center font-mono text-[11px] text-muted num">
                    {tasks.filter((x) => x.tier === t).length}
                  </td>
                ))}
                <td className="pl-2 pt-1 text-right font-mono text-[11px] text-fg-2 num">{tasks.length}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel eyebrow="Work types" title="SDLC type and language mix">
        <div className="space-y-1.5">
          {Object.entries(sdlc).map(([k, n]) => (
            <div key={k} className="grid grid-cols-[120px_1fr_28px] items-center gap-3 text-[12px]">
              <span className="font-mono text-[11.5px] text-fg-2">{k}</span>
              <div className="h-1.5 overflow-hidden rounded-full bg-sunken">
                <div className="h-full rounded-full bg-accent" style={{ width: `${(n / sdlcMax) * 100}%`, opacity: 0.85 }} />
              </div>
              <span className="text-right font-mono text-muted num">{n}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 border-t border-line pt-3">
          <div className="eyebrow mb-2">Languages</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(langs).map(([l, n]) => (
              <Chip key={l}>
                {l} <span className="font-mono text-muted">{n}</span>
              </Chip>
            ))}
          </div>
        </div>
      </Panel>
    </div>
  )
}

// ---------------- catalog ----------------
function Catalog({ tasks, industries, onOpen }: { tasks: TaskInfo[]; industries: string[]; onOpen: (id: string) => void }) {
  const [q, setQ] = useState('')
  const [ind, setInd] = useState('all')
  const [tier, setTier] = useState('all')
  const [type, setType] = useState('all')
  const [lang, setLang] = useState('all')
  const types = [...new Set(tasks.map((t) => t.sdlc_type))].sort()
  const langs = [...new Set(tasks.flatMap((t) => t.languages))].sort()
  const rows = tasks.filter(
    (t) =>
      (ind === 'all' || t.industry === ind) &&
      (tier === 'all' || t.tier === tier) &&
      (type === 'all' || t.sdlc_type === type) &&
      (lang === 'all' || t.languages.includes(lang)) &&
      (!q || `${t.id} ${t.title}`.toLowerCase().includes(q.toLowerCase())),
  )
  return (
    <Panel eyebrow="Every task in the suite" title={`Catalog · ${rows.length} of ${tasks.length}`} bodyClass="p-0">
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2.5">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search tickets" className="w-[200px] pl-8" aria-label="Search tasks" />
        </div>
        <Select aria-label="Industry" value={ind} onChange={(e) => setInd(e.target.value)} className="w-[150px]">
          <option value="all">All industries</option>
          {industries.map((i) => (
            <option key={i} value={i}>
              {INDUSTRY_LABEL[i] ?? i}
            </option>
          ))}
        </Select>
        <Segmented size="sm" value={tier} onChange={setTier} options={[{ value: 'all', label: 'All tiers' }, ...TIERS.map((t) => ({ value: t, label: t[0].toUpperCase() + t.slice(1) }))]} />
        <Select aria-label="SDLC type" value={type} onChange={(e) => setType(e.target.value)} className="w-[150px]">
          <option value="all">All SDLC types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </Select>
        <Select aria-label="Language" value={lang} onChange={(e) => setLang(e.target.value)} className="w-[130px]">
          <option value="all">All languages</option>
          {langs.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </Select>
      </div>
      <div className="grid grid-cols-1 divide-y divide-line/60 md:grid-cols-2 md:divide-y-0">
        {rows.map((t, i) => (
          <button
            key={t.id}
            onClick={() => onOpen(t.id)}
            className={cn('group flex w-full items-start gap-3 border-line/60 px-4 py-3 text-left transition-colors hover:bg-hover', i % 2 === 0 && 'md:border-r', i >= 2 && 'md:border-t')}
          >
            <FileCode2 className="mt-0.5 size-4 shrink-0 text-faint group-hover:text-accent" strokeWidth={1.75} />
            <div className="min-w-0 flex-1">
              <div className="text-[12.5px] font-medium leading-snug text-fg">{t.title}</div>
              <div className="mt-0.5 truncate font-mono text-[10.5px] text-muted">
                {t.id} · v{t.version}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                <Chip>{INDUSTRY_LABEL[t.industry] ?? t.industry}</Chip>
                <TierMark tier={t.tier} />
                <span className="font-mono text-[10.5px] text-fg-2">{t.sdlc_type}</span>
                <span className="font-mono text-[10.5px] text-muted">· {t.languages.join(', ')}</span>
                {t.timeout_s && <span className="font-mono text-[10.5px] text-faint">· {fmtDur(t.timeout_s)} limit</span>}
              </div>
            </div>
            <ArrowRight className="mt-1 size-3.5 shrink-0 text-faint opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        ))}
      </div>
      {rows.length === 0 && <Empty title="No tasks match these filters" />}
    </Panel>
  )
}

// ---------------- drawer ----------------
function TaskDrawer({ id, task, onClose }: { id: string | null; task?: TaskInfo; onClose: () => void }) {
  const dq = useQuery({ queryKey: ['task', id], queryFn: () => api.task(id!), enabled: !!id, retry: 0 })
  const d = dq.data
  const t = d ?? task
  const hist = d?.history
  const ci = hist && hist.n ? wilson(hist.passed, hist.n) : null
  return (
    <Dialog.Root open={!!id} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/45 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed inset-y-0 right-0 z-50 flex w-[min(760px,100vw)] flex-col border-l border-line-strong bg-panel shadow-2xl outline-none" aria-describedby={undefined}>
          <div className="flex items-start gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0 flex-1">
              <div className="eyebrow">{t ? `${INDUSTRY_LABEL[t.industry] ?? t.industry} · ${t.sdlc_type}` : 'Task'}</div>
              <Dialog.Title className="mt-1 text-[16px] font-semibold leading-snug tracking-[-0.01em]">{t?.title ?? id}</Dialog.Title>
              <div className="mt-0.5 font-mono text-[11px] text-muted">
                {id} {t && `· v${t.version}`}
              </div>
            </div>
            <Dialog.Close className="rounded-md p-1.5 text-muted hover:bg-hover hover:text-fg" aria-label="Close">
              <X className="size-4" />
            </Dialog.Close>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {t && (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                <Stat label="Tier">
                  <TierMark tier={t.tier} />
                </Stat>
                <Stat label="Time limit">{t.timeout_s ? fmtDur(t.timeout_s) : '—'}</Stat>
                <Stat label="Hidden tests">
                  {d?.hidden_tests ? (
                    <span className="font-mono text-[13px] num">
                      {d.hidden_tests.fail_to_pass} <span className="text-[11px] text-muted">F2P</span> · {d.hidden_tests.pass_to_pass} <span className="text-[11px] text-muted">P2P</span>
                    </span>
                  ) : (
                    <span className="text-[12px] text-muted">{d ? 'not run yet' : '—'}</span>
                  )}
                </Stat>
                <Stat label="Historical pass rate">
                  {hist && hist.n ? (
                    <span className="font-mono text-[13px] num">
                      {fmtPct(hist.passed / hist.n)} <span className="text-[11px] text-muted">({hist.passed}/{hist.n}{ci ? ` · CI ${fmtPct(ci[0])}–${fmtPct(ci[1])}` : ''})</span>
                    </span>
                  ) : (
                    <span className="text-[12px] text-muted">no runs yet</span>
                  )}
                </Stat>
              </div>
            )}
            <div className="mt-4 flex items-start gap-2.5 rounded-lg border border-line bg-sunken/60 px-3 py-2.5 text-[12px] text-fg-2">
              <EyeOff className="mt-0.5 size-4 shrink-0 text-muted" />
              <span>Hidden tests and the reference solution are not published: they stay hidden to prevent benchmark contamination. Only their counts are shown.</span>
            </div>
            {dq.isLoading ? (
              <Skeleton className="mt-4 h-64" />
            ) : !d ? (
              <div className="mt-4 panel">
                <Empty title="Ticket details are not available from this server yet" hint="GET /api/tasks/{id} returned nothing; the catalog metadata above is complete." />
              </div>
            ) : (
              <>
                <div className="mt-5">
                  <div className="eyebrow mb-2">The exact ticket the agent receives</div>
                  <div className="rounded-xl border border-line bg-raised px-5 py-4">
                    <Markdown source={d.instruction_md} />
                  </div>
                </div>
                <div className="mt-5">
                  <div className="eyebrow mb-2">Seed repository · {d.repo_file_count} files</div>
                  <RepoTree files={d.repo_files} total={d.repo_file_count} />
                </div>
              </>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

function Stat({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-raised px-3 py-2">
      <div className="eyebrow">{label}</div>
      <div className="mt-1">{children}</div>
    </div>
  )
}

interface Node {
  name: string
  children: Map<string, Node>
  file: boolean
}

function RepoTree({ files, total }: { files: string[]; total: number }) {
  const root = useMemo(() => {
    const r: Node = { name: '', children: new Map(), file: false }
    for (const f of [...files].sort()) {
      let cur = r
      const parts = f.split('/').filter(Boolean)
      parts.forEach((p, i) => {
        if (!cur.children.has(p)) cur.children.set(p, { name: p, children: new Map(), file: i === parts.length - 1 })
        cur = cur.children.get(p)!
      })
    }
    return r
  }, [files])
  const render = (n: Node, depth: number): ReactNode[] =>
    [...n.children.values()]
      .sort((a, b) => Number(a.file) - Number(b.file) || a.name.localeCompare(b.name))
      .flatMap((c) => [
        <div key={`${depth}-${c.name}-${c.file}`} className="flex items-center gap-1.5 py-[1px]" style={{ paddingLeft: depth * 14 }}>
          {c.file ? <FileCode2 className="size-3 shrink-0 text-faint" /> : <Folder className="size-3 shrink-0 text-accent" />}
          <span className={c.file ? 'text-fg-2' : 'text-fg'}>{c.name}</span>
        </div>,
        ...(c.file ? [] : render(c, depth + 1)),
      ])
  return (
    <div className="max-h-[320px] overflow-auto rounded-xl border border-line bg-raised px-4 py-3 font-mono text-[11.5px]">
      {render(root, 0)}
      {total > files.length && <div className="mt-1 text-muted">… {total - files.length} more files</div>}
    </div>
  )
}

// ---------------- method ----------------
function Box({ title, sub, tone = 'default', className }: { title: string; sub: string; tone?: 'default' | 'accent' | 'pass' | 'muted'; className?: string }) {
  const tones: Record<string, string> = {
    default: 'border-line bg-raised',
    accent: 'border-accent-line bg-accent-soft',
    pass: 'border-[color-mix(in_oklab,var(--pass)_40%,transparent)] bg-[color-mix(in_oklab,var(--pass)_8%,transparent)]',
    muted: 'border-dashed border-line-strong bg-transparent',
  }
  return (
    <div className={cn('rounded-lg border px-3 py-2.5', tones[tone], className)}>
      <div className="text-[12.5px] font-semibold">{title}</div>
      <div className="mt-0.5 text-[11px] leading-snug text-muted">{sub}</div>
    </div>
  )
}

const Arrow = ({ label, both }: { label?: string; both?: boolean }) => (
  <div className="flex shrink-0 flex-col items-center justify-center px-1 py-1 lg:py-0">
    <span className="font-mono text-[12px] text-faint">{both ? '⇄' : '→'}</span>
    {label && <span className="font-mono text-[9.5px] text-faint">{label}</span>}
  </div>
)

function Pipeline() {
  return (
    <Panel eyebrow="One attempt, end to end" title="Pipeline">
      <div className="flex flex-col items-stretch gap-1 lg:flex-row lg:items-center">
        <Box title="Ticket" sub="instruction.md, pasted into the agent's own UI" />
        <Arrow label="t0" />
        <Box tone="accent" title="Harness, native interactive" sub="Real PTY (TUI) · Playwright (dsh Web UI) · ACP stdio" className="lg:flex-[1.3]" />
        <Arrow both />
        <Box tone="accent" title="GEAP Meter" sub="Local recording proxy · all other egress denied" />
        <Arrow both />
        <Box title="Gemini Enterprise Agent Platform" sub="one locked GCP project · ADC only · global endpoint" />
      </div>
      <div className="my-2 flex justify-center lg:justify-start lg:pl-[18%]">
        <span className="font-mono text-[12px] text-faint">↓ final workspace (copy)</span>
      </div>
      <div className="flex flex-col items-stretch gap-1 lg:flex-row lg:items-center">
        <Box tone="muted" title="Completion detected" sub="hooks / durable turn records + Meter quiescence + screen idle → t_end" />
        <Arrow />
        <Box tone="pass" title="Hidden-test verifier" sub="FAIL_TO_PASS must pass · PASS_TO_PASS must stay green" />
        <Arrow />
        <Box title="Outcome + metrics" sub="tokens, tools, steps, time, validated cost" />
        <Arrow label="fail?" />
        <Box tone="muted" title="Retry policy" sub="fresh (default) or feedback · infra errors don't count" />
      </div>
    </Panel>
  )
}

const STEPS: { title: string; body: ReactNode; facts: string[] }[] = [
  {
    title: 'Native interactive harnesses',
    body: (
      <>
        Claude Code, Pi, Oh My Pi, DeepSeek Harness (dsh) and Antigravity CLI run in the interactive mode a developer uses. TUIs are driven through a real pseudo-terminal: the ticket is typed by
        bracketed paste, Enter is pressed, and submission is confirmed on screen. dsh runs through its Web UI via Playwright, or over ACP stdio. No headless or print modes are used.
      </>
    ),
    facts: ['dsh variants: Web UI PTC · native-tools control · ACP', 'latest CLI versions, frozen per run'],
  },
  {
    title: 'Isolation per attempt',
    body: (
      <>
        Each attempt gets a fresh copy of the seed repository and an isolated HOME containing only a copy of the user's Application Default Credentials (short-lived tokens). No API keys, no
        service-account keys. The environment starts empty with an explicit allowlist, the Google Cloud project is locked, and CLI versions are pinned in a run lock file.
      </>
    ),
    facts: ['ADC only', 'empty env + allowlist', 'lock file per run'],
  },
  {
    title: 'The GEAP Meter',
    body: (
      <>
        Every model call goes through a local recording proxy, by base-URL override or a TLS-intercepting forward proxy for <code className="font-mono text-[0.92em]">*.googleapis.com</code>; all other
        egress is denied. It records the provider's raw usage per call (uncached input, cache read, cache write 5m/1h, output, thinking), latency, time to first token, 429s, tool calls emitted, and
        the thinking level actually requested, verified against the configured level. Harness-internal calls (titles, probes) are tagged <span className="font-mono">aux</span>: billed, not timed.
      </>
    ),
    facts: ['provider-reported usage', 'thinking level verified', 'egress allowlist'],
  },
  {
    title: 'Completion detection',
    body: (
      <>
        A turn is complete when native signals agree: Claude Code and Antigravity Stop hooks, Pi and Oh My Pi extension events, dsh durable turn records, plus Meter quiescence and an idle screen.
        <span className="font-mono"> t0</span> is the moment the prompt is submitted; <span className="font-mono">t_end</span> is when the last model response completed. Detection delay never counts
        against the agent.
      </>
    ),
    facts: ['t0 = prompt submitted', 't_end = last response completed'],
  },
  {
    title: 'Verification by hidden tests',
    body: (
      <>
        Hidden FAIL_TO_PASS tests (the change must make them pass) and PASS_TO_PASS tests (regression guard) run on a throwaway copy of the final workspace. Success is decided only by tests, never by the
        agent's own claim. A task is valid only if the seed fails every FAIL_TO_PASS test and the reference solution passes everything, on three consecutive runs.
      </>
    ),
    facts: ['F2P + P2P', 'validity checked 3× per task'],
  },
  {
    title: 'Retries and infrastructure',
    body: (
      <>
        <b className="font-semibold text-fg">Fresh</b> retries (default) start a new session on a clean repository, so attempts are independent. <b className="font-semibold text-fg">Feedback</b>{' '}
        retries continue the same session with a summary of failing tests, and are reported separately. Infrastructure errors (429 / quota, overload, auth, boot) back off with full jitter and do not
        consume task retries. Concurrency adapts per model × location (AIMD) behind a circuit breaker.
      </>
    ),
    facts: ['fresh by default', 'infra retries are free', 'AIMD + breaker'],
  },
  {
    title: 'Metrics and statistics',
    body: (
      <>
        Tokens by category; tool calls succeeded, failed and retried (including dsh PTC programs vs nested sub-calls); steps; wall, LLM, tool and overhead time; time to success. Aggregates report pass@1
        with Wilson confidence intervals, pass@k (unbiased estimator) and pass^k (consistency) over repeats, bootstrap 95% CIs, cost per solved task and the cost–pass Pareto frontier.
      </>
    ),
    facts: ['pass@1 · Wilson CI', 'pass@k · pass^k', 'bootstrap 95% CI'],
  },
  {
    title: 'Cost, validated in five layers',
    body: (
      <>
        (1) Token integrity: provider-reported usage, cross-checked with harness logs. (2) An explicit, reviewed SKU map built from the Cloud Billing Catalog API. (3) Golden arithmetic tests. (4) A
        cross-check against the public pricing page, including dated promotions, so list and effective cost are both shown. (5) Billing-export reconciliation (planned). Unknown prices are shown as
        "—", never as $0.
      </>
    ),
    facts: ['list vs effective', 'never $0 when unknown'],
  },
]

function Steps() {
  return (
    <ol className="grid grid-cols-1 gap-3 lg:grid-cols-2">
      {STEPS.map((s, i) => (
        <li key={s.title} className="panel flex gap-4 p-5">
          <span className="font-mono text-[12px] font-semibold text-accent num">{String(i + 1).padStart(2, '0')}</span>
          <div className="min-w-0">
            <h3 className="text-[13.5px] font-semibold tracking-[-0.005em]">{s.title}</h3>
            <p className="mt-1.5 text-[12.5px] leading-relaxed text-fg-2">{s.body}</p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {s.facts.map((f) => (
                <Chip key={f} tone="muted" className="border-line">
                  {f}
                </Chip>
              ))}
            </div>
          </div>
        </li>
      ))}
    </ol>
  )
}

function Limitations() {
  const items = [
    ['Feature tickets are precise.', 'Feature tasks spell out interfaces and acceptance criteria so hidden tests can grade them; this favours agents that follow instructions closely over ones that explore.'],
    ['Capability gaps are shown, not hidden.', 'When a harness cannot express a model or thinking level natively (no vanilla route, unsupported control), that cell is marked N/A with the reason instead of being patched.'],
    ['TUI drivers are version-sensitive.', 'Interactive UIs change with every release. Screen signatures are versioned per CLI version, and an unknown version falls back to Meter and screen quiescence.'],
    ['Small samples need repeats.', 'Confidence intervals are wide at low repeat counts; pass@k and pass^k are only reported once there are at least k repeats.'],
  ]
  return (
    <section className="panel border-[color-mix(in_oklab,var(--warn)_30%,var(--line))] p-5">
      <div className="flex items-center gap-2">
        <AlertTriangle className="size-4 text-warn" />
        <h3 className="text-[13.5px] font-semibold">Limitations</h3>
      </div>
      <ul className="mt-3 grid grid-cols-1 gap-x-8 gap-y-3 md:grid-cols-2">
        {items.map(([h, b]) => (
          <li key={h} className="text-[12.5px] leading-relaxed text-fg-2">
            <span className="font-semibold text-fg">{h}</span> {b}
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-2 border-t border-line pt-3 text-[11.5px] text-muted">
        <ShieldCheck className="size-3.5" /> Hidden tests and reference solutions are never published, to prevent benchmark contamination.
      </div>
    </section>
  )
}
