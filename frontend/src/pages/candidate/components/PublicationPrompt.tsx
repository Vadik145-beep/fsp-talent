import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CircleCheck, Eye, EyeOff } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { cn } from '@/shared/lib/cn'
import { Button, Card, useToast } from '@/shared/ui'
import { invalidateCandidate, qk, useProfile, useSettings, useSkillLabel, type CandidateSettings } from '../api'
import { EmployerPreview } from './EmployerPreview'

/**
 * «Профиль скрыт от работодателей» + кнопка «Показать профиль работодателям».
 * Согласие на публикацию — только явным действием (152-ФЗ): тот же PUT, что в настройках,
 * бэкенд пишет запись в согласия. После включения — подтверждение «Профиль в выдаче».
 */
export function PublicationPrompt({ className, preview = true }: { className?: string; preview?: boolean }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const settings = useSettings()
  const profile = useProfile()
  const skillLabel = useSkillLabel()
  const [justEnabled, setJustEnabled] = useState(false)

  const publish = useMutation({
    mutationFn: () => api.put<CandidateSettings>('/candidates/me/settings/publication', { granted: true }),
    onSuccess: (next) => {
      client.setQueryData(qk.settings, next)
      setJustEnabled(true)
      void invalidateCandidate(client)
    },
    onError: (err) => toast({ tone: 'error', title: 'Не удалось изменить согласие', description: getErrorMessage(err) }),
  })

  const s = settings.data
  const p = profile.data
  if (!s || !p) return null

  if (s.publication_consent) {
    if (!justEnabled) return null
    const confirmed = p.grade_status === 'confirmed'
    const visible = confirmed && !s.job_search_paused
    return (
      <Card className={cn('border-success/30 bg-success-soft', className)} data-testid="publication-on" role="status">
        <div className="flex gap-3">
          <CircleCheck className="mt-0.5 size-5 shrink-0 text-success" aria-hidden />
          <div className="grid gap-1 text-[15px] text-ink">
            <p className="font-semibold">{visible ? 'Профиль в выдаче' : 'Согласие на публикацию дано'}</p>
            <p>
              {visible
                ? 'Работодатели видят обезличенную карточку и могут прислать приглашение. ФИО и контакты откроются, только когда вы его примете.'
                : s.job_search_paused
                  ? 'Но поиск на паузе — включите поиск в настройках, и профиль появится в выдаче.'
                  : 'Профиль появится в выдаче, как только грейд будет подтверждён тестом.'}
            </p>
            <p className="text-sm text-muted">
              Отозвать согласие можно в любой момент в{' '}
              <Link to="/candidate/settings" className="font-semibold text-fsp-plum hover:underline">
                настройках
              </Link>
              .
            </p>
          </div>
        </div>
      </Card>
    )
  }

  return (
    <Card className={cn('border-warning/40', className)} data-testid="publication-off">
      {/* Превью под текстом, а не колонкой справа: высокое превью рядом с коротким текстом оставляло слева пустоту */}
      <div className="grid grid-cols-1 items-start gap-5">
        <div className="flex gap-3">
          <span className="hidden size-10 shrink-0 items-center justify-center rounded-lg bg-warning-soft text-warning sm:flex">
            <EyeOff className="size-5" aria-hidden />
          </span>
          <div className="grid min-w-0 gap-2">
            <h2 className="text-lg font-bold text-ink">Профиль скрыт от работодателей</h2>
            <p className="text-[15px] text-ink">
              Вас нет в поиске: не дано согласие на публикацию профиля. Работодатель увидит только обезличенную карточку — без
              ФИО и контактов{preview ? ', как на превью' : ''}.
              {p.grade_status !== 'confirmed' && ' В выдачу профиль попадёт после того, как тест подтвердит грейд.'}
            </p>
            <div className="mt-1 flex flex-col gap-2 sm:flex-row sm:items-center">
              <Button leftIcon={<Eye className="size-4" aria-hidden />} loading={publish.isPending} onClick={() => publish.mutate()}>
                Показать профиль работодателям
              </Button>
              <Link to="/candidate/settings" className="text-sm font-semibold text-fsp-plum hover:underline sm:ml-2">
                Настройки видимости
              </Link>
            </div>
            <p className="text-[13px] text-muted">
              Нажимая кнопку, вы даёте согласие на публикацию обезличенного профиля в поиске работодателей. Отозвать — в любой
              момент в настройках.
            </p>
          </div>
        </div>
        {preview && (
          <div>
            <p className="mb-2 text-sm font-semibold text-ink">Что увидит работодатель</p>
            <EmployerPreview profile={p} privacy={s.privacy} skillLabel={skillLabel} />
          </div>
        )}
      </div>
    </Card>
  )
}
