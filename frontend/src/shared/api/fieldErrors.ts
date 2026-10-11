import { isApiError } from './client'

/** Одна ошибка валидации FastAPI/pydantic из `details.errors`. */
interface PydanticError {
  type?: string
  loc?: (string | number)[]
  msg?: string
  ctx?: Record<string, unknown>
}

/** Человеческий текст для частых полей (pydantic отвечает по-английски). */
const FIELD_TEXT: Record<string, string> = {
  email: 'Введите почту в формате name@example.com',
  password: 'Введите пароль',
  new_password: 'Введите новый пароль',
}

function pydanticMessage(field: string, e: PydanticError): string {
  const ctx = e.ctx ?? {}
  switch (e.type) {
    case 'missing':
      return field === 'email' ? 'Введите почту' : FIELD_TEXT[field] ?? 'Заполните поле'
    case 'string_too_short':
      return Number(ctx.min_length) <= 1 ? 'Заполните поле' : `Не короче ${String(ctx.min_length)} символов`
    case 'string_too_long':
      return `Не длиннее ${String(ctx.max_length)} символов`
    case 'too_short':
      return 'Заполните поле'
    case 'too_long':
      return 'Слишком много значений'
    case 'greater_than':
      return `Должно быть больше ${String(ctx.gt)}`
    case 'greater_than_equal':
      return `Не меньше ${String(ctx.ge)}`
    case 'less_than':
      return `Должно быть меньше ${String(ctx.lt)}`
    case 'less_than_equal':
      return `Не больше ${String(ctx.le)}`
    case 'int_parsing':
    case 'int_type':
    case 'int_from_float':
      return 'Нужно целое число'
    case 'enum':
    case 'literal_error':
      return 'Выберите значение из списка'
  }
  const msg = (e.msg ?? '').replace(/^Value error,\s*/, '')
  if (/[а-яё]/i.test(msg)) return msg
  return FIELD_TEXT[field] ?? 'Проверьте значение'
}

/**
 * Ошибки полей из ответа API 422: `details.fields` ({поле: текст}, свои проверки бэкенда)
 * или `details.errors` (список ошибок pydantic: loc = ["body", "поле", ...]).
 * Пустой объект — ошибок по полям нет (показывать общий текст).
 */
export function apiFieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) return {}
  const result: Record<string, string> = {}
  const fields = error.details?.fields
  if (fields && typeof fields === 'object') {
    for (const [k, v] of Object.entries(fields as Record<string, unknown>)) result[k] = String(v)
  }
  const errors = error.details?.errors
  if (Array.isArray(errors)) {
    for (const e of errors as PydanticError[]) {
      const loc = (e.loc ?? []).filter((x) => x !== 'body')
      const field = typeof loc[0] === 'string' ? loc[0] : null
      if (field && !result[field]) result[field] = pydanticMessage(field, e)
    }
  }
  return result
}

/** Почта похожа на настоящую (та же проверка «до отправки» на всех формах входа). */
export function looksLikeEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim())
}
