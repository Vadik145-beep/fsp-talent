import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Mail, MessageCircle, Phone } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate } from '@/shared/lib/format'
import { Badge, Card, Select, useToast } from '@/shared/ui'
import { rk, type Application, type ApplicationStatus } from '../api'
import { APPLICATION_STATUS_LABELS, APPLICATION_STATUS_TONE } from '../labels'
import { StackTags, ThetaInfo } from './CandidateBits'

/** Отклик: кандидат откликнулся сам, поэтому контакты открыты сразу. */
export function ApplicationItem({ app, showVacancy }: { app: Application; showVacancy?: boolean }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const setStatus = useMutation({
    mutationFn: (status: ApplicationStatus) => api.patch<Application>(`/applications/${app.id}`, { status }),
    onSuccess: (a) => {
      toast({ tone: 'success', title: `Статус: ${APPLICATION_STATUS_LABELS[a.status]}` })
      void qc.invalidateQueries({ queryKey: rk.all })
    },
    onError: (e) => toast({ tone: 'error', title: 'Не удалось сменить статус', description: getErrorMessage(e) }),
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
            options={(Object.keys(APPLICATION_STATUS_LABELS) as ApplicationStatus[]).map((s) => ({ value: s, label: APPLICATION_STATUS_LABELS[s] }))}
            onChange={(e) => setStatus.mutate(e.target.value as ApplicationStatus)}
          />
        </div>
      </div>
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
