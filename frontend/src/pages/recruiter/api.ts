import { useEffect, useMemo, useState } from 'react'
import { useQuery, type QueryClient, type QueryKey } from '@tanstack/react-query'
import { api, isApiError } from '@/shared/api'
import type { components } from '@/shared/api/schema'

/** Типы контракта API (docs/api/openapi.json → schema.ts). */
export type S = components['schemas']
export type Need = S['Need']
export type NeedCreate = S['NeedCreate']
export type NeedParseResult = S['NeedParseResult']
export type MatchList = S['MatchList']
export type MatchedCandidate = S['MatchedCandidate']
export type RecommendedCategory = S['RecommendedCategory']
export type CandidateCard = S['CandidateCard']
export type AnonymousProfile = S['AnonymousCandidateProfile']
export type Invitation = S['Invitation']
export type InvitationDetail = S['InvitationDetail']
export type InvitationCreate = S['InvitationCreate']
export type InvitationQuota = S['InvitationQuota']
export type MarketHint = S['MarketHint']
export type Vacancy = S['Vacancy']
export type VacancyCreate = S['VacancyCreate']
export type Application = S['Application']
export type ApplicationStatus = S['ApplicationStatus']
export type RegularTask = S['RegularTask']
export type TaskSubmission = S['TaskSubmissionForRecruiter']
/** Компания; `invite_code` приходит только администратору компании (поле может отсутствовать). */
export type Company = S['Company'] & { invite_code?: string | null }
export type Recruiter = S['Recruiter']
export type RecruiterDashboard = S['RecruiterDashboard']
export type WorkFormat = S['WorkFormat']
export type ContactMethodType = S['ContactMethodType']

/** Ключи запросов кабинета рекрутера (все начинаются с 'recruiter'). */
export const rk = {
  all: ['recruiter'] as const,
  dashboard: ['recruiter', 'dashboard'] as const,
  company: ['recruiter', 'company'] as const,
  recruiters: ['recruiter', 'company', 'recruiters'] as const,
  needs: ['recruiter', 'needs'] as const,
  need: (id: number) => ['recruiter', 'needs', id] as const,
  needCategories: (id: number) => ['recruiter', 'needs', id, 'categories'] as const,
  matches: (id: number, params: Record<string, unknown>) => ['recruiter', 'needs', id, 'matches', params] as const,
  bank: (params: Record<string, unknown>) => ['recruiter', 'bank', params] as const,
  candidate: (id: number) => ['recruiter', 'candidate', id] as const,
  invitations: ['recruiter', 'invitations'] as const,
  invitation: (id: number) => ['recruiter', 'invitations', id] as const,
  quota: ['recruiter', 'quota'] as const,
  marketHint: (params: Record<string, unknown>) => ['recruiter', 'market-hint', params] as const,
  vacancies: ['recruiter', 'vacancies'] as const,
  vacancy: (id: number) => ['recruiter', 'vacancies', id] as const,
  vacancyApplications: (id: number) => ['recruiter', 'vacancies', id, 'applications'] as const,
  applications: ['recruiter', 'applications'] as const,
  tasks: ['recruiter', 'tasks'] as const,
  submissions: (taskId: number) => ['recruiter', 'tasks', taskId, 'submissions'] as const,
  skills: ['recruiter', 'catalog', 'skills'] as const,
  categories: ['recruiter', 'catalog', 'categories'] as const,
}

export function useQuota() {
  return useQuery({ queryKey: rk.quota, queryFn: () => api.get<InvitationQuota>('/invitations/quota') })
}

export function useCompany() {
  return useQuery({ queryKey: rk.company, queryFn: () => api.get<Company>('/companies/my') })
}

export function useCompanyRecruiters() {
  return useQuery({ queryKey: rk.recruiters, queryFn: () => api.get<Recruiter[]>('/companies/my/recruiters') })
}

export function useCategories() {
  return useQuery({
    queryKey: rk.categories,
    queryFn: () => api.get<S['Category'][]>('/catalog/categories'),
    staleTime: Infinity,
  })
}

/** Справочник стека: подписи по коду и список подписей для подсказок. */
export function useSkills() {
  const q = useQuery({
    queryKey: rk.skills,
    queryFn: () => api.get<S['Skill'][]>('/catalog/skills'),
    staleTime: Infinity,
  })
  return useMemo(() => {
    const list = q.data ?? []
    const byId = new Map(list.map((s) => [s.id, s.label]))
    const byLabel = new Map(list.map((s) => [s.label.toLowerCase(), s.id]))
    return {
      list,
      label: (id: string) => byId.get(id) ?? id,
      idOf: (label: string) => byLabel.get(label.toLowerCase()) ?? label.trim().toLowerCase(),
      isLoading: q.isPending,
    }
  }, [q.data, q.isPending])
}

/** Значение с задержкой — для подсказок при вводе (рыночная подсказка). */
export function useDebounced<T>(value: T, delay = 400): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setV(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])
  return v
}

/** «Кандидат #CFAD» → «CFAD». */
export function pseudonymCodeOf(pseudonym: string): string {
  return pseudonym.replace(/^Кандидат\s*#/i, '').trim()
}

// --- Обновление кэша после мутаций -------------------------------------------------------

/**
 * Положить запись из ответа мутации в кэш списка: заменить по id или добавить.
 * Ответ сервера — правда о записи, поэтому список не перезапрашиваем: так экран сразу
 * показывает изменение и не теряет его, даже если ручка пока не сохраняет (заглушка).
 */
export function upsertInList<T extends { id: number }>(qc: QueryClient, key: QueryKey, item: T, where: 'start' | 'end' = 'start') {
  qc.setQueryData<T[]>(key, (old) => {
    if (!old) return old
    const i = old.findIndex((x) => x.id === item.id)
    if (i >= 0) return old.map((x) => (x.id === item.id ? item : x))
    return where === 'start' ? [item, ...old] : [...old, item]
  })
}

const startsWith = (key: QueryKey, prefix: QueryKey) =>
  prefix.length <= key.length && prefix.every((v, i) => JSON.stringify(v) === JSON.stringify(key[i]))

/** Ключ запроса (вместе со всеми, что начинаются с него) или условие на ключ. */
export type KeyFilter = QueryKey | ((key: QueryKey) => boolean)

/** Запросы подборок по всем потребностям: ['recruiter', 'needs', id, 'matches', …]. */
export const isMatchesKey = (key: QueryKey) => key[0] === 'recruiter' && key[1] === 'needs' && key[3] === 'matches'

/**
 * Перезапросить данные кабинета рекрутера (счётчики, дашборд, квоту и т. п.), кроме запросов,
 * уже обновлённых из ответа мутации, и справочников.
 */
export function refreshRecruiter(qc: QueryClient, ...except: KeyFilter[]) {
  return qc.invalidateQueries({
    predicate: (q) => {
      const key = q.queryKey
      if (key[0] !== 'recruiter' || key[1] === 'catalog') return false
      return !except.some((f) => (typeof f === 'function' ? f(key) : startsWith(key, f)))
    },
  })
}

// --- Ошибки полей формы -----------------------------------------------------------------

interface PydanticError {
  type?: string
  loc?: Array<string | number>
  msg?: string
  ctx?: Record<string, unknown>
}

const SALARY_RANGE_TEXT = '«От» не может быть больше «до»'

function pydanticMessage(e: PydanticError): string {
  const ctx = e.ctx ?? {}
  switch (e.type) {
    case 'missing':
      return 'Обязательное поле'
    case 'string_too_short':
      return `Не короче ${String(ctx.min_length)} символов`
    case 'string_too_long':
      return `Не длиннее ${String(ctx.max_length)} символов`
    case 'too_short':
      return 'Заполните поле'
    case 'too_long':
      return 'Слишком много значений'
    case 'greater_than':
      return `Должно быть больше ${String(ctx.gt)}`
    case 'greater_than_equal':
      return `Не меньше ${String(ctx.ge)}`
    case 'less_than':
      return `Должно быть меньше ${String(ctx.lt)}`
    case 'less_than_equal':
      return `Не больше ${String(ctx.le)}`
    case 'int_parsing':
    case 'int_type':
    case 'int_from_float':
      return 'Нужно целое число'
    case 'enum':
    case 'literal_error':
      return 'Выберите значение из списка'
    case 'salary_range_invalid':
      return SALARY_RANGE_TEXT
  }
  const msg = (e.msg ?? '').replace(/^Value error,\s*/, '')
  return /[а-яё]/i.test(msg) ? msg : 'Проверьте значение'
}

/**
 * Ошибки полей из ответа API: `details.fields` ({поле: текст}) или `details.errors`
 * (список ошибок валидации FastAPI: loc = ["body", "поле", ...]). Ошибка вилки целиком
 * (`salary_range_invalid`) — на поле «от».
 */
export function apiFieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) return {}
  const result: Record<string, string> = {}
  const fields = error.details?.fields
  if (fields && typeof fields === 'object') {
    for (const [k, v] of Object.entries(fields as Record<string, unknown>)) result[k] = String(v)
  }
  const errors = error.details?.errors
  if (Array.isArray(errors)) {
    for (const e of errors as PydanticError[]) {
      const loc = (e.loc ?? []).filter((x) => x !== 'body')
      const field = e.type === 'salary_range_invalid' ? 'salary_from' : typeof loc[0] === 'string' ? loc[0] : null
      if (field && !result[field]) result[field] = pydanticMessage(e)
    }
  }
  if (error.code === 'salary_range_invalid' && !result.salary_from) result.salary_from = SALARY_RANGE_TEXT
  return result
}
