import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { appRoutes } from '@/app/router'
import { getAccessToken, setAccessToken, setApiMode } from '@/shared/api/client'
import { ToastProvider } from '@/shared/ui'
import { AuthProvider, useAuth, type AuthNavigator } from './AuthContext'
import { loginUrl, resolveCabinetAccess, safeNext } from './guard'
import { RequireAuth } from './RequireAuth'

const USERS = {
  candidate: { id: 1, email: 'candidate@example.com', role: 'candidate', full_name: 'Никита Латыпов', candidate_id: 1 },
  recruiter: { id: 41, email: 'recruiter@example.com', role: 'recruiter', full_name: 'Ирина Белова', recruiter_id: 1, company_id: 1 },
} as const

function me(kind: keyof typeof USERS) {
  return { email_verified: true, fsp_id: null, candidate_id: null, recruiter_id: null, company_id: null, ...USERS[kind] }
}

/**
 * Фейковый бэкенд авторизации: refresh по «cookie» (переменная session), login, me, logout.
 * Прочие пути — 500 в формате API (экранам кабинетов данные в этих тестах не нужны).
 */
function fakeAuthBackend(initial: keyof typeof USERS | null = null) {
  let session: keyof typeof USERS | null = initial
  let n = 0
  const calls: string[] = []
  const token = () => `tok-${session}-${n}`
  const fn = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? 'GET'
    calls.push(`${method} ${url}`)
    const headers = (init?.headers ?? {}) as Record<string, string>
    if (url === '/api/auth/refresh') {
      if (!session) return Response.json({ code: 'invalid_refresh_token', message: 'Сессия истекла', details: {} }, { status: 401 })
      n += 1
      return Response.json({ access_token: token(), token_type: 'bearer', expires_in: 900, user: me(session) })
    }
    if (url === '/api/auth/login') {
      const body = JSON.parse(String(init?.body)) as { email: string; password: string }
      const kind = (Object.keys(USERS) as Array<keyof typeof USERS>).find((k) => USERS[k].email === body.email)
      if (!kind || body.password !== 'demo1234') {
        return Response.json({ code: 'invalid_credentials', message: 'Неверная почта или пароль', details: {} }, { status: 401 })
      }
      session = kind
      n += 1
      return Response.json({ access_token: token(), token_type: 'bearer', expires_in: 900, user: me(kind) })
    }
    if (url === '/api/auth/logout') {
      session = null
      return new Response(null, { status: 204 })
    }
    if (url === '/api/auth/me') {
      if (!session || headers.Authorization !== `Bearer ${token()}`) {
        return Response.json({ code: 'unauthorized', message: 'Требуется вход', details: {} }, { status: 401 })
      }
      return Response.json(me(session))
    }
    return Response.json({ code: 'test', message: 'нет данных в тесте', details: {} }, { status: 500 })
  })
  vi.stubGlobal('fetch', fn)
  return {
    calls,
    expireSession: () => {
      session = null
    },
  }
}

function renderRealApp(path: string) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })
  const navigator: AuthNavigator = {
    go: (to) => void router.navigate(to, { replace: true }),
    current: () => `${router.state.location.pathname}${router.state.location.search}`,
  }
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthProvider navigator={navigator}>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { ...utils, router }
}

beforeEach(() => setApiMode('real'))
afterEach(() => {
  vi.unstubAllGlobals()
  setApiMode('mock')
  setAccessToken(null)
})

describe('правила доступа к кабинету', () => {
  it('ждём, пока проверяется сессия', () => {
    expect(resolveCabinetAccess('loading', null, 'candidate', '/candidate')).toEqual({ type: 'wait' })
  })
  it('нет сессии → вход с возвратом', () => {
    expect(resolveCabinetAccess('anonymous', null, 'candidate', '/candidate/profile?x=1')).toEqual({
      type: 'redirect',
      to: '/login?next=%2Fcandidate%2Fprofile%3Fx%3D1',
    })
  })
  it('чужая роль → свой кабинет', () => {
    expect(resolveCabinetAccess('authenticated', 'recruiter', 'candidate', '/candidate')).toEqual({ type: 'redirect', to: '/recruiter' })
  })
  it('своя роль → пускаем', () => {
    expect(resolveCabinetAccess('authenticated', 'candidate', 'candidate', '/candidate')).toEqual({ type: 'allow' })
  })
  it('next — только внутренний путь', () => {
    expect(safeNext('/candidate/fsp')).toBe('/candidate/fsp')
    expect(safeNext('//evil.example')).toBeNull()
    expect(safeNext('https://evil.example')).toBeNull()
    expect(loginUrl('/')).toBe('/login')
  })
})

describe('RequireAuth', () => {
  function Shell({ path }: { path: string }) {
    return (
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/login" element={<p>Экран входа</p>} />
              <Route
                path="/candidate"
                element={
                  <RequireAuth role="candidate">
                    <p>Кабинет соискателя</p>
                  </RequireAuth>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>
    )
  }

  it('без сессии отправляет на вход', async () => {
    fakeAuthBackend(null)
    render(<Shell path="/candidate" />)
    expect(await screen.findByText('Экран входа')).toBeInTheDocument()
    expect(screen.queryByText('Кабинет соискателя')).not.toBeInTheDocument()
  })

  it('с сессией (refresh-cookie) показывает кабинет после GET /auth/me', async () => {
    const backend = fakeAuthBackend('candidate')
    window.localStorage.setItem('fsp.hasSession', '1')
    render(<Shell path="/candidate" />)
    expect(await screen.findByText('Кабинет соискателя')).toBeInTheDocument()
    expect(backend.calls).toEqual(['POST /api/auth/refresh', 'GET /api/auth/me'])
  })
})

describe('вход, выход и защита маршрутов (настоящий API)', () => {
  it('аноним открывает кабинет → /login?next=…, после входа возвращается обратно', async () => {
    const user = userEvent.setup()
    const backend = fakeAuthBackend(null)
    const { router } = renderRealApp('/candidate/settings')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toBe('?next=%2Fcandidate%2Fsettings')
    // без признака сессии при загрузке refresh не дёргаем
    expect(backend.calls).not.toContain('POST /api/auth/refresh')

    await user.type(await screen.findByLabelText(/^Почта/), 'candidate@example.com')
    await user.type(screen.getByLabelText(/^Пароль/), 'demo1234')
    await user.click(screen.getByRole('button', { name: 'Войти' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/candidate/settings'))
    expect(getAccessToken()).toBe('tok-candidate-1')
    expect(window.localStorage.getItem('fsp.hasSession')).toBe('1')
    // токен — только в памяти
    expect(Object.values({ ...window.localStorage }).some((v) => String(v).includes('tok-'))).toBe(false)
  })

  it('чужая роль → в свой кабинет', async () => {
    fakeAuthBackend('recruiter')
    window.localStorage.setItem('fsp.hasSession', '1')
    const { router } = renderRealApp('/candidate/profile')
    await waitFor(() => expect(router.state.location.pathname).toBe('/recruiter'))
  })

  it('неверный пароль — ошибка на форме, без refresh', async () => {
    const user = userEvent.setup()
    const backend = fakeAuthBackend(null)
    renderRealApp('/login')
    await user.type(await screen.findByLabelText(/^Почта/), 'candidate@example.com')
    await user.type(screen.getByLabelText(/^Пароль/), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Войти' }))
    expect(await screen.findByText('Неверная почта или пароль')).toBeInTheDocument()
    expect(backend.calls.filter((c) => c.includes('refresh'))).toHaveLength(0)
  })

  it('выход: POST /auth/logout, токен и признак сессии стёрты', async () => {
    const backend = fakeAuthBackend('candidate')
    window.localStorage.setItem('fsp.hasSession', '1')
    let auth: ReturnType<typeof useAuth> | null = null
    function Probe() {
      auth = useAuth()
      return <p>{auth.status}</p>
    }
    render(
      <QueryClientProvider client={new QueryClient()}>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('authenticated')).toBeInTheDocument()
    expect(auth!.user).toMatchObject({ name: 'Никита Латыпов', email: 'candidate@example.com', role: 'candidate' })
    await act(async () => {
      await auth!.logout()
    })
    expect(screen.getByText('anonymous')).toBeInTheDocument()
    expect(backend.calls).toContain('POST /api/auth/logout')
    expect(getAccessToken()).toBeNull()
    expect(window.localStorage.getItem('fsp.hasSession')).toBeNull()
    expect(auth!.user).toBeNull()
  })

  it('refresh-cookie истекла во время работы → сессия сброшена, кабинет отправляет на вход', async () => {
    const backend = fakeAuthBackend('candidate')
    window.localStorage.setItem('fsp.hasSession', '1')
    const { router } = renderRealApp('/candidate/settings')
    await waitFor(() => expect(getAccessToken()).toBe('tok-candidate-1'))
    backend.expireSession()
    setAccessToken('stale')
    // любой запрос с протухшим токеном: 401 → refresh 401 → выход
    await act(async () => {
      await import('@/shared/api/client').then(({ api }) => api.get('/auth/me').catch(() => undefined))
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    expect(router.state.location.search).toBe('?next=%2Fcandidate%2Fsettings')
  })
})
