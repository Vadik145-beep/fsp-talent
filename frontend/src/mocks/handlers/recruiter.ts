import { http, HttpResponse, type HttpHandler } from 'msw'
import type { components } from '@/shared/api/schema'
import {
  GRADES,
  GRADE_LABELS,
  SPECIALIZATIONS,
  categoryLabel,
  type Grade,
  type Specialization,
} from '@/shared/config/dictionaries'
import { formatMoney, formatPercent } from '@/shared/lib/format'
import { db, demoUser } from '../db'
import { apiError, mockLatency, withScenario } from '../utils'

/**
 * Моки API кабинета рекрутера (трек 1b).
 *
 * Пути и формы ответов — по docs/api/openapi.json. Данные — общая база `db` (как у других ролей):
 * приглашение рекрутера сразу видно соискателю, ответ соискателя — рекрутеру.
 * Общие пути (/api/invitations, /api/vacancies…) обрабатываются только для роли recruiter,
 * для остальных хендлер возвращает undefined — MSW передаёт запрос дальше.
 */

type S = components['schemas']
type WorkFormat = S['WorkFormat']
type InvitationStatus = S['InvitationStatus']

// --- Строки базы (формы записей data/seed) ---------------------------------------------

interface CandidateRow {
  id: number
  user_id: number
  pseudonym: string
  full_name: string
  email: string
  phone: string | null
  telegram: string | null
  city: string | null
  work_formats: WorkFormat[]
  specialization: Specialization | null
  grade: Grade | null
  category: string | null
  category_label: string | null
  theta: number | null
  topic_scores: S['TopicScore'][]
  stack: string[]
  roles_in_team: string[]
  experience_years: number | null
  soft_skills: string[]
  links: S['ProfileLink'][] | null
  min_salary: number | null
  fsp_id: string | null
  fsp_score: number | null
  fsp_badges: S['FspBadge'][]
  privacy: { show_city: boolean; show_experience: boolean; show_links: boolean; show_fsp_achievements: boolean }
  job_search_paused: boolean
  publication_consent: boolean
  freshness: number
  last_test_at: string | null
}

type InvitationRow = Omit<
  S['Invitation'],
  'candidate' | 'candidate_contacts' | 'recruiter_contacts' | 'decline_reason_label'
>
type NeedRow = S['Need']
type VacancyRow = S['Vacancy']
type ApplicationRow = Omit<S['Application'], 'candidate' | 'candidate_contacts'>
type TaskRow = S['RegularTask']
type SubmissionRow = Omit<S['TaskSubmissionForRecruiter'], 'candidate'>
type RecruiterRow = S['Recruiter']
type CompanyRow = S['MyCompany']
type EventRow = S['InvitationEvent']

interface PlatformSettingsRow {
  invitation_quota: number
  invitation_ttl_days: number
  ranking_weights: Record<string, number>
}

const t = {
  candidates: () => db.data.candidates as unknown as CandidateRow[],
  invitations: () => db.data.invitations as unknown as InvitationRow[],
  events: () => db.data.invitation_events as unknown as EventRow[],
  needs: () => db.data.needs as unknown as NeedRow[],
  vacancies: () => db.data.vacancies as unknown as VacancyRow[],
  applications: () => db.data.applications as unknown as ApplicationRow[],
  tasks: () => db.data.regular_tasks as unknown as TaskRow[],
  submissions: () => db.data.task_submissions as unknown as SubmissionRow[],
  recruiters: () => db.data.recruiters as unknown as RecruiterRow[],
  companies: () => db.data.companies as unknown as CompanyRow[],
  settings: () => (db.data.platform_settings as unknown as PlatformSettingsRow[])[0],
  skills: () => db.data.skills as unknown as S['Skill'][],
  categories: () => db.data.categories as unknown as S['Category'][],
  declineReasons: () => db.data.decline_reasons as unknown as S['DeclineReasonItem'][],
}

// --- Кто спрашивает ------------------------------------------------------------------

interface RecruiterCtx {
  recruiter: RecruiterRow
  company: CompanyRow
}

/** Рекрутер из заголовков демо-авторизации; null — запрос не рекрутера (хендлер пропускает). */
function recruiterCtx(request: Request): RecruiterCtx | null {
  const { role, userId } = demoUser(request)
  if (role !== 'recruiter') return null
  const recruiters = t.recruiters()
  const recruiter = recruiters.find((r) => r.user_id === userId) ?? recruiters[0]
  const company = t.companies().find((c) => c.id === recruiter.company_id)
  if (!company) return null
  return { recruiter, company }
}

// --- Общие помощники -----------------------------------------------------------------

const ACTIVE_INVITATION: InvitationStatus[] = ['sent', 'viewed']
const WORK_FORMATS: WorkFormat[] = ['office', 'hybrid', 'remote']
const WORK_FORMAT_LABELS: Record<WorkFormat, string> = {
  office: 'офис',
  hybrid: 'гибрид',
  remote: 'удалённо',
}

function isSpec(v: unknown): v is Specialization {
  return typeof v === 'string' && (SPECIALIZATIONS as readonly string[]).includes(v)
}
function isGrade(v: unknown): v is Grade {
  return typeof v === 'string' && (GRADES as readonly string[]).includes(v)
}
function isWorkFormat(v: unknown): v is WorkFormat {
  return typeof v === 'string' && (WORK_FORMATS as string[]).includes(v)
}

function skillLabel(id: string): string {
  return t.skills().find((s) => s.id === id)?.label ?? id
}

function addDays(iso: string, days: number): string {
  return new Date(new Date(iso).getTime() + days * 86_400_000).toISOString()
}

async function readJson<T>(request: Request): Promise<Partial<T>> {
  try {
    const body = (await request.json()) as unknown
    return body && typeof body === 'object' ? (body as Partial<T>) : {}
  } catch {
    return {}
  }
}

function validationError(fields: Record<string, string>) {
  return apiError(422, 'validation_error', 'Проверьте поля формы.', { fields })
}

function notFound(what = 'Объект не найден') {
  return apiError(404, 'not_found', what)
}

function forbidden(message = 'Недостаточно прав') {
  return apiError(403, 'forbidden', message)
}

/** Проверка вилки от–до (обязательна, от ≤ до). Возвращает ответ-ошибку или null. */
function checkSalary(from: unknown, to: unknown) {
  const fields: Record<string, string> = {}
  if (typeof from !== 'number' || !Number.isFinite(from) || from <= 0) fields.salary_from = 'Укажите сумму «от»'
  if (typeof to !== 'number' || !Number.isFinite(to) || to <= 0) fields.salary_to = 'Укажите сумму «до»'
  if (Object.keys(fields).length) return validationError(fields)
  if ((from as number) > (to as number)) {
    return apiError(422, 'salary_range_invalid', 'Сумма «от» больше суммы «до».', {
      fields: { salary_from: '«От» не может быть больше «до»' },
    })
  }
  return null
}

function num(v: string | null): number | null {
  if (v === null || v === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : null
}

function bool(v: string | null): boolean | null {
  if (v === 'true' || v === '1') return true
  if (v === 'false' || v === '0') return false
  return null
}

// --- Видимость кандидатов (ТЗ 2.2) ---------------------------------------------------

/** В банке и подборке — только с грейдом, согласием на публикацию и без паузы поиска. */
function isVisible(c: CandidateRow): boolean {
  return c.grade !== null && c.category !== null && c.publication_consent && !c.job_search_paused
}

/** Обезличенная карточка: без ФИО, почты, телефона, мессенджеров и минимальной зарплаты. */
export function toCandidateCard(c: CandidateRow): S['CandidateCard'] {
  const showFsp = c.privacy.show_fsp_achievements
  return {
    id: c.id,
    pseudonym: c.pseudonym,
    specialization: c.specialization,
    grade: c.grade,
    category: c.category,
    category_label: c.category_label,
    theta: c.theta,
    stack: [...c.stack],
    work_formats: [...c.work_formats],
    roles_in_team: [...c.roles_in_team],
    city: c.privacy.show_city ? c.city : null,
    experience_years: c.privacy.show_experience ? c.experience_years : null,
    links: c.privacy.show_links ? c.links : null,
    has_fsp: Boolean(c.fsp_id),
    fsp_score: c.fsp_id && showFsp ? c.fsp_score : null,
    fsp_badges: c.fsp_id && showFsp ? c.fsp_badges : [],
    topic_scores: c.topic_scores,
    freshness: c.freshness,
  }
}

function candidateContacts(c: CandidateRow): S['CandidateContacts'] {
  return { full_name: c.full_name, email: c.email, phone: c.phone, telegram: c.telegram }
}

/** Контакты открыты: кандидат принял приглашение компании или сам откликнулся на её вакансию. */
function contactsOpen(candidateId: number, companyId: number): boolean {
  const accepted = t
    .invitations()
    .some((i) => i.candidate_id === candidateId && i.company_id === companyId && i.status === 'accepted')
  const applied = t.applications().some((a) => a.candidate_id === candidateId && a.company_id === companyId)
  return accepted || applied
}

/** Последнее приглашение кандидату от компании. */
function lastInvitation(candidateId: number, companyId: number): InvitationRow | undefined {
  return t
    .invitations()
    .filter((i) => i.candidate_id === candidateId && i.company_id === companyId)
    .sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
}

// --- Приглашения: истечение, квота, обогащение --------------------------------------

/** Приглашения без ответа дольше срока переходят в «истекло» (лениво, при чтении). */
function expireStale(): void {
  const now = db.now()
  let changed = false
  for (const inv of t.invitations()) {
    if (ACTIVE_INVITATION.includes(inv.status) && inv.expires_at < now) {
      inv.status = 'expired'
      t.events().push({ id: db.nextId('invitation_events'), invitation_id: inv.id, type: 'expired', at: now, actor_role: null })
      changed = true
    }
  }
  if (changed) db.save()
}

function quotaFor(recruiterId: number): S['InvitationQuota'] {
  const limit = t.settings()?.invitation_quota ?? 20
  const used = t.invitations().filter((i) => i.recruiter_id === recruiterId && ACTIVE_INVITATION.includes(i.status)).length
  const left = Math.max(0, limit - used)
  return {
    limit,
    used,
    left,
    hint:
      left === 0
        ? 'Квота исчерпана. Отзовите неактуальные приглашения или дождитесь ответов кандидатов.'
        : null,
  }
}

function enrichInvitation(inv: InvitationRow): S['Invitation'] {
  const cand = t.candidates().find((c) => c.id === inv.candidate_id)
  return {
    ...inv,
    candidate: cand ? toCandidateCard(cand) : null,
    candidate_contacts: cand && inv.status === 'accepted' ? candidateContacts(cand) : null,
    recruiter_contacts: null,
    decline_reason_label: inv.decline_reason
      ? (t.declineReasons().find((r) => r.id === inv.decline_reason)?.label ?? null)
      : null,
  }
}

// --- Подбор и ранжирование (T6.2, T6.3) ---------------------------------------------

const ADJACENT_SPECS: Record<Specialization, Specialization[]> = {
  backend: ['devops', 'data_ml'],
  frontend: ['mobile', 'backend'],
  mobile: ['frontend'],
  data_ml: ['backend'],
  qa: ['backend', 'frontend'],
  devops: ['backend'],
}

function categoryCandidates(category: string): CandidateRow[] {
  return t.candidates().filter((c) => isVisible(c) && c.category === category)
}

export function recommendedCategories(need: Pick<NeedRow, 'specialization' | 'grade'>): S['RecommendedCategory'][] {
  const gi = GRADES.indexOf(need.grade)
  const list: Array<{ category: string; relation: S['CategoryRelation'] }> = [
    { category: `${need.specialization}:${need.grade}`, relation: 'primary' },
  ]
  if (gi > 0) list.push({ category: `${need.specialization}:${GRADES[gi - 1]}`, relation: 'grade_lower' })
  if (gi < GRADES.length - 1) list.push({ category: `${need.specialization}:${GRADES[gi + 1]}`, relation: 'grade_higher' })
  for (const spec of ADJACENT_SPECS[need.specialization]) {
    list.push({ category: `${spec}:${need.grade}`, relation: 'adjacent_specialization' })
  }
  return list.map((x) => ({
    category: x.category,
    label: categoryLabel(x.category),
    relation: x.relation,
    candidates_count: categoryCandidates(x.category).length,
  }))
}

/** Нормальная функция распределения: θ → доля прошедших тест с уровнем ниже. */
function normalCdf(x: number): number {
  const sign = x < 0 ? -1 : 1
  const z = Math.abs(x) / Math.SQRT2
  const tt = 1 / (1 + 0.3275911 * z)
  const y = 1 - ((((1.061405429 * tt - 1.453152027) * tt + 1.421413741) * tt - 0.284496736) * tt + 0.254829592) * tt * Math.exp(-z * z)
  return 0.5 * (1 + sign * y)
}

const round2 = (v: number) => Math.round(v * 100) / 100

export function scoreCandidate(c: CandidateRow, need: NeedRow): S['MatchedCandidate'] {
  const weights = { stack: 0.3, theta: 0.25, fsp: 0.15, freshness: 0.1, salary: 0.1, work_format: 0.1, ...t.settings()?.ranking_weights }
  const stack = new Set(c.stack)
  const req = need.skills_required ?? []
  const des = need.skills_desired ?? []
  const reqHit = req.filter((s) => stack.has(s))
  const desHit = des.filter((s) => stack.has(s))
  const reqShare = req.length ? reqHit.length / req.length : 0.5
  const desShare = des.length ? desHit.length / des.length : 0
  const stackValue = des.length ? reqShare * 0.75 + desShare * 0.25 : reqShare

  const thetaValue = c.theta === null ? 0 : normalCdf(c.theta)
  const showFsp = Boolean(c.fsp_id) && c.privacy.show_fsp_achievements
  const fspValue = showFsp && c.fsp_score ? Math.min(1, c.fsp_score / 100) : 0
  const freshValue = c.freshness
  const minSalary = c.min_salary ?? 0
  const salaryFit = minSalary <= need.salary_to
  const salaryValue = minSalary <= need.salary_from ? 1 : salaryFit ? 0.7 : 0
  const formatValue = c.work_formats.includes(need.work_format)
    ? 1
    : need.work_format !== 'office' && c.work_formats.includes('hybrid')
      ? 0.5
      : 0

  const factors: Array<{ factor: string; label: string; value: number }> = [
    { factor: 'stack', label: 'Стек', value: stackValue },
    { factor: 'theta', label: 'Результат теста', value: thetaValue },
    { factor: 'fsp', label: 'Достижения ФСП', value: fspValue },
    { factor: 'freshness', label: 'Свежесть профиля', value: freshValue },
    { factor: 'salary', label: 'Зарплата', value: salaryValue },
    { factor: 'work_format', label: 'Формат работы', value: formatValue },
  ]
  const breakdown: S['ScoreComponent'][] = factors.map((f) => {
    const weight = weights[f.factor as keyof typeof weights] ?? 0
    return { ...f, value: round2(f.value), weight, contribution: round2(f.value * weight) }
  })
  const score = round2(Math.min(1, breakdown.reduce((sum, b) => sum + b.value * b.weight, 0)))

  // «Почему в подборке»: причины по самым весомым факторам, 2–4 штуки.
  const reasons: Array<{ text: string; weight: number }> = []
  if (reqHit.length) {
    const extra = desHit.length ? `, плюс ${desHit.map(skillLabel).join(', ')}` : ''
    reasons.push({
      text: `Стек: ${reqHit.length} из ${req.length} обязательных (${reqHit.map(skillLabel).join(', ')})${extra}`,
      weight: breakdown[0].contribution,
    })
  } else if (desHit.length) {
    reasons.push({ text: `Есть желательные технологии: ${desHit.map(skillLabel).join(', ')}`, weight: breakdown[0].contribution })
  }
  if (c.theta !== null) {
    const strong = c.topic_scores.filter((ts) => ts.level === 'strong').map((ts) => ts.label)
    const pct = Math.round(thetaValue * 100)
    reasons.push({
      text: `Тест сильнее, чем у ${pct} % специалистов${strong.length ? `; сильные темы: ${strong.slice(0, 2).join(', ')}` : ''}`,
      weight: breakdown[1].contribution + 0.01,
    })
  }
  if (fspValue > 0) {
    const badge = c.fsp_badges[0]?.title
    reasons.push({ text: `Подтверждено ФСП${badge ? `: ${badge}` : ''}`, weight: breakdown[2].contribution })
  }
  if (freshValue >= 0.6) {
    reasons.push({ text: 'Профиль свежий: недавно решал задания', weight: breakdown[3].contribution })
  }
  if (salaryValue === 1) reasons.push({ text: 'Ожидания по зарплате укладываются в вилку', weight: breakdown[4].contribution })
  if (formatValue === 1) {
    reasons.push({ text: `Готов работать: ${WORK_FORMAT_LABELS[need.work_format]}`, weight: breakdown[5].contribution * 0.9 })
  }
  const top = reasons.sort((a, b) => b.weight - a.weight).slice(0, 4).map((r) => r.text)
  if (top.length < 2) top.push(`Категория по тесту: ${c.category_label ?? '—'}`)

  return {
    candidate: toCandidateCard(c),
    score,
    breakdown,
    reasons: top,
    salary_fit: salaryFit,
    invitation_status: null,
  }
}

// --- Разбор свободного текста потребности (T6.1, правила) ---------------------------

const SPEC_RULES: Array<[Specialization, RegExp]> = [
  ['devops', /devops|девопс|дев[\s-]?опс|\bsre\b|инфраструктур|kubernetes|k8s|кубер/i],
  ['qa', /\bqa\b|тестировщ|тестирован|автотест|\bаqa\b|\baqa\b|quality/i],
  ['data_ml', /data scien|дата[\s-]?сайент|\bml\b|машинн\w* обучени|аналитик данных|data engineer|дата[\s-]?инженер|\bds\b|nlp|computer vision/i],
  ['mobile', /мобильн|mobile|\bios\b|android|андроид|flutter|swift|kotlin multiplatform/i],
  ['frontend', /фронт|frontend|front-end|react|реакт|vue|angular|вёрстк|верстк/i],
  ['backend', /бэкенд|бекенд|backend|back-end|серверн|\bgo\b|golang|\bна го\b|python|питон|java\b|джав|php|node\.?js|\bnode\b|c#|\.net|fastapi|django|spring/i],
]

const GRADE_RULES: Array<[Grade, RegExp]> = [
  ['intern', /стаж[её]р|стажир|intern|интерн|практикант/i],
  ['junior', /джун|junior|младш/i],
  ['senior', /сеньор|синьор|сеньер|сениор|senior|старш|ведущ|тимлид|team ?lead|\blead\b/i],
  ['middle', /мидл|миддл|middle|mid\b/i],
]

const SKILL_ALIASES: Record<string, string> = {
  'питон': 'python',
  'пайтон': 'python',
  'golang': 'go',
  'го': 'go',
  'джава': 'java',
  'котлин': 'kotlin',
  'постгрес': 'postgresql',
  'postgres': 'postgresql',
  'кафка': 'kafka',
  'редис': 'redis',
  'реакт': 'react',
  'react.js': 'react',
  'reactjs': 'react',
  'вью': 'vue',
  'js': 'javascript',
  'ts': 'typescript',
  'тайпскрипт': 'typescript',
  'node': 'nodejs',
  'нода': 'nodejs',
  'k8s': 'kubernetes',
  'кубер': 'kubernetes',
  'кубернетес': 'kubernetes',
  'докер': 'docker',
  'линукс': 'linux',
  'спарк': 'spark',
  'airflow': 'airflow',
  'sklearn': 'scikit_learn',
  'торч': 'pytorch',
  'кликхаус': 'clickhouse',
  'селениум': 'selenium',
  'next': 'nextjs',
  'tailwind': 'tailwind',
  'css': 'html_css',
  'html': 'html_css',
  'c#': 'csharp',
  '.net': 'csharp',
}

const CITIES = ['Москва', 'Санкт-Петербург', 'Казань', 'Новосибирск', 'Екатеринбург', 'Нижний Новгород', 'Самара', 'Краснодар', 'Пермь', 'Томск']
const CITY_RULES: Array<[string, RegExp]> = [
  ['Москва', /москв|мск/i],
  ['Санкт-Петербург', /петербург|спб|питер\b/i],
  ...CITIES.slice(2).map((city): [string, RegExp] => [city, new RegExp(city.slice(0, -1), 'i')]),
]

const DOMAINS: Array<[string, RegExp]> = [
  ['Финтех', /финтех|fintech|банк|платёж|платеж/i],
  ['E-commerce', /e-?commerce|маркетплейс|интернет-магазин|ритейл|retail/i],
  ['Медицина', /медицин|медтех|здрав/i],
  ['Образование', /edtech|образован|обучени/i],
  ['Логистика', /логистик|доставк/i],
  ['Игры', /геймдев|gamedev|игр/i],
  ['B2B SaaS', /saas|b2b/i],
]

function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Ищет технологии справочника в тексте (по коду, подписи и синонимам). */
function findSkills(text: string): string[] {
  const found: string[] = []
  const lower = text.toLowerCase()
  const has = (token: string) => new RegExp(`(^|[^a-zа-яё0-9+#.])${escapeRe(token.toLowerCase())}(?=$|[^a-zа-яё0-9+#])`, 'i').test(lower)
  for (const s of t.skills()) {
    const tokens = [s.id.replace('_', ' '), s.label]
    if (s.id === 'go') tokens.splice(0, tokens.length, 'go')
    if (tokens.some(has) && !found.includes(s.id)) found.push(s.id)
  }
  for (const [alias, id] of Object.entries(SKILL_ALIASES)) {
    if (has(alias) && !found.includes(id) && t.skills().some((s) => s.id === id)) found.push(id)
  }
  return found
}

function toRub(value: number, suffix: string | undefined): number {
  if (suffix && /к|k|тыс/i.test(suffix)) return value * 1000
  if (value < 1000) return value * 1000
  return value
}

function parseSalary(text: string): { from: number | null; to: number | null } {
  const clean = text.replace(/(\d)\s(?=\d{3}\b)/g, '$1')
  const range = clean.match(/(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?\s*(?:–|—|-|до)\s*(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?|000|₽|руб)?/i)
  if (range) {
    const suffix = range[4] ?? range[2]
    const a = toRub(parseFloat(range[1].replace(',', '.')), range[2] ?? suffix)
    const b = toRub(parseFloat(range[3].replace(',', '.')), suffix)
    if (a >= 10000 && b >= 10000) return { from: Math.round(a), to: Math.round(b) }
  }
  const from = clean.match(/от\s*(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?/i)
  const to = clean.match(/до\s*(\d+(?:[.,]\d+)?)\s*(к|k|тыс\.?)?/i)
  const f = from ? toRub(parseFloat(from[1].replace(',', '.')), from[2]) : null
  const tt = to ? toRub(parseFloat(to[1].replace(',', '.')), to[2]) : null
  return { from: f && f >= 10000 ? Math.round(f) : null, to: tt && tt >= 10000 ? Math.round(tt) : null }
}

const SPEC_TITLE: Record<Specialization, string> = {
  backend: 'Backend-разработчик',
  frontend: 'Frontend-разработчик',
  mobile: 'Mobile-разработчик',
  data_ml: 'Data Scientist / ML-инженер',
  qa: 'QA-инженер',
  devops: 'DevOps-инженер',
}

export function parseNeedText(text: string): S['NeedParseResult'] {
  const desiredSplit = text.split(/желательно|будет плюсом|плюсом будет|приветствуется|nice to have|как плюс/i)
  const mainText = desiredSplit[0]
  const desiredText = desiredSplit.slice(1).join(' ')

  const specialization = SPEC_RULES.find(([, re]) => re.test(text))?.[0] ?? null
  const grade = GRADE_RULES.find(([, re]) => re.test(text))?.[0] ?? null
  const required = findSkills(mainText)
  const desired = findSkills(desiredText).filter((s) => !required.includes(s))
  const work_format: WorkFormat | null = /удал[её]н|remote|из дома|дистанц/i.test(text)
    ? 'remote'
    : /гибрид|hybrid/i.test(text)
      ? 'hybrid'
      : /офис|office/i.test(text)
        ? 'office'
        : null
  const city = CITY_RULES.find(([, re]) => re.test(text))?.[0] ?? null
  const salary = parseSalary(text)
  const domain = DOMAINS.find(([, re]) => re.test(text))?.[0] ?? null

  const mainSkill = required[0] ? skillLabel(required[0]) : null
  const title = specialization
    ? `${grade ? GRADE_LABELS[grade] + ' ' : ''}${SPEC_TITLE[specialization]}${mainSkill ? ` (${mainSkill})` : ''}`
    : null

  const draft: S['NeedDraft'] = {
    title,
    specialization,
    grade,
    skills_required: required,
    skills_desired: desired,
    team_description: domain ? `Сфера: ${domain}` : null,
    work_format,
    city,
    salary_from: salary.from,
    salary_to: salary.to,
  }
  const checks: Array<[string, boolean]> = [
    ['specialization', Boolean(specialization)],
    ['grade', Boolean(grade)],
    ['skills_required', required.length > 0],
    ['skills_desired', desired.length > 0],
    ['work_format', Boolean(work_format)],
    ['salary_from', salary.from !== null],
    ['salary_to', salary.to !== null],
    ['city', Boolean(city)],
    ['team_description', Boolean(domain)],
  ]
  return {
    draft,
    parser: 'rules',
    recognized_fields: checks.filter(([, ok]) => ok).map(([f]) => f),
    // По контракту — фрагменты текста, которые не разобрали; правила мока таких не выделяют.
    unrecognized: [],
  }
}

// --- Рыночная подсказка (T7.7) ------------------------------------------------------

function median(values: number[]): number | null {
  if (!values.length) return null
  const s = [...values].sort((a, b) => a - b)
  const mid = Math.floor(s.length / 2)
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2)
}

const round10k = (v: number) => Math.round(v / 10000) * 10000

export function marketHint(category: string, salaryFrom: number | null, salaryTo: number | null): S['MarketHint'] {
  const accepted = t.invitations().filter((i) => i.category === category && i.status === 'accepted')
  const pool = t.candidates().filter((c) => c.category === category && c.min_salary)
  const mins = pool.map((c) => c.min_salary as number)
  let from: number | null
  let to: number | null
  let sample: number
  if (accepted.length >= 3) {
    from = median(accepted.map((i) => i.salary_from))
    to = median(accepted.map((i) => i.salary_to))
    sample = accepted.length
  } else {
    // Мало принятых приглашений — оцениваем по ожиданиям кандидатов категории (+ принятые).
    const m = median([...mins, ...accepted.map((i) => i.salary_from)])
    from = m !== null ? round10k(m) : null
    to = m !== null ? round10k(m * 1.25) : null
    sample = mins.length + accepted.length
  }
  let probability: number | null = null
  const upper = salaryTo ?? salaryFrom
  if (upper && mins.length) {
    const share = mins.filter((v) => v <= upper).length / mins.length
    const lowerFactor = from && salaryFrom ? Math.min(1, salaryFrom / from) : 1
    probability = Math.max(0.05, Math.min(0.95, 0.1 + 0.85 * share * (0.6 + 0.4 * lowerFactor)))
    probability = round2(probability)
  }
  const label = categoryLabel(category)
  let message = from ? `В категории ${label} обычно принимают от ${formatMoney(from)}.` : `По категории ${label} пока мало данных.`
  if (probability !== null) message += ` Вероятность принятия с такой вилкой — около ${formatPercent(probability)}.`
  return {
    category,
    category_label: label,
    median_accepted_from: from,
    median_accepted_to: to,
    acceptance_probability: probability,
    sample_size: sample,
    message,
  }
}

// --- Профиль кандидата для рекрутера -------------------------------------------------

function testHistory(candidateId: number): S['TestHistoryPoint'][] {
  const sessions = db.data.test_sessions as unknown as Array<{
    candidate_id: number
    status: string
    finished_at: string | null
    result_category: string | null
    passed: boolean | null
    theta: number | null
  }>
  // Как у бэкенда: только подтверждённые тесты, категория — присвоенная
  return sessions
    .filter((s) => s.candidate_id === candidateId && s.status === 'finished' && s.passed && s.finished_at && s.result_category && s.theta !== null)
    .map((s) => ({ date: s.finished_at as string, category: s.result_category as string, theta: s.theta as number }))
    .sort((a, b) => a.date.localeCompare(b.date))
}

export function anonymousProfile(c: CandidateRow, ctx: RecruiterCtx): S['AnonymousCandidateProfile'] {
  const open = contactsOpen(c.id, ctx.company.id)
  const inv = lastInvitation(c.id, ctx.company.id)
  const activeInv = inv && ACTIVE_INVITATION.includes(inv.status)
  return {
    ...toCandidateCard(c),
    soft_skills: [...c.soft_skills],
    test_history: testHistory(c.id),
    invitation_id: inv?.id ?? null,
    invitation_status: inv?.status ?? null,
    contacts_visible: open,
    contacts: open ? candidateContacts(c) : null,
    // После ответа (принято/отклонено/истекло) можно отправить новое предложение; активное — только одно.
    can_invite: isVisible(c) && !activeInv && quotaFor(ctx.recruiter.id).left > 0,
  }
}

// --- Обогащение откликов, заданий, потребностей --------------------------------------

function enrichApplication(a: ApplicationRow): S['Application'] {
  const c = t.candidates().find((x) => x.id === a.candidate_id)
  // Кандидат откликнулся сам — контакты открыты сразу [ТЗ 2.1].
  return { ...a, candidate: c ? toCandidateCard(c) : null, candidate_contacts: c ? candidateContacts(c) : null }
}

function enrichNeed(n: NeedRow): NeedRow {
  return { ...n, candidates_count: categoryCandidates(n.category).length }
}

function enrichVacancy(v: VacancyRow): VacancyRow {
  return { ...v, applications_count: t.applications().filter((a) => a.vacancy_id === v.id).length }
}

function enrichTask(task: TaskRow): TaskRow {
  return { ...task, submissions_count: t.submissions().filter((s) => s.task_id === task.id).length }
}

function enrichSubmission(s: SubmissionRow): S['TaskSubmissionForRecruiter'] {
  const c = t.candidates().find((x) => x.id === s.candidate_id)
  return { ...s, candidate: c ? toCandidateCard(c) : null }
}

function findOwnNeed(id: number, ctx: RecruiterCtx): NeedRow | undefined {
  return t.needs().find((n) => n.id === id && n.company_id === ctx.company.id)
}

function findOwnVacancy(id: number, ctx: RecruiterCtx): VacancyRow | undefined {
  return t.vacancies().find((v) => v.id === id && v.company_id === ctx.company.id)
}

/** Обязательные поля потребности/вакансии. */
function checkPositionFields(body: Partial<S['NeedCreate'] & S['VacancyCreate']>, withDescription: boolean) {
  const fields: Record<string, string> = {}
  if (!body.title || body.title.trim().length < 3) fields.title = 'Название — не короче 3 символов'
  if (withDescription && (!body.description || body.description.trim().length < 10)) {
    fields.description = 'Описание — не короче 10 символов'
  }
  if (!isSpec(body.specialization)) fields.specialization = 'Выберите специализацию'
  if (!isGrade(body.grade)) fields.grade = 'Выберите грейд'
  if (!isWorkFormat(body.work_format)) fields.work_format = 'Выберите формат работы'
  return Object.keys(fields).length ? validationError(fields) : null
}

function normSkills(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : []
}

// --- Хендлеры ------------------------------------------------------------------------

/** GET с учётом режима данных демо-плашки; не рекрутер → undefined (запрос идёт дальше). */
function recruiterGet<T>(
  build: (ctx: RecruiterCtx, info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => T | Response,
  empty?: (ctx: RecruiterCtx) => T,
) {
  return async (info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => {
    const ctx = recruiterCtx(info.request)
    if (!ctx) return undefined
    expireStale()
    let direct: Response | undefined
    const resolver = withScenario({
      data: () => {
        const out = build(ctx, info)
        if (out instanceof Response) {
          direct = out
          return null
        }
        return out
      },
      empty: empty ? () => empty(ctx) : undefined,
    })
    const res = await resolver(info as never)
    return direct ?? res
  }
}

/** Мутации: задержка сети + только рекрутер. */
function recruiterMutation(
  run: (ctx: RecruiterCtx, info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => Promise<Response> | Response,
) {
  return async (info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => {
    const ctx = recruiterCtx(info.request)
    if (!ctx) return undefined
    await mockLatency()
    expireStale()
    return run(ctx, info)
  }
}

/** Демо-код приглашения в компанию: «FSP-C001-7K3Q». Пока не перевыпущен — детерминированный. */
function inviteCodeOf(company: CompanyRow): string {
  if (company.invite_code) return company.invite_code
  return makeInviteCode(company, `${company.id}:${company.inn ?? company.name}`)
}

function makeInviteCode(company: CompanyRow, seed: string): string {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
  let h = 2166136261
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619) >>> 0
  let tail = ''
  for (let i = 0; i < 4; i++) {
    tail += alphabet[h % alphabet.length]
    h = Math.floor(h / alphabet.length)
  }
  return `FSP-C${String(company.id).padStart(3, '0')}-${tail}`
}

const idParam = (v: string | readonly string[] | undefined) => Number(Array.isArray(v) ? v[0] : v)

export const recruiterHandlers: HttpHandler[] = [
  // --- Справочники (для форм рекрутера) ---
  http.get(
    '/api/catalog/skills',
    recruiterGet((_ctx, { request }) => {
      const url = new URL(request.url)
      const spec = url.searchParams.get('specialization')
      const q = url.searchParams.get('q')?.toLowerCase()
      return t
        .skills()
        .filter((s) => (!spec || s.specializations.includes(spec as Specialization)) && (!q || s.label.toLowerCase().includes(q)))
    }),
  ),
  http.get(
    '/api/catalog/categories',
    recruiterGet((_ctx, { request }) => {
      const spec = new URL(request.url).searchParams.get('specialization')
      return t.categories().filter((c) => !spec || c.specialization === spec)
    }),
  ),
  http.get(
    '/api/catalog/decline-reasons',
    recruiterGet(() => t.declineReasons()),
  ),

  // --- Компания ---
  http.get(
    '/api/companies/my',
    // Код приглашения в компанию — только администратору компании.
    recruiterGet((ctx) => {
      const { invite_code: _code, ...company } = ctx.company
      return ctx.recruiter.is_company_admin ? { ...company, invite_code: inviteCodeOf(ctx.company) } : company
    }),
  ),
  http.post(
    '/api/companies/my/invite-code',
    recruiterMutation((ctx) => {
      if (!ctx.recruiter.is_company_admin) return forbidden('Код приглашения меняет только администратор компании')
      ctx.company.invite_code = makeInviteCode(ctx.company, `${ctx.company.id}:${db.now()}:${Math.random()}`)
      db.save()
      return HttpResponse.json(ctx.company)
    }),
  ),
  http.put(
    '/api/companies/my',
    recruiterMutation(async (ctx, { request }) => {
      if (!ctx.recruiter.is_company_admin) return forbidden('Менять профиль может только администратор компании')
      const body = await readJson<S['CompanyUpdate']>(request)
      const fields: Record<string, string> = {}
      if (!body.name || body.name.trim().length < 2) fields.name = 'Название — не короче 2 символов'
      if (!body.contact_email || !/^\S+@\S+\.\S+$/.test(body.contact_email)) fields.contact_email = 'Укажите почту'
      if (Object.keys(fields).length) return validationError(fields)
      Object.assign(ctx.company, {
        name: body.name!.trim(),
        description: body.description ?? '',
        industry: body.industry ?? '',
        website: body.website || null,
        city: body.city || null,
        contact_email: body.contact_email,
        contact_phone: body.contact_phone || null,
      })
      db.save()
      return HttpResponse.json(ctx.company)
    }),
  ),
  http.get(
    '/api/companies/my/recruiters',
    recruiterGet((ctx) => t.recruiters().filter((r) => r.company_id === ctx.company.id)),
  ),
  http.get(
    '/api/companies/my/dashboard',
    recruiterGet<S['RecruiterDashboard']>(
      (ctx) => {
        const invitations = t.invitations().filter((i) => i.company_id === ctx.company.id)
        const byStatus: Record<string, number> = { sent: 0, viewed: 0, accepted: 0, declined: 0, expired: 0, withdrawn: 0 }
        for (const i of invitations) byStatus[i.status] = (byStatus[i.status] ?? 0) + 1
        const apps = t
          .applications()
          .filter((a) => a.company_id === ctx.company.id)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
        const q = quotaFor(ctx.recruiter.id)
        return {
          company_name: ctx.company.name,
          active_needs: t
            .needs()
            .filter((n) => n.company_id === ctx.company.id && n.status === 'active')
            .sort((a, b) => b.created_at.localeCompare(a.created_at))
            .map((n) => ({ id: n.id, title: n.title, category: n.category, candidates_count: categoryCandidates(n.category).length })),
          invitations_by_status: byStatus,
          quota: { limit: q.limit, used: q.used, left: q.left },
          new_applications_count: apps.filter((a) => a.status === 'new').length,
          recent_applications: apps.slice(0, 5).map((a) => ({
            id: a.id,
            vacancy_id: a.vacancy_id,
            vacancy_title: a.vacancy_title,
            candidate_pseudonym: t.candidates().find((c) => c.id === a.candidate_id)?.pseudonym ?? 'Кандидат',
            created_at: a.created_at,
          })),
        }
      },
      (ctx) => {
        const q = quotaFor(ctx.recruiter.id)
        return {
          company_name: ctx.company.name,
          active_needs: [],
          invitations_by_status: {},
          quota: { limit: q.limit, used: 0, left: q.limit },
          new_applications_count: 0,
          recent_applications: [],
        }
      },
    ),
  ),

  // --- Потребности и подборка ---
  http.post(
    '/api/matching/needs/parse',
    recruiterMutation(async (_ctx, { request }) => {
      const body = await readJson<S['NeedParseRequest']>(request)
      const text = (body.text ?? '').trim()
      if (text.length < 5) return validationError({ text: 'Опишите потребность хотя бы парой слов' })
      if (text.length > 3000) return validationError({ text: 'Не длиннее 3000 символов' })
      return HttpResponse.json(parseNeedText(text))
    }),
  ),
  http.get(
    '/api/matching/needs',
    recruiterGet(
      (ctx) =>
        t
          .needs()
          .filter((n) => n.company_id === ctx.company.id)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichNeed),
      () => [],
    ),
  ),
  http.post(
    '/api/matching/needs',
    recruiterMutation(async (ctx, { request }) => {
      const body = await readJson<S['NeedCreate']>(request)
      const err = checkPositionFields(body, false) ?? checkSalary(body.salary_from, body.salary_to)
      if (err) return err
      const category = `${body.specialization}:${body.grade}`
      const need: NeedRow = {
        id: db.nextId('needs'),
        company_id: ctx.company.id,
        recruiter_id: ctx.recruiter.id,
        title: body.title!.trim(),
        raw_text: body.raw_text?.trim() || null,
        specialization: body.specialization!,
        grade: body.grade!,
        skills_required: normSkills(body.skills_required),
        skills_desired: normSkills(body.skills_desired),
        team_description: body.team_description ?? '',
        work_format: body.work_format!,
        city: body.city?.trim() || null,
        salary_from: body.salary_from!,
        salary_to: body.salary_to!,
        category,
        category_label: categoryLabel(category),
        status: 'active',
        candidates_count: categoryCandidates(category).length,
        created_at: db.now(),
      }
      t.needs().push(need)
      db.save()
      return HttpResponse.json(need, { status: 201 })
    }),
  ),
  http.get(
    '/api/matching/needs/:need_id',
    recruiterGet((ctx, { params }) => {
      const need = findOwnNeed(idParam(params.need_id), ctx)
      return need ? enrichNeed(need) : notFound('Потребность не найдена')
    }),
  ),
  http.get(
    '/api/matching/needs/:need_id/categories',
    recruiterGet(
      (ctx, { params }) => {
        const need = findOwnNeed(idParam(params.need_id), ctx)
        return need ? recommendedCategories(need) : notFound('Потребность не найдена')
      },
      () => [],
    ),
  ),
  http.get(
    '/api/matching/needs/:need_id/candidates',
    recruiterGet<S['MatchList']>(
      (ctx, { params, request }) => {
        const need = findOwnNeed(idParam(params.need_id), ctx)
        if (!need) return notFound('Потребность не найдена') as never
        const url = new URL(request.url)
        const category = url.searchParams.get('category') || need.category
        if (!/^[a-z_]+:[a-z]+$/.test(category) || !t.categories().some((c) => c.id === category)) {
          return validationError({ category: 'Неизвестная категория' }) as never
        }
        const filters: S['MatchFilters'] = {
          skills: url.searchParams.getAll('skills').filter(Boolean),
          has_fsp: bool(url.searchParams.get('has_fsp')),
          work_format: isWorkFormat(url.searchParams.get('work_format')) ? (url.searchParams.get('work_format') as WorkFormat) : null,
          city: url.searchParams.get('city') || null,
        }
        const all = categoryCandidates(category)
          .map((c) => {
            const m = scoreCandidate(c, need)
            m.invitation_status = lastInvitation(c.id, ctx.company.id)?.status ?? null
            return m
          })
          .sort((a, b) => b.score - a.score || a.candidate.id - b.candidate.id)
        const items = all.filter(({ candidate: c }) => {
          if (filters.skills?.length && !filters.skills.every((s) => c.stack.includes(s))) return false
          if (filters.has_fsp === true && !c.has_fsp) return false
          if (filters.has_fsp === false && c.has_fsp) return false
          if (filters.work_format && !c.work_formats.includes(filters.work_format)) return false
          if (filters.city && c.city !== filters.city) return false
          return true
        })
        return {
          need_id: need.id,
          category,
          category_label: categoryLabel(category),
          total_before_filters: all.length,
          total: items.length,
          filters,
          items,
        }
      },
      () => ({ need_id: 0, category: '', category_label: '', total_before_filters: 0, total: 0, filters: {}, items: [] }),
    ),
  ),

  // --- Банк кандидатов и обезличенный профиль ---
  http.get(
    '/api/candidates',
    recruiterGet<S['Page_CandidateCard_']>(
      (_ctx, { request }) => {
        const p = new URL(request.url).searchParams
        const spec = p.get('specialization')
        const grade = p.get('grade')
        const category = p.get('category')
        const skills = p.getAll('skills').filter(Boolean)
        const hasFsp = bool(p.get('has_fsp'))
        const format = p.get('work_format')
        const city = p.get('city')
        const sort = p.get('sort') ?? 'theta'
        const page = Math.max(1, num(p.get('page')) ?? 1)
        const pageSize = Math.min(100, Math.max(1, num(p.get('page_size')) ?? 20))
        if (sort && !['theta', 'fsp', 'freshness', 'recent'].includes(sort)) {
          return validationError({ sort: 'Неизвестная сортировка' }) as never
        }
        const rows = t.candidates().filter((c) => {
          if (!isVisible(c)) return false
          if (spec && c.specialization !== spec) return false
          if (grade && c.grade !== grade) return false
          if (category && c.category !== category) return false
          if (skills.length && !skills.every((s) => c.stack.includes(s))) return false
          if (hasFsp === true && !(c.fsp_id && c.privacy.show_fsp_achievements)) return false
          if (hasFsp === false && c.fsp_id) return false
          if (format && !c.work_formats.includes(format as WorkFormat)) return false
          if (city && (!c.privacy.show_city || c.city !== city)) return false
          return true
        })
        const key = (c: CandidateRow): number => {
          if (sort === 'fsp') return c.fsp_id && c.privacy.show_fsp_achievements ? (c.fsp_score ?? 0) : -1
          if (sort === 'freshness') return c.freshness
          if (sort === 'recent') return c.last_test_at ? Date.parse(c.last_test_at) : 0
          return c.theta ?? -99
        }
        rows.sort((a, b) => key(b) - key(a) || a.id - b.id)
        return {
          items: rows.slice((page - 1) * pageSize, page * pageSize).map(toCandidateCard),
          total: rows.length,
          page,
          page_size: pageSize,
        }
      },
      () => ({ items: [], total: 0, page: 1, page_size: 20 }),
    ),
  ),
  http.get(
    '/api/candidates/:candidate_id',
    recruiterGet((ctx, { params }) => {
      const id = idParam(params.candidate_id)
      const c = t.candidates().find((x) => x.id === id)
      // Скрытый кандидат доступен, только если контакты уже открыты (принял приглашение / откликнулся).
      if (!c || (!isVisible(c) && !contactsOpen(c.id, ctx.company.id))) return notFound('Кандидат не найден или скрыл профиль')
      return anonymousProfile(c, ctx)
    }),
  ),

  // --- Приглашения ---
  http.get(
    '/api/invitations/quota',
    recruiterGet((ctx) => quotaFor(ctx.recruiter.id)),
  ),
  http.get(
    '/api/invitations/market-hint',
    recruiterGet((_ctx, { request }) => {
      const p = new URL(request.url).searchParams
      const category = p.get('category')
      if (!category) return validationError({ category: 'Укажите категорию' })
      if (!t.categories().some((c) => c.id === category)) return notFound('Категория не найдена')
      const from = num(p.get('salary_from'))
      const to = num(p.get('salary_to'))
      return marketHint(category, from && from > 0 ? from : null, to && to > 0 ? to : null)
    }),
  ),
  http.get(
    '/api/invitations',
    recruiterGet(
      (ctx, { request }) => {
        const status = new URL(request.url).searchParams.get('status')
        return t
          .invitations()
          .filter((i) => i.company_id === ctx.company.id && (!status || i.status === status))
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichInvitation)
      },
      () => [],
    ),
  ),
  http.post(
    '/api/invitations',
    recruiterMutation(async (ctx, { request }) => {
      const body = await readJson<S['InvitationCreate']>(request)
      const fields: Record<string, string> = {}
      if (!body.description || body.description.trim().length < 10) fields.description = 'Опишите предложение (от 10 символов)'
      const cm = body.contact_method
      if (!cm || !['email', 'phone', 'telegram', 'other'].includes(cm.type)) fields.contact_method = 'Выберите способ связи'
      else if (!cm.value || cm.value.trim().length < 2) fields.contact_method = 'Укажите контакт для связи'
      if (body.task_text && body.task_text.length > 2000) fields.task_text = 'Задание — не длиннее 2000 символов'
      if (Object.keys(fields).length) return validationError(fields)
      const salaryErr = checkSalary(body.salary_from, body.salary_to)
      if (salaryErr) return salaryErr

      const c = t.candidates().find((x) => x.id === body.candidate_id)
      if (!c || !isVisible(c)) return notFound('Кандидат не найден или скрыл профиль')
      const quota = quotaFor(ctx.recruiter.id)
      if (quota.left <= 0) {
        return apiError(409, 'quota_exceeded', `Достигнута квота: ${quota.limit} активных приглашений. Отзовите неактуальные или дождитесь ответов.`, {
          limit: quota.limit,
          used: quota.used,
        })
      }
      const existing = lastInvitation(c.id, ctx.company.id)
      if (existing && ACTIVE_INVITATION.includes(existing.status)) {
        return apiError(409, 'already_invited', 'У кандидата уже есть активное приглашение от вашей компании.', {
          invitation_id: existing.id,
        })
      }
      if (c.min_salary && (body.salary_to as number) < c.min_salary) {
        // Сумму ожиданий кандидата не раскрываем — только факт.
        return apiError(422, 'salary_below_expectations', 'Вилка ниже ожиданий кандидата. Поднимите верхнюю границу.', {
          fields: { salary_to: 'Ниже ожиданий кандидата' },
        })
      }
      if (body.need_id != null && !findOwnNeed(body.need_id, ctx)) return notFound('Потребность не найдена')
      if (body.vacancy_id != null && !findOwnVacancy(body.vacancy_id, ctx)) return notFound('Вакансия не найдена')

      const now = db.now()
      const ttl = t.settings()?.invitation_ttl_days ?? 7
      const inv: InvitationRow = {
        id: db.nextId('invitations'),
        candidate_id: c.id,
        recruiter_id: ctx.recruiter.id,
        company_id: ctx.company.id,
        company_name: ctx.company.name,
        recruiter_name: ctx.recruiter.full_name,
        need_id: body.need_id ?? null,
        vacancy_id: body.vacancy_id ?? null,
        category: c.category as string,
        category_label: c.category_label as string,
        description: body.description!.trim(),
        salary_from: body.salary_from!,
        salary_to: body.salary_to!,
        contact_method: { type: cm!.type, value: cm!.value.trim() },
        task_text: body.task_text?.trim() || null,
        status: 'sent',
        decline_reason: null,
        decline_comment: null,
        created_at: now,
        viewed_at: null,
        responded_at: null,
        expires_at: addDays(now, ttl),
        withdrawn_at: null,
      }
      t.invitations().push(inv)
      t.events().push({ id: db.nextId('invitation_events'), invitation_id: inv.id, type: 'created', at: now, actor_role: 'recruiter' })
      db.save()
      return HttpResponse.json(enrichInvitation(inv), { status: 201 })
    }),
  ),
  http.get(
    '/api/invitations/:invitation_id',
    recruiterGet((ctx, { params }) => {
      const inv = t.invitations().find((i) => i.id === idParam(params.invitation_id))
      if (!inv) return notFound('Приглашение не найдено')
      if (inv.company_id !== ctx.company.id) return forbidden('Это приглашение другой компании')
      const detail: S['InvitationDetail'] = {
        ...enrichInvitation(inv),
        events: t
          .events()
          .filter((e) => e.invitation_id === inv.id)
          .sort((a, b) => a.at.localeCompare(b.at)),
      }
      return detail
    }),
  ),
  http.post(
    '/api/invitations/:invitation_id/withdraw',
    recruiterMutation((ctx, { params }) => {
      const inv = t.invitations().find((i) => i.id === idParam(params.invitation_id))
      if (!inv) return notFound('Приглашение не найдено')
      if (inv.company_id !== ctx.company.id) return forbidden('Это приглашение другой компании')
      if (!ACTIVE_INVITATION.includes(inv.status)) {
        return apiError(409, 'invalid_transition', 'Отозвать можно только отправленное или просмотренное приглашение.', {
          status: inv.status,
        })
      }
      const now = db.now()
      inv.status = 'withdrawn'
      inv.withdrawn_at = now
      t.events().push({ id: db.nextId('invitation_events'), invitation_id: inv.id, type: 'withdrawn', at: now, actor_role: 'recruiter' })
      db.save()
      return HttpResponse.json(enrichInvitation(inv))
    }),
  ),
  // Принять / отклонить может только кандидат — рекрутеру 403 (кандидата обслуживает трек 1a).
  http.post(
    '/api/invitations/:invitation_id/accept',
    recruiterMutation(() => forbidden('Принять приглашение может только кандидат')),
  ),
  http.post(
    '/api/invitations/:invitation_id/decline',
    recruiterMutation(() => forbidden('Отклонить приглашение может только кандидат')),
  ),

  // --- Вакансии и отклики ---
  http.get(
    '/api/vacancies',
    recruiterGet(
      (ctx, { request }) => {
        const p = new URL(request.url).searchParams
        const q = p.get('q')?.toLowerCase()
        const spec = p.get('specialization')
        const grade = p.get('grade')
        return t
          .vacancies()
          .filter(
            (v) =>
              v.company_id === ctx.company.id &&
              (!q || v.title.toLowerCase().includes(q)) &&
              (!spec || v.specialization === spec) &&
              (!grade || v.grade === grade),
          )
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichVacancy)
      },
      () => [],
    ),
  ),
  http.post(
    '/api/vacancies',
    recruiterMutation(async (ctx, { request }) => {
      const body = await readJson<S['VacancyCreate']>(request)
      const err = checkPositionFields(body, true) ?? checkSalary(body.salary_from, body.salary_to)
      if (err) return err
      const category = `${body.specialization}:${body.grade}`
      const v: VacancyRow = {
        id: db.nextId('vacancies'),
        company_id: ctx.company.id,
        company_name: ctx.company.name,
        title: body.title!.trim(),
        description: body.description!.trim(),
        team_description: (body.team_description ?? '').trim(),
        specialization: body.specialization!,
        grade: body.grade!,
        skills_required: normSkills(body.skills_required),
        skills_desired: normSkills(body.skills_desired),
        work_format: body.work_format!,
        city: body.city?.trim() || null,
        salary_from: body.salary_from!,
        salary_to: body.salary_to!,
        category,
        category_label: categoryLabel(category),
        status: 'draft',
        applications_count: 0,
        created_at: db.now(),
        published_at: null,
        my_application_id: null,
      }
      t.vacancies().push(v)
      db.save()
      return HttpResponse.json(v, { status: 201 })
    }),
  ),
  http.get(
    '/api/vacancies/:vacancy_id',
    recruiterGet((ctx, { params }) => {
      const v = findOwnVacancy(idParam(params.vacancy_id), ctx)
      return v ? enrichVacancy(v) : notFound('Вакансия не найдена')
    }),
  ),
  http.put(
    '/api/vacancies/:vacancy_id',
    recruiterMutation(async (ctx, { params, request }) => {
      const v = findOwnVacancy(idParam(params.vacancy_id), ctx)
      if (!v) return notFound('Вакансия не найдена')
      const body = await readJson<S['VacancyCreate']>(request)
      const err = checkPositionFields(body, true) ?? checkSalary(body.salary_from, body.salary_to)
      if (err) return err
      const category = `${body.specialization}:${body.grade}`
      Object.assign(v, {
        title: body.title!.trim(),
        description: body.description!.trim(),
        specialization: body.specialization,
        grade: body.grade,
        skills_required: normSkills(body.skills_required),
        skills_desired: normSkills(body.skills_desired),
        work_format: body.work_format,
        city: body.city?.trim() || null,
        salary_from: body.salary_from,
        salary_to: body.salary_to,
        category,
        category_label: categoryLabel(category),
      })
      // Название вакансии в откликах — для обоих кабинетов.
      for (const a of t.applications()) if (a.vacancy_id === v.id) a.vacancy_title = v.title
      db.save()
      return HttpResponse.json(enrichVacancy(v))
    }),
  ),
  http.post(
    '/api/vacancies/:vacancy_id/publish',
    recruiterMutation((ctx, { params }) => {
      const v = findOwnVacancy(idParam(params.vacancy_id), ctx)
      if (!v) return notFound('Вакансия не найдена')
      if (v.status === 'published') return apiError(409, 'invalid_transition', 'Вакансия уже опубликована.')
      v.status = 'published'
      v.published_at = db.now()
      db.save()
      return HttpResponse.json(enrichVacancy(v))
    }),
  ),
  http.post(
    '/api/vacancies/:vacancy_id/unpublish',
    recruiterMutation((ctx, { params }) => {
      const v = findOwnVacancy(idParam(params.vacancy_id), ctx)
      if (!v) return notFound('Вакансия не найдена')
      if (v.status !== 'published') return apiError(409, 'invalid_transition', 'Вакансия не опубликована.')
      v.status = 'unpublished'
      db.save()
      return HttpResponse.json(enrichVacancy(v))
    }),
  ),
  http.get(
    '/api/vacancies/:vacancy_id/applications',
    recruiterGet(
      (ctx, { params }) => {
        const v = findOwnVacancy(idParam(params.vacancy_id), ctx)
        if (!v) return notFound('Вакансия не найдена')
        return t
          .applications()
          .filter((a) => a.vacancy_id === v.id)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichApplication)
      },
      () => [],
    ),
  ),
  http.post(
    '/api/vacancies/:vacancy_id/applications',
    recruiterMutation(() => forbidden('Откликаться может только кандидат')),
  ),
  http.get(
    '/api/applications',
    recruiterGet(
      (ctx) =>
        t
          .applications()
          .filter((a) => a.company_id === ctx.company.id)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichApplication),
      () => [],
    ),
  ),
  http.patch(
    '/api/applications/:application_id',
    recruiterMutation(async (ctx, { params, request }) => {
      const a = t.applications().find((x) => x.id === idParam(params.application_id))
      if (!a || a.company_id !== ctx.company.id) return notFound('Отклик не найден')
      const body = await readJson<S['ApplicationStatusUpdate']>(request)
      if (!body.status || !['new', 'viewed', 'invited', 'rejected'].includes(body.status)) {
        return validationError({ status: 'Неизвестный статус отклика' })
      }
      a.status = body.status
      a.updated_at = db.now()
      db.save()
      return HttpResponse.json(enrichApplication(a))
    }),
  ),

  // --- Регулярные задания ---
  http.get(
    '/api/tasks',
    recruiterGet(
      (ctx) =>
        t
          .tasks()
          .filter((task) => task.company_id === ctx.company.id)
          .sort((a, b) => b.created_at.localeCompare(a.created_at))
          .map(enrichTask),
      () => [],
    ),
  ),
  http.post(
    '/api/tasks',
    recruiterMutation(async (ctx, { request }) => {
      const body = await readJson<S['RegularTaskCreate']>(request)
      const fields: Record<string, string> = {}
      if (!body.title || body.title.trim().length < 3) fields.title = 'Название — не короче 3 символов'
      if (!body.statement || body.statement.trim().length < 10) fields.statement = 'Условие — не короче 10 символов'
      const days = body.deadline_days ?? 7
      if (!Number.isInteger(days) || days < 1 || days > 30) fields.deadline_days = 'Срок — от 1 до 30 дней'
      if (Object.keys(fields).length) return validationError(fields)
      if (!body.category || !t.categories().some((c) => c.id === body.category)) {
        return apiError(422, 'unknown_category', 'Неизвестная категория.', { fields: { category: 'Выберите категорию' } })
      }
      const now = db.now()
      const task: TaskRow = {
        id: db.nextId('regular_tasks'),
        company_id: ctx.company.id,
        company_name: ctx.company.name,
        recruiter_id: ctx.recruiter.id,
        title: body.title!.trim(),
        statement: body.statement!.trim(),
        category: body.category,
        category_label: categoryLabel(body.category),
        deadline_days: days,
        status: 'active',
        submissions_count: 0,
        created_at: now,
      }
      t.tasks().push(task)
      // Очередь раздачи: задание сразу получают до 5 кандидатов категории без активного задания.
      const busy = new Set(t.submissions().filter((s) => s.status === 'assigned').map((s) => s.candidate_id))
      for (const c of categoryCandidates(task.category).filter((c) => !busy.has(c.id)).slice(0, 5)) {
        t.submissions().push({
          id: db.nextId('task_submissions'),
          task_id: task.id,
          candidate_id: c.id,
          task_title: task.title,
          statement: task.statement,
          company_name: task.company_name,
          status: 'assigned',
          assigned_at: now,
          due_at: addDays(now, days),
          answer_kind: null,
          answer_text: null,
          submitted_at: null,
          score: null,
          grader_comment: null,
          graded_at: null,
        })
      }
      db.save()
      return HttpResponse.json(enrichTask(task), { status: 201 })
    }),
  ),
  http.get(
    '/api/tasks/:task_id/submissions',
    recruiterGet(
      (ctx, { params }) => {
        const task = t.tasks().find((x) => x.id === idParam(params.task_id) && x.company_id === ctx.company.id)
        if (!task) return notFound('Задание не найдено')
        const order: Record<string, number> = { submitted: 0, graded: 1, assigned: 2, expired: 3 }
        return t
          .submissions()
          .filter((s) => s.task_id === task.id)
          .sort((a, b) => order[a.status] - order[b.status] || b.assigned_at.localeCompare(a.assigned_at))
          .map(enrichSubmission)
      },
      () => [],
    ),
  ),
  http.post(
    '/api/tasks/submissions/:submission_id/grade',
    recruiterMutation(async (ctx, { params, request }) => {
      const s = t.submissions().find((x) => x.id === idParam(params.submission_id))
      const task = s && t.tasks().find((x) => x.id === s.task_id)
      if (!s || !task || task.company_id !== ctx.company.id) return notFound('Ответ не найден')
      if (s.status !== 'submitted' && s.status !== 'graded') {
        return apiError(409, 'invalid_transition', 'Оценить можно только присланный ответ.', { status: s.status })
      }
      const body = await readJson<S['SubmissionGrade']>(request)
      if (typeof body.score !== 'number' || !Number.isInteger(body.score) || body.score < 0 || body.score > 3) {
        return validationError({ score: 'Оценка — целое число от 0 до 3' })
      }
      if (body.comment && body.comment.length > 1000) return validationError({ comment: 'Комментарий — до 1000 символов' })
      const firstGrade = s.status === 'submitted'
      s.score = body.score
      s.grader_comment = body.comment?.trim() || null
      s.graded_at = db.now()
      s.status = 'graded'
      // Оценённое задание освежает профиль (T9.3) — видно в «почему в подборке».
      const c = t.candidates().find((x) => x.id === s.candidate_id)
      if (c && firstGrade) c.freshness = round2(Math.min(1, c.freshness + 0.04 + 0.03 * body.score))
      db.save()
      return HttpResponse.json(enrichSubmission(s))
    }),
  ),
]
