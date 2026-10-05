import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/** Фокус внутри окна, Escape закрывает, прокрутка страницы блокируется, фокус возвращается. */
function useDialogBehavior(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    const node = ref.current
    // Фокус: [data-autofocus] → первое поле окна (не крестик) → само окно.
    const first =
      node?.querySelector<HTMLElement>('[data-autofocus]') ??
      Array.from(node?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []).find((el) => !el.hasAttribute('data-dialog-close'))
    ;(first ?? node)?.focus()
    const prevOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.stopPropagation()
        onCloseRef.current()
      } else if (e.key === 'Tab' && node) {
        const items = Array.from(node.querySelectorAll<HTMLElement>(FOCUSABLE))
        if (!items.length) return
        const firstItem = items[0]
        const lastItem = items[items.length - 1]
        if (e.shiftKey && document.activeElement === firstItem) {
          e.preventDefault()
          lastItem.focus()
        } else if (!e.shiftKey && document.activeElement === lastItem) {
          e.preventDefault()
          firstItem.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prevOverflow
      previouslyFocused?.focus?.()
    }
  }, [open])

  return ref
}

function CloseButton({ onClose }: { onClose: () => void }) {
  return (
    <button
      type="button"
      onClick={onClose}
      data-dialog-close
      className="rounded-sm p-1.5 text-subtle transition-colors hover:bg-violet-soft hover:text-ink"
      aria-label="Закрыть"
    >
      <X className="size-5" aria-hidden />
    </button>
  )
}

// --- Modal ----------------------------------------------------------------------------
export interface ModalProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  description?: ReactNode
  children?: ReactNode
  /** Кнопки внизу окна. */
  footer?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  /** Закрывать кликом по фону (по умолчанию да). */
  dismissible?: boolean
}

const modalSize = { sm: 'max-w-md', md: 'max-w-xl', lg: 'max-w-3xl' }

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  dismissible = true,
}: ModalProps) {
  const ref = useDialogBehavior(open, onClose)
  const titleId = useId()
  const descId = useId()
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4">
      <div
        className="absolute inset-0 animate-fade-in bg-fsp-night/45 backdrop-blur-[2px]"
        onClick={dismissible ? onClose : undefined}
        aria-hidden
      />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        className={cn(
          'relative flex max-h-[92vh] w-full animate-pop-in flex-col rounded-t-xl bg-surface shadow-[var(--shadow-pop)] outline-none sm:rounded-xl',
          modalSize[size],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4 sm:px-6">
          <div className="min-w-0">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            {description && (
              <p id={descId} className="mt-0.5 text-sm text-muted">
                {description}
              </p>
            )}
          </div>
          <CloseButton onClose={onClose} />
        </div>
        <div className="overflow-y-auto px-5 py-4 sm:px-6">{children}</div>
        {footer && (
          <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3 sm:px-6">
            {footer}
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}

// --- Drawer ---------------------------------------------------------------------------
export interface DrawerProps {
  open: boolean
  onClose: () => void
  title?: ReactNode
  children?: ReactNode
  footer?: ReactNode
  side?: 'left' | 'right'
  /** Ширина панели (класс Tailwind). */
  widthClass?: string
  /** Класс для самой панели (например, тёмный фон меню). */
  panelClassName?: string
  /** Скрыть стандартную шапку с заголовком. */
  hideHeader?: boolean
  ariaLabel?: string
}

export function Drawer({
  open,
  onClose,
  title,
  children,
  footer,
  side = 'right',
  widthClass = 'w-full max-w-md',
  panelClassName,
  hideHeader,
  ariaLabel,
}: DrawerProps) {
  const ref = useDialogBehavior(open, onClose)
  const titleId = useId()
  if (!open) return null
  return createPortal(
    <div className="fixed inset-0 z-50">
      <div className="absolute inset-0 animate-fade-in bg-fsp-night/45" onClick={onClose} aria-hidden />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title && !hideHeader ? titleId : undefined}
        aria-label={ariaLabel}
        tabIndex={-1}
        className={cn(
          'absolute inset-y-0 flex flex-col bg-surface shadow-[var(--shadow-pop)] outline-none',
          side === 'right' ? 'right-0 animate-slide-in-right' : 'left-0 animate-slide-in-left',
          widthClass,
          panelClassName,
        )}
      >
        {!hideHeader && (
          <div className="flex items-center justify-between gap-4 border-b border-line px-5 py-4">
            <h2 id={titleId} className="text-lg font-semibold">
              {title}
            </h2>
            <CloseButton onClose={onClose} />
          </div>
        )}
        <div className="flex-1 overflow-y-auto">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>,
    document.body,
  )
}
