import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach } from 'vitest'
import { db } from '@/mocks/db'
import { candidateHandlers } from '@/mocks/handlers/candidate'
import { publicHandlers } from '@/mocks/handlers/public'

/** Хендлер-«заглушка» в конце цепочки: показывает, что запрос прошёл мимо хендлеров соискателя. */
export const FALLTHROUGH_STATUS = 418

/**
 * MSW в тестах: хендлеры трека 1a + общая база моков, сброс базы перед каждым тестом.
 * Относительные URL клиента (/api/...) дополняются origin'ом jsdom — в Node fetch их не понимает.
 */
export function setupMockServer() {
  const server = setupServer(
    ...publicHandlers,
    ...candidateHandlers,
    http.all('*/api/*', () => HttpResponse.json({ code: 'fallthrough', message: 'нет хендлера', details: {} }, { status: FALLTHROUGH_STATUS })),
  )
  let originalFetch: typeof fetch
  beforeAll(() => {
    server.listen({ onUnhandledRequest: 'error' })
    originalFetch = globalThis.fetch
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
      originalFetch(typeof input === 'string' && input.startsWith('/') ? `${window.location.origin}${input}` : input, init)) as typeof fetch
  })
  beforeEach(() => db.reset())
  afterEach(() => server.resetHandlers())
  afterAll(() => {
    globalThis.fetch = originalFetch
    server.close()
  })
  return server
}

/** Запрос к мокам от имени демо-пользователя. */
export async function call<T = unknown>(
  method: string,
  path: string,
  { role = 'candidate', userId = 1, body }: { role?: string; userId?: number; body?: unknown } = {},
): Promise<{ status: number; data: T }> {
  const res = await fetch(`${window.location.origin}/api${path}`, {
    method,
    headers: { 'X-Demo-Role': role, 'X-Demo-User-Id': String(userId), ...(body ? { 'Content-Type': 'application/json' } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  })
  const text = await res.text()
  return { status: res.status, data: (text ? JSON.parse(text) : undefined) as T }
}
