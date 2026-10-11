import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, MessageCircle, Phone } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate, formatPhone } from '@/shared/lib/format'
import { Badge, Button, Card, useToast } from '@/shared/ui'
import { apiFieldErrors, refreshRecruiter, rk, upsertInList, type Application, type ApplicationStatus } from '../api'
import { APPLICATION_STATUS_LABELS, APPLICATION_STATUS_TONE, CONTACT_TYPE_LABELS } from '../labels'
import { ApplicationInviteModal, type ApplicationInviteBody } from './ApplicationInviteModal'
import { StackTags, ThetaInfo } from './CandidateBits'

type StatusBody = { status: ApplicationStatus } & Partial<ApplicationInviteBody>

/** Отклик: кандидат откликнулся сам, поэтому контакты открыты сразу. */
export function ApplicationItem({ app, showVacancy }: { app: Application; showVacancy?: boolean }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [inviting, setInviting] = useState(false)
  const [inviteError, setInviteError] = useState<string>()
  const setStatus = useMutation({
    mutationFn: (body: StatusBody) => api.patch<Application>(`/applications/${app.id}`, body),
    onSuccess: (a) => {
      setInviting(false)
      toast({
        tone: 'success',
        title: `Статус: ${APPLICATION_STATUS_LABELS[a.status]}`,
        description: a.status === 'invited' ? 'Кандидат увидит ваш контакт в откликах и получит письмо.' : undefined,
      })
      upsertInList(qc, rk.applications, a)
      upsertInList(qc, rk.vacancyApplications(a.vacancy_id), a)
      void refreshRecruiter(qc, rk.applications, rk.vacancyApplications(a.vacancy_id))
    },
    onError: (e) => {
      const field = apiFieldErrors(e).contact_method
      if (inviting && field) setInviteError(field)
      else toast({ tone: 'error', title: 'Не удалось сменить статус', description: getErrorMessage(e) })
    },
  })
  // «Просмотрен» ставится сам, когда новый отклик попал на экран рекрутера; бейдж «Новый» держим до перезагрузки
  const [wasNew] = useState(app.status === 'new')
  const cardRef = useRef<HTMLDivElement>(null)
  const markViewed = useMutation({
    mutationFn: () => api.patch<Application>(`/applications/${app.id}`, { status: 'viewed' }),
    onSuccess: (a) => {
      upsertInList(qc, rk.applications, a)
      upsertInList(qc, rk.vacancyApplications(a.vacancy_id), a)
      void refreshRecruiter(qc, rk.applications, rk.vacancyApplications(a.vacancy_id))
    },
  })
  const { mutate: viewNow } = markViewed
  const isNew = app.status === 'new'
  useEffect(() => {
    const el = cardRef.current
    if (!isNew || !el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect()
          viewNow()
        }
      },
      { threshold: 0.5 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [isNew, viewNow])
  const c = app.candidate
  const contacts = app.candidate_contacts
  const canInvite = app.status !== 'invited'
  const canReject = app.status === 'new' || app.status === 'viewed'
  return (
    <div ref={cardRef}>
    <Card padding="sm" className="flex flex-col gap-3" data-testid="application-item">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 font-semibold">
            {contacts?.full_name ?? c?.pseudonym ?? 'Кандидат'}
            {wasNew && canReject && <Badge tone={APPLICATION_STATUS_TONE.new}>{APPLICATION_STATUS_LABELS.new}</Badge>}
          </p>
          <p className="text-[13px] text-muted">
            {c?.category_label ?? 'Категория не определена'}
            {showVacancy && (
              <>
                {' · '}
                <Link to={`/recruiter/vacancies/${app.vacancy_id}`} className="font-medium text-fsp-plum hover:underline">
                  {app.vacancy_title}
                </Link>
              </>
            )}
            {' · '}
            {formatDate(app.created_at)}
          </p>
        </div>
        {/* действия кнопками; итог (приглашён / отказ) — бейджем */}
        <div className="flex flex-wrap items-center gap-2">
          {(app.status === 'invited' || app.status === 'rejected') && (
            <Badge tone={APPLICATION_STATUS_TONE[app.status]}>{APPLICATION_STATUS_LABELS[app.status]}</Badge>
          )}
          {canReject && (
            <Button size="sm" variant="ghost" disabled={setStatus.isPending} onClick={() => setStatus.mutate({ status: 'rejected' })}>
              Отклонить
            </Button>
          )}
          {canInvite && (
            <Button
              size="sm"
              variant={app.status === 'rejected' ? 'secondary' : 'primary'}
              disabled={setStatus.isPending}
              onClick={() => {
                setInviteError(undefined)
                setInviting(true)
              }}
            >
              Пригласить
            </Button>
          )}
        </div>
      </div>
      {inviting && (
        <ApplicationInviteModal
          app={app}
          error={inviteError}
          pending={setStatus.isPending}
          onClose={() => setInviting(false)}
          onSubmit={(body) => setStatus.mutate({ status: 'invited', ...body })}
        />
      )}
      {app.status === 'invited' && app.contact_method && (
        <p className="text-[13px] text-muted" data-testid="application-invite-contact">
          Кандидат видит ваш контакт: {CONTACT_TYPE_LABELS[app.contact_method.type]} · {app.contact_method.value}
          {app.invite_message && <> · «{app.invite_message}»</>}
        </p>
      )}
      {contacts && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-md bg-success-soft px-3 py-2 text-sm" data-testid="application-contacts">
          <span className="inline-flex items-center gap-1.5">
            <Mail className="size-4 text-success" aria-hidden />
            {contacts.email}
          </span>
          {contacts.phone && (
            <span className="inline-flex items-center gap-1.5">
              <Phone className="size-4 text-success" aria-hidden />
              {formatPhone(contacts.phone)}
            </span>
          )}
          {contacts.telegram && (
            <span className="inline-flex items-center gap-1.5">
              <MessageCircle className="size-4 text-success" aria-hidden />
              {contacts.telegram}
            </span>
          )}
        </div>
      )}
      {app.cover_letter && <p className="text-sm text-ink">«{app.cover_letter}»</p>}
      {c && (
        <div className="flex flex-col gap-2">
          <ThetaInfo theta={c.theta} />
          <StackTags stack={c.stack} limit={8} />
          <Link to={`/recruiter/candidates/${c.id}?vacancy=${app.vacancy_id}`} className="text-[13px] font-semibold text-fsp-plum hover:underline">
            Профиль и результаты теста
          </Link>
        </div>
      )}
    </Card>
    </div>
  )
}
