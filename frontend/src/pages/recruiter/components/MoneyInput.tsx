import { useId, type ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { controlClass, Field } from '@/shared/ui'
import { formatNumber } from '@/shared/lib/format'

export interface MoneyInputProps {
  value: number | null
  onChange: (value: number | null) => void
  label?: ReactNode
  error?: ReactNode
  hint?: ReactNode
  required?: boolean
  placeholder?: string
  id?: string
  className?: string
}

/** Сумма в рублях: ввод только цифр, отображение с разрядами («300 000 ₽»). */
export function MoneyInput({ value, onChange, label, error, hint, required, placeholder, id, className }: MoneyInputProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <Field label={label} error={error} hint={hint} required={required} htmlFor={inputId} className={className}>
      <div className="relative flex items-center">
        <input
          id={inputId}
          inputMode="numeric"
          autoComplete="off"
          value={value === null ? '' : formatNumber(value)}
          placeholder={placeholder}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          onChange={(e) => {
            const digits = e.target.value.replace(/\D/g, '').slice(0, 8)
            onChange(digits ? Number(digits) : null)
          }}
          className={cn(controlClass, 'h-10 pr-8 tabular-nums')}
        />
        <span className="pointer-events-none absolute right-3 text-sm text-subtle" aria-hidden>
          ₽
        </span>
      </div>
    </Field>
  )
}
