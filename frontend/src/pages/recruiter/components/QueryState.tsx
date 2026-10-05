import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { Card, ErrorState, SkeletonCard } from '@/shared/ui'

export interface QueryStateProps<T> {
  query: UseQueryResult<T>
  /** Пустые данные → показать `empty`. */
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
  /** Заглушка загрузки (по умолчанию — 3 карточки-скелета). */
  loading?: ReactNode
  errorTitle?: string
  children: (data: T) => ReactNode
}

/** Загрузка / ошибка / пусто / данные — одинаково на всех экранах рекрутера. */
export function QueryState<T>({ query, isEmpty, empty, loading, errorTitle, children }: QueryStateProps<T>) {
  if (query.isPending) {
    return (
      <>
        {loading ?? (
          <div className="flex flex-col gap-3">
            <SkeletonCard />
            <SkeletonCard />
            <SkeletonCard />
          </div>
        )}
      </>
    )
  }
  if (query.isError) {
    return (
      <Card padding="none">
        <ErrorState
          title={errorTitle}
          error={query.error}
          onRetry={() => void query.refetch()}
          retrying={query.isFetching}
        />
      </Card>
    )
  }
  if (isEmpty?.(query.data) && empty) return <>{empty}</>
  return <>{children(query.data)}</>
}
