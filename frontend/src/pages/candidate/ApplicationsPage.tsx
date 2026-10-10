import { Link } from 'react-router'
import { Send } from 'lucide-react'
import { formatDate } from '@/shared/lib/format'
import { Badge, Card, EmptyState, PageHeader } from '@/shared/ui'
import { useApplications } from './api'
import { InviteContact } from './components/InviteContact'
import { QueryView } from './components/QueryView'
import { APPLICATION_STATUS } from './labels'

export default function ApplicationsPage() {
  const q = useApplications()
  return (
    <>
      <PageHeader title="Мои отклики" description="Вакансии, на которые вы откликнулись сами, и их статус." />
      <QueryView
        query={q}
        isEmpty={(list) => list.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<Send aria-hidden />}
              title="Откликов пока нет"
              description="Найдите вакансию по душе — или дождитесь приглашения от работодателя."
              action={
                <Link to="/candidate/vacancies" className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover">
                  Смотреть вакансии
                </Link>
              }
            />
          </Card>
        }
      >
        {(list) => (
          <ul className="grid gap-3">
            {list.map((a) => {
              const st = APPLICATION_STATUS[a.status]
              return (
                <li key={a.id}>
                  <Card>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <p className="text-lg font-semibold text-ink">{a.vacancy_title}</p>
                        <p className="text-sm text-muted">
                          {a.company_name} · отклик от {formatDate(a.created_at)}
                        </p>
                      </div>
                      <Badge tone={st.tone} className="self-start px-3 py-1 text-sm">
                        {st.label}
                      </Badge>
                    </div>
                    <p className="mt-2 text-sm text-muted">{st.hint}</p>
                    {a.status === 'invited' && <InviteContact contact={a.contact_method} message={a.invite_message} />}
                    {a.cover_letter && (
                      <p className="mt-3 line-clamp-2 rounded-md bg-surface-muted p-3 text-sm text-ink">«{a.cover_letter}»</p>
                    )}
                    {a.updated_at !== a.created_at && <p className="mt-2 text-[13px] text-subtle">Статус обновлён {formatDate(a.updated_at)}</p>}
                  </Card>
                </li>
              )
            })}
          </ul>
        )}
      </QueryView>
    </>
  )
}
