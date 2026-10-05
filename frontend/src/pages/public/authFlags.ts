import { readStorage, writeStorage } from '@/shared/lib/storage'

/**
 * Флаг «только что зарегистрировался как соискатель»: после первого входа ведём в онбординг.
 * Хранится в localStorage, сбрасывается после перехода.
 */
const ONBOARDING_KEY = 'fsp.onboardingPending'

export function markOnboardingPending(email: string): void {
  writeStorage(ONBOARDING_KEY, email.toLowerCase())
}

export function takeOnboardingPending(): boolean {
  const value = readStorage(ONBOARDING_KEY)
  if (value) writeStorage(ONBOARDING_KEY, null)
  return !!value
}

/** Префикс токена из письма в прототипе (письма не отправляются). */
export const MOCK_VERIFY_PREFIX = 'mock-verify-'

/** Демо-учётки (data/seed/demo_accounts.json), пароль у всех один. */
export const DEMO_PASSWORD = 'demo1234'
export const DEMO_LOGINS = [
  { role: 'candidate', label: 'Соискатель', email: 'candidate@example.com' },
  { role: 'recruiter', label: 'Рекрутер', email: 'recruiter@example.com' },
  { role: 'admin', label: 'Админ', email: 'admin@example.com' },
] as const
