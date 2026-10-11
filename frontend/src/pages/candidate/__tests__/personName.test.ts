import { describe, expect, it } from 'vitest'
import { greetingName } from '../components/personName'

describe('greetingName', () => {
  it('берёт имя из ФИО в любом порядке', () => {
    expect(greetingName('Колесникова Анна Сергеевна')).toBe('Анна')
    expect(greetingName('Латыпов Никита Ильич')).toBe('Никита')
    expect(greetingName('Анна Колесникова')).toBe('Анна')
    expect(greetingName('Колесникова Анна')).toBe('Анна')
    expect(greetingName('Никита Латыпов')).toBe('Никита')
    expect(greetingName('Мария')).toBe('Мария')
    expect(greetingName('  ')).toBeNull()
  })
})
