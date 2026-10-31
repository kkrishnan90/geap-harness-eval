import * as T from '@radix-ui/react-tooltip'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export const TooltipProvider = T.Provider

export function Tip({ content, children, side = 'top', className }: { content: ReactNode; children: ReactNode; side?: 'top' | 'bottom' | 'left' | 'right'; className?: string }) {
  if (content == null || content === '') return <>{children}</>
  return (
    <T.Root delayDuration={120}>
      <T.Trigger asChild>{children}</T.Trigger>
      <T.Portal>
        <T.Content
          side={side}
          sideOffset={6}
          className={cn(
            'z-50 max-w-[320px] rounded-md border border-line-strong bg-raised px-2.5 py-1.5 text-[11.5px] leading-snug text-fg shadow-xl',
            'data-[state=delayed-open]:animate-in',
            className,
          )}
        >
          {content}
        </T.Content>
      </T.Portal>
    </T.Root>
  )
}
