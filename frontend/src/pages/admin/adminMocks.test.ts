import { setupServer } from 'msw/node'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { db } from '@/mocks/db'
import { adminHandlers, buildVacancyTest, evaluateMatchingCsv } from '@/mocks/handlers/admin'
import type { ItemDetail, PlatformSettings, VacancyTestResult } from './api'

// Моки админки проверяем настоящими HTTP-запросами через MSW (как в браузере).
const server = setupServer(...adminHandlers)
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }))
afterAll(() => server.close())
beforeEach(() => db.reset())

async function call<T>(method: string, path: string, body?: unknown, role = 'admin'): Promise<{ status: number; data: T }> {
  const res = await fetch(new URL(path, window.location.origin), {
    method,
    headers: { 'Content-Type': 'application/json', 'X-Demo-Role': role, 'X-Demo-User-Id': role === 'admin' ? '48' : '1' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  return { status: res.status, data: (text ? JSON.parse(text) : undefined) as T }
}

const item = (id: number) => (db.data.items as unknown as ItemDetail[]).find((i) => i.id === id)!

describe('моки админки: банк задач', () => {
  it('вывод шаблона из оборота меняет статус в общей базе и пишет журнал', async () => {
    expect(item(28).status).toBe('active')
    const auditBefore = db.data.audit_log.length

    const res = await call<ItemDetail>('POST', '/api/admin/items/28/retire')

    expect(res.status).toBe(200)
    expect(res.data.status).toBe('retired')
    expect(item(28).status).toBe('retired')
    expect(db.data.audit_log.length).toBe(auditBefore + 1)
    expect(db.data.audit_log.at(-1)?.action).toBe('item_retired')
    // Изменение сохранено в localStorage — переживёт перезагрузку страницы.
    expect(window.localStorage.getItem('fsp.mockDb.v1')).toContain('"status":"retired"')

    const again = await call<{ code: string }>('POST', '/api/admin/items/28/retire')
    expect(again.status).toBe(409)
    expect(again.data.code).toBe('invalid_transition')
  })

  it('черновик одобряется в пилот, активный шаблон одобрить нельзя', async () => {
    expect((await call<ItemDetail>('POST', '/api/admin/items/10/approve')).data.status).toBe('pilot')
    expect(item(10).status).toBe('pilot')
    expect((await call('POST', '/api/admin/items/1/approve')).status).toBe(409)
  })

  it('карточка шаблона отдаёт 3 разных варианта', async () => {
    const res = await call<ItemDetail>('GET', '/api/admin/items/3')
    expect(res.data.preview_variants).toHaveLength(3)
    expect(new Set(res.data.preview_variants.map((v) => v.seed)).size).toBe(3)
  })

  it('чужой роли админские пути закрыты', async () => {
    expect((await call('GET', '/api/admin/items', undefined, 'candidate')).status).toBe(403)
  })
})

describe('моки админки: настройки', () => {
  it('изменение квоты и весов сохраняется в platform_settings', async () => {
    const weights = { stack: 0.4, theta: 0.2, fsp: 0.1, freshness: 0.1, salary: 0.1, work_format: 0.1 }
    const res = await call<PlatformSettings>('PUT', '/api/admin/settings', { invitation_quota: 35, ranking_weights: weights })

    expect(res.status).toBe(200)
    expect(res.data.invitation_quota).toBe(35)
    const stored = (db.data.platform_settings as unknown as PlatformSettings[])[0]
    expect(stored.invitation_quota).toBe(35)
    expect(stored.ranking_weights).toEqual(weights)
    expect(stored.grade_change_cooldown_days).toBe(90)

    const reread = await call<PlatformSettings>('GET', '/api/admin/settings')
    expect(reread.data.invitation_quota).toBe(35)
    expect(db.data.audit_log.at(-1)?.action).toBe('settings_updated')
  })

  it('неверные значения отклоняются с понятной ошибкой', async () => {
    const res = await call<{ code: string; details: Record<string, string> }>('PUT', '/api/admin/settings', {
      invitation_quota: 0,
      grade_thresholds: [{ specialization: 'backend', junior_from: 0.5, middle_from: 0, senior_from: 1 }],
    })
    expect(res.status).toBe(422)
    expect(res.data.details.invitation_quota).toBeTruthy()
    expect(res.data.details.grade_thresholds).toBeTruthy()
    expect((db.data.platform_settings as unknown as PlatformSettings[])[0].invitation_quota).toBe(20)
  })
})

describe('моки админки: задания из вакансий', () => {
  it('разбор вакансии выдаёт темы, шаблоны банка и черновик для темы без шаблонов', async () => {
    const text =
      'Ищем Middle Python-разработчика в команду платежей. FastAPI, PostgreSQL, Redis, Kafka. ' +
      'Нужно понимать транзакции, конкурентный доступ и уметь проектировать REST API. Плюсом будет опыт с OAuth 2.0.'
    const itemsBefore = db.data.items.length

    const res = await call<VacancyTestResult>('POST', '/api/admin/vacancy-tests', { text })

    expect(res.status).toBe(200)
    const r = res.data
    expect(r.specialization).toBe('backend')
    expect(r.grade).toBe('middle')
    const topics = r.topics.map((t) => t.topic)
    expect(topics).toEqual(expect.arrayContaining(['backend.http_api', 'backend.databases', 'backend.concurrency', 'backend.security']))
    expect(r.items.map((i) => i.item_id)).toEqual(expect.arrayContaining([1, 2, 3]))
    expect(r.items.every((i) => i.reason.length > 20)).toBe(true)
    expect(r.drafts.map((d) => d.topic)).toContain('backend.security')

    // Черновик появился в банке и его можно одобрить.
    expect(db.data.items.length).toBe(itemsBefore + 1)
    const draft = (db.data.items as unknown as ItemDetail[]).at(-1)!
    expect(draft.status).toBe('draft')
    expect(draft.preview_variants).toHaveLength(3)
    expect((await call<ItemDetail>('POST', `/api/admin/items/${draft.id}/approve`)).data.status).toBe('pilot')

    // Результат попал в историю.
    const list = await call<VacancyTestResult[]>('GET', '/api/admin/vacancy-tests')
    expect(list.data[0].id).toBe(r.id)
  })

  it('повторный разбор не плодит дубли черновиков', () => {
    const text = 'Senior Go-разработчик, gRPC, PostgreSQL, OAuth и JWT, микросервисы.'
    buildVacancyTest(text)
    const n = db.data.items.length
    const again = buildVacancyTest(text)
    expect(db.data.items.length).toBe(n)
    expect(again.grade).toBe('senior')
    expect(again.drafts[0]?.topic).toBe('backend.security')
  })

  it('короткий текст — ошибка валидации', async () => {
    expect((await call('POST', '/api/admin/vacancy-tests', { text: 'мало' })).status).toBe(422)
  })
})

describe('моки админки: метрики подбора по CSV', () => {
  it('считает precision@10 по загруженным парам', () => {
    const csv = 'need_id,candidate_id,relevant\n1,1,1\n1,2,0\n1,3,1\n1,4,1\n2,5,0\n2,6,1\n'
    const r = evaluateMatchingCsv('pairs.csv', csv)
    if ('error' in r) throw new Error(r.error)
    expect(r.pairs_count).toBe(6)
    expect(r.needs_count).toBe(2)
    expect(r.precision_at_10).toBeCloseTo((3 / 4 + 1 / 2) / 2, 3)
    expect(r.relevant_in_top_share).toBe(1)
    expect(r.per_need).toHaveLength(2)
  })

  it('без нужных колонок — понятная ошибка', () => {
    expect(evaluateMatchingCsv('x.csv', 'a,b\n1,2')).toEqual({ error: expect.stringContaining('need_id') })
  })
})
