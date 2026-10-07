import { api, getApiMode } from '@/shared/api'
import type { components } from '@/shared/api/schema'

/**
 * Вход и привязка через ФСП ID (Keycloak, OIDC Authorization Code + PKCE).
 * 1. Бэкенд отдаёт ссылку авторизации (GET /auth/fsp/authorize-url).
 *    Настоящий API: state, nonce и PKCE (code_verifier/code_challenge) делает бэкенд и хранит
 *    в подписанной httpOnly cookie — клиент просто уходит по ссылке.
 *    Моки: заглушка Keycloak внутри прототипа, PKCE для наглядности делает клиент.
 * 2. Keycloak возвращает на /auth/fsp-callback?code&state — там код меняется на сессию
 *    (POST /auth/fsp/login) или привязывается к профилю (POST /auth/fsp-link).
 */
export type FspPurpose = 'login' | 'link'
type S = components['schemas']

export interface PendingFspAuth {
  state: string
  purpose: FspPurpose
  redirectUri: string
  /** Только моки: клиентский PKCE прототипа. */
  codeVerifier?: string
  /** Куда вернуться после привязки. */
  returnTo?: string
}

const KEY = 'fsp.oidcPending'

function randomString(length: number): string {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
  const bytes = new Uint8Array(length)
  crypto.getRandomValues(bytes)
  return Array.from(bytes, (b) => alphabet[b % alphabet.length]).join('')
}

async function challengeFor(verifier: string): Promise<string> {
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
    return btoa(String.fromCharCode(...new Uint8Array(digest)))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '')
  } catch {
    // crypto.subtle недоступен (не https) — для заглушки прототипа достаточно
    return verifier
  }
}

export function readPendingFspAuth(): PendingFspAuth | null {
  try {
    const raw = window.sessionStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as PendingFspAuth) : null
  } catch {
    return null
  }
}

export function clearPendingFspAuth(): void {
  try {
    window.sessionStorage.removeItem(KEY)
  } catch {
    // хранилище недоступно
  }
}

function savePending(pending: PendingFspAuth): void {
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(pending))
  } catch {
    // без sessionStorage проверка state на клиенте пропускается (бэкенд всё равно проверит)
  }
}

export function fspRedirectUri(): string {
  return `${window.location.origin}/auth/fsp-callback`
}

/** Начать вход/привязку. navigate — для ссылок внутри приложения (моки), иначе полный переход. */
export async function startFspAuth(
  purpose: FspPurpose,
  navigate: (to: string) => void,
  returnTo?: string,
): Promise<void> {
  const redirectUri = fspRedirectUri()
  const res = await api.get<S['FspAuthorizeUrl']>('/auth/fsp/authorize-url', {
    query: { purpose, redirect_uri: redirectUri },
  })

  if (getApiMode() === 'real') {
    savePending({ state: res.state, purpose, redirectUri, returnTo })
    window.location.assign(res.authorize_url)
    return
  }

  const codeVerifier = randomString(64)
  const url = new URL(res.authorize_url, window.location.origin)
  url.searchParams.set('code_challenge', await challengeFor(codeVerifier))
  url.searchParams.set('code_challenge_method', 'S256')
  savePending({ state: res.state, purpose, codeVerifier, redirectUri, returnTo })
  if (url.origin === window.location.origin) navigate(`${url.pathname}${url.search}`)
  else window.location.assign(url.toString())
}

/** Тело обмена кода: в настоящем API без code_verifier (его хранит бэкенд). */
export function codeExchangeBody(code: string, state: string, pending: PendingFspAuth | null): S['FspCodeExchange'] {
  const body: S['FspCodeExchange'] = { code, state, redirect_uri: pending?.redirectUri ?? fspRedirectUri() }
  if (getApiMode() === 'mock') body.code_verifier = pending?.codeVerifier ?? 'x'.repeat(43)
  return body
}
