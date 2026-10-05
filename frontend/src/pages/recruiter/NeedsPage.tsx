import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ChevronRight, Plus, Target, Users } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDate, formatSalaryRange, plural } from '@/shared/lib/format'
import { Badge, Card, EmptyState, PageHeader, Tabs } from '@/shared/ui'
import { rk, type Need } from './api'
import { WORK_FORMAT_LABELS } from './labels'
import { StackTags } from './components/CandidateBits'
import { QueryState } from './components/QueryState'

const newNeedLink =
  'inline-flex h-10 items-center gap-2 rounded-md bg-primary px-4 text-sm font-semibold text-on-primary shadow-sm hover:bg-primary-hover'

/** Список потребностей компании: открыть подборку или создать новую. */
export default function RecruiterNeedsPage() {
  const [tab, setTab] = useState<'active' | 'closed'>('active')
  const needs = useQuery({ queryKey: rk.needs, queryFn: () => api.get<Need[]>('/matching/needs') })
  const counts = {
    active: needs.data?.filter((n) => n.status === 'active').length,
    closed: needs.data?.filter((n) => n.status === 'closed').length,
  }
  return (
    <>
      <PageHeader
        title="Потребности"
        description="Кого ищет компания. По каждой потребности — подборка кандидатов с объяснением."
        actions={
          <Link to="/recruiter/needs/new" className={newNeedLink}>
            <Plus className="size-4" aria-hidden />
            Новая потребность
          </Link>
        }
      />
      <Tabs
        className="mb-4"
        value={tab}
        onChange={(v) => setTab(v as 'active' | 'closed')}
        items={[
          { id: 'active', label: 'Активные', count: counts.active },
          { id: 'closed', label: 'Закрытые', count: counts.closed },
        ]}
      />
      <QueryState
        query={needs}
        isEmpty={(d) => d.filter((n) => n.status === tab).length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<Target aria-hidden />}
              title={tab === 'active' ? 'Активных потребностей нет' : 'Закрытых потребностей нет'}
              description="Опишите, кого ищете, — подборка появится сразу."
              action={
                tab === 'active' ? (
                  <Link to="/recruiter/needs/new" className={newNeedLink}>
                    <Plus className="size-4" aria-hidden />
                    Новая потребность
                  </Link>
                ) : undefined
              }
            />
          </Card>
        }
      >
        {(data) => (
          <ul className="flex flex-col gap-3">
            {data
              .filter((n) => n.status === tab)
              .map((n) => (
                <li key={n.id}>
                  <Link to={`/recruiter/needs/${n.id}`} className="block rounded-lg focus-visible:shadow-[var(--shadow-focus)] focus-visible:outline-none">
                    <Card interactive className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h2 className="text-base font-semibold">{n.title}</h2>
                          <Badge tone="violet">{n.category_label}</Badge>
                          {n.status === 'closed' && <Badge tone="neutral">Закрыта</Badge>}
                        </div>
                        <p className="mt-1 text-sm text-muted">
                          {formatSalaryRange(n.salary_from, n.salary_to)} · {WORK_FORMAT_LABELS[n.work_format]}
                          {n.city ? ` · ${n.city}` : ''} · создана {formatDate(n.created_at)}
                        </p>
                        {Boolean(n.skills_required?.length) && <StackTags className="mt-2" stack={n.skills_required ?? []} />}
                      </div>
                      <div className="flex shrink-0 items-center gap-3">
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-violet-soft px-3 py-1 text-sm font-semibold text-fsp-plum">
                          <Users className="size-4" aria-hidden />
                          {n.candidates_count} {plural(n.candidates_count, ['кандидат', 'кандидата', 'кандидатов'])}
                        </span>
                        <ChevronRight className="size-5 text-subtle" aria-hidden />
                      </div>
                    </Card>
                  </Link>
                </li>
              ))}
          </ul>
        )}
      </QueryState>
    </>
  )
}
