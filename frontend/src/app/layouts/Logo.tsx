import { Link } from 'react-router'
import { cn } from '@/shared/lib/cn'

/** Текстовый логотип «ФСП · Таланты». tone="light" — на тёмной шапке. */
export function Logo({ to = '/', tone = 'dark', className }: { to?: string; tone?: 'light' | 'dark'; className?: string }) {
  return (
    <Link
      to={to}
      className={cn('inline-flex items-center gap-2 rounded-sm font-bold tracking-tight', className)}
      aria-label="ФСП · Таланты — на главную"
    >
      <span className="flex size-8 items-center justify-center rounded-md bg-primary text-sm text-white">Ф</span>
      <span className={cn('text-[17px] whitespace-nowrap', tone === 'light' ? 'text-white' : 'text-fsp-night')}>
        ФСП <span className="text-fsp-rose">·</span> Таланты
      </span>
    </Link>
  )
}
