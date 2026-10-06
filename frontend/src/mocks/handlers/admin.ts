import { http, HttpResponse, type HttpHandler, type HttpResponseResolver } from 'msw'
import type { components } from '@/shared/api/schema'
import { db, demoUser, type CollectionName } from '../db'
import { apiError, mockLatency, withScenario } from '../utils'

/**
 * Моки API кабинета администратора (трек 1c).
 * Пути и формы — по docs/api/openapi.json. Данные — общая база моков (db), правки админа
 * сохраняются в db и видны другим ролям (блокировки, статусы шаблонов, настройки платформы).
 * /api/admin/* — только админ (остальным 403). Общие пути (/api/catalog/*, /api/eval/*)
 * обрабатываем только для роли admin, для остальных возвращаем undefined — дальше их ловят
 * хендлеры других ролей.
 */

type S = components['schemas']
type Role = S['Role']
type SpecCode = S['SpecializationCode']
type GradeCode = S['GradeCode']
type ItemDetail = S['ItemDetail']
type ItemSummary = S['ItemSummary']
type ItemVariantPreview = S['ItemVariantPreview']
type AuditEntry = S['AuditEntry']
type UserRecord = S['UserRecord']
type PlatformSettings = S['PlatformSettings']
type ValidationChart = S['ValidationChart']
type VacancyTestResult = S['VacancyTestResult']
type Report = S['Report']
type Skill = S['Skill']
type Topic = S['Topic']

interface CompanyRow {
  id: number
  name: string
  description: string
  industry: string
  website?: string | null
  city?: string | null
  contact_email: string
  contact_phone?: string | null
  inn?: string | null
  verified_domain: boolean
  trust_score: number
  blocked?: boolean
  created_at: string
}

interface CandidateRow {
  id: number
  user_id: number
  category: string
  specialization: string
  stack: string[]
}

interface NeedRow {
  id: number
  category: string
  skills_required: string[]
  skills_desired: string[]
}

const ROLE_LABEL: Record<Role, string> = { candidate: 'соискатель', recruiter: 'рекрутер', admin: 'администратор' }
const GRADE_ORDER: Record<GradeCode, number> = { intern: 0, junior: 1, middle: 2, senior: 3 }
const GRADE_LABEL: Record<GradeCode, string> = { intern: 'Стажёр', junior: 'Junior', middle: 'Middle', senior: 'Senior' }
const GRADES: GradeCode[] = ['intern', 'junior', 'middle', 'senior']
const SPECS: SpecCode[] = ['backend', 'frontend', 'mobile', 'data_ml', 'qa', 'devops']
const VALIDATION_SEED = 20261011

/** Коллекция базы моков с типом из контракта. Каждый раз берём заново: db.reset() меняет db.data. */
function col<T>(name: CollectionName): T[] {
  return db.data[name] as unknown as T[]
}

const forbidden = () => apiError(403, 'forbidden', 'Недостаточно прав')
const notFound = () => apiError(404, 'not_found', 'Объект не найден')

/** GET с учётом режима данных демо-плашки. shared=true — чужой роли отдаём undefined (ловят другие хендлеры). */
function adminGet<T>(data: Parameters<typeof withScenario<T>>[0]['data'], empty?: () => T, shared = false): HttpResponseResolver {
  const inner = withScenario<T>({ data, empty })
  return async (info) => {
    if (demoUser(info.request).role !== 'admin') return shared ? undefined : forbidden()
    return inner(info)
  }
}

/** Мутация: только админ, задержка «как у сети». */
function adminWrite(handler: HttpResponseResolver, shared = false): HttpResponseResolver {
  return async (info) => {
    if (demoUser(info.request).role !== 'admin') return shared ? undefined : forbidden()
    await mockLatency()
    return handler(info)
  }
}

function addAudit(
  request: Request,
  action: string,
  targetType: string,
  targetId: number | null,
  summary: string,
  details: Record<string, unknown> = {},
): void {
  const { userId } = demoUser(request)
  col<AuditEntry>('audit_log').push({
    id: db.nextId('audit_log'),
    at: db.now(),
    actor_user_id: userId ?? 48,
    actor_role: 'admin',
    action,
    target_type: targetType,
    target_id: targetId,
    summary,
    details,
  })
}

/** Ошибка валидации как у бэкенда (FastAPI/pydantic): details.errors = [{loc, msg, type, ctx}]. */
interface FieldError {
  field: string
  type: string
  msg: string
  ctx?: Record<string, unknown>
}

function validationError(errors: FieldError[]) {
  return apiError(422, 'validation_error', 'Ошибка валидации данных', {
    errors: errors.map((e) => ({ loc: ['body', e.field], msg: e.msg, type: e.type, ...(e.ctx ? { ctx: e.ctx } : {}) })),
  })
}

function pageOf<T>(rows: T[], url: URL) {
  const page = Math.max(1, Number(url.searchParams.get('page')) || 1)
  const pageSize = Math.min(200, Math.max(1, Number(url.searchParams.get('page_size')) || 50))
  return { items: rows.slice((page - 1) * pageSize, page * pageSize), total: rows.length, page, page_size: pageSize }
}

const byDateDesc = (a: { at: string; id: number }, b: { at: string; id: number }) =>
  b.at.localeCompare(a.at) || b.id - a.id

// --- Детерминированный генератор (seed → одна и та же последовательность) ---------------------
export function mulberry32(seed: number): () => number {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function shuffled<T>(list: T[], rnd: () => number): T[] {
  const out = [...list]
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

const round = (v: number, d = 2) => Math.round(v * 10 ** d) / 10 ** d

// --- Дашборд ---------------------------------------------------------------------------------
function buildDashboard(): S['AdminDashboard'] {
  const users = col<UserRecord>('users')
  const usersByRole: Record<Role, number> = { candidate: 0, recruiter: 0, admin: 0 }
  for (const u of users) usersByRole[u.role] = (usersByRole[u.role] ?? 0) + 1

  const sessions = col<{ started_at: string }>('test_sessions')
  const byDay = new Map<string, number>()
  for (const s of sessions) {
    const d = s.started_at.slice(0, 10)
    byDay.set(d, (byDay.get(d) ?? 0) + 1)
  }

  const invitations = col<{ status: S['InvitationStatus'] }>('invitations')
  const byStatus: Record<S['InvitationStatus'], number> = {
    sent: 0,
    viewed: 0,
    accepted: 0,
    declined: 0,
    expired: 0,
    withdrawn: 0,
  }
  for (const inv of invitations) byStatus[inv.status] += 1
  // Как на бэкенде (AdminService.dashboard): принятые / все отправленные.
  const base = invitations.length

  const items = col<ItemDetail>('items')
  return {
    users_by_role: usersByRole,
    tests_total: sessions.length,
    tests_by_day: [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, count]) => ({ date, count })),
    invitations_by_status: byStatus,
    invite_to_accept_conversion: base > 0 ? round(byStatus.accepted / base, 2) : 0,
    leak_flags: items
      .filter((i) => i.leak_flag)
      .sort((a, b) => b.leak_score - a.leak_score)
      .map((i) => ({ item_id: i.id, title: i.title, specialization: i.specialization, leak_score: i.leak_score })),
    open_reports: col<Report>('reports').filter((r) => r.status === 'new' || r.status === 'in_review').length,
  }
}

const EMPTY_DASHBOARD: S['AdminDashboard'] = {
  users_by_role: { candidate: 0, recruiter: 0, admin: 0 },
  tests_total: 0,
  tests_by_day: [],
  invitations_by_status: { sent: 0, viewed: 0, accepted: 0, declined: 0, expired: 0, withdrawn: 0 },
  invite_to_accept_conversion: 0,
  leak_flags: [],
  open_reports: 0,
}

// --- Компании --------------------------------------------------------------------------------
/** Скоринг и доля ответов — как на бэкенде (companies/service.py: trust_score, response_rate). */
function adminCompany(c: CompanyRow): S['AdminCompany'] {
  const invitations = col<{ company_id: number; status: string }>('invitations').filter((i) => i.company_id === c.id)
  const answered = invitations.filter((i) => i.status === 'accepted' || i.status === 'declined').length
  const decided = invitations.filter((i) => i.status === 'accepted' || i.status === 'declined' || i.status === 'expired').length
  const reports = col<Report>('reports').filter((r) => r.company_id === c.id)
  const responseRate = decided ? round(answered / decided, 2) : 0
  let score = decided ? 30 + 50 * responseRate : 50
  if (c.verified_domain) score += 10
  score -= 15 * reports.filter((r) => r.status === 'resolved').length
  score -= 5 * reports.filter((r) => r.status === 'new' || r.status === 'in_review').length
  return {
    ...c,
    blocked: Boolean(c.blocked),
    trust_score: round(Math.min(100, Math.max(0, score)), 1),
    recruiters_count: col<{ company_id: number }>('recruiters').filter((r) => r.company_id === c.id).length,
    invitations_sent: invitations.length,
    response_rate: responseRate,
    reports_count: reports.length,
  }
}

// --- Банк задач ------------------------------------------------------------------------------
function summary(item: ItemDetail): ItemSummary {
  const { description: _d, preview_variants: _p, ...rest } = item
  return rest
}

function buildCoverage(): S['CoverageCell'][] {
  const items = col<ItemDetail>('items')
  const cells: S['CoverageCell'][] = []
  for (const t of col<Topic>('topics')) {
    for (const g of GRADES) {
      const here = items.filter((i) => i.topic === t.id && i.target_grade === g)
      cells.push({
        specialization: t.specialization,
        topic: t.id,
        topic_label: t.label,
        grade: g,
        active: here.filter((i) => i.status === 'active').length,
        pilot: here.filter((i) => i.status === 'pilot').length,
      })
    }
  }
  return cells
}

/**
 * Пересчёт калибровки (заглушка T4.9): b сдвигается в сторону наблюдаемой доли верных,
 * ожидаемая доля подтягивается к наблюдаемой; пилот с ≥ 150 ответами становится активным.
 * Слитые (leak_flag) шаблоны не трогаем: их ответы искажены.
 */
function recalibrate(): S['RecalibrationResult'] {
  const changes: S['CalibrationChange'][] = []
  let promoted = 0
  for (const item of col<ItemDetail>('items')) {
    if (item.status !== 'active' && item.status !== 'pilot') continue
    if (item.leak_flag || item.exposures < 15 || item.correct_rate == null || item.expected_correct_rate == null) continue
    const gap = item.correct_rate - item.expected_correct_rate
    const bAfter = round(Math.max(-4, Math.min(4, item.b - 1.2 * gap)))
    const aAfter = round(Math.max(0.2, Math.min(4, item.a * (1 - Math.abs(gap) * 0.5))))
    if (bAfter === item.b && aAfter === item.a) continue
    changes.push({ item_id: item.id, a_before: item.a, a_after: aAfter, b_before: item.b, b_after: bAfter })
    item.a = aAfter
    item.b = bAfter
    item.expected_correct_rate = round((item.expected_correct_rate + item.correct_rate) / 2)
    if (item.status === 'pilot' && item.exposures >= 150 && item.a >= 0.4 && Math.abs(item.b) <= 3.5) {
      item.status = 'active'
      promoted += 1
    }
  }
  return { started_at: db.now(), items_recalibrated: changes.length, pilot_promoted: promoted, changes }
}

// --- Разбор вакансии (заглушка T4.8: словарь тем, без LLM) ------------------------------------
const TOPIC_KEYWORDS: Record<string, string[]> = {
  'backend.http_api': ['rest', 'api', 'http', 'fastapi', 'django', 'flask', 'grpc', 'graphql', 'spring'],
  'backend.databases': ['postgresql', 'postgres', 'mysql', 'sql', 'транзакц', 'индекс', 'clickhouse', 'redis'],
  'backend.concurrency': ['конкурентн', 'асинхрон', 'async', 'горутин', 'многопоточ', 'kafka', 'очеред', 'rabbitmq'],
  'backend.architecture': ['архитектур', 'микросервис', 'ddd', 'паттерн', 'проектирова'],
  'backend.algorithms': ['алгоритм', 'структуры данных', 'сложность'],
  'backend.security': ['oauth', 'безопасност', 'jwt', 'owasp', 'авторизац', 'аутентификац'],
  'frontend.js_core': ['javascript', 'event loop', 'promise', 'es6'],
  'frontend.react': ['react', 'redux', 'mobx', 'zustand', 'next.js', 'хуки'],
  'frontend.css_layout': ['css', 'вёрстк', 'верстк', 'flexbox', 'адаптивн', 'scss', 'tailwind'],
  'frontend.browser': ['браузер', 'производительност', 'web vitals', 'рендеринг'],
  'frontend.typescript': ['typescript'],
  'frontend.testing': ['jest', 'vitest', 'playwright', 'cypress', 'testing library', 'unit-тест', 'юнит-тест'],
  'mobile.lifecycle': ['жизненн', 'activity', 'fragment', 'lifecycle', 'viewcontroller'],
  'mobile.ui': ['compose', 'swiftui', 'uikit', 'навигац', 'recyclerview'],
  'mobile.networking': ['retrofit', 'room', 'coredata', 'okhttp', 'офлайн', 'хранени'],
  'mobile.language': ['kotlin', 'swift', 'корутин', 'coroutines'],
  'mobile.release': ['google play', 'app store', 'публикац', 'gradle', 'fastlane'],
  'data_ml.statistics': ['статистик', 'вероятност', 'a/b', 'гипотез'],
  'data_ml.ml_basics': ['scikit', 'sklearn', 'машинн', 'бустинг', 'catboost', 'xgboost', 'регресси', 'классификац'],
  'data_ml.deep_learning': ['pytorch', 'tensorflow', 'нейросет', 'deep learning', 'трансформер'],
  'data_ml.sql_data': ['pandas', 'sql', 'spark', 'airflow', 'etl'],
  'data_ml.metrics': ['метрик', 'валидац', 'roc', 'precision', 'recall'],
  'qa.test_design': ['тест-дизайн', 'тест-кейс', 'граничн', 'эквивалентност', 'чек-лист'],
  'qa.automation': ['автотест', 'selenium', 'pytest', 'playwright', 'автоматизац'],
  'qa.api_testing': ['postman', 'api', 'swagger', 'rest'],
  'qa.process': ['баг-репорт', 'jira', 'регресс', 'баг'],
  'qa.performance': ['нагрузочн', 'jmeter', 'k6', 'locust'],
  'devops.linux': ['linux', 'bash', 'tcp', 'nginx', 'сети'],
  'devops.containers': ['docker', 'kubernetes', 'k8s', 'helm', 'контейнер'],
  'devops.ci_cd': ['ci/cd', 'gitlab ci', 'github actions', 'jenkins', 'argo', 'пайплайн'],
  'devops.monitoring': ['prometheus', 'grafana', 'мониторинг', 'логировани', 'alertmanager', 'loki'],
  'devops.iac': ['terraform', 'ansible', 'iac', 'инфраструктура как код'],
}

const SPEC_HINTS: Record<SpecCode, string[]> = {
  backend: ['backend', 'бэкенд', 'python', 'golang', 'go-разработ', 'java', 'php', 'node.js', 'fastapi', 'django'],
  frontend: ['frontend', 'фронтенд', 'react', 'vue', 'angular', 'вёрстк'],
  mobile: ['android', 'ios', 'мобильн', 'kotlin', 'swift'],
  data_ml: ['data scien', 'ml-', ' ml ', 'машинн', 'data scientist', 'датасаентист', 'scikit', 'pandas'],
  qa: ['qa', 'тестировщик', 'тестирован'],
  devops: ['devops', 'sre', 'девопс', 'kubernetes', 'terraform'],
}

interface DraftTemplate {
  title: string
  format: S['ItemFormat']
  prompt: string
  variant: (seed: number) => Pick<ItemVariantPreview, 'prompt' | 'options' | 'steps' | 'unit' | 'correct_answer'>
}

const APPS = ['Кошелёк', 'Доставка', 'Кинотеатр', 'Фитнес', 'Библиотека', 'Такси', 'Поликлиника']
const emptyAnswer = { choice_ids: null, value: null, text: null, line: null, order: null }

const DRAFT_TEMPLATES: Record<string, DraftTemplate> = {
  'backend.security': {
    title: 'Поток Authorization Code в OAuth 2.0',
    format: 'ordering',
    prompt: 'Расположите шаги потока Authorization Code + PKCE в правильном порядке.',
    variant: (seed) => {
      const rnd = mulberry32(seed)
      const app = APPS[seed % APPS.length]
      const steps = [
        { id: 's1', text: `Приложение «${app}» создаёт code_verifier и code_challenge` },
        { id: 's2', text: 'Пользователь перенаправляется на страницу входа провайдера' },
        { id: 's3', text: 'Провайдер возвращает одноразовый code на redirect_uri' },
        { id: 's4', text: 'Приложение меняет code + code_verifier на токены' },
        { id: 's5', text: 'Приложение вызывает API с access_token' },
      ]
      return {
        prompt: `Расположите шаги входа в приложение «${app}» через OAuth 2.0 (Authorization Code + PKCE).`,
        options: null,
        steps: shuffled(steps, rnd),
        unit: null,
        correct_answer: { ...emptyAnswer, order: steps.map((s) => s.id) },
      }
    },
  },
  'frontend.testing': {
    title: 'Запрос Testing Library для кнопки',
    format: 'single_choice',
    prompt: 'Каким запросом Testing Library лучше найти кнопку в тесте?',
    variant: (seed) => {
      const rnd = mulberry32(seed)
      const label = ['Оплатить', 'Сохранить', 'В корзину', 'Отправить', 'Войти'][seed % 5]
      const right = `getByRole('button', { name: '${label}' })`
      const opts = shuffled(
        [right, `getByTestId('${label.toLowerCase()}-btn')`, `container.querySelector('.btn-${seed % 9}')`, `getByText('${label}').parentElement`],
        rnd,
      )
      return {
        prompt: `На странице есть кнопка «${label}». Каким запросом Testing Library её лучше найти, чтобы тест проверял то, что видит пользователь?`,
        options: opts.map((text, i) => ({ id: 'abcd'[i], text })),
        steps: null,
        unit: null,
        correct_answer: { ...emptyAnswer, choice_ids: ['abcd'[opts.indexOf(right)]] },
      }
    },
  },
  'qa.test_design': {
    title: 'Классы эквивалентности для поля ввода',
    format: 'numeric',
    prompt: 'Сколько классов эквивалентности у поля с допустимым диапазоном?',
    variant: (seed) => {
      const rnd = mulberry32(seed)
      const lo = 1 + Math.floor(rnd() * 20)
      const hi = lo + 10 + Math.floor(rnd() * 90)
      const field = ['Возраст', 'Число гостей', 'Срок вклада, мес.', 'Количество товаров'][seed % 4]
      return {
        prompt: `Поле «${field}» принимает целые числа от ${lo} до ${hi}. Сколько минимально тестовых значений нужно по методу граничных значений (по два на каждую границу)?`,
        options: null,
        steps: null,
        unit: 'значений',
        correct_answer: { ...emptyAnswer, value: 4 },
      }
    },
  },
  'qa.process': {
    title: 'Серьёзность и приоритет бага',
    format: 'single_choice',
    prompt: 'Оцените серьёзность дефекта по описанию.',
    variant: (seed) => {
      const rnd = mulberry32(seed)
      const cases = [
        { text: 'приложение падает при оплате заказа', right: 'Блокирующий' },
        { text: 'опечатка в подвале сайта', right: 'Незначительный' },
        { text: 'фильтр по цене иногда игнорируется', right: 'Значительный' },
      ]
      const c = cases[seed % cases.length]
      const labels = shuffled(['Блокирующий', 'Значительный', 'Незначительный', 'Тривиальный'], rnd)
      return {
        prompt: `Дефект: ${c.text}. Какую серьёзность (severity) ему поставить?`,
        options: labels.map((t, i) => ({ id: 'abcd'[i], text: t })),
        steps: null,
        unit: null,
        correct_answer: { ...emptyAnswer, choice_ids: ['abcd'[labels.indexOf(c.right)]] },
      }
    },
  },
}

function genericDraft(label: string): DraftTemplate {
  return {
    title: `Базовый вопрос: ${label}`,
    format: 'short_text',
    prompt: `Короткий вопрос по теме «${label}» на примере сервиса.`,
    variant: (seed) => ({
      prompt: `Сервис «${APPS[seed % APPS.length]}»: назовите один ключевой приём из темы «${label}», который вы бы применили, и зачем.`,
      options: null,
      steps: null,
      unit: null,
      correct_answer: { ...emptyAnswer, text: 'Проверяется вручную по критериям черновика' },
    }),
  }
}

function makeVariants(id: number, tpl: DraftTemplate, topic: string, topicLabel: string): ItemVariantPreview[] {
  return [101, 202, 303].map((k) => {
    const seed = id * 1000 + k
    return {
      instance_id: `it-${String(id).padStart(4, '0')}-s${seed}`,
      format: tpl.format,
      topic,
      topic_label: topicLabel,
      code: null,
      time_limit_sec: 120,
      seed,
      ...tpl.variant(seed),
    }
  })
}

function findKeywords(text: string, keywords: string[]): string[] {
  const lower = ` ${text.toLowerCase()} `
  const found: string[] = []
  for (const kw of keywords) {
    const at = lower.indexOf(kw)
    if (at < 0) continue
    // Слово из исходного текста (с регистром) по найденной позиции.
    const original = ` ${text} `.slice(at, at + kw.length).trim()
    const end = ` ${text} `.slice(at + kw.length).match(/^[\p{L}\d+#.-]*/u)?.[0] ?? ''
    found.push((original + end).replace(/[.,;:]+$/, ''))
  }
  return [...new Set(found)]
}

function detectGrade(text: string): { grade: GradeCode; why: string } {
  const t = text.toLowerCase()
  if (/senior|сеньор|синьор|ведущ|lead\b|тимлид/.test(t)) return { grade: 'senior', why: 'в тексте указан уровень Senior' }
  if (/middle|мидл|миддл/.test(t)) return { grade: 'middle', why: 'в тексте указан уровень Middle' }
  if (/junior|джун|младш/.test(t)) return { grade: 'junior', why: 'в тексте указан уровень Junior' }
  if (/стажёр|стажер|стажир|intern/.test(t)) return { grade: 'intern', why: 'в тексте указана стажировка' }
  return { grade: 'middle', why: 'уровень в тексте не указан — взят Middle' }
}

/** Текст вакансии → темы → шаблоны банка → черновики для тем без шаблонов. Создаёт черновики в банке. */
export function buildVacancyTest(text: string, specialization?: SpecCode | null): VacancyTestResult {
  const topics = col<Topic>('topics')
  const items = col<ItemDetail>('items')

  // 1. Специализация: по словам-подсказкам и найденным темам.
  let spec: SpecCode = specialization ?? 'backend'
  let specWhy = 'специализация задана вручную'
  if (!specialization) {
    const score = (s: SpecCode) =>
      2 * findKeywords(text, SPEC_HINTS[s]).length +
      topics.filter((t) => t.specialization === s).reduce((n, t) => n + findKeywords(text, TOPIC_KEYWORDS[t.id] ?? []).length, 0)
    spec = [...SPECS].sort((a, b) => score(b) - score(a))[0]
    specWhy = `специализация определена по словам в тексте (${findKeywords(text, SPEC_HINTS[spec]).slice(0, 3).join(', ') || 'по темам'})`
  }
  const { grade, why: gradeWhy } = detectGrade(text)

  // 2. Темы специализации, найденные в тексте.
  const detected: S['DetectedTopic'][] = []
  for (const t of topics.filter((x) => x.specialization === spec)) {
    const matched = findKeywords(text, TOPIC_KEYWORDS[t.id] ?? [])
    if (!matched.length) continue
    const covered = items.some((i) => i.topic === t.id && i.status === 'active')
    detected.push({ topic: t.id, label: t.label, matched_by: matched, confidence: round(Math.min(0.95, 0.55 + 0.15 * matched.length)), covered })
  }
  detected.sort((a, b) => b.confidence - a.confidence)

  // 3. По одному активному шаблону на тему — ближайший по грейду, при равенстве с большей различающей силой.
  const selected: S['SelectedItem'][] = []
  for (const d of detected.filter((x) => x.covered)) {
    const best = items
      .filter((i) => i.topic === d.topic && i.status === 'active')
      .sort(
        (a, b) =>
          Math.abs(GRADE_ORDER[a.target_grade] - GRADE_ORDER[grade]) - Math.abs(GRADE_ORDER[b.target_grade] - GRADE_ORDER[grade]) ||
          b.a - a.a,
      )[0]
    const sameGrade = best.target_grade === grade
    selected.push({
      item_id: best.id,
      code: best.code,
      title: best.title,
      topic: d.topic,
      reason:
        `Тема «${d.label}» найдена по словам: ${d.matched_by.join(', ')}. ` +
        (sameGrade
          ? `Шаблон рассчитан на ${GRADE_LABEL[grade]}`
          : `Шаблона под ${GRADE_LABEL[grade]} нет, взят ближайший — ${GRADE_LABEL[best.target_grade]}`) +
        `, различающая сила a = ${best.a.toFixed(2).replace('.', ',')}${best.leak_flag ? ' (внимание: флаг утечки)' : ''}.`,
    })
  }

  // 4. Темы без активных шаблонов: существующий черновик/пилот или новый черновик.
  // item_id — id черновика в банке (бэкенд трека 3c добавляет это поле в ItemDraft).
  const drafts: Array<S['ItemDraft'] & { item_id: number }> = []
  for (const d of detected.filter((x) => !x.covered)) {
    const existing = items.find((i) => i.topic === d.topic && (i.status === 'draft' || i.status === 'pilot'))
    if (existing) {
      drafts.push({ item_id: existing.id, topic: d.topic, label: d.label, title: existing.title, format: existing.format, prompt: existing.preview_variants[0]?.prompt ?? existing.description, status: existing.status })
      continue
    }
    const tpl = DRAFT_TEMPLATES[d.topic] ?? genericDraft(d.label)
    const id = db.nextId('items')
    const code = `${spec.slice(0, 2)}-${d.topic.split('.')[1].slice(0, 4)}-${String(id).padStart(3, '0')}`
    items.push({
      id,
      code,
      title: tpl.title,
      description: `Черновик по вакансии: «${tpl.title}». Создан по словарю тем (без LLM), ждёт одобрения администратора.`,
      specialization: spec,
      topic: d.topic,
      topic_label: d.label,
      target_grade: grade,
      format: tpl.format,
      a: 1.0,
      b: [-1.5, -0.5, 0.5, 1.5][GRADE_ORDER[grade]],
      status: 'draft',
      source: 'llm_vacancy',
      exposures: 0,
      correct_rate: null,
      expected_correct_rate: null,
      leak_flag: false,
      leak_score: 0,
      variants_count: 50,
      created_at: db.now(),
      preview_variants: makeVariants(id, tpl, d.topic, d.label),
    })
    drafts.push({ item_id: id, topic: d.topic, label: d.label, title: tpl.title, format: tpl.format, prompt: tpl.prompt, status: 'draft' })
  }

  const explanation = [
    `Специализация ${spec === 'data_ml' ? 'Data Science / ML' : spec}: ${specWhy}`,
    `Грейд ${GRADE_LABEL[grade]}: ${gradeWhy}`,
    detected.length
      ? `Найдено тем: ${detected.length}, из них покрыто активными шаблонами банка: ${detected.filter((d) => d.covered).length}`
      : 'Темы из словаря в тексте не найдены — уточните текст вакансии',
    ...drafts.map((d) =>
      d.status === 'draft'
        ? `Для темы «${d.label}» активных шаблонов нет — черновик «${d.title}», после одобрения он пойдёт в тесты как непроверочный`
        : `Для темы «${d.label}» есть только пилотный шаблон «${d.title}» — он идёт в тест как непроверочный и не влияет на балл`,
    ),
    'Тест адаптивный: эти шаблоны задают темы, а конкретные варианты (числа, код, порядок ответов) у каждого кандидата свои',
  ]

  const firstLine = text.trim().split('\n')[0].replace(/^#+\s*/, '').slice(0, 90)
  const result: VacancyTestResult = {
    id: db.nextId('vacancy_tests'),
    vacancy_title: firstLine || 'Вакансия без заголовка',
    vacancy_text: text.trim(),
    specialization: spec,
    grade,
    parser: 'rules',
    topics: detected,
    items: selected,
    drafts,
    explanation,
  }
  col<VacancyTestResult>('vacancy_tests').push(result)
  return result
}

// --- Валидация -------------------------------------------------------------------------------
/**
 * Графики валидации. Пока в фикстуре заглушки (is_stub), подставляем цифры настоящей симуляции
 * движка из docs/testing/engine.md (seed 20261011, 1000 кандидатов, банк 240 задач).
 * Разбивка точности по грейдам и точки графиков восстановлены так, чтобы итог совпадал с таблицами
 * документа. Когда волна 5c положит в фикстуру настоящие данные (is_stub=false), они покажутся как есть.
 */
function engineCharts(): Record<string, ValidationChart> {
  const rnd = mulberry32(VALIDATION_SEED)
  const gauss = () => Math.sqrt(-2 * Math.log(rnd() + 1e-12)) * Math.cos(2 * Math.PI * rnd())
  const recovery = Array.from({ length: 150 }, () => {
    const t = Math.max(-2.8, Math.min(2.8, gauss()))
    return { x: round(t), y: round(Math.max(-3.2, Math.min(3.2, t + 0.33 * gauss()))) }
  })
  return {
    grade_accuracy: {
      id: 'grade_accuracy',
      title: 'Точность определения грейда',
      description: 'Доля синтетических кандидатов, у которых грейд по тесту совпал с истинным (точно и с ошибкой не больше одного грейда).',
      chart_type: 'bar',
      x_label: 'Истинный грейд',
      y_label: 'Доля кандидатов',
      series: [
        { name: 'Точно', points: [{ x: 'Стажёр', y: 0.87 }, { x: 'Junior', y: 0.75 }, { x: 'Middle', y: 0.75 }, { x: 'Senior', y: 0.86 }] },
        { name: '±1 грейд', points: [{ x: 'Стажёр', y: 1 }, { x: 'Junior', y: 1 }, { x: 'Middle', y: 1 }, { x: 'Senior', y: 1 }] },
      ],
      summary: { exact: 0.784, within_one: 1.0, exact_far_from_threshold: 0.885 },
      is_stub: true,
    },
    theta_recovery: {
      id: 'theta_recovery',
      title: 'Оценка уровня против истинного',
      description: 'Истинный уровень синтетического кандидата (известен заранее) против оценки теста.',
      chart_type: 'scatter',
      x_label: 'Истинный уровень θ',
      y_label: 'Оценка теста θ̂',
      series: [{ name: 'Кандидаты', points: recovery }],
      summary: { correlation: 0.945, rmse: 0.332, mean_se: 0.349, mean_test_length: 12.8 },
      is_stub: true,
    },
    retest_stability: {
      id: 'retest_stability',
      title: 'Стабильность при повторном тесте',
      description: 'Те же кандидаты проходят тест второй раз с другими вариантами задач.',
      chart_type: 'bar',
      x_label: 'Правило остановки теста',
      y_label: 'Доля совпадений',
      series: [
        { name: 'Тот же грейд', points: [{ x: 'до 15 задач (SE < 0,35)', y: 0.679 }, { x: 'до 20 задач (SE < 0,30)', y: 0.736 }] },
        { name: 'То же решение «подтверждён / нет»', points: [{ x: 'до 15 задач (SE < 0,35)', y: 0.864 }, { x: 'до 20 задач (SE < 0,30)', y: 0.882 }] },
      ],
      summary: { agreement: 0.679, cohen_kappa: 0.558, theta_retest_corr: 0.891, decision_agreement: 0.864, agreement_long: 0.736 },
      is_stub: true,
    },
    test_length: {
      id: 'test_length',
      title: 'Длина адаптивного теста',
      description: 'Сколько задач понадобилось до остановки (SE < 0,35 или 15 задач).',
      chart_type: 'histogram',
      x_label: 'Задач в тесте',
      y_label: 'Кандидатов',
      series: [
        {
          name: 'Тесты',
          points: [[6, 5], [7, 10], [8, 20], [9, 35], [10, 60], [11, 100], [12, 140], [13, 177], [14, 220], [15, 233]].map(([x, y]) => ({ x, y })),
        },
      ],
      summary: { mean: 12.8, share_max_length: 0.233, share_stopped_by_se: 0.767 },
      is_stub: true,
    },
    leak_detector: {
      id: 'leak_detector',
      title: 'Защита от утечки заданий',
      description: 'Симуляция: 20% задач слиты, 10% кандидатов — «читеры». Как часто читеру завышают грейд в каждом режиме защиты.',
      chart_type: 'bar',
      x_label: 'Режим',
      y_label: 'Доля завышенных грейдов',
      series: [
        {
          name: 'Читеры',
          points: [
            { x: 'Нет утечки', y: 0.1 },
            { x: 'Без защиты', y: 0.85 },
            { x: 'Детектор', y: 0.38 },
            { x: 'Параметризация', y: 0.14 },
            { x: 'Обе защиты', y: 0.14 },
          ],
        },
        {
          name: 'Честные',
          points: [
            { x: 'Нет утечки', y: 0.101 },
            { x: 'Без защиты', y: 0.099 },
            { x: 'Детектор', y: 0.118 },
            { x: 'Параметризация', y: 0.098 },
            { x: 'Обе защиты', y: 0.098 },
          ],
        },
      ],
      summary: { precision: 1.0, recall: 0.938, recall_speed_signal: 0.729, recall_irt_signal: 0.062, cheater_recall: 0.83 },
      is_stub: true,
    },
    bank_size: {
      id: 'bank_size',
      title: 'Сколько шаблонов нужно в банке',
      description: 'Точность теста при разном размере банка одной специализации (500 кандидатов на каждый размер).',
      chart_type: 'line',
      x_label: 'Шаблонов в банке',
      y_label: 'Значение',
      series: [
        { name: 'Корреляция с истинным уровнем', points: [[15, 0.898], [30, 0.921], [60, 0.898], [120, 0.939], [240, 0.941]].map(([x, y]) => ({ x, y })) },
        { name: 'Грейд точно', points: [[15, 0.73], [30, 0.774], [60, 0.718], [120, 0.77], [240, 0.794]].map(([x, y]) => ({ x, y })) },
      ],
      summary: { se_at_15: 0.484, se_at_240: 0.344 },
      is_stub: true,
    },
  }
}

function buildCharts(): ValidationChart[] {
  const engine = engineCharts()
  const fromSeed = col<ValidationChart>('validation_charts').map((c) => (c.is_stub && engine[c.id] ? engine[c.id] : c))
  const extra = Object.values(engine).filter((c) => !fromSeed.some((s) => s.id === c.id))
  // Различающая сила: точки из фикстуры (шаблоны банка); средняя r_pb — из симуляции (линейная форма 30 задач).
  return [...fromSeed, ...extra].map((c) =>
    c.id === 'item_discrimination' && c.is_stub
      ? {
          ...c,
          description: 'Каждая точка — шаблон: параметр a модели против корреляции ответа на задачу с итоговым баллом.',
          summary: { mean_point_biserial: 0.348, mean_a: 1.32, share_above_02: 1.0, adaptive_mean_point_biserial: 0.269 },
        }
      : c,
  )
}

/** CSV пар «потребность — кандидат» → метрики подбора (порядок строк внутри потребности = ранжирование). */
export function evaluateMatchingCsv(filename: string, text: string): S['MatchingEvalResult'] | { error: string } {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  if (lines.length < 2) return { error: 'В файле нет строк с данными' }
  const sep = lines[0].includes(';') ? ';' : ','
  const header = lines[0].split(sep).map((h) => h.trim().toLowerCase().replace(/^"|"$/g, ''))
  const iNeed = header.indexOf('need_id')
  const iCand = header.indexOf('candidate_id')
  const iRel = header.indexOf('relevant')
  if (iNeed < 0 || iCand < 0) return { error: 'Нужны колонки need_id и candidate_id (relevant — необязательно)' }

  const needs = col<NeedRow>('needs')
  const candidates = col<CandidateRow>('candidates')
  const groups = new Map<string, Array<{ cand: string; rel: number }>>()
  for (const line of lines.slice(1)) {
    const cells = line.split(sep).map((c) => c.trim().replace(/^"|"$/g, ''))
    const needId = cells[iNeed]
    const candId = cells[iCand]
    if (!needId || !candId) continue
    let rel: number
    if (iRel >= 0 && cells[iRel] !== undefined && cells[iRel] !== '') {
      rel = Number(cells[iRel]) > 0 ? 1 : 0
    } else {
      // Без разметки: релевантен, если категория кандидата совпала с категорией потребности.
      const need = needs.find((n) => String(n.id) === needId)
      const cand = candidates.find((c) => String(c.id) === candId)
      rel = need && cand && need.category === cand.category ? 1 : 0
    }
    if (!groups.has(needId)) groups.set(needId, [])
    groups.get(needId)!.push({ cand: candId, rel })
  }
  if (!groups.size) return { error: 'Не нашлось ни одной пары need_id — candidate_id' }

  const dcg = (rels: number[]) => rels.reduce((s, r, i) => s + r / Math.log2(i + 2), 0)
  const metrics = (rows: Array<{ rel: number }>, all: Array<{ rel: number }>) => {
    const top = rows.slice(0, 10).map((r) => r.rel)
    const ideal = all.map((r) => r.rel).sort((a, b) => b - a).slice(0, 10)
    const idcg = dcg(ideal)
    return { p: top.length ? top.reduce((s, r) => s + r, 0) / top.length : 0, ndcg: idcg > 0 ? dcg(top) / idcg : 0 }
  }
  // Базовая линия «поиск по ключевым словам»: порядок по числу совпавших технологий стека.
  const overlap = (needId: string, candId: string) => {
    const need = needs.find((n) => String(n.id) === needId)
    const cand = candidates.find((c) => String(c.id) === candId)
    if (!need || !cand) return 0
    const want = new Set([...need.skills_required, ...need.skills_desired])
    return cand.stack.filter((s) => want.has(s)).length
  }

  const perNeed: S['NeedMetrics'][] = []
  let sumP = 0
  let sumN = 0
  let sumBP = 0
  let sumBN = 0
  let relTop = 0
  let relAll = 0
  let pairs = 0
  for (const [needId, rows] of groups) {
    pairs += rows.length
    const m = metrics(rows, rows)
    const baselineOrder = [...rows].sort((a, b) => overlap(needId, b.cand) - overlap(needId, a.cand))
    const b = metrics(baselineOrder, rows)
    const relevantTotal = rows.reduce((s, r) => s + r.rel, 0)
    relAll += relevantTotal
    relTop += rows.slice(0, 10).reduce((s, r) => s + r.rel, 0)
    sumP += m.p
    sumN += m.ndcg
    sumBP += b.p
    sumBN += b.ndcg
    perNeed.push({ need_id: needId, precision_at_10: round(m.p, 3), ndcg_at_10: round(m.ndcg, 3), relevant_total: relevantTotal })
  }
  const n = groups.size
  return {
    filename,
    pairs_count: pairs,
    needs_count: n,
    precision_at_10: round(sumP / n, 3),
    ndcg_at_10: round(sumN / n, 3),
    relevant_in_top_share: relAll ? round(relTop / relAll, 3) : 0,
    baseline_precision_at_10: round(sumBP / n, 3),
    baseline_ndcg_at_10: round(sumBN / n, 3),
    per_need: perNeed,
    is_stub: true,
  }
}

// --- Настройки ---------------------------------------------------------------------------------
type Upd = S['PlatformSettingsUpdate']

/** Проверки PUT /api/admin/settings как у бэкенда: pydantic-границы, затем invalid_thresholds / invalid_weights. */
function validateSettings(body: Upd): Response | null {
  const errors: FieldError[] = []
  const range = (key: keyof Upd, min: number, max: number, int: boolean, minExclusive = false) => {
    const v = body[key]
    if (v == null) return
    if (typeof v !== 'number' || (int && !Number.isInteger(v))) errors.push({ field: key, type: int ? 'int_type' : 'float_type', msg: 'Input should be a valid number' })
    else if (minExclusive ? v <= min : v < min)
      errors.push(minExclusive ? { field: key, type: 'greater_than', msg: `Input should be greater than ${min}`, ctx: { gt: min } } : { field: key, type: 'greater_than_equal', msg: `Input should be greater than or equal to ${min}`, ctx: { ge: min } })
    else if (v > max) errors.push({ field: key, type: 'less_than_equal', msg: `Input should be less than or equal to ${max}`, ctx: { le: max } })
  }
  range('grade_change_cooldown_days', 0, 365, true)
  range('retry_cooldown_days', 0, 365, true)
  range('invitation_quota', 1, 500, true)
  range('invitation_ttl_days', 1, 60, true)
  range('cat_max_items', 5, 50, true)
  range('cat_se_stop', 0, 2, false, true)
  range('exposure_max_share', 0, 1, false, true)
  if (body.ranking_weights && Object.values(body.ranking_weights).some((x) => typeof x !== 'number' || x < 0))
    errors.push({ field: 'ranking_weights', type: 'greater_than_equal', msg: 'Input should be greater than or equal to 0', ctx: { ge: 0 } })
  if (errors.length) return validationError(errors)
  for (const t of body.grade_thresholds ?? []) {
    if (!(t.junior_from < t.middle_from && t.middle_from < t.senior_from))
      return apiError(422, 'invalid_thresholds', 'Пороги θ должны возрастать: junior < middle < senior', { specialization: t.specialization })
  }
  if (body.ranking_weights && Object.values(body.ranking_weights).reduce((sum, x) => sum + x, 0) <= 0)
    return apiError(422, 'invalid_weights', 'Хотя бы один вес ранжирования должен быть больше нуля')
  return null
}

/** Проверки SkillUpsert как у бэкенда (pydantic). */
function validateSkill(body: S['SkillUpsert']): Response | null {
  const errors: FieldError[] = []
  if (!/^[a-z0-9_+.#-]+$/.test(body.id ?? '') || (body.id ?? '').length > 40)
    errors.push({ field: 'id', type: 'string_pattern_mismatch', msg: "String should match pattern '^[a-z0-9_+.#-]+$'" })
  if (!body.label?.trim()) errors.push({ field: 'label', type: 'string_too_short', msg: 'String should have at least 1 character', ctx: { min_length: 1 } })
  if (!body.specializations?.length) errors.push({ field: 'specializations', type: 'too_short', msg: 'List should have at least 1 item after validation, not 0', ctx: { min_length: 1 } })
  return errors.length ? validationError(errors) : null
}

const SETTINGS_LABELS: Record<string, string> = {
  grade_thresholds: 'пороги θ',
  grade_change_cooldown_days: 'кулдаун смены грейда',
  retry_cooldown_days: 'кулдаун повтора',
  invitation_quota: 'квота приглашений',
  invitation_ttl_days: 'срок приглашения',
  cat_se_stop: 'точность остановки теста',
  cat_max_items: 'максимум задач',
  exposure_max_share: 'лимит показов задачи',
  ranking_weights: 'веса ранжирования',
}

// --- Хендлеры ----------------------------------------------------------------------------------
export const adminHandlers: HttpHandler[] = [
  // Дашборд
  http.get('/api/admin/dashboard', adminGet(buildDashboard, () => EMPTY_DASHBOARD)),

  // Пользователи
  http.get(
    '/api/admin/users',
    adminGet(
      ({ request }) => {
        const url = new URL(request.url)
        const q = url.searchParams.get('q')?.trim().toLowerCase()
        const role = url.searchParams.get('role')
        const blocked = url.searchParams.get('blocked')
        const rows = col<UserRecord>('users').filter(
          (u) =>
            (!q || u.email.toLowerCase().includes(q) || u.full_name.toLowerCase().includes(q)) &&
            (!role || u.role === role) &&
            (blocked == null || blocked === '' || Boolean(u.blocked) === (blocked === 'true')),
        )
        return pageOf(rows, url)
      },
      () => ({ items: [], total: 0, page: 1, page_size: 50 }),
    ),
  ),
  http.patch(
    '/api/admin/users/:id',
    adminWrite(async ({ request, params }) => {
      const id = Number(params.id)
      const user = col<UserRecord>('users').find((u) => u.id === id)
      if (!user) return notFound()
      const body = (await request.json()) as S['AdminUserUpdate']
      const me = demoUser(request).userId
      if (id === me && (body.blocked === true || (body.role && body.role !== 'admin')))
        return apiError(409, 'cannot_change_self', 'Нельзя заблокировать или понизить себя')
      if (body.role && body.role !== user.role) {
        const from = user.role
        user.role = body.role
        addAudit(request, 'user_role_changed', 'user', id, `Роль изменена: ${ROLE_LABEL[from]} → ${ROLE_LABEL[body.role]}`, { role: [from, body.role] })
      }
      if (body.blocked != null && body.blocked !== Boolean(user.blocked)) {
        user.blocked = body.blocked
        addAudit(
          request,
          body.blocked ? 'user_blocked' : 'user_unblocked',
          'user',
          id,
          `${body.blocked ? 'Заблокирован' : 'Разблокирован'} пользователь ${user.full_name} (${user.email})`,
        )
      }
      db.save()
      return HttpResponse.json(user)
    }),
  ),
  http.get(
    '/api/admin/users/:id/audit',
    adminGet(
      ({ params }) => {
        const id = Number(params.id)
        const candidate = col<CandidateRow>('candidates').find((c) => c.user_id === id)
        return col<AuditEntry>('audit_log')
          .filter(
            (e) =>
              (e.target_type === 'user' && e.target_id === id) ||
              e.actor_user_id === id ||
              (candidate != null &&
                ((e.target_type === 'candidate' && e.target_id === candidate.id) || e.details?.candidate_id === candidate.id)),
          )
          .sort(byDateDesc)
      },
      () => [],
    ),
  ),

  // Компании
  http.get('/api/admin/companies', adminGet(() => col<CompanyRow>('companies').map(adminCompany), () => [])),
  http.patch(
    '/api/admin/companies/:id',
    adminWrite(async ({ request, params }) => {
      const company = col<CompanyRow>('companies').find((c) => c.id === Number(params.id))
      if (!company) return notFound()
      const body = (await request.json()) as S['CompanyAdminUpdate']
      if (typeof body.blocked !== 'boolean') return apiError(422, 'validation_error', 'Ошибка валидации данных', { blocked: 'Нужно true или false' })
      if (body.blocked !== Boolean(company.blocked)) {
        company.blocked = body.blocked
        addAudit(request, body.blocked ? 'company_blocked' : 'company_unblocked', 'company', company.id,
          `${body.blocked ? 'Заблокирована' : 'Разблокирована'} компания «${company.name}»`)
        db.save()
      }
      return HttpResponse.json(adminCompany(company))
    }),
  ),

  // Настройки
  http.get('/api/admin/settings', adminGet(() => col<PlatformSettings>('platform_settings')[0])),
  http.put(
    '/api/admin/settings',
    adminWrite(async ({ request }) => {
      const body = (await request.json()) as Upd
      const invalid = validateSettings(body)
      if (invalid) return invalid
      const settings = col<PlatformSettings>('platform_settings')[0]
      const changed: string[] = []
      for (const [key, value] of Object.entries(body)) {
        if (value == null || !(key in SETTINGS_LABELS)) continue
        if (JSON.stringify((settings as unknown as Record<string, unknown>)[key]) === JSON.stringify(value)) continue
        ;(settings as unknown as Record<string, unknown>)[key] = value
        changed.push(key)
      }
      if (changed.length) {
        addAudit(request, 'settings_updated', 'settings', null, `Изменены настройки: ${changed.map((k) => SETTINGS_LABELS[k]).join(', ')}`, { fields: changed })
        db.save()
      }
      return HttpResponse.json(settings)
    }),
  ),

  // Справочники (общие GET — только для админа)
  http.get('/api/catalog/specializations', adminGet(() => col<S['Specialization']>('specializations'), undefined, true)),
  http.get('/api/catalog/grades', adminGet(() => col<S['Grade']>('grades'), undefined, true)),
  http.get(
    '/api/catalog/topics',
    adminGet(({ request }) => {
      const spec = new URL(request.url).searchParams.get('specialization')
      return col<Topic>('topics').filter((t) => !spec || t.specialization === spec)
    }, undefined, true),
  ),
  http.get(
    '/api/catalog/skills',
    adminGet(({ request }) => {
      const url = new URL(request.url)
      const spec = url.searchParams.get('specialization')
      const q = url.searchParams.get('q')?.trim().toLowerCase()
      return col<Skill>('skills').filter(
        (s) => (!spec || s.specializations.includes(spec as SpecCode)) && (!q || s.label.toLowerCase().includes(q) || s.id.includes(q)),
      )
    }, () => [], true),
  ),
  http.patch(
    '/api/admin/catalog/specializations/:id',
    adminWrite(async ({ request, params }) => {
      const spec = col<S['Specialization']>('specializations').find((s) => s.id === params.id)
      if (!spec) return notFound()
      const body = (await request.json()) as S['CatalogLabelUpdate']
      if (!body.label?.trim()) return apiError(422, 'validation_error', 'Ошибка валидации данных', { label: 'Подпись не может быть пустой' })
      spec.label = body.label.trim()
      if (body.description != null) spec.description = body.description
      if (body.active != null) spec.active = body.active
      addAudit(request, 'catalog_updated', 'specialization', null, `Изменена специализация «${spec.label}»${spec.active === false ? ', скрыта' : ''}`, { id: spec.id })
      db.save()
      return HttpResponse.json(spec)
    }),
  ),
  http.patch(
    '/api/admin/catalog/grades/:id',
    adminWrite(async ({ request, params }) => {
      const grade = col<S['Grade']>('grades').find((g) => g.id === params.id)
      if (!grade) return notFound()
      const body = (await request.json()) as S['CatalogLabelUpdate']
      if (!body.label?.trim()) return apiError(422, 'validation_error', 'Ошибка валидации данных', { label: 'Подпись не может быть пустой' })
      grade.label = body.label.trim()
      addAudit(request, 'catalog_updated', 'grade', null, `Изменена подпись грейда: ${grade.label}`, { id: grade.id })
      db.save()
      return HttpResponse.json(grade)
    }),
  ),
  http.post(
    '/api/admin/catalog/skills',
    adminWrite(async ({ request }) => {
      const body = (await request.json()) as S['SkillUpsert']
      const invalid = validateSkill(body)
      if (invalid) return invalid
      if (col<Skill>('skills').some((s) => s.id === body.id)) return apiError(409, 'skill_exists', 'Такая технология уже есть', { id: body.id })
      const skill: Skill = { id: body.id, label: body.label.trim(), specializations: body.specializations }
      col<Skill>('skills').push(skill)
      addAudit(request, 'catalog_created', 'skill', null, `Добавлена технология «${skill.label}»`, { id: skill.id })
      db.save()
      return HttpResponse.json(skill, { status: 201 })
    }),
  ),
  http.put(
    '/api/admin/catalog/skills/:id',
    adminWrite(async ({ request, params }) => {
      const skill = col<Skill>('skills').find((s) => s.id === params.id)
      if (!skill) return notFound()
      const body = (await request.json()) as S['SkillUpsert']
      const invalid = validateSkill(body)
      if (invalid) return invalid
      if (body.id !== skill.id) return apiError(422, 'id_mismatch', 'Код технологии менять нельзя', { id: skill.id, new: body.id })
      skill.label = body.label.trim()
      skill.specializations = body.specializations
      addAudit(request, 'catalog_updated', 'skill', null, `Изменена технология «${skill.label}»`, { id: skill.id })
      db.save()
      return HttpResponse.json(skill)
    }),
  ),
  http.delete(
    '/api/admin/catalog/skills/:id',
    adminWrite(({ request, params }) => {
      const id = String(params.id)
      const skills = col<Skill>('skills')
      const idx = skills.findIndex((s) => s.id === id)
      if (idx < 0) return notFound()
      const inUse =
        col<CandidateRow>('candidates').some((c) => c.stack.includes(id)) ||
        col<{ skills_required: string[]; skills_desired: string[] }>('vacancies').some(
          (v) => v.skills_required.includes(id) || v.skills_desired.includes(id),
        ) ||
        col<NeedRow>('needs').some((n) => n.skills_required.includes(id) || n.skills_desired.includes(id))
      if (inUse) return apiError(409, 'skill_in_use', 'Технология используется в профилях, вакансиях или потребностях', { id })
      const [removed] = skills.splice(idx, 1)
      addAudit(request, 'catalog_deleted', 'skill', null, `Удалена технология «${removed.label}»`, { id })
      db.save()
      return new HttpResponse(null, { status: 204 })
    }),
  ),

  // Темы теста
  http.post(
    '/api/admin/catalog/topics',
    adminWrite(async ({ request }) => {
      const body = (await request.json()) as S['TopicCreate']
      const errors: FieldError[] = []
      if (!/^[a-z_]+\.[a-z0-9_]+$/.test(body.id ?? '') || (body.id ?? '').length > 64)
        errors.push({ field: 'id', type: 'string_pattern_mismatch', msg: "String should match pattern '^[a-z_]+\\.[a-z0-9_]+$'" })
      if (!body.label?.trim()) errors.push({ field: 'label', type: 'string_too_short', msg: 'String should have at least 1 character', ctx: { min_length: 1 } })
      if (errors.length) return validationError(errors)
      if (!SPECS.includes(body.specialization)) return notFound()
      if (!body.id.startsWith(`${body.specialization}.`))
        return apiError(422, 'topic_code_invalid', 'Код темы начинается с кода специализации: <специализация>.<тема>', { id: body.id, specialization: body.specialization })
      if (col<Topic>('topics').some((t) => t.id === body.id)) return apiError(409, 'topic_exists', 'Такая тема уже есть', { id: body.id })
      const topic: Topic = { id: body.id, specialization: body.specialization, label: body.label.trim() }
      col<Topic>('topics').push(topic)
      addAudit(request, 'catalog_created', 'topic', null, `Добавлена тема «${topic.label}»`, { id: topic.id })
      db.save()
      return HttpResponse.json(topic, { status: 201 })
    }),
  ),
  http.patch(
    '/api/admin/catalog/topics/:id',
    adminWrite(async ({ request, params }) => {
      const topic = col<Topic>('topics').find((t) => t.id === params.id)
      if (!topic) return notFound()
      const body = (await request.json()) as S['LabelUpdate']
      if (!body.label?.trim()) return validationError([{ field: 'label', type: 'string_too_short', msg: 'String should have at least 1 character', ctx: { min_length: 1 } }])
      topic.label = body.label.trim()
      addAudit(request, 'catalog_updated', 'topic', null, `Изменена тема «${topic.label}»`, { id: topic.id })
      db.save()
      return HttpResponse.json(topic)
    }),
  ),
  http.delete(
    '/api/admin/catalog/topics/:id',
    adminWrite(({ request, params }) => {
      const topics = col<Topic>('topics')
      const idx = topics.findIndex((t) => t.id === params.id)
      if (idx < 0) return notFound()
      const items = col<ItemDetail>('items').filter((i) => i.topic === params.id).length
      if (items) return apiError(409, 'topic_in_use', 'По теме есть шаблоны задач — сначала перенесите или выведите их', { id: params.id, usage: { items } })
      const [removed] = topics.splice(idx, 1)
      addAudit(request, 'catalog_deleted', 'topic', null, `Удалена тема «${removed.label}»`, { id: removed.id })
      db.save()
      return new HttpResponse(null, { status: 204 })
    }),
  ),

  // Банк задач
  http.get(
    '/api/admin/items',
    adminGet(
      ({ request }) => {
        const url = new URL(request.url)
        const p = url.searchParams
        const leak = p.get('leak_flag')
        const rows = col<ItemDetail>('items')
          .filter(
            (i) =>
              (!p.get('specialization') || i.specialization === p.get('specialization')) &&
              (!p.get('topic') || i.topic === p.get('topic')) &&
              (!p.get('status') || i.status === p.get('status')) &&
              (leak == null || leak === '' || i.leak_flag === (leak === 'true')),
          )
          .map(summary)
        return pageOf(rows, url)
      },
      () => ({ items: [], total: 0, page: 1, page_size: 50 }),
    ),
  ),
  http.get('/api/admin/items/coverage', adminGet(buildCoverage, () => [])),
  http.post(
    '/api/admin/items/recalibrate',
    adminWrite(({ request }) => {
      const result = recalibrate()
      addAudit(request, 'items_recalibrated', 'item', null,
        `Пересчитана калибровка: изменено ${result.items_recalibrated}, переведено из пилота ${result.pilot_promoted}`)
      db.save()
      return HttpResponse.json(result)
    }),
  ),
  http.get(
    '/api/admin/items/:id',
    async (info) => {
      if (demoUser(info.request).role !== 'admin') return forbidden()
      const item = col<ItemDetail>('items').find((i) => i.id === Number(info.params.id))
      if (!item) {
        await mockLatency()
        return notFound()
      }
      return withScenario({ data: () => item })(info)
    },
  ),
  http.post(
    '/api/admin/items/:id/retire',
    adminWrite(({ request, params }) => {
      const item = col<ItemDetail>('items').find((i) => i.id === Number(params.id))
      if (!item) return notFound()
      if (item.status === 'retired') return apiError(409, 'invalid_transition', 'Шаблон уже выведен из оборота')
      item.status = 'retired'
      addAudit(request, 'item_retired', 'item', item.id, `Шаблон «${item.title}» выведен из оборота`,
        item.leak_flag ? { reason: 'leak', leak_score: item.leak_score } : {})
      db.save()
      return HttpResponse.json(item)
    }),
  ),
  http.post(
    '/api/admin/items/:id/approve',
    adminWrite(({ request, params }) => {
      const item = col<ItemDetail>('items').find((i) => i.id === Number(params.id))
      if (!item) return notFound()
      if (item.status !== 'draft') return apiError(409, 'invalid_transition', 'Одобрить можно только черновик')
      item.status = 'pilot'
      addAudit(request, 'item_approved', 'item', item.id, `Черновик «${item.title}» одобрен: пилот, на балл не влияет`)
      db.save()
      return HttpResponse.json(item)
    }),
  ),

  // Задания из вакансий
  http.get(
    '/api/admin/vacancy-tests',
    adminGet(() => [...col<VacancyTestResult>('vacancy_tests')].sort((a, b) => b.id - a.id), () => []),
  ),
  http.post(
    '/api/admin/vacancy-tests',
    adminWrite(async ({ request }) => {
      const body = (await request.json()) as S['VacancyTestRequest']
      const text = (body.text ?? '').trim()
      if (text.length < 20) return apiError(422, 'validation_error', 'Ошибка валидации данных', { text: 'Нужно хотя бы 20 символов текста вакансии' })
      if (text.length > 20000) return apiError(422, 'validation_error', 'Ошибка валидации данных', { text: 'Не больше 20 000 символов' })
      const result = buildVacancyTest(text, body.specialization)
      db.save()
      return HttpResponse.json(result)
    }),
  ),

  // Жалобы
  http.get(
    '/api/admin/reports',
    adminGet(({ request }) => {
      const status = new URL(request.url).searchParams.get('status')
      const order: Record<string, number> = { new: 0, in_review: 1, resolved: 2, rejected: 3 }
      return col<Report>('reports')
        .filter((r) => !status || r.status === status)
        .sort((a, b) => order[a.status] - order[b.status] || b.created_at.localeCompare(a.created_at))
    }, () => []),
  ),
  http.patch(
    '/api/admin/reports/:id',
    adminWrite(async ({ request, params }) => {
      const report = col<Report>('reports').find((r) => r.id === Number(params.id))
      if (!report) return notFound()
      const body = (await request.json()) as S['ReportUpdate']
      if (!['new', 'in_review', 'resolved', 'rejected'].includes(body.status))
        return apiError(422, 'validation_error', 'Ошибка валидации данных', { status: 'Неизвестный статус' })
      report.status = body.status
      if (body.resolution != null) report.resolution = body.resolution
      const done = body.status === 'resolved' || body.status === 'rejected'
      report.resolved_at = done ? db.now() : null
      if (done)
        addAudit(request, 'report_resolved', 'report', report.id,
          `Жалоба на «${report.company_name}» ${body.status === 'resolved' ? 'решена' : 'отклонена'}${body.resolution ? `: ${body.resolution}` : ''}`)
      db.save()
      return HttpResponse.json(report)
    }),
  ),

  // Журнал
  http.get(
    '/api/admin/audit',
    adminGet(
      ({ request }) => {
        const url = new URL(request.url)
        const action = url.searchParams.get('action')
        const target = url.searchParams.get('target_type')
        const rows = col<AuditEntry>('audit_log')
          .filter((e) => (!action || e.action === action) && (!target || e.target_type === target))
          .sort(byDateDesc)
        return pageOf(rows, url)
      },
      () => ({ items: [], total: 0, page: 1, page_size: 50 }),
    ),
  ),

  // Валидация (общий путь — только для админа)
  http.get(
    '/api/eval/validation',
    adminGet(() => ({ charts: buildCharts(), generated_at: '2026-10-06T09:00:00+03:00', seed: VALIDATION_SEED }),
      () => ({ charts: [], generated_at: '2026-10-06T09:00:00+03:00', seed: VALIDATION_SEED }), true),
  ),
  http.get('/api/eval/charts/:id', async (info) => {
    if (demoUser(info.request).role !== 'admin') return undefined
    const chart = buildCharts().find((c) => c.id === info.params.id)
    if (!chart) {
      await mockLatency()
      return notFound()
    }
    return withScenario({ data: () => chart })(info)
  }),
  http.post(
    '/api/eval/matching',
    adminWrite(async ({ request }) => {
      const form = await request.formData()
      const file = form.get('file')
      if (!file || typeof file === 'string') return apiError(422, 'validation_error', 'Ошибка валидации данных', { file: 'Прикрепите CSV-файл' })
      if (file.size > 10 * 1024 * 1024) return apiError(413, 'file_too_large', 'Файл больше 10 МБ')
      const result = evaluateMatchingCsv(file.name, await file.text())
      if ('error' in result) return apiError(422, 'validation_error', result.error, { file: result.error })
      return HttpResponse.json(result)
    }, true),
  ),
]
