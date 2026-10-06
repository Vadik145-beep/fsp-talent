import type { ReactNode } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/shared/lib/cn'

export interface Step {
  id: string
  label: ReactNode
  description?: ReactNode
}

export interface StepperProps {
  steps: Step[]
  /** Индекс текущего шага (с нуля). */
  current: number
  /** Клик по пройденному шагу — вернуться к нему. */
  onStepClick?: (index: number) => void
  className?: string
}

/** Шаги мастера (онбординг соискателя). На мобильном — компактная строка «Шаг 2 из 5». */
export function Stepper({ steps, current, onStepClick, className }: StepperProps) {
  return (
    <nav aria-label="Шаги" className={className}>
      <p className="mb-2 text-sm text-muted sm:hidden">
        Шаг {Math.min(current + 1, steps.length)} из {steps.length}:{' '}
        <span className="font-semibold text-ink">{steps[current]?.label}</span>
      </p>
      <div className="mb-1 h-1.5 overflow-hidden rounded-full bg-line sm:hidden">
        <div
          className="h-full rounded-full bg-primary transition-[width]"
          style={{ width: `${((current + 1) / steps.length) * 100}%` }}
        />
      </div>
      <ol className="hidden items-start sm:flex">
        {steps.map((step, i) => {
          const state = i < current ? 'done' : i === current ? 'current' : 'upcoming'
          const clickable = state === 'done' && onStepClick
          const circle = (
            <span
              className={cn(
                'flex size-8 shrink-0 items-center justify-center rounded-full border-2 font-num text-sm font-semibold transition-colors',
                state === 'done' && 'border-primary bg-primary text-on-primary',
                state === 'current' && 'border-primary bg-surface text-primary',
                state === 'upcoming' && 'border-line-strong bg-surface text-subtle',
              )}
            >
              {state === 'done' ? <Check className="size-4" aria-hidden /> : i + 1}
            </span>
          )
          return (
            <li
              key={step.id}
              className="flex flex-1 items-start last:flex-none"
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <div className="flex flex-col items-center gap-1.5 text-center">
                {clickable ? (
                  <button type="button" onClick={() => onStepClick(i)} aria-label={`Вернуться к шагу ${i + 1}`}>
                    {circle}
                  </button>
                ) : (
                  circle
                )}
                <span
                  className={cn(
                    'max-w-28 text-xs leading-tight font-medium',
                    state === 'upcoming' ? 'text-subtle' : 'text-ink',
                  )}
                >
                  {step.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <span
                  className={cn('mx-2 mt-4 h-px flex-1', i < current ? 'bg-primary' : 'bg-line-strong')}
                  aria-hidden
                />
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
