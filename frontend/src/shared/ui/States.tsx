import type { ReactNode } from 'react'
import { TriangleAlert, Inbox, RotateCw } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { getErrorMessage } from '@/shared/api/client'
import { BrandLines } from './Brand'
import { Button } from './Button'

// --- EmptyState -----------------------------------------------------------------------
export interface EmptyStateProps {
  title: ReactNode
  description?: ReactNode
  icon?: ReactNode
  /** Кнопка действия: «Создать потребность», «Сбросить фильтры»… */
  action?: ReactNode
  className?: string
  compact?: boolean
}

export function EmptyState({ title, description, icon, action, className, compact }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center text-center',
        compact ? 'gap-2 px-4 py-6' : 'gap-3 px-6 py-12',
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {!compact && <BrandLines variant="rule" className="w-10 text-primary/35 sm:w-16" />}
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full border border-primary-tint bg-primary-soft text-primary [&>svg]:size-6">
          {icon ?? <Inbox aria-hidden />}
        </div>
        {!compact && <BrandLines variant="rule" className="w-10 text-primary/35 sm:w-16" />}
      </div>
      <div className="max-w-md">
        <p className="text-base font-semibold text-ink">{title}</p>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {action && <div className="mt-1">{action}</div>}
    </div>
  )
}

// --- ErrorState -----------------------------------------------------------------------
export interface ErrorStateProps {
  title?: ReactNode
  /** Ошибка из useQuery — текст возьмётся из неё. */
  error?: unknown
  description?: ReactNode
  onRetry?: () => void
  retrying?: boolean
  className?: string
}

export function ErrorState({
  title = 'Не удалось загрузить данные',
  error,
  description,
  onRetry,
  retrying,
  className,
}: ErrorStateProps) {
  const text = description ?? (error ? getErrorMessage(error) : 'Проверьте подключение и попробуйте ещё раз.')
  return (
    <div role="alert" className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}>
      <div className="flex size-12 items-center justify-center rounded-full bg-danger-soft text-danger">
        <TriangleAlert className="size-6" aria-hidden />
      </div>
      <div className="max-w-md">
        <p className="text-base font-semibold text-ink">{title}</p>
        <p className="mt-1 text-sm text-muted">{text}</p>
      </div>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} loading={retrying} leftIcon={<RotateCw className="size-4" aria-hidden />}>
          Повторить
        </Button>
      )}
    </div>
  )
}

// --- Skeleton -------------------------------------------------------------------------
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-sm bg-line', className)} aria-hidden />
}

/** Несколько строк-заглушек для текста или списка. */
export function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-2', className)} role="status" aria-label="Загрузка">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-2/3' : 'w-full')} />
      ))}
    </div>
  )
}

/** Заглушка карточки списка. */
export function SkeletonCard({ className }: { className?: string }) {
  return (
    <div className={cn('rounded-lg border border-line bg-surface p-5', className)} role="status" aria-label="Загрузка">
      <div className="flex items-center gap-3">
        <Skeleton className="size-10 rounded-full" />
        <div className="flex-1 space-y-2">
          <Skeleton className="h-4 w-1/2" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      </div>
      <Skeleton className="mt-4 h-3 w-full" />
      <Skeleton className="mt-2 h-3 w-5/6" />
    </div>
  )
}
