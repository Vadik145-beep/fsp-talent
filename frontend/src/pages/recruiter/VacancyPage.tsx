import { useState } from 'react'
import { useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { EyeOff, Inbox, Pencil, Upload } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate } from '@/shared/lib/format'
import { humanizeSkillCodes } from '@/shared/lib/skillText'
import { Badge, Button, Card, CardHeader, EmptyState, PageHeader, SalaryRange, Skeleton, SkeletonCard, useToast } from '@/shared/ui'
import { refreshRecruiter, rk, upsertInList, useSkills, type Application, type Vacancy } from './api'
import { VACANCY_STATUS, WORK_FORMAT_LABELS } from './labels'
import { ApplicationItem } from './components/ApplicationItem'
import { StackTags } from './components/CandidateBits'
import { QueryState } from './components/QueryState'
import { VacancyFormModal } from './components/VacancyFormModal'

/** Вакансия: условия, публикация и входящие отклики. */
export default function RecruiterVacancyPage() {
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editOpen, setEditOpen] = useState(false)
  const skills = useSkills()
  const vacancy = useQuery({ queryKey: rk.vacancy(id), queryFn: () => api.get<Vacancy>(`/vacancies/${id}`) })
  const apps = useQuery({
    queryKey: rk.vacancyApplications(id),
    queryFn: () => api.get<Application[]>(`/vacancies/${id}/applications`),
    enabled: vacancy.isSuccess,
  })
  const publish = useMutation({
    mutationFn: (action: 'publish' | 'unpublish') => api.post<Vacancy>(`/vacancies/${id}/${action}`),
    onSuccess: (v) => {
      toast({ tone: 'success', title: v.status === 'published' ? 'Вакансия опубликована' : 'Вакансия снята с публикации' })
      upsertInList(qc, rk.vacancies, v)
      qc.setQueryData(rk.vacancy(v.id), v)
      void refreshRecruiter(qc, rk.vacancies)
    },
    onError: (e) => toast({ tone: 'error', title: 'Не получилось', description: getErrorMessage(e) }),
  })

  if (vacancy.isPending) {
    return (
      <>
        <Skeleton className="mb-6 h-10 w-1/2" />
        <SkeletonCard />
      </>
    )
  }
  if (vacancy.isError) {
    return (
      <>
        <PageHeader title="Вакансия" back={{ to: '/recruiter/vacancies', label: 'Вакансии' }} />
        <QueryState query={vacancy}>{() => null}</QueryState>
      </>
    )
  }
  const v = vacancy.data
  const st = VACANCY_STATUS[v.status]
  return (
    <>
      <PageHeader
        title={v.title}
        back={{ to: '/recruiter/vacancies', label: 'Вакансии' }}
        meta={
          <>
            <Badge tone={st.tone}>{st.label}</Badge>
            <Badge tone="violet">{v.category_label}</Badge>
          </>
        }
        description={`Создана ${formatDate(v.created_at)}${v.published_at ? ` · опубликована ${formatDate(v.published_at)}` : ''}`}
        actions={
          <>
            <Button variant="secondary" onClick={() => setEditOpen(true)} leftIcon={<Pencil className="size-4" aria-hidden />}>
              Редактировать
            </Button>
            {v.status === 'published' ? (
              <Button variant="secondary" loading={publish.isPending} onClick={() => publish.mutate('unpublish')} leftIcon={<EyeOff className="size-4" aria-hidden />}>
                Снять с публикации
              </Button>
            ) : (
              <Button loading={publish.isPending} onClick={() => publish.mutate('publish')} leftIcon={<Upload className="size-4" aria-hidden />}>
                Опубликовать
              </Button>
            )}
          </>
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card className="self-start">
          <SalaryRange from={v.salary_from} to={v.salary_to} label="Зарплата" size="lg" />
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div>
              <dt className="text-xs text-muted">Формат</dt>
              <dd className="font-medium">{WORK_FORMAT_LABELS[v.work_format]}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Город</dt>
              <dd className="font-medium">{v.city ?? 'Не важно'}</dd>
            </div>
          </dl>
          {Boolean(v.skills_required?.length) && (
            <div className="mt-4">
              <p className="mb-1.5 text-xs text-muted">Обязательный стек</p>
              <StackTags stack={v.skills_required ?? []} />
            </div>
          )}
          {Boolean(v.skills_desired?.length) && (
            <div className="mt-3">
              <p className="mb-1.5 text-xs text-muted">Желательно</p>
              <StackTags stack={v.skills_desired ?? []} />
            </div>
          )}
          <p className="mt-4 text-sm whitespace-pre-line">{humanizeSkillCodes(v.description, skills.label)}</p>
          {v.team_description?.trim() && (
            <div className="mt-4">
              <p className="mb-1 text-xs text-muted">Чем занимается команда</p>
              <p className="text-sm whitespace-pre-line">{v.team_description}</p>
            </div>
          )}
        </Card>
        <section aria-label="Отклики">
          <CardHeader title={`Отклики · ${v.applications_count ?? 0}`} description="Кандидат откликнулся сам — его контакты открыты сразу." />
          <QueryState
            query={apps}
            isEmpty={(d) => d.length === 0}
            empty={
              <Card padding="none">
                <EmptyState
                  icon={<Inbox aria-hidden />}
                  title="Откликов пока нет"
                  description={v.status === 'published' ? 'Вакансия в ленте — отклики появятся здесь.' : 'Опубликуйте вакансию, чтобы соискатели её увидели.'}
                />
              </Card>
            }
          >
            {(data) => (
              <ul className="flex flex-col gap-3">
                {data.map((a) => (
                  <li key={a.id}>
                    <ApplicationItem app={a} />
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </section>
      </div>
      <VacancyFormModal open={editOpen} vacancy={v} onClose={() => setEditOpen(false)} />
    </>
  )
}
