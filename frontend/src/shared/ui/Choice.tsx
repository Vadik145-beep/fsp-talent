import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

// --- Checkbox -------------------------------------------------------------------------
export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label: ReactNode
  description?: ReactNode
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, description, className, id, ...rest },
  ref,
) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <div className={cn('flex items-start gap-2.5', className)}>
      <input
        ref={ref}
        id={inputId}
        type="checkbox"
        className="mt-0.5 size-[18px] shrink-0 cursor-pointer rounded-xs border-line-strong accent-primary disabled:cursor-not-allowed"
        aria-describedby={description ? `${inputId}-desc` : undefined}
        {...rest}
      />
      <div className="min-w-0">
        <label htmlFor={inputId} className="cursor-pointer text-sm font-medium text-ink">
          {label}
        </label>
        {description && (
          <p id={`${inputId}-desc`} className="text-[13px] text-muted">
            {description}
          </p>
        )}
      </div>
    </div>
  )
})

// --- Switch ---------------------------------------------------------------------------
export interface SwitchProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label: ReactNode
  description?: ReactNode
  disabled?: boolean
  id?: string
  className?: string
}

export function Switch({ checked, onChange, label, description, disabled, id, className }: SwitchProps) {
  const autoId = useId()
  const switchId = id ?? autoId
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="min-w-0">
        <label htmlFor={switchId} className="cursor-pointer text-sm font-medium text-ink">
          {label}
        </label>
        {description && (
          <p id={`${switchId}-desc`} className="text-[13px] text-muted">
            {description}
          </p>
        )}
      </div>
      <button
        id={switchId}
        type="button"
        role="switch"
        aria-checked={checked}
        aria-describedby={description ? `${switchId}-desc` : undefined}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors',
          'focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)] disabled:cursor-not-allowed disabled:opacity-50',
          checked ? 'bg-primary' : 'bg-line-strong',
        )}
      >
        <span
          className={cn(
            'inline-block size-5 rounded-full bg-white shadow transition-transform',
            checked ? 'translate-x-[22px]' : 'translate-x-0.5',
          )}
        />
      </button>
    </div>
  )
}

// --- RadioGroup -----------------------------------------------------------------------
export interface RadioOption {
  value: string
  label: ReactNode
  description?: ReactNode
  disabled?: boolean
}

export interface RadioGroupProps {
  name?: string
  value: string | null
  onChange: (value: string) => void
  options: RadioOption[]
  label?: ReactNode
  /** cards — крупные карточки (выбор роли, грейда); list — обычные радиокнопки. */
  variant?: 'list' | 'cards'
  orientation?: 'vertical' | 'horizontal'
  error?: ReactNode
  className?: string
}

export function RadioGroup({
  name,
  value,
  onChange,
  options,
  label,
  variant = 'list',
  orientation = 'vertical',
  error,
  className,
}: RadioGroupProps) {
  const autoName = useId()
  const groupName = name ?? autoName
  return (
    <fieldset className={cn('flex flex-col gap-2', className)}>
      {label && <legend className="mb-1.5 text-sm font-medium text-ink">{label}</legend>}
      <div
        className={cn(
          'flex gap-2',
          orientation === 'vertical' ? 'flex-col' : 'flex-row flex-wrap',
          variant === 'cards' && orientation === 'horizontal' && 'grid grid-cols-1 sm:grid-cols-2',
        )}
      >
        {options.map((o) => {
          const optionId = `${groupName}-${o.value}`
          const checked = value === o.value
          return (
            <label
              key={o.value}
              htmlFor={optionId}
              className={cn(
                'flex cursor-pointer items-start gap-2.5',
                variant === 'cards' &&
                  'rounded-lg border border-line-strong bg-surface p-4 transition-colors hover:border-primary',
                variant === 'cards' && checked && 'border-primary bg-primary-soft hover:border-primary',
                o.disabled && 'cursor-not-allowed opacity-60',
              )}
            >
              <input
                id={optionId}
                type="radio"
                name={groupName}
                value={o.value}
                checked={checked}
                disabled={o.disabled}
                onChange={() => onChange(o.value)}
                className="mt-0.5 size-[18px] shrink-0 cursor-pointer accent-primary"
              />
              <span className="min-w-0">
                <span className="block text-sm font-medium text-ink">{o.label}</span>
                {o.description && (
                  <span className="block text-[13px] text-muted">{o.description}</span>
                )}
              </span>
            </label>
          )
        })}
      </div>
      {error && (
        <p className="text-[13px] text-danger" role="alert">
          {error}
        </p>
      )}
    </fieldset>
  )
}
