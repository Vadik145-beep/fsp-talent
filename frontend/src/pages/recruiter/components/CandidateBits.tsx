import { Check, ShieldOff } from 'lucide-react'
import { Badge, FspVerifiedBadge, Tag, Tooltip } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import { formatDecimal } from '@/shared/lib/format'
import { useSkills, type CandidateCard } from '../api'
import { thetaLevel, thetaSummary } from '../lib'

// --- Стек с подсветкой совпадений ----------------------------------------------------

export interface StackTagsProps {
  stack: string[]
  /** Технологии потребности или фильтра — совпавшие подсвечиваются. */
  highlight?: string[]
  /** Показать не больше N тегов (остальные — «+3»). */
  limit?: number
  className?: string
}

export function StackTags({ stack, highlight = [], limit, className }: StackTagsProps) {
  const skills = useSkills()
  const hl = new Set(highlight)
  // Совпадения — первыми, чтобы были видны сразу.
  const sorted = [...stack].sort((a, b) => Number(hl.has(b)) - Number(hl.has(a)))
  const shown = limit ? sorted.slice(0, limit) : sorted
  const rest = sorted.length - shown.length
  return (
    <ul className={cn('flex flex-wrap gap-1.5', className)} aria-label="Стек">
      {shown.map((s) => (
        <li key={s}>
          {hl.has(s) ? (
            <Tag tone="success" icon={<Check aria-hidden />}>
              <span className="sr-only">Совпадает: </span>
              {skills.label(s)}
            </Tag>
          ) : (
            <Tag tone="neutral">{skills.label(s)}</Tag>
          )}
        </li>
      ))}
      {rest > 0 && (
        <li>
          <Tag tone="neutral">+{rest}</Tag>
        </li>
      )}
    </ul>
  )
}

// --- Бейджи ФСП или нейтральное «нет данных ФСП» -------------------------------------

export function FspBadges({ candidate, compact }: { candidate: Pick<CandidateCard, 'has_fsp' | 'fsp_badges'>; compact?: boolean }) {
  const badges = candidate.fsp_badges ?? []
  if (badges.length) {
    const shown = compact ? badges.slice(0, 1) : badges
    return (
      <span className="flex flex-wrap gap-1.5">
        {shown.map((b) => (
          <FspVerifiedBadge key={b.id} label={b.title} />
        ))}
        {compact && badges.length > 1 && <Badge tone="violet">ещё {badges.length - 1}</Badge>}
      </span>
    )
  }
  return (
    <Badge tone="neutral" icon={<ShieldOff aria-hidden />}>
      Нет данных ФСП
    </Badge>
  )
}

// --- θ понятным языком --------------------------------------------------------------

export function ThetaInfo({ theta, className }: { theta: number | null | undefined; className?: string }) {
  if (theta == null) return <span className={cn('text-sm text-muted', className)}>Тест не пройден</span>
  return (
    <span className={cn('inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 text-sm', className)}>
      <span className="font-semibold text-ink">{thetaSummary(theta)}</span>
      <Tooltip content="θ — оценка уровня по адаптивному тесту. 0 — средний уровень среди всех прошедших, +1 — заметно выше.">
        <button type="button" className="rounded-xs text-muted underline decoration-dotted underline-offset-2 hover:text-ink">
          θ = {formatDecimal(theta)} · {thetaLevel(theta)}
        </button>
      </Tooltip>
    </span>
  )
}
