import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Inbox, Mail, Plus, Target, Users, UserCheck } from 'lucide-react'
import type { ReactNode } from 'react'
import { api } from '@/shared/api'
import { INVITATION_STATUSES, categoryLabel } from '@/shared/config/dictionaries'
import { formatDate, plural } from '@/shared/lib/format'
import { Card, CardHeader, EmptyState, PageHeader, Skeleton, StatusPill } from '@/shared/ui'
import { rk, type RecruiterDashboard } from './api'
import { ContactRules } from './components/ContactRules'
import { QueryState } from './components/QueryState'
import { QuotaMeter } from './components/QuotaMeter'

const primaryLink =
  'inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:bg-primary-hover'
const secondaryLink =
  'inline-flex h-10 items-center gap-2 rounded-md border border-line-strong bg-surface px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft'

/** Главная рекрутера: потребности, приглашения по статусам, квота, новые отклики. */
export default function RecruiterDashboardPage() {
  const dash = useQuery({ queryKey: rk.dashboard, queryFn: () => api.get<RecruiterDashboard>('/companies/my/dashboard') })
  const d = dash.data
  const by = d?.invitations_by_status ?? {}
  const inWork = (by.sent ?? 0) + (by.viewed ?? 0)
  const maxCount = Math.max(1, ...INVITATION_STATUSES.map((s) => by[s] ?? 0))

  return (
    <>
      <PageHeader
        title={d ? d.company_name : 'Главная'}
        description="Опишите, кого ищете, — получите подборку по категориям из теста и пригласите кандидата с зарплатой."
        actions={
          <>
            <Link to="/recruiter/candidates" className={secondaryLink}>
              <Users className="size-4" aria-hidden />
              Банк кандидатов
            </Link>
            <Link to="/recruiter/needs/new" className={primaryLink}>
              <Plus className="size-4" aria-hidden />
              Новая потребность
            </Link>
          </>
        }
      />

      <QueryState
        query={dash}
        loading={
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24" />
            ))}
          </div>
        }
      >
        {(data) => (
          <>
            <div className="mb-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <Kpi icon={<Target aria-hidden />} label="Активные потребности" value={data.active_needs.length} to="/recruiter/needs" />
              <Kpi icon={<Mail aria-hidden />} label="Приглашения ждут ответа" value={inWork} to="/recruiter/invitations" />
              <Kpi icon={<UserCheck aria-hidden />} label="Приняли приглашение" value={by.accepted ?? 0} to="/recruiter/invitations?status=accepted" />
              <Kpi icon={<Inbox aria-hidden />} label="Новые отклики" value={data.new_applications_count} to="/recruiter/vacancies?tab=applications" accent={data.new_applications_count > 0} />
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              <div className="flex flex-col gap-4">
                <Card>
                  <CardHeader
                    title="Активные потребности"
                    actions={
                      <Link to="/recruiter/needs" className="text-sm font-semibold text-fsp-plum hover:underline">
                        Все
                      </Link>
                    }
                  />
                  {data.active_needs.length ? (
                    <ul className="flex flex-col divide-y divide-line">
                      {data.active_needs.map((n) => (
                        <li key={n.id}>
                          <Link to={`/recruiter/needs/${n.id}`} className="flex items-center justify-between gap-3 py-3 hover:text-fsp-plum">
                            <span className="min-w-0">
                              <span className="block truncate font-semibold">{n.title}</span>
                              <span className="block text-[13px] text-muted">{categoryLabel(n.category)}</span>
                            </span>
                            <span className="flex shrink-0 items-center gap-2 text-sm font-semibold text-fsp-plum">
                              {n.candidates_count} {plural(n.candidates_count, ['кандидат', 'кандидата', 'кандидатов'])}
                              <ArrowRight className="size-4" aria-hidden />
                            </span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState
                      compact
                      title="Потребностей пока нет"
                      action={
                        <Link to="/recruiter/needs/new" className={primaryLink}>
                          Описать потребность
                        </Link>
                      }
                    />
                  )}
                </Card>

                <Card>
                  <CardHeader
                    title="Новые отклики"
                    actions={
                      <Link to="/recruiter/vacancies?tab=applications" className="text-sm font-semibold text-fsp-plum hover:underline">
                        Все отклики
                      </Link>
                    }
                  />
                  {data.recent_applications.length ? (
                    <ul className="flex flex-col divide-y divide-line">
                      {data.recent_applications.map((a) => (
                        <li key={a.id}>
                          <Link to={`/recruiter/vacancies/${a.vacancy_id}`} className="flex items-center justify-between gap-3 py-2.5 text-sm hover:text-fsp-plum">
                            <span className="min-w-0">
                              <span className="block truncate font-medium">{a.vacancy_title}</span>
                              <span className="block text-[13px] text-muted">{a.candidate_pseudonym}</span>
                            </span>
                            <span className="shrink-0 text-[13px] text-muted">{formatDate(a.created_at)}</span>
                          </Link>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyState compact title="Откликов пока нет" />
                  )}
                </Card>
              </div>

              <div className="flex flex-col gap-4">
                <Card>
                  <CardHeader title="Приглашения по статусам" />
                  <ul className="flex flex-col gap-2.5">
                    {INVITATION_STATUSES.map((s) => (
                      <li key={s}>
                        <Link to={`/recruiter/invitations?status=${s}`} className="grid grid-cols-[120px_1fr_32px] items-center gap-3 text-sm hover:opacity-80">
                          <StatusPill status={s} className="justify-self-start" />
                          <span className="h-2 overflow-hidden rounded-full bg-line" aria-hidden>
                            <span className="block h-full rounded-full bg-fsp-lavender" style={{ width: `${((by[s] ?? 0) / maxCount) * 100}%` }} />
                          </span>
                          <b className="text-right tabular-nums">{by[s] ?? 0}</b>
                        </Link>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-5 border-t border-line pt-4">
                    <QuotaMeter />
                  </div>
                </Card>
                <ContactRules />
              </div>
            </div>
          </>
        )}
      </QueryState>
    </>
  )
}

function Kpi({ icon, label, value, to, accent }: { icon: ReactNode; label: string; value: number; to: string; accent?: boolean }) {
  return (
    <Link to={to} className="block rounded-lg focus-visible:shadow-[var(--shadow-focus)] focus-visible:outline-none">
      <Card interactive className="flex h-full items-center gap-4" padding="sm">
        <span className={accent ? 'flex size-11 items-center justify-center rounded-full bg-accent-soft text-accent [&>svg]:size-5' : 'flex size-11 items-center justify-center rounded-full bg-violet-soft text-fsp-plum [&>svg]:size-5'}>
          {icon}
        </span>
        <span>
          <span className="block text-2xl font-bold tabular-nums">{value}</span>
          <span className="block text-[13px] text-muted">{label}</span>
        </span>
      </Card>
    </Link>
  )
}
