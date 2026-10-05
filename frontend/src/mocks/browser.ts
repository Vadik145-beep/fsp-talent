import { setupWorker } from 'msw/browser'
import { handlers } from './handlers'

/** Service Worker MSW: перехватывает /api/* в браузере, когда VITE_USE_MOCKS не 'false'. */
export const worker = setupWorker(...handlers)

export async function startMocks(): Promise<void> {
  await worker.start({
    serviceWorker: { url: '/mockServiceWorker.js' },
    quiet: true,
    onUnhandledRequest(request, print) {
      // Статику Vite пропускаем молча, о незамоканных /api — предупреждаем.
      if (new URL(request.url).pathname.startsWith('/api/')) print.warning()
    },
  })
}
