import { readStorage, writeStorage } from '@/shared/lib/storage'

/**
 * Режим данных моков — чтобы на согласовании показать все состояния экрана.
 * Переключается в демо-плашке («Данные: …»), хранится в localStorage.
 * Этот файл без импорта msw: его можно подключать в обычный код (демо-плашка).
 */
export type MockScenario = 'normal' | 'empty' | 'error' | 'slow'

export const MOCK_SCENARIO_LABELS: Record<MockScenario, string> = {
  normal: 'обычные',
  empty: 'пустые списки',
  error: 'ошибка сервера',
  slow: 'медленная сеть',
}

const KEY = 'fsp.mockScenario'

export function getMockScenario(): MockScenario {
  const v = readStorage(KEY)
  return v === 'empty' || v === 'error' || v === 'slow' ? v : 'normal'
}

export function setMockScenario(value: MockScenario): void {
  writeStorage(KEY, value === 'normal' ? null : value)
}
