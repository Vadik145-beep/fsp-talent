import type { Step } from '@/shared/ui'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import type { GradeCode, SpecializationCode, SurveyResult } from '../api'

/** Шаги мастера онбординга: тест и результат — отдельные маршруты, Stepper общий. */
export const ONBOARDING_STEPS: Step[] = [
  { id: 'profile', label: 'Профиль' },
  { id: 'survey', label: 'Опрос' },
  { id: 'grade', label: 'Грейд' },
  { id: 'test', label: 'Тест' },
  { id: 'result', label: 'Результат' },
]

export interface OnboardingProgress {
  step: number
  survey?: SurveyResult | null
  specialization?: SpecializationCode | null
  grade?: GradeCode | null
}

const KEY = 'fsp.candidate.onboarding'

export function readOnboarding(): OnboardingProgress {
  try {
    const raw = readStorage(KEY)
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<OnboardingProgress>
      return { ...parsed, step: typeof parsed.step === 'number' ? parsed.step : 0 }
    }
  } catch {
    // испорченное значение — начинаем сначала
  }
  return { step: 0 }
}

export function writeOnboarding(value: OnboardingProgress | null): void {
  writeStorage(KEY, value ? JSON.stringify(value) : null)
}
