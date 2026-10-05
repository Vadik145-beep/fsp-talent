import { useState } from 'react'
import { RouterProvider } from 'react-router'
import { QueryClientProvider } from '@tanstack/react-query'
import { queryClient } from '@/shared/api/queryClient'
import { ToastProvider } from '@/shared/ui'
import { AuthProvider } from './auth/AuthContext'
import { createAppRouter } from './router'

/** Провайдеры приложения: данные (TanStack Query), уведомления, демо-авторизация, роутер. */
export function App() {
  const [router] = useState(createAppRouter)
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>
          <RouterProvider router={router} />
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  )
}
