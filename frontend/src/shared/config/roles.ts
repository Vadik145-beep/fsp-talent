export const ROLES = ['candidate', 'recruiter', 'admin'] as const
export type Role = (typeof ROLES)[number]

export const ROLE_LABELS: Record<Role, string> = {
  candidate: 'Соискатель',
  recruiter: 'Рекрутер',
  admin: 'Администратор',
}

/** Короткие подписи для переключателя ролей. */
export const ROLE_SHORT_LABELS: Record<Role, string> = {
  candidate: 'соискатель',
  recruiter: 'рекрутер',
  admin: 'админ',
}

export const ROLE_HOME: Record<Role, string> = {
  candidate: '/candidate',
  recruiter: '/recruiter',
  admin: '/admin',
}

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value)
}
