/**
 * Общая база моков прототипа: все фикстуры data/seed в одном изменяемом хранилище.
 *
 * Зачем: хендлеры разных ролей работают с ОДНИМИ данными. Рекрутер отправил приглашение →
 * соискатель видит его у себя после переключения роли. Изменения сохраняются в localStorage,
 * «Сбросить данные» в демо-плашке возвращает исходные фикстуры.
 *
 * Правила для хендлеров:
 * - читать: `db.data.invitations`; менять: мутировать массив/объект, затем `db.save()`;
 * - новый id: `db.nextId('invitations')`; текущее время: `db.now()`;
 * - кто делает запрос: `demoUser(request)` (заголовки X-Demo-Role / X-Demo-User-Id).
 * Этот файл в волне 1 не правится.
 */
import type { Role } from '@/shared/config/roles'
import { isRole } from '@/shared/config/roles'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import applications from '@seed/applications.json'
import auditLog from '@seed/audit_log.json'
import candidates from '@seed/candidates.json'
import categories from '@seed/categories.json'
import companies from '@seed/companies.json'
import consents from '@seed/consents.json'
import declineReasons from '@seed/decline_reasons.json'
import demoAccounts from '@seed/demo_accounts.json'
import fspAchievements from '@seed/fsp_achievements.json'
import gradeHistory from '@seed/grade_history.json'
import grades from '@seed/grades.json'
import invitationEvents from '@seed/invitation_events.json'
import invitations from '@seed/invitations.json'
import items from '@seed/items.json'
import needs from '@seed/needs.json'
import platformSettings from '@seed/platform_settings.json'
import recruiters from '@seed/recruiters.json'
import regularTasks from '@seed/regular_tasks.json'
import reports from '@seed/reports.json'
import skills from '@seed/skills.json'
import specializations from '@seed/specializations.json'
import surveyQuestions from '@seed/survey_questions.json'
import taskSubmissions from '@seed/task_submissions.json'
import testSessions from '@seed/test_sessions.json'
import topics from '@seed/topics.json'
import users from '@seed/users.json'
import vacancies from '@seed/vacancies.json'
import vacancyTests from '@seed/vacancy_tests.json'
import validationCharts from '@seed/validation_charts.json'

const SEED = {
  applications: applications,
  audit_log: auditLog,
  candidates: candidates,
  categories: categories,
  companies: companies,
  consents: consents,
  decline_reasons: declineReasons,
  demo_accounts: demoAccounts,
  fsp_achievements: fspAchievements,
  grade_history: gradeHistory,
  grades: grades,
  invitation_events: invitationEvents,
  invitations: invitations,
  items: items,
  needs: needs,
  platform_settings: platformSettings,
  recruiters: recruiters,
  regular_tasks: regularTasks,
  reports: reports,
  skills: skills,
  specializations: specializations,
  survey_questions: surveyQuestions,
  task_submissions: taskSubmissions,
  test_sessions: testSessions,
  topics: topics,
  users: users,
  vacancies: vacancies,
  vacancy_tests: vacancyTests,
  validation_charts: validationCharts,
}

type Seed = typeof SEED
export type MockDb = { -readonly [K in keyof Seed]: Seed[K][number][] }
export type CollectionName = keyof MockDb

const STORAGE_KEY = 'fsp.mockDb.v1'

function fresh(): MockDb {
  return structuredClone(SEED) as unknown as MockDb
}

function load(): MockDb {
  const raw = readStorage(STORAGE_KEY)
  if (raw) {
    try {
      return { ...fresh(), ...(JSON.parse(raw) as Partial<MockDb>) }
    } catch {
      // испорченное сохранение — начинаем с фикстур
    }
  }
  return fresh()
}

export const db = {
  data: load(),
  /** Сохранить изменения (вызывать после каждой мутации). */
  save(): void {
    writeStorage(STORAGE_KEY, JSON.stringify(this.data))
  },
  /** Вернуть исходные фикстуры. */
  reset(): void {
    writeStorage(STORAGE_KEY, null)
    this.data = fresh()
  },
  /** Следующий числовой id в коллекции. */
  nextId(name: CollectionName): number {
    const items = this.data[name] as Array<{ id: number | string }>
    return items.reduce((max, item) => (typeof item.id === 'number' && item.id > max ? item.id : max), 0) + 1
  },
  now(): string {
    return new Date().toISOString()
  },
}

export interface DemoRequestUser {
  role: Role | null
  userId: number | null
}

/** Кто делает запрос: роль и id пользователя из заголовков демо-авторизации. */
export function demoUser(request: Request): DemoRequestUser {
  const role = request.headers.get('X-Demo-Role')
  const id = Number(request.headers.get('X-Demo-User-Id'))
  return { role: isRole(role) ? role : null, userId: Number.isFinite(id) && id > 0 ? id : null }
}
