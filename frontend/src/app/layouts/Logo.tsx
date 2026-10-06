import { Link } from 'react-router'
import { cn } from '@/shared/lib/cn'
import { brandAsset } from '@/shared/ui'

/**
 * Логотип: официальный знак ФСП (SVG из брендбука) + подпись продукта «Таланты» шрифтом бренда.
 * compact — только знак и подпись; compact="mobile" — знак и подпись только на узких экранах (<640px).
 * tone оставлен для совместимости: шапка теперь светлая, «light» рисует белую подпись для тёмного фона.
 */
export function Logo({
  to = '/',
  tone = 'dark',
  compact = false,
  className,
}: {
  to?: string
  tone?: 'light' | 'dark'
  compact?: boolean | 'mobile'
  className?: string
}) {
  const mark = (extra?: string) => (
    <img src={brandAsset('fsp-mark.svg')} alt="" aria-hidden className={cn('block h-7 w-auto', extra)} width={29} height={28} />
  )
  const full = (extra?: string) => (
    <img src={brandAsset('fsp-logo.svg')} alt="" aria-hidden className={cn('block h-8 w-auto', extra)} width={95} height={32} />
  )
  return (
    <Link
      to={to}
      className={cn('inline-flex shrink-0 items-center gap-2.5 rounded-sm', className)}
      aria-label="ФСП · Таланты — на главную"
    >
      {compact === 'mobile' ? (
        <>
          {mark('sm:hidden')}
          {full('hidden sm:block')}
        </>
      ) : compact ? (
        mark()
      ) : (
        full()
      )}
      <span
        className={cn('h-6 w-px', tone === 'light' ? 'bg-white/40' : 'bg-line-strong')}
        aria-hidden
      />
      <span
        className={cn(
          'font-display text-[17px] leading-none font-semibold tracking-[-0.03em] whitespace-nowrap',
          tone === 'light' ? 'text-white' : 'text-primary',
        )}
      >
        Таланты
      </span>
    </Link>
  )
}
