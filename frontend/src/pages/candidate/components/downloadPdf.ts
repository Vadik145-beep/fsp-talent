import { buildUrl, getApiRole, getErrorMessage } from '@/shared/api'
import { getApiUserId } from '@/shared/api/client'

/** Скачать стандартизированный PDF-профиль (GET /candidates/me/profile.pdf). */
export async function downloadProfilePdf(): Promise<void> {
  const headers: Record<string, string> = { Accept: 'application/pdf' }
  const role = getApiRole()
  const userId = getApiUserId()
  if (role) headers['X-Demo-Role'] = role
  if (userId !== null) headers['X-Demo-User-Id'] = String(userId)
  const res = await fetch(buildUrl('/candidates/me/profile.pdf'), { headers, credentials: 'include' })
  if (!res.ok) {
    let message = 'Не удалось сформировать PDF'
    try {
      const body = (await res.json()) as { message?: string }
      if (body.message) message = body.message
    } catch (err) {
      message = getErrorMessage(err) || message
    }
    throw new Error(message)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'fsp-profile.pdf'
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
