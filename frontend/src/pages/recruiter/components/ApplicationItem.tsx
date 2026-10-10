import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, MessageCircle, Phone } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate } from '@/shared/lib/format'
import { Badge, Card, Select, useToast } from '@/shared/ui'
import { apiFieldErrors, refreshRecruiter, rk, upsertInList, type Application, type ApplicationStatus } from '../api'
import { APPLICATION_STATUS_LABELS, APPLICATION_STATUS_TONE, APPLICATION_TRANSITIONS, CONTACT_TYPE_LABELS } from '../labels'
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
  const c = app.candidate
  const contacts = app.candidate_contacts
  return (
    <Card padding="sm" className="flex flex-col gap-3" data-testid="application-item">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-semibold">{contacts?.full_name ?? c?.pseudonym ?? 'Кандидат'}</p>
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
        <div className="flex items-center gap-2">
          <Badge tone={APPLICATION_STATUS_TONE[app.status]}>{APPLICATION_STATUS_LABELS[app.status]}</Badge>
          <Select
            aria-label="Статус отклика"
            containerClassName="w-40"
            value={app.status}
            disabled={setStatus.isPending}
            // только текущий статус и разрешённые переходы
            options={[app.status, ...APPLICATION_TRANSITIONS[app.status]].map((s) => ({ value: s, label: APPLICATION_STATUS_LABELS[s] }))}
            onChange={(e) => {
              const status = e.target.value as ApplicationStatus
              if (status === 'invited') {
                setInviteError(undefined)
                setInviting(true)
              } else setStatus.mutate({ status })
            }}
          />
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
              {contacts.phone}
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
          <Link to={`/recruiter/candidates/${c.id}`} className="text-[13px] font-semibold text-fsp-plum hover:underline">
            Профиль и результаты теста
          </Link>
        </div>
      )}
    </Card>
  )
}
