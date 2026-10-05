import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, buildUrl, setApiRole } from './client'

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
