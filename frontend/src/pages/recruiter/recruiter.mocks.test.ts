import { getResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { recruiterHandlers, parseNeedText } from '@/mocks/handlers/recruiter'
import { db } from '@/mocks/db'
import { api, setApiRole, type ApiError } from '@/shared/api'
import type { AnonymousProfile, Invitation, InvitationQuota, MatchList, S } from './api'

/**
 * Моки кабинета рекрутера: правила видимости, вилка, квота, статусы, подборка.
 * Кандидат 32 (Backend · Middle, ожидания 230 000 ₽) не связан с компанией 1 — контакты закрыты.
 */
const server = setupServer(...recruiterHandlers)
const CAND = 32
const SECRET = { name: 'Виктория Степанова', email: 'v.stepanova.32@example.com', phone: '132-33-26', telegram: 'example_viktoriya32' }

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())
beforeEach(() => {
  db.reset()
  setApiRole('recruiter', 41)
})

async function apiError(p: Promise<unknown>): Promise<ApiError> {
  try {
    await p
  } catch (e) {
    return e as ApiError
  }
  throw new Error('ожидалась ошибка')
}

const invite = (over: Partial<S['InvitationCreate']> = {}) =>
  api.post<Invitation>('/invitations', {
    candidate_id: CAND,
    description: 'Приглашаем в команду платёжного шлюза.',
    salary_from: 240000,
    salary_to: 300000,
    contact_method: { type: 'email', value: 'recruiter@example.com' },
    ...over,
  })

describe('обезличенный профиль', () => {
  it('до принятия приглашения нет ФИО и контактов', async () => {
    const p = await api.get<AnonymousProfile>(`/candidates/${CAND}`)
    const raw = JSON.stringify(p)
    for (const v of Object.values(SECRET)) expect(raw).not.toContain(v)
    expect(p).not.toHaveProperty('full_name')
    expect(p).not.toHaveProperty('email')
    expect(p).not.toHaveProperty('min_salary')
    expect(p.contacts_visible).toBe(false)
    expect(p.contacts).toBeNull()
    expect(p.pseudonym).toBe('Кандидат #4BF1')
    expect(p.can_invite).toBe(true)
  })

  it('в банке кандидатов и в подборке тоже нет ФИО и контактов', async () => {
    const page = await api.get<S['Page_BankCandidateCard_']>('/candidates', { query: { page_size: 100 } })
    const matches = await api.get<MatchList>('/matching/needs/1/candidates')
    const raw = JSON.stringify(page) + JSON.stringify(matches)
    for (const v of Object.values(SECRET)) expect(raw).not.toContain(v)
    expect(raw).not.toContain('"full_name"')
    expect(raw).not.toContain('"min_salary"')
  })

  it('после принятия приглашения контакты открываются', async () => {
    const inv = await invite()
    // Кандидат принимает (как сделал бы кабинет соискателя).
    const row = (db.data.invitations as unknown as Invitation[]).find((i) => i.id === inv.id)!
    row.status = 'accepted'
    db.save()
    const p = await api.get<AnonymousProfile>(`/candidates/${CAND}`)
    expect(p.contacts_visible).toBe(true)
    expect(p.contacts?.full_name).toBe(SECRET.name)
    const list = await api.get<Invitation[]>('/invitations', { query: { status: 'accepted' } })
    expect(list.find((i) => i.id === inv.id)?.candidate_contacts?.email).toBe(SECRET.email)
  })
})

describe('приглашение', () => {
  it('вилка ниже ожиданий → salary_below_expectations без суммы кандидата', async () => {
    const err = await apiError(invite({ salary_from: 180000, salary_to: 220000 }))
    expect(err.status).toBe(422)
    expect(err.code).toBe('salary_below_expectations')
    const raw = JSON.stringify({ m: err.message, d: err.details })
    expect(raw).not.toMatch(/230\s?000/)
  })

  it('от > до → salary_range_invalid; без вилки → validation_error', async () => {
    expect((await apiError(invite({ salary_from: 300000, salary_to: 250000 }))).code).toBe('salary_range_invalid')
    expect((await apiError(invite({ salary_from: undefined }))).code).toBe('validation_error')
  })

  it('приглашение попадает в общую базу и видно соискателю', async () => {
    const before = db.data.invitations.length
    const inv = await invite({ task_text: 'Как бы вы ускорили медленный API?' })
    expect(inv.status).toBe('sent')
    expect(db.data.invitations).toHaveLength(before + 1)
    const row = (db.data.invitations as unknown as Invitation[]).at(-1)!
    expect(row).toMatchObject({ id: inv.id, candidate_id: CAND, company_id: 1, recruiter_id: 1, status: 'sent', salary_to: 300000 })
    expect(window.localStorage.getItem('fsp.mockDb.v1')).toContain(`"candidate_id":${CAND}`)
    expect((db.data.invitation_events as unknown as S['InvitationEvent'][]).some((e) => e.invitation_id === inv.id && e.type === 'created')).toBe(true)
    // Повторное — уже есть активное.
    expect((await apiError(invite())).code).toBe('already_invited')
  })

  it('квота: при 20 активных — quota_exceeded', async () => {
    const rows = db.data.invitations as unknown as Invitation[]
    const template = rows.find((i) => i.recruiter_id === 1)!
    let used = rows.filter((i) => i.recruiter_id === 1 && (i.status === 'sent' || i.status === 'viewed')).length
    while (used < 20) {
      rows.push({ ...template, id: 1000 + used, candidate_id: 9000 + used, status: 'sent', expires_at: '2099-01-01T00:00:00Z' })
      used++
    }
    db.save()
    const q = await api.get<InvitationQuota>('/invitations/quota')
    expect(q).toMatchObject({ limit: 20, used: 20, left: 0 })
    expect(q.hint).toBeTruthy()
    const err = await apiError(invite())
    expect(err.status).toBe(409)
    expect(err.code).toBe('quota_exceeded')
  })

  it('отзыв: отправленное → отозвано, повторно → 409', async () => {
    const inv = await invite()
    const w = await api.post<Invitation>(`/invitations/${inv.id}/withdraw`)
    expect(w.status).toBe('withdrawn')
    const err = await apiError(api.post(`/invitations/${inv.id}/withdraw`))
    expect(err.status).toBe(409)
    expect(err.code).toBe('invalid_transition')
  })

  it('рыночная подсказка меняется от вилки', async () => {
    const low = await api.get<S['MarketHint']>('/invitations/market-hint', { query: { category: 'backend:middle', salary_from: 100000, salary_to: 150000 } })
    const high = await api.get<S['MarketHint']>('/invitations/market-hint', { query: { category: 'backend:middle', salary_from: 250000, salary_to: 320000 } })
    expect(low.median_accepted_from).toBeGreaterThan(0)
    expect(high.acceptance_probability!).toBeGreaterThan(low.acceptance_probability!)
    expect(high.message).toContain('обычно принимают от')
  })
})

describe('подборка', () => {
  it('фильтры сужают, без фильтров — исходный список', async () => {
    const all = await api.get<MatchList>('/matching/needs/1/candidates')
    expect(all.total).toBe(all.total_before_filters)
    expect(all.total).toBeGreaterThan(1)
    const narrowed = await api.get<MatchList>('/matching/needs/1/candidates', { query: { skills: ['kafka'] } })
    expect(narrowed.total_before_filters).toBe(all.total)
    expect(narrowed.total).toBeLessThan(all.total)
    expect(narrowed.items.every((m) => m.candidate.stack.includes('kafka'))).toBe(true)
    const again = await api.get<MatchList>('/matching/needs/1/candidates')
    expect(again.items.map((m) => m.candidate.id)).toEqual(all.items.map((m) => m.candidate.id))
  })

  it('у каждого 2–4 причины, счёт = сумма вкладов, выдача по убыванию', async () => {
    const res = await api.get<MatchList>('/matching/needs/1/candidates', { query: { category: 'backend:junior' } })
    expect(res.items.length).toBeGreaterThan(0)
    for (const m of res.items) {
      expect(m.reasons.length).toBeGreaterThanOrEqual(2)
      expect(m.reasons.length).toBeLessThanOrEqual(4)
      const sum = m.breakdown.reduce((s, b) => s + b.value * b.weight, 0)
      expect(Math.abs(sum - m.score)).toBeLessThan(0.02)
    }
    const scores = res.items.map((m) => m.score)
    expect([...scores].sort((a, b) => b - a)).toEqual(scores)
  })

  it('рекомендованные категории: основная, грейд ±1, смежные — с числом кандидатов', async () => {
    const cats = await api.get<S['RecommendedCategory'][]>('/matching/needs/1/categories')
    expect(cats[0]).toMatchObject({ category: 'backend:middle', relation: 'primary' })
    expect(cats.map((c) => c.relation)).toEqual(expect.arrayContaining(['grade_lower', 'grade_higher', 'adjacent_specialization']))
    expect(cats.every((c) => typeof c.candidates_count === 'number')).toBe(true)
  })
})

describe('разбор свободного текста', () => {
  it.each([
    ['Нужен сеньор на Go в финтех, удалёнка, 300–400к', { specialization: 'backend', grade: 'senior', work_format: 'remote', salary_from: 300000, salary_to: 400000 }, ['go']],
    ['Ищем мидл фронтендера на React и TypeScript, гибрид в Москве, 200–260 тыс. Желательно Next.js', { specialization: 'frontend', grade: 'middle', work_format: 'hybrid', city: 'Москва', salary_from: 200000, salary_to: 260000 }, ['react', 'typescript']],
    ['Джун тестировщик: автотесты на Python и pytest, офис в Казани, до 120к', { specialization: 'qa', grade: 'junior', work_format: 'office', city: 'Казань', salary_to: 120000 }, ['python', 'pytest']],
    ['DevOps middle, Kubernetes, Terraform, от 250 000 до 320 000 ₽', { specialization: 'devops', grade: 'middle', salary_from: 250000, salary_to: 320000 }, ['kubernetes', 'terraform']],
  ])('%s', (text, expected, skills) => {
    const r = parseNeedText(text)
    expect(r.draft).toMatchObject(expected)
    expect(r.draft.skills_required).toEqual(expect.arrayContaining(skills))
  })

  it('желательный стек отделяется', () => {
    expect(parseNeedText('Мидл фронтенд на React, желательно Next.js').draft.skills_desired).toContain('nextjs')
  })
})

describe('роли', () => {
  it('запрос не рекрутера хендлер пропускает дальше (undefined)', async () => {
    const req = (role: string) =>
      new Request('http://localhost:3000/api/invitations', { headers: { 'X-Demo-Role': role, 'X-Demo-User-Id': '1' } })
    expect(await getResponse(recruiterHandlers, req('candidate'))).toBeUndefined()
    expect(await getResponse(recruiterHandlers, req('recruiter'))).toBeInstanceOf(Response)
  })
})

describe('код приглашения в компанию', () => {
  it('администратор выпускает новый код, старый больше не приходит', async () => {
    const before = await api.get<S['MyCompany']>('/companies/my')
    expect(before.invite_code).toMatch(/^FSP-C001-/)
    const fresh = await api.post<S['MyCompany']>('/companies/my/invite-code')
    expect(fresh.invite_code).toMatch(/^FSP-C001-/)
    expect(fresh.invite_code).not.toBe(before.invite_code)
    expect((await api.get<S['MyCompany']>('/companies/my')).invite_code).toBe(fresh.invite_code)
  })

  it('обычный рекрутер кода не видит и выпустить не может', async () => {
    setApiRole('recruiter', 42)
    expect(await api.get<S['MyCompany']>('/companies/my')).not.toHaveProperty('invite_code')
    expect((await apiError(api.post('/companies/my/invite-code'))).status).toBe(403)
  })
})

describe('релевантность дисциплин ФСП (E08)', () => {
  it('профиль кандидата: пометка «профильно для …» по его специализации', async () => {
    // кандидат 1: Backend · Middle, лучшее — победа в продуктовом программировании
    const p = await api.get<AnonymousProfile>('/candidates/1')
    expect(p.fsp_profile_note).toMatch(/— профильно для Backend$/)
    // без ФСП — пометки нет
    const none = await api.get<AnonymousProfile>(`/candidates/${CAND}`)
    expect(none.fsp_profile_note ?? null).toBeNull()
  })

  it('подборка: причина ФСП с пометкой, если дисциплина профильная', async () => {
    const list = await api.get<MatchList>('/matching/needs/1/candidates')
    const first = list.items.find((m) => m.candidate.id === 1)!
    expect(first.reasons.some((r) => r.startsWith('Подтверждено ФСП') && r.endsWith('профильно для Backend'))).toBe(true)
  })
})
