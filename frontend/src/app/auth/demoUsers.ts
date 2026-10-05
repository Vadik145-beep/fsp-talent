import type { Role } from '@/shared/config/roles'

export interface DemoUser {
  id: string
  /** id пользователя в data/seed/users.json — уходит в API заголовком X-Demo-User-Id. */
  userId: number
  role: Role
  name: string
  email: string
  /** Подпись в меню пользователя. */
  subtitle: string
}

/**
 * Демо-пользователи прототипа (по одному на роль) — те же, что в data/seed/demo_accounts.json.
 * В волнах 2–4 заменятся настоящей сессией с бэкенда.
 */
export const DEMO_USERS: Record<Role, DemoUser> = {
  candidate: {
    id: 'demo-candidate',
    userId: 1,
    role: 'candidate',
    name: 'Никита Латыпов',
    email: 'candidate@example.com',
    subtitle: 'Соискатель',
  },
  recruiter: {
    id: 'demo-recruiter',
    userId: 41,
    role: 'recruiter',
    name: 'Ирина Белова',
    email: 'recruiter@example.com',
    subtitle: 'Рекрутер',
  },
  admin: {
    id: 'demo-admin',
    userId: 48,
    role: 'admin',
    name: 'Администратор платформы',
    email: 'admin@example.com',
    subtitle: 'Администратор платформы',
  },
}
