import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/shared/api'
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
export type Company = S['Company']
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
