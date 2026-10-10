import { useMemo, useState, type ReactNode } from 'react'
import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { useMediaQuery } from '@/shared/lib/useMediaQuery'
import { Skeleton } from './States'

export type SortDirection = 'asc' | 'desc'
export interface SortState {
  key: string
  direction: SortDirection
}

export interface TableColumn<T> {
  key: string
  header: ReactNode
  /** Что показать в ячейке. По умолчанию — row[key]. */
  render?: (row: T) => ReactNode
  /** Можно ли сортировать по колонке. */
  sortable?: boolean
  /** Значение для сортировки (по умолчанию row[key]). */
  sortValue?: (row: T) => string | number | null | undefined
  align?: 'left' | 'right' | 'center'
  className?: string
  /** Скрыть колонку на узких экранах. */
  hideOnMobile?: boolean
}

export interface TableProps<T> {
  columns: TableColumn<T>[]
  rows: T[]
  rowKey: (row: T) => string | number
  onRowClick?: (row: T) => void
  /** Внешнее управление сортировкой (например, серверной). Без него — сортировка на клиенте. */
  sort?: SortState | null
  onSortChange?: (sort: SortState | null) => void
  defaultSort?: SortState
  loading?: boolean
  /** Что показать, если строк нет (обычно EmptyState). */
  empty?: ReactNode
  caption?: string
  className?: string
  /**
   * На узком экране (до 640 px) показывать строки карточками: первая колонка — заголовок,
   * остальные — «подпись: значение». Колонки с hideOnMobile в карточке тоже видны.
   */
  mobileCards?: boolean
}

function readValue<T>(row: T, col: TableColumn<T>): string | number | null | undefined {
  if (col.sortValue) return col.sortValue(row)
  const v = (row as Record<string, unknown>)[col.key]
  return typeof v === 'number' || typeof v === 'string' ? v : v == null ? null : String(v)
}

/** Таблица с сортировкой по клику на заголовок (по возрастанию → по убыванию → без сортировки). */
export function Table<T>({
  columns,
  rows,
  rowKey,
  onRowClick,
  sort: controlledSort,
  onSortChange,
  defaultSort,
  loading,
  empty,
  caption,
  className,
  mobileCards,
}: TableProps<T>) {
  const narrow = useMediaQuery('(max-width: 639px)')
  const [innerSort, setInnerSort] = useState<SortState | null>(defaultSort ?? null)
  const isControlled = controlledSort !== undefined
  const sort = isControlled ? controlledSort : innerSort

  function toggle(key: string) {
    let next: SortState | null
    if (!sort || sort.key !== key) next = { key, direction: 'asc' }
    else if (sort.direction === 'asc') next = { key, direction: 'desc' }
    else next = null
    if (!isControlled) setInnerSort(next)
    onSortChange?.(next)
  }

  const sortedRows = useMemo(() => {
    if (!sort || isControlled) return rows
    const col = columns.find((c) => c.key === sort.key)
    if (!col) return rows
    const dir = sort.direction === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const va = readValue(a, col)
      const vb = readValue(b, col)
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * dir
      return String(va).localeCompare(String(vb), 'ru') * dir
    })
  }, [rows, sort, columns, isControlled])

  const alignClass = (a?: 'left' | 'right' | 'center') =>
    a === 'right' ? 'text-right' : a === 'center' ? 'text-center' : 'text-left'

  const cell = (row: T, col: TableColumn<T>) =>
    col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '—')

  if (mobileCards && narrow) {
    const [head, ...rest] = columns
    return (
      <div className={cn('rounded-lg border border-line bg-surface', className)} data-testid="table-cards">
        {caption && <p className="sr-only">{caption}</p>}
        {loading ? (
          <div className="grid gap-3 p-4">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        ) : sortedRows.length === 0 ? (
          (empty ?? <p className="px-4 py-8 text-center text-muted">Нет данных</p>)
        ) : (
          <ul className="divide-y divide-line">
            {sortedRows.map((row) => (
              <li
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === 'Enter') onRowClick(row)
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                className={cn(
                  'grid gap-2 px-4 py-3 text-sm text-ink',
                  onRowClick && 'cursor-pointer transition-colors hover:bg-primary-soft focus-visible:bg-primary-soft',
                )}
              >
                {head && <div className="min-w-0 font-semibold">{cell(row, head)}</div>}
                {rest.length > 0 && (
                  <dl className="grid grid-cols-[auto_minmax(0,1fr)] items-center gap-x-3 gap-y-1.5">
                    {rest.map((col) =>
                      col.header ? (
                        <div key={col.key} className="contents">
                          <dt className="text-[13px] text-muted">{col.header}</dt>
                          <dd className="min-w-0">{cell(row, col)}</dd>
                        </div>
                      ) : (
                        <dd key={col.key} className="col-span-2 min-w-0">
                          {cell(row, col)}
                        </dd>
                      ),
                    )}
                  </dl>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    )
  }

  return (
    <div className={cn('overflow-x-auto rounded-lg border border-line bg-surface', className)}>
      <table className="w-full border-collapse text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead>
          <tr className="border-b border-line bg-surface-muted">
            {columns.map((col) => {
              const active = sort?.key === col.key
              const ariaSort = active ? (sort.direction === 'asc' ? 'ascending' : 'descending') : undefined
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={col.sortable ? (ariaSort ?? 'none') : undefined}
                  className={cn(
                    'px-4 py-2.5 text-xs font-semibold tracking-wide text-muted uppercase',
                    alignClass(col.align),
                    col.hideOnMobile && 'hidden md:table-cell',
                    col.className,
                  )}
                >
                  {col.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggle(col.key)}
                      className={cn(
                        'inline-flex items-center gap-1 uppercase hover:text-ink',
                        active && 'text-ink',
                      )}
                    >
                      {col.header}
                      {active ? (
                        sort.direction === 'asc' ? (
                          <ArrowUp className="size-3.5" aria-hidden />
                        ) : (
                          <ArrowDown className="size-3.5" aria-hidden />
                        )
                      ) : (
                        <ArrowUpDown className="size-3.5 opacity-50" aria-hidden />
                      )}
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                {columns.map((col) => (
                  <td key={col.key} className={cn('px-4 py-3', col.hideOnMobile && 'hidden md:table-cell')}>
                    <Skeleton className="h-4 w-3/4" />
                  </td>
                ))}
              </tr>
            ))
          ) : sortedRows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="p-0">
                {empty ?? <p className="px-4 py-8 text-center text-muted">Нет данных</p>}
              </td>
            </tr>
          ) : (
            sortedRows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                onKeyDown={
                  onRowClick
                    ? (e) => {
                        if (e.key === 'Enter') onRowClick(row)
                      }
                    : undefined
                }
                tabIndex={onRowClick ? 0 : undefined}
                className={cn(
                  'border-b border-line last:border-0',
                  onRowClick && 'cursor-pointer transition-colors hover:bg-primary-soft focus-visible:bg-primary-soft',
                )}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={cn(
                      'px-4 py-3 align-middle text-ink',
                      alignClass(col.align),
                      col.hideOnMobile && 'hidden md:table-cell',
                      col.className,
                    )}
                  >
                    {cell(row, col)}

                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
