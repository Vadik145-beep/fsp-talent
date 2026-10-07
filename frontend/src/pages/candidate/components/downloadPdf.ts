import { apiFetch } from '@/shared/api'

/**
 * Скачать стандартизированный PDF-профиль (GET /candidates/me/profile.pdf).
 * Через общий клиент: Bearer/демо-заголовки и обновление токена по 401 — как у остальных запросов.
 */
export async function downloadProfilePdf(): Promise<void> {
  const blob = await apiFetch<Blob>('/candidates/me/profile.pdf', {
    headers: { Accept: 'application/pdf' },
    responseType: 'blob',
  })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'fsp-profile.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
