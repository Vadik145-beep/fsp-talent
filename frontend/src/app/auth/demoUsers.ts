import type { Role } from '@/shared/config/roles'

export interface DemoUser {
  id: string
  role: Role
  name: string
  email: string
  /** Подпись в меню пользователя. */
  subtitle: string
}

/**
 * Демо-пользователи прототипа (по одному на роль). Вымышленные.
 * В волнах 2–4 заменятся настоящей сессией с бэкенда.
 */
export const DEMO_USERS: Record<Role, DemoUser> = {
  candidate: {
    id: 'demo-candidate',
    role: 'candidate',
    name: 'Анна Козлова',
    email: 'anna.kozlova@example.com',
    subtitle: 'Соискатель',
  },
  recruiter: {
    id: 'demo-recruiter',
    role: 'recruiter',
    name: 'Дмитрий Орлов',
    email: 'd.orlov@example.com',
    subtitle: 'Рекрутер',
  },
  admin: {
    id: 'demo-admin',
    role: 'admin',
    name: 'Мария Белова',
    email: 'admin@example.com',
    subtitle: 'Администратор платформы',
  },
}
