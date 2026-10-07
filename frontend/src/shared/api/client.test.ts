import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  api,
  ApiError,
  buildUrl,
  getAccessToken,
  refreshAccessToken,
  setAccessToken,
  setApiMode,
  setApiRole,
  setSessionExpiredHandler,
} from './client'

function mockFetch(response: Response | Error) {
  const fn = vi.fn(async () => {
    if (response instanceof Error) throw response
    return response
  })
  vi.stubGlobal('fetch', fn)
  return fn
}

afterEach(() => {
  vi.unstubAllGlobals()
  setApiRole(null)
  setApiMode('mock')
  setAccessToken(null)
  setSessionExpiredHandler(null)
})

describe('api client', () => {
  it('собирает URL с базой /api и query', () => {
    expect(buildUrl('/candidates', { spec: 'backend', grade: ['junior', 'middle'], empty: '', none: undefined })).toBe(
      '/api/candidates?spec=backend&grade=junior&grade=middle',
    )
  })

  it('отправляет X-Demo-Role и JSON-тело', async () => {
    setApiRole('recruiter')
    const fetchMock = mockFetch(Response.json({ id: 1 }, { status: 201 }))
    const res = await api.post<{ id: number }>('/invitations', { salary_from: 250000 })
    expect(res).toEqual({ id: 1 })
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/invitations')
    const headers = init.headers as Record<string, string>
    expect(headers['X-Demo-Role']).toBe('recruiter')
    expect(headers['Content-Type']).toBe('application/json')
    expect(init.body).toBe('{"salary_from":250000}')
  })

  it('без роли заголовок не отправляется', async () => {
    const fetchMock = mockFetch(Response.json({ status: 'ok' }))
    await api.get('/health')
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Record<string, string>)['X-Demo-Role']).toBeUndefined()
  })

  it('разбирает ошибку формата {code, message, details}', async () => {
    mockFetch(
      Response.json(
        { code: 'salary_below_minimum', message: 'Зарплата ниже минимальной', details: { min: 280000 } },
        { status: 422 },
      ),
    )
    const err = await api.get('/x').catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err).toMatchObject({ status: 422, code: 'salary_below_minimum', message: 'Зарплата ниже минимальной', details: { min: 280000 } })
  })

  it('ошибка без JSON — общий текст', async () => {
    mockFetch(new Response('Bad Gateway', { status: 502 }))
    const err = (await api.get('/x').catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe('http_502')
    expect(err.message).toContain('502')
  })

  it('нет сети — network_error', async () => {
    mockFetch(new TypeError('Failed to fetch'))
    const err = (await api.get('/x').catch((e: unknown) => e)) as ApiError
    expect(err.status).toBe(0)
    expect(err.code).toBe('network_error')
  })

  it('204 → undefined', async () => {
    mockFetch(new Response(null, { status: 204 }))
    await expect(api.delete('/x')).resolves.toBeUndefined()
  })
})

// --- Настоящий API: Bearer, refresh по 401, очередь ------------------------------------
interface Call {
  url: string
  auth: string | undefined
  demoRole: string | undefined
}

const ME = {
  id: 1,
  email: 'candidate@example.com',
  role: 'candidate',
  full_name: 'Никита',
  email_verified: true,
  fsp_id: null,
  candidate_id: 1,
  recruiter_id: null,
  company_id: null,
}

/**
 * Фейковый бэкенд: /auth/refresh выдаёт токен `fresh-N` (или 401, если refreshOk=false),
 * остальные пути отвечают 200 только с актуальным токеном, иначе 401 token_expired.
 */
function fakeBackend({ refreshOk = true, refreshDelay = 0 } = {}) {
  const calls: Call[] = []
  let issued = 0
  let valid: string | null = null
  const fn = vi.fn(async (input: string, init?: RequestInit) => {
    const headers = (init?.headers ?? {}) as Record<string, string>
    calls.push({ url: input, auth: headers.Authorization, demoRole: headers['X-Demo-Role'] })
    if (input === '/api/auth/refresh') {
      if (refreshDelay) await new Promise((r) => setTimeout(r, refreshDelay))
      if (!refreshOk) return Response.json({ code: 'invalid_refresh_token', message: 'Сессия истекла', details: {} }, { status: 401 })
      issued += 1
      valid = `fresh-${issued}`
      return Response.json({ access_token: valid, token_type: 'bearer', expires_in: 900, user: ME })
    }
    if (input === '/api/auth/login') {
      return Response.json({ code: 'invalid_credentials', message: 'Неверная почта или пароль', details: {} }, { status: 401 })
    }
    if (valid && headers.Authorization === `Bearer ${valid}`) return Response.json({ ok: true, path: input })
    return Response.json({ code: 'token_expired', message: 'Сессия истекла, обновите токен', details: {} }, { status: 401 })
  })
  vi.stubGlobal('fetch', fn)
  return { calls, refreshCalls: () => calls.filter((c) => c.url === '/api/auth/refresh').length }
}

describe('api client: настоящий API', () => {
  it('шлёт Bearer и не шлёт X-Demo-*', async () => {
    setApiMode('real')
    setApiRole('candidate', 1)
    setAccessToken('t1')
    const fetchMock = mockFetch(Response.json({ ok: true }))
    await api.get('/candidates/me/profile')
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    const headers = init.headers as Record<string, string>
    expect(headers.Authorization).toBe('Bearer t1')
    expect(headers['X-Demo-Role']).toBeUndefined()
    expect(headers['X-Demo-User-Id']).toBeUndefined()
    expect(init.credentials).toBe('include')
  })

  it('в режиме моков Bearer не шлёт', async () => {
    setAccessToken('t1')
    setApiRole('candidate', 1)
    const fetchMock = mockFetch(Response.json({ ok: true }))
    await api.get('/x')
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('401 → один refresh → повтор с новым токеном', async () => {
    setApiMode('real')
    setAccessToken('expired')
    const backend = fakeBackend()
    const res = await api.get<{ ok: boolean }>('/candidates/me/profile')
    expect(res.ok).toBe(true)
    expect(backend.refreshCalls()).toBe(1)
    expect(backend.calls.map((c) => [c.url, c.auth])).toEqual([
      ['/api/candidates/me/profile', 'Bearer expired'],
      ['/api/auth/refresh', undefined],
      ['/api/candidates/me/profile', 'Bearer fresh-1'],
    ])
    expect(getAccessToken()).toBe('fresh-1')
  })

  it('параллельные 401 ждут один общий refresh (очередь)', async () => {
    setApiMode('real')
    setAccessToken('expired')
    const backend = fakeBackend({ refreshDelay: 20 })
    const results = await Promise.all([api.get('/a'), api.get('/b'), api.get('/c'), api.post('/d', { x: 1 })])
    expect(results).toHaveLength(4)
    expect(backend.refreshCalls()).toBe(1)
    const retried = backend.calls.filter((c) => c.auth === 'Bearer fresh-1').map((c) => c.url)
    expect(retried.sort()).toEqual(['/api/a', '/api/b', '/api/c', '/api/d'])
  })

  it('запрос, начатый во время refresh, ждёт его и уходит уже с новым токеном', async () => {
    setApiMode('real')
    setAccessToken('expired')
    const backend = fakeBackend({ refreshDelay: 30 })
    const refreshing = refreshAccessToken()
    const late = api.get('/late')
    await Promise.all([refreshing, late])
    const lateCalls = backend.calls.filter((c) => c.url === '/api/late')
    expect(lateCalls).toEqual([{ url: '/api/late', auth: 'Bearer fresh-1', demoRole: undefined }])
    expect(backend.refreshCalls()).toBe(1)
  })

  it('refresh не удался → 401 наружу, токен сброшен, AuthProvider узнаёт о выходе', async () => {
    setApiMode('real')
    setAccessToken('expired')
    const expired = vi.fn()
    setSessionExpiredHandler(expired)
    const backend = fakeBackend({ refreshOk: false })
    const err = (await api.get('/candidates/me/profile').catch((e: unknown) => e)) as ApiError
    expect(err.status).toBe(401)
    expect(backend.refreshCalls()).toBe(1)
    expect(getAccessToken()).toBeNull()
    expect(expired).toHaveBeenCalledTimes(1)
  })

  it('401 на входе по паролю — без refresh', async () => {
    setApiMode('real')
    const backend = fakeBackend()
    const err = (await api.post('/auth/login', { email: 'a@b.c', password: 'x' }).catch((e: unknown) => e)) as ApiError
    expect(err.code).toBe('invalid_credentials')
    expect(backend.refreshCalls()).toBe(0)
  })

  it('файл читается как Blob', async () => {
    setApiMode('real')
    mockFetch(new Response('%PDF-1.4', { headers: { 'Content-Type': 'application/pdf' } }))
    const blob = await api.get<Blob>('/candidates/me/profile.pdf', { responseType: 'blob' })
    expect(blob.size).toBe(8)
  })
})
