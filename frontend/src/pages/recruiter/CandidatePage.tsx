import { useState, type ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Lock, Mail, MessageCircle, Phone, Send, UserRound } from 'lucide-react'
import { api } from '@/shared/api'
import { categoryLabel, type InvitationStatus } from '@/shared/config/dictionaries'
import { formatDate } from '@/shared/lib/format'
import {
  Badge,
  Button,
  Card,
  CardHeader,
  FspVerifiedBadge,
  PageHeader,
  ProgressBar,
  Pseudonym,
  Skeleton,
  SkeletonCard,
  StatusPill,
} from '@/shared/ui'
import { pseudonymCodeOf, rk, useQuota, type AnonymousProfile, type Need, type S } from './api'
import { WORK_FORMAT_LABELS, yearsText } from './labels'
import { thetaPercentile } from './lib'
import { StackTags, ThetaInfo } from './components/CandidateBits'
import { InviteModal } from './components/InviteModal'
import { QueryState } from './components/QueryState'

const LEVEL_TITLE: Record<S['TopicLevel'], string> = { strong: 'Сильные темы', ok: 'На уровне грейда', weak: 'Зоны роста' }
const LEVEL_TONE = { strong: 'success', ok: 'violet', weak: 'warning' } as const

/** Обезличенный профиль: до принятия приглашения — без ФИО и контактов. */
export default function RecruiterCandidatePage() {
  const id = Number(useParams().id)
  const [sp] = useSearchParams()
  const needId = Number(sp.get('need')) || null
  const [inviteOpen, setInviteOpen] = useState(false)
  const quota = useQuota()

  const profile = useQuery({ queryKey: rk.candidate(id), queryFn: () => api.get<AnonymousProfile>(`/candidates/${id}`) })
  const need = useQuery({
    queryKey: rk.need(needId ?? 0),
    queryFn: () => api.get<Need>(`/matching/needs/${needId}`),
    enabled: needId !== null,
  })
  const back = needId ? { to: `/recruiter/needs/${needId}`, label: 'К подборке' } : { to: '/recruiter/candidates', label: 'Банк кандидатов' }

  if (profile.isPending) {
    return (
      <>
        <Skeleton className="mb-6 h-14 w-80" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </>
    )
  }
  if (profile.isError) {
    return (
      <>
        <PageHeader title="Профиль кандидата" back={back} />
        <QueryState query={profile} errorTitle="Профиль недоступен">
          {() => null}
        </QueryState>
      </>
    )
  }

  const p = profile.data
  const code = pseudonymCodeOf(p.pseudonym)
  const highlight = [...(need.data?.skills_required ?? []), ...(need.data?.skills_desired ?? [])]
  const status = p.invitation_status as InvitationStatus | null | undefined
  const topics = p.topic_scores ?? []
  const inviteBlock = !p.can_invite
    ? status === 'sent' || status === 'viewed'
        ? 'Приглашение уже отправлено — ждём ответа.'
        : quota.data?.left === 0
          ? 'Квота приглашений исчерпана.'
          : 'Сейчас пригласить нельзя.'
    : null

  return (
    <>
      <PageHeader
        title={p.contacts_visible && p.contacts ? p.contacts.full_name : p.pseudonym}
        back={back}
        meta={
          <>
            {p.category_label && <Badge tone="violet">{p.category_label}</Badge>}
            {status && <StatusPill status={status} />}
          </>
        }
        description={[p.city, p.experience_years != null ? `опыт ${yearsText(p.experience_years)}` : null, p.work_formats.map((f) => WORK_FORMAT_LABELS[f]).join(', ')]
          .filter(Boolean)
          .join(' · ')}
        actions={
          <div className="flex flex-col items-end gap-1">
            <Button onClick={() => setInviteOpen(true)} disabled={!p.can_invite} leftIcon={<Send className="size-4" aria-hidden />}>
              Пригласить
            </Button>
            {inviteBlock && <span className="text-[13px] text-muted">{inviteBlock}</span>}
          </div>
        }
      />

      {p.contacts_visible && p.contacts ? (
        <Card className="mb-4 border-success/30 bg-success-soft" data-testid="contacts-open">
          <CardHeader title="Контакты открыты" description="Кандидат принял приглашение или сам откликнулся на вакансию компании." />
          <dl className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <ContactItem icon={<UserRound aria-hidden />} label="ФИО" value={p.contacts.full_name} />
            <ContactItem icon={<Mail aria-hidden />} label="Почта" value={p.contacts.email} href={`mailto:${p.contacts.email}`} />
            <ContactItem icon={<Phone aria-hidden />} label="Телефон" value={p.contacts.phone} href={p.contacts.phone ? `tel:${p.contacts.phone.replace(/[^\d+]/g, '')}` : undefined} />
            <ContactItem icon={<MessageCircle aria-hidden />} label="Telegram" value={p.contacts.telegram} />
          </dl>
        </Card>
      ) : (
        <Card className="mb-4 flex items-start gap-3" padding="sm" data-testid="contacts-hidden">
          <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-violet-soft text-fsp-plum">
            <Lock className="size-4" aria-hidden />
          </span>
          <div className="text-sm">
            <Pseudonym code={code} size="sm" />
            <p className="mt-1 text-muted">
              ФИО и контакты скрыты. Они откроются, когда кандидат примет ваше приглашение. Названия прошлых компаний не показываем.
            </p>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title="Результат теста" description={p.category ? `Категория ${categoryLabel(p.category)} присвоена по адаптивному тесту` : undefined} />
          <ThetaInfo theta={p.theta} />
          {p.theta != null && (
            <ProgressBar className="mt-3" value={Math.round(thetaPercentile(p.theta) * 100)} showValue={false} tone="violet" label="Уровень среди прошедших тест" size="sm" />
          )}
          {(['strong', 'ok', 'weak'] as const).map((level) => {
            const list = topics.filter((t) => t.level === level)
            if (!list.length) return null
            return (
              <section key={level} className="mt-5">
                <h4 className="mb-2 flex items-center gap-2 text-sm font-semibold">
                  <Badge tone={LEVEL_TONE[level]}>{LEVEL_TITLE[level]}</Badge>
                </h4>
                <div className="flex flex-col gap-2.5">
                  {list.map((t) => (
                    <ProgressBar key={t.topic} label={t.label} value={Math.round(t.score * 100)} size="sm" tone={level === 'weak' ? 'warning' : level === 'strong' ? 'success' : 'violet'} />
                  ))}
                </div>
              </section>
            )
          })}
          {!topics.length && <p className="mt-3 text-sm text-muted">Разбор по темам недоступен.</p>}
          {Boolean(p.test_history?.length) && (
            <section className="mt-5 border-t border-line pt-4">
              <h4 className="mb-2 text-sm font-semibold">История тестов</h4>
              <ul className="flex flex-col gap-1 text-sm">
                {p.test_history!.map((h) => (
                  <li key={h.date} className="flex justify-between gap-3">
                    <span>{categoryLabel(h.category)}</span>
                    <span className="text-muted tabular-nums">
                      θ {h.theta.toFixed(2).replace('.', ',')} · {formatDate(h.date)}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </Card>

        <div className="flex flex-col gap-4">
          <Card>
            <CardHeader title="Стек и опыт" description={highlight.length ? 'Зелёным — совпадения с потребностью' : undefined} />
            <StackTags stack={p.stack} highlight={highlight} />
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-muted">Опыт</dt>
                <dd className="font-medium">{p.experience_years != null ? yearsText(p.experience_years) : 'Скрыт кандидатом'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Формат работы</dt>
                <dd className="font-medium">{p.work_formats.map((f) => WORK_FORMAT_LABELS[f]).join(', ') || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Роли в команде</dt>
                <dd className="font-medium">{p.roles_in_team.join(', ') || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted">Софт-скиллы</dt>
                <dd className="font-medium">{p.soft_skills?.join(', ') || '—'}</dd>
              </div>
            </dl>
            <div className="mt-4">
              <ProgressBar label="Свежесть профиля" value={Math.round(p.freshness * 100)} size="sm" tone="primary" />
              <p className="mt-1 text-[13px] text-muted">Растёт, когда кандидат решает регулярные задания.</p>
            </div>
          </Card>

          <Card>
            <CardHeader title="Достижения ФСП" />
            {p.fsp_badges?.length ? (
              <div className="flex flex-col gap-2">
                {p.fsp_badges.map((b) => (
                  <div key={b.id} className="flex flex-wrap items-center gap-2">
                    <FspVerifiedBadge label="Подтверждено ФСП" />
                    <span className="text-sm font-medium">{b.title}</span>
                  </div>
                ))}
                {p.fsp_score != null && <p className="mt-1 text-[13px] text-muted">ФСП-скор: {Math.round(p.fsp_score)} из 100</p>}
              </div>
            ) : (
              <p className="text-sm text-muted" data-testid="no-fsp">
                {p.has_fsp
                  ? 'Кандидат скрыл достижения ФСП настройками приватности.'
                  : 'Нет данных ФСП: кандидат не привязал ФСП ID. Это не минус — оценивайте по тесту.'}
              </p>
            )}
          </Card>
        </div>
      </div>

      <InviteModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        candidate={p}
        need={need.data ? { id: need.data.id, title: need.data.title, salary_from: need.data.salary_from, salary_to: need.data.salary_to } : null}
      />
    </>
  )
}

function ContactItem({ icon, label, value, href }: { icon: ReactNode; label: string; value?: string | null; href?: string }) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 text-success [&>svg]:size-4">{icon}</span>
      <div className="min-w-0">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="truncate font-semibold">
          {value ? href ? <a href={href} className="hover:underline">{value}</a> : value : '—'}
        </dd>
      </div>
    </div>
  )
}
