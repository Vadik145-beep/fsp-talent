import type { ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { formatSigned } from '@/shared/lib/format'

// --- ProgressBar ----------------------------------------------------------------------
export interface ProgressBarProps {
  /** Текущее значение. */
  value: number
  max?: number
  label?: ReactNode
  /** Показать «7 / 15» или процент справа от подписи. */
  showValue?: 'percent' | 'fraction' | false
  tone?: 'primary' | 'violet' | 'success' | 'warning'
  size?: 'sm' | 'md'
  className?: string
}

const barTone = {
  primary: 'bg-primary',
  violet: 'bg-fsp-plum',
  success: 'bg-success',
  warning: 'bg-[#c27100]',
}

export function ProgressBar({
  value,
  max = 100,
  label,
  showValue = 'percent',
  tone = 'primary',
  size = 'md',
  className,
}: ProgressBarProps) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0
  const valueText = showValue === 'fraction' ? `${value} / ${max}` : `${Math.round(pct)} %`
  return (
    <div className={cn('w-full', className)}>
      {(label || showValue) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-2 text-sm">
          {label && <span className="font-medium text-ink">{label}</span>}
          {showValue && <span className="tabular-nums text-muted">{valueText}</span>}
        </div>
      )}
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-valuetext={valueText}
        aria-label={typeof label === 'string' ? label : undefined}
        className={cn('overflow-hidden rounded-full bg-line', size === 'sm' ? 'h-1.5' : 'h-2.5')}
      >
        <div className={cn('h-full rounded-full transition-[width] duration-300', barTone[tone])} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// --- ScoreBar -------------------------------------------------------------------------
export interface ScoreBarProps {
  /** Фактор ранжирования: «Совпадение стека», «Результат теста»… */
  label: ReactNode
  /** Сила фактора от 0 до 1 (длина полоски). */
  value: number
  /** Вклад в итоговый счёт (например, 0.32 → «+0,32»). */
  contribution?: number
  /** Пояснение под полоской: «4 из 5 обязательных технологий». */
  hint?: ReactNode
  className?: string
}

/** Полоска вклада фактора в счёт — для блока «почему в подборке». */
export function ScoreBar({ label, value, contribution, hint, className }: ScoreBarProps) {
  const pct = Math.min(100, Math.max(0, value * 100))
  return (
    <div className={cn('w-full', className)}>
      <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium text-ink">{label}</span>
        {contribution !== undefined && (
          <span
            className={cn(
              'font-semibold tabular-nums',
              contribution < 0 ? 'text-danger' : 'text-fsp-plum',
            )}
          >
            {formatSigned(contribution)}
          </span>
        )}
      </div>
      <div
        className="h-2 overflow-hidden rounded-full bg-violet-soft"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        aria-label={typeof label === 'string' ? label : undefined}
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-fsp-lavender to-fsp-pink"
          style={{ width: `${pct}%` }}
        />
      </div>
      {hint && <p className="mt-1 text-[13px] text-muted">{hint}</p>}
    </div>
  )
}
