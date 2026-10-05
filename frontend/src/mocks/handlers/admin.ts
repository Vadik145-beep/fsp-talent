import type { HttpHandler } from 'msw'

/**
 * Моки API кабинета администратора (трек 1c).
 * Правит только трек своей роли. Фикстуры: import x from '@seed/<file>.json'.
 * Помощники: withScenario, apiError, mockLatency из '../utils'.
 */
export const adminHandlers: HttpHandler[] = []
