import { http, HttpResponse, type HttpHandler, type HttpResponseResolver } from 'msw'
import type { components } from '@/shared/api/schema'
import { db, demoUser } from '../db'
import { apiError, mockLatency, withScenario } from '../utils'

/**
 * Моки API кабинета соискателя (трек 1a). Пути и ответы — по docs/api/openapi.json.
 *
 * - Данные — общая база моков (db.data), мутации сохраняются db.save(): рекрутер после
 *   переключения роли видит, что кандидат принял/отклонил приглашение, откликнулся, ответил.
 * - Общие для ролей пути (/api/invitations, /api/vacancies, /api/applications…) обрабатываются
 *   только для роли candidate, иначе хендлер возвращает undefined и запрос уходит хендлеру роли.
 * - Тест: упрощённая адаптивность на вариантах из items.json (preview_variants): следующая
 *   задача — самая информативная для текущей θ (2PL, информация Фишера, случайно из топ-3),
 *   θ и SE пересчитываются EAP по сетке, стоп — 12–15 задач (SE < 0,35 после 12-й).
 *   Внутреннее состояние сессии лежит в поле `_mock` записи test_sessions и наружу не отдаётся.
 */

type S = components['schemas']
type Grade = S['GradeCode']
type Spec = S['SpecializationCode']

// --- Типы строк общей базы (поля как в data/seed, плюс служебные «_…» прототипа) ---------
type CandidateRow = S['CandidateProfile'] & {
  _fsp_linked_at?: string | null
  _fsp_synced_at?: string | null
  _fsp_backup?: { fsp_id: string; fsp_score: number | null; fsp_badges: S['FspBadge'][] } | null
}
type InvitationRow = Omit<S['Invitation'], 'candidate' | 'candidate_contacts' | 'recruiter_contacts' | 'decline_reason_label'>
type EventRow = S['InvitationEvent']
type VacancyRow = S['Vacancy']
type ApplicationRow = Omit<S['Application'], 'candidate' | 'candidate_contacts'>
type SubmissionRow = S['TaskSubmission']
type GradeHistoryRow = S['GradeHistoryEntry']
type ConsentRow = S['Consent']
type AchievementRow = S['FspAchievement']

interface RecruiterRow {
  id: number
  user_id: number
  company_id: number
  full_name: string
  position: string
  email: string
  phone: string | null
  telegram: string | null
}

interface VariantRow {
  instance_id: string
  format: S['ItemFormat']
  topic: string
  topic_label: string
  prompt: string
  code: string | null
  options: S['ChoiceOption'][] | null
  steps: S['ChoiceOption'][] | null
  unit: string | null
  time_limit_sec: number
  seed: number
  correct_answer: S['AnswerPayload']
}

interface ItemRow {
  id: number
  specialization: Spec
  topic: string
  topic_label: string
  target_grade: Grade
  format: S['ItemFormat']
  a: number
  b: number
  status: string
  preview_variants: VariantRow[]
}

interface MockAnswer {
  instance_id: string
  item_id: number
  topic: string
  topic_label: string
  a: number
  b: number
  correct: boolean
  time_expired: boolean
}

interface MockSessionState {
  prior: number
  current: { instance_id: string; item_id: number; started_at: string } | null
  answers: MockAnswer[]
}

type SessionRow = S['TestSession'] & { _mock?: MockSessionState }

const T = {
  candidates: () => db.data.candidates as unknown as CandidateRow[],
  invitations: () => db.data.invitations as unknown as InvitationRow[],
  events: () => db.data.invitation_events as unknown as EventRow[],
  recruiters: () => db.data.recruiters as unknown as RecruiterRow[],
  vacancies: () => db.data.vacancies as unknown as VacancyRow[],
  applications: () => db.data.applications as unknown as ApplicationRow[],
  submissions: () => db.data.task_submissions as unknown as SubmissionRow[],
  sessions: () => db.data.test_sessions as unknown as SessionRow[],
  history: () => db.data.grade_history as unknown as GradeHistoryRow[],
  consents: () => db.data.consents as unknown as ConsentRow[],
  achievements: () => db.data.fsp_achievements as unknown as AchievementRow[],
  items: () => db.data.items as unknown as ItemRow[],
  audit: () => db.data.audit_log as unknown as Array<Record<string, unknown>>,
  reports: () => db.data.reports as unknown as S['Report'][],
}

const DEMO_CANDIDATE_USER_ID = 1
const GRADES: Grade[] = ['intern', 'junior', 'middle', 'senior']
const GRADE_LABELS: Record<Grade, string> = { intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior' }
const SPEC_LABELS: Record<Spec, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  mobile: 'Mobile',
  data_ml: 'Data Science / ML',
  qa: 'QA',
  devops: 'DevOps',
}
const DAY = 24 * 60 * 60 * 1000
const MIN_ITEMS = 12
const MAX_ITEMS = 15
const SE_STOP = 0.35
/** Запас на сеть: ответ позже лимита на столько секунд ещё засчитывается. */
const TIME_GRACE_SEC = 5

function settings() {
  const s = db.data.platform_settings[0]
  return {
    changeCooldownDays: s?.grade_change_cooldown_days ?? 90,
    retryCooldownDays: s?.retry_cooldown_days ?? 30,
    consentVersion: s?.consent_version ?? '2026-10-01',
    thresholds: (spec: Spec) => {
      const t = s?.grade_thresholds.find((x) => x.specialization === spec)
      return { junior: t?.junior_from ?? -1, middle: t?.middle_from ?? 0, senior: t?.senior_from ?? 1 }
    },
  }
}

function categoryLabel(spec: Spec, grade: Grade) {
  return `${SPEC_LABELS[spec]} · ${GRADE_LABELS[grade]}`
}

function gradeByTheta(spec: Spec, theta: number): Grade {
  const t = settings().thresholds(spec)
  if (theta >= t.senior) return 'senior'
  if (theta >= t.middle) return 'middle'
  if (theta >= t.junior) return 'junior'
  return 'intern'
}

function lowerBound(spec: Spec, grade: Grade): number {
  const t = settings().thresholds(spec)
  return grade === 'intern' ? -Infinity : t[grade]
}

const round2 = (x: number) => Math.round(x * 100) / 100
const addDays = (iso: string, days: number) => new Date(new Date(iso).getTime() + days * DAY).toISOString()
const isFuture = (iso: string | null | undefined) => !!iso && new Date(iso).getTime() > Date.now()
const latest = <T>(rows: T[], key: (r: T) => string) =>
  [...rows].sort((a, b) => key(b).localeCompare(key(a)))

/** Убрать служебные поля прототипа («_…») из ответа. */
function publicView<T extends object>(row: T): T {
  return Object.fromEntries(Object.entries(row).filter(([k]) => !k.startsWith('_'))) as T
}

async function readJson<T>(request: Request): Promise<Partial<T>> {
  try {
    return ((await request.json()) ?? {}) as Partial<T>
  } catch {
    return {}
  }
}

// --- Кто делает запрос --------------------------------------------------------------------
function isCandidate(request: Request) {
  return demoUser(request).role === 'candidate'
}

function currentCandidate(request: Request): CandidateRow | undefined {
  const userId = demoUser(request).userId ?? DEMO_CANDIDATE_USER_ID
  return T.candidates().find((c) => c.user_id === userId)
}

const notFound = (what = 'Объект не найден') => apiError(404, 'not_found', what)
const noProfile = () => apiError(404, 'not_found', 'Профиль кандидата не найден')

/** Хендлер только для соискателя: другие роли проходят дальше (undefined). */
function forCandidate(resolver: HttpResponseResolver): HttpResponseResolver {
  return (info) => {
    if (!isCandidate(info.request)) return undefined
    return resolver(info)
  }
}

/** GET для соискателя с режимом данных демо-плашки. */
function candidateGet<T>(
  data: (candidate: CandidateRow, info: Parameters<HttpResponseResolver>[0]) => T | Response,
  empty?: (candidate: CandidateRow) => T,
): HttpResponseResolver {
  return forCandidate(async (info) => {
    const candidate = currentCandidate(info.request)
    if (!candidate) {
      await mockLatency()
      return noProfile()
    }
    const result = data(candidate, info)
    if (result instanceof Response) {
      await mockLatency()
      return result
    }
    return withScenario({ data: () => result, empty: empty ? () => empty(candidate) : undefined })(info)
  })
}

/** Мутация соискателя: задержка сети, профиль обязателен. */
function candidateMutation(
  handle: (candidate: CandidateRow, info: Parameters<HttpResponseResolver>[0]) => Promise<Response> | Response,
): HttpResponseResolver {
  return forCandidate(async (info) => {
    await mockLatency()
    const candidate = currentCandidate(info.request)
    if (!candidate) return noProfile()
    return handle(candidate, info)
  })
}

function audit(entry: { actor_user_id: number | null; actor_role: string | null; action: string; target_type: string; target_id: number | null; summary: string; details?: Record<string, unknown> }) {
  T.audit().push({ id: db.nextId('audit_log'), at: db.now(), details: {}, ...entry })
}

// --- Профиль ----------------------------------------------------------------------------
function completeness(c: CandidateRow): number {
  const checks = [
    c.full_name?.trim().length >= 2,
    !!(c.phone || c.telegram),
    !!c.city,
    c.work_formats.length > 0,
    c.stack.length >= 3,
    c.experience_years > 0,
    (c.roles_in_team ?? []).length > 0,
    (c.soft_skills ?? []).length > 0,
    (c.about ?? '').trim().length >= 20,
    (c.links ?? []).length > 0,
    typeof c.min_salary === 'number' && c.min_salary > 0,
  ]
  return Math.round((checks.filter(Boolean).length / checks.length) * 100)
}

function profileView(c: CandidateRow): S['CandidateProfile'] {
  return { ...publicView(c), profile_completeness: completeness(c) }
}

const MAX_RESUME_BYTES = 5 * 1024 * 1024

function resumeFields(c: CandidateRow): S['ResumeParseResult']['fields'] {
  // Прототип: «распознанное» резюме — данные профиля плюс пара правдоподобных отличий.
  return {
    full_name: { value: c.full_name, confidence: 0.96 },
    email: { value: c.email, confidence: 0.99 },
    phone: { value: c.phone ?? '+7 900 123-45-67', confidence: 0.9 },
    telegram: { value: c.telegram ?? null, confidence: 0.7 },
    city: { value: c.city ?? 'Казань', confidence: 0.82 },
    stack: { value: c.stack.length ? c.stack : ['python', 'postgresql', 'docker'], confidence: 0.81 },
    experience_years: { value: c.experience_years || 2, confidence: 0.68 },
    roles_in_team: { value: c.roles_in_team?.length ? c.roles_in_team : ['Разработчик'], confidence: 0.55 },
    soft_skills: { value: c.soft_skills?.length ? c.soft_skills : ['Коммуникация'], confidence: 0.48 },
    about: { value: c.about || 'Разрабатываю серверную часть веб-сервисов.', confidence: 0.6 },
    links: { value: (c.links ?? []).map((l) => l.url), confidence: 0.9 },
  }
}

/** Минимальный PDF (латиница): настоящий стандартизированный профиль генерирует бэкенд. */
function buildPdf(lines: string[]): Uint8Array {
  const esc = (s: string) => s.replace(/[\\()]/g, (m) => `\\${m}`)
  const content =
    'BT /F1 20 Tf 56 780 Td (' + esc(lines[0] ?? '') + ') Tj /F1 12 Tf ' +
    lines.slice(1).map((l) => `0 -22 Td (${esc(l)}) Tj`).join(' ') + ' ET'
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>',
    `<< /Length ${content.length} >>\nstream\n${content}\nendstream`,
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
  ]
  let out = '%PDF-1.4\n'
  const offsets: number[] = []
  objects.forEach((obj, i) => {
    offsets.push(out.length)
    out += `${i + 1} 0 obj\n${obj}\nendobj\n`
  })
  const xref = out.length
  out += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`
  out += offsets.map((o) => `${String(o).padStart(10, '0')} 00000 n \n`).join('')
  out += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF`
  return new TextEncoder().encode(out)
}

const TRANSLIT: Record<string, string> = {
  а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm',
  н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'kh', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch',
  ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya', '·': '-', '«': '"', '»': '"', '—': '-', '–': '-',
}
function translit(s: string): string {
  return [...s]
    .map((ch) => {
      const low = ch.toLowerCase()
      const t = TRANSLIT[low]
      if (t === undefined) return /[\x20-\x7e]/.test(ch) ? ch : ''
      return ch === low ? t : t.charAt(0).toUpperCase() + t.slice(1)
    })
    .join('')
}

// --- ФСП --------------------------------------------------------------------------------
const LEVEL_WEIGHT: Record<S['FspLevel'], number> = { regional: 1, national: 2, international: 3 }

function computeFsp(fspId: string): { score: number | null; badges: S['FspBadge'][] } {
  const list = T.achievements().filter((a) => a.fsp_id === fspId)
  if (!list.length) return { score: null, badges: [] }
  const now = Date.now()
  let score = 0
  for (const a of list) {
    const place = a.place == null ? 0.4 : a.place <= 3 ? 1 : a.place <= 10 ? 0.7 : 0.5
    const ageYears = (now - new Date(a.date).getTime()) / (365 * DAY)
    const fresh = ageYears < 1 ? 1 : ageYears < 2 ? 0.8 : 0.6
    score += LEVEL_WEIGHT[a.level] * place * fresh * 10
  }
  const badges: S['FspBadge'][] = []
  const prize = list.find((a) => a.place != null && a.place <= 3 && a.level !== 'regional')
  if (prize) {
    badges.push({
      id: 'prize_national',
      title: prize.level === 'international' ? 'Призёр международного соревнования' : 'Призёр всероссийского соревнования',
      level: prize.level,
      verified: true,
    })
  }
  const n = list.length
  const word = n % 10 === 1 && n % 100 !== 11 ? 'соревнования' : 'соревнований'
  badges.push({ id: 'participant_many', title: `Участник ${n} ${word} ФСП`, level: null, verified: true })
  return { score: Math.min(100, round2(score)), badges }
}

function fspStatus(c: CandidateRow): S['FspStatus'] {
  if (!c.fsp_id) {
    return {
      linked: false,
      fsp_id: null,
      linked_at: null,
      last_sync_at: null,
      achievements_count: 0,
      fsp_score: null,
      badges: [],
      has_history: false,
      message: 'ФСП ID не привязан. Привяжите его, чтобы достижения появились в профиле с отметкой «подтверждено ФСП».',
    }
  }
  const count = T.achievements().filter((a) => a.fsp_id === c.fsp_id).length
  return {
    linked: true,
    fsp_id: c.fsp_id,
    linked_at: c._fsp_linked_at ?? c.created_at,
    last_sync_at: c._fsp_synced_at ?? c._fsp_linked_at ?? c.created_at,
    achievements_count: count,
    fsp_score: count ? (c.fsp_score ?? null) : null,
    badges: count ? (c.fsp_badges ?? []) : [],
    has_history: count > 0,
    message: count
      ? null
      : 'В реестре ФСП пока нет ваших соревнований. Это не снижает позицию в выдаче — просто нет бонуса за достижения.',
  }
}

// --- Приглашения ------------------------------------------------------------------------
function expireOverdue() {
  let changed = false
  for (const inv of T.invitations()) {
    if ((inv.status === 'sent' || inv.status === 'viewed') && !isFuture(inv.expires_at)) {
      inv.status = 'expired'
      T.events().push({ id: db.nextId('invitation_events'), invitation_id: inv.id, type: 'expired', at: inv.expires_at, actor_role: null })
      changed = true
    }
  }
  if (changed) db.save()
}

function declineLabel(reason: S['DeclineReason'] | null | undefined) {
  if (!reason) return null
  return db.data.decline_reasons.find((r) => r.id === reason)?.label ?? reason
}

function invitationView(inv: InvitationRow): S['Invitation'] {
  const recruiter = T.recruiters().find((r) => r.id === inv.recruiter_id)
  return {
    ...inv,
    candidate: null,
    candidate_contacts: null,
    recruiter_contacts:
      inv.status === 'accepted' && recruiter
        ? {
            full_name: recruiter.full_name,
            position: recruiter.position,
            email: recruiter.email,
            phone: recruiter.phone,
            telegram: recruiter.telegram,
          }
        : null,
    decline_reason_label: declineLabel(inv.decline_reason),
  }
}

function ownInvitation(c: CandidateRow, id: string | readonly string[] | undefined) {
  const n = Number(id)
  if (!Number.isInteger(n)) return undefined
  return T.invitations().find((i) => i.id === n && i.candidate_id === c.id)
}

function pushEvent(invitationId: number, type: S['InvitationEventType'], actor: S['Role'] | null) {
  T.events().push({ id: db.nextId('invitation_events'), invitation_id: invitationId, type, at: db.now(), actor_role: actor })
}

// --- Тест -------------------------------------------------------------------------------
const START_THETA: Record<Grade, number> = { intern: -1.5, junior: -0.5, middle: 0.5, senior: 1.5 }

function prob(theta: number, a: number, b: number) {
  return 1 / (1 + Math.exp(-a * (theta - b)))
}

/** EAP-оценка θ по сетке с нормальным априорным распределением. */
function estimate(answers: MockAnswer[], prior: number): { theta: number; se: number } {
  let sw = 0
  let st = 0
  let st2 = 0
  for (let t = -4; t <= 4.0001; t += 0.05) {
    let w = Math.exp(-0.5 * (t - prior) ** 2)
    for (const ans of answers) {
      const p = prob(t, ans.a, ans.b)
      w *= ans.correct ? p : 1 - p
    }
    sw += w
    st += w * t
    st2 += w * t * t
  }
  const theta = st / sw
  const se = Math.sqrt(Math.max(st2 / sw - theta * theta, 0))
  return { theta, se }
}

/** Пул вариантов: задачи специализации + по одной задаче недостающих форматов (для демо форматов). */
function poolFor(spec: Spec): Array<{ item: ItemRow; variant: VariantRow }> {
  const usable = T.items().filter((i) => i.status === 'active' || i.status === 'pilot')
  const own = usable.filter((i) => i.specialization === spec)
  const formats = new Set(own.map((i) => i.format))
  const extra: ItemRow[] = []
  for (const item of usable) {
    if (!formats.has(item.format)) {
      formats.add(item.format)
      extra.push(item)
    }
  }
  return [...own, ...extra].flatMap((item) => item.preview_variants.map((variant) => ({ item, variant })))
}

function findVariant(instanceId: string) {
  for (const item of T.items()) {
    const variant = item.preview_variants.find((v) => v.instance_id === instanceId)
    if (variant) return { item, variant }
  }
  return undefined
}

function pickNext(session: SessionRow, state: MockSessionState, theta: number) {
  const used = new Set(state.answers.map((a) => a.instance_id))
  const usedItems = new Set(state.answers.map((a) => a.item_id))
  const lastTopic = state.answers[state.answers.length - 1]?.topic
  const candidates = poolFor(session.specialization).filter(({ variant }) => !used.has(variant.instance_id))
  if (!candidates.length) return undefined
  const fresh = candidates.filter(({ item }) => !usedItems.has(item.id))
  const pool = fresh.length ? fresh : candidates
  const scored = pool
    .map((c) => {
      const p = prob(theta, c.item.a, c.item.b)
      let info = c.item.a ** 2 * p * (1 - p)
      if (c.item.topic === lastTopic) info *= 0.6 // баланс тем
      return { ...c, info }
    })
    .sort((x, y) => y.info - x.info)
  const top = scored.slice(0, 3)
  return top[Math.floor(Math.random() * top.length)]
}

function itemView(v: VariantRow): S['ItemView'] {
  return {
    instance_id: v.instance_id,
    format: v.format,
    topic: v.topic,
    topic_label: v.topic_label,
    prompt: v.prompt,
    code: v.code,
    options: v.options,
    steps: v.steps,
    unit: v.unit,
    time_limit_sec: v.time_limit_sec,
  }
}

function norm(s: string | null | undefined) {
  return (s ?? '').trim().toLowerCase().replace(/\s+/g, ' ').replace(/[«»"']/g, '')
}

function checkAnswer(v: VariantRow, ans: S['AnswerPayload']): boolean {
  const ok = v.correct_answer
  switch (v.format) {
    case 'single_choice':
    case 'multiple_choice': {
      const a = [...(ans.choice_ids ?? [])].sort().join(',')
      const b = [...(ok.choice_ids ?? [])].sort().join(',')
      return a.length > 0 && a === b
    }
    case 'numeric': {
      if (typeof ans.value !== 'number' || typeof ok.value !== 'number') return false
      return Math.abs(ans.value - ok.value) <= Math.max(1e-6, Math.abs(ok.value) * 0.01)
    }
    case 'short_text':
    case 'code_output':
      return norm(ans.text) !== '' && norm(ans.text) === norm(ok.text)
    case 'find_error_line':
      return ans.line === ok.line
    case 'ordering':
      return (ans.order ?? []).join(',') === (ok.order ?? []).join(',')
    default:
      return false
  }
}

function timeLeft(state: MockSessionState, v: VariantRow): number {
  if (!state.current) return v.time_limit_sec
  const spent = (Date.now() - new Date(state.current.started_at).getTime()) / 1000
  return Math.max(0, Math.round(v.time_limit_sec - spent))
}

function sessionState(session: SessionRow): S['TestSessionState'] {
  const state = session._mock
  const current = session.status === 'in_progress' && state?.current ? findVariant(state.current.instance_id) : undefined
  return {
    session: publicView(session),
    current_item: current ? itemView(current.variant) : null,
    item_number: current ? session.items_answered + 1 : session.items_answered,
    time_left_sec: current && state ? timeLeft(state, current.variant) : null,
  }
}

function topicScores(state: MockSessionState, theta: number, spec: Spec): S['TopicScore'][] {
  const byTopic = new Map<string, MockAnswer[]>()
  // Задачи других специализаций (добавлены ради демонстрации форматов) в разбор по темам не идут.
  const own = state.answers.filter((a) => T.items().find((i) => i.id === a.item_id)?.specialization === spec)
  for (const a of own.length ? own : state.answers) byTopic.set(a.topic, [...(byTopic.get(a.topic) ?? []), a])
  return [...byTopic.entries()].map(([topic, list]) => {
    const acc = list.filter((a) => a.correct).length / list.length
    const meanB = list.reduce((s, a) => s + a.b, 0) / list.length
    const score = round2(Math.min(1, Math.max(0, 0.65 * acc + 0.35 * prob(theta, 1.2, meanB))))
    const level: S['TopicLevel'] = score >= 0.65 ? 'strong' : score >= 0.4 ? 'ok' : 'weak'
    return { topic, label: list[0].topic_label, score, level }
  })
}

function addHistory(c: CandidateRow, entry: Omit<GradeHistoryRow, 'id' | 'candidate_id' | 'at'>) {
  T.history().push({ id: db.nextId('grade_history'), candidate_id: c.id, at: db.now(), ...entry })
}

/** Завершить сессию: θ, интервал, грейд по правилам (без принудительного понижения), история. */
function finishSession(session: SessionRow, c: CandidateRow) {
  const state = session._mock!
  const { theta, se } = estimate(state.answers, state.prior)
  const spec = session.specialization
  const target = session.target_grade
  const estimated = gradeByTheta(spec, theta)
  const passed = theta >= lowerBound(spec, target)
  const now = db.now()

  session.status = 'finished'
  session.finished_at = now
  session.theta = round2(theta)
  session.se = round2(se)
  session.ci_low = round2(theta - 1.96 * se)
  session.ci_high = round2(theta + 1.96 * se)
  session.passed = passed
  session.result_grade = passed ? target : estimated
  session.result_category = `${spec}:${session.result_grade}`
  session.topic_scores = topicScores(state, theta, spec)
  state.current = null

  // Профиль обновляется результатом, только если грейд подтверждён или категории ещё не было:
  // неудачная попытка не портит текущую категорию (принудительно не понижаем).
  if (passed || !c.grade) {
    c.theta = session.theta
    c.theta_se = session.se
    c.topic_scores = session.topic_scores
  }
  c.last_test_at = session.started_at

  addHistory(c, {
    event: passed ? 'test_passed' : 'test_failed',
    specialization: spec,
    grade_from: c.grade ?? null,
    grade_to: passed ? target : null,
    test_session_id: session.id,
    comment: passed
      ? `Подтверждён грейд ${GRADE_LABELS[target]}, θ = ${session.theta}`
      : `Грейд ${GRADE_LABELS[target]} не подтверждён, θ = ${session.theta}`,
  })

  if (passed && (c.grade !== target || c.specialization !== spec)) {
    const from = c.grade ?? null
    c.specialization = spec
    c.grade = target
    c.category = `${spec}:${target}`
    c.category_label = categoryLabel(spec, target)
    c.grade_changed_at = now
    addHistory(c, {
      event: 'grade_changed',
      specialization: spec,
      grade_from: from,
      grade_to: target,
      test_session_id: session.id,
      comment: `Присвоена категория ${c.category_label}`,
    })
    audit({
      actor_user_id: null,
      actor_role: null,
      action: 'grade_changed',
      target_type: 'candidate',
      target_id: c.id,
      summary: `Присвоена категория ${c.category_label}`,
      details: { grade_from: from, grade_to: target },
    })
  }

  const rec = recommendation(session, c)
  if (rec.action === 'offer_lower' || rec.action === 'offer_higher') {
    addHistory(c, {
      event: rec.action,
      specialization: spec,
      grade_from: c.grade ?? null,
      grade_to: rec.action === 'offer_lower' ? neighbour(target, -1) : neighbour(target, 1),
      test_session_id: session.id,
      comment: rec.message,
    })
  }
}

function neighbour(grade: Grade, step: number): Grade | null {
  return GRADES[GRADES.indexOf(grade) + step] ?? null
}

/** Когда снова можно сменить грейд (кулдаун 90 дней от последней смены). */
function changeAvailableAt(c: CandidateRow): string | null {
  if (!c.grade_changed_at) return null
  const at = addDays(c.grade_changed_at, settings().changeCooldownDays)
  return isFuture(at) ? at : null
}

/** Когда можно повторить неудачную попытку на этот грейд (30 дней). */
function retryAvailableAt(c: CandidateRow, spec: Spec, grade: Grade): string | null {
  const failed = latest(
    T.sessions().filter(
      (s) => s.candidate_id === c.id && s.specialization === spec && s.target_grade === grade && s.status === 'finished' && s.passed === false,
    ),
    (s) => s.finished_at ?? s.started_at,
  )[0]
  if (!failed) return null
  const at = addDays(failed.finished_at ?? failed.started_at, settings().retryCooldownDays)
  return isFuture(at) ? at : null
}

function maxDate(...dates: Array<string | null>): string | null {
  const list = dates.filter((d): d is string => !!d)
  return list.length ? list.sort().at(-1)! : null
}

function recommendation(session: SessionRow, c: CandidateRow): S['Recommendation'] {
  const spec = session.specialization
  const target = session.target_grade
  if (session.passed) {
    const higher = neighbour(target, 1)
    const t = settings().thresholds(spec)
    const nextBound = higher ? t[higher as Exclude<Grade, 'intern'>] : Infinity
    if (higher && (session.ci_low ?? -Infinity) > nextBound - 0.7 && (session.theta ?? 0) > nextBound - 0.3) {
      const at = maxDate(changeAvailableAt(c), retryAvailableAt(c, spec, higher))
      return {
        action: 'offer_higher',
        message: at
          ? `Уверенный результат. Тест на ${GRADE_LABELS[higher]} станет доступен после кулдауна смены грейда.`
          : `Уверенный результат — можно пройти тест на ${GRADE_LABELS[higher]}.`,
        available_at: at,
      }
    }
    return { action: 'stay', message: `Грейд ${GRADE_LABELS[target]} подтверждён.`, available_at: null }
  }
  const lower = neighbour(target, -1)
  if (!lower) {
    const at = retryAvailableAt(c, spec, target)
    return {
      action: 'retry_later',
      message: 'Результат ниже порога стажёра. Подтянуть темы и пройти тест снова можно через 30 дней.',
      available_at: at,
    }
  }
  const at = c.grade ? changeAvailableAt(c) : null
  if (c.grade && c.category_label) {
    return {
      action: 'offer_lower',
      message: `Грейд ${GRADE_LABELS[target]} не подтверждён. Текущая категория «${c.category_label}» сохраняется — принудительно не понижаем.`,
      available_at: at,
    }
  }
  return {
    action: 'offer_lower',
    message: `Грейд ${GRADE_LABELS[target]} не подтверждён. Уровень соответствует ${GRADE_LABELS[gradeByTheta(spec, session.theta ?? 0)]} — пройдите тест на ${GRADE_LABELS[lower]}, чтобы получить категорию. Принудительно грейд не понижаем.`,
    available_at: at,
  }
}

function testResult(session: SessionRow, c: CandidateRow): S['TestResult'] {
  const scores = session.topic_scores ?? []
  const resultGrade = session.result_grade ?? session.target_grade
  return {
    session_id: session.id,
    specialization: session.specialization,
    target_grade: session.target_grade,
    result_grade: resultGrade,
    category: `${session.specialization}:${resultGrade}`,
    category_label: categoryLabel(session.specialization, resultGrade),
    theta: session.theta ?? 0,
    se: session.se ?? 0,
    ci_low: session.ci_low ?? 0,
    ci_high: session.ci_high ?? 0,
    passed: !!session.passed,
    items_answered: session.items_answered,
    finished_at: session.finished_at ?? session.started_at,
    topic_scores: scores,
    strong_topics: scores.filter((s) => s.level === 'strong').map((s) => s.label),
    weak_topics: scores.filter((s) => s.level === 'weak').map((s) => s.label),
    recommendation: recommendation(session, c),
  }
}

function gradeStatus(c: CandidateRow): S['GradeStatus'] {
  const spec = c.specialization ?? null
  const grade = c.grade ?? null
  const change = changeAvailableAt(c)
  const lower = grade ? neighbour(grade, -1) : null
  const higher = grade ? neighbour(grade, 1) : null
  const lowerAt = spec && lower ? maxDate(change, retryAvailableAt(c, spec, lower)) : null
  const higherAt = spec && higher ? maxDate(change, retryAvailableAt(c, spec, higher)) : null
  return {
    candidate_id: c.id,
    specialization: spec,
    grade,
    category: c.category ?? null,
    category_label: c.category_label ?? null,
    theta: c.theta ?? null,
    grade_changed_at: c.grade_changed_at ?? null,
    grade_change_cooldown_days: settings().changeCooldownDays,
    retry_cooldown_days: settings().retryCooldownDays,
    can_test_lower: !!lower && !lowerAt,
    lower_available_at: lower ? lowerAt : null,
    can_test_higher: !!higher && !higherAt,
    higher_available_at: higher ? higherAt : null,
    history: latest(T.history().filter((h) => h.candidate_id === c.id), (h) => `${h.at}#${String(h.id).padStart(6, '0')}`),
    tests: latest(T.sessions().filter((s) => s.candidate_id === c.id), (s) => s.started_at).map((s) => publicView(s)),
  }
}

// --- Опрос ------------------------------------------------------------------------------
function surveyResult(answers: S['SurveyAnswer'][]): S['SurveyResult'] {
  const options = new Map(
    db.data.survey_questions.flatMap((q) => (q.options ?? []).map((o) => [o.id, o as S['SurveyOption']] as const)),
  )
  const votes = new Map<Spec, number>()
  for (const a of answers) {
    for (const id of a.option_ids ?? []) {
      for (const spec of options.get(id)?.specializations ?? []) votes.set(spec, (votes.get(spec) ?? 0) + 1)
    }
  }
  if (!votes.size) votes.set('backend', 1)
  const total = [...votes.values()].reduce((s, n) => s + n, 0)
  const ranked = [...votes.entries()].sort((x, y) => y[1] - x[1])
  const best = ranked[0][0]
  const chosen = new Set(answers.flatMap((a) => a.option_ids ?? []))
  const grade: Grade = chosen.has('q4_5') ? 'senior' : chosen.has('q4_3') ? 'middle' : chosen.has('q4_1') ? 'junior' : 'intern'
  const experience: Record<Grade, string> = {
    intern: 'опыта пока нет',
    junior: 'опыт до 2 лет',
    middle: 'опыт 2–5 лет',
    senior: 'опыт больше 5 лет',
  }
  return {
    recommended_specialization: best,
    alternatives: ranked.slice(0, 3).map(([specialization, n]) => ({ specialization, score: round2(n / total) })),
    suggested_grade: grade,
    topics: db.data.topics.filter((t) => t.specialization === best).map((t) => t.id).slice(0, 6),
    explanation: [
      `${ranked[0][1]} из ${total} ответов указывают на ${SPEC_LABELS[best]}`,
      `Вы указали, что ${experience[grade]}, — предлагаем начать с грейда ${GRADE_LABELS[grade]}`,
      'Опрос не оценивается баллом: специализацию и грейд можно поменять',
    ],
  }
}

// ============================================================================================
export const candidateHandlers: HttpHandler[] = [
  // --- Главная ---
  http.get(
    '/api/candidates/me/dashboard',
    candidateGet(
      (c) => {
        expireOverdue()
        const invitations = latest(T.invitations().filter((i) => i.candidate_id === c.id), (i) => i.created_at)
        const active = latest(T.submissions().filter((s) => s.candidate_id === c.id && s.status === 'assigned'), (s) => s.assigned_at)[0]
        const hints: string[] = []
        if (!c.fsp_id) hints.push('Привяжите ФСП ID — достижения появятся в профиле с отметкой «подтверждено ФСП»')
        if (!c.links?.length) hints.push('Добавьте ссылку на GitHub — профиль станет полнее')
        if (!c.grade) hints.push('Пройдите тест, чтобы получить категорию и попасть в выдачу работодателям')
        if (!c.publication_consent) hints.push('Дайте согласие на публикацию профиля — без него работодатели вас не видят')
        if (c.job_search_paused) hints.push('Поиск на паузе: работодатели не видят ваш профиль')
        const dashboard: S['CandidateDashboard'] = {
          full_name: c.full_name,
          category: c.category ?? null,
          category_label: c.category_label ?? null,
          grade: c.grade ?? null,
          theta: c.theta ?? null,
          onboarding_completed: !!c.grade,
          new_invitations_count: invitations.filter((i) => i.status === 'sent').length,
          recent_invitations: invitations.slice(0, 3).map((i) => ({
            id: i.id,
            company_name: i.company_name,
            salary_from: i.salary_from,
            salary_to: i.salary_to,
            status: i.status,
            created_at: i.created_at,
          })),
          active_task: active ? { submission_id: active.id, title: active.task_title, due_at: active.due_at } : null,
          profile_completeness: completeness(c),
          fsp_linked: !!c.fsp_id,
          hints,
        }
        return dashboard
      },
      (c) => ({
        full_name: c.full_name,
        category: null,
        category_label: null,
        grade: null,
        theta: null,
        onboarding_completed: false,
        new_invitations_count: 0,
        recent_invitations: [],
        active_task: null,
        profile_completeness: 20,
        fsp_linked: false,
        hints: ['Пройдите тест, чтобы получить категорию и попасть в выдачу работодателям'],
      }),
    ),
  ),

  // --- Профиль ---
  http.get('/api/candidates/me/profile', candidateGet((c) => profileView(c))),

  http.put(
    '/api/candidates/me/profile',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['CandidateProfileUpdate']>(request)
      const fields: Record<string, string> = {}
      if (!body.full_name || body.full_name.trim().length < 2) fields.full_name = 'Укажите имя и фамилию'
      if (!body.work_formats?.length) fields.work_formats = 'Выберите хотя бы один формат работы'
      if (typeof body.experience_years !== 'number' || body.experience_years < 0 || body.experience_years > 50) {
        fields.experience_years = 'Стаж — от 0 до 50 лет'
      }
      if (body.min_salary != null && (body.min_salary < 0 || body.min_salary > 10_000_000)) {
        fields.min_salary = 'Проверьте сумму'
      }
      if (Object.keys(fields).length) return apiError(422, 'validation_error', 'Проверьте поля формы', { fields })
      Object.assign(c, {
        full_name: body.full_name!.trim(),
        phone: body.phone ?? null,
        telegram: body.telegram ?? null,
        city: body.city ?? null,
        work_formats: body.work_formats,
        stack: body.stack ?? c.stack,
        roles_in_team: body.roles_in_team ?? [],
        experience_years: body.experience_years,
        soft_skills: body.soft_skills ?? [],
        about: body.about ?? '',
        links: body.links ?? [],
        min_salary: body.min_salary ?? null,
      })
      c.profile_completeness = completeness(c)
      db.save()
      return HttpResponse.json(profileView(c))
    }),
  ),

  http.post(
    '/api/candidates/me/resume',
    candidateMutation(async (c, { request }) => {
      let file: File | null
      try {
        const value = (await request.formData()).get('file')
        file = value instanceof File ? value : null
      } catch {
        file = null
      }
      if (!file) return apiError(422, 'validation_error', 'Прикрепите файл', { fields: { file: 'Прикрепите PDF' } })
      const isPdf = file.type === 'application/pdf' || file.type === 'application/x-pdf' || /\.pdf$/i.test(file.name)
      if (!isPdf) return apiError(415, 'unsupported_file', 'Нужен PDF', { content_type: file.type })
      if (file.size > MAX_RESUME_BYTES) return apiError(413, 'file_too_large', 'Файл больше 5 МБ')
      const result: S['ResumeParseResult'] = {
        resume_id: Date.now() % 100000,
        filename: file.name || 'resume.pdf',
        parser: 'rules',
        fields: resumeFields(c),
        unmatched_skills: ['Celery'],
      }
      return HttpResponse.json(result)
    }),
  ),

  http.get(
    '/api/candidates/me/profile.pdf',
    forCandidate(async ({ request }) => {
      await mockLatency()
      const c = currentCandidate(request)
      if (!c) return noProfile()
      const lines = [
        'FSP Talenty - candidate profile',
        translit(`${c.full_name}`),
        translit(c.category_label ?? 'Kategoriya ne opredelena'),
        `Theta: ${c.theta ?? '-'}   SE: ${c.theta_se ?? '-'}`,
        `Stack: ${c.stack.join(', ')}`,
        `FSP: ${c.fsp_id ? `${c.fsp_id} (verified by FSP)` : 'no FSP history'}`,
        '',
        'Prototype on mocks: the standard PDF profile is generated by the backend.',
      ]
      return new HttpResponse(buildPdf(lines), {
        headers: { 'Content-Type': 'application/pdf', 'Content-Disposition': 'attachment; filename="fsp-profile.pdf"' },
      })
    }),
  ),

  // --- Настройки и согласия ---
  http.get(
    '/api/candidates/me/settings',
    candidateGet((c) => {
      const s: S['CandidateSettings'] = {
        privacy: c.privacy,
        job_search_paused: !!c.job_search_paused,
        publication_consent: c.publication_consent,
        fsp_linked: !!c.fsp_id,
        fsp_id: c.fsp_id ?? null,
      }
      return s
    }),
  ),

  http.put(
    '/api/candidates/me/settings/privacy',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['PrivacySettings']>(request)
      c.privacy = {
        show_city: body.show_city ?? c.privacy.show_city,
        show_experience: body.show_experience ?? c.privacy.show_experience,
        show_links: body.show_links ?? c.privacy.show_links,
        show_fsp_achievements: body.show_fsp_achievements ?? c.privacy.show_fsp_achievements,
      }
      db.save()
      return HttpResponse.json({ privacy: c.privacy, job_search_paused: !!c.job_search_paused, publication_consent: c.publication_consent, fsp_linked: !!c.fsp_id, fsp_id: c.fsp_id ?? null } satisfies S['CandidateSettings'])
    }),
  ),

  http.put(
    '/api/candidates/me/settings/job-search',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['JobSearchUpdate']>(request)
      if (typeof body.paused !== 'boolean') return apiError(422, 'validation_error', 'Поле paused обязательно')
      c.job_search_paused = body.paused
      db.save()
      return HttpResponse.json({ privacy: c.privacy, job_search_paused: c.job_search_paused, publication_consent: c.publication_consent, fsp_linked: !!c.fsp_id, fsp_id: c.fsp_id ?? null } satisfies S['CandidateSettings'])
    }),
  ),

  http.get(
    '/api/users/me/consents',
    candidateGet((c) => T.consents().filter((x) => x.user_id === c.user_id)),
  ),

  http.put(
    '/api/users/me/consents/:consentType',
    candidateMutation(async (c, { request, params }) => {
      const type = params.consentType
      if (type !== 'processing' && type !== 'publication') return notFound('Неизвестный тип согласия')
      const body = await readJson<S['ConsentUpdate']>(request)
      if (typeof body.granted !== 'boolean') return apiError(422, 'validation_error', 'Поле granted обязательно')
      if (type === 'processing' && !body.granted) {
        return apiError(
          409,
          'consent_required',
          'Без согласия на обработку данных пользоваться сервисом нельзя. Чтобы отозвать его, удалите аккаунт через поддержку.',
        )
      }
      const now = db.now()
      let consent = T.consents().find((x) => x.user_id === c.user_id && x.type === type)
      if (!consent) {
        consent = { id: db.nextId('consents'), user_id: c.user_id, type, version: settings().consentVersion, granted: false, granted_at: null, revoked_at: null }
        T.consents().push(consent)
      }
      consent.granted = body.granted
      consent.version = body.version || settings().consentVersion
      if (body.granted) {
        consent.granted_at = now
        consent.revoked_at = null
      } else {
        consent.revoked_at = now
      }
      if (type === 'publication') {
        c.publication_consent = body.granted
        if (!body.granted) {
          audit({ actor_user_id: c.user_id, actor_role: 'candidate', action: 'consent_revoked', target_type: 'consent', target_id: consent.id, summary: 'Отозвано согласие на публикацию профиля', details: { type } })
        }
      }
      db.save()
      return HttpResponse.json(consent)
    }),
  ),

  // --- ФСП ID ---
  http.post(
    '/api/auth/fsp-link',
    candidateMutation(async (c, { request }) => {
      const { code = '' } = await readJson<S['FspCodeExchange']>(request)
      if (!code.startsWith('mock:')) return apiError(400, 'oidc_error', 'Ошибка обмена кода авторизации')
      const fspId = code.slice('mock:'.length)
      if (!/^FSP-\d{6}$/.test(fspId)) return apiError(400, 'oidc_error', 'Ошибка обмена кода авторизации')
      if (T.candidates().some((x) => x.id !== c.id && x.fsp_id === fspId)) {
        return apiError(409, 'fsp_id_taken', 'Этот ФСП ID уже привязан к другому профилю')
      }
      const now = db.now()
      if (c._fsp_backup?.fsp_id === fspId) {
        c.fsp_score = c._fsp_backup.fsp_score
        c.fsp_badges = c._fsp_backup.fsp_badges
      } else {
        const fsp = computeFsp(fspId)
        c.fsp_score = fsp.score
        c.fsp_badges = fsp.badges
      }
      c.fsp_id = fspId
      c._fsp_linked_at = now
      c._fsp_synced_at = now
      db.save()
      return HttpResponse.json(fspStatus(c))
    }),
  ),

  http.delete(
    '/api/auth/fsp-link',
    candidateMutation((c) => {
      if (!c.fsp_id) return apiError(409, 'fsp_not_linked', 'ФСП ID не привязан')
      c._fsp_backup = { fsp_id: c.fsp_id, fsp_score: c.fsp_score ?? null, fsp_badges: c.fsp_badges ?? [] }
      c.fsp_id = null
      c.fsp_score = null
      c.fsp_badges = []
      c._fsp_linked_at = null
      c._fsp_synced_at = null
      db.save()
      return HttpResponse.json(fspStatus(c))
    }),
  ),

  http.get(
    '/api/fsp/status',
    candidateGet(
      (c) => fspStatus(c),
      (c) => ({ ...fspStatus({ ...c, fsp_id: null }) }),
    ),
  ),

  http.get(
    '/api/fsp/achievements',
    candidateGet(
      (c) => (c.fsp_id ? latest(T.achievements().filter((a) => a.fsp_id === c.fsp_id), (a) => a.date) : []),
      () => [],
    ),
  ),

  http.post(
    '/api/fsp/sync',
    candidateMutation((c) => {
      if (!c.fsp_id) return apiError(409, 'fsp_not_linked', 'ФСП ID не привязан')
      c._fsp_synced_at = db.now()
      db.save()
      return HttpResponse.json(fspStatus(c))
    }),
  ),

  // --- Опрос и тест ---
  http.get('/api/testing/survey', candidateGet(() => db.data.survey_questions)),

  http.post(
    '/api/testing/survey',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['SurveySubmit']>(request)
      const answers = body.answers ?? []
      const required = db.data.survey_questions.filter((q) => q.required)
      const missing = required.filter((q) => !answers.some((a) => a.question_id === q.id && ((a.option_ids ?? []).length || a.text?.trim())))
      if (missing.length) {
        return apiError(422, 'validation_error', 'Ответьте на обязательные вопросы', { fields: Object.fromEntries(missing.map((q) => [q.id, 'Обязательный вопрос'])) })
      }
      const result = surveyResult(answers)
      addHistory(c, {
        event: 'survey',
        specialization: result.recommended_specialization,
        grade_from: null,
        grade_to: null,
        test_session_id: null,
        comment: `Опрос рекомендовал специализацию ${SPEC_LABELS[result.recommended_specialization]}`,
      })
      db.save()
      return HttpResponse.json(result)
    }),
  ),

  http.get('/api/testing/grade', candidateGet((c) => gradeStatus(c))),

  http.get(
    '/api/testing/sessions',
    candidateGet(
      (c) => latest(T.sessions().filter((s) => s.candidate_id === c.id), (s) => s.started_at).map((s) => publicView(s)),
      () => [],
    ),
  ),

  http.post(
    '/api/testing/sessions',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['TestSessionCreate']>(request)
      const spec = body.specialization
      const target = body.target_grade
      const kind = body.kind ?? 'placement'
      if (!spec || !(spec in SPEC_LABELS) || !target || !GRADES.includes(target)) {
        return apiError(422, 'validation_error', 'Выберите специализацию и грейд')
      }
      const running = T.sessions().find((s) => s.candidate_id === c.id && s.status === 'in_progress')
      if (running) {
        return apiError(409, 'session_in_progress', 'Сначала завершите начатый тест', { session_id: running.id })
      }
      if (kind !== 'placement') {
        const at = maxDate(c.grade ? changeAvailableAt(c) : null, retryAvailableAt(c, spec, target))
        if (at) {
          return apiError(409, 'cooldown_active', 'Сменить грейд можно не чаще раза в 90 дней', { available_at: at })
        }
      } else {
        const retry = retryAvailableAt(c, spec, target)
        if (retry) {
          return apiError(409, 'cooldown_active', 'Повторить неудачную попытку на этот грейд можно через 30 дней', { available_at: retry })
        }
      }
      const prior = START_THETA[target]
      const session: SessionRow = {
        id: db.nextId('test_sessions'),
        candidate_id: c.id,
        specialization: spec,
        target_grade: target,
        kind,
        status: 'in_progress',
        started_at: db.now(),
        finished_at: null,
        items_answered: 0,
        max_items: MAX_ITEMS,
        theta: null,
        se: null,
        ci_low: null,
        ci_high: null,
        result_grade: null,
        result_category: null,
        passed: null,
        topic_scores: [],
        _mock: { prior, current: null, answers: [] },
      }
      const first = pickNext(session, session._mock!, prior)
      if (!first) return apiError(409, 'no_items', 'В банке нет задач для этой специализации')
      session._mock!.current = { instance_id: first.variant.instance_id, item_id: first.item.id, started_at: db.now() }
      T.sessions().push(session)
      db.save()
      return HttpResponse.json(sessionState(session), { status: 201 })
    }),
  ),

  http.get(
    '/api/testing/sessions/:sessionId',
    candidateGet((c, { params }) => {
      const session = T.sessions().find((s) => s.id === Number(params.sessionId) && s.candidate_id === c.id)
      if (!session) return notFound('Тест не найден')
      return sessionState(session)
    }),
  ),

  http.post(
    '/api/testing/sessions/:sessionId/answers',
    candidateMutation(async (c, { request, params }) => {
      const session = T.sessions().find((s) => s.id === Number(params.sessionId) && s.candidate_id === c.id)
      if (!session) return notFound('Тест не найден')
      if (session.status !== 'in_progress' || !session._mock?.current) {
        return apiError(409, 'session_finished', 'Тест уже завершён')
      }
      const body = await readJson<S['AnswerSubmit']>(request)
      const state = session._mock
      const current = state.current!
      if (body.instance_id !== current.instance_id) {
        return apiError(409, 'item_mismatch', 'Ответ пришёл не на текущую задачу. Обновите страницу.')
      }
      const found = findVariant(current.instance_id)!
      const left = timeLeft(state, found.variant)
      const spent = (Date.now() - new Date(current.started_at).getTime()) / 1000
      const expired = left <= 0 && spent > found.variant.time_limit_sec + TIME_GRACE_SEC
      const correct = !expired && checkAnswer(found.variant, body.answer ?? {})
      state.answers.push({
        instance_id: current.instance_id,
        item_id: found.item.id,
        topic: found.item.topic,
        topic_label: found.item.topic_label,
        a: found.item.a,
        b: found.item.b,
        correct,
        time_expired: expired,
      })
      session.items_answered = state.answers.length
      const { theta, se } = estimate(state.answers, state.prior)
      session.theta = round2(theta)
      session.se = round2(se)

      const n = state.answers.length
      // Стоп: 15 задач или SE < 0,35 после 12-й (и если банк кончился раньше).
      const next = n >= MAX_ITEMS || (n >= MIN_ITEMS && se < SE_STOP) ? undefined : pickNext(session, state, theta)
      if (next) {
        state.current = { instance_id: next.variant.instance_id, item_id: next.item.id, started_at: db.now() }
      } else {
        finishSession(session, c)
      }
      db.save()
      const ack: S['AnswerAck'] = {
        session_id: session.id,
        answered: n,
        finished: !next,
        next_item: next ? itemView(next.variant) : null,
        time_expired: expired,
      }
      return HttpResponse.json(ack)
    }),
  ),

  http.get(
    '/api/testing/sessions/:sessionId/result',
    candidateGet((c, { params }) => {
      const session = T.sessions().find((s) => s.id === Number(params.sessionId) && s.candidate_id === c.id)
      if (!session) return notFound('Тест не найден')
      if (session.status !== 'finished') return apiError(409, 'session_not_finished', 'Тест ещё не завершён')
      return testResult(session, c)
    }),
  ),

  // --- Приглашения ---
  http.get(
    '/api/invitations',
    candidateGet(
      (c, { request }) => {
        expireOverdue()
        const status = new URL(request.url).searchParams.get('status')
        return latest(
          T.invitations().filter((i) => i.candidate_id === c.id && (!status || i.status === status)),
          (i) => i.created_at,
        ).map(invitationView)
      },
      () => [],
    ),
  ),

  http.get(
    '/api/invitations/:invitationId',
    forCandidate((info) => {
      // quota / market-hint — пути рекрутера, не перехватываем.
      if (!/^\d+$/.test(String(info.params.invitationId))) return undefined
      return candidateGet((c, { params }) => {
        expireOverdue()
        const inv = ownInvitation(c, params.invitationId)
        if (!inv) return notFound('Приглашение не найдено')
        if (inv.status === 'sent') {
          inv.status = 'viewed'
          inv.viewed_at = db.now()
          pushEvent(inv.id, 'viewed', 'candidate')
          db.save()
        }
        const detail: S['InvitationDetail'] = {
          ...invitationView(inv),
          events: T.events()
            .filter((e) => e.invitation_id === inv.id)
            .sort((a, b) => a.at.localeCompare(b.at) || a.id - b.id),
        }
        return detail
      })(info)
    }),
  ),

  http.post(
    '/api/invitations/:invitationId/accept',
    candidateMutation((c, { params }) => {
      expireOverdue()
      const inv = ownInvitation(c, params.invitationId)
      if (!inv) return notFound('Приглашение не найдено')
      if (inv.status !== 'sent' && inv.status !== 'viewed') {
        return apiError(409, 'invalid_transition', `Приглашение уже в статусе «${statusLabel(inv.status)}»`, { status: inv.status })
      }
      const now = db.now()
      if (!inv.viewed_at) {
        inv.viewed_at = now
        pushEvent(inv.id, 'viewed', 'candidate')
      }
      inv.status = 'accepted'
      inv.responded_at = now
      pushEvent(inv.id, 'accepted', 'candidate')
      pushEvent(inv.id, 'contacts_revealed', null)
      audit({
        actor_user_id: c.user_id,
        actor_role: 'candidate',
        action: 'contacts_revealed',
        target_type: 'invitation',
        target_id: inv.id,
        summary: `Раскрыты контакты: ${c.pseudonym} ↔ ${inv.company_name}`,
        details: { candidate_id: c.id, company_id: inv.company_id },
      })
      db.save()
      return HttpResponse.json(invitationView(inv))
    }),
  ),

  http.post(
    '/api/invitations/:invitationId/decline',
    candidateMutation(async (c, { request, params }) => {
      expireOverdue()
      const inv = ownInvitation(c, params.invitationId)
      if (!inv) return notFound('Приглашение не найдено')
      const body = await readJson<S['DeclineRequest']>(request)
      const reasons = db.data.decline_reasons.map((r) => r.id as string)
      if (!body.reason || !reasons.includes(body.reason)) {
        return apiError(422, 'validation_error', 'Выберите причину отказа', { fields: { reason: 'Выберите причину' } })
      }
      if (body.reason === 'other' && !body.comment?.trim()) {
        return apiError(422, 'validation_error', 'Опишите причину в комментарии', { fields: { comment: 'Напишите пару слов' } })
      }
      if (inv.status !== 'sent' && inv.status !== 'viewed') {
        return apiError(409, 'invalid_transition', `Приглашение уже в статусе «${statusLabel(inv.status)}»`, { status: inv.status })
      }
      const now = db.now()
      if (!inv.viewed_at) {
        inv.viewed_at = now
        pushEvent(inv.id, 'viewed', 'candidate')
      }
      inv.status = 'declined'
      inv.decline_reason = body.reason
      inv.decline_comment = body.comment?.trim() || null
      inv.responded_at = now
      pushEvent(inv.id, 'declined', 'candidate')
      db.save()
      return HttpResponse.json(invitationView(inv))
    }),
  ),

  // --- Жалоба на работодателя ---
  http.post(
    '/api/reports',
    candidateMutation(async (c, { request }) => {
      const body = await readJson<S['ReportCreate']>(request)
      const company = db.data.companies.find((x) => x.id === body.company_id)
      if (!company) return notFound('Компания не найдена')
      if (!body.reason || !body.text?.trim()) {
        return apiError(422, 'validation_error', 'Выберите причину и опишите ситуацию', { fields: { text: 'Опишите ситуацию' } })
      }
      const report: S['Report'] = {
        id: db.nextId('reports'),
        company_id: company.id,
        company_name: company.name,
        reporter_candidate_id: c.id,
        invitation_id: body.invitation_id ?? null,
        vacancy_id: body.vacancy_id ?? null,
        reason: body.reason,
        text: body.text.trim(),
        status: 'new',
        resolution: null,
        created_at: db.now(),
        resolved_at: null,
      }
      T.reports().push(report)
      db.save()
      return HttpResponse.json(report, { status: 201 })
    }),
  ),

  // --- Вакансии и отклики ---
  http.get(
    '/api/vacancies',
    candidateGet(
      (c, { request }) => {
        const p = new URL(request.url).searchParams
        const spec = p.get('specialization')
        const grade = p.get('grade')
        const format = p.get('work_format')
        const skills = p.getAll('skills').flatMap((s) => s.split(',')).filter(Boolean)
        const salaryMin = Number(p.get('salary_min')) || 0
        const q = p.get('q')?.trim().toLowerCase()
        return latest(
          T.vacancies().filter(
            (v) =>
              v.status === 'published' &&
              (!spec || v.specialization === spec) &&
              (!grade || v.grade === grade) &&
              (!format || v.work_format === format) &&
              (!salaryMin || v.salary_to >= salaryMin) &&
              skills.every((s) => [...(v.skills_required ?? []), ...(v.skills_desired ?? [])].includes(s)) &&
              (!q || `${v.title} ${v.description} ${v.company_name}`.toLowerCase().includes(q)),
          ),
          (v) => v.published_at ?? v.created_at,
        ).map((v) => ({
          ...v,
          my_application_id: T.applications().find((a) => a.vacancy_id === v.id && a.candidate_id === c.id)?.id ?? null,
        }))
      },
      () => [],
    ),
  ),

  http.get(
    '/api/vacancies/:vacancyId',
    candidateGet((c, { params }) => {
      const v = T.vacancies().find((x) => x.id === Number(params.vacancyId))
      const mine = T.applications().find((a) => a.vacancy_id === v?.id && a.candidate_id === c.id)
      if (!v || (v.status !== 'published' && !mine)) return notFound('Вакансия не найдена')
      return { ...v, my_application_id: mine?.id ?? null }
    }),
  ),

  http.post(
    '/api/vacancies/:vacancyId/applications',
    candidateMutation(async (c, { request, params }) => {
      const v = T.vacancies().find((x) => x.id === Number(params.vacancyId))
      if (!v || v.status !== 'published') return notFound('Вакансия не найдена или снята с публикации')
      if (T.applications().some((a) => a.vacancy_id === v.id && a.candidate_id === c.id)) {
        return apiError(409, 'already_applied', 'Вы уже откликнулись на эту вакансию')
      }
      const body = await readJson<S['ApplicationCreate']>(request)
      const now = db.now()
      const app: ApplicationRow = {
        id: db.nextId('applications'),
        vacancy_id: v.id,
        candidate_id: c.id,
        vacancy_title: v.title,
        company_id: v.company_id,
        company_name: v.company_name,
        cover_letter: body.cover_letter?.trim() ?? '',
        status: 'new',
        created_at: now,
        updated_at: now,
      }
      T.applications().push(app)
      v.applications_count = (v.applications_count ?? 0) + 1
      db.save()
      return HttpResponse.json({ ...app, candidate: null, candidate_contacts: null } satisfies S['Application'], { status: 201 })
    }),
  ),

  http.get(
    '/api/applications',
    candidateGet(
      (c) =>
        latest(T.applications().filter((a) => a.candidate_id === c.id), (a) => a.created_at).map((a) => ({
          ...a,
          candidate: null,
          candidate_contacts: null,
        })),
      () => [],
    ),
  ),

  // --- Регулярные задания ---
  http.get(
    '/api/tasks/inbox',
    candidateGet(
      (c) => {
        const mine = latest(T.submissions().filter((s) => s.candidate_id === c.id), (s) => s.assigned_at)
        for (const s of mine) {
          if (s.status === 'assigned' && !isFuture(s.due_at)) s.status = 'expired'
        }
        const active = mine.find((s) => s.status === 'assigned') ?? null
        const inbox: S['TaskInbox'] = {
          active,
          history: mine.filter((s) => s !== active),
          freshness: c.freshness,
        }
        return inbox
      },
      (c) => ({ active: null, history: [], freshness: c.freshness }),
    ),
  ),

  http.post(
    '/api/tasks/submissions/:submissionId/answer',
    candidateMutation(async (c, { request, params }) => {
      const sub = T.submissions().find((s) => s.id === Number(params.submissionId) && s.candidate_id === c.id)
      if (!sub) return notFound('Задание не найдено')
      if (sub.status !== 'assigned') return apiError(409, 'submission_closed', 'На это задание уже нельзя ответить')
      if (!isFuture(sub.due_at)) {
        sub.status = 'expired'
        db.save()
        return apiError(409, 'submission_expired', 'Срок ответа истёк')
      }
      const body = await readJson<S['SubmissionAnswer']>(request)
      if (!body.answer_kind || !['text', 'code', 'approach'].includes(body.answer_kind) || !body.answer_text?.trim()) {
        return apiError(422, 'validation_error', 'Напишите ответ', { fields: { answer_text: 'Напишите ответ' } })
      }
      sub.answer_kind = body.answer_kind
      sub.answer_text = body.answer_text.trim()
      sub.status = 'submitted'
      sub.submitted_at = db.now()
      // Свежесть профиля растёт после ответа на задание (T9.3).
      c.freshness = round2(Math.min(1, c.freshness + 0.08))
      db.save()
      return HttpResponse.json(sub)
    }),
  ),
]

function statusLabel(status: S['InvitationStatus']) {
  const labels: Record<S['InvitationStatus'], string> = {
    sent: 'Отправлено',
    viewed: 'Просмотрено',
    accepted: 'Принято',
    declined: 'Отклонено',
    expired: 'Истекло',
    withdrawn: 'Отозвано',
  }
  return labels[status]
}
