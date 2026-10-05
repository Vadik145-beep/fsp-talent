import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { SearchX, Send, ShieldCheck } from 'lucide-react'
import { api } from '@/shared/api'
import { GRADE_OPTIONS, SPECIALIZATION_OPTIONS } from '@/shared/config/dictionaries'
import { cn } from '@/shared/lib/cn'
import { plural } from '@/shared/lib/format'
import { Badge, Button, Card, EmptyState, FilterBar, PageHeader, Pagination, Pseudonym, Select, Tag } from '@/shared/ui'
import { pseudonymCodeOf, rk, useCategories, type CandidateCard, type S } from './api'
import { WORK_FORMAT_LABELS, yearsText } from './labels'
import { FspBadges, StackTags, ThetaInfo } from './components/CandidateBits'
import { InviteModal } from './components/InviteModal'
import { QueryState } from './components/QueryState'
import { SkillInput } from './components/SkillInput'

const PAGE_SIZE = 10
const SORT_OPTIONS = [
  { value: 'theta', label: 'По результату теста' },
  { value: 'fsp', label: 'По достижениям ФСП' },
  { value: 'freshness', label: 'По свежести профиля' },
  { value: 'recent', label: 'Недавно прошли тест' },
]
const FILTER_KEYS = ['specialization', 'grade', 'category', 'skills', 'has_fsp']

/** Банк кандидатов: поиск по всей базе с фильтрами, сортировкой и страницами (фильтры — в URL). */
export default function RecruiterCandidatesPage() {
  const [sp, setSp] = useSearchParams()
  const categories = useCategories()
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null)

  const params = {
    specialization: sp.get('specialization') || null,
    grade: sp.get('grade') || null,
    category: sp.get('category') || null,
    skills: sp.getAll('skills'),
    has_fsp: sp.get('has_fsp') === 'true' ? true : null,
    sort: sp.get('sort') || 'theta',
    page: Number(sp.get('page')) || 1,
    page_size: PAGE_SIZE,
  }
  const activeCount =
    (params.specialization ? 1 : 0) + (params.grade ? 1 : 0) + (params.category ? 1 : 0) + params.skills.length + (params.has_fsp ? 1 : 0)

  const bank = useQuery({
    queryKey: rk.bank(params),
    queryFn: () => api.get<S['Page_CandidateCard_']>('/candidates', { query: params }),
    placeholderData: keepPreviousData,
  })

  function update(mut: (p: URLSearchParams) => void, resetPage = true) {
    const next = new URLSearchParams(sp)
    mut(next)
    if (resetPage) next.delete('page')
    setSp(next, { replace: true })
  }
  const setOne = (key: string, value: string | null) => update((p) => (value ? p.set(key, value) : p.delete(key)))

  const categoryOptions = (categories.data ?? [])
    .filter((c) => !params.specialization || c.specialization === params.specialization)
    .filter((c) => !params.grade || c.grade === params.grade)
    .map((c) => ({ value: c.id, label: c.label }))

  return (
    <>
      <PageHeader
        title="Банк кандидатов"
        description="Вся база в обезличенном виде. Категория присвоена по тесту, бейдж ФСП — подтверждённые достижения."
      />
      <FilterBar
        activeCount={activeCount}
        onReset={() => update((p) => FILTER_KEYS.forEach((k) => p.delete(k)))}
        actions={
          <Select
            label="Сортировка"
            containerClassName="sm:w-56"
            value={params.sort}
            options={SORT_OPTIONS}
            onChange={(e) => update((p) => p.set('sort', e.target.value))}
          />
        }
      >
        <Select
          label="Специализация"
          containerClassName="sm:w-44"
          placeholder="Все"
          options={SPECIALIZATION_OPTIONS}
          value={params.specialization ?? ''}
          onChange={(e) => update((p) => {
            if (e.target.value) p.set('specialization', e.target.value)
            else p.delete('specialization')
            p.delete('category')
          })}
        />
        <Select
          label="Грейд"
          containerClassName="sm:w-36"
          placeholder="Все"
          options={GRADE_OPTIONS}
          value={params.grade ?? ''}
          onChange={(e) => update((p) => {
            if (e.target.value) p.set('grade', e.target.value)
            else p.delete('grade')
            p.delete('category')
          })}
        />
        <Select
          label="Категория"
          containerClassName="sm:w-52"
          placeholder="Все"
          options={categoryOptions}
          value={params.category ?? ''}
          onChange={(e) => setOne('category', e.target.value || null)}
        />
        <SkillInput
          label="Стек (все из списка)"
          className="sm:w-64"
          value={params.skills}
          onChange={(v) =>
            update((p) => {
              p.delete('skills')
              v.forEach((s) => p.append('skills', s))
            })
          }
        />
        <div className="flex flex-col gap-1.5">
          <span className="text-sm font-medium text-ink" aria-hidden>
            &nbsp;
          </span>
          <Tag onClick={() => setOne('has_fsp', params.has_fsp ? null : 'true')} selected={Boolean(params.has_fsp)} icon={<ShieldCheck aria-hidden />}>
            Есть достижения ФСП
          </Tag>
        </div>
      </FilterBar>

      <QueryState
        query={bank}
        isEmpty={(d) => d.items.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<SearchX aria-hidden />}
              title="Никого не нашли"
              description="Ослабьте фильтры: уберите часть стека или выберите соседний грейд."
              action={
                activeCount > 0 ? (
                  <Button variant="secondary" onClick={() => update((p) => FILTER_KEYS.forEach((k) => p.delete(k)))}>
                    Сбросить фильтры
                  </Button>
                ) : undefined
              }
            />
          </Card>
        }
      >
        {(d) => (
          <>
            <p className="mb-3 text-sm" aria-live="polite" data-testid="bank-total">
              Найдено <b>{d.total}</b> {plural(d.total, ['кандидат', 'кандидата', 'кандидатов'])}
            </p>
            <ul className={cn('grid grid-cols-1 gap-3 md:grid-cols-2', bank.isPlaceholderData && 'opacity-60')}>
              {d.items.map((c) => (
                <li key={c.id} className="min-w-0">
                  <Card className="flex h-full flex-col gap-3" padding="sm" data-testid="bank-card">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <Link to={`/recruiter/candidates/${c.id}`} className="min-w-0 hover:opacity-80">
                        <Pseudonym
                          code={pseudonymCodeOf(c.pseudonym)}
                          subtitle={[c.category_label, c.city, c.experience_years != null ? yearsText(c.experience_years) : null].filter(Boolean).join(' · ')}
                        />
                      </Link>
                      <FspBadges candidate={c} compact />
                    </div>
                    <ThetaInfo theta={c.theta} />
                    <StackTags stack={c.stack} highlight={params.skills} limit={7} />
                    <div className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
                      <span className="flex flex-wrap gap-1">
                        {c.work_formats.map((f) => (
                          <Badge key={f} tone="neutral">
                            {WORK_FORMAT_LABELS[f]}
                          </Badge>
                        ))}
                      </span>
                      <span className="flex gap-1.5">
                        <Link
                          to={`/recruiter/candidates/${c.id}`}
                          className="inline-flex h-8 items-center rounded-sm px-3 text-[13px] font-semibold text-fsp-plum hover:bg-violet-soft"
                        >
                          Профиль
                        </Link>
                        <Button size="sm" variant="secondary" onClick={() => setInviteFor(c)} leftIcon={<Send className="size-3.5" aria-hidden />}>
                          Пригласить
                        </Button>
                      </span>
                    </div>
                  </Card>
                </li>
              ))}
            </ul>
            <Pagination
              className="mt-6"
              page={d.page}
              pageCount={Math.ceil(d.total / d.page_size)}
              onChange={(page) => update((p) => p.set('page', String(page)), false)}
            />
          </>
        )}
      </QueryState>

      {inviteFor && <InviteModal open onClose={() => setInviteFor(null)} candidate={inviteFor} />}
    </>
  )
}
