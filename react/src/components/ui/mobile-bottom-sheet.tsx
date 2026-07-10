import * as React from 'react'
import { cn } from '@/lib/utils'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'

type MobileBottomSheetProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  children: React.ReactNode
  className?: string
  contentClassName?: string
  showHandle?: boolean
}

export function MobileBottomSheet({
  open,
  onOpenChange,
  title,
  children,
  className,
  contentClassName,
  showHandle = true,
}: MobileBottomSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="bottom"
        className={cn(
          'rounded-t-2xl px-0 gap-0 pt-0 pb-[max(1rem,env(safe-area-inset-bottom))] max-h-[85dvh]',
          className
        )}
      >
        {showHandle && (
          <div
            aria-hidden
            className="mx-auto mt-2.5 mb-0.5 h-1 w-9 shrink-0 rounded-full bg-muted-foreground/30"
          />
        )}
        <SheetHeader className="px-4 py-2 pr-12 text-left space-y-0">
          <SheetTitle className="text-sm font-medium leading-snug">
            {title}
          </SheetTitle>
        </SheetHeader>
        <div className={cn('px-4 pb-1', contentClassName)}>{children}</div>
      </SheetContent>
    </Sheet>
  )
}
