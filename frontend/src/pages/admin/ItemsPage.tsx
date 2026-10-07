import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Library, ShieldAlert } from 'lucide-react'
import { api } from '@/shared/api'
import {
  GRADE_LABELS,
  GRADE_OPTIONS,
  SPECIALIZATION_LABELS,
  SPECIALIZATION_OPTIONS,
  type Grade,
  type Specialization,
} from '@/shared/config/dictionaries'
import { Button, Card, EmptyState, ErrorState, FilterBar, PageHeader, Select, SkeletonText, Table, Tabs, Tag, type TableColumn } from '@/shared/ui'
import { fetchAllItems, type CoverageCell, type ItemSummary, type Topic } from './api'
import { CoverageHeatmap } from './components/CoverageHeatmap'
import { ItemStatusBadge, LeakBadge, StatTile } from './components/common'
import { RecalibrateButton } from './components/RecalibrateButton'
import { ITEM_FORMAT_LABELS, ITEM_STATUS_LABELS, num, pct } from './labels'

const STATUS_OPTIONS = Object.entries(ITEM_STATUS_LABELS).map(([value, label]) => ({ value, label }))
const FORMAT_OPTIONS = Object.entries(ITEM_FORMAT_LABELS).map(([value, label]) => ({ value, label }))

/** Доля верных: факт против ожидания модели (полоска + числа). */
function CorrectRate({ row }: { row: ItemSummary }) {
  if (row.correct_rate == null) return <span className="text-subtle">нет ответов</span>
  const exp = row.expected_correct_rate
  const high = exp != null && row.correct_rate - exp >= 0.1
  return (
    <div className="min-w-28" title={exp != null ? `Ожидается по модели: ${pct(exp)}` : undefined}>
      <div className="flex items-baseline justify-between gap-2 text-[13px] tabular-nums">
        <b className={high ? 'text-danger' : 'text-ink'}>{pct(row.correct_rate)}</b>
        {exp != null && <span className="text-muted">ожид. {pct(exp)}</span>}
      </div>
      <div className="relative mt-1 h-1.5 rounded-full bg-line">
        <div className={`h-full rounded-full ${high ? 'bg-danger' : 'bg-fsp-blue'}`} style={{ width: `${row.correct_rate * 100}%` }} />
        {exp != null && <span className="absolute -top-0.5 h-2.5 w-0.5 bg-ink" style={{ left: `${exp * 100}%` }} aria-hidden />}
      </div>
    </div>
  )
}

export default function AdminItemsPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'coverage' ? 'coverage' : 'bank'
  const spec = params.get('specialization') ?? ''
  const topic = params.get('topic') ?? ''
  const status = params.get('status') ?? ''
  const leak = params.get('leak') === 'true'
  const grade = params.get('grade') ?? ''
  const format = params.get('format') ?? ''
  const search = params.get('q') ?? ''

  const set = (patch: Record<string, string | null>) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const [k, v] of Object.entries(patch)) {
          if (v) next.set(k, v)
          else next.delete(k)
        }
        return next
      },
      { replace: true },
    )

  const items = useQuery({
    queryKey: ['admin', 'items', { spec, topic, status, leak }],
    queryFn: () => fetchAllItems({ specialization: spec, topic, status, leak_flag: leak ? true : undefined }),
  })
  const allItems = useQuery({ queryKey: ['admin', 'items', 'all'], queryFn: () => fetchAllItems() })
  const topics = useQuery({ queryKey: ['admin', 'topics'], queryFn: () => api.get<Topic[]>('/catalog/topics') })
  const coverage = useQuery({
    queryKey: ['admin', 'coverage'],
    queryFn: () => api.get<CoverageCell[]>('/admin/items/coverage'),
    enabled: view === 'coverage',
  })

  const rows = useMemo(() => {
    const s = search.trim().toLowerCase()
    return (items.data?.items ?? []).filter(
      (i) =>
        (!grade || i.target_grade === grade) &&
        (!format || i.format === format) &&
        (!s || i.title.toLowerCase().includes(s) || i.code.toLowerCase().includes(s)),
    )
  }, [items.data, grade, format, search])

  const stats = useMemo(() => {
    const list = allItems.data?.items ?? []
    const count = (st: string) => list.filter((i) => i.status === st).length
    return { total: list.length, active: count('active'), pilot: count('pilot'), draft: count('draft'), retired: count('retired'), leaks: list.filter((i) => i.leak_flag).length }
  }, [allItems.data])

  const topicOptions = (topics.data ?? [])
    .filter((t) => !spec || t.specialization === spec)
    .map((t) => ({ value: t.id, label: spec ? t.label : `${SPECIALIZATION_LABELS[t.specialization as Specialization]}: ${t.label}` }))
  const activeCount = view === 'coverage' ? (spec ? 1 : 0) : [spec, topic, status, leak ? '1' : '', grade, format, search].filter(Boolean).length

  const columns: TableColumn<ItemSummary>[] = [
    {
      key: 'title',
      header: 'Шаблон',
      sortable: true,
      render: (r) => (
        <div className="min-w-48">
          <p className="font-semibold text-ink">{r.title}</p>
          <p className="font-mono text-xs text-muted">
            {r.code} · {r.variants_count}+ вариантов{r.source === 'llm_vacancy' ? ' · из вакансии' : ''}
          </p>
        </div>
      ),
    },
    { key: 'specialization', header: 'Специализация', sortable: true, hideOnMobile: true, render: (r) => SPECIALIZATION_LABELS[r.specialization] },
    { key: 'topic_label', header: 'Тема', sortable: true, hideOnMobile: true },
    { key: 'format', header: 'Формат', hideOnMobile: true, render: (r) => ITEM_FORMAT_LABELS[r.format] },
    {
      key: 'target_grade',
      header: 'Грейд',
      sortable: true,
      sortValue: (r) => ['intern', 'junior', 'middle', 'senior'].indexOf(r.target_grade),
      render: (r) => GRADE_LABELS[r.target_grade as Grade],
    },
    { key: 'a', header: 'a', sortable: true, align: 'right', hideOnMobile: true, render: (r) => num(r.a) },
    { key: 'b', header: 'b', sortable: true, align: 'right', hideOnMobile: true, render: (r) => num(r.b) },
    { key: 'exposures', header: 'Показы', sortable: true, align: 'right', hideOnMobile: true },
    { key: 'correct_rate', header: 'Доля верных', sortable: true, hideOnMobile: true, render: (r) => <CorrectRate row={r} /> },
    {
      key: 'status',
      header: 'Статус',
      sortable: true,
      render: (r) => (
        <div className="flex flex-col items-start gap-1">
          <ItemStatusBadge status={r.status} />
          {r.leak_flag && <LeakBadge score={r.leak_score} />}
        </div>
      ),
    },
  ]

  return (
    <>
      <PageHeader
        title="Банк задач"
        description="Параметрические шаблоны: у каждого кандидата свой вариант. Сложность b и различающая сила a измеряются по ответам, детектор следит за утечками."
        actions={<RecalibrateButton />}
      />

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Всего шаблонов" value={stats.total} />
        <StatTile label="Активных" value={stats.active} tone="success" />
        <StatTile label="Пилот" value={stats.pilot} hint="не влияют на балл" />
        <StatTile label="Черновиков" value={stats.draft} tone={stats.draft ? 'warning' : 'default'} hint="ждут одобрения" />
        <StatTile label="Выведено" value={stats.retired} />
        <StatTile label="Флаги утечки" value={stats.leaks} tone={stats.leaks ? 'accent' : 'default'} />
      </div>

      <Tabs
        className="mb-4"
        ariaLabel="Вид"
        items={[
          { id: 'bank', label: 'Шаблоны' },
          { id: 'coverage', label: 'Покрытие тем × грейдов' },
        ]}
        value={view}
        onChange={(v) => set({ view: v === 'bank' ? null : v })}
      />

      <FilterBar
        search={view === 'bank' ? { value: search, onChange: (v) => set({ q: v }), placeholder: 'Название или код шаблона' } : undefined}
        activeCount={activeCount}
        onReset={() => setParams(view === 'coverage' ? { view } : {}, { replace: true })}
      >
        <Select
          aria-label="Специализация"
          containerClassName="sm:w-56"
          placeholder="Все специализации"
          options={SPECIALIZATION_OPTIONS}
          value={spec}
          onChange={(e) => set({ specialization: e.target.value, topic: null })}
        />
        {view === 'bank' && (
          <>
            <Select aria-label="Тема" containerClassName="sm:w-56" placeholder="Все темы" options={topicOptions} value={topic} onChange={(e) => set({ topic: e.target.value })} />
            <Select aria-label="Грейд" containerClassName="sm:w-36" placeholder="Все грейды" options={GRADE_OPTIONS} value={grade} onChange={(e) => set({ grade: e.target.value })} />
            <Select aria-label="Формат" containerClassName="sm:w-48" placeholder="Все форматы" options={FORMAT_OPTIONS} value={format} onChange={(e) => set({ format: e.target.value })} />
            <Select aria-label="Статус" containerClassName="sm:w-40" placeholder="Все статусы" options={STATUS_OPTIONS} value={status} onChange={(e) => set({ status: e.target.value })} />
            <Tag icon={<ShieldAlert aria-hidden />} selected={leak} onClick={() => set({ leak: leak ? null : 'true' })}>
              Только с флагом утечки
            </Tag>
          </>
        )}
      </FilterBar>

      {view === 'coverage' ? (
        coverage.isPending ? (
          <Card>
            <SkeletonText lines={8} />
          </Card>
        ) : coverage.isError ? (
          <Card padding="none">
            <ErrorState error={coverage.error} onRetry={() => coverage.refetch()} />
          </Card>
        ) : coverage.data.length === 0 ? (
          <Card padding="none">
            <EmptyState icon={<Library aria-hidden />} title="Банк пуст" description="Шаблоны загружаются сидом или создаются из вакансий." />
          </Card>
        ) : (
          <CoverageHeatmap cells={coverage.data} specialization={spec || undefined} />
        )
      ) : items.isError ? (
        <Card padding="none">
          <ErrorState error={items.error} onRetry={() => items.refetch()} />
        </Card>
      ) : (
        <>
          <Table
            caption="Шаблоны банка задач"
            columns={columns}
            rows={rows}
            rowKey={(r) => r.id}
            loading={items.isPending}
            onRowClick={(r) => navigate(`/admin/items/${r.id}`)}
            empty={
              <EmptyState
                icon={<Library aria-hidden />}
                title={activeCount ? 'Под фильтры ничего не подошло' : 'Шаблонов пока нет'}
                action={activeCount ? <Button variant="secondary" onClick={() => setParams({}, { replace: true })}>Сбросить фильтры</Button> : undefined}
              />
            }
          />
          {!items.isPending && rows.length > 0 && (
            <p className="mt-2 text-[13px] text-muted">
              Показано {rows.length}. a — различающая сила (чем больше, тем лучше задача отделяет сильных от слабых), b — сложность по шкале уровня
              (0 — средний кандидат). Чёрная риска на полоске — доля верных, которую ожидает модель.
            </p>
          )}
        </>
      )}
    </>
  )
}
