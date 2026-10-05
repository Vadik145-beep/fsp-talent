import { Link } from 'react-router'
import { CircleCheck, Send, TriangleAlert } from 'lucide-react'
import { Badge, Button, Card, Pseudonym, ScoreBar, StatusPill } from '@/shared/ui'
import { formatPercent } from '@/shared/lib/format'
import type { InvitationStatus } from '@/shared/config/dictionaries'
import { pseudonymCodeOf, type MatchedCandidate } from '../api'
import { WORK_FORMAT_LABELS, yearsText } from '../labels'
import { FspBadges, StackTags } from './CandidateBits'

export interface MatchCardProps {
  match: MatchedCandidate
  rank: number
  /** Технологии потребности — для подсветки совпадений. */
  highlight: string[]
  profileHref: string
  onInvite: () => void
}

const ACTIVE: string[] = ['sent', 'viewed']

/** Карточка подборки: псевдоним, стек с совпадениями, «почему в подборке» и вклад факторов в счёт. */
export function MatchCard({ match, rank, highlight, profileHref, onInvite }: MatchCardProps) {
  const c = match.candidate
  const subtitle = [
    c.category_label,
    c.city,
    c.experience_years != null ? `опыт ${yearsText(c.experience_years)}` : null,
  ]
    .filter(Boolean)
    .join(' · ')
  const status = match.invitation_status as InvitationStatus | null | undefined
  const invited = Boolean(status && ACTIVE.includes(status))
  return (
    <Card padding="none" className="overflow-hidden" data-testid="match-card">
      <div className="flex flex-col gap-4 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-fsp-night text-xs font-bold text-white" aria-label={`Место ${rank}`}>
              {rank}
            </span>
            <Link to={profileHref} className="min-w-0 rounded-sm hover:opacity-80">
              <Pseudonym code={pseudonymCodeOf(c.pseudonym)} subtitle={subtitle} />
            </Link>
          </div>
          <div className="shrink-0 text-right">
            <div className="text-2xl leading-none font-bold text-fsp-plum tabular-nums">{Math.round(match.score * 100)}</div>
            <div className="mt-0.5 text-[11px] font-medium text-muted">соответствие из 100</div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <FspBadges candidate={c} compact />
          {c.work_formats.map((f) => (
            <Badge key={f} tone="neutral">
              {WORK_FORMAT_LABELS[f]}
            </Badge>
          ))}
          {status && <StatusPill status={status} />}
          {!match.salary_fit && (
            <Badge tone="warning" icon={<TriangleAlert aria-hidden />}>
              Ожидания выше вилки
            </Badge>
          )}
        </div>

        <StackTags stack={c.stack} highlight={highlight} />

        <div className="grid gap-5 border-t border-line pt-4 md:grid-cols-2">
          <section aria-label="Почему в подборке">
            <h4 className="mb-2 text-sm font-semibold text-ink">Почему в подборке</h4>
            <ul className="flex flex-col gap-2">
              {match.reasons.map((r) => (
                <li key={r} className="flex gap-2 text-sm text-ink">
                  <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                  <span>{r}</span>
                </li>
              ))}
            </ul>
          </section>
          <section aria-label="Вклад в счёт">
            <h4 className="mb-2 text-sm font-semibold text-ink">Вклад в счёт</h4>
            <div className="flex flex-col gap-2">
              {match.breakdown.map((b) => (
                <ScoreBar
                  key={b.factor}
                  label={
                    <>
                      {b.label} <span className="font-normal text-subtle">· вес {formatPercent(b.weight)}</span>
                    </>
                  }
                  value={b.value}
                  contribution={b.contribution}
                />
              ))}
            </div>
          </section>
        </div>
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line bg-surface-muted px-4 py-3 sm:px-5">
        <Link
          to={profileHref}
          className="inline-flex h-8 items-center rounded-sm px-3 text-[13px] font-semibold text-fsp-plum hover:bg-violet-soft"
        >
          Открыть профиль
        </Link>
        <Button size="sm" onClick={onInvite} disabled={invited} leftIcon={<Send className="size-3.5" aria-hidden />}>
          {invited ? 'Ждём ответа' : status ? 'Пригласить снова' : 'Пригласить'}
        </Button>
      </div>
    </Card>
  )
}
