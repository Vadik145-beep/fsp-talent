import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

export interface TabItem {
  id: string
  label: ReactNode
  /** Счётчик рядом с названием. */
  count?: number
  disabled?: boolean
  /** Содержимое вкладки. Если не задано — вкладки только переключают value. */
  content?: ReactNode
}

export interface TabsProps {
  items: TabItem[]
  value: string
  onChange: (id: string) => void
  /** underline — вкладки страницы; pills — компактный сегментный переключатель. */
  variant?: 'underline' | 'pills'
  className?: string
  ariaLabel?: string
}

export function Tabs({ items, value, onChange, variant = 'underline', className, ariaLabel }: TabsProps) {
  const baseId = useId()
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const enabled = items.filter((i) => !i.disabled)
  const activeItem = items.find((i) => i.id === value)

  function onKeyDown(e: KeyboardEvent) {
    const idx = enabled.findIndex((i) => i.id === value)
    let next = -1
    if (e.key === 'ArrowRight') next = (idx + 1) % enabled.length
    else if (e.key === 'ArrowLeft') next = (idx - 1 + enabled.length) % enabled.length
    else if (e.key === 'Home') next = 0
    else if (e.key === 'End') next = enabled.length - 1
    if (next < 0) return
    e.preventDefault()
    const target = enabled[next]
    onChange(target.id)
    refs.current[items.indexOf(target)]?.focus()
  }

  return (
    <div className={className}>
      <div
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className={cn(
          'flex overflow-x-auto',
          variant === 'underline' ? 'gap-1 border-b border-line' : 'inline-flex gap-1 rounded-md bg-neutral-soft p-1',
        )}
      >
        {items.map((item, i) => {
          const selected = item.id === value
          return (
            <button
              key={item.id}
              ref={(el) => {
                refs.current[i] = el
              }}
              type="button"
              role="tab"
              id={`${baseId}-tab-${item.id}`}
              aria-selected={selected}
              aria-controls={item.content !== undefined ? `${baseId}-panel-${item.id}` : undefined}
              tabIndex={selected ? 0 : -1}
              disabled={item.disabled}
              onClick={() => onChange(item.id)}
              className={cn(
                'inline-flex shrink-0 items-center gap-2 text-sm font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-50',
                variant === 'underline'
                  ? cn(
                      '-mb-px border-b-2 px-3 py-2.5',
                      selected ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-ink',
                    )
                  : cn(
                      'rounded-sm px-3 py-1.5',
                      selected ? 'bg-surface text-ink shadow-sm' : 'text-muted hover:text-ink',
                    ),
              )}
            >
              {item.label}
              {item.count !== undefined && (
                <span
                  className={cn(
                    'rounded-full px-1.5 font-num text-xs',
                    selected ? 'bg-primary-tint text-fsp-blue-deep' : 'bg-neutral-soft text-neutral',
                  )}
                >
                  {item.count}
                </span>
              )}
            </button>
          )
        })}
      </div>
      {activeItem?.content !== undefined && (
        <div
          role="tabpanel"
          id={`${baseId}-panel-${activeItem.id}`}
          aria-labelledby={`${baseId}-tab-${activeItem.id}`}
          className="pt-4"
        >
          {activeItem.content}
        </div>
      )}
    </div>
  )
}
