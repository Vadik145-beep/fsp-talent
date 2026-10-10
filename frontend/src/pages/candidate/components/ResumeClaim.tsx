import { FileText } from 'lucide-react'
import { GRADE_LABELS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { readStorage, writeStorage } from '@/shared/lib/storage'
import { cn } from '@/shared/lib/cn'
import type { ResumeClaim } from './profileFormModel'

/**
 * Специализация и грейд «из резюме». Категорию присваивает только тест,
 * поэтому резюме — лишь заявка: «по резюме Senior → тест подтвердил Middle».
 */

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

const percent = (v: number) => `${Math.round(v * 100)} %`

/** Подпись заявленной категории: «Frontend · Senior», «Frontend», «Senior». */
export function claimLabel(c: ResumeClaim): string {
  return [c.specialization && SPECIALIZATION_LABELS[c.specialization.value], c.grade && GRADE_LABELS[c.grade.value]]
    .filter(Boolean)
    .join(' · ')
}

/** Плашка «Из резюме: Frontend · Senior — заявлено, подтвердите тестом» с уверенностью распознавания. */
export function ResumeClaimNote({
  claim,
  onboarding = true,
  className,
}: {
  claim: ResumeClaim
  /** В онбординге подсказываем, где изменить выбор; в профиле — где пройти тест. */
  onboarding?: boolean
  className?: string
}) {
  if (!hasClaim(claim)) return null
  const parts: Array<{ name: string; confidence: number }> = []
  if (claim.specialization) parts.push({ name: 'специализация', confidence: claim.specialization.confidence })
  if (claim.grade) parts.push({ name: 'грейд', confidence: claim.grade.confidence })
  const unsure = parts.filter((p) => p.confidence < 0.7)
  return (
    <div
      className={cn('flex items-start gap-3 rounded-lg border border-fsp-lavender bg-surface px-4 py-3 text-sm', className)}
      data-testid="resume-claim"
    >
      <FileText className="mt-0.5 size-4 shrink-0 text-fsp-plum" aria-hidden />
      <div className="grid gap-0.5">
        <p className="text-ink">
          <span className="font-semibold">Из резюме: {claimLabel(claim)}</span> — заявлено, подтвердите тестом
        </p>
        <p className="text-[13px] text-muted">
          Уверенность распознавания: {parts.map((p) => `${p.name} ${percent(p.confidence)}`).join(', ')}.
          {unsure.length > 0 && (
            <span className="font-medium text-warning"> {unsure.map((p) => p.name).join(' и ')} — неуверенно, проверьте.</span>
          )}{' '}
          Категорию присваивает тест, а не резюме.
          {onboarding ? ' Выбор можно изменить на шагах «Опрос» и «Грейд».' : ' Пройти тест — в разделе «Категория и грейд».'}
        </p>
      </div>
    </div>
  )
}
