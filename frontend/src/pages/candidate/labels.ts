import type { Tone } from '@/shared/ui'
import type { S } from './api'

/** Подписи значений из контракта API для экранов соискателя. */

export const WORK_FORMAT_LABELS: Record<S['WorkFormat'], string> = {
  office: 'Офис',
  hybrid: 'Гибрид',
  remote: 'Удалёнка',
}

export const WORK_FORMAT_OPTIONS = (Object.keys(WORK_FORMAT_LABELS) as S['WorkFormat'][]).map((value) => ({
  value,
  label: WORK_FORMAT_LABELS[value],
}))

export const FSP_DISCIPLINE_LABELS: Record<S['FspDiscipline'], string> = {
  product: 'Продуктовое программирование',
  algorithmic: 'Алгоритмическое программирование',
  cybersecurity: 'Кибербезопасность',
  uas: 'Программирование БАС',
  robotics: 'Робототехника',
}

export const FSP_LEVEL_LABELS: Record<S['FspLevel'], string> = {
  regional: 'Региональный',
  national: 'Всероссийский',
  international: 'Международный',
}

export const APPLICATION_STATUS: Record<S['ApplicationStatus'], { label: string; tone: Tone; hint: string }> = {
  new: { label: 'Отправлен', tone: 'info', hint: 'Работодатель ещё не открыл отклик' },
  viewed: { label: 'Просмотрен', tone: 'violet', hint: 'Работодатель посмотрел ваш профиль' },
  invited: { label: 'Приглашение', tone: 'success', hint: 'Работодатель хочет пообщаться' },
  rejected: { label: 'Отказ', tone: 'neutral', hint: 'Работодатель выбрал другого кандидата' },
}

export const SUBMISSION_STATUS: Record<S['SubmissionStatus'], { label: string; tone: Tone }> = {
  assigned: { label: 'Ждёт ответа', tone: 'accent' },
  submitted: { label: 'На проверке', tone: 'info' },
  graded: { label: 'Оценено', tone: 'success' },
  expired: { label: 'Срок истёк', tone: 'neutral' },
  skipped: { label: 'Выбрана другая', tone: 'neutral' },
}

export const ANSWER_KIND_LABELS: Record<S['AnswerKind'], string> = {
  approach: 'Подход',
  text: 'Текст',
  code: 'Код',
}

export const CONTACT_TYPE_LABELS: Record<S['ContactMethodType'], string> = {
  email: 'Почта',
  phone: 'Телефон',
  telegram: 'Telegram',
  other: 'Другое',
}

export const LINK_TYPE_LABELS: Record<S['LinkType'], string> = {
  github: 'GitHub',
  gitlab: 'GitLab',
  portfolio: 'Портфолио',
  linkedin: 'LinkedIn',
  other: 'Ссылка',
}

export const GRADE_EVENT_LABELS: Record<S['GradeEventType'], string> = {
  survey: 'Опрос по специализации',
  test_passed: 'Тест пройден',
  test_failed: 'Тест не пройден',
  grade_changed: 'Категория присвоена',
  offer_lower: 'Предложен тест на грейд ниже',
  offer_higher: 'Предложен тест на грейд выше',
}

export const TOPIC_LEVEL: Record<S['TopicLevel'], { label: string; tone: Tone; bar: 'success' | 'violet' | 'warning' }> = {
  strong: { label: 'Сильная сторона', tone: 'success', bar: 'success' },
  // Уровень темы считается относительно итоговой θ самого кандидата, а не грейда.
  ok: { label: 'В пределах уровня', tone: 'violet', bar: 'violet' },
  weak: { label: 'Стоит подтянуть', tone: 'warning', bar: 'warning' },
}

export const TEST_KIND_LABELS: Record<S['TestSessionKind'], string> = {
  placement: 'Первичный тест',
  lower: 'Тест на грейд ниже',
  higher: 'Тест на грейд выше',
}

export const ITEM_FORMAT_LABELS: Record<S['ItemFormat'], string> = {
  single_choice: 'Один вариант',
  multiple_choice: 'Несколько вариантов',
  numeric: 'Число',
  short_text: 'Короткий ответ',
  code_output: 'Что выведет код',
  find_error_line: 'Строка с ошибкой',
  ordering: 'Порядок шагов',
}

export const REPORT_REASON_LABELS: Record<S['ReportReason'], string> = {
  fake_vacancy: 'Фиктивная вакансия или просят денег',
  spam: 'Спам, массовая рассылка',
  salary_mismatch: 'Зарплата не совпадает с обещанной',
  rude: 'Некорректное общение',
  other: 'Другое',
}

/** Запасные подписи причин отказа, если справочник не загрузился. */
export const DECLINE_REASON_FALLBACK: Record<S['DeclineReason'], string> = {
  salary_too_low: 'Мала зарплата',
  wrong_stack: 'Не тот стек',
  not_interested_domain: 'Не интересна сфера',
  not_looking: 'Не ищу работу сейчас',
  other: 'Другое',
}

/** θ → «0,42» (знак минуса типографский). */
export function formatTheta(value: number, digits = 2): string {
  const s = Math.abs(value).toFixed(digits).replace('.', ',')
  return value < 0 ? `−${s}` : s
}
