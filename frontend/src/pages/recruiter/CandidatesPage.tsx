import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { Check, CircleCheck, SearchX, Send, ShieldCheck, SlidersHorizontal } from 'lucide-react'
import { api } from '@/shared/api'
import { GRADE_OPTIONS, INVITATION_STATUS_LABELS, SPECIALIZATION_OPTIONS, type InvitationStatus } from '@/shared/config/dictionaries'
import { cn } from '@/shared/lib/cn'
import { plural } from '@/shared/lib/format'
import { useMediaQuery } from '@/shared/lib/useMediaQuery'
import { Badge, Button, Card, EmptyState, FilterBar, PageHeader, Pagination, Pseudonym, Select, StatusPill, Tag } from '@/shared/ui'
import { pseudonymCodeOf, rk, useCategories, type Need, type S } from './api'
import { WORK_FORMAT_LABELS, yearsText } from './labels'
import { FspBadges, StackTags, ThetaInfo } from './components/CandidateBits'
import { InviteModal } from './components/InviteModal'
import { QueryState } from './components/QueryState'
import { SkillInput } from './components/SkillInput'

type BankCard = S['BankCandidateCard']

const PAGE_SIZE = 10
const MATCH_SORT = { value: 'match', label: 'По соответствию' }
const SORT_OPTIONS = [
  { value: 'theta', label: 'По результату теста' },
  { value: 'fsp', label: 'По достижениям ФСП' },
  { value: 'freshness', label: 'По свежести профиля' },
  { value: 'recent', label: 'Недавно прошли тест' },
]
const FILTER_KEYS = ['specialization', 'grade', 'category', 'skills', 'has_fsp']
/** В URL: `need=<id>` — выбранная потребность, `need=none` — без потребности. */
const NO_NEED = 'none'
/** Приглашение ещё в силе или принято — второе отправить нельзя (как в подборке). */
const BLOCKING: InvitationStatus[] = ['sent', 'viewed', 'accepted']
/** Причина «Тест сильнее, чем у N %…» дублирует строку результата теста на карточке. */
const THETA_REASON = /^Тест сильнее, чем у \d+ % специалистов(?:; сильные темы: (.+))?$/

/** Последняя активная потребность компании — выбор по умолчанию. */
function latestActive(needs: Need[]): Need | null {
  const active = needs.filter((n) => n.status === 'active')
  active.sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at) || b.id - a.id)
  return active[0] ?? null
}

function needLabel(n: Need): string {
  return `${n.title} · ${n.category_label}${n.status === 'active' ? '' : ' (закрыта)'}`
}

/** Причины без дубля результата теста: остаются только сильные темы. */
function bankReasons(reasons: string[]): string[] {
  return reasons.flatMap((r) => {
    const m = THETA_REASON.exec(r)
    if (!m) return [r]
    return m[1] ? [`Сильные темы теста: ${m[1]}`] : []
  })
}

/** Банк кандидатов: поиск по всей базе с фильтрами, сортировкой и страницами (фильтры — в URL). */
export default function RecruiterCandidatesPage() {
  const [sp, setSp] = useSearchParams()
  const categories = useCategories()
  const desktop = useMediaQuery('(min-width: 640px)')
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [inviteFor, setInviteFor] = useState<BankCard | null>(null)
  const needs = useQuery({ queryKey: rk.needs, queryFn: () => api.get<Need[]>('/matching/needs') })
  const needList = needs.data ?? []
  const needParam = sp.get('need')
  const need =
    needParam === NO_NEED ? null : needParam ? (needList.find((n) => String(n.id) === needParam) ?? null) : latestActive(needList)
  const sortParam = sp.get('sort')
  const sort = need ? sortParam || 'match' : sortParam && sortParam !== 'match' ? sortParam : 'theta'

  // Потребность по умолчанию — сразу в адрес вместе с её специализацией: в топе не будет людей
  // чужой специализации, а фильтр можно снять (потребность в адресе — повторно он не встанет).
  const defaultNeed = needParam ? null : need
  useEffect(() => {
    if (!defaultNeed) return
    setSp(
      (prev) => {
        const next = new URLSearchParams(prev)
        next.set('need', String(defaultNeed.id))
        if (!next.get('specialization') && !next.get('category')) next.set('specialization', defaultNeed.specialization)
        return next
      },
      { replace: true },
    )
  }, [defaultNeed, setSp])

  const params = {
    specialization: sp.get('specialization') || null,
    grade: sp.get('grade') || null,
    category: sp.get('category') || null,
    skills: sp.getAll('skills'),
    has_fsp: sp.get('has_fsp') === 'true' ? true : null,
    need_id: need?.id ?? null,
    sort,
    page: Number(sp.get('page')) || 1,
    page_size: PAGE_SIZE,
  }
  const activeCount =
    (params.specialization ? 1 : 0) + (params.grade ? 1 : 0) + (params.category ? 1 : 0) + params.skills.length + (params.has_fsp ? 1 : 0)

  const bank = useQuery({
    queryKey: rk.bank(params),
    queryFn: () => api.get<S['Page_BankCandidateCard_']>('/candidates', { query: params }),
    placeholderData: keepPreviousData,
    // выбор потребности по умолчанию зависит от списка потребностей — ждём его и подстановки в адрес
    enabled: !needs.isPending && !defaultNeed,
  })
  const needOptions = [{ value: NO_NEED, label: 'Без потребности' }, ...needList.map((n) => ({ value: String(n.id), label: needLabel(n) }))]

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

  /** Потребность — в приглашение, только если кандидат той же специализации (иначе чужая вилка и need_id). */
  const inviteNeed = (c: BankCard) =>
    need && c.specialization === need.specialization
      ? { id: need.id, title: need.title, salary_from: need.salary_from, salary_to: need.salary_to }
      : null

  const filters = (
    <FilterBar
      className={desktop ? undefined : 'mb-0 border-0 p-0'}
      activeCount={activeCount}
      onReset={() => update((p) => FILTER_KEYS.forEach((k) => p.delete(k)))}
      actions={
        <Select
          label="Сортировка"
          containerClassName="w-full sm:w-56"
          value={params.sort}
          options={need ? [MATCH_SORT, ...SORT_OPTIONS] : SORT_OPTIONS}
          onChange={(e) => update((p) => p.set('sort', e.target.value))}
        />
      }
    >
      <Select
        label="Под потребность"
        containerClassName="sm:w-[26rem]"
        value={need ? String(need.id) : NO_NEED}
        options={needOptions}
        disabled={needs.isPending}
        title={need ? needLabel(need) : 'Без потребности'}
        data-testid="bank-need"
        onChange={(e) =>
          update((p) => {
            const value = e.target.value
            p.set('need', value)
            // у новой потребности своя сортировка по умолчанию
            if (p.get('sort') === 'match' || value === NO_NEED) p.delete('sort')
            // специализация потребности — фильтром (его можно снять)
            const picked = needList.find((n) => String(n.id) === value)
            if (picked) {
              p.set('specialization', picked.specialization)
              p.delete('category')
            }
          })
        }
      />
      <Select
        label="Специализация"
        containerClassName="sm:w-44"
        placeholder="Все"
        options={SPECIALIZATION_OPTIONS}
        value={params.specialization ?? ''}
        onChange={(e) =>
          update((p) => {
            if (e.target.value) p.set('specialization', e.target.value)
            else p.delete('specialization')
            p.delete('category')
          })
        }
      />
      <Select
        label="Грейд"
        containerClassName="sm:w-36"
        placeholder="Все"
        options={GRADE_OPTIONS}
        value={params.grade ?? ''}
        onChange={(e) =>
          update((p) => {
            if (e.target.value) p.set('grade', e.target.value)
            else p.delete('grade')
            p.delete('category')
          })
        }
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
        <span className="hidden text-sm font-medium text-ink sm:block" aria-hidden>
          &nbsp;
        </span>
        <Tag onClick={() => setOne('has_fsp', params.has_fsp ? null : 'true')} selected={Boolean(params.has_fsp)} icon={<ShieldCheck aria-hidden />}>
          Есть достижения ФСП
        </Tag>
      </div>
    </FilterBar>
  )

  return (
    <>
      <PageHeader
        title="Банк кандидатов"
        description="Вся база в обезличенном виде. Категория присвоена по тесту, бейдж ФСП — подтверждённые достижения. Выберите потребность — кандидаты встанут по соответствию ей."
      />
      {desktop ? (
        filters
      ) : (
        <div className="mb-4 rounded-lg border border-line bg-surface">
          <button
            type="button"
            onClick={() => setFiltersOpen((v) => !v)}
            aria-expanded={filtersOpen}
            aria-controls="bank-filters"
            className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left text-sm font-semibold"
          >
            <span className="inline-flex shrink-0 items-center gap-2 whitespace-nowrap">
              <SlidersHorizontal className="size-4 text-fsp-plum" aria-hidden />
              Фильтры{activeCount > 0 ? ` · ${activeCount}` : ''}
            </span>
            <span className="min-w-0 truncate text-[13px] font-normal text-muted">{need ? need.title : 'Без потребности'}</span>
          </button>
          {filtersOpen && (
            <div id="bank-filters" className="border-t border-line p-3">
              {filters}
            </div>
          )}
        </div>
      )}

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
              {need && <> · соответствие потребности «{need.title}»</>}
            </p>
            <ul className={cn('grid grid-cols-1 gap-3 md:grid-cols-2', bank.isPlaceholderData && 'opacity-60')}>
              {d.items.map((c) => {
                const reasons = bankReasons(c.match_reasons ?? [])
                const status = (c.invitation_status ?? null) as InvitationStatus | null
                const blocked = Boolean(status && BLOCKING.includes(status))
                return (
                  <li key={c.id} className="min-w-0">
                    <Card className="flex h-full flex-col gap-3" padding="sm" data-testid="bank-card">
                      {/* с процентом соответствия — без переноса: псевдоним сжимается, процент справа */}
                      <div className={cn('flex items-start justify-between gap-2', c.match_score == null && 'flex-wrap')}>
                        <Link to={`/recruiter/candidates/${c.id}`} className="flex min-w-0 hover:opacity-80">
                          <Pseudonym
                            code={pseudonymCodeOf(c.pseudonym)}
                            subtitle={[c.category_label, c.city, c.experience_years != null ? yearsText(c.experience_years) : null].filter(Boolean).join(' · ')}
                          />
                        </Link>
                        {c.match_score != null ? (
                          <div className="shrink-0 text-right" data-testid="bank-match">
                            <div className="text-2xl leading-none font-bold text-fsp-plum tabular-nums">{Math.round(c.match_score * 100)}%</div>
                            <div className="mt-0.5 text-[11px] leading-tight font-medium text-muted">соответствие</div>
                          </div>
                        ) : (
                          <FspBadges candidate={c} compact />
                        )}
                      </div>
                      {(c.match_score != null || status) && (
                        <div className="flex flex-wrap items-center gap-1.5">
                          {c.match_score != null && <FspBadges candidate={c} compact />}
                          {status && <StatusPill status={status} />}
                        </div>
                      )}
                      <ThetaInfo theta={c.theta} />
                      {reasons.length > 0 && (
                        <ul className="flex flex-col gap-1.5" aria-label="Почему подходит" data-testid="bank-reasons">
                          {reasons.map((r) => (
                            <li key={r} className="flex gap-2 text-sm text-ink">
                              <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
                              <span>{r}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                      <StackTags stack={c.stack} highlight={need ? [...(need.skills_required ?? []), ...(need.skills_desired ?? []), ...params.skills] : params.skills} limit={7} />
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
                          {blocked && status ? (
                            <Button size="sm" variant="secondary" disabled leftIcon={<Check className="size-3.5" aria-hidden />}>
                              {status === 'accepted' ? 'Принял приглашение' : `Приглашён · ${INVITATION_STATUS_LABELS[status].toLowerCase()}`}
                            </Button>
                          ) : (
                            <Button size="sm" variant="secondary" onClick={() => setInviteFor(c)} leftIcon={<Send className="size-3.5" aria-hidden />}>
                              {status ? 'Пригласить снова' : 'Пригласить'}
                            </Button>
                          )}
                        </span>
                      </div>
                    </Card>
                  </li>
                )
              })}
            </ul>
            <Pagination
              className="mt-6"
              page={d.page}
              pageCount={Math.ceil(d.total / d.page_size)}
              onChange={(page) => {
                update((p) => p.set('page', String(page)), false)
                window.scrollTo({ top: 0, behavior: 'smooth' })
              }}
            />
          </>
        )}
      </QueryState>

      {inviteFor && (
        <InviteModal
          open
          onClose={() => setInviteFor(null)}
          candidate={inviteFor}
          need={inviteNeed(inviteFor)}
        />
      )}
    </>
  )
}
