import * as S from '@radix-ui/react-switch'
import { cn } from '@/lib/utils'

export function Switch({ checked, onCheckedChange, id, disabled, label }: { checked: boolean; onCheckedChange: (v: boolean) => void; id?: string; disabled?: boolean; label?: string }) {
  return (
    <S.Root
      id={id}
      aria-label={label}
      checked={checked}
      disabled={disabled}
      onCheckedChange={onCheckedChange}
      className={cn('relative h-[18px] w-[32px] shrink-0 rounded-full border border-line-strong bg-sunken transition-colors data-[state=checked]:border-accent data-[state=checked]:bg-accent disabled:opacity-40')}
    >
      <S.Thumb className="block h-3 w-3 translate-x-[2px] rounded-full bg-fg-2 shadow transition-transform data-[state=checked]:translate-x-[15px] data-[state=checked]:bg-white" />
    </S.Root>
  )
}
