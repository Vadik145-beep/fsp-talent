import { cloneElement, isValidElement, useId, useState, type ReactElement, type ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'
import { formatSalaryRange } from '@/shared/lib/format'
import { pseudonymCode } from '@/shared/lib/pseudonym'

// --- SalaryRange ----------------------------------------------------------------------
export interface SalaryRangeProps {
  from?: number | null
  to?: number | null
  currency?: string
  /** Подпись перед суммой, например «Зарплата». */
  label?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/** Вилка зарплаты: «от 250 000 до 350 000 ₽». */
export function SalaryRange({ from, to, currency, label, size = 'md', className }: SalaryRangeProps) {
  const text = formatSalaryRange(from, to, currency)
  const empty = from == null && to == null
  return (
    <span className={cn('inline-flex flex-col', className)}>
      {label && <span className="text-xs font-medium text-muted">{label}</span>}
      <span
        className={cn(
          'font-num font-semibold',
          empty ? 'text-subtle' : 'text-ink',
          size === 'sm' && 'text-sm',
          size === 'md' && 'text-base',
          size === 'lg' && 'text-xl',
        )}
      >
        {text}
      </span>
    </span>
  )
}

// --- Tooltip --------------------------------------------------------------------------
export interface TooltipProps {
  content: ReactNode
  /** Один элемент, который можно сфокусировать (кнопка, ссылка, иконка с tabIndex). */
  children: ReactElement<Record<string, unknown>>
  side?: 'top' | 'bottom'
  className?: string
}

/** Подсказка при наведении и фокусе. */
export function Tooltip({ content, children, side = 'top', className }: TooltipProps) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const trigger = isValidElement(children)
    ? cloneElement(children, { 'aria-describedby': open ? id : undefined })
    : children
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      onKeyDown={(e) => {
        if (e.key === 'Escape') setOpen(false)
      }}
    >
      {trigger}
      {open && (
        <span
          id={id}
          role="tooltip"
          className={cn(
            'pointer-events-none absolute left-1/2 z-40 w-max max-w-64 -translate-x-1/2 animate-fade-in rounded-sm bg-fsp-black px-2.5 py-1.5 text-xs leading-snug font-medium text-white shadow-lg',
            side === 'top' ? 'bottom-full mb-2' : 'top-full mt-2',
            className,
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}

// --- Avatar ---------------------------------------------------------------------------
export interface AvatarProps {
  name: string
  src?: string | null
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const avatarSize = { sm: 'size-8 text-xs', md: 'size-10 text-sm', lg: 'size-14 text-lg' }
// Белые инициалы на любом из фонов — контраст не ниже 6.3:1.
const avatarColors = ['bg-fsp-blue', 'bg-fsp-blue-deep', 'bg-fsp-black', 'bg-info', 'bg-success']

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join('')
}

function colorFor(seed: string) {
  let h = 0
  for (let i = 0; i < seed.length; i++) h = (h * 31 + seed.charCodeAt(i)) >>> 0
  return avatarColors[h % avatarColors.length]
}

export function Avatar({ name, src, size = 'md', className }: AvatarProps) {
  if (src) {
    return <img src={src} alt={name} className={cn('shrink-0 rounded-full object-cover', avatarSize[size], className)} />
  }
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white',
        avatarSize[size],
        colorFor(name),
        className,
      )}
      aria-hidden
    >
      {initials(name) || '?'}
    </span>
  )
}

// --- Pseudonym ------------------------------------------------------------------------
export interface PseudonymProps {
  /** Готовый код («A7F2»). Если нет — будет посчитан из id. */
  code?: string
  id?: string | number
  /** Подпись под псевдонимом: категория, город… */
  subtitle?: ReactNode
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

/** Обезличенный кандидат: «Кандидат #A7F2». ФИО и фото не показываются до принятия приглашения. */
export function Pseudonym({ code, id, subtitle, size = 'md', className }: PseudonymProps) {
  const c = (code ?? (id !== undefined ? pseudonymCode(id) : '????')).toUpperCase()
  return (
    <span className={cn('inline-flex min-w-0 items-center gap-3', className)}>
      <span
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-full bg-primary font-mono font-semibold text-on-primary',
          avatarSize[size],
          // код псевдонима целиком (до 4 знаков), как в подписи «Кандидат #CFAD», — без обрезки «#CF»
          size === 'sm' && 'text-[9px] tracking-tight',
          size === 'md' && 'text-[10px] tracking-tight',
        )}
        aria-hidden
      >
        {c.slice(0, 4)}
      </span>
      <span className="min-w-0">
        <span className="block truncate font-semibold text-ink">Кандидат #{c}</span>
        {subtitle && <span className="block truncate text-[13px] text-muted">{subtitle}</span>}
      </span>
    </span>
  )
}
