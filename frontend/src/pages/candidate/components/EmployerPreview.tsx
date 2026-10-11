import { EyeOff, Lock, MapPin, Briefcase, Link2, ShieldQuestion } from 'lucide-react'
import { Badge, FspVerifiedBadge, ProgressBar, Pseudonym, Tag } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import { plural } from '@/shared/lib/format'
import type { CandidateProfile, PrivacySettings } from '../api'
import { LINK_TYPE_LABELS, TOPIC_LEVEL, WORK_FORMAT_LABELS, formatTheta } from '../labels'

/**
 * «Так вас видит работодатель» до принятия приглашения: обезличенная карточка.
 * Повторяет правила CandidateCard из контракта: нет ФИО, контактов и минимальной зарплаты;
 * город, стаж, ссылки и достижения ФСП — по настройкам приватности.
 */
export interface EmployerPreviewProps {
  profile: CandidateProfile
  privacy: PrivacySettings
  hidden?: { paused: boolean; noConsent: boolean }
  skillLabel?: (id: string) => string
  className?: string
}

function Hidden({ children }: { children: string }) {
  return (
    <span className="inline-flex items-center gap-1 text-[13px] text-subtle">
      <EyeOff className="size-3.5" aria-hidden />
      {children}
    </span>
  )
}

export function EmployerPreview({ profile, privacy, hidden, skillLabel = (id) => id, className }: EmployerPreviewProps) {
  const code = profile.pseudonym.split('#')[1] ?? profile.pseudonym
  const notVisible = hidden && (hidden.paused || hidden.noConsent)
  // все темы, как в карточке у рекрутера (раньше — четыре лучших, и часть тем из разбора пропадала)
  const topics = [...(profile.topic_scores ?? [])].sort((a, b) => b.score - a.score)
  const years = profile.experience_years

  return (
    <div className={cn('rounded-lg border border-line bg-surface', className)}>
      {notVisible && (
        <div className="flex items-start gap-2 rounded-t-lg border-b border-warning/20 bg-warning-soft px-4 py-2.5 text-[13px] text-warning">
          <ShieldQuestion className="mt-0.5 size-4 shrink-0" aria-hidden />
          {hidden?.noConsent
            ? 'Нет согласия на публикацию — сейчас работодатели не видят профиль в поиске.'
            : 'Поиск на паузе — сейчас работодатели не видят профиль в поиске.'}
        </div>
      )}
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <Pseudonym code={code} subtitle={profile.category_label ?? 'Категория не определена'} />
          {typeof profile.theta === 'number' && (
            <Badge tone="violet" title="Оценка уровня по тесту">
              θ {formatTheta(profile.theta)}
            </Badge>
          )}
        </div>

        <dl className="mt-4 grid gap-2 text-sm">
          <div className="flex items-center gap-2">
            <dt className="sr-only">Город</dt>
            <MapPin className="size-4 shrink-0 text-subtle" aria-hidden />
            <dd>{privacy.show_city ? (profile.city ?? 'Город не указан') : <Hidden>Город скрыт</Hidden>}</dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="sr-only">Стаж</dt>
            <Briefcase className="size-4 shrink-0 text-subtle" aria-hidden />
            <dd>
              {privacy.show_experience ? (
                `Стаж ${String(years).replace('.', ',')} ${years % 1 ? 'года' : plural(years, ['год', 'года', 'лет'])}`
              ) : (
                <Hidden>Стаж скрыт</Hidden>
              )}
              {' · '}
              {profile.work_formats.map((f) => WORK_FORMAT_LABELS[f]).join(', ') || 'формат не указан'}
            </dd>
          </div>
          <div className="flex items-center gap-2">
            <dt className="sr-only">Ссылки</dt>
            <Link2 className="size-4 shrink-0 text-subtle" aria-hidden />
            <dd>
              {privacy.show_links ? (
                profile.links?.length ? (
                  profile.links.map((l) => LINK_TYPE_LABELS[l.type]).join(', ')
                ) : (
                  'Ссылок нет'
                )
              ) : (
                <Hidden>Ссылки скрыты</Hidden>
              )}
            </dd>
          </div>
        </dl>

        {profile.stack.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {profile.stack.map((s) => (
              <Tag key={s}>{skillLabel(s)}</Tag>
            ))}
          </div>
        )}

        {topics.length > 0 && (
          <div className="mt-4 grid gap-2.5">
            <p className="text-xs font-semibold tracking-wide text-muted uppercase">Результаты теста по темам</p>
            {topics.map((t) => (
              <ProgressBar key={t.topic} label={t.label} value={Math.round(t.score * 100)} tone={TOPIC_LEVEL[t.level].bar} size="sm" />
            ))}
          </div>
        )}

        <div className="mt-4">
          <p className="mb-1.5 text-xs font-semibold tracking-wide text-muted uppercase">Достижения ФСП</p>
          {!privacy.show_fsp_achievements ? (
            <Hidden>Достижения скрыты</Hidden>
          ) : profile.fsp_badges?.length ? (
            <div className="flex flex-wrap gap-1.5">
              {profile.fsp_badges.map((b) => (
                <FspVerifiedBadge key={b.id} label={b.title} />
              ))}
            </div>
          ) : (
            <span className="text-[13px] text-muted">Нет данных ФСП</span>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2 rounded-md bg-violet-soft px-3 py-2 text-[13px] text-fsp-plum">
          <Lock className="size-4 shrink-0" aria-hidden />
          ФИО, почта и телефон откроются только после принятия приглашения
        </div>
      </div>
    </div>
  )
}
