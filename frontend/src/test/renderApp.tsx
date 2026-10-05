import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/app/auth/AuthContext'
import { appRoutes } from '@/app/router'
import { ToastProvider } from '@/shared/ui'
import type { Role } from '@/shared/config/roles'

/** Рендер всего приложения на заданном адресе (для тестов маршрутов и layout'ов). */
export function renderApp(path: string, { role = null }: { role?: Role | null } = {}) {
  const router = createMemoryRouter(appRoutes, { initialEntries: [path] })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={client}>
      <ToastProvider>
        <AuthProvider initialRole={role}>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>,
  )
  return { ...utils, router }
}
