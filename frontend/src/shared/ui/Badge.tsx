import type { HTMLAttributes, ReactNode } from 'react'
import { Check, Clock, Eye, Send, Undo2, X, type LucideIcon } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import {
  INVITATION_STATUS_LABELS,
  type InvitationStatus,
} from '@/shared/config/dictionaries'
import { FspMark } from './Brand'

export type Tone = 'neutral' | 'info' | 'violet' | 'accent' | 'success' | 'warning' | 'danger'

const toneClass: Record<Tone, string> = {
  neutral: 'bg-neutral-soft text-neutral',
  info: 'bg-info-soft text-info',
  violet: 'bg-violet-soft text-violet',
  accent: 'bg-primary-tint text-fsp-blue-deep',
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

/** Бейдж «Подтверждено ФСП» (со знаком ФСП) — у достижений и профилей, сверенных с реестром ФСП. */
export function FspVerifiedBadge({ className, label = 'Подтверждено ФСП' }: { className?: string; label?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full bg-primary-soft py-0.5 pr-2.5 pl-1.5 text-xs font-semibold whitespace-nowrap text-fsp-blue-deep ring-1 ring-primary-tint ring-inset',
        className,
      )}
    >
      <FspMark className="size-3.5" />
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
            ? 'border-primary bg-primary text-on-primary hover:bg-primary-hover'
            : 'border-line-strong bg-surface text-ink hover:border-primary hover:bg-primary-soft',
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
          <X className="size-3.5" aria-hidden />
        </button>
      )}
    </span>
  )
}

// --- StatusPill (статусы приглашений) -------------------------------------------------
// Статус различается не только цветом: у каждого своя иконка и подпись.
const statusTone: Record<InvitationStatus, { cls: string; icon: LucideIcon }> = {
  sent: { cls: 'bg-info-soft text-info', icon: Send },
  viewed: { cls: 'bg-violet-soft text-violet', icon: Eye },
  accepted: { cls: 'bg-success-soft text-success', icon: Check },
  declined: { cls: 'bg-danger-soft text-danger', icon: X },
  expired: { cls: 'bg-neutral-soft text-neutral', icon: Clock },
  withdrawn: { cls: 'bg-warning-soft text-warning', icon: Undo2 },
}

export interface StatusPillProps {
  status: InvitationStatus
  className?: string
}

/** Статус приглашения: Отправлено, Просмотрено, Принято, Отклонено, Истекло, Отозвано. */
export function StatusPill({ status, className }: StatusPillProps) {
  const tone = statusTone[status]
  const Icon = tone.icon
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full py-0.5 pr-2.5 pl-2 text-xs font-semibold whitespace-nowrap',
        tone.cls,
        className,
      )}
      data-status={status}
    >
      <Icon className="size-3.5 shrink-0" strokeWidth={2.25} aria-hidden />
      {INVITATION_STATUS_LABELS[status]}
    </span>
  )
}
