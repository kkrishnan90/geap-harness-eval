import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-[12.5px] font-medium transition-[background,color,border,box-shadow] duration-150 disabled:pointer-events-none disabled:opacity-45 select-none [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary: 'bg-accent text-accent-fg shadow-[0_1px_0_rgba(255,255,255,.18)_inset,0_1px_2px_rgba(0,0,0,.3)] hover:brightness-110',
        secondary: 'bg-raised border border-line text-fg hover:bg-hover hover:border-line-strong',
        ghost: 'text-fg-2 hover:bg-hover hover:text-fg',
        danger: 'bg-transparent border border-line text-fail hover:bg-[color-mix(in_oklab,var(--fail)_12%,transparent)]',
      },
      size: { sm: 'h-7 px-2.5', md: 'h-8 px-3', lg: 'h-9 px-4 text-[13px]', icon: 'h-8 w-8', 'icon-sm': 'h-7 w-7' },
    },
    defaultVariants: { variant: 'secondary', size: 'md' },
  },
)

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild, ...props }, ref) => {
  const Comp = asChild ? Slot : 'button'
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props} />
})
Button.displayName = 'Button'
