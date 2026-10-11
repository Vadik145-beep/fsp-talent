import { describe, expect, it } from 'vitest'
import { ApiError } from './client'
import { apiFieldErrors, looksLikeEmail } from './fieldErrors'

describe('apiFieldErrors', () => {
  it('ошибки pydantic (details.errors) → текст у поля', () => {
    const err = new ApiError(422, 'validation_error', 'Ошибка валидации данных', {
      errors: [
        { type: 'value_error', loc: ['body', 'email'], msg: 'value is not a valid email address' },
        { type: 'string_too_short', loc: ['body', 'password'], msg: 'String should have at least 1 character', ctx: { min_length: 1 } },
      ],
    })
    expect(apiFieldErrors(err)).toEqual({ email: 'Введите почту в формате name@example.com', password: 'Заполните поле' })
  })

  it('свои проверки бэкенда (details.fields) и не-API ошибки', () => {
    const err = new ApiError(422, 'validation_error', 'x', { fields: { consent_processing: 'Нужно согласие' } })
    expect(apiFieldErrors(err)).toEqual({ consent_processing: 'Нужно согласие' })
    expect(apiFieldErrors(new Error('сеть'))).toEqual({})
  })

  it('looksLikeEmail', () => {
    expect(looksLikeEmail(' a@b.ru ')).toBe(true)
    expect(looksLikeEmail('a@b')).toBe(false)
  })
})
