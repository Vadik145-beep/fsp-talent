import { useState } from 'react'
import { Link } from 'react-router'
import { ChevronRight, Clock, Mail, MessagesSquare } from 'lucide-react'
import { formatDate, formatSalaryRange } from '@/shared/lib/format'
import { Card, EmptyState, PageHeader, StatusPill, Tabs } from '@/shared/ui'
import { useInvitations, type Invitation } from './api'
import { QueryView } from './components/QueryView'
import { CONTACT_TYPE_LABELS } from './labels'

type TabId = 'all' | 'new' | 'accepted' | 'declined' | 'archive'

const TAB_FILTER: Record<TabId, (i: Invitation) => boolean> = {
  all: () => true,
  new: (i) => i.status === 'sent' || i.status === 'viewed',
  accepted: (i) => i.status === 'accepted',
  declined: (i) => i.status === 'declined',
  archive: (i) => i.status === 'expired' || i.status === 'withdrawn',
}

export default function InvitationsPage() {
  const q = useInvitations()
  const [tab, setTab] = useState<TabId>('all')
  return (
    <>
      <PageHeader
        title="Приглашения"
        description="Работодатели нашли вас по категории. В каждом приглашении — зарплата «от–до»; ваши контакты откроются, только если примете."
      />
      <QueryView
        query={q}
        isEmpty={(list) => list.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<Mail aria-hidden />}
              title="Приглашений пока нет"
              description="Они появятся, когда работодатель найдёт вас в подборке. Полный профиль и свежие задания поднимают вас выше."
              action={
                <Link to="/candidate/profile" className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover">
                  Дополнить профиль
                </Link>
              }
            />
          </Card>
        }
      >
        {(list) => {
          const rows = list.filter(TAB_FILTER[tab])
          return (
            <>
              <Tabs
                className="mb-4"
                value={tab}
                onChange={(v) => setTab(v as TabId)}
                ariaLabel="Фильтр приглашений"
                items={[
                  { id: 'all', label: 'Все', count: list.length },
                  { id: 'new', label: 'Ждут ответа', count: list.filter(TAB_FILTER.new).length },
                  { id: 'accepted', label: 'Принятые', count: list.filter(TAB_FILTER.accepted).length },
                  { id: 'declined', label: 'Отклонённые', count: list.filter(TAB_FILTER.declined).length },
                  { id: 'archive', label: 'Архив', count: list.filter(TAB_FILTER.archive).length },
                ]}
              />
              {rows.length ? (
                <ul className="grid gap-3">
                  {rows.map((inv) => (
                    <li key={inv.id}>
                      <InvitationRow inv={inv} />
                    </li>
                  ))}
                </ul>
              ) : (
                <Card padding="none">
                  <EmptyState compact title="В этом разделе пусто" />
                </Card>
              )}
            </>
          )
        }}
      </QueryView>
    </>
  )
}

function InvitationRow({ inv }: { inv: Invitation }) {
  const waiting = inv.status === 'sent' || inv.status === 'viewed'
  return (
    <Link
      to={`/candidate/invitations/${inv.id}`}
      className="group block rounded-lg border border-line bg-surface p-4 shadow-[var(--shadow-card)] transition-[border-color,box-shadow] hover:border-fsp-lavender hover:shadow-[var(--shadow-pop)] focus-visible:shadow-[var(--shadow-focus)] focus-visible:outline-none sm:p-5"
    >
      <div className="flex items-start gap-4">
        <span className="hidden size-11 shrink-0 items-center justify-center rounded-md bg-fsp-plum text-sm font-bold text-white sm:flex" aria-hidden>
          {inv.company_name
            .replace(/[«»"]/g, '')
            .split(/\s+/)
            .slice(0, 2)
            .map((w) => w[0])
            .join('')
            .toUpperCase()}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="font-semibold text-ink">{inv.company_name}</span>
            <StatusPill status={inv.status} />
            {inv.status === 'sent' && <span className="size-2 rounded-full bg-primary" aria-label="Новое" />}
          </div>
          <p className="mt-1 text-xl font-bold text-fsp-night tabular-nums sm:text-2xl">{formatSalaryRange(inv.salary_from, inv.salary_to)}</p>
          <p className="mt-1 line-clamp-1 text-sm text-muted">{inv.description}</p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted">
            <span>{inv.category_label}</span>
            <span>Связь: {CONTACT_TYPE_LABELS[inv.contact_method.type]}</span>
            {inv.task_text && (
              <span className="inline-flex items-center gap-1">
                <MessagesSquare className="size-3.5" aria-hidden /> Есть вопрос к созвону
              </span>
            )}
            {waiting ? (
              <span className="inline-flex items-center gap-1 font-medium text-warning">
                <Clock className="size-3.5" aria-hidden /> Ответить до {formatDate(inv.expires_at)}
              </span>
            ) : (
              <span>Получено {formatDate(inv.created_at)}</span>
            )}
          </div>
        </div>
        <ChevronRight className="mt-1 size-5 shrink-0 text-subtle transition-transform group-hover:translate-x-0.5" aria-hidden />
      </div>
    </Link>
  )
}
