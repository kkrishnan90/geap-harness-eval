import * as T from '@radix-ui/react-tabs'
import { cn } from '@/lib/utils'
import type { ComponentProps } from 'react'

export const Tabs = T.Root
export function TabsList({ className, ...p }: ComponentProps<typeof T.List>) {
  return <T.List className={cn('inline-flex h-8 items-center gap-0.5 rounded-lg border border-line bg-sunken p-0.5', className)} {...p} />
}
export function TabsTrigger({ className, ...p }: ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        'h-full rounded-md px-2.5 text-[12px] font-medium text-muted transition-colors hover:text-fg data-[state=active]:bg-raised data-[state=active]:text-fg data-[state=active]:shadow-[0_1px_2px_rgba(0,0,0,.25)]',
        className,
      )}
      {...p}
    />
  )
}
export const TabsContent = T.Content
