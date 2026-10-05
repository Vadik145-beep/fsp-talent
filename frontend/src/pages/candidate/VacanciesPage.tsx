import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Briefcase, Check, MapPin, SearchX } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { GRADE_OPTIONS, SPECIALIZATION_OPTIONS } from '@/shared/config/dictionaries'
import { formatDate, formatSalaryRange, plural } from '@/shared/lib/format'
import { Badge, Button, Card, Drawer, EmptyState, FilterBar, Input, Modal, PageHeader, Select, Tag, Textarea, useToast } from '@/shared/ui'
import { qk, useSkillLabel, type Application, type Vacancy } from './api'
import { QueryView } from './components/QueryView'
import { WORK_FORMAT_LABELS, WORK_FORMAT_OPTIONS } from './labels'

const FILTER_KEYS = ['q', 'specialization', 'grade', 'work_format', 'salary_min'] as const

export default function VacanciesPage() {
  const [params, setParams] = useSearchParams()
  const filters = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ''])) as Record<(typeof FILTER_KEYS)[number], string>
  const [search, setSearch] = useState(filters.q)
  const [opened, setOpened] = useState<Vacancy | null>(null)
  const [applyTo, setApplyTo] = useState<Vacancy | null>(null)
  const skillLabel = useSkillLabel()

  const q = useQuery({
    queryKey: qk.vacancies(filters),
    queryFn: () =>
      api.get<Vacancy[]>('/vacancies', {
        query: { ...filters, salary_min: filters.salary_min ? Number(filters.salary_min) : undefined },
      }),
  })

  function setFilter(key: (typeof FILTER_KEYS)[number], value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }

  const activeCount = FILTER_KEYS.filter((k) => filters[k]).length

  return (
    <>
      <PageHeader title="Вакансии" description="Опубликованные вакансии компаний. Отклик сразу открывает работодателю ваши контакты." />
      <FilterBar
        search={{
          value: search,
          onChange: (v) => {
            setSearch(v)
            setFilter('q', v.trim())
          },
          placeholder: 'Должность, компания, технология',
        }}
        activeCount={activeCount}
        onReset={() => {
          setSearch('')
          setParams(new URLSearchParams(), { replace: true })
        }}
      >
        <Select
          aria-label="Специализация"
          value={filters.specialization}
          onChange={(e) => setFilter('specialization', e.target.value)}
          options={SPECIALIZATION_OPTIONS}
          placeholder="Все специализации"
          containerClassName="sm:w-48"
        />
        <Select
          aria-label="Грейд"
          value={filters.grade}
          onChange={(e) => setFilter('grade', e.target.value)}
          options={GRADE_OPTIONS}
          placeholder="Любой грейд"
          containerClassName="sm:w-40"
        />
        <Select
          aria-label="Формат работы"
          value={filters.work_format}
          onChange={(e) => setFilter('work_format', e.target.value)}
          options={WORK_FORMAT_OPTIONS}
          placeholder="Любой формат"
          containerClassName="sm:w-40"
        />
        <Input
          aria-label="Зарплата от, ₽"
          placeholder="Зарплата от, ₽"
          inputMode="numeric"
          value={filters.salary_min}
          onChange={(e) => setFilter('salary_min', e.target.value.replace(/\D/g, ''))}
          containerClassName="sm:w-44"
        />
      </FilterBar>

      <QueryView
        query={q}
        isEmpty={(list) => list.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<SearchX aria-hidden />}
              title={activeCount ? 'Ничего не нашли' : 'Вакансий пока нет'}
              description={activeCount ? 'Попробуйте убрать часть фильтров.' : 'Компании ещё не опубликовали вакансии. Работодатели также могут пригласить вас сами.'}
              action={
                activeCount ? (
                  <Button
                    variant="secondary"
                    onClick={() => {
                      setSearch('')
                      setParams(new URLSearchParams(), { replace: true })
                    }}
                  >
                    Сбросить фильтры
                  </Button>
                ) : undefined
              }
            />
          </Card>
        }
      >
        {(list) => (
          <>
            <p className="mb-3 text-sm text-muted">
              {list.length} {plural(list.length, ['вакансия', 'вакансии', 'вакансий'])}
            </p>
            <ul className="grid gap-3">
              {list.map((v) => (
                <li key={v.id}>
                  <Card interactive onClick={() => setOpened(v)} className="sm:p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <h2 className="text-lg font-semibold text-ink">
                          <button type="button" className="text-left hover:text-fsp-plum focus-visible:outline-none focus-visible:underline" onClick={() => setOpened(v)}>
                            {v.title}
                          </button>
                        </h2>
                        <p className="text-sm text-muted">
                          {v.company_name} · {v.category_label}
                        </p>
                        <p className="mt-2 text-xl font-bold text-fsp-night tabular-nums">{formatSalaryRange(v.salary_from, v.salary_to)}</p>
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-muted">
                          <span className="inline-flex items-center gap-1">
                            <Briefcase className="size-3.5" aria-hidden /> {WORK_FORMAT_LABELS[v.work_format]}
                          </span>
                          {v.city && (
                            <span className="inline-flex items-center gap-1">
                              <MapPin className="size-3.5" aria-hidden /> {v.city}
                            </span>
                          )}
                          <span>{formatDate(v.published_at ?? v.created_at)}</span>
                        </div>
                        <div className="mt-3 flex flex-wrap gap-1.5">
                          {(v.skills_required ?? []).map((s) => (
                            <Tag key={s}>{skillLabel(s)}</Tag>
                          ))}
                          {(v.skills_desired ?? []).map((s) => (
                            <Tag key={s} tone="neutral">
                              {skillLabel(s)}
                            </Tag>
                          ))}
                        </div>
                      </div>
                      <div className="shrink-0" onClick={(e) => e.stopPropagation()}>
                        {v.my_application_id ? (
                          <Badge tone="success" icon={<Check />}>
                            Вы откликнулись
                          </Badge>
                        ) : (
                          <Button onClick={() => setApplyTo(v)}>Откликнуться</Button>
                        )}
                      </div>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
          </>
        )}
      </QueryView>

      <Drawer
        open={!!opened}
        onClose={() => setOpened(null)}
        title={opened?.title}
        widthClass="w-full max-w-lg"
        footer={
          opened &&
          (opened.my_application_id ? (
            <Link to="/candidate/applications" className="inline-flex h-10 items-center rounded-md px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft">
              Мои отклики
            </Link>
          ) : (
            <Button
              onClick={() => {
                setApplyTo(opened)
                setOpened(null)
              }}
            >
              Откликнуться
            </Button>
          ))
        }
      >
        {opened && (
          <div className="grid gap-4 p-5">
            <div>
              <p className="text-sm text-muted">{opened.company_name}</p>
              <p className="mt-1 text-2xl font-bold text-fsp-night tabular-nums">{formatSalaryRange(opened.salary_from, opened.salary_to)}</p>
              <p className="mt-1 text-sm text-muted">
                {opened.category_label} · {WORK_FORMAT_LABELS[opened.work_format]}
                {opened.city ? ` · ${opened.city}` : ''}
              </p>
            </div>
            <p className="text-[15px] leading-relaxed whitespace-pre-line text-ink">{opened.description}</p>
            {(opened.skills_required ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-ink">Обязательно</p>
                <div className="flex flex-wrap gap-1.5">
                  {(opened.skills_required ?? []).map((s) => (
                    <Tag key={s}>{skillLabel(s)}</Tag>
                  ))}
                </div>
              </div>
            )}
            {(opened.skills_desired ?? []).length > 0 && (
              <div>
                <p className="mb-1.5 text-sm font-medium text-ink">Желательно</p>
                <div className="flex flex-wrap gap-1.5">
                  {(opened.skills_desired ?? []).map((s) => (
                    <Tag key={s} tone="neutral">
                      {skillLabel(s)}
                    </Tag>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </Drawer>

      <ApplyModal vacancy={applyTo} onClose={() => setApplyTo(null)} />
    </>
  )
}

function ApplyModal({ vacancy, onClose }: { vacancy: Vacancy | null; onClose: () => void }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const [letter, setLetter] = useState('')
  const apply = useMutation({
    mutationFn: (v: Vacancy) => api.post<Application>(`/vacancies/${v.id}/applications`, { cover_letter: letter.trim() }),
    onSuccess: () => {
      setLetter('')
      onClose()
      void client.invalidateQueries({ queryKey: ['candidate', 'vacancies'] })
      void client.invalidateQueries({ queryKey: qk.applications })
      toast({ tone: 'success', title: 'Отклик отправлен', description: 'Статус — в разделе «Мои отклики».' })
    },
    onError: (err) => toast({ tone: 'error', title: 'Отклик не отправлен', description: getErrorMessage(err) }),
  })
  return (
    <Modal
      open={!!vacancy}
      onClose={onClose}
      title="Отклик на вакансию"
      description={vacancy ? `${vacancy.title} · ${vacancy.company_name}` : undefined}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={() => vacancy && apply.mutate(vacancy)} loading={apply.isPending}>
            Отправить отклик
          </Button>
        </>
      }
    >
      <div className="grid gap-3">
        <Textarea
          label="Сопроводительное письмо (необязательно)"
          rows={4}
          value={letter}
          onChange={(e) => setLetter(e.target.value)}
          placeholder="Пара предложений: почему вам интересна вакансия"
          maxLength={1000}
        />
        <p className="rounded-md bg-violet-soft px-3 py-2 text-[13px] text-fsp-plum">
          Работодатель увидит ваш профиль с ФИО и контактами — вы откликнулись сами. Категория и результаты теста тоже будут видны.
        </p>
      </div>
    </Modal>
  )
}
