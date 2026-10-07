import { GRADE_LABELS, GRADES, type Grade } from '@/shared/config/dictionaries'
import { cn } from '@/shared/lib/cn'
import { formatTheta } from '../labels'

/**
 * Шкала уровня: зоны грейдов по порогам θ, точка — оценка, полоса — 90%-интервал.
 * Пороги по умолчанию — как в настройках платформы (−1 / 0 / 1); точные пороги отдаст бэкенд.
 */
export interface ThetaScaleProps {
  theta: number
  ciLow?: number | null
  ciHigh?: number | null
  thresholds?: { junior: number; middle: number; senior: number }
  className?: string
}

const MIN = -3
const MAX = 3
const ZONE_CLASS: Record<Grade, string> = {
  intern: 'bg-neutral-soft',
  junior: 'bg-primary-soft',
  middle: 'bg-primary-tint',
  senior: 'bg-accent-soft',
}

const pct = (x: number) => ((Math.min(MAX, Math.max(MIN, x)) - MIN) / (MAX - MIN)) * 100

export function ThetaScale({ theta, ciLow, ciHigh, thresholds = { junior: -1, middle: 0, senior: 1 }, className }: ThetaScaleProps) {
  const bounds: Record<Grade, [number, number]> = {
    intern: [MIN, thresholds.junior],
    junior: [thresholds.junior, thresholds.middle],
    middle: [thresholds.middle, thresholds.senior],
    senior: [thresholds.senior, MAX],
  }
  const current = GRADES.find((g) => theta >= bounds[g][0] && theta < bounds[g][1]) ?? (theta >= MAX ? 'senior' : 'intern')
  const hasCi = typeof ciLow === 'number' && typeof ciHigh === 'number'
  return (
    <figure className={cn('w-full', className)}>
      <div className="relative pt-9 pb-1">
        {/* Подпись над точкой */}
        <div className="absolute top-0 -translate-x-1/2 whitespace-nowrap" style={{ left: `${pct(theta)}%` }}>
          <span className="rounded-sm bg-fsp-night px-2 py-0.5 text-xs font-semibold text-white tabular-nums">
            {formatTheta(theta)}
          </span>
        </div>
        <div className="relative flex h-14 overflow-hidden rounded-md">
          {GRADES.map((g) => (
            <div
              key={g}
              className={cn(
                'flex items-start justify-center border-r border-white pt-1.5 text-xs font-semibold last:border-r-0',
                ZONE_CLASS[g],
                g === current ? 'text-fsp-night' : 'text-muted',
              )}
              style={{ width: `${pct(bounds[g][1]) - pct(bounds[g][0])}%` }}
            >
              <span className="truncate px-1">{GRADE_LABELS[g]}</span>
            </div>
          ))}
          {hasCi && (
            <div
              className="absolute top-[70%] h-3 -translate-y-1/2 rounded-full bg-fsp-pink/35 ring-1 ring-fsp-pink/60"
              style={{ left: `${pct(ciLow)}%`, width: `${Math.max(1, pct(ciHigh) - pct(ciLow))}%` }}
              aria-hidden
            />
          )}
          <div
            className="absolute top-[70%] size-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-primary shadow"
            style={{ left: `${pct(theta)}%` }}
            aria-hidden
          />
        </div>
        <div className="relative mt-1 h-4 text-[11px] text-subtle tabular-nums" aria-hidden>
          {[MIN, thresholds.junior, thresholds.middle, thresholds.senior, MAX].map((t, i, all) => (
            <span
              key={t}
              className={cn('absolute', i === 0 ? 'left-0' : i === all.length - 1 ? 'right-0' : '-translate-x-1/2')}
              style={i === 0 || i === all.length - 1 ? undefined : { left: `${pct(t)}%` }}
            >
              {formatTheta(t, 0)}
            </span>
          ))}
        </div>
      </div>
      <figcaption className="sr-only">
        Уровень {formatTheta(theta)}
        {hasCi ? `, с вероятностью 90 % от ${formatTheta(ciLow)} до ${formatTheta(ciHigh)}` : ''}, зона «{GRADE_LABELS[current]}».
      </figcaption>
    </figure>
  )
}
