/**
 * Релевантность дисциплин ФСП специализации — копия `backend/app/fsp/scoring.py`
 * (DISCIPLINE_RELEVANCE, fsp_score_for, fsp_reason_for, fsp_profile_note) для режима моков.
 * 1 — профильно, 0,7–0,9 — смежно, 0,3–0,6 — далеко, но полезно. Ни одна дисциплина не обнуляется.
 */
import { SPECIALIZATION_LABELS, type Specialization } from '@/shared/config/dictionaries'
import { db } from './db'

export const DISCIPLINE_RELEVANCE: Record<string, Record<Specialization, number>> = {
  product: { backend: 1.0, frontend: 1.0, mobile: 1.0, data_ml: 0.7, qa: 0.8, devops: 0.7 },
  algorithmic: { backend: 1.0, frontend: 0.7, mobile: 0.7, data_ml: 1.0, qa: 0.7, devops: 0.6 },
  cybersecurity: { backend: 0.8, frontend: 0.4, mobile: 0.4, data_ml: 0.4, qa: 0.9, devops: 1.0 },
  uas: { backend: 0.5, frontend: 0.3, mobile: 0.7, data_ml: 0.9, qa: 0.5, devops: 0.5 },
  robotics: { backend: 0.5, frontend: 0.3, mobile: 0.6, data_ml: 0.9, qa: 0.5, devops: 0.5 },
}
const PROFILE_RELEVANCE = 0.9

interface Ach {
  fsp_id: string
  discipline: string
  level: string
  date: string
  place: number | null
  diploma: string | null
}

const LEVEL_WEIGHT: Record<string, number> = { regional: 1, national: 2, international: 3 }
const LEVEL_GENITIVE: Record<string, string> = { regional: 'регионального', national: 'всероссийского', international: 'международного' }
const DISCIPLINE_GENITIVE: Record<string, string> = {
  product: 'продуктовому программированию',
  algorithmic: 'алгоритмическому программированию',
  cybersecurity: 'программированию систем ИБ',
  uas: 'программированию БАС',
  robotics: 'программированию робототехники',
}
const DIPLOMA_WEIGHT: Record<string, number> = { 'Диплом I степени': 0.8, 'Диплом II степени': 0.6, 'Диплом III степени': 0.45 }

export function relevance(discipline: string, spec: string | null | undefined): number {
  if (!spec) return 1
  return DISCIPLINE_RELEVANCE[discipline]?.[spec as Specialization] ?? 1
}

function points(a: Ach): number {
  const r =
    a.place != null
      ? ({ 1: 1, 2: 0.85, 3: 0.7 } as Record<number, number>)[a.place] ?? (a.place <= 10 ? 0.4 : 0.25)
      : a.diploma
        ? DIPLOMA_WEIGHT[a.diploma] ?? 0.45
        : 0.1
  const ageYears = Math.max(0, (Date.parse(db.now()) - Date.parse(a.date)) / (365.25 * 86_400_000))
  return (LEVEL_WEIGHT[a.level] ?? 1) * r * 0.5 ** (ageYears / 2)
}

function describe(a: Ach): string {
  const what = a.place === 1 ? 'Победитель' : a.diploma || (a.place != null && a.place <= 3) ? 'Призёр' : 'Участник'
  return `${what} ${LEVEL_GENITIVE[a.level] ?? ''} соревнования по ${DISCIPLINE_GENITIVE[a.discipline] ?? 'спортивному программированию'}, ${a.date.slice(0, 4)}`
}

export function achievementsOf(fspId: string | null | undefined): Ach[] {
  if (!fspId) return []
  return (db.data.fsp_achievements as unknown as Ach[]).filter((a) => a.fsp_id === fspId)
}

/** ФСП-скор 0–100 под специализацию потребности; нет достижений — null. */
export function fspScoreFor(achs: Ach[], spec: string | null | undefined): number | null {
  if (!achs.length) return null
  const s = achs.reduce((sum, a) => sum + points(a) * relevance(a.discipline, spec), 0)
  return Math.round(100 * (1 - Math.exp(-s / 3)))
}

const profileNote = (spec: string) => `профильно для ${SPECIALIZATION_LABELS[spec as Specialization] ?? spec}`

export function fspReasonFor(achs: Ach[], spec: string | null | undefined): string | null {
  if (!achs.length) return null
  const best = [...achs].sort((a, b) => points(b) * relevance(b.discipline, spec) - points(a) * relevance(a.discipline, spec))[0]
  const profile = spec && relevance(best.discipline, spec) >= PROFILE_RELEVANCE
  return profile ? `${describe(best)} — ${profileNote(spec)}` : describe(best)
}

export function fspProfileNote(achs: Ach[], spec: string | null | undefined): string | null {
  if (!spec) return null
  const profile = achs.filter((a) => relevance(a.discipline, spec) >= PROFILE_RELEVANCE)
  if (!profile.length) return null
  const best = profile.sort((a, b) => points(b) - points(a))[0]
  return `${describe(best)} — ${profileNote(spec)}`
}
