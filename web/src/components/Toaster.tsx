import { AnimatePresence, motion } from 'framer-motion'
import { Lock, X } from 'lucide-react'
import { dismissToast, useToasts } from '@/lib/auth'

export function Toaster() {
  const items = useToasts()
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[min(380px,calc(100vw-32px))] flex-col gap-2" role="status" aria-live="polite">
      <AnimatePresence initial={false}>
        {items.map((t) => (
          <motion.div key={t.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 8 }} className="panel pointer-events-auto flex items-start gap-3 p-3.5 shadow-2xl">
            <Lock className="mt-0.5 size-4 shrink-0 text-warn" />
            <div className="min-w-0 flex-1">
              <div className="text-[12.5px] font-semibold">{t.title}</div>
              {t.body && <div className="mt-0.5 text-[11.5px] text-muted">{t.body}</div>}
              {t.href && (
                <a href={t.href} className="mt-1.5 inline-block text-[12px] font-medium text-accent hover:underline">
                  {t.hrefLabel ?? 'Open'} →
                </a>
              )}
            </div>
            <button onClick={() => dismissToast(t.id)} className="rounded p-0.5 text-muted hover:text-fg" aria-label="Dismiss">
              <X className="size-3.5" />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}
