import { GRADE_LABELS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import type { ResumeClaim } from './profileFormModel'

/** Заявка «из резюме» хранится в браузере, чтобы на результате теста показать «по резюме → по тесту». */
const KEY = 'fsp.candidate.resumeClaim'

export function readResumeClaim(): ResumeClaim {
  try {
    const raw = readStorage(KEY)
    return raw ? (JSON.parse(raw) as ResumeClaim) : {}
  } catch {
    return {}
  }
}

export function writeResumeClaim(claim: ResumeClaim | null): void {
  writeStorage(KEY, claim && (claim.specialization || claim.grade) ? JSON.stringify(claim) : null)
}

export const hasClaim = (c: ResumeClaim | null | undefined): c is ResumeClaim => !!c && !!(c.specialization || c.grade)

/** Подпись заявленной категории: «Frontend · Senior», «Frontend», «Senior». */
export function claimLabel(c: ResumeClaim): string {
  return [c.specialization && SPECIALIZATION_LABELS[c.specialization.value], c.grade && GRADE_LABELS[c.grade.value]]
    .filter(Boolean)
    .join(' · ')
}
