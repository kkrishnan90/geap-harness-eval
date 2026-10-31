import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

/**
 * Minimal, safe Markdown renderer for task tickets: builds React elements only (never innerHTML).
 * Supports headings, paragraphs, lists, fenced code, blockquotes, pipe tables, and inline code/bold/italic/links.
 */
export function Markdown({ source, className }: { source: string; className?: string }) {
  return <div className={cn('md text-[13px] leading-relaxed text-fg-2', className)}>{renderBlocks(source.replace(/\r\n/g, '\n'))}</div>
}

function renderBlocks(src: string): ReactNode[] {
  const lines = src.split('\n')
  const out: ReactNode[] = []
  let i = 0
  let key = 0
  while (i < lines.length) {
    const line = lines[i]
    if (!line.trim()) {
      i++
      continue
    }
    const fence = line.match(/^\s*(```|~~~)\s*([\w+-]*)/)
    if (fence) {
      const body: string[] = []
      i++
      while (i < lines.length && !lines[i].trim().startsWith(fence[1])) body.push(lines[i++])
      i++
      out.push(
        <pre key={key++} className="my-3 overflow-x-auto rounded-lg border border-line bg-term px-3.5 py-2.5 font-mono text-[11.5px] leading-[1.6] text-[#d7dae0]">
          {fence[2] && <div className="mb-1 font-sans text-[10px] uppercase tracking-wider text-[#7d8591]">{fence[2]}</div>}
          {body.join('\n')}
        </pre>,
      )
      continue
    }
    const h = line.match(/^(#{1,6})\s+(.*)$/)
    if (h) {
      const lvl = h[1].length
      const cls = lvl === 1 ? 'mt-1 mb-3 text-[17px] font-semibold tracking-[-0.01em] text-fg' : lvl === 2 ? 'mt-5 mb-2 text-[13.5px] font-semibold text-fg' : 'mt-4 mb-1.5 text-[12.5px] font-semibold text-fg'
      out.push(
        <div key={key++} role="heading" aria-level={lvl} className={cls}>
          {inline(h[2])}
        </div>,
      )
      i++
      continue
    }
    if (/^\s*>/.test(line)) {
      const body: string[] = []
      while (i < lines.length && /^\s*>/.test(lines[i])) body.push(lines[i++].replace(/^\s*>\s?/, ''))
      out.push(
        <blockquote key={key++} className="my-3 border-l-2 border-accent-line pl-3 text-muted">
          {renderBlocks(body.join('\n'))}
        </blockquote>,
      )
      continue
    }
    if (/^\s*\|.*\|\s*$/.test(line) && i + 1 < lines.length && /^\s*\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const row = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim())
      const head = row(line)
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) rows.push(row(lines[i++]))
      out.push(
        <div key={key++} className="my-3 overflow-x-auto rounded-lg border border-line">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-line text-muted">
                {head.map((c, j) => (
                  <th key={j} className="px-3 py-1.5 text-left font-medium">
                    {inline(c)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r, j) => (
                <tr key={j} className="border-b border-line/50 last:border-0">
                  {r.map((c, k) => (
                    <td key={k} className="px-3 py-1.5">
                      {inline(c)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>,
      )
      continue
    }
    const li = line.match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/)
    if (li) {
      const ordered = /\d/.test(li[2])
      const items: string[] = []
      while (i < lines.length) {
        const m = lines[i].match(/^\s*([-*+]|\d+[.)])\s+(.*)$/)
        if (m) items.push(m[2])
        else if (lines[i].trim() && /^\s{2,}/.test(lines[i]) && items.length) items[items.length - 1] += ' ' + lines[i].trim()
        else break
        i++
      }
      const L = ordered ? 'ol' : 'ul'
      out.push(
        <L key={key++} className={cn('my-2 space-y-1 pl-5', ordered ? 'list-decimal' : 'list-disc marker:text-faint')}>
          {items.map((t, j) => (
            <li key={j}>{inline(t.replace(/^\[( |x)\]\s*/i, (_m, c: string) => (c.trim() ? '☑ ' : '☐ ')))}</li>
          ))}
        </L>,
      )
      continue
    }
    const para: string[] = []
    while (i < lines.length && lines[i].trim() && !/^(#{1,6}\s|\s*```|\s*~~~|\s*>|\s*([-*+]|\d+[.)])\s)/.test(lines[i])) para.push(lines[i++].trim())
    out.push(
      <p key={key++} className="my-2">
        {inline(para.join(' '))}
      </p>,
    )
  }
  return out
}

function inline(text: string): ReactNode[] {
  const out: ReactNode[] = []
  const re = /(`[^`]+`)|(\*\*[^*]+\*\*)|(__[^_]+__)|(\*[^*\s][^*]*\*)|(\[[^\]]+\]\([^)\s]+\))/g
  let last = 0
  let m: RegExpExecArray | null
  let k = 0
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index))
    const t = m[0]
    if (t.startsWith('`')) out.push(<code key={k++} className="rounded border border-line bg-sunken px-1 py-px font-mono text-[0.9em] text-fg">{t.slice(1, -1)}</code>)
    else if (t.startsWith('**') || t.startsWith('__')) out.push(<strong key={k++} className="font-semibold text-fg">{t.slice(2, -2)}</strong>)
    else if (t.startsWith('*')) out.push(<em key={k++}>{t.slice(1, -1)}</em>)
    else {
      const lm = t.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/)!
      const href = lm[2]
      out.push(
        /^https?:\/\//i.test(href) ? (
          <a key={k++} href={href} target="_blank" rel="noopener noreferrer nofollow" className="text-accent hover:underline">
            {lm[1]}
          </a>
        ) : (
          <span key={k++} className="text-fg">
            {lm[1]}
          </span>
        ),
      )
    }
    last = m.index + t.length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}
