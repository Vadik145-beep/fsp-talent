import { Link } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDateTime } from '@/shared/lib/format'
import { Button, Drawer, Pseudonym, SalaryRange, SkeletonText, StatusPill, ErrorState } from '@/shared/ui'
import { pseudonymCodeOf, rk, type Invitation, type InvitationDetail } from '../api'
import { CONTACT_TYPE_LABELS, EVENT_LABELS } from '../labels'

const CAN_WITHDRAW = ['sent', 'viewed']

/** Карточка приглашения: условия, журнал событий, причина отказа, контакты после принятия. */
export function InvitationDrawer({
  id,
  onClose,
  onWithdraw,
}: {
  id: number | null
  onClose: () => void
  onWithdraw: (id: number) => void
}) {
  const q = useQuery({
    queryKey: rk.invitation(id ?? 0),
    queryFn: () => api.get<InvitationDetail>(`/invitations/${id}`),
    enabled: id !== null,
  })
  const qc = useQueryClient()
  // Строка из списка — пока карточка грузится и если карточки на сервере нет (без журнала).
  const fromList = qc.getQueryData<Invitation[]>(rk.invitations)?.find((i) => i.id === id)
  const inv: InvitationDetail | undefined = q.data ?? (fromList && (q.isPending || q.isError) ? { ...fromList, events: [] } : undefined)
  const noEvents = !q.data && Boolean(inv)
  return (
    <Drawer
      open={id !== null}
      onClose={onClose}
      title="Приглашение"
      footer={
        inv && CAN_WITHDRAW.includes(inv.status) ? (
          <Button variant="danger" onClick={() => onWithdraw(inv.id)}>
            Отозвать приглашение
          </Button>
        ) : undefined
      }
    >
      <div className="flex flex-col gap-5 p-5">
        {q.isPending && !inv && <SkeletonText lines={6} />}
        {q.isError && !inv && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
        {inv && (
          <>
            <div className="flex items-start justify-between gap-3">
              {inv.candidate ? (
                <Link to={`/recruiter/candidates/${inv.candidate_id}`} className="min-w-0 hover:opacity-80">
                  <Pseudonym code={pseudonymCodeOf(inv.candidate.pseudonym)} subtitle={inv.category_label} />
                </Link>
              ) : (
                <span>{inv.category_label}</span>
              )}
              <StatusPill status={inv.status} />
            </div>

            {inv.status === 'accepted' && inv.candidate_contacts ? (
              <section className="rounded-md bg-success-soft p-3 text-sm" data-testid="invitation-contacts">
                <h3 className="mb-1 font-semibold text-success">Контакты кандидата</h3>
                <p className="font-semibold">{inv.candidate_contacts.full_name}</p>
                <p>{inv.candidate_contacts.email}</p>
                {inv.candidate_contacts.phone && <p>{inv.candidate_contacts.phone}</p>}
                {inv.candidate_contacts.telegram && <p>{inv.candidate_contacts.telegram}</p>}
              </section>
            ) : (
              <p className="flex items-center gap-1.5 text-[13px] text-muted">
                <Lock className="size-3.5" aria-hidden />
                Контакты откроются после принятия.
              </p>
            )}

            {inv.status === 'declined' && (
              <section className="rounded-md bg-danger-soft p-3 text-sm">
                <h3 className="font-semibold text-danger">Отказ: {inv.decline_reason_label ?? 'причина не указана'}</h3>
                {inv.decline_comment && <p className="mt-1 text-ink">«{inv.decline_comment}»</p>}
              </section>
            )}

            <SalaryRange from={inv.salary_from} to={inv.salary_to} label="Вилка" size="lg" />
            <section>
              <h3 className="mb-1 text-xs font-medium text-muted">Описание</h3>
              <p className="text-sm whitespace-pre-line">{inv.description}</p>
            </section>
            <section>
              <h3 className="mb-1 text-xs font-medium text-muted">Способ связи</h3>
              <p className="text-sm">
                {CONTACT_TYPE_LABELS[inv.contact_method.type]}: {inv.contact_method.value}
              </p>
            </section>
            {inv.task_text && (
              <section>
                <h3 className="mb-1 text-xs font-medium text-muted">Короткое задание</h3>
                <p className="text-sm">{inv.task_text}</p>
              </section>
            )}
            <p className="text-[13px] text-muted">
              Отправил {inv.recruiter_name} · действует до {formatDateTime(inv.expires_at)}
            </p>

            <section>
              <h3 className="mb-2 text-sm font-semibold">Журнал</h3>
              {noEvents && (
                <p className="text-[13px] text-muted">{q.isPending ? 'Загружаем журнал…' : 'Журнал событий пока недоступен.'}</p>
              )}
              <ol className="relative flex flex-col gap-3 border-l-2 border-line pl-4">
                {(inv.events ?? []).map((e) => (
                  <li key={e.id} className="text-sm">
                    <span className="absolute -left-[5px] mt-1.5 size-2 rounded-full bg-fsp-lavender" aria-hidden />
                    <p className="font-medium">{EVENT_LABELS[e.type]}</p>
                    <p className="text-[13px] text-muted">{formatDateTime(e.at)}</p>
                  </li>
                ))}
              </ol>
            </section>
          </>
        )}
      </div>
    </Drawer>
  )
}
