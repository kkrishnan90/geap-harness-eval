import { useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import { Terminal as XTerm } from '@xterm/xterm'
import { getMode, openPty, type PtyFrame } from '@/lib/api'
import { cn } from '@/lib/utils'

const XTERM_THEME = {
  background: '#0b0c0f',
  foreground: '#d7dae0',
  cursor: '#7c6cff',
  cursorAccent: '#0b0c0f',
  selectionBackground: '#7c6cff44',
  black: '#1b1e24',
  red: '#f0585e',
  green: '#3ccf8e',
  yellow: '#f5b83d',
  blue: '#5aa9e6',
  magenta: '#c08cf0',
  cyan: '#2cc1b0',
  white: '#d7dae0',
  brightBlack: '#5b6270',
  brightRed: '#ff7b80',
  brightGreen: '#6ee7b0',
  brightYellow: '#ffd27a',
  brightBlue: '#8cc8ff',
  brightMagenta: '#d9b4ff',
  brightCyan: '#6fe3d6',
  brightWhite: '#ffffff',
}

export interface TermHandle {
  write: (d: string | Uint8Array) => void
  reset: () => void
}

/**
 * Fixed-geometry xterm: the terminal keeps the PTY's own cols × rows (no reflow, so TUIs render exactly as
 * recorded) and the whole screen is scaled with a CSS transform to fit the container.
 */
export const XtermView = forwardRef<TermHandle, { className?: string; fontSize?: number; cols?: number; rows?: number; align?: 'start' | 'center' }>(function XtermView(
  { className, fontSize = 13, cols = 220, rows = 60, align = 'start' },
  ref,
) {
  const host = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const term = useRef<XTerm | null>(null)
  useImperativeHandle(ref, () => ({
    write: (d) => term.current?.write(d),
    reset: () => term.current?.reset(),
  }))
  useEffect(() => {
    const t = new XTerm({
      cols,
      rows,
      fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
      fontSize,
      lineHeight: 1.15,
      theme: XTERM_THEME,
      convertEol: false,
      disableStdin: true,
      cursorBlink: false,
      cursorStyle: 'bar',
      scrollback: 1000,
      allowProposedApi: true,
    })
    t.open(inner.current!)
    term.current = t
    const fit = () => {
      const h = host.current
      const el = inner.current
      if (!h || !el) return
      const nw = el.scrollWidth || 1
      const nh = el.scrollHeight || 1
      const s = Math.min(h.clientWidth / nw, h.clientHeight / nh)
      el.style.transform = `scale(${s > 0 && Number.isFinite(s) ? s : 1})`
      el.style.left = align === 'center' ? `${Math.max(0, (h.clientWidth - nw * s) / 2)}px` : '0px'
    }
    const ro = new ResizeObserver(fit)
    ro.observe(host.current!)
    ro.observe(inner.current!)
    requestAnimationFrame(fit)
    document.fonts?.ready.then(fit).catch(() => {})
    return () => {
      ro.disconnect()
      t.dispose()
      term.current = null
    }
  }, [fontSize, cols, rows, align])
  return (
    <div ref={host} className={cn('relative h-full w-full overflow-hidden bg-term', className)}>
      <div ref={inner} className="absolute top-0 origin-top-left" style={{ width: 'max-content' }} />
    </div>
  )
})

/** Live PTY bound to WS /api/attempts/{id}/pty. Image frames (dsh screencast) switch to an <img>. */
export function LiveTerminal({ attemptId, className, fallback, cols, rows }: { attemptId: string; className?: string; fallback?: React.ReactNode; cols?: number; rows?: number }) {
  // real PTYs run at 220 × 60; the mock simulator writes ~110-col output
  const c = cols ?? (getMode() === 'mock' ? 110 : 220)
  const r = rows ?? (getMode() === 'mock' ? 34 : 60)
  const ref = useRef<TermHandle>(null)
  const [img, setImg] = useState<string | null>(null)
  const [status, setStatus] = useState<'connecting' | 'open' | 'closed'>('connecting')
  useEffect(() => {
    ref.current?.reset()
    setImg(null)
    const off = openPty(
      attemptId,
      (f: PtyFrame) => {
        if (f.kind === 'image') setImg(f.url)
        else ref.current?.write(f.data)
      },
      (s) => setStatus(s),
    )
    return off
  }, [attemptId])
  return (
    <div className={cn('relative h-full w-full overflow-hidden bg-term', className)}>
      {fallback ? fallback : img ? <img src={img} alt="Live screencast of the dsh web UI" className="h-full w-full object-contain" /> : <XtermView ref={ref} cols={c} rows={r} />}
      {status === 'closed' && !fallback && <div className="absolute right-2 top-2 rounded bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400">stream closed</div>}
    </div>
  )
}
