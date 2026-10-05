/** Справочники MVP. Коды фиксированы (см. общие правила), подписи — для интерфейса. */

export const SPECIALIZATIONS = ['backend', 'frontend', 'mobile', 'data_ml', 'qa', 'devops'] as const
export type Specialization = (typeof SPECIALIZATIONS)[number]

export const SPECIALIZATION_LABELS: Record<Specialization, string> = {
  backend: 'Backend',
  frontend: 'Frontend',
  mobile: 'Mobile',
  data_ml: 'Data Science / ML',
  qa: 'QA',
  devops: 'DevOps',
}

export const GRADES = ['intern', 'junior', 'middle', 'senior'] as const
export type Grade = (typeof GRADES)[number]

export const GRADE_LABELS: Record<Grade, string> = {
  intern: 'Стажёр',
  junior: 'Junior',
  middle: 'Middle',
  senior: 'Senior',
}

/** Код категории: "backend:middle". */
export type CategoryCode = `${Specialization}:${Grade}`

export function categoryCode(spec: Specialization, grade: Grade): CategoryCode {
  return `${spec}:${grade}`
}

/** "backend:middle" → «Backend · Middle». Неизвестный код возвращается как есть. */
export function categoryLabel(code: string): string {
  const [spec, grade] = code.split(':')
  const s = SPECIALIZATION_LABELS[spec as Specialization]
  const g = GRADE_LABELS[grade as Grade]
  return s && g ? `${s} · ${g}` : code
}

export const SPECIALIZATION_OPTIONS = SPECIALIZATIONS.map((value) => ({
  value,
  label: SPECIALIZATION_LABELS[value],
}))

export const GRADE_OPTIONS = GRADES.map((value) => ({ value, label: GRADE_LABELS[value] }))

/** Статусы приглашений (E7). */
export const INVITATION_STATUSES = [
  'sent',
  'viewed',
  'accepted',
  'declined',
  'expired',
  'withdrawn',
] as const
export type InvitationStatus = (typeof INVITATION_STATUSES)[number]

export const INVITATION_STATUS_LABELS: Record<InvitationStatus, string> = {
  sent: 'Отправлено',
  viewed: 'Просмотрено',
  accepted: 'Принято',
  declined: 'Отклонено',
  expired: 'Истекло',
  withdrawn: 'Отозвано',
}
