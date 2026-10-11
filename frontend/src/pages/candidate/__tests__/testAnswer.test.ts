import { describe, expect, it } from 'vitest'
import { codeOutputHint, numericHint } from '../components/testAnswer'

describe('подсказки к ответу — по условию задачи', () => {
  it('число: «целое» без дробной части', () => {
    expect(numericHint('Ответ — целое число секунд.')).toBe('Целое число')
    expect(numericHint('Сколько раз в консоли появится render?')).toBe('Целое число')
    expect(numericHint('Чему равна точность модели?')).toMatch(/через запятую/)
  })
  it('«что выведет»: про консоль только если условие о выводе', () => {
    expect(codeOutputHint('Что выведет этот код в Node.js?')).toMatch(/консоли/)
    expect(codeOutputHint('Что будет показано в строках сверху вниз? Ответ — пары Имя=текст.')).not.toMatch(/консоли/)
  })
})
