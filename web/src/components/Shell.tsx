import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useState, type ReactNode } from 'react'
import { Command } from 'cmdk'
import * as Dialog from '@radix-ui/react-dialog'
import { Activity, BookOpenText, Boxes, Eye, ShieldCheck, Coins, FlaskConical, Gauge, LayoutGrid, Moon, Search, Settings2, Sun, SquareTerminal, Pause, Play, Square, Database } from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useTheme } from '@/lib/theme'
import { useRun } from '@/lib/run'
import { useLive } from '@/lib/live'
import { api, getMode, getModeReason } from '@/lib/api'
import { cn } from '@/lib/utils'
import { adminHref, handleWriteError, useMe } from '@/lib/auth'
import { useGcpTarget } from '@/lib/hooks'
import { fmtUsd, fmtDateTime } from '@/lib/format'
import { Kbd, Select } from './ui/misc'
import { Tip } from './ui/tooltip'
import { Button } from './ui/button'
import { StatusPill } from './domain'

export const NAV = [
  { to: '/build', label: 'Run Builder', icon: FlaskConical, key: 'B' },
  { to: '/method', label: 'Tasks & Method', icon: BookOpenText, key: 'T' },
  { to: '/live', label: 'Mission Control', icon: LayoutGrid, key: 'M' },
  { to: '/compare', label: 'Compare', icon: Boxes, key: 'C' },
  { to: '/cost', label: 'Cost Center', icon: Coins, key: '$' },
  { to: '/inspect', label: 'Trial Inspector', icon: SquareTerminal, key: 'I' },
  { to: '/quota', label: 'Quota & Health', icon: Gauge, key: 'Q' },
  { to: '/settings', label: 'Settings', icon: Settings2, key: ',' },
]

function Logo() {
  const { project } = useGcpTarget()
  return (
    <div className="flex items-center gap-2.5 px-1">
      <svg viewBox="0 0 24 24" className="size-6" aria-hidden>
        <rect width="24" height="24" rx="6" fill="var(--raised)" stroke="var(--line-strong)" />
        {[0, 1, 2].flatMap((r) =>
          [0, 1, 2].map((c) => <rect key={`${r}${c}`} x={5 + c * 5} y={5 + r * 5} width={4} height={4} rx={1} fill="var(--accent)" opacity={r === c ? 1 : Math.abs(r - c) === 1 ? 0.5 : 0.22} />),
        )}
      </svg>
      <div className="leading-tight">
        <div className="text-[13px] font-semibold tracking-[-0.01em]">GEAP Harness Eval</div>
        <div className="max-w-[150px] truncate font-mono text-[10px] text-muted">{project ? `${project} · global` : 'global'}</div>
      </div>
    </div>
  )
}

export function Sidebar() {
  const mode = getMode()
  const me = useMe()
  const { identity } = useGcpTarget()
  return (
    <aside className="sticky top-0 hidden h-screen w-[216px] shrink-0 flex-col border-r border-line bg-[var(--bg-grain)] md:flex">
      <div className="flex h-14 items-center px-3">
        <Logo />
      </div>
      <nav className="flex flex-col gap-0.5 px-2 py-2" aria-label="Main">
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            className={({ isActive }) =>
              cn(
                'group relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12.5px] font-medium text-fg-2 transition-colors hover:bg-hover hover:text-fg',
                isActive && 'bg-raised text-fg shadow-[inset_0_0_0_1px_var(--line)]',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && <span className="absolute -left-2 top-1.5 h-5 w-[3px] rounded-r bg-accent" />}
                <n.icon className={cn('size-4', isActive ? 'text-accent' : 'text-muted group-hover:text-fg-2')} strokeWidth={1.75} />
                {n.label}
              </>
            )}
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto space-y-2 p-3">
        <Tip content={mode === 'mock' ? `Simulated data (${getModeReason()}). Start the server on :8787 for real runs.` : `Connected to ${getModeReason()}`}>
          <div className={cn('flex items-center gap-2 rounded-md border px-2.5 py-2 text-[11.5px]', mode === 'mock' ? 'border-[color-mix(in_oklab,var(--warn)_35%,transparent)] text-warn' : 'border-line text-fg-2')}>
            <Database className="size-3.5" />
            <span className="font-medium">{mode === 'mock' ? 'Mock data' : 'Live server'}</span>
            <span className="ml-auto font-mono text-[10px] text-muted">{mode === 'mock' ? 'sim' : ':8787'}</span>
          </div>
        </Tip>
        {me.admin ? (
          <Tip content="Signed in through the admin path: launching and controlling runs is enabled.">
            <div className="flex items-center gap-2 rounded-md border border-accent-line bg-accent-soft px-2.5 py-1.5 text-[11px] text-accent">
              <ShieldCheck className="size-3.5 shrink-0" />
              <span className="truncate font-medium">Admin{me.email ? ` · ${me.email}` : ''}</span>
            </div>
          </Tip>
        ) : (
          <Tip content="Everything is visible; launching, pausing and cancelling runs requires admin sign-in.">
            <a href={adminHref()} className="flex items-center gap-2 rounded-md border border-line px-2.5 py-1.5 text-[11px] text-muted transition-colors hover:border-line-strong hover:text-fg-2">
              <Eye className="size-3.5 shrink-0" />
              <span className="font-medium">Public read-only view</span>
              <span className="ml-auto text-[10px] text-faint">sign in</span>
            </a>
          </Tip>
        )}
        {identity && <div className="truncate px-1 font-mono text-[10px] text-faint" title="Runs use this ADC identity">{identity}</div>}
      </div>
    </aside>
  )
}

function LiveIndicator() {
  const connected = useLive((s) => s.connected)
  const status = useLive((s) => s.run?.status)
  const live = connected === 'open' && status === 'running'
  return (
    <Tip content={connected === 'open' ? 'Event stream connected' : connected === 'error' ? 'Event stream reconnecting…' : 'Not connected'}>
      <span className="inline-flex items-center gap-1.5 font-mono text-[10.5px] uppercase tracking-wider text-muted">
        <span className={cn('size-1.5 rounded-full', live ? 'live-dot bg-pass' : connected === 'error' ? 'bg-fail' : 'bg-idle')} />
        {live ? 'live' : connected === 'error' ? 'retrying' : status ?? 'idle'}
      </span>
    </Tip>
  )
}

export function Topbar({ onPalette, title }: { onPalette: () => void; title: string }) {
  const { theme, toggle } = useTheme()
  const { runs, runId, setRunId, current } = useRun()
  const spend = useLive((s) => s.run?.spend_usd)
  const spendEff = useLive((s) => s.run?.spend_effective_usd)
  const st = useLive((s) => s.run?.status) ?? current?.status
  const qc = useQueryClient()
  const me = useMe()
  const act = async (a: 'pause' | 'resume' | 'cancel') => {
    if (!runId) return
    try {
      await api.action(runId, a)
    } catch (err) {
      if (!handleWriteError(err)) throw err
    }
    qc.invalidateQueries({ queryKey: ['runs'] })
  }
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-line bg-[color-mix(in_oklab,var(--bg)_85%,transparent)] px-4 backdrop-blur-md md:px-5">
      <h1 className="min-w-0 truncate text-[14px] font-semibold tracking-[-0.01em]">{title}</h1>
      <div className="mx-1 hidden h-4 w-px bg-line sm:block" />
      <div className="hidden items-center gap-2 sm:flex">
        <Select aria-label="Run" value={runId ?? ''} onChange={(e) => setRunId(e.target.value)} className="w-[230px]">
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.name} · {r.status} · {fmtDateTime(r.created_at)}
            </option>
          ))}
        </Select>
        {st && <StatusPill status={st} />}
        <LiveIndicator />
      </div>
      <div className="ml-auto flex items-center gap-2">
        {spend != null && (
          <span className="hidden font-mono text-[12px] text-fg-2 num lg:inline">
            {fmtUsd(spendEff ?? spend)} <span className="text-muted">effective</span>
            {spendEff != null && <span className="text-muted"> · {fmtUsd(spend)} list</span>}
          </span>
        )}
        {me.admin && st === 'running' && (
          <Tip content="Pause: in-flight attempts finish, no new attempts are admitted">
            <Button size="icon-sm" variant="ghost" onClick={() => act('pause')} aria-label="Pause run">
              <Pause />
            </Button>
          </Tip>
        )}
        {me.admin && st === 'paused' && (
          <Tip content="Resume run">
            <Button size="icon-sm" variant="ghost" onClick={() => act('resume')} aria-label="Resume run">
              <Play />
            </Button>
          </Tip>
        )}
        {me.admin && (st === 'running' || st === 'paused') && (
          <Tip content="Cancel run">
            <Button size="icon-sm" variant="ghost" onClick={() => act('cancel')} aria-label="Cancel run">
              <Square />
            </Button>
          </Tip>
        )}
        <button onClick={onPalette} className="flex h-8 items-center gap-2 rounded-md border border-line bg-raised pl-2.5 pr-1.5 text-[12px] text-muted transition-colors hover:border-line-strong hover:text-fg-2">
          <Search className="size-3.5" />
          <span className="hidden sm:inline">Jump to…</span>
          <Kbd>⌘K</Kbd>
        </button>
        <Button size="icon" variant="ghost" onClick={toggle} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}>
          {theme === 'dark' ? <Sun /> : <Moon />}
        </Button>
      </div>
    </header>
  )
}

export function CommandPalette({ open, setOpen }: { open: boolean; setOpen: (v: boolean) => void }) {
  const nav = useNavigate()
  const { runs, setRunId, runId } = useRun()
  const { toggle } = useTheme()
  const attempts = useLive((s) => Object.values(s.attempts).filter((a) => ['running', 'verifying', 'backoff', 'preparing'].includes(a.status)))
  const go = (p: string) => {
    nav(p)
    setOpen(false)
  }
  const Item = ({ children, onSelect, value, hint }: { children: ReactNode; onSelect: () => void; value: string; hint?: ReactNode }) => (
    <Command.Item value={value} onSelect={onSelect} className="flex h-9 cursor-pointer items-center gap-2.5 rounded-md px-2.5 text-[12.5px] text-fg-2 data-[selected=true]:bg-hover data-[selected=true]:text-fg">
      {children}
      {hint && <span className="ml-auto font-mono text-[10.5px] text-muted">{hint}</span>}
    </Command.Item>
  )
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-40 bg-black/50 backdrop-blur-[2px]" />
        <Dialog.Content className="fixed left-1/2 top-[14vh] z-50 w-[min(640px,calc(100vw-32px))] -translate-x-1/2 overflow-hidden rounded-xl border border-line-strong bg-panel shadow-2xl" aria-describedby={undefined}>
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command loop>
            <div className="flex items-center gap-2 border-b border-line px-3.5">
              <Search className="size-4 text-muted" />
              <Command.Input autoFocus placeholder="Go to a view, switch run, open a live attempt…" className="h-12 flex-1 bg-transparent text-[13.5px] text-fg outline-none placeholder:text-faint" />
              <Kbd>esc</Kbd>
            </div>
            <Command.List className="max-h-[420px] overflow-y-auto p-1.5">
              <Command.Empty className="px-3 py-8 text-center text-[12.5px] text-muted">No matches.</Command.Empty>
              <Command.Group heading="Views">
                {NAV.map((n) => (
                  <Item key={n.to} value={`view ${n.label}`} onSelect={() => go(n.to)}>
                    <n.icon className="size-4 text-muted" strokeWidth={1.75} /> {n.label}
                  </Item>
                ))}
              </Command.Group>
              {attempts.length > 0 && (
                <Command.Group heading="Live attempts">
                  {attempts.map((a) => (
                    <Item key={a.id} value={`attempt ${a.task_id} ${a.harness} ${a.profile_id} ${a.id}`} onSelect={() => go(`/inspect/${a.trial_id}/${a.id}`)} hint={`attempt ${a.idx}`}>
                      <Activity className="size-4 text-run" strokeWidth={1.75} />
                      <span className="truncate">{a.task_id}</span>
                      <span className="text-muted">· {a.harness} · {a.profile_id}</span>
                    </Item>
                  ))}
                </Command.Group>
              )}
              <Command.Group heading="Runs">
                {runs.map((r) => (
                  <Item
                    key={r.id}
                    value={`run ${r.name} ${r.id}`}
                    onSelect={() => {
                      setRunId(r.id)
                      setOpen(false)
                    }}
                    hint={r.id === runId ? 'current' : r.status}
                  >
                    <Database className="size-4 text-muted" strokeWidth={1.75} /> {r.name}
                  </Item>
                ))}
              </Command.Group>
              <Command.Group heading="Actions">
                <Item
                  value="toggle theme dark light"
                  onSelect={() => {
                    toggle()
                    setOpen(false)
                  }}
                >
                  <Sun className="size-4 text-muted" strokeWidth={1.75} /> Toggle light / dark
                </Item>
                <Item value="new run builder launch" onSelect={() => go('/build')}>
                  <FlaskConical className="size-4 text-muted" strokeWidth={1.75} /> New run
                </Item>
              </Command.Group>
            </Command.List>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  )
}

export function usePaletteHotkey(setOpen: (fn: (v: boolean) => boolean) => void) {
  const nav = useNavigate()
  const loc = useLocation()
  useEffect(() => {
    let g = false
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
        return
      }
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.metaKey || e.ctrlKey) return
      if (e.key === 'g') {
        g = true
        setTimeout(() => (g = false), 800)
        return
      }
      if (g) {
        const m: Record<string, string> = { t: '/method', b: '/build', m: '/live', c: '/compare', $: '/cost', i: '/inspect', q: '/quota', s: '/settings' }
        if (m[e.key]) nav(m[e.key])
        g = false
      }
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [nav, loc, setOpen])
}

export function useNow(ms = 1000) {
  const [n, setN] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setN(Date.now()), ms)
    return () => clearInterval(id)
  }, [ms])
  return n
}
