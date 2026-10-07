import { useEffect, type ReactNode } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, ChevronLeft, ChevronRight, Construction, Search, X } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { APP_NAME } from '@/shared/config/env'
import { Button } from './Button'
import { EmptyState } from './States'
import { Card } from './Card'

// --- PageHeader -----------------------------------------------------------------------
export interface Crumb {
  label: ReactNode
  to?: string
}

export interface PageHeaderProps {
  title: string
  description?: ReactNode
  /** Кнопки справа: «Создать», «Скачать PDF»… */
  actions?: ReactNode
  /** Ссылка «назад» над заголовком. */
  back?: { to: string; label?: string }
  breadcrumbs?: Crumb[]
  /** Доп. элементы рядом с заголовком (бейджи, статус). */
  meta?: ReactNode
  className?: string
}

/** Заголовок экрана. Заодно ставит document.title. */
export function PageHeader({ title, description, actions, back, breadcrumbs, meta, className }: PageHeaderProps) {
  useEffect(() => {
    document.title = `${title} · ${APP_NAME}`
  }, [title])

  return (
    <header className={cn('mb-6', className)}>
      {back && (
        <Link
          to={back.to}
          className="mb-2 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-primary"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {back.label ?? 'Назад'}
        </Link>
      )}
      {breadcrumbs && breadcrumbs.length > 0 && (
        <nav aria-label="Навигация" className="mb-2">
          <ol className="flex flex-wrap items-center gap-1 text-sm text-muted">
            {breadcrumbs.map((c, i) => (
              <li key={i} className="flex items-center gap-1">
                {i > 0 && <ChevronRight className="size-3.5" aria-hidden />}
                {c.to ? (
                  <Link to={c.to} className="hover:text-primary">
                    {c.label}
                  </Link>
                ) : (
                  <span className="text-ink">{c.label}</span>
                )}
              </li>
            ))}
          </ol>
        </nav>
      )}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl leading-tight font-semibold sm:text-[28px]">{title}</h1>
            {meta}
          </div>
          {description && <p className="mt-1 max-w-3xl text-[15px] text-muted">{description}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </div>
    </header>
  )
}

// --- FilterBar ------------------------------------------------------------------------
export interface FilterBarProps {
  search?: { value: string; onChange: (value: string) => void; placeholder?: string }
  /** Сколько фильтров выбрано — показывает «Сбросить». */
  activeCount?: number
  onReset?: () => void
  /** Селекты, чипы и прочие фильтры. */
  children?: ReactNode
  /** Справа: сортировка, переключатель вида. */
  actions?: ReactNode
  className?: string
}

export function FilterBar({ search, activeCount = 0, onReset, children, actions, className }: FilterBarProps) {
  return (
    <div className={cn('mb-4 flex flex-col gap-3 rounded-lg border border-line bg-surface p-3 sm:p-4', className)}>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end">
        {search && (
          <div className="relative min-w-0 sm:min-w-64 sm:flex-1">
            <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" aria-hidden />
            <input
              type="search"
              value={search.value}
              onChange={(e) => search.onChange(e.target.value)}
              placeholder={search.placeholder ?? 'Поиск'}
              aria-label={search.placeholder ?? 'Поиск'}
              className="h-10 w-full rounded-md border border-line-strong bg-surface pr-3 pl-9 text-[15px] placeholder:text-subtle hover:border-subtle focus:border-primary focus:shadow-[var(--shadow-focus)] focus:outline-none"
            />
          </div>
        )}
        {children}
        {(actions || (onReset && activeCount > 0)) && (
          <div className="flex items-center gap-2 sm:ml-auto">
            {onReset && activeCount > 0 && (
              <Button variant="ghost" size="md" onClick={onReset} leftIcon={<X className="size-4" aria-hidden />}>
                Сбросить ({activeCount})
              </Button>
            )}
            {actions}
          </div>
        )}
      </div>
    </div>
  )
}

// --- Pagination -----------------------------------------------------------------------
export interface PaginationProps {
  /** Текущая страница, с 1. */
  page: number
  pageCount: number
  onChange: (page: number) => void
  className?: string
}

function pageList(page: number, count: number): Array<number | 'gap'> {
  if (count <= 7) return Array.from({ length: count }, (_, i) => i + 1)
  const set = new Set([1, count, page - 1, page, page + 1])
  const sorted = [...set].filter((p) => p >= 1 && p <= count).sort((a, b) => a - b)
  const out: Array<number | 'gap'> = []
  sorted.forEach((p, i) => {
    if (i > 0 && p - sorted[i - 1] > 1) out.push('gap')
    out.push(p)
  })
  return out
}

export function Pagination({ page, pageCount, onChange, className }: PaginationProps) {
  if (pageCount <= 1) return null
  const btn =
    'inline-flex h-9 min-w-9 items-center justify-center rounded-md px-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-40'
  return (
    <nav aria-label="Страницы" className={cn('flex items-center justify-center gap-1', className)}>
      <button
        type="button"
        className={cn(btn, 'text-primary hover:bg-primary-soft')}
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        aria-label="Предыдущая страница"
      >
        <ChevronLeft className="size-4" aria-hidden />
      </button>
      {pageList(page, pageCount).map((p, i) =>
        p === 'gap' ? (
          <span key={`gap-${i}`} className="px-1 text-subtle" aria-hidden>
            …
          </span>
        ) : (
          <button
            key={p}
            type="button"
            onClick={() => onChange(p)}
            aria-current={p === page ? 'page' : undefined}
            className={cn(btn, 'font-num', p === page ? 'bg-primary text-on-primary' : 'text-ink hover:bg-primary-soft')}
          >
            {p}
          </button>
        ),
      )}
      <button
        type="button"
        className={cn(btn, 'text-primary hover:bg-primary-soft')}
        onClick={() => onChange(page + 1)}
        disabled={page >= pageCount}
        aria-label="Следующая страница"
      >
        <ChevronRight className="size-4" aria-hidden />
      </button>
    </nav>
  )
}

// --- ScreenStub -----------------------------------------------------------------------
export interface ScreenStubProps {
  title: string
  /** Что будет на экране (из карты экранов). */
  description?: ReactNode
  route?: string
}

/** Заглушка экрана каркаса. Трек волны 1 заменяет её содержимым. */
export function ScreenStub({ title, description, route }: ScreenStubProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <Card padding="none">
        <EmptyState
          icon={<Construction aria-hidden />}
          title="Экран в работе"
          description={route ? `Маршрут ${route} зарегистрирован, содержимое появится в волне 1.` : undefined}
        />
      </Card>
    </>
  )
}
