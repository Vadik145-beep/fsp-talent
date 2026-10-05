import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { setApiRole } from '@/shared/api/client'
import { isRole, type Role } from '@/shared/config/roles'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import { DEMO_USERS, type DemoUser } from './demoUsers'

/**
 * Простая демо-авторизация прототипа: текущая роль и пользователь.
 * Роль запоминается в localStorage и уходит в API заголовком X-Demo-Role.
 * В волнах 2–4 заменяется настоящей авторизацией (сессия/токен с бэкенда) —
 * интерфейс useAuth() стоит сохранить.
 */
export interface AuthState {
  user: DemoUser | null
  role: Role | null
  /** Войти/переключиться демо-пользователем роли. */
  switchRole: (role: Role) => void
  logout: () => void
}

const STORAGE_KEY = 'fsp.demoRole'

const AuthContext = createContext<AuthState | null>(null)

function readInitialRole(): Role | null {
  const stored = readStorage(STORAGE_KEY)
  const role = isRole(stored) ? stored : null
  setApiRole(role)
  return role
}

export function AuthProvider({ children, initialRole }: { children: ReactNode; initialRole?: Role | null }) {
  const [role, setRole] = useState<Role | null>(() => {
    if (initialRole !== undefined) {
      setApiRole(initialRole)
      return initialRole
    }
    return readInitialRole()
  })

  const switchRole = useCallback((next: Role) => {
    // Заголовок обновляем сразу, до перерисовки: запросы нового экрана уйдут с новой ролью.
    setApiRole(next)
    writeStorage(STORAGE_KEY, next)
    setRole(next)
  }, [])

  const logout = useCallback(() => {
    setApiRole(null)
    writeStorage(STORAGE_KEY, null)
    setRole(null)
  }, [])

  const value = useMemo<AuthState>(
    () => ({ user: role ? DEMO_USERS[role] : null, role, switchRole, logout }),
    [role, switchRole, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth: нет AuthProvider выше по дереву')
  return ctx
}
