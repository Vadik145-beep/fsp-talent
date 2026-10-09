import { useNavigate } from 'react-router'
import { BadgeCheck, CircleAlert } from 'lucide-react'
import { GRADE_LABELS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/cn'
import { Badge, Button } from '@/shared/ui'
import type { GradeCode, SpecializationCode } from '../api'
import { writeOnboarding } from './onboardingSteps'

/**
 * Статус грейда (ответ организаторов FTT.4): грейд соискатель выбирает сам,
 * но официально он присваивается только по результату теста.
 */

/** «Подтверждён тестом 8 октября 2026 г.» — рядом с категорией. */
export function GradeConfirmedBadge({ at, className }: { at?: string | null; className?: string }) {
  return (
    <Badge tone="success" icon={<BadgeCheck aria-hidden />} className={className} data-testid="grade-confirmed">
      {at ? `Подтверждён тестом ${formatDate(at)}` : 'Подтверждён тестом'}
    </Badge>
  )
}

/** Кнопка «Пройти тест»: мастер онбординга сразу на шаге теста с заявленным грейдом. */
export function TakeTestButton({
  specialization,
  grade,
  size = 'md',
  className,
}: {
  specialization: SpecializationCode
  grade: GradeCode
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const navigate = useNavigate()
  return (
    <Button
      size={size}
      className={className}
      onClick={() => {
        writeOnboarding({ step: 3, specialization, grade })
        navigate('/candidate/onboarding')
      }}
    >
      Пройти тест
    </Button>
  )
}

/** Блок «Грейд Middle — не подтверждён» с объяснением и кнопкой теста. */
export function UnconfirmedGrade({
  specialization,
  grade,
  compact,
  className,
}: {
  specialization: SpecializationCode | null | undefined
  grade: GradeCode
  compact?: boolean
  className?: string
}) {
  return (
    <div className={cn('grid gap-3', className)} data-testid="grade-unconfirmed">
      <div>
        {specialization && !compact && (
          <p className="text-3xl font-bold text-fsp-night">
            {SPECIALIZATION_LABELS[specialization]} · {GRADE_LABELS[grade]}
          </p>
        )}
        <p className={cn('flex flex-wrap items-center gap-2', !compact && 'mt-2')}>
          <span className="font-semibold text-ink">Грейд {GRADE_LABELS[grade]}</span>
          <Badge tone="warning" icon={<CircleAlert aria-hidden />}>
            не подтверждён
          </Badge>
        </p>
        <p className="mt-1 text-sm text-muted">
          Грейд выбран вами. Официально он присваивается только по результату теста — до этого работодатели не видят ваш
          профиль в подборке.
        </p>
      </div>
      {specialization && <TakeTestButton specialization={specialization} grade={grade} size={compact ? 'sm' : 'md'} className="justify-self-start" />}
    </div>
  )
}
