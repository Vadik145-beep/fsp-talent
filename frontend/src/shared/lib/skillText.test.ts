import { describe, expect, it } from 'vitest'
import { humanizeSkillCodes } from './skillText'

const LABELS: Record<string, string> = { kotlin: 'Kotlin', jetpack_compose: 'Jetpack Compose', android_sdk: 'Android SDK', go: 'Go' }
const label = (id: string) => LABELS[id] ?? id

describe('humanizeSkillCodes', () => {
  it('перечень после «Стек:» и коды с подчёркиванием — подписями из справочника', () => {
    expect(humanizeSkillCodes('Ищем разработчика. Стек: kotlin, jetpack_compose, android_sdk. Формат: удалёнка.', label)).toBe(
      'Ищем разработчика. Стек: Kotlin, Jetpack Compose, Android SDK. Формат: удалёнка.',
    )
    expect(humanizeSkillCodes('Опыт с jetpack_compose обязателен', label)).toBe('Опыт с Jetpack Compose обязателен')
  })

  it('обычные слова и неизвестные коды не трогает', () => {
    expect(humanizeSkillCodes('Мы go-to команда, unknown_code тоже', label)).toBe('Мы go-to команда, unknown_code тоже')
  })
})
