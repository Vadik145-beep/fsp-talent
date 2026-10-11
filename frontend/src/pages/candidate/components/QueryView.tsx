import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { isApiError } from '@/shared/api'
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
  /** Что показать на 404 (объекта нет или он чужой) вместо ошибки с «Повторить». */
  notFound?: ReactNode
}

export function QueryView<T>({ query, children, loading, isEmpty, empty, errorTitle, notFound }: QueryViewProps<T>) {
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
    if (notFound && isApiError(query.error) && query.error.status === 404) return <>{notFound}</>
    return (
      <Card padding="none">
        <ErrorState title={errorTitle} error={query.error} onRetry={() => void query.refetch()} retrying={query.isFetching} />
      </Card>
    )
  }
  if (isEmpty?.(query.data) && empty) return <>{empty}</>
  return <>{children(query.data)}</>
}
