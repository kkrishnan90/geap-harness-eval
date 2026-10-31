import { lazy, Suspense, useState } from 'react'
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './lib/theme'
import { RunProvider } from './lib/run'
import { TooltipProvider } from './components/ui/tooltip'
import { CommandPalette, NAV, Sidebar, Topbar, usePaletteHotkey } from './components/Shell'
import { Skeleton } from './components/ui/misc'
import { cn } from './lib/utils'
import { ErrorBoundary } from './components/ErrorBoundary'
import { BASE_PATH } from './lib/auth'
import { Toaster } from './components/Toaster'
import MissionControl from './views/MissionControl'

const RunBuilder = lazy(() => import('./views/RunBuilder'))
const Compare = lazy(() => import('./views/Compare'))
const CostCenter = lazy(() => import('./views/CostCenter'))
const TrialInspector = lazy(() => import('./views/TrialInspector'))
const Quota = lazy(() => import('./views/Quota'))
const Settings = lazy(() => import('./views/Settings'))
const Method = lazy(() => import('./views/Method'))

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 5_000, refetchOnWindowFocus: false, retry: 1 } } })

const TITLES: Record<string, string> = Object.fromEntries(NAV.map((n) => [n.to, n.label]))

function Layout() {
  const [open, setOpen] = useState(false)
  usePaletteHotkey(setOpen)
  const loc = useLocation()
  const base = '/' + (loc.pathname.split('/')[1] ?? '')
  return (
    <div className="flex min-h-full">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={TITLES[base] ?? 'GEAP Harness Eval'} onPalette={() => setOpen(true)} />
        <nav className="flex gap-1 overflow-x-auto border-b border-line px-3 py-1.5 md:hidden" aria-label="Main">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => cn('shrink-0 rounded-md px-2.5 py-1 text-[12px] text-fg-2', isActive && 'bg-raised text-fg')}>
              {n.label}
            </NavLink>
          ))}
        </nav>
        <main className="min-w-0 flex-1 px-4 py-4 md:px-5 md:py-5">
          <div className="mx-auto max-w-[1680px]">
            <ErrorBoundary label={TITLES[base] ?? 'This view'} resetKey={loc.pathname}>
            <Suspense fallback={<div className="grid gap-3"><Skeleton className="h-24" /><Skeleton className="h-72" /></div>}>
              <Routes>
                <Route path="/" element={<Navigate to="/live" replace />} />
                <Route path="/build" element={<RunBuilder />} />
                <Route path="/live" element={<MissionControl />} />
                <Route path="/compare" element={<Compare />} />
                <Route path="/cost" element={<CostCenter />} />
                <Route path="/inspect" element={<TrialInspector />} />
                <Route path="/inspect/:trialId" element={<TrialInspector />} />
                <Route path="/inspect/:trialId/:attemptId" element={<TrialInspector />} />
                <Route path="/quota" element={<Quota />} />
                <Route path="/settings" element={<Settings />} />
                <Route path="/method" element={<Method />} />
                <Route path="*" element={<Navigate to="/live" replace />} />
              </Routes>
            </Suspense>
            </ErrorBoundary>
          </div>
        </main>
      </div>
      <CommandPalette open={open} setOpen={setOpen} />
      <Toaster />
    </div>
  )
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={qc}>
        <TooltipProvider delayDuration={120}>
          <BrowserRouter basename={BASE_PATH || undefined}>
            <RunProvider>
              <Layout />
            </RunProvider>
          </BrowserRouter>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  )
}
