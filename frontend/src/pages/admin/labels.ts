/** Подписи и цвета статусов кабинета администратора. */
import type { Tone } from '@/shared/ui'
import type { ItemFormat, ItemStatus, ReportReason, ReportStatus } from './api'

export const ITEM_FORMAT_LABELS: Record<ItemFormat, string> = {
  single_choice: 'Один ответ',
  multiple_choice: 'Несколько ответов',
  numeric: 'Число',
  short_text: 'Короткий ответ',
  code_output: 'Что выведет код',
  find_error_line: 'Строка с ошибкой',
  ordering: 'Порядок шагов',
}

export const ITEM_STATUS_LABELS: Record<ItemStatus, string> = {
  draft: 'Черновик',
  pilot: 'Пилот',
  active: 'Активен',
  retired: 'Выведен',
}

export const ITEM_STATUS_TONES: Record<ItemStatus, Tone> = {
  draft: 'warning',
  pilot: 'info',
  active: 'success',
  retired: 'neutral',
}

export const ITEM_STATUS_HINTS: Record<ItemStatus, string> = {
  draft: 'Черновик ждёт одобрения администратора, кандидатам не показывается',
  pilot: 'Непроверочная задача: показывается в тесте, но не влияет на балл, пока не наберёт ответы',
  active: 'Рабочая задача: влияет на оценку уровня',
  retired: 'Выведена из оборота: больше не показывается',
}

export const REPORT_REASON_LABELS: Record<ReportReason, string> = {
  fake_vacancy: 'Фиктивная вакансия',
  spam: 'Спам',
  salary_mismatch: 'Зарплата не совпала',
  rude: 'Грубость',
  other: 'Другое',
}

export const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  new: 'Новая',
  in_review: 'В работе',
  resolved: 'Решена',
  rejected: 'Отклонена',
}

export const REPORT_STATUS_TONES: Record<ReportStatus, Tone> = {
  new: 'accent',
  in_review: 'info',
  resolved: 'success',
  rejected: 'neutral',
}

/** Действия журнала. Неизвестное действие показываем кодом. */
export const AUDIT_ACTION_LABELS: Record<string, string> = {
  contacts_revealed: 'Раскрыты контакты',
  grade_changed: 'Смена грейда',
  user_blocked: 'Блокировка пользователя',
  user_unblocked: 'Разблокировка пользователя',
  user_role_changed: 'Смена роли',
  company_blocked: 'Блокировка компании',
  company_unblocked: 'Разблокировка компании',
  item_leak_flagged: 'Флаг утечки',
  item_retired: 'Шаблон выведен',
  item_approved: 'Черновик одобрен',
  items_recalibrated: 'Пересчёт калибровки',
  settings_updated: 'Изменены настройки',
  catalog_created: 'Добавлено в справочник',
  catalog_updated: 'Изменён справочник',
  catalog_deleted: 'Удалено из справочника',
  report_resolved: 'Жалоба обработана',
  consent_granted: 'Дано согласие',
  consent_revoked: 'Отзыв согласия',
}

export const AUDIT_ACTION_TONES: Record<string, Tone> = {
  contacts_revealed: 'success',
  grade_changed: 'violet',
  user_blocked: 'danger',
  company_blocked: 'danger',
  catalog_deleted: 'warning',
  item_leak_flagged: 'warning',
  item_retired: 'neutral',
  consent_revoked: 'warning',
}

export const TARGET_TYPE_LABELS: Record<string, string> = {
  invitation: 'Приглашение',
  candidate: 'Кандидат',
  user: 'Пользователь',
  company: 'Компания',
  item: 'Шаблон задачи',
  settings: 'Настройки',
  consent: 'Согласие',
  report: 'Жалоба',
  catalog: 'Справочник',
  skill: 'Технология',
  specialization: 'Специализация',
  grade: 'Грейд',
  category: 'Категория',
  topic: 'Тема теста',
}

/** Подписи ключей настроек (для журнала: «было → стало»). */
export const SETTING_LABELS: Record<string, string> = {
  grade_thresholds: 'Пороги θ',
  grade_change_cooldown_days: 'Кулдаун смены грейда, дней',
  retry_cooldown_days: 'Кулдаун повтора, дней',
  invitation_quota: 'Квота приглашений',
  invitation_ttl_days: 'Срок приглашения, дней',
  cat_se_stop: 'Стоп теста по точности',
  cat_max_items: 'Максимум задач',
  exposure_max_share: 'Лимит показов задачи',
  ranking_weights: 'Веса ранжирования',
}

/** 0.873 → «87 %», null → «—». */
export function pct(value: number | null | undefined, digits = 0): string {
  if (value == null || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits).replace('.', ',')}\u00A0%`
}

/** 1.234 → «1,23». */
export function num(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return '—'
  return value.toFixed(digits).replace('.', ',').replace('-', '−')
}
