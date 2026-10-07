import { useState } from 'react'
import { Link } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Bar, BarChart, CartesianGrid, Cell, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight, ClipboardCheck, Flag, Handshake, ShieldAlert, Users } from 'lucide-react'
import { api } from '@/shared/api'
import { INVITATION_STATUSES, INVITATION_STATUS_LABELS, SPECIALIZATION_LABELS, type Specialization } from '@/shared/config/dictionaries'
import { ROLE_LABELS } from '@/shared/config/roles'
import { formatNumber, plural } from '@/shared/lib/format'
import { Badge, Card, CardHeader, EmptyState, ErrorState, PageHeader, Tabs } from '@/shared/ui'
import type { AdminDashboard } from './api'
import { ChartBox } from './components/charts'
import { AXIS, BRAND, CURSOR_FILL, GRID, INVITATION_STATUS_COLORS, TOOLTIP_STYLE, VALUE_LABEL } from './components/chartTheme'
import { StatTile, StatTileSkeleton } from './components/common'
import { num, pct } from './labels'

const PERIODS = [
  { id: '7', label: '7 дней', days: 7 },
  { id: '30', label: '30 дней', days: 30 },
  { id: 'all', label: 'Всё время', days: 0 },
]

/** Дни подряд от первой даты до последней (пустые дни — нули), за выбранный период. */
function daysSeries(rows: AdminDashboard['tests_by_day'], days: number) {
  if (!rows.length) return []
  const last = new Date(`${rows[rows.length - 1].date}T00:00:00`)
  const first = days ? new Date(last.getTime() - (days - 1) * 86400000) : new Date(`${rows[0].date}T00:00:00`)
  const map = new Map(rows.map((r) => [r.date, r.count]))
  const out: Array<{ date: string; label: string; count: number }> = []
  for (let d = new Date(first); d <= last; d = new Date(d.getTime() + 86400000)) {
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    out.push({ date: key, label: d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }), count: map.get(key) ?? 0 })
  }
  return out
}

export default function AdminDashboardPage() {
  const [period, setPeriod] = useState('30')
  const q = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: () => api.get<AdminDashboard>('/admin/dashboard') })

  return (
    <>
      <PageHeader title="Дашборд" description="Состояние платформы: люди, тесты, приглашения и сигналы, которые требуют внимания." />
      {q.isPending ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <StatTileSkeleton key={i} />
          ))}
        </div>
      ) : q.isError ? (
        <Card padding="none">
          <ErrorState error={q.error} onRetry={() => q.refetch()} retrying={q.isFetching} />
        </Card>
      ) : (
        <DashboardBody data={q.data} period={period} setPeriod={setPeriod} />
      )}
    </>
  )
}

function DashboardBody({ data, period, setPeriod }: { data: AdminDashboard; period: string; setPeriod: (p: string) => void }) {
  const usersTotal = Object.values(data.users_by_role).reduce((s, n) => s + n, 0)
  const invTotal = Object.values(data.invitations_by_status).reduce((s, n) => s + n, 0)
  const days = daysSeries(data.tests_by_day, PERIODS.find((p) => p.id === period)!.days)
  const periodTotal = days.reduce((s, d) => s + d.count, 0)
  const invRows = INVITATION_STATUSES.map((s) => ({ status: s, label: INVITATION_STATUS_LABELS[s], count: data.invitations_by_status[s] ?? 0 }))

  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          icon={<Users aria-hidden />}
          label="Пользователей"
          value={formatNumber(usersTotal)}
          hint={(['candidate', 'recruiter', 'admin'] as const).map((r) => `${ROLE_LABELS[r]}: ${data.users_by_role[r] ?? 0}`).join(' · ')}
        />
        <StatTile icon={<ClipboardCheck aria-hidden />} label="Тестов пройдено" value={formatNumber(data.tests_total)} hint={`за выбранный период: ${periodTotal}`} />
        <StatTile
          icon={<Handshake aria-hidden />}
          tone="success"
          label="Конверсия «приглашение → принятие»"
          value={pct(data.invite_to_accept_conversion)}
          hint={`принято ${data.invitations_by_status.accepted ?? 0} из ${invTotal} отправленных`}
        />
        <StatTile
          icon={<Flag aria-hidden />}
          tone={data.open_reports ? 'accent' : 'default'}
          label="Открытых жалоб"
          value={data.open_reports}
          hint={
            <Link to="/admin/reports" className="font-medium text-fsp-plum hover:underline">
              Перейти к жалобам
            </Link>
          }
        />
      </div>

      <div className="grid gap-6 xl:grid-cols-5">
        <Card className="xl:col-span-3">
          <CardHeader
            title="Тесты по дням"
            description="Сколько тестов на грейд завершили кандидаты."
            actions={<Tabs variant="pills" items={PERIODS} value={period} onChange={setPeriod} ariaLabel="Период" />}
          />
          {days.length ? (
            <ChartBox height={240} label={`Тесты по дням: ${periodTotal} за период`}>
              <BarChart data={days} margin={{ top: 4, right: 4, bottom: 4, left: -16 }} barCategoryGap={2}>
                <CartesianGrid {...GRID} vertical={false} />
                <XAxis dataKey="label" {...AXIS} interval="preserveStartEnd" minTickGap={16} />
                <YAxis allowDecimals={false} {...AXIS} width={44} />
                <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: CURSOR_FILL }} formatter={(v) => [v, 'Тестов']} />
                <Bar dataKey="count" fill={BRAND} radius={[4, 4, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ChartBox>
          ) : (
            <EmptyState compact title="Тестов пока не было" />
          )}
        </Card>

        <Card className="xl:col-span-2">
          <CardHeader title="Приглашения по статусам" description={`Всего ${invTotal} ${plural(invTotal, ['приглашение', 'приглашения', 'приглашений'])}`} />
          {invTotal ? (
            <ChartBox height={240} label="Приглашения по статусам">
              <BarChart data={invRows} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 8 }} barCategoryGap={6}>
                <CartesianGrid {...GRID} horizontal={false} />
                <XAxis type="number" allowDecimals={false} {...AXIS} />
                <YAxis type="category" dataKey="label" width={96} {...AXIS} />
                <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: CURSOR_FILL }} formatter={(v) => [v, 'Приглашений']} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]} maxBarSize={22} label={{ position: 'right', ...VALUE_LABEL, fontSize: 12 }}>
                  {invRows.map((r) => (
                    <Cell key={r.status} fill={INVITATION_STATUS_COLORS[r.status] ?? BRAND} />
                  ))}
                </Bar>
              </BarChart>
            </ChartBox>
          ) : (
            <EmptyState compact title="Приглашений пока нет" />
          )}
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Флаги утечек"
          description="Детектор заметил: задачу стали решать заметно лучше, чем ожидает модель, — возможно, ответ слит. Проверьте шаблон и выведите его из оборота."
          actions={
            data.leak_flags.length ? (
              <Link to="/admin/items?leak=true" className="inline-flex items-center gap-1 text-sm font-semibold text-fsp-plum hover:underline">
                Все в банке задач <ArrowRight className="size-4" aria-hidden />
              </Link>
            ) : undefined
          }
        />
        {data.leak_flags.length ? (
          <ul className="divide-y divide-line">
            {data.leak_flags.map((f) => (
              <li key={f.item_id}>
                <Link
                  to={`/admin/items/${f.item_id}`}
                  className="flex flex-wrap items-center gap-3 rounded-md px-2 py-3 transition-colors hover:bg-violet-soft/60 focus-visible:bg-violet-soft/60 focus-visible:outline-none"
                >
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-danger-soft text-danger">
                    <ShieldAlert className="size-5" aria-hidden />
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold text-ink">{f.title}</span>
                    <span className="block text-[13px] text-muted">{SPECIALIZATION_LABELS[f.specialization as Specialization]} · шаблон #{f.item_id}</span>
                  </span>
                  <Badge tone="danger">z = {num(f.leak_score, 1)}</Badge>
                  <ArrowRight className="size-4 text-subtle" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState compact icon={<ShieldAlert aria-hidden />} title="Флагов утечек нет" description="Детектор не нашёл подозрительных шаблонов." />
        )}
      </Card>
    </div>
  )
}
