import { cn } from '@/shared/lib/cn'
import { brandAsset } from './brandAsset'

// --- FspMark --------------------------------------------------------------------------
export interface FspMarkProps {
  className?: string
  /** Подпись для скринридера. Без неё знак декоративный. */
  label?: string
}

/** Знак ФСП (официальный SVG из брендбука). Размер — классом, например size-4. */
export function FspMark({ className, label }: FspMarkProps) {
  return (
    <img
      src={brandAsset('fsp-mark.svg')}
      alt={label ?? ''}
      aria-hidden={label ? undefined : true}
      className={cn('inline-block size-4 shrink-0 object-contain', className)}
      width={16}
      height={16}
    />
  )
}

// --- BrandLines -----------------------------------------------------------------------
const LINES = {
  /** Как на обложках ФСП: линия по верху и вниз со скруглением. */
  corner: { viewBox: '0 0 220 170', d: 'M8 8 H172 A40 40 0 0 1 212 48 V162', dots: [[8, 8], [212, 162]] },
  /** Ступенька, как lineline1.png из брендбука. */
  wave: {
    viewBox: '0 0 240 140',
    d: 'M6 6 V40 A30 30 0 0 0 36 70 H84 A30 30 0 0 1 114 100 V104 A30 30 0 0 0 144 134 H204 A30 30 0 0 0 234 104 V6',
    dots: [[6, 6], [234, 6]],
  },
} as const

/** corner, wave — фигуры фиксированных пропорций; rule — горизонтальный разделитель по ширине. */
export type BrandLinesVariant = keyof typeof LINES | 'rule'

export interface BrandLinesProps {
  variant?: BrandLinesVariant
  className?: string
}

/**
 * Линейная графика бренда ФСП: тонкие линии со скруглениями и точками на концах.
 * Декоративная (aria-hidden). Цвет — через text-*, по умолчанию синий ФСП.
 * Размер задаётся классом (w-40, h-24…); пропорции сохраняются, кроме варианта rule.
 */
export function BrandLines({ variant = 'corner', className }: BrandLinesProps) {
  if (variant === 'rule') {
    return (
      <div className={cn('pointer-events-none flex items-center text-primary', className)} aria-hidden>
        <span className="size-2 shrink-0 rounded-full bg-current" />
        <span className="h-px flex-1 bg-current" />
        <span className="size-2 shrink-0 rounded-full bg-current" />
      </div>
    )
  }
  const shape = LINES[variant]
  return (
    <svg
      viewBox={shape.viewBox}
      fill="none"
      aria-hidden
      focusable="false"
      className={cn('pointer-events-none block text-primary', className)}
    >
      <path d={shape.d} stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {shape.dots.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r={4} fill="currentColor" />
      ))}
    </svg>
  )
}
