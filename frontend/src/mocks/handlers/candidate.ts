import type { HttpHandler } from 'msw'

/**
 * Моки API кабинета соискателя (трек 1a).
 * Правит только трек своей роли. Фикстуры: import x from '@seed/<file>.json'.
 * Помощники: withScenario, apiError, mockLatency из '../utils'.
 */
export const candidateHandlers: HttpHandler[] = []
