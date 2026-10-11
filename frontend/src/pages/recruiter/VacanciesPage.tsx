import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Briefcase, Inbox, Pencil, Plus } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDate, formatSalaryRange } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, PageHeader, Table, Tabs, type TableColumn } from '@/shared/ui'
import { rk, type Application, type Vacancy } from './api'
import { VACANCY_STATUS } from './labels'
import { ApplicationItem } from './components/ApplicationItem'
import { QueryState } from './components/QueryState'
import { VacancyFormModal } from './components/VacancyFormModal'

/** Вакансии компании (CRUD) и все отклики. */
export default function RecruiterVacanciesPage() {
  const navigate = useNavigate()
  const [sp, setSp] = useSearchParams()
  const tab = sp.get('tab') === 'applications' ? 'applications' : 'vacancies'
  const [editing, setEditing] = useState<Vacancy | null | undefined>(undefined)
  const vacancies = useQuery({ queryKey: rk.vacancies, queryFn: () => api.get<Vacancy[]>('/vacancies') })
  const applications = useQuery({ queryKey: rk.applications, queryFn: () => api.get<Application[]>('/applications') })
  const newApps = applications.data?.filter((a) => a.status === 'new').length

  const columns: TableColumn<Vacancy>[] = [
    {
      key: 'title',
      header: 'Вакансия',
      sortable: true,
      render: (v) => (
        <span className="block min-w-0">
          <span className="block font-semibold">{v.title}</span>
          <span className="block text-[13px] text-muted">{v.category_label}</span>
        </span>
      ),
    },
    {
      key: 'salary',
      header: 'Зарплата',
      sortable: true,
      sortValue: (v) => v.salary_to,
      hideOnMobile: true,
      render: (v) => <span className="whitespace-nowrap tabular-nums">{formatSalaryRange(v.salary_from, v.salary_to)}</span>,
    },
    { key: 'status', header: 'Статус', sortable: true, render: (v) => <Badge tone={VACANCY_STATUS[v.status].tone}>{VACANCY_STATUS[v.status].label}</Badge> },
    { key: 'applications_count', header: 'Отклики', sortable: true, align: 'right', render: (v) => <b className="tabular-nums">{v.applications_count ?? 0}</b> },
    { key: 'created_at', header: 'Создана', sortable: true, hideOnMobile: true, render: (v) => formatDate(v.created_at) },
    {
      key: 'edit',
      header: '',
      align: 'right',
      render: (v) => (
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Редактировать «${v.title}»`}
          onClick={(e) => {
            e.stopPropagation()
            setEditing(v)
          }}
          leftIcon={<Pencil className="size-3.5" aria-hidden />}
        >
          Изменить
        </Button>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="Вакансии"
        description="Дополнительный канал: кандидаты откликаются сами, и их контакты открываются сразу."
        actions={
          <Button onClick={() => setEditing(null)} leftIcon={<Plus className="size-4" aria-hidden />}>
            Создать вакансию
          </Button>
        }
      />
      {/* подписи вкладок зависят от обоих списков — пока грузятся, держим место той же высоты, чтобы вкладки не прыгали */}
      {vacancies.isPending || applications.isPending ? (
        <div className="mb-4 h-[42px] shadow-[inset_0_-1px_0_var(--color-line)]" aria-hidden />
      ) : (
        <Tabs
          className="mb-4"
          value={tab}
          onChange={(v) => setSp(v === 'applications' ? { tab: 'applications' } : {}, { replace: true })}
          items={[
            { id: 'vacancies', label: 'Вакансии', count: vacancies.data?.length },
            {
              id: 'applications',
              // счётчик — все отклики; новые — отдельной подписью (было «4» при 13 в списке)
              label: newApps ? `Отклики · новых ${newApps} из ${applications.data?.length ?? 0}` : 'Отклики',
              count: newApps ? undefined : applications.data?.length,
            },
          ]}
        />
      )}
      {tab === 'vacancies' ? (
        <QueryState
          query={vacancies}
          isEmpty={(d) => d.length === 0}
          loading={<Table mobileCards caption="Вакансии" columns={columns} rows={[]} rowKey={(v) => v.id} loading />}
          empty={
            <Card padding="none">
              <EmptyState
                icon={<Briefcase aria-hidden />}
                title="Вакансий пока нет"
                description="Создайте вакансию — она появится в ленте соискателей после публикации."
                action={<Button onClick={() => setEditing(null)}>Создать вакансию</Button>}
              />
            </Card>
          }
        >
          {(data) => (
            <Table mobileCards caption="Вакансии" columns={columns} rows={data} rowKey={(v) => v.id} onRowClick={(v) => navigate(`/recruiter/vacancies/${v.id}`)} />
          )}
        </QueryState>
      ) : (
        <QueryState
          query={applications}
          isEmpty={(d) => d.length === 0}
          empty={
            <Card padding="none">
              <EmptyState icon={<Inbox aria-hidden />} title="Откликов пока нет" description="Опубликуйте вакансию — соискатели смогут откликнуться." />
            </Card>
          }
        >
          {(data) => (
            <ul className="flex flex-col gap-3">
              {data.map((a) => (
                <li key={a.id}>
                  <ApplicationItem app={a} showVacancy />
                </li>
              ))}
            </ul>
          )}
        </QueryState>
      )}
      <VacancyFormModal open={editing !== undefined} vacancy={editing} onClose={() => setEditing(undefined)} />
    </>
  )
}
