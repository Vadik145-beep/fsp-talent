import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { QueryClientContext } from '@tanstack/react-query'
import {
  api,
  getApiMode,
  refreshAccessToken,
  setAccessToken,
  setApiRole,
  setSessionExpiredHandler,
  type TokenResponse,
} from '@/shared/api/client'
import type { components } from '@/shared/api/schema'
import { isRole, ROLE_HOME, ROLE_LABELS, type Role } from '@/shared/config/roles'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import { DEMO_USERS, type DemoUser } from './demoUsers'
import { resolveCabinetAccess, type AuthStatus } from './guard'

export type { AuthStatus } from './guard'
export type Me = components['schemas']['Me']

/**
 * Авторизация приложения. Два режима (VITE_USE_MOCKS):
 * - моки (прототип): демо-пользователь роли, роль в localStorage, в API — заголовки X-Demo-*;
 * - настоящий API: вход POST /auth/login, access-токен в памяти, refresh — httpOnly cookie,
 *   тихое обновление по 401 (shared/api/client), GET /auth/me при загрузке приложения.
 * Интерфейс useAuth() общий: layout и кабинеты не знают, какой режим включён.
 */
export interface AuthState {
  /** Текущий пользователь в виде, удобном шапке и меню. */
  user: DemoUser | null
  role: Role | null
  /** loading — проверяем сессию при загрузке приложения (только настоящий API). */
  status: AuthStatus
  /** true — прототип на моках. */
  isMock: boolean
  /** Ответ GET /auth/me (настоящий API; в моках — null). */
  me: Me | null
  /**
   * Моки: войти/переключиться демо-пользователем роли.
   * Настоящий API: запрос на вход в кабинет роли — нет сессии → /login?next=…, чужая роль → свой кабинет.
   */
  switchRole: (role: Role) => void
  /** Вход по почте и паролю. Ошибки API пробрасываются (ApiError). */
  login: (email: string, password: string) => Promise<Me>
  /** Принять сессию, выданную бэкендом (вход через ФСП ID). */
  acceptSession: (token: TokenResponse) => void
  /** Перечитать GET /auth/me (например, после привязки ФСП ID). */
  reloadUser: () => Promise<void>
  logout: () => Promise<void>
}

/** Переход вне React Router (AuthProvider стоит выше роутера). */
export interface AuthNavigator {
  go: (to: string) => void
  current: () => string
}

/** По умолчанию — браузерный роутер: меняем адрес и сообщаем роутеру событием popstate. */
const browserNavigator: AuthNavigator = {
  go: (to) => {
    window.history.replaceState(window.history.state, '', to)
    window.dispatchEvent(new PopStateEvent('popstate', { state: window.history.state }))
  },
  current: () => `${window.location.pathname}${window.location.search}`,
}

const DEMO_ROLE_KEY = 'fsp.demoRole'
/** Признак «в этом браузере был вход» — без него при загрузке не дёргаем refresh (лишний 401). */
const SESSION_HINT_KEY = 'fsp.hasSession'
/** Черновики интерфейса, привязанные к пользователю: при выходе стираем, чтобы не достались следующему. */
const USER_SCOPED_KEYS = ['fsp.candidate.onboarding']

const AuthContext = createContext<AuthState | null>(null)

function readInitialDemoRole(): Role | null {
  const stored = readStorage(DEMO_ROLE_KEY)
  const role = isRole(stored) ? stored : null
  setApiRole(role, role ? DEMO_USERS[role].userId : null)
  return role
}

/** Пользователь для шапки из ответа /auth/me. */
export function userFromMe(me: Me): DemoUser {
  return {
    id: `user-${me.id}`,
    userId: me.id,
    role: me.role,
    name: me.full_name,
    email: me.email,
    subtitle: ROLE_LABELS[me.role],
  }
}

export function AuthProvider(props: { children: ReactNode; initialRole?: Role | null; navigator?: AuthNavigator }) {
  return getApiMode() === 'mock' ? <MockAuthProvider {...props} /> : <RealAuthProvider {...props} />
}

// --- Моки: демо-пользователи ------------------------------------------------------------
function MockAuthProvider({ children, initialRole }: { children: ReactNode; initialRole?: Role | null }) {
  const [role, setRole] = useState<Role | null>(() => {
    if (initialRole !== undefined) {
      setApiRole(initialRole, initialRole ? DEMO_USERS[initialRole].userId : null)
      return initialRole
    }
    return readInitialDemoRole()
  })

  const switchRole = useCallback((next: Role) => {
    // Заголовок обновляем сразу, до перерисовки: запросы нового экрана уйдут с новой ролью.
    setApiRole(next, DEMO_USERS[next].userId)
    writeStorage(DEMO_ROLE_KEY, next)
    setRole(next)
  }, [])

  const logout = useCallback(async () => {
    setApiRole(null)
    writeStorage(DEMO_ROLE_KEY, null)
    setRole(null)
  }, [])

  const acceptSession = useCallback((token: TokenResponse) => switchRole(token.user.role), [switchRole])

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.post<TokenResponse>('/auth/login', { email, password })
      // Прототип: кабинет открывается демо-пользователем роли.
      acceptSession(res)
      return res.user
    },
    [acceptSession],
  )

  const value = useMemo<AuthState>(
    () => ({
      user: role ? DEMO_USERS[role] : null,
      role,
      status: role ? 'authenticated' : 'anonymous',
      isMock: true,
      me: null,
      switchRole,
      login,
      acceptSession,
      reloadUser: async () => {},
      logout,
    }),
    [role, switchRole, login, acceptSession, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// --- Настоящий API ------------------------------------------------------------------------
function RealAuthProvider({ children, navigator = browserNavigator }: { children: ReactNode; navigator?: AuthNavigator }) {
  const queryClient = useContext(QueryClientContext)
  const [me, setMe] = useState<Me | null>(null)
  const [status, setStatus] = useState<AuthStatus>(() => (readStorage(SESSION_HINT_KEY) ? 'loading' : 'anonymous'))
  const bootstrapped = useRef(false)

  const dropSession = useCallback(() => {
    setAccessToken(null)
    writeStorage(SESSION_HINT_KEY, null)
    setMe(null)
    setStatus('anonymous')
  }, [])

  // Refresh не удался (истёк/отозван) — выходим; кабинет сам отправит на /login.
  useEffect(() => {
    setSessionExpiredHandler(dropSession)
    return () => setSessionExpiredHandler(null)
  }, [dropSession])

  // Загрузка приложения: refresh по cookie → GET /auth/me.
  useEffect(() => {
    if (bootstrapped.current || !readStorage(SESSION_HINT_KEY)) return
    bootstrapped.current = true
    void (async () => {
      try {
        await refreshAccessToken()
        const current = await api.get<Me>('/auth/me')
        setMe(current)
        setStatus('authenticated')
      } catch {
        dropSession()
      }
    })()
  }, [dropSession])

  const acceptSession = useCallback(
    (token: TokenResponse) => {
      setAccessToken(token.access_token)
      writeStorage(SESSION_HINT_KEY, '1')
      // Данные прошлого пользователя в кэше не нужны.
      queryClient?.removeQueries()
      setMe(token.user)
      setStatus('authenticated')
    },
    [queryClient],
  )

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.post<TokenResponse>('/auth/login', { email, password })
      acceptSession(res)
      return res.user
    },
    [acceptSession],
  )

  const reloadUser = useCallback(async () => {
    const current = await api.get<Me>('/auth/me')
    setMe(current)
  }, [])

  // Один выход за раз: повторный вызов (двойной эффект StrictMode, двойной клик) ждёт первый.
  const logoutInFlight = useRef<Promise<void> | null>(null)
  const logout = useCallback(() => {
    if (!logoutInFlight.current) {
      logoutInFlight.current = (async () => {
        try {
          await api.post('/auth/logout')
        } catch {
          // сеть или сессия уже закрыта — локально выходим в любом случае
        }
        dropSession()
        USER_SCOPED_KEYS.forEach((key) => writeStorage(key, null))
        queryClient?.removeQueries()
      })().finally(() => {
        logoutInFlight.current = null
      })
    }
    return logoutInFlight.current
  }, [dropSession, queryClient])

  const switchRole = useCallback(
    (required: Role) => {
      const current = navigator.current()
      // Переход уже начат (адрес сменился, а роутер ещё грузит экран) — второй раз не уводим.
      if (!current.startsWith(ROLE_HOME[required])) return
      const decision = resolveCabinetAccess(status, me?.role ?? null, required, current)
      if (decision.type === 'redirect') navigator.go(decision.to)
    },
    [status, me, navigator],
  )

  const value = useMemo<AuthState>(
    () => ({
      user: me ? userFromMe(me) : null,
      role: me?.role ?? null,
      status,
      isMock: false,
      me,
      switchRole,
      login,
      acceptSession,
      reloadUser,
      logout,
    }),
    [me, status, switchRole, login, acceptSession, reloadUser, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth: нет AuthProvider выше по дереву')
  return ctx
}
