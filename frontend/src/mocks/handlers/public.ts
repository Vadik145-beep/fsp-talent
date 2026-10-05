import { http, HttpResponse, type HttpHandler } from 'msw'
import type { components } from '@/shared/api/schema'
import { db, demoUser } from '../db'
import { apiError, mockLatency, withScenario } from '../utils'

/**
 * Моки публичных запросов (трек 1a): авторизация и справочники.
 * Справочники — без проверки роли (нужны всем кабинетам).
 *
 * Прототип: пароль демо-учёток — demo1234 (data/seed/demo_accounts.json).
 * Новые пользователи после регистрации хранятся в общей базе моков (db.data.users),
 * ссылка из письма — /verify-email?token=mock-verify-<user_id>.
 * ФСП ID: authorize-url ведёт на /auth/fsp-callback?mock_idp=1 — там прототип показывает
 * выбор тестового участника вместо страницы Keycloak; код авторизации — `mock:<FSP-ID>`.
 */

type S = components['schemas']

interface UserRow {
  id: number
  email: string
  role: S['Role']
  full_name: string
  email_verified: boolean
  blocked: boolean
  created_at: string
  last_login_at: string | null
  /** Только для пользователей, зарегистрированных в прототипе. */
  _password?: string
}

interface DemoAccountRow {
  id: number
  role: S['Role']
  email: string
  password: string
  user_id: number
}

const users = () => db.data.users as unknown as UserRow[]
const demoAccounts = () => db.data.demo_accounts as unknown as DemoAccountRow[]

export const MOCK_VERIFY_PREFIX = 'mock-verify-'
export const MOCK_FSP_CODE_PREFIX = 'mock:'

/** Неудачные попытки входа по почте (в памяти вкладки) — для 429. */
const failedLogins = new Map<string, number>()
const MAX_LOGIN_ATTEMPTS = 5

function toMe(user: UserRow): S['Me'] {
  const candidate = (db.data.candidates as unknown as Array<{ id: number; user_id: number; fsp_id?: string | null }>).find(
    (c) => c.user_id === user.id,
  )
  const recruiter = (db.data.recruiters as unknown as Array<{ id: number; user_id: number; company_id: number }>).find(
    (r) => r.user_id === user.id,
  )
  return {
    id: user.id,
    email: user.email,
    role: user.role,
    full_name: user.full_name,
    email_verified: user.email_verified,
    fsp_id: candidate?.fsp_id ?? null,
    candidate_id: candidate?.id ?? null,
    recruiter_id: recruiter?.id ?? null,
    company_id: recruiter?.company_id ?? null,
  }
}

function tokenFor(user: UserRow): S['TokenResponse'] {
  user.last_login_at = db.now()
  db.save()
  return { access_token: `mock-access-${user.id}`, token_type: 'bearer', expires_in: 900, user: toMe(user) }
}

function validationError(fields: Record<string, string>) {
  return apiError(422, 'validation_error', 'Проверьте поля формы', { fields })
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

async function readJson<T>(request: Request): Promise<Partial<T>> {
  try {
    return ((await request.json()) ?? {}) as Partial<T>
  } catch {
    return {}
  }
}

// --- Справочники ------------------------------------------------------------------------
const catalogHandlers: HttpHandler[] = [
  http.get('/api/catalog/specializations', withScenario({ data: () => db.data.specializations })),
  http.get('/api/catalog/grades', withScenario({ data: () => db.data.grades })),
  http.get(
    '/api/catalog/categories',
    withScenario({
      data: ({ request }) => {
        const spec = new URL(request.url).searchParams.get('specialization')
        return db.data.categories.filter((c) => !spec || c.specialization === spec)
      },
    }),
  ),
  http.get(
    '/api/catalog/topics',
    withScenario({
      data: ({ request }) => {
        const spec = new URL(request.url).searchParams.get('specialization')
        return db.data.topics.filter((t) => !spec || t.specialization === spec)
      },
    }),
  ),
  http.get(
    '/api/catalog/skills',
    withScenario({
      data: ({ request }) => {
        const params = new URL(request.url).searchParams
        const spec = params.get('specialization')
        const q = params.get('q')?.trim().toLowerCase()
        return db.data.skills.filter(
          (s) =>
            (!spec || (s.specializations as string[]).includes(spec)) &&
            (!q || s.label.toLowerCase().includes(q) || s.id.includes(q)),
        )
      },
    }),
  ),
  http.get('/api/catalog/decline-reasons', withScenario({ data: () => db.data.decline_reasons })),
]

// --- Авторизация ------------------------------------------------------------------------
const authHandlers: HttpHandler[] = [
  http.post('/api/auth/register', async ({ request }) => {
    await mockLatency()
    const body = await readJson<S['RegisterRequest']>(request)
    const email = (body.email ?? '').trim().toLowerCase()
    const fields: Record<string, string> = {}
    if (!EMAIL_RE.test(email)) fields.email = 'Укажите почту в формате name@example.com'
    if (!body.password || body.password.length < 8) fields.password = 'Пароль — не короче 8 символов'
    if (!body.full_name || body.full_name.trim().length < 2) fields.full_name = 'Укажите имя и фамилию'
    if (body.role !== 'candidate' && body.role !== 'recruiter') fields.role = 'Выберите роль'
    if (body.consent_processing !== true) fields.consent_processing = 'Без согласия на обработку данных регистрация невозможна'
    if (body.role === 'recruiter' && !body.company?.name?.trim() && !body.company?.invite_code?.trim()) {
      fields.company = 'Укажите компанию или код приглашения'
    }
    if (Object.keys(fields).length) return validationError(fields)
    if (users().some((u) => u.email.toLowerCase() === email)) {
      return apiError(409, 'email_taken', 'Пользователь с такой почтой уже есть')
    }

    let companyId: number | null = null
    if (body.role === 'recruiter') {
      const code = body.company?.invite_code?.trim()
      if (code) {
        // Прототип: код приглашения в компанию — INVITE-<id компании>.
        const id = Number(code.toUpperCase().replace('INVITE-', ''))
        if (!db.data.companies.some((c) => c.id === id)) {
          return apiError(404, 'company_invite_not_found', 'Код приглашения в компанию не найден')
        }
        companyId = id
      }
    }

    const now = db.now()
    const user: UserRow = {
      id: db.nextId('users'),
      email,
      role: body.role as S['Role'],
      full_name: body.full_name!.trim(),
      email_verified: false,
      blocked: false,
      created_at: now,
      last_login_at: null,
      _password: body.password,
    }
    users().push(user)

    if (body.role === 'recruiter') {
      if (companyId === null) {
        companyId = db.nextId('companies')
        ;(db.data.companies as unknown as Array<Record<string, unknown>>).push({
          id: companyId,
          name: body.company!.name!.trim(),
          description: '',
          industry: '',
          website: null,
          city: null,
          contact_email: email,
          contact_phone: null,
          inn: body.company?.inn ?? null,
          verified_domain: false,
          trust_score: 50,
          blocked: false,
          created_at: now,
        })
      }
      ;(db.data.recruiters as unknown as Array<Record<string, unknown>>).push({
        id: db.nextId('recruiters'),
        user_id: user.id,
        company_id: companyId,
        full_name: user.full_name,
        position: 'Рекрутер',
        email,
        phone: null,
        telegram: null,
        is_company_admin: !body.company?.invite_code,
      })
    }

    ;(db.data.consents as unknown as Array<Record<string, unknown>>).push({
      id: db.nextId('consents'),
      user_id: user.id,
      type: 'processing',
      version: body.consent_version || '2026-10-01',
      granted: true,
      granted_at: now,
      revoked_at: null,
    })
    db.save()

    const response: S['RegisterResponse'] = {
      user_id: user.id,
      email,
      status: 'pending_verification',
      message: 'Мы отправили письмо со ссылкой для подтверждения. Ссылка действует 24 часа.',
    }
    return HttpResponse.json(response, { status: 201 })
  }),

  http.post('/api/auth/verify-email', async ({ request }) => {
    await mockLatency()
    const { token = '' } = await readJson<S['VerifyEmailRequest']>(request)
    if (token === `${MOCK_VERIFY_PREFIX}expired`) {
      return apiError(410, 'token_expired', 'Ссылка устарела. Отправьте письмо ещё раз.')
    }
    const id = token.startsWith(MOCK_VERIFY_PREFIX) ? Number(token.slice(MOCK_VERIFY_PREFIX.length)) : NaN
    const user = users().find((u) => u.id === id)
    if (!user) return apiError(400, 'token_invalid', 'Ссылка недействительна. Проверьте, что скопировали её целиком.')
    user.email_verified = true
    db.save()
    const response: S['MessageResponse'] = { ok: true, message: 'Почта подтверждена. Теперь можно войти.' }
    return HttpResponse.json(response)
  }),

  http.post('/api/auth/resend-verification', async ({ request }) => {
    await mockLatency()
    const { email = '' } = await readJson<S['ResendVerificationRequest']>(request)
    if (!EMAIL_RE.test(email.trim())) return validationError({ email: 'Укажите почту' })
    const response: S['MessageResponse'] = { ok: true, message: 'Письмо отправлено повторно.' }
    return HttpResponse.json(response, { status: 202 })
  }),

  http.post('/api/auth/login', async ({ request }) => {
    await mockLatency()
    const body = await readJson<S['LoginRequest']>(request)
    const email = (body.email ?? '').trim().toLowerCase()
    const password = body.password ?? ''
    if (!email || !password) {
      return validationError({ ...(email ? {} : { email: 'Укажите почту' }), ...(password ? {} : { password: 'Укажите пароль' }) })
    }
    if ((failedLogins.get(email) ?? 0) >= MAX_LOGIN_ATTEMPTS) {
      return apiError(429, 'too_many_attempts', 'Слишком много попыток, попробуйте через 15 минут')
    }
    const demo = demoAccounts().find((a) => a.email.toLowerCase() === email && a.password === password)
    const user = demo
      ? users().find((u) => u.id === demo.user_id)
      : users().find((u) => u.email.toLowerCase() === email && u._password !== undefined && u._password === password)
    if (!user) {
      failedLogins.set(email, (failedLogins.get(email) ?? 0) + 1)
      return apiError(401, 'invalid_credentials', 'Неверная почта или пароль')
    }
    failedLogins.delete(email)
    if (user.blocked) return apiError(403, 'user_blocked', 'Учётная запись заблокирована')
    if (!user.email_verified) {
      return apiError(403, 'email_not_verified', 'Подтвердите почту по ссылке из письма', { email: user.email, user_id: user.id })
    }
    return HttpResponse.json(tokenFor(user))
  }),

  http.post('/api/auth/refresh', async ({ request }) => {
    await mockLatency()
    const { userId } = demoUser(request)
    const user = users().find((u) => u.id === userId)
    if (!user) return apiError(401, 'unauthorized', 'Требуется вход')
    return HttpResponse.json(tokenFor(user))
  }),

  http.post('/api/auth/logout', async () => {
    await mockLatency()
    return new HttpResponse(null, { status: 204 })
  }),

  http.get('/api/auth/me', async ({ request }) => {
    await mockLatency()
    const { userId } = demoUser(request)
    const user = users().find((u) => u.id === userId)
    if (!user) return apiError(401, 'unauthorized', 'Требуется вход')
    return HttpResponse.json(toMe(user))
  }),

  http.post('/api/auth/password-reset/request', async ({ request }) => {
    await mockLatency()
    const { email = '' } = await readJson<S['PasswordResetRequest']>(request)
    if (!EMAIL_RE.test(email.trim())) return validationError({ email: 'Укажите почту' })
    const response: S['MessageResponse'] = {
      ok: true,
      message: 'Если такая почта зарегистрирована, мы отправили на неё ссылку для сброса пароля.',
    }
    return HttpResponse.json(response, { status: 202 })
  }),

  http.post('/api/auth/password-reset/confirm', async () => {
    await mockLatency()
    const response: S['MessageResponse'] = { ok: true, message: 'Пароль изменён.' }
    return HttpResponse.json(response)
  }),

  http.get('/api/auth/fsp/authorize-url', async ({ request }) => {
    await mockLatency()
    const params = new URL(request.url).searchParams
    const purpose = params.get('purpose') === 'link' ? 'link' : 'login'
    const state = Math.random().toString(36).slice(2, 12)
    // Вместо Keycloak — экран выбора тестового участника внутри прототипа.
    const query = new URLSearchParams({ mock_idp: '1', state, purpose, code_challenge: '<из PKCE на клиенте>' })
    const response: S['FspAuthorizeUrl'] = { authorize_url: `/auth/fsp-callback?${query}`, state, purpose }
    return HttpResponse.json(response)
  }),

  http.post('/api/auth/fsp/login', async ({ request }) => {
    await mockLatency()
    const { code = '' } = await readJson<S['FspCodeExchange']>(request)
    if (!code.startsWith(MOCK_FSP_CODE_PREFIX)) return apiError(400, 'oidc_error', 'Ошибка обмена кода авторизации')
    const fspId = code.slice(MOCK_FSP_CODE_PREFIX.length)
    const candidate = (db.data.candidates as unknown as Array<{ user_id: number; fsp_id?: string | null }>).find(
      (c) => c.fsp_id === fspId,
    )
    const user = candidate ? users().find((u) => u.id === candidate.user_id) : undefined
    if (!user) {
      return apiError(
        404,
        'fsp_account_not_linked',
        'Этот ФСП ID не привязан ни к одному профилю. Войдите по почте и привяжите ФСП ID в настройках.',
        { fsp_id: fspId },
      )
    }
    return HttpResponse.json(tokenFor(user))
  }),
]

export const publicHandlers: HttpHandler[] = [...catalogHandlers, ...authHandlers]
