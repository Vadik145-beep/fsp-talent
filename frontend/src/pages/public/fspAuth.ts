import { api } from '@/shared/api'
import type { components } from '@/shared/api/schema'

/**
 * Вход и привязка через ФСП ID (Keycloak, OIDC Authorization Code + PKCE).
 * 1. Бэкенд отдаёт ссылку авторизации (GET /auth/fsp/authorize-url).
 * 2. Клиент создаёт code_verifier, подставляет code_challenge (S256) и уходит по ссылке.
 * 3. Keycloak возвращает на /auth/fsp-callback?code&state — там код меняется на сессию
 *    (POST /auth/fsp/login) или привязывается к профилю (POST /auth/fsp-link).
 */
export type FspPurpose = 'login' | 'link'

export interface PendingFspAuth {
  state: string
  purpose: FspPurpose
  codeVerifier: string
  redirectUri: string
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
    // crypto.subtle недоступен (не https) — в проде такого нет, для прототипа достаточно
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

/** Начать вход/привязку. navigate — для ссылок внутри приложения (моки), иначе полный переход. */
export async function startFspAuth(
  purpose: FspPurpose,
  navigate: (to: string) => void,
  returnTo?: string,
): Promise<void> {
  const redirectUri = `${window.location.origin}/auth/fsp-callback`
  const res = await api.get<components['schemas']['FspAuthorizeUrl']>('/auth/fsp/authorize-url', {
    query: { purpose, redirect_uri: redirectUri },
  })
  const codeVerifier = randomString(64)
  const url = new URL(res.authorize_url, window.location.origin)
  url.searchParams.set('code_challenge', await challengeFor(codeVerifier))
  url.searchParams.set('code_challenge_method', 'S256')
  const pending: PendingFspAuth = { state: res.state, purpose, codeVerifier, redirectUri, returnTo }
  try {
    window.sessionStorage.setItem(KEY, JSON.stringify(pending))
  } catch {
    // без sessionStorage проверка state на возврате пропускается
  }
  if (url.origin === window.location.origin) navigate(`${url.pathname}${url.search}`)
  else window.location.assign(url.toString())
}
