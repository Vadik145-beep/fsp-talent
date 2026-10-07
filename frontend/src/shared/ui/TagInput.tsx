import { useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { Field } from './Field'

export interface TagInputProps {
  value: string[]
  onChange: (value: string[]) => void
  /** Подсказки (например, справочник стека). */
  options?: string[]
  /** Можно ли добавить значение не из списка. */
  allowCustom?: boolean
  label?: ReactNode
  hint?: ReactNode
  error?: ReactNode
  placeholder?: string
  maxItems?: number
  disabled?: boolean
  id?: string
  className?: string
}

/**
 * Мультивыбор с чипами (стек технологий и т.п.).
 * Enter или запятая — добавить, Backspace в пустом поле — убрать последний, стрелки — по подсказкам.
 */
export function TagInput({
  value,
  onChange,
  options = [],
  allowCustom = true,
  label,
  hint,
  error,
  placeholder = 'Начните вводить…',
  maxItems,
  disabled,
  id,
  className,
}: TagInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const listId = `${inputId}-list`
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)

  const suggestions = useMemo(() => {
    const q = query.trim().toLowerCase()
    const selected = new Set(value.map((v) => v.toLowerCase()))
    return options
      .filter((o) => !selected.has(o.toLowerCase()) && (!q || o.toLowerCase().includes(q)))
      .slice(0, 8)
  }, [options, query, value])

  const full = maxItems !== undefined && value.length >= maxItems

  function add(raw: string) {
    const item = raw.trim()
    if (!item || full) return
    if (value.some((v) => v.toLowerCase() === item.toLowerCase())) {
      setQuery('')
      return
    }
    const fromList = options.find((o) => o.toLowerCase() === item.toLowerCase())
    if (!fromList && !allowCustom) return
    onChange([...value, fromList ?? item])
    setQuery('')
    setActive(0)
  }

  function remove(item: string) {
    onChange(value.filter((v) => v !== item))
    inputRef.current?.focus()
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault()
      if (open && suggestions[active]) add(suggestions[active])
      else add(query)
    } else if (e.key === 'Backspace' && !query && value.length) {
      onChange(value.slice(0, -1))
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => Math.min(i + 1, Math.max(suggestions.length - 1, 0)))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const showList = open && suggestions.length > 0 && !disabled && !full

  return (
    <Field label={label} hint={hint} error={error} htmlFor={inputId} className={className}>
      <div className="relative">
        <div
          className={cn(
            'flex min-h-10 w-full flex-wrap items-center gap-1.5 rounded-md border border-line-strong bg-surface px-2 py-1.5',
            'transition-colors hover:border-subtle focus-within:border-primary focus-within:shadow-[var(--shadow-focus)]',
            error && 'border-danger',
            disabled && 'cursor-not-allowed bg-surface-muted',
          )}
          onClick={() => inputRef.current?.focus()}
        >
          {value.map((item) => (
            <span
              key={item}
              className="inline-flex items-center gap-1 rounded-sm bg-primary-soft py-0.5 pr-1 pl-2 text-[13px] font-medium text-fsp-blue-deep"
            >
              {item}
              {!disabled && (
                <button
                  type="button"
                  className="rounded-xs p-0.5 hover:bg-primary-tint"
                  aria-label={`Убрать ${item}`}
                  onClick={(e) => {
                    e.stopPropagation()
                    remove(item)
                  }}
                >
                  <X className="size-3.5" aria-hidden />
                </button>
              )}
            </span>
          ))}
          <input
            ref={inputRef}
            id={inputId}
            role="combobox"
            aria-expanded={showList}
            aria-controls={listId}
            aria-autocomplete="list"
            aria-activedescendant={showList ? `${listId}-${active}` : undefined}
            aria-invalid={error ? true : undefined}
            disabled={disabled || full}
            value={query}
            placeholder={value.length ? '' : placeholder}
            onChange={(e) => {
              setQuery(e.target.value)
              setOpen(true)
              setActive(0)
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 120)}
            onKeyDown={onKeyDown}
            className="min-w-[8ch] flex-1 bg-transparent px-1 py-0.5 text-[15px] outline-none placeholder:text-subtle disabled:cursor-not-allowed"
          />
        </div>
        {showList && (
          <ul
            id={listId}
            role="listbox"
            className="absolute z-30 mt-1 max-h-60 w-full animate-pop-in overflow-auto rounded-md border border-line bg-surface py-1 shadow-[var(--shadow-pop)]"
          >
            {suggestions.map((s, i) => (
              <li
                key={s}
                id={`${listId}-${i}`}
                role="option"
                aria-selected={i === active}
                className={cn(
                  'cursor-pointer px-3 py-1.5 text-sm',
                  i === active ? 'bg-primary-soft text-fsp-blue-deep' : 'text-ink',
                )}
                onMouseDown={(e) => {
                  e.preventDefault()
                  add(s)
                }}
                onMouseEnter={() => setActive(i)}
              >
                {s}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Field>
  )
}
