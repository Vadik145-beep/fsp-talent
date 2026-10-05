import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/shared/api'
import type { components } from '@/shared/api/schema'

/** Типы и запросы кабинета соискателя. Типы — из OpenAPI (src/shared/api/schema.ts). */
export type S = components['schemas']
export type CandidateProfile = S['CandidateProfile']
export type CandidateProfileUpdate = S['CandidateProfileUpdate']
export type CandidateDashboard = S['CandidateDashboard']
export type CandidateSettings = S['CandidateSettings']
export type PrivacySettings = S['PrivacySettings']
export type Invitation = S['Invitation']
export type InvitationDetail = S['InvitationDetail']
export type Vacancy = S['Vacancy']
export type Application = S['Application']
export type TaskInbox = S['TaskInbox']
export type TaskSubmission = S['TaskSubmission']
export type GradeStatus = S['GradeStatus']
export type TestSession = S['TestSession']
export type TestSessionState = S['TestSessionState']
export type TestResult = S['TestResult']
export type ItemView = S['ItemView']
export type AnswerPayload = S['AnswerPayload']
export type AnswerAck = S['AnswerAck']
export type FspStatus = S['FspStatus']
export type FspAchievement = S['FspAchievement']
export type SurveyQuestion = S['SurveyQuestion']
export type SurveyResult = S['SurveyResult']
export type Consent = S['Consent']
export type Skill = S['Skill']
export type DeclineReason = S['DeclineReason']
export type WorkFormat = S['WorkFormat']
export type SpecializationCode = S['SpecializationCode']
export type GradeCode = S['GradeCode']

/** Ключи запросов: всё начинается с 'candidate', чтобы не пересекаться с другими ролями. */
export const qk = {
  all: ['candidate'] as const,
  dashboard: ['candidate', 'dashboard'] as const,
  profile: ['candidate', 'profile'] as const,
  settings: ['candidate', 'settings'] as const,
  consents: ['candidate', 'consents'] as const,
  grade: ['candidate', 'grade'] as const,
  sessions: ['candidate', 'sessions'] as const,
  session: (id: number) => ['candidate', 'session', id] as const,
  result: (id: number) => ['candidate', 'result', id] as const,
  survey: ['candidate', 'survey'] as const,
  invitations: ['candidate', 'invitations'] as const,
  invitation: (id: number) => ['candidate', 'invitation', id] as const,
  vacancies: (filters: Record<string, unknown>) => ['candidate', 'vacancies', filters] as const,
  applications: ['candidate', 'applications'] as const,
  tasks: ['candidate', 'tasks'] as const,
  fspStatus: ['candidate', 'fsp', 'status'] as const,
  fspAchievements: ['candidate', 'fsp', 'achievements'] as const,
  skills: ['candidate', 'catalog', 'skills'] as const,
  declineReasons: ['candidate', 'catalog', 'decline-reasons'] as const,
}

export const useDashboard = () =>
  useQuery({ queryKey: qk.dashboard, queryFn: () => api.get<CandidateDashboard>('/candidates/me/dashboard') })

export const useProfile = () =>
  useQuery({ queryKey: qk.profile, queryFn: () => api.get<CandidateProfile>('/candidates/me/profile') })

export const useSettings = () =>
  useQuery({ queryKey: qk.settings, queryFn: () => api.get<CandidateSettings>('/candidates/me/settings') })

export const useConsents = () =>
  useQuery({ queryKey: qk.consents, queryFn: () => api.get<Consent[]>('/users/me/consents') })

export const useGradeStatus = () =>
  useQuery({ queryKey: qk.grade, queryFn: () => api.get<GradeStatus>('/testing/grade') })

export const useInvitations = () =>
  useQuery({ queryKey: qk.invitations, queryFn: () => api.get<Invitation[]>('/invitations') })

export const useApplications = () =>
  useQuery({ queryKey: qk.applications, queryFn: () => api.get<Application[]>('/applications') })

export const useTaskInbox = () => useQuery({ queryKey: qk.tasks, queryFn: () => api.get<TaskInbox>('/tasks/inbox') })

export const useFspStatus = () =>
  useQuery({ queryKey: qk.fspStatus, queryFn: () => api.get<FspStatus>('/fsp/status') })

export const useFspAchievements = () =>
  useQuery({ queryKey: qk.fspAchievements, queryFn: () => api.get<FspAchievement[]>('/fsp/achievements') })

/** Справочник стека: в случае ошибки экраны работают с кодами технологий. */
export const useSkills = () =>
  useQuery({ queryKey: qk.skills, queryFn: () => api.get<Skill[]>('/catalog/skills'), staleTime: 10 * 60_000 })

export const useDeclineReasons = () =>
  useQuery({
    queryKey: qk.declineReasons,
    queryFn: () => api.get<S['DeclineReasonItem'][]>('/catalog/decline-reasons'),
    staleTime: 10 * 60_000,
  })

/** Подпись технологии по коду из справочника (python → Python). */
export function useSkillLabel(): (id: string) => string {
  const skills = useSkills()
  return (id: string) => skills.data?.find((s) => s.id === id)?.label ?? id
}

/** Старт теста. 409 session_in_progress отдаёт id начатой сессии в details. */
export function useStartTest() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (body: S['TestSessionCreate']) => api.post<TestSessionState>('/testing/sessions', body),
    onSuccess: (state) => {
      client.setQueryData(qk.session(state.session.id), state)
      void client.invalidateQueries({ queryKey: qk.sessions })
      void client.invalidateQueries({ queryKey: qk.grade })
    },
  })
}

/** После действий, меняющих профиль, обновить всё, что от него зависит. */
export function invalidateCandidate(client: ReturnType<typeof useQueryClient>) {
  return client.invalidateQueries({ queryKey: qk.all })
}
