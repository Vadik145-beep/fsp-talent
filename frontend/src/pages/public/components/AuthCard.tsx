import { useEffect, type ReactNode } from 'react'
import { APP_NAME } from '@/shared/config/env'

/** Карточка формы входа/регистрации по центру экрана. */
export function AuthCard({ title, description, children, footer }: { title: string; description?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  useEffect(() => {
    document.title = `${title} · ${APP_NAME}`
  }, [title])
  return (
    <div className="mx-auto w-full max-w-md py-4 sm:py-10">
      <div className="rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)] sm:p-8">
        <h1 className="text-2xl font-bold">{title}</h1>
        {description && <p className="mt-1 text-[15px] text-muted">{description}</p>}
        <div className="mt-6">{children}</div>
      </div>
      {footer && <div className="mt-4 text-center text-sm text-muted">{footer}</div>}
    </div>
  )
}

/** Блок ошибки над формой. */
export function FormAlert({ children, tone = 'danger' }: { children: ReactNode; tone?: 'danger' | 'info' | 'success' }) {
  const cls =
    tone === 'danger'
      ? 'border-danger/30 bg-danger-soft text-danger'
      : tone === 'success'
        ? 'border-success/30 bg-success-soft text-success'
        : 'border-info/30 bg-info-soft text-info'
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={`mb-4 rounded-md border px-3 py-2.5 text-sm ${cls}`}>
      {children}
    </div>
  )
}

/** Разделитель «или». */
export function OrDivider() {
  return (
    <div className="my-5 flex items-center gap-3 text-xs font-semibold tracking-wide text-subtle uppercase" aria-hidden>
      <span className="h-px flex-1 bg-line" />
      или
      <span className="h-px flex-1 bg-line" />
    </div>
  )
}
