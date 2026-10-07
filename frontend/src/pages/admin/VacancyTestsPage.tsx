import { useState, type ReactNode } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, FileText, Lightbulb, ListChecks, Sparkles, Tags, Wand2 } from 'lucide-react'
import { api } from '@/shared/api'
import { GRADE_LABELS, SPECIALIZATION_LABELS, SPECIALIZATION_OPTIONS } from '@/shared/config/dictionaries'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, ProgressBar, Select, SkeletonText, Tag, Textarea } from '@/shared/ui'
import { fetchAllItems, useAdminMutation, type ItemDetail, type ItemDraft, type ItemSummary, type SpecCode, type VacancyTestResult } from './api'
import { ItemStatusBadge } from './components/common'
import { ITEM_FORMAT_LABELS } from './labels'

/** Примеры (по мотивам data/samples/vacancies). В Middle React есть тема без шаблонов в банке — получится черновик. */
const BUILTIN_SAMPLES = [
  {
    id: 'python',
    label: 'Middle Python',
    text:
      'Middle Python-разработчик (платежи)\n' +
      'Ищем Middle Python-разработчика в команду платежей. FastAPI, PostgreSQL, Redis, Kafka. Нужно понимать транзакции, ' +
      'конкурентный доступ и уметь проектировать REST API. Плюсом будет опыт с OAuth 2.0.',
  },
  {
    id: 'react',
    label: 'Middle React',
    text:
      'Frontend-разработчик (React), Middle. Маркетплейс, Москва, гибрид, 200–260 тыс.\n' +
      'Стек: React, TypeScript, Redux Toolkit, Next.js. Вёрстка по макетам, CSS-модули, адаптивность. ' +
      'Следим за производительностью в браузере (Web Vitals). Код покрываем тестами: Jest и Testing Library.',
  },
  {
    id: 'android',
    label: 'Junior Android',
    text:
      'Junior Android-разработчик (Kotlin), Казань, офис, 110–150 тыс.\n' +
      'Kotlin, корутины, Jetpack Compose, Retrofit, Room. Понимание жизненного цикла Activity и Fragment. ' +
      'Опыт публикации в Google Play будет плюсом.',
  },
  {
    id: 'qa',
    label: 'Middle QA',
    text:
      'QA-инженер, Middle. Тест-дизайн: граничные значения, классы эквивалентности. Тестирование API в Postman, ' +
      'автотесты на pytest, баг-репорты в Jira, регресс перед релизом. Плюсом — нагрузочное тестирование на k6.',
  },
]

export default function AdminVacancyTestsPage() {
  const [text, setText] = useState('')
  const [spec, setSpec] = useState('')
  // Что открыто: собранный сейчас тест или запись истории (у заглушки бэкенда id результата совпадает с примером).
  const [shown, setShown] = useState<{ result: VacancyTestResult; fromHistory: boolean } | null>(null)

  const history = useQuery({ queryKey: ['admin', 'vacancy-tests'], queryFn: () => api.get<VacancyTestResult[]>('/admin/vacancy-tests') })
  const build = useAdminMutation(
    (vars: { text: string; specialization: SpecCode | null }) => api.post<VacancyTestResult>('/admin/vacancy-tests', vars),
    { success: (r) => `Тест собран: ${r.items.length} шаблонов, черновиков ${r.drafts.length}`, onSuccess: (r) => setShown({ result: r, fromHistory: false }) },
  )

  const shownResult = shown?.fromHistory ? (history.data?.find((r) => r.id === shown.result.id) ?? shown.result) : shown?.result
  const tooShort = text.trim().length < 20

  return (
    <>
      <PageHeader
        title="Задания из вакансий"
        description="Вставьте текст вакансии — система найдёт темы, подберёт шаблоны из банка и объяснит выбор. Для тем без шаблонов создаст черновики, их нужно одобрить."
      />

      <Card className="mb-6">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium text-muted">Пример:</span>
          {BUILTIN_SAMPLES.map((s) => (
            <Tag key={s.id} icon={<FileText aria-hidden />} onClick={() => setText(s.text)}>
              {s.label}
            </Tag>
          ))}
        </div>
        <Textarea
          label="Текст вакансии"
          rows={7}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Например: «Ищем Middle Python-разработчика: FastAPI, PostgreSQL, Kafka…»"
          hint={`${text.trim().length} символов, нужно не меньше 20`}
        />
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <Select
            label="Специализация"
            containerClassName="sm:w-64"
            placeholder="Определить по тексту"
            options={SPECIALIZATION_OPTIONS}
            value={spec}
            onChange={(e) => setSpec(e.target.value)}
          />
          <Button
            leftIcon={<Wand2 className="size-4" aria-hidden />}
            disabled={tooShort}
            loading={build.isPending}
            onClick={() => build.mutate({ text, specialization: (spec || null) as SpecCode | null })}
          >
            Сформировать тест
          </Button>
        </div>
      </Card>

      {shownResult ? <VacancyTestView result={shownResult} /> : null}

      <Card padding="none" className="mt-6">
        <div className="p-5 pb-2">
          <CardHeader className="mb-0" title="Собранные тесты" description="История: нажмите, чтобы открыть разбор." />
        </div>
        {history.isPending ? (
          <div className="p-5">
            <SkeletonText lines={3} />
          </div>
        ) : history.isError ? (
          <ErrorState error={history.error} onRetry={() => history.refetch()} />
        ) : history.data.length === 0 ? (
          <EmptyState compact icon={<Sparkles aria-hidden />} title="Пока ничего не собирали" description="Вставьте текст вакансии или возьмите пример." />
        ) : (
          <ul className="divide-y divide-line">
            {history.data.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setShown({ result: r, fromHistory: true })}
                  aria-current={(shown?.fromHistory && shown.result.id === r.id) || undefined}
                  className="flex w-full flex-wrap items-center gap-3 px-5 py-3 text-left transition-colors hover:bg-violet-soft/60 aria-[current]:bg-violet-soft"
                >
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-semibold text-ink">{r.vacancy_title}</span>
                    <span className="block text-[13px] text-muted">
                      {r.created_at ? `${formatDateTime(r.created_at)} · ` : ''}
                      {SPECIALIZATION_LABELS[r.specialization]} · {GRADE_LABELS[r.grade]} · тем {r.topics.length}, шаблонов {r.items.length}, черновиков {r.drafts.length}
                    </span>
                  </span>
                  <ArrowRight className="size-4 text-subtle" aria-hidden />
                </button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  )
}

function Step({ n, icon, title, children }: { n: number; icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="relative pl-12">
      <span className="absolute top-0 left-0 flex size-9 items-center justify-center rounded-full bg-fsp-plum text-white [&>svg]:size-[18px]" aria-hidden>
        {icon}
      </span>
      <h3 className="mb-3 text-base font-semibold">
        <span className="text-muted">Шаг {n}.</span> {title}
      </h3>
      {children}
    </section>
  )
}

function VacancyTestView({ result }: { result: VacancyTestResult }) {
  return (
    <Card>
      <CardHeader
        title={result.vacancy_title}
        description={`${SPECIALIZATION_LABELS[result.specialization]} · ${GRADE_LABELS[result.grade]} · разбор ${result.parser === 'llm' ? 'через LLM' : 'по словарю тем (без LLM)'}`}
      />
      <div className="flex flex-col gap-7">
        <Step n={1} icon={<Tags />} title="Темы, найденные в тексте">
          {result.topics.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {result.topics.map((t) => (
                <div key={t.topic} className="rounded-md border border-line p-3">
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <b className="text-ink">{t.label}</b>
                    {t.covered ? <Badge tone="success">есть в банке</Badge> : <Badge tone="warning">нет шаблонов</Badge>}
                  </div>
                  <p className="mb-2 text-[13px] text-muted">
                    По словам:{' '}
                    {t.matched_by.map((w) => (
                      <mark key={w} className="mr-1 rounded-xs bg-fsp-blush px-1 text-ink">
                        {w}
                      </mark>
                    ))}
                  </p>
                  <ProgressBar value={Math.round(t.confidence * 100)} label="Уверенность" size="sm" tone="violet" />
                </div>
              ))}
            </div>
          ) : (
            <EmptyState compact title="Темы не найдены" description="В тексте нет слов из словаря тем. Добавьте стек и задачи." />
          )}
        </Step>

        <Step n={2} icon={<ListChecks />} title="Шаблоны в тесте и почему они выбраны">
          {result.items.length ? (
            <ol className="flex flex-col gap-2">
              {result.items.map((i, idx) => (
                <li key={i.item_id} className="flex gap-3 rounded-md border border-line p-3">
                  <span className="font-semibold text-muted">{idx + 1}.</span>
                  <div className="min-w-0 flex-1">
                    <Link to={`/admin/items/${i.item_id}`} className="font-semibold text-fsp-plum hover:underline">
                      {i.title}
                    </Link>{' '}
                    <span className="font-mono text-xs text-muted">{i.code}</span>
                    {i.target_grade && <Badge tone="neutral" className="ml-2">{GRADE_LABELS[i.target_grade]}</Badge>}
                    <p className="mt-0.5 text-sm text-ink">{i.reason}</p>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-muted">Подходящих активных шаблонов нет — тест соберётся из черновиков после одобрения.</p>
          )}
        </Step>

        {result.drafts.length > 0 && (
          <Step n={3} icon={<Sparkles />} title="Черновики для тем без шаблонов">
            <p className="mb-3 text-sm text-muted">
              Черновик не влияет на оценки. После одобрения он становится пилотом: кандидаты решают его как непроверочную задачу, набирается статистика, затем
              калибровка.
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              {result.drafts.map((d) => (
                <DraftCard key={`${d.item_id ?? ''}-${d.topic}-${d.title}`} draft={d} />
              ))}
            </div>
          </Step>
        )}

        <div className="rounded-lg bg-violet-soft p-4">
          <p className="mb-2 flex items-center gap-2 font-semibold text-fsp-plum">
            <Lightbulb className="size-5" aria-hidden /> Как система рассуждала
          </p>
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink">
            {result.explanation.map((e) => (
              <li key={e}>{e}</li>
            ))}
          </ul>
        </div>
      </div>
    </Card>
  )
}

/**
 * Черновик шаблона. Если бэкенд прислал item_id (трек 3c) — берём шаблон по id;
 * иначе ищем его в банке по теме и названию.
 */
function DraftCard({ draft }: { draft: ItemDraft }) {
  const byId = useQuery({
    queryKey: ['admin', 'item', String(draft.item_id)],
    queryFn: () => api.get<ItemDetail>(`/admin/items/${draft.item_id}`),
    enabled: draft.item_id != null,
  })
  const byTopic = useQuery({
    queryKey: ['admin', 'items', 'by-topic', draft.topic],
    queryFn: () => fetchAllItems({ topic: draft.topic }),
    enabled: draft.item_id == null,
  })
  const item: ItemSummary | undefined = draft.item_id != null ? byId.data : byTopic.data?.items.find((i) => i.title === draft.title)
  const approve = useAdminMutation((id: number) => api.post<ItemDetail>(`/admin/items/${id}/approve`), {
    success: `Черновик «${draft.title}» одобрен — теперь это пилот`,
  })
  // Ответ на одобрение важнее списка: на заглушке бэкенда статус в банке пока не сохраняется.
  const status = approve.data?.status ?? item?.status ?? draft.status ?? 'draft'
  const itemId = item?.id ?? draft.item_id ?? null

  return (
    <div className="flex flex-col rounded-md border border-line p-3">
      <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
        <span className="text-[13px] font-medium text-muted">{draft.label}</span>
        <ItemStatusBadge status={status} />
      </div>
      <p className="font-semibold text-ink">{draft.title}</p>
      <p className="mt-1 text-sm text-ink">{draft.prompt}</p>
      <p className="mt-1 text-[13px] text-muted">
        Формат: {ITEM_FORMAT_LABELS[draft.format]}
        {draft.origin ? ` · ${draft.origin === 'llm' ? 'составлен LLM' : 'заготовка словаря тем'}` : ''}
        {draft.reused ? ' · черновик по этой теме и грейду уже был — новый не создавали' : ''}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        {status === 'draft' && itemId != null && (
          <Button size="sm" leftIcon={<CheckCircle2 className="size-4" aria-hidden />} loading={approve.isPending} onClick={() => approve.mutate(itemId)}>
            Одобрить
          </Button>
        )}
        {itemId != null && (
          <Link to={`/admin/items/${itemId}`} className="text-sm font-semibold text-fsp-plum hover:underline">
            Открыть шаблон и варианты
          </Link>
        )}
        {itemId == null && !byTopic.isPending && <span className="text-[13px] text-muted">Шаблон в банке ещё не создан</span>}
        {status === 'pilot' && <span className="text-[13px] text-info">Идёт в тесты как непроверочный</span>}
      </div>
    </div>
  )
}
