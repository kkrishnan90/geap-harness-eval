import type { ReactNode, SelectHTMLAttributes, InputHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'
import { ChevronDown } from 'lucide-react'
import { ErrorBoundary } from '../ErrorBoundary'

export function Panel({ title, eyebrow, actions, children, className, bodyClass, id }: { title?: ReactNode; eyebrow?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string; id?: string }) {
  return (
    <section id={id} className={cn('panel flex min-w-0 flex-col', className)}>
      {(title || actions || eyebrow) && (
        <header className="flex min-h-11 flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-b border-line px-4 py-2">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-0.5">{eyebrow}</div>}
            {title && <h2 className="truncate text-[13px] font-semibold tracking-[-0.005em] text-fg">{title}</h2>}
          </div>
          {actions && <div className="flex min-w-0 flex-wrap items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn('min-h-0 flex-1 p-4', bodyClass)}>
        <ErrorBoundary compact label={typeof title === 'string' ? title : 'This panel'}>
          {children}
        </ErrorBoundary>
      </div>
    </section>
  )
}

export function Select({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <div className={cn('relative inline-flex', className)}>
      <select
        className="h-8 w-full appearance-none rounded-md border border-line bg-raised pl-2.5 pr-7 text-[12.5px] text-fg outline-none transition-colors hover:border-line-strong focus-visible:border-accent disabled:opacity-50"
        {...p}
      >
        {children}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2 top-1/2 size-3.5 -translate-y-1/2 text-muted" />
    </div>
  )
}

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-8 rounded-md border border-line bg-raised px-2.5 text-[12.5px] text-fg outline-none transition-colors placeholder:text-faint hover:border-line-strong focus-visible:border-accent',
        className,
      )}
      {...p}
    />
  )
}

export function Segmented<T extends string>({ value, onChange, options, size = 'md', className }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; disabled?: boolean; title?: string }[]; size?: 'sm' | 'md'; className?: string }) {
  return (
    <div role="radiogroup" className={cn('inline-flex items-center gap-0.5 rounded-lg border border-line bg-sunken p-0.5', size === 'sm' ? 'h-7' : 'h-8', className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="radio"
          aria-checked={value === o.value}
          disabled={o.disabled}
          title={o.title}
          onClick={() => onChange(o.value)}
          className={cn(
            'h-full rounded-md px-2.5 text-[12px] font-medium text-muted transition-colors hover:text-fg disabled:cursor-not-allowed disabled:opacity-35',
            value === o.value && 'bg-raised text-fg shadow-[0_1px_2px_rgba(0,0,0,.25)]',
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Chip({ children, tone = 'default', className, title }: { children: ReactNode; tone?: 'default' | 'accent' | 'pass' | 'fail' | 'warn' | 'muted'; className?: string; title?: string }) {
  const tones: Record<string, string> = {
    default: 'border-line bg-raised text-fg-2',
    muted: 'border-transparent bg-transparent text-muted',
    accent: 'border-accent-line bg-accent-soft text-accent',
    pass: 'border-[color-mix(in_oklab,var(--pass)_35%,transparent)] bg-[color-mix(in_oklab,var(--pass)_10%,transparent)] text-pass',
    fail: 'border-[color-mix(in_oklab,var(--fail)_35%,transparent)] bg-[color-mix(in_oklab,var(--fail)_10%,transparent)] text-fail',
    warn: 'border-[color-mix(in_oklab,var(--warn)_35%,transparent)] bg-[color-mix(in_oklab,var(--warn)_10%,transparent)] text-warn',
  }
  return (
    <span title={title} className={cn('inline-flex h-5 items-center gap-1 whitespace-nowrap rounded-[5px] border px-1.5 text-[11px] font-medium leading-none', tones[tone], className)}>
      {children}
    </span>
  )
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded border border-line-strong bg-sunken px-1 font-mono text-[10px] text-muted">{children}</kbd>
}

export function Empty({ title, hint, icon }: { title: string; hint?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex h-full min-h-32 flex-col items-center justify-center gap-1.5 px-6 py-8 text-center">
      {icon && <div className="mb-1 text-faint">{icon}</div>}
      <div className="text-[13px] font-medium text-fg-2">{title}</div>
      {hint && <div className="max-w-sm text-[12px] text-muted">{hint}</div>}
    </div>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-raised', className)} />
}

export function Field({ label, hint, children, className }: { label: ReactNode; hint?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <label className={cn('flex flex-col gap-1.5', className)}>
      <span className="text-[11.5px] font-medium text-fg-2">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-muted">{hint}</span>}
    </label>
  )
}
