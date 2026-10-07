import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/shared/api'
import { apiFieldErrors, isMatchesKey, refreshRecruiter, rk, upsertInList } from './api'

/** Помощники кабинета рекрутера для работы с реальным API: ошибки полей и кэш после мутаций. */
describe('apiFieldErrors', () => {
  it('понимает details.fields (моки)', () => {
    const e = new ApiError(422, 'validation_error', 'Проверьте поля формы.', { fields: { salary_to: 'Укажите сумму «до»' } })
    expect(apiFieldErrors(e)).toEqual({ salary_to: 'Укажите сумму «до»' })
  })

  it('понимает details.errors FastAPI и пишет по-русски', () => {
    const e = new ApiError(422, 'validation_error', 'Ошибка валидации данных', {
      errors: [
        { type: 'string_too_short', loc: ['body', 'description'], msg: 'String should have at least 10 characters', ctx: { min_length: 10 } },
        { type: 'missing', loc: ['body', 'salary_to'], msg: 'Field required' },
        { type: 'string_too_short', loc: ['body', 'contact_method', 'value'], msg: 'String should have at least 2 characters', ctx: { min_length: 2 } },
        { type: 'greater_than', loc: ['body', 'salary_from'], msg: 'Input should be greater than 0', ctx: { gt: 0 } },
      ],
    })
    expect(apiFieldErrors(e)).toEqual({
      description: 'Не короче 10 символов',
      salary_to: 'Обязательное поле',
      contact_method: 'Не короче 2 символов',
      salary_from: 'Должно быть больше 0',
    })
  })

  it('salary_range_invalid (ошибка модели целиком) — на поле «от»', () => {
    const e = new ApiError(422, 'validation_error', 'Ошибка валидации данных', {
      errors: [{ type: 'salary_range_invalid', loc: ['body'], msg: 'Зарплата «от» не может быть больше зарплаты «до»' }],
    })
    expect(apiFieldErrors(e)).toEqual({ salary_from: '«От» не может быть больше «до»' })
    expect(apiFieldErrors(new ApiError(422, 'salary_range_invalid', 'Сумма «от» больше суммы «до».'))).toEqual({
      salary_from: '«От» не может быть больше «до»',
    })
  })

  it('русское сообщение валидатора оставляет, английское заменяет', () => {
    const e = new ApiError(422, 'validation_error', '', {
      errors: [
        { type: 'value_error', loc: ['body', 'city'], msg: 'Value error, Город не найден' },
        { type: 'url_parsing', loc: ['body', 'website'], msg: 'Input should be a valid URL' },
      ],
    })
    expect(apiFieldErrors(e)).toEqual({ city: 'Город не найден', website: 'Проверьте значение' })
  })

  it('не ошибка API — пусто', () => {
    expect(apiFieldErrors(new Error('x'))).toEqual({})
    expect(apiFieldErrors(new ApiError(409, 'already_invited', 'Уже приглашён'))).toEqual({})
  })
})

describe('кэш после мутаций', () => {
  it('upsertInList заменяет по id и добавляет новую запись в начало', () => {
    const qc = new QueryClient()
    qc.setQueryData(rk.vacancies, [{ id: 1, title: 'a' }, { id: 2, title: 'b' }])
    upsertInList(qc, rk.vacancies, { id: 2, title: 'B' })
    upsertInList(qc, rk.vacancies, { id: 3, title: 'c' })
    expect(qc.getQueryData(rk.vacancies)).toEqual([{ id: 3, title: 'c' }, { id: 1, title: 'a' }, { id: 2, title: 'B' }])
    // списка в кэше нет — не создаём неполный
    upsertInList(qc, rk.tasks, { id: 1 })
    expect(qc.getQueryData(rk.tasks)).toBeUndefined()
  })

  it('refreshRecruiter не трогает обновлённые ключи, подборки по условию и справочники', async () => {
    const qc = new QueryClient()
    const keys = [rk.invitations, rk.invitation(5), rk.quota, rk.dashboard, rk.skills, rk.matches(1, { category: 'backend:middle' }), rk.candidate(32)]
    for (const k of keys) qc.setQueryData(k, {})
    await refreshRecruiter(qc, rk.invitations, rk.candidate(32), isMatchesKey)
    const stale = keys.filter((k) => qc.getQueryState(k)?.isInvalidated).map((k) => k.slice(1).join('/'))
    expect(stale).toEqual(['quota', 'dashboard'])
  })
})
