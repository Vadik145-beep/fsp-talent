import { http, HttpResponse, type HttpHandler } from 'msw'

/**
 * Общие моки (не принадлежат одной роли). В волне 1 сюда не пишем —
 * справочники и прочее общее кладите в хендлеры своей роли или согласуйте с дирижёром.
 */
export const commonHandlers: HttpHandler[] = [
  http.get('/api/health', () => HttpResponse.json({ status: 'ok', mode: 'mocks' })),
]
