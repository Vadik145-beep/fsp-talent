import { useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Info, SearchX, ShieldCheck, Users, X } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { cn } from '@/shared/lib/cn'
import { formatPercent, formatSalaryRange, plural } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, FilterBar, PageHeader, Select, Skeleton, SkeletonCard, Tag } from '@/shared/ui'
import {
  rk,
  useSkills,
  type MatchList,
  type MatchedCandidate,
  type Need,
  type RecommendedCategory,
  type WorkFormat,
} from './api'
import { RELATION_LABELS, WORK_FORMAT_LABELS, WORK_FORMAT_OPTIONS } from './labels'
import { InviteModal } from './components/InviteModal'
import { MatchCard } from './components/MatchCard'
import { QueryState } from './components/QueryState'

const FILTER_KEYS = ['skills', 'has_fsp', 'work_format', 'city'] as const

/** Подборка по потребности: рекомендованные категории → ранжированные кандидаты с объяснением. */
export default function RecruiterNeedPage() {
  const needId = Number(useParams().id)
  const [sp, setSp] = useSearchParams()
  const skills = useSkills()
  const [inviteFor, setInviteFor] = useState<MatchedCandidate | null>(null)

  const need = useQuery({ queryKey: rk.need(needId), queryFn: () => api.get<Need>(`/matching/needs/${needId}`) })
  const cats = useQuery({
    queryKey: rk.needCategories(needId),
    queryFn: () => api.get<RecommendedCategory[]>(`/matching/needs/${needId}/categories`),
    enabled: need.isSuccess,
  })

  const category = sp.get('category') || need.data?.category || ''
  const filters = {
    skills: sp.getAll('skills'),
    has_fsp: sp.get('has_fsp') === 'true' ? true : null,
    work_format: (sp.get('work_format') || null) as WorkFormat | null,
    city: sp.get('city') || null,
  }
  const activeCount = filters.skills.length + (filters.has_fsp ? 1 : 0) + (filters.work_format ? 1 : 0) + (filters.city ? 1 : 0)

  // Исходная подборка категории (без уточнений) — кэшируется и не теряется при фильтрах.
  const base = useQuery({
    queryKey: rk.matches(needId, { category }),
    queryFn: () => api.get<MatchList>(`/matching/needs/${needId}/candidates`, { query: { category } }),
    enabled: Boolean(category),
  })
  const refined = useQuery({
    queryKey: rk.matches(needId, { category, ...filters }),
    queryFn: () =>
      api.get<MatchList>(`/matching/needs/${needId}/candidates`, {
        query: { category, skills: filters.skills, has_fsp: filters.has_fsp, work_format: filters.work_format, city: filters.city },
      }),
    enabled: Boolean(category) && activeCount > 0,
    placeholderData: keepPreviousData,
  })
  const list = activeCount > 0 ? refined : base

  function update(mut: (p: URLSearchParams) => void) {
    const next = new URLSearchParams(sp)
    mut(next)
    setSp(next, { replace: true })
  }
  const toggleSkill = (s: string) =>
    update((p) => {
      const cur = p.getAll('skills')
      p.delete('skills')
      for (const x of cur.includes(s) ? cur.filter((v) => v !== s) : [...cur, s]) p.append('skills', x)
    })
  const resetFilters = () => update((p) => FILTER_KEYS.forEach((k) => p.delete(k)))
  const selectCategory = (c: string) => {
    const next = new URLSearchParams(sp)
    next.set('category', c)
    setSp(next)
  }

  const highlight = [...(need.data?.skills_required ?? []), ...(need.data?.skills_desired ?? [])]

  // Варианты уточнений — из исходной подборки, чтобы не пропадали при сужении.
  const stackCounts = new Map<string, number>()
  for (const m of base.data?.items ?? []) for (const s of m.candidate.stack) stackCounts.set(s, (stackCounts.get(s) ?? 0) + 1)
  const popular = [...stackCounts.entries()].sort((a, b) => b[1] - a[1]).map(([s]) => s)
  const skillOptions = [...new Set([...highlight, ...popular, ...filters.skills])].slice(0, 10)
  const citySet = new Set<string>()
  for (const m of base.data?.items ?? []) if (m.candidate.city) citySet.add(m.candidate.city)
  if (filters.city) citySet.add(filters.city)
  const cityOptions = [...citySet].sort((a, b) => a.localeCompare(b, 'ru')).map((c) => ({ value: c, label: c }))

  if (need.isPending) {
    return (
      <>
        <Skeleton className="mb-6 h-10 w-2/3" />
        <SkeletonCard />
      </>
    )
  }
  if (need.isError) {
    return (
      <>
        <PageHeader title="Подборка" back={{ to: '/recruiter/needs', label: 'Потребности' }} />
        <QueryState query={need}>{() => null}</QueryState>
      </>
    )
  }
  const n = need.data
  const weights = base.data?.items[0]?.breakdown

  return (
    <>
      <PageHeader
        title={n.title}
        back={{ to: '/recruiter/needs', label: 'Потребности' }}
        meta={<Badge tone="violet">{n.category_label}</Badge>}
        description={[formatSalaryRange(n.salary_from, n.salary_to), WORK_FORMAT_LABELS[n.work_format], n.city]
          .filter(Boolean)
          .join(' · ')}
        actions={
          <Link to="/recruiter/candidates" className="text-sm font-semibold text-fsp-plum hover:underline">
            Искать во всём банке
          </Link>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="flex min-w-0 flex-col gap-4" aria-label="Рекомендованные категории">
          <Card padding="sm">
            <h2 className="mb-1 text-sm font-semibold">Рекомендованные категории</h2>
            <p className="mb-3 text-[13px] text-muted">Подборка строится по категориям из теста, а не по тексту резюме.</p>
            {cats.isPending ? (
              <div className="flex flex-col gap-2">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            ) : cats.isError ? (
              <div className="flex flex-col items-start gap-1 text-sm">
                <p className="text-danger">Не удалось загрузить категории: {getErrorMessage(cats.error)}</p>
                <Button variant="ghost" size="sm" onClick={() => void cats.refetch()} loading={cats.isFetching}>
                  Повторить
                </Button>
              </div>
            ) : (
              <ul className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 lg:flex-col lg:overflow-visible">
                {cats.data.map((c) => {
                  const active = c.category === category
                  return (
                    <li key={c.category} className="shrink-0">
                      <button
                        type="button"
                        onClick={() => selectCategory(c.category)}
                        aria-current={active ? 'true' : undefined}
                        className={cn(
                          'flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2 text-left transition-colors',
                          active
                            ? 'border-fsp-plum bg-fsp-plum text-white'
                            : 'border-line bg-surface hover:border-fsp-lavender hover:bg-violet-soft',
                        )}
                      >
                        <span className="min-w-0">
                          <span className="block text-sm font-semibold whitespace-nowrap">{c.label}</span>
                          <span className={cn('block text-xs', active ? 'text-on-nav-muted' : 'text-muted')}>
                            {RELATION_LABELS[c.relation]}
                          </span>
                        </span>
                        <span
                          className={cn(
                            'inline-flex min-w-7 justify-center rounded-full px-2 py-0.5 text-xs font-bold tabular-nums',
                            active ? 'bg-white/20 text-white' : c.candidates_count ? 'bg-violet-soft text-fsp-plum' : 'bg-neutral-soft text-subtle',
                          )}
                          aria-label={`${c.candidates_count} ${plural(c.candidates_count, ['кандидат', 'кандидата', 'кандидатов'])}`}
                        >
                          {c.candidates_count}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>

          <Card padding="sm" className="hidden lg:block">
            <h2 className="mb-2 text-sm font-semibold">Потребность</h2>
            <dl className="flex flex-col gap-2 text-sm">
              <div>
                <dt className="text-xs text-muted">Обязательный стек</dt>
                <dd>{n.skills_required?.length ? n.skills_required.map(skills.label).join(', ') : '—'}</dd>
              </div>
              {Boolean(n.skills_desired?.length) && (
                <div>
                  <dt className="text-xs text-muted">Желательно</dt>
                  <dd>{n.skills_desired!.map(skills.label).join(', ')}</dd>
                </div>
              )}
              {n.team_description && (
                <div>
                  <dt className="text-xs text-muted">Команда</dt>
                  <dd>{n.team_description}</dd>
                </div>
              )}
            </dl>
          </Card>
        </aside>

        <section aria-label="Кандидаты" className="min-w-0">
          <FilterBar activeCount={activeCount} onReset={resetFilters}>
            <div className="flex min-w-0 flex-col gap-1.5">
              <span className="text-sm font-medium text-ink">Уточнить по стеку</span>
              <div className="flex flex-wrap gap-1.5">
                {skillOptions.map((s) => (
                  <Tag key={s} onClick={() => toggleSkill(s)} selected={filters.skills.includes(s)}>
                    {skills.label(s)}
                  </Tag>
                ))}
                <Tag
                  onClick={() => update((p) => (filters.has_fsp ? p.delete('has_fsp') : p.set('has_fsp', 'true')))}
                  selected={Boolean(filters.has_fsp)}
                  icon={<ShieldCheck aria-hidden />}
                >
                  Есть ФСП
                </Tag>
              </div>
            </div>
            <Select
              label="Формат"
              containerClassName="sm:w-40"
              placeholder="Любой"
              value={filters.work_format ?? ''}
              options={WORK_FORMAT_OPTIONS}
              onChange={(e) => update((p) => (e.target.value ? p.set('work_format', e.target.value) : p.delete('work_format')))}
            />
            <Select
              label="Город"
              containerClassName="sm:w-44"
              placeholder="Любой"
              value={filters.city ?? ''}
              options={cityOptions}
              onChange={(e) => update((p) => (e.target.value ? p.set('city', e.target.value) : p.delete('city')))}
            />
          </FilterBar>

          {list.data && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-sm" aria-live="polite" data-testid="match-summary">
              {activeCount > 0 ? (
                <span>
                  <b>Показано {list.data.total} из {list.data.total_before_filters}</b>
                  <span className="text-muted"> · исходная подборка сохранена</span>
                </span>
              ) : (
                <span>
                  <b>
                    {list.data.total} {plural(list.data.total, ['кандидат', 'кандидата', 'кандидатов'])}
                  </b>
                  <span className="text-muted"> в категории {list.data.category_label}, по убыванию соответствия</span>
                </span>
              )}
              {activeCount > 0 && (
                <Button variant="ghost" size="sm" onClick={resetFilters} leftIcon={<X className="size-4" aria-hidden />}>
                  Вернуть исходную подборку
                </Button>
              )}
            </div>
          )}

          {weights && (
            <details className="mb-4 rounded-md border border-line bg-surface px-4 py-2.5 text-sm">
              <summary className="flex cursor-pointer items-center gap-2 font-semibold text-fsp-plum">
                <Info className="size-4" aria-hidden />
                Как считается соответствие
              </summary>
              <p className="mt-2 text-muted">
                Счёт от 0 до 100 = {weights.map((w) => `${w.label.toLowerCase()} ${formatPercent(w.weight)}`).join(' + ')}. У каждого
                фактора полоска показывает силу (0–1), число справа — вклад в итог. Ожидания кандидата по зарплате сравниваются с
                вилкой без раскрытия суммы.
              </p>
            </details>
          )}

          <QueryState
            query={list}
            errorTitle="Не удалось построить подборку"
            isEmpty={(d) => d.items.length === 0}
            empty={
              <Card padding="none">
                {activeCount > 0 ? (
                  <EmptyState
                    icon={<SearchX aria-hidden />}
                    title="Под уточнения никто не подошёл"
                    description={`Исходная подборка на месте: ${list.data?.total_before_filters ?? 0} ${plural(list.data?.total_before_filters ?? 0, ['кандидат', 'кандидата', 'кандидатов'])}.`}
                    action={
                      <Button variant="secondary" onClick={resetFilters}>
                        Сбросить уточнения
                      </Button>
                    }
                  />
                ) : (
                  <EmptyState
                    icon={<Users aria-hidden />}
                    title="В этой категории пока нет кандидатов"
                    description="Посмотрите соседние категории слева — там может быть подходящий грейд или смежная специализация."
                  />
                )}
              </Card>
            }
          >
            {(d) => (
              <ol className={cn('flex flex-col gap-4 transition-opacity', list.isPlaceholderData && 'opacity-60')}>
                {d.items.map((m, i) => (
                  <li key={m.candidate.id}>
                    <MatchCard
                      match={m}
                      rank={i + 1}
                      highlight={highlight}
                      profileHref={`/recruiter/candidates/${m.candidate.id}?need=${needId}`}
                      onInvite={() => setInviteFor(m)}
                    />
                  </li>
                ))}
              </ol>
            )}
          </QueryState>
        </section>
      </div>

      {inviteFor && (
        <InviteModal
          open
          onClose={() => setInviteFor(null)}
          candidate={inviteFor.candidate}
          need={{ id: n.id, title: n.title, salary_from: n.salary_from, salary_to: n.salary_to }}
        />
      )}
    </>
  )
}
