import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Award, ExternalLink, Info, Medal, RefreshCw, ShieldCheck, Trophy, Users } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate, formatDateTime } from '@/shared/lib/format'
import { cn } from '@/shared/lib/cn'
import { Badge, Button, Card, EmptyState, FspVerifiedBadge, PageHeader, Tooltip, useToast } from '@/shared/ui'
import { qk, useFspAchievements, useFspStatus, type FspAchievement, type FspStatus } from './api'
import { FspLinkButton } from './components/FspLinkButton'
import { QueryView } from './components/QueryView'
import { FSP_DISCIPLINE_LABELS, FSP_LEVEL_LABELS } from './labels'

export default function FspPage() {
  const status = useFspStatus()
  return (
    <>
      <PageHeader
        title="Достижения ФСП"
        description="Соревнования из реестра Федерации спортивного программирования. Подтверждены ФСП — подделать нельзя."
      />
      <QueryView query={status}>{(s) => (s.linked ? <Linked status={s} /> : <NotLinked message={s.message} />)}</QueryView>
    </>
  )
}

function NotLinked({ message }: { message?: string | null }) {
  return (
    <Card padding="none">
      <EmptyState
        icon={<ShieldCheck aria-hidden />}
        title="ФСП ID не привязан"
        description={
          <>
            {message ?? 'Привяжите ФСП ID — достижения подтянутся из реестра с отметкой «подтверждено ФСП».'}
            <br />
            Не участвовали в соревнованиях — ничего страшного: это не снижает позицию в выдаче.
          </>
        }
        action={<FspLinkButton />}
      />
    </Card>
  )
}

function Linked({ status }: { status: FspStatus }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const achievements = useFspAchievements()
  const sync = useMutation({
    mutationFn: () => api.post<FspStatus>('/fsp/sync'),
    onSuccess: (s) => {
      client.setQueryData(qk.fspStatus, s)
      void client.invalidateQueries({ queryKey: qk.fspAchievements })
      toast({ tone: 'success', title: 'Данные ФСП обновлены' })
    },
    onError: (err) => toast({ tone: 'error', title: 'Реестр ФСП недоступен', description: getErrorMessage(err) }),
  })

  return (
    <div className="grid gap-5">
      <Card>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-x-8 gap-y-3">
            <Stat label="ФСП ID" value={status.fsp_id ?? '—'} mono />
            <Stat label="Соревнований" value={String(status.achievements_count ?? 0)} />
            {status.has_history && typeof status.fsp_score === 'number' && (
              <div>
                <p className="flex items-center gap-1 text-xs font-semibold tracking-wide text-muted uppercase">
                  ФСП-скор
                  <Tooltip content="Уровень соревнования × место × свежесть результата. Входит в ранжирование выдачи.">
                    <button type="button" className="rounded-full text-subtle hover:text-ink" aria-label="Как считается ФСП-скор">
                      <Info className="size-3.5" aria-hidden />
                    </button>
                  </Tooltip>
                </p>
                <p className="text-2xl font-bold text-fsp-night tabular-nums">
                  {String(status.fsp_score).replace('.', ',')}
                  <span className="text-base font-medium text-muted"> / 100</span>
                </p>
              </div>
            )}
          </div>
          <div className="flex flex-col items-start gap-1 sm:items-end">
            <Button variant="secondary" size="sm" leftIcon={<RefreshCw className="size-4" aria-hidden />} loading={sync.isPending} onClick={() => sync.mutate()}>
              Обновить из реестра
            </Button>
            {status.last_sync_at && <p className="text-[13px] text-muted">Обновлено {formatDateTime(status.last_sync_at)}</p>}
          </div>
        </div>
        {status.badges && status.badges.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-2 border-t border-line pt-4">
            {status.badges.map((b) => (
              <FspVerifiedBadge key={b.id} label={b.title} />
            ))}
          </div>
        )}
      </Card>

      {!status.has_history ? (
        <Card padding="none">
          <EmptyState
            icon={<Award aria-hidden />}
            title="Нет данных ФСП"
            description={
              status.message ?? 'В реестре ФСП пока нет ваших соревнований. Это не снижает позицию в выдаче — просто нет бонуса за достижения.'
            }
          />
        </Card>
      ) : (
        <QueryView query={achievements} isEmpty={(l) => l.length === 0} empty={<Card padding="none"><EmptyState title="Нет данных ФСП" /></Card>}>
          {(list) => (
            <ul className="grid gap-3">
              {list.map((a) => (
                <li key={a.id}>
                  <AchievementCard a={a} />
                </li>
              ))}
            </ul>
          )}
        </QueryView>
      )}

      <p className="text-sm text-muted">
        Работодатели видят достижения до принятия приглашения, если это разрешено в{' '}
        <Link to="/candidate/settings" className="font-semibold text-fsp-plum hover:underline">
          настройках приватности
        </Link>
        .
      </p>
    </div>
  )
}

function Stat({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs font-semibold tracking-wide text-muted uppercase">{label}</p>
      <p className={cn('text-2xl font-bold text-fsp-night', mono && 'font-mono text-xl')}>{value}</p>
    </div>
  )
}

function placeView(place: number | null | undefined) {
  if (place == null) return { text: 'Участник', cls: 'bg-neutral-soft text-neutral', icon: Users }
  if (place <= 3) {
    const cls = place === 1 ? 'bg-[#fff1c2] text-[#7a5300]' : place === 2 ? 'bg-[#eceef2] text-[#454a57]' : 'bg-[#f8e1cf] text-[#7a3f12]'
    return { text: `${place} место`, cls, icon: Trophy }
  }
  return { text: `${place} место`, cls: 'bg-violet-soft text-fsp-plum', icon: Medal }
}

function AchievementCard({ a }: { a: FspAchievement }) {
  const place = placeView(a.place)
  const PlaceIcon = place.icon
  return (
    <Card>
      <div className="flex gap-4">
        <span className={cn('flex size-12 shrink-0 flex-col items-center justify-center rounded-lg text-xs font-bold', place.cls)}>
          <PlaceIcon className="size-5" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
            <p className="font-semibold text-ink">{a.competition}</p>
            {a.verified !== false && <FspVerifiedBadge className="self-start" />}
          </div>
          <p className="text-sm text-muted">
            {FSP_DISCIPLINE_LABELS[a.discipline]} · {FSP_LEVEL_LABELS[a.level]} · {formatDate(a.date)}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
            <Badge className={place.cls}>{place.text}</Badge>
            {a.diploma && <Badge tone="accent">{a.diploma}</Badge>}
            {a.team && <span className="text-ink">Команда «{a.team}»</span>}
            {a.role && <span className="text-muted">· {a.role}</span>}
            {typeof a.rating === 'number' && <span className="text-muted">· рейтинг {a.rating}</span>}
          </div>
          {a.protocol_url && (
            <a href={a.protocol_url} target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-fsp-plum hover:underline">
              Протокол соревнования <ExternalLink className="size-3.5" aria-hidden />
            </a>
          )}
        </div>
      </div>
    </Card>
  )
}
