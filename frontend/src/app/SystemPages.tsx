import { isRouteErrorResponse, Link, useRouteError } from 'react-router'
import { Compass, TriangleAlert } from 'lucide-react'
import { BrandLines, Spinner } from '@/shared/ui'

const homeLink =
  'inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover'

/** Экран, пока грузится первый чанк маршрута. */
export function AppLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas text-primary">
      <Spinner size={32} label="Загрузка" />
    </div>
  )
}

export function NotFoundPage() {
  return (
    <div className="flex flex-col items-center gap-4 py-20 text-center">
      <div className="flex items-center gap-3">
        <BrandLines variant="rule" className="w-16 text-primary/40 sm:w-24" />
        <Compass className="size-12 shrink-0 text-primary" strokeWidth={1.5} aria-hidden />
        <BrandLines variant="rule" className="w-16 text-primary/40 sm:w-24" />
      </div>
      <h1 className="text-2xl font-semibold">Страница не найдена</h1>
      <p className="max-w-md text-muted">Возможно, ссылка устарела или в адресе опечатка.</p>
      <Link to="/" className={homeLink}>
        На главную
      </Link>
    </div>
  )
}

/** errorElement корневого маршрута: необработанная ошибка рендера или загрузки. */
export function RouteErrorPage() {
  const error = useRouteError()
  if (isRouteErrorResponse(error) && error.status === 404) {
    return (
      <div className="min-h-screen bg-canvas px-4">
        <NotFoundPage />
      </div>
    )
  }
  const message = error instanceof Error ? error.message : 'Неизвестная ошибка'
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-canvas px-4 text-center">
      <TriangleAlert className="size-12 text-accent" aria-hidden />
      <h1 className="text-2xl font-semibold">Что-то сломалось</h1>
      <p className="max-w-md text-muted">Обновите страницу. Если не поможет — сообщите нам.</p>
      {import.meta.env.DEV && (
        <pre className="max-w-2xl overflow-auto rounded-md bg-surface p-3 text-left text-xs text-danger">{message}</pre>
      )}
      <Link to="/" className={homeLink}>
        На главную
      </Link>
    </div>
  )
}
