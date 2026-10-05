import type { HttpHandler } from 'msw'

/**
 * Моки API кабинета рекрутера (трек 1b).
 * Правит только трек своей роли. Фикстуры: import x from '@seed/<file>.json'.
 * Помощники: withScenario, apiError, mockLatency из '../utils'.
 */
export const recruiterHandlers: HttpHandler[] = []
