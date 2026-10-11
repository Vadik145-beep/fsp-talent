import { Gauge } from 'lucide-react'
import { getErrorMessage } from '@/shared/api'
import { GRADE_LABELS } from '@/shared/config/dictionaries'
import { cn } from '@/shared/lib/cn'
import { Button, Card, useToast } from '@/shared/ui'
import { useAcceptMeasured, type GradeCode } from '../api'

/**
 * Первичный тест не подтвердил заявленный грейд, но измерил уровень ниже —
 * категорию по нему можно взять сразу, не дожидаясь повтора через 30 дней.
 * `banner` — тёмный баннер главной, `card` — блок над результатом теста.
 */
/** Кнопка «Получить категорию …» — общая для баннера, блока результата и карточки категории. */
export function AcceptMeasuredButton({
  sessionId,
  categoryLabel,
  size = 'md',
  className,
}: {
  sessionId: number
  categoryLabel: string
  size?: 'sm' | 'md' | 'lg'
  className?: string
}) {
  const { toast } = useToast()
  const accept = useAcceptMeasured()
  return (
    <Button
      size={size}
      className={cn('shrink-0', className)}
      loading={accept.isPending}
      onClick={() =>
        accept.mutate(sessionId, {
          onSuccess: () => toast({ tone: 'success', title: `Категория «${categoryLabel}» присвоена` }),
          onError: (err) => toast({ tone: 'error', title: 'Не удалось получить категорию', description: getErrorMessage(err) }),
        })
      }
    >
      Получить категорию {categoryLabel}
    </Button>
  )
}

export function MeasuredOffer({
  sessionId,
  targetGrade,
  grade,
  categoryLabel,
  variant = 'card',
  className,
}: {
  sessionId: number
  targetGrade: GradeCode
  grade: GradeCode
  categoryLabel: string
  variant?: 'card' | 'banner'
  className?: string
}) {
  const banner = variant === 'banner'
  const button = <AcceptMeasuredButton sessionId={sessionId} categoryLabel={categoryLabel} size={banner ? 'lg' : 'md'} />
  return (
    <Card
      className={cn(banner ? 'border-0 bg-fsp-night text-white' : 'border-primary/40 bg-violet-soft/40', className)}
      padding="lg"
      data-testid="measured-offer"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex gap-4">
          <span
            className={cn(
              'flex size-12 shrink-0 items-center justify-center rounded-lg',
              banner ? 'bg-white/10 text-fsp-blush' : 'bg-surface text-fsp-plum',
            )}
          >
            <Gauge className="size-6" aria-hidden />
          </span>
          <div>
            {banner ? (
              <>
                <h2 className="text-xl font-bold text-white">
                  Тест на {GRADE_LABELS[targetGrade]} не подтвердил грейд. По результату теста — {GRADE_LABELS[grade]}
                </h2>
                <p className="mt-1 text-on-nav-muted">
                  Получите категорию {categoryLabel} — и профиль попадёт в выдачу работодателям.
                </p>
              </>
            ) : (
              <>
                <p className="text-lg font-bold text-ink">
                  Грейд {GRADE_LABELS[targetGrade]} не подтверждён. Тест показал уровень «{GRADE_LABELS[grade]}» — получить категорию{' '}
                  {categoryLabel}?
                </p>
                <p className="mt-1 text-[15px] text-muted">
                  С категорией профиль попадёт в выдачу работодателям. Тест на {GRADE_LABELS[targetGrade]} можно будет пройти снова
                  позже.
                </p>
              </>
            )}
          </div>
        </div>
        {button}
      </div>
    </Card>
  )
}
