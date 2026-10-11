import { describe, expect, it } from 'vitest'
import { db } from '@/mocks/db'
import type { components } from '@/shared/api/schema'
import { FALLTHROUGH_STATUS, call, setupMockServer } from './mswTestServer'

type S = components['schemas']

setupMockServer()

const invitation = (id: number) => db.data.invitations.find((i) => i.id === id)!

describe('моки соискателя: приглашения', () => {
  it('принятие меняет статус в общей базе и открывает контакты рекрутера', async () => {
    const res = await call<S['Invitation']>('POST', '/invitations/2/accept')
    expect(res.status).toBe(200)
    expect(res.data.status).toBe('accepted')
    expect(res.data.recruiter_contacts?.email).toBe('m.titova.hr@example.com')
    expect(invitation(2).status).toBe('accepted')
    expect(db.data.invitation_events.some((e) => e.invitation_id === 2 && e.type === 'contacts_revealed')).toBe(true)
    // повторно принять нельзя
    expect((await call('POST', '/invitations/2/accept')).status).toBe(409)
  })

  // №21 — приглашение демо-соискателю со сроком до 20.11.2026 (не истекает на дату проверки)
  it('отклонение сохраняет причину и комментарий', async () => {
    const res = await call<S['Invitation']>('POST', '/invitations/21/decline', {
      body: { reason: 'salary_too_low', comment: 'Жду от 250 000' },
    })
    expect(res.status).toBe(200)
    expect(res.data.decline_reason_label).toBe('Зарплата ниже ожиданий')
    expect(invitation(21).status).toBe('declined')
    expect(invitation(21).decline_reason).toBe('salary_too_low')
    expect(invitation(21).decline_comment).toBe('Жду от 250 000')
  })

  it('без причины или «другое» без комментария — 422', async () => {
    expect((await call('POST', '/invitations/21/decline', { body: {} })).status).toBe(422)
    expect((await call('POST', '/invitations/21/decline', { body: { reason: 'other' } })).status).toBe(422)
    expect(invitation(21).status).toBe('sent')
  })

  it('открытие карточки переводит «отправлено» в «просмотрено»', async () => {
    expect(invitation(2).status).toBe('sent')
    const res = await call<S['InvitationDetail']>('GET', '/invitations/2')
    expect(res.data.status).toBe('viewed')
    expect(res.data.recruiter_contacts).toBeNull()
    expect(invitation(2).status).toBe('viewed')
  })

  it('чужие роли проходят мимо хендлеров соискателя', async () => {
    expect((await call('GET', '/invitations', { role: 'recruiter', userId: 41 })).status).toBe(FALLTHROUGH_STATUS)
    expect((await call('GET', '/invitations/quota', { role: 'candidate' })).status).toBe(FALLTHROUGH_STATUS)
  })
})

describe('моки соискателя: тест и грейд', () => {
  it('кулдаун: тест на грейд выше недоступен 90 дней после смены грейда', async () => {
    const grade = await call<S['CandidateGradeStatus']>('GET', '/testing/grade')
    expect(grade.data.can_test_higher).toBe(false)
    expect(grade.data.higher_available_at).toMatch(/^2026-12-09/)
    const start = await call<{ code: string; details: Record<string, unknown> }>('POST', '/testing/sessions', {
      body: { specialization: 'backend', target_grade: 'senior', kind: 'higher' },
    })
    expect(start.status).toBe(409)
    expect(start.data.code).toBe('cooldown_active')
    expect(start.data.details.reason_code).toBe('grade_change_cooldown')
    expect(String(start.data.details.available_at)).toMatch(/^2026-12-09/)
  })

  it('GET /candidates/me/grade: статус + варианты пересдачи с причиной (как бэкенд)', async () => {
    const grade = await call<S['CandidateGradeStatus']>('GET', '/candidates/me/grade')
    expect(grade.status).toBe(200)
    expect(grade.data.category).toBe('backend:middle')
    expect(grade.data.higher).toMatchObject({ target_grade: 'senior', allowed: false, code: 'grade_change_cooldown' })
    expect(grade.data.higher?.available_at).toMatch(/^2026-12-09/)
    expect(grade.data.lower).toMatchObject({ target_grade: 'junior', allowed: false })
    expect(grade.data.can_test_higher).toBe(false)
  })

  it('адаптивный тест: 12–20 задач, затем категория, θ и интервал', async () => {
    const created = await call<S['TestSessionState']>('POST', '/testing/sessions', {
      body: { specialization: 'backend', target_grade: 'middle', kind: 'placement' },
    })
    expect(created.status).toBe(201)
    const id = created.data.session.id
    let item = created.data.current_item
    const formats = new Set<string>()
    let answered = 0
    while (item) {
      formats.add(item.format)
      const ack = await call<S['AnswerAck']>('POST', `/testing/sessions/${id}/answers`, {
        body: { instance_id: item.instance_id, answer: { choice_ids: ['a'], value: 1, text: 'x', line: 1, order: [] } },
      })
      expect(ack.status).toBe(200)
      answered = ack.data.answered
      item = ack.data.finished ? null : (ack.data.next_item ?? null)
    }
    expect(answered).toBeGreaterThanOrEqual(12)
    expect(answered).toBeLessThanOrEqual(20)
    expect(formats.size).toBeGreaterThanOrEqual(4)
    const result = await call<S['TestResult']>('GET', `/testing/sessions/${id}/result`)
    expect(result.status).toBe(200)
    expect(result.data.category).toMatch(/^backend:/)
    expect(result.data.ci_low).toBeLessThan(result.data.theta)
    expect(result.data.ci_high).toBeGreaterThan(result.data.theta)
    expect(result.data.topic_scores.length).toBeGreaterThan(0)
  }, 30_000)
})

describe('моки соискателя: кандидат без ФСП (user 26)', () => {
  it('статус ФСП нейтральный, достижения пустые, главная и настройки работают', async () => {
    const status = await call<S['FspStatus']>('GET', '/fsp/status', { userId: 26 })
    expect(status.status).toBe(200)
    expect(status.data.linked).toBe(false)
    expect(status.data.has_history).toBe(false)
    expect((await call<unknown[]>('GET', '/fsp/achievements', { userId: 26 })).data).toEqual([])
    const dash = await call<S['CandidateDashboard']>('GET', '/candidates/me/dashboard', { userId: 26 })
    expect(dash.data.fsp_linked).toBe(false)
    expect(dash.data.category).toBe('frontend:junior')
    expect((await call('GET', '/candidates/me/settings', { userId: 26 })).status).toBe(200)
  })

  it('привязка ФСП ID без истории и отвязка', async () => {
    const linked = await call<S['FspStatus']>('POST', '/auth/fsp-link', {
      userId: 26,
      body: { code: 'mock:FSP-000036', state: 's', code_verifier: 'x'.repeat(43), redirect_uri: 'http://localhost/auth/fsp-callback' },
    })
    expect(linked.data.linked).toBe(true)
    expect(linked.data.has_history).toBe(false)
    const taken = await call<{ code: string }>('POST', '/auth/fsp-link', {
      userId: 26,
      body: { code: 'mock:FSP-000001', state: 's', code_verifier: 'x'.repeat(43), redirect_uri: 'x' },
    })
    expect(taken.data.code).toBe('fsp_id_taken')
    expect((await call<S['FspStatus']>('DELETE', '/auth/fsp-link', { userId: 26 })).data.linked).toBe(false)
  })
})

describe('моки соискателя: отклик и задание', () => {
  it('отклик на вакансию создаёт запись, повторный — 409', async () => {
    const res = await call<S['Application']>('POST', '/vacancies/3/applications', { body: { cover_letter: 'Здравствуйте' } })
    expect(res.status).toBe(201)
    expect(db.data.applications.some((a) => a.id === res.data.id && a.candidate_id === 1)).toBe(true)
    expect((await call('POST', '/vacancies/3/applications', { body: {} })).status).toBe(409)
    const list = await call<S['Vacancy'][]>('GET', '/vacancies')
    expect(list.data.find((v) => v.id === 3)?.my_application_id).toBe(res.data.id)
  })

  it('задачи недели: три от разных компаний, ответ на одну снимает остальные', async () => {
    const inbox = await call<S['TaskInbox']>('GET', '/tasks/inbox')
    // в демо-данных у кандидата три задачи недели от трёх компаний
    expect(inbox.data.offers).toHaveLength(3)
    expect(new Set(inbox.data.offers.map((o) => o.company_name)).size).toBe(3)
    const [chosen, ...rest] = inbox.data.offers
    const res = await call<S['TaskSubmission']>('POST', `/tasks/submissions/${chosen.id}/answer`, {
      body: { answer_kind: 'approach', answer_text: 'Кэш с TTL и инвалидация по событию' },
    })
    expect(res.status).toBe(200)
    expect(res.data.status).toBe('submitted')
    expect(rest.map((o) => db.data.task_submissions.find((s) => s.id === o.id)?.status)).toEqual(['skipped', 'skipped'])
    const after = await call<S['TaskInbox']>('GET', '/tasks/inbox')
    expect(after.data.offers).toHaveLength(0)
    expect(after.data.answered_this_week).toBe(true)
  })
})

describe('моки авторизации', () => {
  it('регистрация → вход до подтверждения запрещён → подтверждение → вход', async () => {
    const reg = await call<S['RegisterResponse']>('POST', '/auth/register', {
      role: '',
      body: { email: 'new@example.com', password: 'secret123', full_name: 'Новый Человек', role: 'candidate', consent_processing: true },
    })
    expect(reg.status).toBe(201)
    const early = await call<{ code: string }>('POST', '/auth/login', { role: '', body: { email: 'new@example.com', password: 'secret123' } })
    expect(early.data.code).toBe('email_not_verified')
    expect((await call('POST', '/auth/verify-email', { role: '', body: { token: `mock-verify-${reg.data.user_id}` } })).status).toBe(200)
    const ok = await call<S['TokenResponse']>('POST', '/auth/login', { role: '', body: { email: 'new@example.com', password: 'secret123' } })
    expect(ok.status).toBe(200)
    expect(ok.data.user.role).toBe('candidate')
  })

  it('без согласия на обработку ПДн регистрация невозможна', async () => {
    const res = await call<{ details: { fields: Record<string, string> } }>('POST', '/auth/register', {
      role: '',
      body: { email: 'x@example.com', password: 'secret123', full_name: 'Икс', role: 'candidate', consent_processing: false },
    })
    expect(res.status).toBe(422)
    expect(res.data.details.fields.consent_processing).toBeTruthy()
  })
})

describe('моки соискателя: согласие на публикацию', () => {
  it('PUT /candidates/me/settings/publication меняет согласие и возвращает настройки', async () => {
    const off = await call<S['CandidateSettings']>('PUT', '/candidates/me/settings/publication', { body: { granted: false } })
    expect(off.status).toBe(200)
    expect(off.data.publication_consent).toBe(false)
    const consents = await call<S['Consent'][]>('GET', '/users/me/consents')
    expect(consents.data.find((c) => c.type === 'publication')?.granted).toBe(false)
    const on = await call<S['CandidateSettings']>('PUT', '/candidates/me/settings/publication', { body: { granted: true } })
    expect(on.data.publication_consent).toBe(true)
    expect((await call('PUT', '/candidates/me/settings/publication', { body: {} })).status).toBe(422)
  })
})

describe('моки соискателя: «грейд не подтверждён» (FTT.4)', () => {
  const cand40 = { role: 'candidate' as const, userId: 40 } // QA, без грейда

  it('заявленный грейд — статус unconfirmed, после выбора — на главной и в профиле', async () => {
    const before = await call<S['CandidateProfile']>('GET', '/candidates/me/profile', cand40)
    expect(before.data.grade_status).toBe('none')
    const res = await call<S['CandidateGradeStatus']>('PUT', '/candidates/me/declared-grade', {
      ...cand40,
      body: { specialization: 'qa', grade: 'middle' },
    })
    expect(res.status).toBe(200)
    expect(res.data.grade_status).toBe('unconfirmed')
    expect(res.data.declared_grade).toBe('middle')
    expect(res.data.grade).toBeNull()
    const dashboard = await call<S['CandidateDashboard']>('GET', '/candidates/me/dashboard', cand40)
    expect(dashboard.data.grade_status).toBe('unconfirmed')
    expect(dashboard.data.hints.some((h) => h.includes('Middle не подтверждён'))).toBe(true)
  })

  it('несданный Junior без грейда: категория по уровню теста — один раз', async () => {
    const created = await call<S['TestSessionState']>('POST', '/testing/sessions', {
      ...cand40,
      body: { specialization: 'qa', target_grade: 'junior', kind: 'placement' },
    })
    expect(created.status).toBe(201)
    const id = created.data.session.id
    let item = created.data.current_item
    while (item) {
      const ack = await call<S['AnswerAck']>('POST', `/testing/sessions/${id}/answers`, {
        ...cand40,
        body: { instance_id: item.instance_id, answer: { choice_ids: ['zz'], text: '###', line: 9999, order: ['zz'] } },
      })
      item = ack.data.finished ? null : (ack.data.next_item ?? null)
    }
    const result = await call<S['TestResult']>('GET', `/testing/sessions/${id}/result`, cand40)
    expect(result.data.passed).toBe(false)
    expect(result.data.measured_grade).toBe('intern')
    expect(result.data.can_accept_measured).toBe(true)
    const dash = await call<S['CandidateDashboard']>('GET', '/candidates/me/dashboard', cand40)
    expect(dash.data.measured_offer).toMatchObject({ session_id: id, target_grade: 'junior', grade: 'intern', category: 'qa:intern' })
    const accepted = await call<S['TestResult']>('POST', `/testing/sessions/${id}/accept-measured`, cand40)
    expect(accepted.status).toBe(200)
    expect(accepted.data.measured_accepted).toBe(true)
    const profile = await call<S['CandidateProfile']>('GET', '/candidates/me/profile', cand40)
    expect(profile.data.category).toBe('qa:intern')
    expect(profile.data.grade_status).toBe('confirmed')
    const again = await call<{ code: string }>('POST', `/testing/sessions/${id}/accept-measured`, cand40)
    expect(again.status).toBe(409)
    expect(again.data.code).toBe('measured_already_accepted')
  }, 30_000)

  it('кандидат с грейдом по тесту — confirmed с датой', async () => {
    const profile = await call<S['CandidateProfile']>('GET', '/candidates/me/profile')
    expect(profile.data.grade_status).toBe('confirmed')
    expect(profile.data.grade_confirmed_at).toBeTruthy()
  })
})
