import { useEffect, useState, type ReactNode } from 'react'
import { useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AtSign, Building2, Check, Clock, Flag, Lock, Mail, MessageCircle, MessagesSquare, Phone, Send, X } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import { INVITATION_STATUS_LABELS } from '@/shared/config/dictionaries'
import { formatDate, formatDateTime, formatSalaryRange } from '@/shared/lib/format'
import { Button, Card, CardHeader, EmptyState, Modal, PageHeader, RadioGroup, Select, Skeleton, StatusPill, Tag, Textarea, useToast } from '@/shared/ui'
import { qk, useDeclineReasons, type DeclineReason, type Invitation, type InvitationDetail, type S } from './api'
import { QueryView } from './components/QueryView'
import { CONTACT_TYPE_LABELS, DECLINE_REASON_FALLBACK, REPORT_REASON_LABELS } from './labels'

const EVENT_LABELS: Record<S['InvitationEventType'], string> = {
  created: 'Приглашение отправлено',
  viewed: 'Вы открыли приглашение',
  accepted: 'Вы приняли приглашение',
  declined: 'Вы отклонили приглашение',
  expired: 'Срок ответа истёк',
  withdrawn: 'Работодатель отозвал приглашение',
  contacts_revealed: 'Контакты открыты обеим сторонам',
}

const CONTACT_ICON: Record<S['ContactMethodType'], typeof Mail> = { email: Mail, phone: Phone, telegram: Send, other: MessageCircle }

export default function InvitationPage() {
  const { id } = useParams()
  const invitationId = Number(id)
  const client = useQueryClient()
  const q = useQuery({
    queryKey: qk.invitation(invitationId),
    queryFn: () => api.get<InvitationDetail>(`/invitations/${invitationId}`),
    enabled: Number.isInteger(invitationId),
  })
  const notFound = isApiError(q.error) && q.error.status === 404

  // Открытие переводит «Отправлено» → «Просмотрено»: обновить список и главную.
  const loaded = q.isSuccess
  useEffect(() => {
    if (loaded) {
      void client.invalidateQueries({ queryKey: qk.invitations })
      void client.invalidateQueries({ queryKey: qk.dashboard })
    }
  }, [loaded, client])

  return (
    <>
      <PageHeader
        title={q.data ? q.data.company_name : 'Приглашение'}
        back={{ to: '/candidate/invitations', label: 'Все приглашения' }}
        meta={q.data && <StatusPill status={q.data.status} />}
      />
      {notFound ? (
        <Card padding="none">
          <EmptyState title="Приглашение не найдено" description="Возможно, ссылка устарела." />
        </Card>
      ) : (
        <QueryView
          query={q}
          loading={
            <Card padding="lg">
              <Skeleton className="h-9 w-1/2" />
              <Skeleton className="mt-4 h-4 w-full" />
              <Skeleton className="mt-2 h-4 w-2/3" />
            </Card>
          }
        >
          {(inv) => <InvitationView inv={inv} />}
        </QueryView>
      )}
    </>
  )
}

function InvitationView({ inv }: { inv: InvitationDetail }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const [acceptOpen, setAcceptOpen] = useState(false)
  const [declineOpen, setDeclineOpen] = useState(false)
  const [reportOpen, setReportOpen] = useState(false)
  const waiting = inv.status === 'sent' || inv.status === 'viewed'
  const ContactIcon = CONTACT_ICON[inv.contact_method.type]

  function applyUpdate(updated: Invitation) {
    client.setQueryData<InvitationDetail>(qk.invitation(inv.id), (old) => ({
      ...updated,
      events: old?.events ?? [],
    }))
    void client.invalidateQueries({ queryKey: qk.invitation(inv.id) })
    void client.invalidateQueries({ queryKey: qk.invitations })
    void client.invalidateQueries({ queryKey: qk.dashboard })
  }

  const accept = useMutation({
    mutationFn: () => api.post<Invitation>(`/invitations/${inv.id}/accept`),
    onSuccess: (updated) => {
      setAcceptOpen(false)
      applyUpdate(updated)
      toast({ tone: 'success', title: 'Приглашение принято', description: 'Контакты рекрутера открыты. Он тоже видит ваши.' })
    },
    onError: (err) => toast({ tone: 'error', title: 'Не получилось принять', description: getErrorMessage(err) }),
  })

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <div className="grid gap-5">
        <Card padding="lg">
          <p className="text-sm font-semibold text-muted">Зарплата в месяц</p>
          <p className="mt-1 text-3xl font-bold text-fsp-night tabular-nums sm:text-4xl">{formatSalaryRange(inv.salary_from, inv.salary_to)}</p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Tag>{inv.category_label}</Tag>
            <span className="inline-flex items-center gap-1.5 text-sm text-muted">
              <Building2 className="size-4" aria-hidden /> {inv.company_name} · {inv.recruiter_name}
            </span>
          </div>
          <p className="mt-5 text-[15px] leading-relaxed whitespace-pre-line text-ink">{inv.description}</p>
        </Card>

        <Card>
          <CardHeader title="Способ связи" />
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-md bg-violet-soft text-fsp-plum">
              <ContactIcon className="size-5" aria-hidden />
            </span>
            <div>
              <p className="font-semibold text-ink">{CONTACT_TYPE_LABELS[inv.contact_method.type]}</p>
              {inv.status === 'accepted' ? (
                <p className="text-[15px] text-ink">{inv.contact_method.value}</p>
              ) : (
                <p className="inline-flex items-center gap-1 text-sm text-muted">
                  <Lock className="size-3.5" aria-hidden /> Откроется после принятия
                </p>
              )}
            </div>
          </div>
        </Card>

        {inv.has_task_text && (
          <Card>
            <CardHeader
              title={
                <span className="inline-flex items-center gap-2">
                  <MessagesSquare className="size-5 text-fsp-plum" aria-hidden /> Вопрос к созвону
                </span>
              }
              description={
                inv.task_text
                  ? 'Подумайте заранее — рекрутер обсудит это с вами на созвоне.'
                  : 'Рекрутер подготовил вопрос, который обсудит с вами на созвоне.'
              }
            />
            {inv.task_text ? (
              <p className="rounded-md bg-surface-muted p-3 text-[15px] text-ink">{inv.task_text}</p>
            ) : (
              <p className="inline-flex items-center gap-1 text-sm text-muted">
                <Lock className="size-3.5" aria-hidden /> Откроется после принятия
              </p>
            )}
          </Card>
        )}

        {inv.events && inv.events.length > 0 && (
          <Card>
            <CardHeader title="История" />
            <ol className="grid gap-3">
              {inv.events.map((e) => (
                <li key={e.id} className="flex items-start gap-3">
                  <span className="mt-1.5 size-2 shrink-0 rounded-full bg-fsp-lavender" aria-hidden />
                  <span>
                    <span className="block text-sm font-medium text-ink">{EVENT_LABELS[e.type]}</span>
                    <span className="block text-[13px] text-muted">{formatDateTime(e.at)}</span>
                  </span>
                </li>
              ))}
            </ol>
          </Card>
        )}
      </div>

      <aside className="grid gap-4 lg:sticky lg:top-20">
        {waiting && (
          <Card>
            <p className="font-semibold text-ink">Ваш ответ</p>
            <p className="mt-1 inline-flex items-center gap-1.5 text-sm text-warning">
              <Clock className="size-4" aria-hidden /> До {formatDate(inv.expires_at)}, потом приглашение истечёт
            </p>
            <div className="mt-4 grid gap-2">
              <Button size="lg" leftIcon={<Check className="size-4" aria-hidden />} onClick={() => setAcceptOpen(true)}>
                Принять
              </Button>
              <Button variant="secondary" size="lg" leftIcon={<X className="size-4" aria-hidden />} onClick={() => setDeclineOpen(true)}>
                Отклонить
              </Button>
            </div>
            <p className="mt-3 text-[13px] text-muted">
              Примете — работодатель увидит ваши ФИО и контакты, а вы — контакты рекрутера. Отклоните — он узнает только причину.
            </p>
          </Card>
        )}

        {inv.status === 'accepted' && inv.recruiter_contacts && (
          <Card className="border-success/40">
            <p className="inline-flex items-center gap-2 font-semibold text-success">
              <Check className="size-5" aria-hidden /> Контакты открыты
            </p>
            <p className="mt-3 text-lg font-semibold text-ink">{inv.recruiter_contacts.full_name}</p>
            <p className="text-sm text-muted">
              {inv.recruiter_contacts.position}, {inv.company_name}
            </p>
            <ul className="mt-3 grid gap-2 text-[15px]">
              <ContactLine icon={<Mail className="size-4" aria-hidden />}>
                <a href={`mailto:${inv.recruiter_contacts.email}`} className="text-fsp-plum hover:underline">
                  {inv.recruiter_contacts.email}
                </a>
              </ContactLine>
              {inv.recruiter_contacts.phone && (
                <ContactLine icon={<Phone className="size-4" aria-hidden />}>
                  <a href={`tel:${inv.recruiter_contacts.phone.replace(/[^\d+]/g, '')}`} className="text-fsp-plum hover:underline">
                    {inv.recruiter_contacts.phone}
                  </a>
                </ContactLine>
              )}
              {inv.recruiter_contacts.telegram && (
                <ContactLine icon={<AtSign className="size-4" aria-hidden />}>{inv.recruiter_contacts.telegram}</ContactLine>
              )}
            </ul>
            <p className="mt-3 text-[13px] text-muted">Рекрутер свяжется с вами: {CONTACT_TYPE_LABELS[inv.contact_method.type].toLowerCase()}.</p>
          </Card>
        )}

        {inv.status === 'declined' && (
          <Card>
            <p className="font-semibold text-ink">Вы отклонили приглашение</p>
            <p className="mt-2 text-sm text-muted">Причина</p>
            <p className="text-[15px] text-ink">{inv.decline_reason_label ?? (inv.decline_reason ? DECLINE_REASON_FALLBACK[inv.decline_reason] : '—')}</p>
            {inv.decline_comment && <p className="mt-2 rounded-md bg-surface-muted p-2 text-sm text-ink">«{inv.decline_comment}»</p>}
            <p className="mt-3 text-[13px] text-muted">Работодатель видит причину — это помогает ему делать точнее следующие предложения.</p>
          </Card>
        )}

        {(inv.status === 'expired' || inv.status === 'withdrawn') && (
          <Card>
            <p className="font-semibold text-ink">{INVITATION_STATUS_LABELS[inv.status]}</p>
            <p className="mt-1 text-sm text-muted">
              {inv.status === 'expired' ? 'Срок ответа — 7 дней. Приглашение больше не активно.' : 'Работодатель отозвал приглашение.'}
            </p>
          </Card>
        )}

        <button type="button" onClick={() => setReportOpen(true)} className="inline-flex items-center gap-1.5 justify-self-start text-sm font-medium text-muted hover:text-danger">
          <Flag className="size-4" aria-hidden /> Пожаловаться на работодателя
        </button>
      </aside>

      <Modal
        open={acceptOpen}
        onClose={() => setAcceptOpen(false)}
        size="sm"
        title="Принять приглашение?"
        description={`${inv.company_name} · ${formatSalaryRange(inv.salary_from, inv.salary_to)}`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAcceptOpen(false)}>
              Отмена
            </Button>
            <Button onClick={() => accept.mutate()} loading={accept.isPending}>
              Принять и открыть контакты
            </Button>
          </>
        }
      >
        <p className="text-[15px] text-ink">
          Работодатель увидит ваши ФИО, почту и телефон. Вы увидите контакты рекрутера. Отменить раскрытие нельзя.
        </p>
      </Modal>

      <DeclineModal open={declineOpen} onClose={() => setDeclineOpen(false)} inv={inv} onDeclined={applyUpdate} />
      <ReportModal open={reportOpen} onClose={() => setReportOpen(false)} inv={inv} />
    </div>
  )
}

function ContactLine({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="flex items-center gap-2">
      <span className="text-subtle">{icon}</span>
      {children}
    </li>
  )
}

function DeclineModal({
  open,
  onClose,
  inv,
  onDeclined,
}: {
  open: boolean
  onClose: () => void
  inv: InvitationDetail
  onDeclined: (updated: Invitation) => void
}) {
  const { toast } = useToast()
  const reasons = useDeclineReasons()
  const [reason, setReason] = useState<DeclineReason | null>(null)
  const [comment, setComment] = useState('')
  const [error, setError] = useState<string | null>(null)
  const decline = useMutation({
    mutationFn: () => api.post<Invitation>(`/invitations/${inv.id}/decline`, { reason, comment: comment.trim() || null }),
    onSuccess: (updated) => {
      onClose()
      onDeclined(updated)
      toast({ tone: 'info', title: 'Приглашение отклонено', description: 'Работодатель увидит причину.' })
    },
    onError: (err) => setError(getErrorMessage(err)),
  })
  const options = (reasons.data ?? (Object.keys(DECLINE_REASON_FALLBACK) as DeclineReason[]).map((id) => ({ id, label: DECLINE_REASON_FALLBACK[id] }))).map(
    (r) => ({ value: r.id, label: r.label }),
  )

  function submit() {
    if (!reason) return setError('Выберите причину')
    if (reason === 'other' && !comment.trim()) return setError('Напишите пару слов о причине')
    setError(null)
    decline.mutate()
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Отклонить приглашение"
      description="Работодатель увидит причину — без вашего имени и контактов."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="danger" onClick={submit} loading={decline.isPending}>
            Отклонить
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <RadioGroup label="Причина" value={reason} onChange={(v) => setReason(v as DeclineReason)} options={options} />
        <Textarea
          label={reason === 'other' ? 'Комментарий' : 'Комментарий (необязательно)'}
          rows={3}
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Например: рассматриваю предложения от 250 000 ₽"
          maxLength={500}
        />
        {error && (
          <p className="text-sm text-danger" role="alert">
            {error}
          </p>
        )}
      </div>
    </Modal>
  )
}

// как на бэкенде: ReportCreate.text — от 5 до 3000 символов
const REPORT_TEXT_MIN = 5
const REPORT_TEXT_MAX = 3000

function ReportModal({ open, onClose, inv }: { open: boolean; onClose: () => void; inv: InvitationDetail }) {
  const { toast } = useToast()
  const [reason, setReason] = useState<S['ReportReason']>('fake_vacancy')
  const [text, setText] = useState('')
  const tooShort = text.trim().length < REPORT_TEXT_MIN
  const report = useMutation({
    mutationFn: () => api.post<S['Report']>('/reports', { company_id: inv.company_id, invitation_id: inv.id, reason, text: text.trim() }),
    onSuccess: () => {
      onClose()
      setText('')
      toast({ tone: 'success', title: 'Жалоба отправлена', description: 'Модератор проверит работодателя.' })
    },
  })
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Пожаловаться на работодателя"
      description={inv.company_name}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="danger" onClick={() => report.mutate()} loading={report.isPending} disabled={tooShort}>
            Отправить
          </Button>
        </>
      }
    >
      <div className="grid gap-4">
        <Select
          label="Что случилось"
          value={reason}
          onChange={(e) => setReason(e.target.value as S['ReportReason'])}
          options={(Object.keys(REPORT_REASON_LABELS) as S['ReportReason'][]).map((r) => ({ value: r, label: REPORT_REASON_LABELS[r] }))}
        />
        <Textarea
          label="Подробности"
          rows={3}
          maxLength={REPORT_TEXT_MAX}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            if (report.isError) report.reset()
          }}
          hint={tooShort ? `Опишите, что произошло, — минимум ${REPORT_TEXT_MIN} символов` : undefined}
          error={report.isError ? getErrorMessage(report.error) : undefined}
        />
      </div>
    </Modal>
  )
}
