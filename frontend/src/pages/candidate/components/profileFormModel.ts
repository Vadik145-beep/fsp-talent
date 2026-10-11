import { formatPhone } from '@/shared/lib/format'
import { GRADES, SPECIALIZATIONS } from '@/shared/config/dictionaries'
import type { CandidateProfile, CandidateProfileUpdate, GradeCode, S, SpecializationCode, WorkFormat } from '../api'

/** Состояние формы профиля (строки для числовых полей — чтобы можно было стереть значение). */
export interface ProfileFormState {
  full_name: string
  phone: string
  telegram: string
  city: string
  work_formats: WorkFormat[]
  stack: string[]
  roles_in_team: string[]
  experience_years: string
  soft_skills: string[]
  about: string
  links: S['ProfileLink'][]
  min_salary: string
}

/** Уверенность распознавания по полям формы (из PDF). */
export type ParsedConfidence = Partial<Record<keyof ProfileFormState, number>>

export function formFromProfile(p: Partial<CandidateProfile> | undefined): ProfileFormState {
  return {
    full_name: p?.full_name ?? '',
    phone: p?.phone ? formatPhone(p.phone) : '',
    telegram: p?.telegram ?? '',
    city: p?.city ?? '',
    work_formats: p?.work_formats ?? [],
    stack: p?.stack ?? [],
    roles_in_team: p?.roles_in_team ?? [],
    experience_years: p?.experience_years != null ? String(p.experience_years).replace('.', ',') : '',
    soft_skills: p?.soft_skills ?? [],
    about: p?.about ?? '',
    links: p?.links ?? [],
    min_salary: p?.min_salary != null ? String(p.min_salary) : '',
  }
}

function guessLinkType(url: string): S['LinkType'] {
  if (/github\.com/i.test(url)) return 'github'
  if (/gitlab\./i.test(url)) return 'gitlab'
  if (/linkedin\./i.test(url)) return 'linkedin'
  return 'portfolio'
}

/** Ссылка без схемы («github.com/имя») → «https://github.com/имя». Пустую строку не трогаем. */
export function normalizeUrl(raw: string): string {
  const url = raw.trim()
  if (!url) return ''
  if (/^[a-z][a-z\d+.-]*:\/\//i.test(url)) return url
  return `https://${url.replace(/^\/+/, '')}`
}

const WORK_FORMAT_CODES: readonly WorkFormat[] = ['office', 'hybrid', 'remote']
const isWorkFormat = (v: string): v is WorkFormat => (WORK_FORMAT_CODES as readonly string[]).includes(v)

const asString = (v: unknown) => (typeof v === 'string' ? v : typeof v === 'number' ? String(v) : '')
const asList = (v: unknown) => (Array.isArray(v) ? v.filter((x): x is string => typeof x === 'string') : [])

/**
 * Специализация и грейд, заявленные в резюме. Это не категория: категорию присваивает только тест,
 * а резюме лишь предзаполняет выбор в онбординге.
 */
export interface ResumeClaim {
  specialization?: { value: SpecializationCode; confidence: number }
  grade?: { value: GradeCode; confidence: number }
}

const isSpecialization = (v: string): v is SpecializationCode => (SPECIALIZATIONS as readonly string[]).includes(v)
const isGrade = (v: string): v is GradeCode => (GRADES as readonly string[]).includes(v)

/** Подставить распознанные из PDF поля в форму. Возвращает форму, уверенность по полям и заявленную категорию. */
export function applyParsedResume(
  base: ProfileFormState,
  parsed: S['ResumeParseResponse'],
): { form: ProfileFormState; confidence: ParsedConfidence; claim: ResumeClaim } {
  const form = { ...base }
  const confidence: ParsedConfidence = {}
  const claim: ResumeClaim = {}
  for (const [key, field] of Object.entries(parsed.fields)) {
    const v = field.value
    // Не найдено в резюме: value null, confidence 0 — поле формы не трогаем.
    if (field.confidence <= 0 || v === null || v === undefined || (Array.isArray(v) && v.length === 0) || v === '') continue
    switch (key) {
      case 'phone':
        form.phone = formatPhone(asString(v))
        confidence.phone = field.confidence
        break
      case 'full_name':
      case 'telegram':
      case 'city':
      case 'about':
        form[key] = asString(v)
        confidence[key] = field.confidence
        break
      case 'experience_years':
        form.experience_years = asString(v).replace('.', ',')
        confidence.experience_years = field.confidence
        break
      case 'stack':
      case 'roles_in_team':
      case 'soft_skills':
        form[key] = asList(v)
        confidence[key] = field.confidence
        break
      case 'work_formats': {
        // Бэкенд отдаёт список кодов; на всякий случай принимаем и одну строку.
        const formats = [...new Set((typeof v === 'string' ? [v] : asList(v)).map((x) => x.trim().toLowerCase()))].filter(isWorkFormat)
        if (!formats.length) break
        form.work_formats = formats
        confidence.work_formats = field.confidence
        break
      }
      case 'links':
        form.links = asList(v)
          .map(normalizeUrl)
          .filter(Boolean)
          .map((url) => ({ type: guessLinkType(url), url }))
        confidence.links = field.confidence
        break
      case 'specialization': {
        const code = asString(v).trim().toLowerCase()
        if (isSpecialization(code)) claim.specialization = { value: code, confidence: field.confidence }
        break
      }
      case 'grade': {
        const code = asString(v).trim().toLowerCase()
        if (isGrade(code)) claim.grade = { value: code, confidence: field.confidence }
        break
      }
      default:
        break
    }
  }
  return { form, confidence, claim }
}

const URL_RE = /^https?:\/\/\S+\.\S+/i

export function parseYears(raw: string): number | null {
  const n = Number(raw.replace(',', '.').trim())
  return raw.trim() && Number.isFinite(n) ? n : null
}

export function validateProfile(f: ProfileFormState): Record<string, string> {
  const e: Record<string, string> = {}
  if (f.full_name.trim().length < 2) e.full_name = 'Укажите имя и фамилию'
  if (!f.work_formats.length) e.work_formats = 'Выберите хотя бы один формат'
  const years = parseYears(f.experience_years)
  if (years === null || years < 0 || years > 50) e.experience_years = 'Стаж — число от 0 до 50'
  if (f.min_salary.trim() && !/^\d+$/.test(f.min_salary.replace(/\s/g, ''))) e.min_salary = 'Только цифры, в рублях'
  if (f.links.some((l) => !URL_RE.test(normalizeUrl(l.url)))) e.links = 'Проверьте адрес ссылки, например github.com/имя'
  if (f.telegram.trim() && !/^@?[A-Za-z0-9_]{4,}$/.test(f.telegram.trim())) e.telegram = 'Ник в Telegram: латиница, цифры, «_»'
  return e
}

export function toUpdate(f: ProfileFormState): CandidateProfileUpdate {
  const salary = f.min_salary.replace(/\s/g, '')
  const tg = f.telegram.trim()
  return {
    full_name: f.full_name.trim(),
    phone: f.phone.trim() || null,
    telegram: tg ? (tg.startsWith('@') ? tg : `@${tg}`) : null,
    city: f.city.trim() || null,
    work_formats: f.work_formats,
    stack: f.stack,
    roles_in_team: f.roles_in_team,
    experience_years: parseYears(f.experience_years) ?? 0,
    soft_skills: f.soft_skills,
    about: f.about.trim(),
    links: f.links.map((l) => ({ ...l, url: normalizeUrl(l.url) })).filter((l) => l.url),
    min_salary: salary ? Number(salary) : null,
  }
}
