import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Card, ErrorState, SkeletonCard } from '@/shared/ui'

/**
 * Три состояния запроса в одном месте: загрузка → ошибка (с «Повторить») → пусто → данные.
 * Кандидат на перенос в shared/ui.
 */
export interface QueryViewProps<T> {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
  /** Что показать при загрузке (по умолчанию — две карточки-скелета). */
  loading?: ReactNode
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  errorTitle?: string
}

export function QueryView<T>({ query, children, loading, isEmpty, empty, errorTitle }: QueryViewProps<T>) {
  if (query.isPending) {
    return (
      loading ?? (
        <div className="grid gap-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )
    )
  }
  if (query.isError) {
    return (
      <Card padding="none">
        <ErrorState title={errorTitle} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />
      </Card>
    )
  }
  if (isEmpty?.(query.data) && empty) return <>{empty}</>
  return <>{children(query.data)}</>
}
