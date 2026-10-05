import { useMemo, useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Ban, Building, CircleCheck, ExternalLink, Flag, ShieldCheck, ShieldQuestion } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDate } from '@/shared/lib/format'
import { Badge, Button, Card, Drawer, EmptyState, ErrorState, FilterBar, PageHeader, ScoreBar, Select, SkeletonCard } from '@/shared/ui'
import { useAdminMutation, type AdminCompany } from './api'
import { ConfirmModal } from './components/common'
import { pct } from './labels'

function trustLevel(score: number) {
  if (score >= 75) return { label: 'Надёжная', tone: 'success' as const, bar: 'bg-success' }
  if (score >= 50) return { label: 'Проверить', tone: 'warning' as const, bar: 'bg-[#c27100]' }
  return { label: 'Риск', tone: 'danger' as const, bar: 'bg-danger' }
}

/** Из чего складывается скоринг (концепция T12.1): какие сигналы тянут вверх и вниз. */
function trustFactors(c: AdminCompany) {
  return [
    { label: 'Почта рекрутеров на домене компании', value: c.verified_domain ? 1 : 0, hint: c.verified_domain ? 'подтверждено' : 'не подтверждено — частый признак фиктивной компании' },
    { label: 'ИНН указан и найден в реестре', value: c.inn ? 1 : 0, hint: c.inn ? `ИНН ${c.inn}` : 'ИНН не указан' },
    { label: 'Отвечают ли кандидаты на приглашения', value: c.response_rate, hint: `${pct(c.response_rate)} приглашений с ответом из ${c.invitations_sent}` },
    { label: 'Без жалоб кандидатов', value: Math.max(0, 1 - c.reports_count / 3), hint: c.reports_count ? `жалоб: ${c.reports_count}` : 'жалоб нет' },
  ]
}

function TrustScore({ score }: { score: number }) {
  const lvl = trustLevel(score)
  return (
    <div className="min-w-32">
      <div className="flex items-baseline justify-between gap-2">
        <b className="text-lg tabular-nums">{Math.round(score)}</b>
        <Badge tone={lvl.tone}>{lvl.label}</Badge>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-line" role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={score} aria-label="Скоринг надёжности">
        <div className={`h-full rounded-full ${lvl.bar}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export default function AdminCompaniesPage() {
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('')
  const [openId, setOpenId] = useState<number | null>(null)
  const q = useQuery({ queryKey: ['admin', 'companies'], queryFn: () => api.get<AdminCompany[]>('/admin/companies') })

  const rows = useMemo(() => {
    const s = search.trim().toLowerCase()
    return (q.data ?? [])
      .filter((c) => !s || c.name.toLowerCase().includes(s) || c.industry.toLowerCase().includes(s))
      .filter((c) => !filter || (filter === 'blocked' ? c.blocked : filter === 'risk' ? c.trust_score < 50 && !c.blocked : !c.blocked))
      .sort((a, b) => a.trust_score - b.trust_score)
  }, [q.data, search, filter])

  return (
    <>
      <PageHeader
        title="Компании"
        description="Скоринг надёжности работодателя защищает кандидатов от фиктивных вакансий: домен почты, ИНН, ответы на приглашения, жалобы."
      />
      <FilterBar search={{ value: search, onChange: setSearch, placeholder: 'Название или отрасль' }} activeCount={[search, filter].filter(Boolean).length} onReset={() => (setSearch(''), setFilter(''))}>
        <Select
          aria-label="Показать"
          containerClassName="sm:w-52"
          placeholder="Все компании"
          options={[
            { value: 'active', label: 'Активные' },
            { value: 'risk', label: 'С низким скорингом' },
            { value: 'blocked', label: 'Заблокированные' },
          ]}
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </FilterBar>
      {q.isPending ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : q.isError ? (
        <Card padding="none">
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      ) : rows.length === 0 ? (
        <Card padding="none">
          <EmptyState icon={<Building aria-hidden />} title={q.data.length ? 'Под фильтр ничего не подошло' : 'Компаний пока нет'} />
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {rows.map((c) => (
            <Card key={c.id} interactive role="button" tabIndex={0} aria-label={`Открыть компанию ${c.name}`}
              onClick={() => setOpenId(c.id)} onKeyDown={(e) => e.key === 'Enter' && setOpenId(c.id)}
              className={c.blocked ? 'opacity-75' : undefined}>
              <div className="mb-3 flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-ink">{c.name}</p>
                  <p className="text-[13px] text-muted">
                    {c.industry}
                    {c.city ? ` · ${c.city}` : ''}
                  </p>
                </div>
                {c.blocked && <Badge tone="danger">Заблокирована</Badge>}
              </div>
              <TrustScore score={c.trust_score} />
              <dl className="mt-4 grid grid-cols-3 gap-2 text-center text-[13px]">
                <div className="rounded-md bg-surface-muted p-2">
                  <dd className="text-base font-bold text-ink">{c.invitations_sent}</dd>
                  <dt className="text-muted">приглашений</dt>
                </div>
                <div className="rounded-md bg-surface-muted p-2">
                  <dd className="text-base font-bold text-ink">{pct(c.response_rate)}</dd>
                  <dt className="text-muted">с ответом</dt>
                </div>
                <div className="rounded-md bg-surface-muted p-2">
                  <dd className={`text-base font-bold ${c.reports_count ? 'text-danger' : 'text-ink'}`}>{c.reports_count}</dd>
                  <dt className="text-muted">жалоб</dt>
                </div>
              </dl>
              <div className="mt-3 flex flex-wrap gap-1.5">
                {c.verified_domain ? (
                  <Badge tone="success" icon={<ShieldCheck aria-hidden />}>Домен подтверждён</Badge>
                ) : (
                  <Badge tone="warning" icon={<ShieldQuestion aria-hidden />}>Домен не подтверждён</Badge>
                )}
                {!c.inn && <Badge tone="warning">Нет ИНН</Badge>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <CompanyDrawer company={q.data?.find((c) => c.id === openId) ?? null} onClose={() => setOpenId(null)} />
    </>
  )
}

function CompanyDrawer({ company, onClose }: { company: AdminCompany | null; onClose: () => void }) {
  const [confirm, setConfirm] = useState(false)
  const patch = useAdminMutation((blocked: boolean) => api.patch<AdminCompany>(`/admin/companies/${company!.id}`, { blocked }), {
    success: (c) => (c.blocked ? `Компания «${c.name}» заблокирована` : `Компания «${c.name}» разблокирована`),
    onSuccess: () => setConfirm(false),
  })
  return (
    <Drawer open={company !== null} onClose={onClose} title={company?.name ?? 'Компания'}>
      {company && (
        <div className="flex flex-col gap-6 p-5">
          <p className="text-sm text-ink">{company.description}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
            <dt className="text-muted">Отрасль</dt>
            <dd>{company.industry}</dd>
            <dt className="text-muted">Сайт</dt>
            <dd>
              {company.website ? (
                <a href={company.website} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-fsp-plum hover:underline">
                  {company.website.replace(/^https?:\/\//, '')} <ExternalLink className="size-3.5" aria-hidden />
                </a>
              ) : (
                '—'
              )}
            </dd>
            <dt className="text-muted">Почта</dt>
            <dd>{company.contact_email}</dd>
            <dt className="text-muted">Рекрутеров</dt>
            <dd>{company.recruiters_count}</dd>
            <dt className="text-muted">На платформе с</dt>
            <dd>{formatDate(company.created_at)}</dd>
          </dl>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Скоринг надёжности</h3>
            <TrustScore score={company.trust_score} />
            <div className="mt-4 flex flex-col gap-3">
              {trustFactors(company).map((f) => (
                <ScoreBar key={f.label} label={f.label} value={f.value} hint={f.hint} />
              ))}
            </div>
            <p className="mt-3 text-[13px] text-muted">
              Новые компании с низким скорингом ограничены: меньше квота приглашений, вакансии проходят ручную проверку.
            </p>
          </section>

          {company.reports_count > 0 && (
            <Link to="/admin/reports" className="inline-flex items-center gap-2 text-sm font-semibold text-fsp-plum hover:underline">
              <Flag className="size-4" aria-hidden /> Жалобы на компанию: {company.reports_count}
            </Link>
          )}

          <section>
            <h3 className="mb-2 text-sm font-semibold">Доступ</h3>
            {company.blocked ? (
              <Button variant="secondary" leftIcon={<CircleCheck className="size-4" aria-hidden />} loading={patch.isPending} onClick={() => patch.mutate(false)}>
                Разблокировать компанию
              </Button>
            ) : (
              <Button variant="danger" leftIcon={<Ban className="size-4" aria-hidden />} onClick={() => setConfirm(true)}>
                Заблокировать компанию
              </Button>
            )}
          </section>
        </div>
      )}
      <ConfirmModal
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => patch.mutate(true)}
        loading={patch.isPending}
        danger
        title={`Заблокировать «${company?.name ?? ''}»?`}
        description="Рекрутеры компании не смогут отправлять приглашения и публиковать вакансии. Кандидаты больше не увидят её вакансий."
        confirmLabel="Заблокировать"
      />
    </Drawer>
  )
}
