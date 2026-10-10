import type { Tone } from '@/shared/ui'
import type { ApplicationStatus, ContactMethodType, S, WorkFormat } from './api'

export const WORK_FORMAT_LABELS: Record<WorkFormat, string> = {
  office: 'Офис',
  hybrid: 'Гибрид',
  remote: 'Удалённо',
}

export const WORK_FORMAT_OPTIONS = (Object.keys(WORK_FORMAT_LABELS) as WorkFormat[]).map((value) => ({
  value,
  label: WORK_FORMAT_LABELS[value],
}))

export const CONTACT_TYPE_LABELS: Record<ContactMethodType, string> = {
  email: 'Почта',
  phone: 'Телефон',
  telegram: 'Telegram',
  other: 'Другое',
}

export const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  new: 'Новый',
  viewed: 'Просмотрен',
  invited: 'Приглашён',
  rejected: 'Отказ',
}

/** Допустимые переходы статуса отклика — как на бэкенде (APPLICATION_TRANSITIONS); назад нельзя, иначе 409. */
export const APPLICATION_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  new: ['viewed', 'invited', 'rejected'],
  viewed: ['invited', 'rejected'],
  invited: ['rejected'],
  rejected: ['invited'],
}

export const APPLICATION_STATUS_TONE: Record<ApplicationStatus, Tone> = {
  new: 'accent',
  viewed: 'info',
  invited: 'success',
  rejected: 'neutral',
}

export const VACANCY_STATUS: Record<S['VacancyStatus'], { label: string; tone: Tone }> = {
  draft: { label: 'Черновик', tone: 'neutral' },
  published: { label: 'Опубликована', tone: 'success' },
  unpublished: { label: 'Снята с публикации', tone: 'warning' },
}

export const RELATION_LABELS: Record<S['CategoryRelation'], string> = {
  primary: 'Основная',
  grade_lower: 'Грейд ниже',
  grade_higher: 'Грейд выше',
  adjacent_specialization: 'Смежная специализация',
}

export const SUBMISSION_STATUS: Record<S['SubmissionStatus'], { label: string; tone: Tone }> = {
  assigned: { label: 'Предложено', tone: 'neutral' },
  submitted: { label: 'Нужна оценка', tone: 'accent' },
  graded: { label: 'Оценено', tone: 'success' },
  expired: { label: 'Срок истёк', tone: 'warning' },
  skipped: { label: 'Выбрал другую', tone: 'neutral' },
}

export const ANSWER_KIND_LABELS: Record<S['AnswerKind'], string> = {
  text: 'Текст',
  code: 'Код',
  approach: 'Подход',
}

export const SCORE_LABELS = ['Не решено', 'Слабо', 'Хорошо', 'Отлично'] as const

export const EVENT_LABELS: Record<S['InvitationEventType'], string> = {
  created: 'Приглашение отправлено',
  viewed: 'Кандидат открыл приглашение',
  accepted: 'Кандидат принял приглашение',
  declined: 'Кандидат отклонил приглашение',
  expired: 'Срок ответа истёк',
  withdrawn: 'Приглашение отозвано',
  contacts_revealed: 'Контакты открыты обеим сторонам',
}

/** «2 года», «5 лет». */
export function yearsText(n: number): string {
  const n10 = n % 10
  const n100 = n % 100
  const word = n10 === 1 && n100 !== 11 ? 'год' : n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14) ? 'года' : 'лет'
  return `${String(n).replace('.', ',')} ${word}`
}
