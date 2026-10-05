import { Link } from 'react-router'
import { cn } from '@/shared/lib/cn'
import { Skeleton } from '@/shared/ui'
import { useQuota } from '../api'

/** Счётчик квоты активных приглашений: «осталось 19 из 20». */
export function QuotaMeter({ className, compact }: { className?: string; compact?: boolean }) {
  const q = useQuota()
  if (q.isPending) return <Skeleton className={cn('h-10 w-56', className)} />
  if (q.isError) return null
  const { limit, used, left, hint } = q.data
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0
  const tone = left === 0 ? 'bg-danger' : left <= 3 ? 'bg-[#c27100]' : 'bg-fsp-plum'
  return (
    <div className={cn('min-w-0', className)} data-testid="quota-meter">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-ink">Квота приглашений</span>
        <span className="tabular-nums text-muted">
          осталось <b className={cn('text-ink', left === 0 && 'text-danger')}>{left}</b> из {limit}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 overflow-hidden rounded-full bg-line"
        role="meter"
        aria-label="Использовано приглашений"
        aria-valuemin={0}
        aria-valuemax={limit}
        aria-valuenow={used}
      >
        <div className={cn('h-full rounded-full transition-[width]', tone)} style={{ width: `${pct}%` }} />
      </div>
      {!compact && (
        <p className={cn('mt-1 text-[13px]', left === 0 ? 'text-danger' : 'text-muted')}>
          {hint ?? `Активных: ${used}. Ответ или отзыв приглашения освобождает место.`}{' '}
          {left === 0 && (
            <Link to="/recruiter/invitations?status=sent" className="font-semibold underline">
              К приглашениям
            </Link>
          )}
        </p>
      )}
    </div>
  )
}
