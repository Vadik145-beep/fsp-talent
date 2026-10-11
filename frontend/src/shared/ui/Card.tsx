import type { HTMLAttributes, ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  padding?: 'none' | 'sm' | 'md' | 'lg'
  /** Подсветка при наведении — для кликабельных карточек. */
  interactive?: boolean
}

const paddingClass = { none: '', sm: 'p-4', md: 'p-5', lg: 'p-6 sm:p-8' }

export function Card({ padding = 'md', interactive, className, children, ...rest }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-line bg-surface shadow-[var(--shadow-card)]',
        paddingClass[padding],
        interactive && 'cursor-pointer transition-[border-color,box-shadow] hover:border-primary hover:shadow-[var(--shadow-pop)]',
        className,
      )}
      {...rest}
    >
      {children}
    </div>
  )
}

export interface CardHeaderProps {
  title: ReactNode
  description?: ReactNode
  actions?: ReactNode
  className?: string
}

export function CardHeader({ title, description, actions, className }: CardHeaderProps) {
  return (
    <div className={cn('mb-4 flex flex-wrap items-start justify-between gap-3', className)}>
      <div className="min-w-0">
        <h3 className="text-base font-semibold">{title}</h3>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {/* На узком экране действия переносятся под заголовок и сами переносятся по строкам — без горизонтальной прокрутки. */}
      {actions && <div className="flex max-w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-2 sm:shrink-0">{actions}</div>}
    </div>
  )
}
