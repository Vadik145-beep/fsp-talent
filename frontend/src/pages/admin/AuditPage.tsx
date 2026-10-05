import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { api } from '@/shared/api'
import { ROLE_LABELS } from '@/shared/config/roles'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, EmptyState, ErrorState, FilterBar, PageHeader, Pagination, Select, Table } from '@/shared/ui'
import type { AuditEntry, AuditPage } from './api'
import { AUDIT_ACTION_LABELS, AUDIT_ACTION_TONES, TARGET_TYPE_LABELS } from './labels'

const PAGE_SIZE = 20
const ACTION_OPTIONS = Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => ({ value, label }))
const TARGET_OPTIONS = Object.entries(TARGET_TYPE_LABELS).map(([value, label]) => ({ value, label }))

function details(e: AuditEntry): string {
  const d = e.details ?? {}
  const parts = Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
  return parts.join(' · ')
}

export default function AdminAuditPage() {
  const [action, setAction] = useState('')
  const [target, setTarget] = useState('')
  const [page, setPage] = useState(1)
  const q = useQuery({
    queryKey: ['admin', 'audit', { action, target, page }],
    queryFn: () => api.get<AuditPage>('/admin/audit', { query: { action, target_type: target, page, page_size: PAGE_SIZE } }),
    placeholderData: (prev) => prev,
  })
  const active = [action, target].filter(Boolean).length
  const reset = () => (setAction(''), setTarget(''), setPage(1))

  return (
    <>
      <PageHeader title="Журнал" description="Кто и что сделал: раскрытие контактов, смены грейда, блокировки, вывод шаблонов, изменения настроек. Записи не редактируются." />
      <FilterBar activeCount={active} onReset={reset}>
        <Select aria-label="Действие" containerClassName="sm:w-64" placeholder="Все действия" options={ACTION_OPTIONS} value={action} onChange={(e) => (setAction(e.target.value), setPage(1))} />
        <Select aria-label="Объект" containerClassName="sm:w-52" placeholder="Все объекты" options={TARGET_OPTIONS} value={target} onChange={(e) => (setTarget(e.target.value), setPage(1))} />
      </FilterBar>
      {q.isError ? (
        <div className="rounded-lg border border-line bg-surface">
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </div>
      ) : (
        <>
          <Table
            caption="Журнал действий"
            rows={q.data?.items ?? []}
            rowKey={(e) => e.id}
            loading={q.isPending}
            empty={
              <EmptyState
                icon={<ScrollText aria-hidden />}
                title={active ? 'Под фильтры записей нет' : 'Журнал пуст'}
                action={active ? <Button variant="secondary" onClick={reset}>Сбросить фильтры</Button> : undefined}
              />
            }
            columns={[
              { key: 'at', header: 'Когда', render: (e) => <span className="whitespace-nowrap tabular-nums">{formatDateTime(e.at)}</span> },
              { key: 'action', header: 'Действие', render: (e) => <Badge tone={AUDIT_ACTION_TONES[e.action] ?? 'violet'}>{AUDIT_ACTION_LABELS[e.action] ?? e.action}</Badge> },
              {
                key: 'summary',
                header: 'Что произошло',
                render: (e) => (
                  <div className="min-w-56">
                    <p className="text-ink">{e.summary}</p>
                    {details(e) && <p className="font-mono text-xs text-muted">{details(e)}</p>}
                  </div>
                ),
              },
              {
                key: 'actor',
                header: 'Кто',
                hideOnMobile: true,
                render: (e) => (e.actor_role ? `${ROLE_LABELS[e.actor_role]}${e.actor_user_id ? ` #${e.actor_user_id}` : ''}` : 'Система'),
              },
              {
                key: 'target',
                header: 'Объект',
                hideOnMobile: true,
                render: (e) => `${TARGET_TYPE_LABELS[e.target_type] ?? e.target_type}${e.target_id != null ? ` #${e.target_id}` : ''}`,
              },
            ]}
          />
          {q.data && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p className="text-[13px] text-muted">Записей: {q.data.total}</p>
              <Pagination page={page} pageCount={Math.ceil(q.data.total / PAGE_SIZE)} onChange={setPage} />
            </div>
          )}
        </>
      )}
    </>
  )
}
