import { API_BASE, USE_MOCKS } from '@/shared/config/env'
import type { Role } from '@/shared/config/roles'
import type { components } from './schema'

/**
 * Ошибка API в едином формате бэкенда: {"code": "...", "message": "...", "details": {...}}.
 * status = 0 — запрос не дошёл до сервера (нет сети, сервер не запущен).
 */
export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/** Текст ошибки для показа пользователю. */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) return error.message
  if (error instanceof Error && error.message) return error.message
  return 'Что-то пошло не так. Попробуйте ещё раз.'
}

// --- Режим: моки (демо-заголовки) или настоящий API (Bearer) ---------------------------
export type ApiMode = 'mock' | 'real'
let apiMode: ApiMode = USE_MOCKS ? 'mock' : 'real'

/** Режим клиента. По умолчанию — из VITE_USE_MOCKS; переключать нужно только в тестах. */
export function setApiMode(mode: ApiMode): void {
  apiMode = mode
}

export function getApiMode(): ApiMode {
  return apiMode
}

// --- Текущая роль для заголовка X-Demo-Role (только режим моков) ----------------------
// AuthProvider обновляет её при смене демо-пользователя. Хранится вне React, чтобы клиент можно
// было вызывать откуда угодно (queryFn, хендлеры событий).
let currentRole: Role | null = null
let currentUserId: number | null = null

export function setApiRole(role: Role | null, userId: number | null = null): void {
  currentRole = role
  currentUserId = role ? userId : null
}

/** id демо-пользователя (X-Demo-User-Id) — для MSW-хендлеров и отладки. */
export function getApiUserId(): number | null {
  return currentUserId
}

export function getApiRole(): Role | null {
  return currentRole
}

// --- Сессия настоящего API -------------------------------------------------------------
// Access-токен живёт только в памяти вкладки (не в localStorage). После перезагрузки страницы
// его снова выдаёт POST /auth/refresh по httpOnly cookie refresh_token.
export type TokenResponse = components['schemas']['TokenResponse']

let accessToken: string | null = null
let refreshInFlight: Promise<TokenResponse> | null = null
let onSessionExpired: (() => void) | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function getAccessToken(): string | null {
  return accessToken
}

/** Кого позвать, когда refresh не удался (сессия истекла или отозвана). Ставит AuthProvider. */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

/**
 * Запросы, где 401 — ответ по существу (неверный пароль и т.п.), а не истёкший токен:
 * для них refresh не делаем.
 */
const NO_REFRESH_PATHS = new Set([
  '/auth/login',
  '/auth/refresh',
  '/auth/logout',
  '/auth/register',
  '/auth/verify-email',
  '/auth/resend-verification',
  '/auth/password-reset/request',
  '/auth/password-reset/confirm',
  '/auth/fsp/login',
  '/auth/fsp/authorize-url',
])

function normalizePath(path: string): string {
  return path.startsWith('/') ? path : `/${path}`
}

/**
 * Обновить access-токен по refresh-cookie. Параллельные вызовы ждут один и тот же запрос:
 * refresh-токен ротируется, и второй запрос со старым cookie получил бы 401.
 */
export function refreshAccessToken(): Promise<TokenResponse> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await sendRequest('/auth/refresh', { method: 'POST' }, null)
        if (!res.ok) throw await parseError(res)
        const body = (await res.json()) as TokenResponse
        accessToken = body.access_token
        return body
      } catch (error) {
        accessToken = null
        if (isApiError(error) && (error.status === 401 || error.status === 403)) onSessionExpired?.()
        throw error
      } finally {
        refreshInFlight = null
      }
    })()
  }
  return refreshInFlight
}

// --- Запрос ----------------------------------------------------------------------------
export type QueryValue = string | number | boolean | null | undefined
export type QueryParams = Record<string, QueryValue | QueryValue[]>

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  /** Объект → JSON. FormData/Blob/строка уходят как есть. */
  body?: unknown
  query?: QueryParams
  headers?: Record<string, string>
  signal?: AbortSignal
  /** Как читать успешный ответ: по content-type (по умолчанию) или как файл (Blob). */
  responseType?: 'auto' | 'blob'
  /** Не обновлять токен по 401. */
  skipAuthRefresh?: boolean
}

export function buildUrl(path: string, query?: QueryParams): string {
  const base = API_BASE.replace(/\/$/, '')
  const p = normalizePath(path)
  const params = new URLSearchParams()
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      const values = Array.isArray(value) ? value : [value]
      for (const v of values) {
        if (v !== undefined && v !== null && v !== '') params.append(key, String(v))
      }
    }
  }
  const qs = params.toString()
  return `${base}${p}${qs ? `?${qs}` : ''}`
}

function isRawBody(body: unknown): body is BodyInit {
  return (
    typeof body === 'string' ||
    body instanceof FormData ||
    body instanceof Blob ||
    body instanceof URLSearchParams ||
    body instanceof ArrayBuffer
  )
}

async function parseError(response: Response): Promise<ApiError> {
  let payload: unknown = null
  try {
    payload = await response.json()
  } catch {
    // тело не JSON — ниже подставим общий текст
  }
  if (payload && typeof payload === 'object' && 'code' in payload && 'message' in payload) {
    const p = payload as { code: unknown; message: unknown; details?: unknown }
    return new ApiError(
      response.status,
      String(p.code),
      String(p.message),
      p.details && typeof p.details === 'object' ? (p.details as Record<string, unknown>) : {},
    )
  }
  const fallback =
    response.status >= 500
      ? `Ошибка сервера (${response.status}). Попробуйте позже.`
      : `Запрос не выполнен (${response.status}).`
  return new ApiError(response.status, `http_${response.status}`, fallback)
}

/** Один fetch с заголовками режима: Bearer (настоящий API) или X-Demo-* (моки). */
async function sendRequest(path: string, options: RequestOptions, token: string | null): Promise<Response> {
  const { method = 'GET', body, query, headers = {}, signal } = options
  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...headers }
  if (apiMode === 'mock') {
    if (currentRole) finalHeaders['X-Demo-Role'] = currentRole
    if (currentUserId !== null) finalHeaders['X-Demo-User-Id'] = String(currentUserId)
  } else if (token) {
    finalHeaders.Authorization = `Bearer ${token}`
  }

  let finalBody: BodyInit | undefined
  if (body !== undefined) {
    if (isRawBody(body)) {
      finalBody = body
    } else {
      finalBody = JSON.stringify(body)
      finalHeaders['Content-Type'] = 'application/json'
    }
  }

  try {
    return await fetch(buildUrl(path, query), {
      method,
      headers: finalHeaders,
      body: finalBody,
      signal,
      credentials: 'include',
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Нет связи с сервером. Проверьте подключение.')
  }
}

/**
 * Базовый запрос к API. Возвращает распарсенный JSON (или undefined для 204).
 * Настоящий API: на 401 один раз обновляет токен (один refresh на все параллельные запросы)
 * и повторяет запрос; пока refresh идёт, новые запросы ждут его.
 */
export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const canRefresh = apiMode === 'real' && !options.skipAuthRefresh && !NO_REFRESH_PATHS.has(normalizePath(path))

  if (canRefresh && refreshInFlight) await refreshInFlight.catch(() => undefined)
  const sentWith = accessToken
  let response = await sendRequest(path, options, sentWith)

  if (response.status === 401 && canRefresh) {
    let token: string | null
    if (accessToken && accessToken !== sentWith) {
      // токен уже обновил другой запрос, пока этот был в пути
      token = accessToken
    } else {
      try {
        token = (await refreshAccessToken()).access_token
      } catch {
        token = null
      }
    }
    if (token) response = await sendRequest(path, options, token)
  }

  if (!response.ok) throw await parseError(response)
  if (options.responseType === 'blob') return (await response.blob()) as T
  if (response.status === 204) return undefined as T

  const contentType = response.headers.get('content-type') ?? ''
  if (contentType.includes('application/json')) return (await response.json()) as T
  return (await response.text()) as T
}

/** Короткие методы: api.get('/candidates/me'), api.post('/invitations', body). */
export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'POST', body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'PUT', body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'PATCH', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'DELETE' }),
}
