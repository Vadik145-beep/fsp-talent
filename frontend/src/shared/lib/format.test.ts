import { describe, expect, it } from 'vitest'
import { formatDuration, formatMoney, formatPercent, formatSalaryRange, formatSigned, plural, pluralize, toFixedRound } from './format'
import { categoryLabel } from '@/shared/config/dictionaries'
import { pseudonymCode } from './pseudonym'

// Неразрывный пробел заменяем обычным, чтобы ожидания читались.
const n = (s: string) => s.replace(/\u00A0/g, ' ')

describe('форматирование', () => {
  it('вилка зарплаты', () => {
    expect(n(formatSalaryRange(250000, 350000))).toBe('от 250 000 до 350 000 ₽')
    expect(n(formatSalaryRange(250000, null))).toBe('от 250 000 ₽')
    expect(n(formatSalaryRange(undefined, 90000))).toBe('до 90 000 ₽')
    expect(n(formatSalaryRange(300000, 300000))).toBe('300 000 ₽')
    expect(formatSalaryRange()).toBe('Зарплата не указана')
  })

  it('деньги, вклад, длительность, склонение', () => {
    expect(n(formatMoney(1234567))).toBe('1 234 567 ₽')
    expect(formatSigned(0.324)).toBe('+0,32')
    expect(formatSigned(-0.05)).toBe('−0,05')
    expect(formatDuration(65)).toBe('01:05')
    expect(formatDuration(3725)).toBe('1:02:05')
    expect(plural(1, ['кандидат', 'кандидата', 'кандидатов'])).toBe('кандидат')
    expect(plural(3, ['кандидат', 'кандидата', 'кандидатов'])).toBe('кандидата')
    expect(plural(11, ['кандидат', 'кандидата', 'кандидатов'])).toBe('кандидатов')
    expect(plural(25, ['кандидат', 'кандидата', 'кандидатов'])).toBe('кандидатов')
  })

  it('округление без ошибки двоичной дроби', () => {
    // 0.5765 * 100 = 57.64999…: toFixed дал бы «57.6», в отчёте валидации — 57,7.
    expect(toFixedRound(0.5765 * 100, 1)).toBe('57.7')
    expect(n(formatPercent(0.5765, 1))).toBe('57,7 %')
    expect(n(formatPercent(0.9474, 1))).toBe('94,7 %')
    expect(n(formatPercent(0.1267, 1))).toBe('12,7 %')
    expect(toFixedRound(1.005, 2)).toBe('1.01')
    expect(toFixedRound(0.3576, 2)).toBe('0.36')
    expect(toFixedRound(-0.125, 2)).toBe('-0.13')
    expect(toFixedRound(-0.001, 1)).toBe('0.0')
    expect(toFixedRound(20, 0)).toBe('20')
    expect(toFixedRound(1e-9, 2)).toBe('0.00')
  })

  it('число со склонением', () => {
    expect(n(pluralize(143, ['символ', 'символа', 'символов']))).toBe('143 символа')
    expect(n(pluralize(1, ['жалоба', 'жалобы', 'жалоб']))).toBe('1 жалоба')
    expect(n(pluralize(12, ['жалоба', 'жалобы', 'жалоб']))).toBe('12 жалоб')
    expect(n(pluralize(1021, ['пара', 'пары', 'пар']))).toBe('1 021 пара')
  })

  it('подпись категории и псевдоним', () => {
    expect(categoryLabel('backend:middle')).toBe('Backend · Middle')
    expect(categoryLabel('data_ml:intern')).toBe('Data Science / ML · Стажёр')
    expect(categoryLabel('unknown')).toBe('unknown')
    expect(pseudonymCode('cand-1')).toMatch(/^[0-9A-F]{4}$/)
    expect(pseudonymCode('cand-1')).toBe(pseudonymCode('cand-1'))
  })
})
