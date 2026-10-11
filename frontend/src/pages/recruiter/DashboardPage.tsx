import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Plus, Users } from 'lucide-react'
import { api } from '@/shared/api'
import { categoryLabel } from '@/shared/config/dictionaries'
import { formatDate, plural } from '@/shared/lib/format'
import { Card, CardHeader, EmptyState, PageHeader, Skeleton } from '@/shared/ui'
import { rk, useQuota, type RecruiterDashboard } from './api'
import { QueryState } from './components/QueryState'

const primaryLink =
  'inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:bg-primary-hover'
const secondaryLink =
  'inline-flex h-10 items-center gap-2 rounded-md border border-line-strong bg-surface px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft'

/** Главная рекрутера: строка про приглашения, активные поиски кандидатов, новые отклики. */
export default function RecruiterDashboardPage() {
  const dash = useQuery({ queryKey: rk.dashboard, queryFn: () => api.get<RecruiterDashboard>('/companies/my/dashboard') })
  const d = dash.data
  const by = d?.invitations_by_status ?? {}
  const inWork = (by.sent ?? 0) + (by.viewed ?? 0)
  const quota = useQuota()

  return (
    <>
      <PageHeader
        title={d ? d.company_name : 'Главная'}
        description="Опишите, кого ищете, — получите подборку кандидатов и пригласите подходящих."
        actions={
          <>
            <Link to="/recruiter/candidates" className={secondaryLink}>
              <Users className="size-4" aria-hidden />
              Банк кандидатов
            </Link>
            <Link to="/recruiter/needs/new" className={primaryLink}>
              <Plus className="size-4" aria-hidden />
              Новый поиск
            </Link>
          </>
        }
      />

      <QueryState
        query={dash}
        loading={
          <div className="grid gap-4 lg:grid-cols-2">
            {Array.from({ length: 2 }).map((_, i) => (
              <Skeleton key={i} className="h-64" />
            ))}
          </div>
        }
      >
        {(data) => (
          <>
            <p className="mb-5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-muted">
              <span className="font-semibold text-ink">Приглашения:</span>
              <Link to="/recruiter/invitations" className="font-semibold text-fsp-plum hover:underline">
                {inWork} ждут ответа
              </Link>
              ·
              <Link to="/recruiter/invitations?status=accepted" className="font-semibold text-fsp-plum hover:underline">
                {by.accepted ?? 0} {plural(by.accepted ?? 0, ['принял', 'приняли', 'приняли'])}
              </Link>
              {quota.data && (
                <>
                  · <span>можно отправить ещё {quota.data.left}</span>
                </>
              )}
            </p>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader
                  title="Активные поиски"
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
                            <span className="block font-semibold break-words">{n.title}</span>
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
                    title="Поисков пока нет"
                    action={
                      <Link to="/recruiter/needs/new" className={primaryLink}>
                        Начать поиск
                      </Link>
                    }
                  />
                )}
              </Card>

              <Card>
                <CardHeader
                  title={data.new_applications_count ? `Новые отклики · ${data.new_applications_count}` : 'Новые отклики'}
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
                            <span className="block font-medium break-words">{a.vacancy_title}</span>
                            <span className="block text-[13px] text-muted">{a.candidate_name ?? a.candidate_pseudonym}</span>
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
          </>
        )}
      </QueryState>
    </>
  )
}
