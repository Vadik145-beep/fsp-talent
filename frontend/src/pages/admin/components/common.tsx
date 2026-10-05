import { useState, type ReactNode } from 'react'
import { ShieldAlert } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { Badge, Button, Modal, Skeleton, Textarea, Tooltip } from '@/shared/ui'
import type { ItemStatus } from '../api'
import { ITEM_STATUS_HINTS, ITEM_STATUS_LABELS, ITEM_STATUS_TONES, num } from '../labels'

// --- StatTile: крупное число с подписью ---------------------------------------------------
export interface StatTileProps {
  label: ReactNode
  value: ReactNode
  hint?: ReactNode
  icon?: ReactNode
  tone?: 'default' | 'accent' | 'warning' | 'success'
  className?: string
}

const tileTone = {
  default: 'bg-violet-soft text-fsp-plum',
  accent: 'bg-primary-soft text-primary',
  warning: 'bg-warning-soft text-warning',
  success: 'bg-success-soft text-success',
}

export function StatTile({ label, value, hint, icon, tone = 'default', className }: StatTileProps) {
  return (
    <div className={cn('flex min-w-0 items-start gap-3 rounded-lg border border-line bg-surface p-4 shadow-[var(--shadow-card)]', className)}>
      {icon && <span className={cn('flex size-10 shrink-0 items-center justify-center rounded-md [&>svg]:size-5', tileTone[tone])}>{icon}</span>}
      <div className="min-w-0">
        <p className="text-[13px] font-medium text-muted">{label}</p>
        <p className="text-2xl leading-tight font-bold tabular-nums text-ink">{value}</p>
        {hint && <p className="mt-0.5 text-[13px] text-muted">{hint}</p>}
      </div>
    </div>
  )
}

export function StatTileSkeleton() {
  return (
    <div className="rounded-lg border border-line bg-surface p-4" role="status" aria-label="Загрузка">
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="mt-3 h-7 w-1/3" />
    </div>
  )
}

// --- Бейджи шаблона ---------------------------------------------------------------------
export function ItemStatusBadge({ status }: { status: ItemStatus }) {
  return (
    <Tooltip content={ITEM_STATUS_HINTS[status]}>
      <span tabIndex={0} className="rounded-full focus-visible:outline-none">
        <Badge tone={ITEM_STATUS_TONES[status]}>{ITEM_STATUS_LABELS[status]}</Badge>
      </span>
    </Tooltip>
  )
}

export function LeakBadge({ score }: { score: number }) {
  return (
    <Badge tone="danger" icon={<ShieldAlert aria-hidden />} title={`Доля верных выше ожидаемой: z = ${num(score)}`}>
      Утечка · z {num(score, 1)}
    </Badge>
  )
}

// --- Окно подтверждения ------------------------------------------------------------------
export interface ConfirmModalProps {
  open: boolean
  onClose: () => void
  onConfirm: (comment: string) => void
  title: ReactNode
  description?: ReactNode
  confirmLabel: string
  danger?: boolean
  loading?: boolean
  /** Показать поле комментария. */
  withComment?: { label: string; placeholder?: string; required?: boolean }
  children?: ReactNode
}

export function ConfirmModal(props: ConfirmModalProps) {
  // Внутренняя часть монтируется заново при каждом открытии — комментарий не тянется с прошлого раза.
  return props.open ? <ConfirmModalBody {...props} /> : null
}

function ConfirmModalBody({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel,
  danger,
  loading,
  withComment,
  children,
}: ConfirmModalProps) {
  const [comment, setComment] = useState('')
  const blocked = Boolean(withComment?.required && !comment.trim())
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button variant={danger ? 'danger' : 'primary'} loading={loading} disabled={blocked} onClick={() => onConfirm(comment.trim())}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      {children}
      {withComment && (
        <Textarea
          label={withComment.label}
          placeholder={withComment.placeholder}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={3}
          required={withComment.required}
          containerClassName={children ? 'mt-4' : undefined}
        />
      )}
    </Modal>
  )
}

/** Секция карточки с заголовком (без лишней рамки). */
export function SectionTitle({ children, hint }: { children: ReactNode; hint?: ReactNode }) {
  return (
    <div className="mb-3">
      <h2 className="text-lg font-semibold">{children}</h2>
      {hint && <p className="text-sm text-muted">{hint}</p>}
    </div>
  )
}
