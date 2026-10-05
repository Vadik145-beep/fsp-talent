import { QueryClient } from '@tanstack/react-query'
import { isApiError } from './client'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // 4xx повторять бессмысленно; сеть и 5xx — один повтор.
      retry: (failureCount, error) => {
        if (isApiError(error) && error.status >= 400 && error.status < 500) return false
        return failureCount < 1
      },
    },
    mutations: { retry: false },
  },
})
