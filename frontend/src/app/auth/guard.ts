import { ROLE_HOME, type Role } from '@/shared/config/roles'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export type AccessDecision = { type: 'wait' } | { type: 'allow' } | { type: 'redirect'; to: string }

/** Адрес входа с возвратом на текущую страницу после входа. */
export function loginUrl(returnTo: string): string {
  return returnTo && returnTo !== '/' && !returnTo.startsWith('/login')
    ? `/login?next=${encodeURIComponent(returnTo)}`
    : '/login'
}

/**
 * Можно ли открыть кабинет роли `required`:
 * сессия ещё грузится — ждём; нет сессии — на вход с возвратом; чужая роль — в свой кабинет.
 */
export function resolveCabinetAccess(
  status: AuthStatus,
  userRole: Role | null,
  required: Role,
  currentPath: string,
): AccessDecision {
  if (status === 'loading') return { type: 'wait' }
  if (status === 'anonymous' || !userRole) return { type: 'redirect', to: loginUrl(currentPath) }
  if (userRole !== required) return { type: 'redirect', to: ROLE_HOME[userRole] }
  return { type: 'allow' }
}

/** `next` из адреса входа: только внутренний путь (без //host и схем). */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return null
  return next
}
