import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Building, CheckCircle2, Eye, Flag, XCircle } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, Checkbox, EmptyState, ErrorState, PageHeader, SkeletonCard, Tabs } from '@/shared/ui'
import { useAdminMutation, type AdminCompany, type Report, type ReportDecision, type ReportStatus } from './api'
import { ConfirmModal } from './components/common'
import { REPORT_REASON_LABELS, REPORT_STATUS_LABELS, REPORT_STATUS_TONES } from './labels'

const TABS: Array<{ id: string; label: string; statuses: ReportStatus[] }> = [
  { id: 'open', label: 'Открытые', statuses: ['new', 'in_review'] },
  { id: 'resolved', label: 'Решённые', statuses: ['resolved'] },
  { id: 'rejected', label: 'Отклонённые', statuses: ['rejected'] },
  { id: 'all', label: 'Все', statuses: ['new', 'in_review', 'resolved', 'rejected'] },
]

export default function AdminReportsPage() {
  const [tab, setTab] = useState('open')
  const [decide, setDecide] = useState<{ report: Report; status: 'resolved' | 'rejected' } | null>(null)
  const [blockCompany, setBlockCompany] = useState(false)
  // Ответ сервера на действие показываем сразу, не дожидаясь перезапроса списка.
  const [acted, setActed] = useState<Record<number, Report>>({})
  const reports = useQuery({ queryKey: ['admin', 'reports'], queryFn: () => api.get<Report[]>('/admin/reports') })
  const companies = useQuery({ queryKey: ['admin', 'companies'], queryFn: () => api.get<AdminCompany[]>('/admin/companies') })

  const update = useAdminMutation(
    (v: { id: number; status: ReportStatus; resolution?: string; block_company?: boolean }) =>
      api.patch<Report>(`/admin/reports/${v.id}`, { status: v.status, resolution: v.resolution ?? null, block_company: Boolean(v.block_company) } satisfies ReportDecision),
    {
      success: (r, v) =>
        `Жалоба: ${REPORT_STATUS_LABELS[r.status].toLowerCase()}${v.block_company ? `, компания «${r.company_name}» заблокирована` : ''}`,
      onSuccess: (r) => setActed((m) => ({ ...m, [r.id]: r })),
    },
  )

  const list = (reports.data ?? []).map((r) => acted[r.id] ?? r)
  const current = TABS.find((t) => t.id === tab)!
  const rows = list.filter((r) => current.statuses.includes(r.status))
  const company = (id: number) => companies.data?.find((c) => c.id === id)

  async function confirmDecision(resolution: string) {
    if (!decide) return
    const block = decide.status === 'resolved' && blockCompany && !company(decide.report.company_id)?.blocked
    await update.mutateAsync({ id: decide.report.id, status: decide.status, resolution, block_company: block })
    setDecide(null)
    setBlockCompany(false)
  }

  return (
    <>
      <PageHeader title="Жалобы" description="Кандидаты жалуются на работодателей: фиктивные вакансии, спам, обман с зарплатой. Жалобы снижают скоринг компании." />
      <Tabs
        className="mb-4"
        ariaLabel="Статус жалоб"
        value={tab}
        onChange={setTab}
        items={TABS.map((t) => ({ id: t.id, label: t.label, count: reports.data ? list.filter((r) => t.statuses.includes(r.status)).length : undefined }))}
      />
      {reports.isPending ? (
        <div className="flex flex-col gap-4">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : reports.isError ? (
        <Card padding="none">
          <ErrorState error={reports.error} onRetry={() => reports.refetch()} />
        </Card>
      ) : rows.length === 0 ? (
        <Card padding="none">
          <EmptyState icon={<Flag aria-hidden />} title={tab === 'open' ? 'Открытых жалоб нет' : 'Жалоб нет'} description={tab === 'open' ? 'Очередь пуста — все жалобы разобраны.' : undefined} />
        </Card>
      ) : (
        <ul className="flex flex-col gap-4">
          {rows.map((r) => {
            const c = company(r.company_id)
            const open = r.status === 'new' || r.status === 'in_review'
            return (
              <li key={r.id}>
                <Card>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="mb-1 flex flex-wrap items-center gap-2">
                        <Badge tone={REPORT_STATUS_TONES[r.status]}>{REPORT_STATUS_LABELS[r.status]}</Badge>
                        <Badge tone="violet">{REPORT_REASON_LABELS[r.reason]}</Badge>
                        <span className="text-xs text-muted">№ {r.id} · {formatDateTime(r.created_at)}</span>
                      </div>
                      <p className="flex items-center gap-1.5 font-semibold text-ink">
                        <Building className="size-4 text-muted" aria-hidden /> {r.company_name}
                        {c && (
                          <span className={`text-[13px] font-medium ${c.trust_score < 50 ? 'text-danger' : 'text-muted'}`}>
                            · скоринг {Math.round(c.trust_score)}
                            {c.blocked ? ' · заблокирована' : ''}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <blockquote className="mt-3 rounded-md border-l-4 border-fsp-lavender bg-surface-muted px-3 py-2 text-sm text-ink">«{r.text}»</blockquote>
                  <p className="mt-2 text-[13px] text-muted">
                    Кандидат #{r.reporter_candidate_id}
                    {r.invitation_id ? ` · по приглашению №${r.invitation_id}` : ''}
                    {r.vacancy_id ? ` · по вакансии №${r.vacancy_id}` : ''}
                  </p>
                  {r.resolution && (
                    <p className="mt-2 text-sm">
                      <b>Решение:</b> {r.resolution}
                      {r.resolved_at ? <span className="text-muted"> · {formatDateTime(r.resolved_at)}</span> : null}
                    </p>
                  )}
                  {open && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {r.status === 'new' && (
                        <Button size="sm" variant="secondary" leftIcon={<Eye className="size-4" aria-hidden />}
                          loading={update.isPending && update.variables?.id === r.id && update.variables.status === 'in_review'}
                          onClick={() => update.mutate({ id: r.id, status: 'in_review' })}>
                          Взять в работу
                        </Button>
                      )}
                      <Button size="sm" leftIcon={<CheckCircle2 className="size-4" aria-hidden />} onClick={() => setDecide({ report: r, status: 'resolved' })}>
                        Подтвердить и решить
                      </Button>
                      <Button size="sm" variant="ghost" leftIcon={<XCircle className="size-4" aria-hidden />} onClick={() => setDecide({ report: r, status: 'rejected' })}>
                        Отклонить
                      </Button>
                    </div>
                  )}
                </Card>
              </li>
            )
          })}
        </ul>
      )}
      <ConfirmModal
        open={decide !== null}
        onClose={() => (setDecide(null), setBlockCompany(false))}
        onConfirm={(text) => void confirmDecision(text).catch(() => undefined)}
        loading={update.isPending}
        danger={decide?.status === 'resolved' && blockCompany}
        title={decide?.status === 'resolved' ? 'Жалоба подтверждена' : 'Отклонить жалобу?'}
        description={`«${decide?.report.company_name ?? ''}»: ${decide ? REPORT_REASON_LABELS[decide.report.reason].toLowerCase() : ''}`}
        confirmLabel={decide?.status === 'resolved' ? 'Сохранить решение' : 'Отклонить'}
        withComment={{ label: 'Решение (увидит кандидат)', placeholder: decide?.status === 'resolved' ? 'Например: компании вынесено предупреждение' : 'Например: нарушений не найдено', required: true }}
      >
        {decide?.status === 'resolved' && !company(decide.report.company_id)?.blocked && (
          <Checkbox label="Заблокировать компанию" description="Рекрутеры не смогут приглашать кандидатов и публиковать вакансии." checked={blockCompany} onChange={(e) => setBlockCompany(e.target.checked)} />
        )}
      </ConfirmModal>
    </>
  )
}
