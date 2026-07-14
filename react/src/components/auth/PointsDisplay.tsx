import { useBalance } from '@/hooks/use-balance'
import { cn } from '@/lib/utils'

interface PointsDisplayProps {
  children?: React.ReactNode
  className?: string
}

export function PointsDisplay({ children, className }: PointsDisplayProps) {
  const { balance } = useBalance()

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span className="text-xs text-muted-foreground tabular-nums">
        {Number(balance).toFixed(0)} 积分
      </span>
      {children}
    </div>
  )
}
