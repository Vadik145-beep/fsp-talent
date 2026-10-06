import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { TriangleAlert, CircleCheck, Info, X, CircleX } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export type ToastTone = 'success' | 'error' | 'info' | 'warning'

export interface ToastOptions {
  title: ReactNode
  description?: ReactNode
  tone?: ToastTone
  /** Сколько показывать, мс. 0 — пока не закроют. */
  duration?: number
}

interface ToastItem extends ToastOptions {
  id: number
}

interface ToastApi {
  toast: (options: ToastOptions) => number
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastApi | null>(null)

const toneMeta: Record<ToastTone, { icon: ReactNode; cls: string }> = {
  success: { icon: <CircleCheck className="size-5 text-success" aria-hidden />, cls: 'border-l-success' },
  error: { icon: <CircleX className="size-5 text-accent" aria-hidden />, cls: 'border-l-accent' },
  info: { icon: <Info className="size-5 text-primary" aria-hidden />, cls: 'border-l-primary' },
  warning: { icon: <TriangleAlert className="size-5 text-warning" aria-hidden />, cls: 'border-l-warning' },
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])
  const nextId = useRef(1)

  const dismiss = useCallback((id: number) => {
    setItems((list) => list.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = nextId.current++
      setItems((list) => [...list.slice(-3), { tone: 'info', duration: 4500, ...options, id }])
      const duration = options.duration ?? 4500
      if (duration > 0) setTimeout(() => dismiss(id), duration)
      return id
    },
    [dismiss],
  )

  const api = useMemo(() => ({ toast, dismiss }), [toast, dismiss])

  return (
    <ToastContext.Provider value={api}>
      {children}
      {createPortal(
        <div
          aria-live="polite"
          aria-relevant="additions"
          className="pointer-events-none fixed inset-x-0 bottom-0 z-[60] flex flex-col items-center gap-2 p-4 sm:items-end"
        >
          {items.map((t) => {
            const meta = toneMeta[t.tone ?? 'info']
            return (
              <div
                key={t.id}
                role={t.tone === 'error' ? 'alert' : 'status'}
                className={cn(
                  'pointer-events-auto flex w-full max-w-sm animate-pop-in items-start gap-3 rounded-md border border-l-4 border-line bg-surface p-3.5 shadow-[var(--shadow-pop)]',
                  meta.cls,
                )}
              >
                <span className="mt-0.5 shrink-0">{meta.icon}</span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink">{t.title}</p>
                  {t.description && <p className="mt-0.5 text-[13px] text-muted">{t.description}</p>}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(t.id)}
                  className="shrink-0 rounded-xs p-0.5 text-subtle hover:text-ink"
                  aria-label="Закрыть уведомление"
                >
                  <X className="size-4" aria-hidden />
                </button>
              </div>
            )
          })}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

/** const { toast } = useToast(); toast({ title: 'Приглашение отправлено', tone: 'success' }) */
export function useToast(): ToastApi {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast: нет ToastProvider выше по дереву')
  return ctx
}
