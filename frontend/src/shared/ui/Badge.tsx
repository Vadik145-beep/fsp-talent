import type { HTMLAttributes, ReactNode } from 'react'
import { Check, ShieldCheck, X } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import {
  INVITATION_STATUS_LABELS,
  type InvitationStatus,
} from '@/shared/config/dictionaries'

export type Tone = 'neutral' | 'info' | 'violet' | 'accent' | 'success' | 'warning' | 'danger'

const toneClass: Record<Tone, string> = {
  neutral: 'bg-neutral-soft text-neutral',
  info: 'bg-info-soft text-info',
  violet: 'bg-violet-soft text-violet',
  accent: 'bg-primary-tint text-[#9c0034]',
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
}

// --- Badge ----------------------------------------------------------------------------
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  icon?: ReactNode
}

/** Небольшая метка-статус (не кликабельная). */
export function Badge({ tone = 'neutral', icon, className, children, ...rest }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap [&>svg]:size-3.5',
        toneClass[tone],
        className,
      )}
      {...rest}
    >
      {icon}
      {children}
    </span>
  )
}

/** Бейдж «Подтверждено ФСП» — у достижений и профилей, сверенных с реестром ФСП. */
export function FspVerifiedBadge({ className, label = 'Подтверждено ФСП' }: { className?: string; label?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full bg-fsp-night px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap text-white',
        className,
      )}
    >
      <ShieldCheck className="size-3.5 text-fsp-blush" aria-hidden />
      {label}
    </span>
  )
}

// --- Tag / Chip -----------------------------------------------------------------------
export interface TagProps {
  children: ReactNode
  tone?: Tone
  /** Показать крестик удаления. */
  onRemove?: () => void
  /** Чип-фильтр: кликабельный, с состоянием «выбран». */
  selected?: boolean
  onClick?: () => void
  icon?: ReactNode
  className?: string
}

/** Тег (технология, тема) или чип-фильтр (если передан onClick). */
export function Tag({ children, tone = 'violet', onRemove, selected, onClick, icon, className }: TagProps) {
  const base =
    'inline-flex items-center gap-1 rounded-sm px-2 py-0.5 text-[13px] font-medium whitespace-nowrap [&>svg]:size-3.5'
  if (onClick) {
    return (
      <button
        type="button"
        aria-pressed={selected}
        onClick={onClick}
        className={cn(
          base,
          'h-8 rounded-full border px-3 transition-colors focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]',
          selected
            ? 'border-fsp-plum bg-fsp-plum text-white hover:bg-fsp-night'
            : 'border-line-strong bg-surface text-ink hover:border-fsp-lavender hover:bg-violet-soft',
          className,
        )}
      >
        {selected ? <Check aria-hidden /> : icon}
        {children}
      </button>
    )
  }
  return (
    <span className={cn(base, toneClass[tone], onRemove && 'pr-1', className)}>
      {icon}
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="rounded-xs p-0.5 hover:bg-black/5"
          aria-label={`Убрать ${typeof children === 'string' ? children : ''}`.trim()}
        >
          <X aria-hidden />
        </button>
      )}
    </span>
  )
}

// --- StatusPill (статусы приглашений) -------------------------------------------------
const statusTone: Record<InvitationStatus, { cls: string; dot: string }> = {
  sent: { cls: 'bg-info-soft text-info', dot: 'bg-info' },
  viewed: { cls: 'bg-violet-soft text-violet', dot: 'bg-violet' },
  accepted: { cls: 'bg-success-soft text-success', dot: 'bg-success' },
  declined: { cls: 'bg-danger-soft text-danger', dot: 'bg-danger' },
  expired: { cls: 'bg-neutral-soft text-neutral', dot: 'bg-subtle' },
  withdrawn: { cls: 'bg-warning-soft text-warning', dot: 'bg-warning' },
}

export interface StatusPillProps {
  status: InvitationStatus
  className?: string
}

/** Статус приглашения: Отправлено, Просмотрено, Принято, Отклонено, Истекло, Отозвано. */
export function StatusPill({ status, className }: StatusPillProps) {
  const tone = statusTone[status]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold whitespace-nowrap',
        tone.cls,
        className,
      )}
      data-status={status}
    >
      <span className={cn('size-1.5 rounded-full', tone.dot)} aria-hidden />
      {INVITATION_STATUS_LABELS[status]}
    </span>
  )
}
