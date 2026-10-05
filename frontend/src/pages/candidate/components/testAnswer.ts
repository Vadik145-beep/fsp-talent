import type { AnswerPayload, ItemView } from '../api'

/** Разбор числа: «40», «40,5», «1 000» (пробелы между разрядами допустимы). null — не число. */
export function parseNumber(raw: string): number | null {
  const cleaned = raw.replace(/\s/g, '').replace(',', '.')
  if (!cleaned || !/^-?\d*\.?\d+$/.test(cleaned)) return null
  return Number(cleaned)
}

/** Ответ в том виде, в каком уходит на сервер (заполнено поле нужного формата). */
export function normalizeAnswer(item: ItemView, value: AnswerPayload & { raw?: string }): AnswerPayload {
  switch (item.format) {
    case 'single_choice':
    case 'multiple_choice':
      return { choice_ids: value.choice_ids ?? [] }
    case 'numeric':
      return { value: parseNumber(value.raw ?? '') }
    case 'short_text':
    case 'code_output':
      return { text: (value.text ?? '').trim() }
    case 'find_error_line':
      return { line: value.line ?? null }
    case 'ordering':
      return { order: value.order ?? (item.steps ?? []).map((s) => s.id) }
    default:
      return {}
  }
}

/** Можно ли отправить ответ (для упорядочивания — всегда: исходный порядок тоже ответ). */
export function isAnswerReady(item: ItemView, value: AnswerPayload & { raw?: string }): boolean {
  const a = normalizeAnswer(item, value)
  switch (item.format) {
    case 'single_choice':
    case 'multiple_choice':
      return (a.choice_ids ?? []).length > 0
    case 'numeric':
      return a.value !== null && a.value !== undefined
    case 'short_text':
    case 'code_output':
      return !!a.text
    case 'find_error_line':
      return typeof a.line === 'number'
    case 'ordering':
      return true
    default:
      return false
  }
}
