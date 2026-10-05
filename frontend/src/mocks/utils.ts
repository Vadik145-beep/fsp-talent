import { delay, HttpResponse, type HttpResponseResolver } from 'msw'
import { getMockScenario } from './scenario'

/** Ответ-ошибка в едином формате API: {code, message, details}. */
export function apiError(
  status: number,
  code: string,
  message: string,
  details: Record<string, unknown> = {},
) {
  return HttpResponse.json({ code, message, details }, { status })
}

/** Задержка «как у сети»: 250–450 мс, в режиме «медленная сеть» — 2,5 с. */
export async function mockLatency(): Promise<void> {
  await delay(getMockScenario() === 'slow' ? 2500 : 250 + Math.round(Math.random() * 200))
}

/**
 * Обработчик GET-запроса с учётом режима данных из демо-плашки:
 * normal/slow — data(), empty — empty() (если не задан — data()), error — 500 в формате API.
 *
 * Пример:
 *   http.get('/api/invitations', withScenario({ data: () => invitations, empty: () => [] }))
 */
export function withScenario<T>(opts: {
  data: (info: Parameters<HttpResponseResolver>[0]) => T
  empty?: () => T
}): HttpResponseResolver {
  return async (info) => {
    await mockLatency()
    const scenario = getMockScenario()
    if (scenario === 'error') {
      return apiError(500, 'mock_error', 'Сервер временно недоступен (режим «ошибка» в демо-плашке).')
    }
    if (scenario === 'empty' && opts.empty) return HttpResponse.json(opts.empty() as never)
    return HttpResponse.json(opts.data(info) as never)
  }
}
