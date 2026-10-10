import { useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Columns3, Mail, Rows3 } from 'lucide-react'
import { api } from '@/shared/api'
import { INVITATION_STATUSES, INVITATION_STATUS_LABELS, type InvitationStatus } from '@/shared/config/dictionaries'
import { formatDate, formatSalaryRange } from '@/shared/lib/format'
import { Button, Card, EmptyState, PageHeader, Pseudonym, StatusPill, Table, Tabs, Tag, type TableColumn } from '@/shared/ui'
import { pseudonymCodeOf, rk, type Invitation } from './api'
import { InvitationDrawer } from './components/InvitationDrawer'
import { QueryState } from './components/QueryState'
import { QuotaMeter } from './components/QuotaMeter'
import { WithdrawDialog } from './components/WithdrawDialog'

const CAN_WITHDRAW: InvitationStatus[] = ['sent', 'viewed']

function CandidateCell({ inv }: { inv: Invitation }) {
  if (inv.status === 'accepted' && inv.candidate_contacts) {
    return (
      <span className="block min-w-0">
        <span className="block font-semibold">{inv.candidate_contacts.full_name}</span>
        <span className="block text-[13px] text-muted">{inv.candidate_contacts.email}</span>
      </span>
    )
  }
  return inv.candidate ? <Pseudonym size="sm" code={pseudonymCodeOf(inv.candidate.pseudonym)} /> : <span>—</span>
}

/** Приглашения компании: таблица и канбан по статусам, отзыв, контакты принявших. */
export default function RecruiterInvitationsPage() {
  const [sp, setSp] = useSearchParams()
  const view = sp.get('view') === 'board' ? 'board' : 'table'
  const statusFilter = (sp.get('status') as InvitationStatus | null) ?? null
  const [openId, setOpenId] = useState<number | null>(null)
  const [withdrawId, setWithdrawId] = useState<number | null>(null)
  const invitations = useQuery({ queryKey: rk.invitations, queryFn: () => api.get<Invitation[]>('/invitations') })

  const setParam = (key: string, value: string | null) => {
    const next = new URLSearchParams(sp)
    if (value) next.set(key, value)
    else next.delete(key)
    setSp(next, { replace: true })
  }

  const counts = Object.fromEntries(INVITATION_STATUSES.map((s) => [s, invitations.data?.filter((i) => i.status === s).length ?? 0]))

  const columns: TableColumn<Invitation>[] = [
    { key: 'candidate', header: 'Кандидат', render: (i) => <CandidateCell inv={i} /> },
    { key: 'category_label', header: 'Категория', sortable: true, hideOnMobile: true },
    {
      key: 'salary',
      header: 'Вилка',
      sortable: true,
      sortValue: (i) => i.salary_to,
      render: (i) => <span className="whitespace-nowrap tabular-nums">{formatSalaryRange(i.salary_from, i.salary_to)}</span>,
      hideOnMobile: true,
    },
    {
      key: 'status',
      header: 'Статус',
      sortable: true,
      render: (i) => (
        <span className="flex flex-col items-start gap-0.5">
          <StatusPill status={i.status} />
          {i.status === 'declined' && i.decline_reason_label && <span className="text-[13px] text-muted">{i.decline_reason_label}</span>}
        </span>
      ),
    },
    {
      key: 'created_at',
      header: 'Отправлено',
      sortable: true,
      render: (i) => <span className="whitespace-nowrap">{formatDate(i.created_at)}</span>,
      hideOnMobile: true,
    },
    {
      key: 'actions',
      header: '',
      align: 'right',
      render: (i) =>
        CAN_WITHDRAW.includes(i.status) ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={(e) => {
              e.stopPropagation()
              setWithdrawId(i.id)
            }}
          >
            Отозвать
          </Button>
        ) : null,
    },
  ]

  return (
    <>
      <PageHeader
        title="Приглашения"
        description="Статусы обновляются, когда кандидат открывает, принимает или отклоняет приглашение."
        actions={
          <Tabs
            variant="pills"
            ariaLabel="Вид"
            value={view}
            onChange={(v) => setParam('view', v === 'board' ? 'board' : null)}
            items={[
              { id: 'table', label: <><Rows3 className="size-4" aria-hidden /> Таблица</> },
              { id: 'board', label: <><Columns3 className="size-4" aria-hidden /> Канбан</> },
            ]}
          />
        }
      />
      <Card padding="sm" className="mb-4">
        <QuotaMeter />
      </Card>

      <QueryState
        query={invitations}
        isEmpty={(d) => d.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<Mail aria-hidden />}
              title="Приглашений пока нет"
              description="Откройте подборку по потребности или банк кандидатов и пригласите первого."
              action={
                <Link to="/recruiter/needs" className="font-semibold text-fsp-plum hover:underline">
                  К потребностям
                </Link>
              }
            />
          </Card>
        }
      >
        {(data) =>
          view === 'table' ? (
            <>
              <div className="mb-3 flex flex-wrap gap-1.5" role="group" aria-label="Фильтр по статусу">
                <Tag onClick={() => setParam('status', null)} selected={!statusFilter}>
                  Все · {data.length}
                </Tag>
                {INVITATION_STATUSES.map((s) => (
                  <Tag key={s} onClick={() => setParam('status', statusFilter === s ? null : s)} selected={statusFilter === s}>
                    {INVITATION_STATUS_LABELS[s]} · {counts[s]}
                  </Tag>
                ))}
              </div>
              <Table
                mobileCards
                caption="Приглашения"
                columns={columns}
                rows={statusFilter ? data.filter((i) => i.status === statusFilter) : data}
                rowKey={(i) => i.id}
                onRowClick={(i) => setOpenId(i.id)}
                empty={<EmptyState compact title="С таким статусом приглашений нет" />}
              />
            </>
          ) : (
            <div className="-mx-4 overflow-x-auto px-4 pb-2 sm:mx-0 sm:px-0" data-testid="invitations-board">
              <div className="grid w-max grid-cols-[repeat(6,15rem)] gap-3 xl:w-auto xl:min-w-[1080px] xl:grid-cols-6">
                {INVITATION_STATUSES.map((s) => {
                  const items = data.filter((i) => i.status === s)
                  return (
                    <section key={s} aria-label={INVITATION_STATUS_LABELS[s]} className="flex flex-col gap-2 rounded-lg bg-surface-muted p-2">
                      <header className="flex items-center justify-between px-1 py-1">
                        <StatusPill status={s} />
                        <span className="text-xs font-semibold text-muted tabular-nums">{items.length}</span>
                      </header>
                      {items.map((i) => (
                        <button
                          key={i.id}
                          type="button"
                          onClick={() => setOpenId(i.id)}
                          className="rounded-md border border-line bg-surface p-2.5 text-left text-sm shadow-[var(--shadow-card)] hover:border-fsp-lavender"
                        >
                          <CandidateCell inv={i} />
                          <span className="mt-1.5 block text-[13px] text-muted">{i.category_label}</span>
                          <span className="block text-[13px] font-semibold tabular-nums">{formatSalaryRange(i.salary_from, i.salary_to)}</span>
                          {i.status === 'declined' && i.decline_reason_label && (
                            <span className="mt-1 block text-[13px] text-danger">{i.decline_reason_label}</span>
                          )}
                          <span className="mt-1 block text-xs text-subtle">{formatDate(i.created_at)}</span>
                        </button>
                      ))}
                      {!items.length && <p className="px-1 py-3 text-center text-xs text-subtle">Пусто</p>}
                    </section>
                  )
                })}
              </div>
            </div>
          )
        }
      </QueryState>

      <InvitationDrawer id={openId} onClose={() => setOpenId(null)} onWithdraw={(id) => {
          setOpenId(null)
          setWithdrawId(id)
        }}
      />
      <WithdrawDialog id={withdrawId} onClose={() => setWithdrawId(null)} />
    </>
  )
}
