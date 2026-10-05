import { API_BASE } from '@/shared/config/env'
import type { Role } from '@/shared/config/roles'

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

// --- Текущая роль для заголовка X-Demo-Role ---------------------------------------------
// AuthProvider обновляет её при смене пользователя. Хранится вне React, чтобы клиент можно
// было вызывать откуда угодно (queryFn, хендлеры событий).
let currentRole: Role | null = null

export function setApiRole(role: Role | null): void {
  currentRole = role
}

export function getApiRole(): Role | null {
  return currentRole
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
}

export function buildUrl(path: string, query?: QueryParams): string {
  const base = API_BASE.replace(/\/$/, '')
  const p = path.startsWith('/') ? path : `/${path}`
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

/** Базовый запрос к API. Возвращает распарсенный JSON (или undefined для 204). */
export async function apiFetch<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, query, headers = {}, signal } = options
  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...headers }
  if (currentRole) finalHeaders['X-Demo-Role'] = currentRole

  let finalBody: BodyInit | undefined
  if (body !== undefined) {
    if (isRawBody(body)) {
      finalBody = body
    } else {
      finalBody = JSON.stringify(body)
      finalHeaders['Content-Type'] = 'application/json'
    }
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, query), {
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

  if (!response.ok) throw await parseError(response)
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
