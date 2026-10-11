import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ScrollText } from 'lucide-react'
import { api } from '@/shared/api'
import { GRADE_LABELS } from '@/shared/config/dictionaries'
import { ROLE_LABELS } from '@/shared/config/roles'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, EmptyState, ErrorState, FilterBar, PageHeader, Pagination, Select, Table } from '@/shared/ui'
import type { AuditEntry, AuditPage } from './api'
import {
  AUDIT_ACTION_LABELS,
  AUDIT_ACTION_TONES,
  ITEM_STATUS_LABELS,
  num,
  REPORT_REASON_LABELS,
  REPORT_STATUS_LABELS,
  SETTING_LABELS,
  TARGET_TYPE_LABELS,
} from './labels'

const PAGE_SIZE = 20
const ACTION_OPTIONS = Object.entries(AUDIT_ACTION_LABELS).map(([value, label]) => ({ value, label }))
const TARGET_OPTIONS = Object.entries(TARGET_TYPE_LABELS).map(([value, label]) => ({ value, label }))

const scalar = (v: unknown) => v == null || ['string', 'number', 'boolean'].includes(typeof v)

/** Ссылки на объекты в подробностях: «Кандидат #16». */
const REF_LABELS: Record<string, string> = {
  company_id: 'Компания',
  candidate_id: 'Кандидат',
  user_id: 'Пользователь',
  vacancy_id: 'Вакансия',
  recruiter_id: 'Рекрутер',
  token_id: 'Токен',
  webhook_id: 'Вебхук',
  report_id: 'Жалоба',
  item_id: 'Шаблон',
  need_id: 'Потребность',
  invitation_id: 'Приглашение',
  session_id: 'Сессия теста',
}

/** Подписи остальных полей подробностей; значения переводим справочниками ниже. */
const DETAIL_LABELS: Record<string, string> = {
  ...SETTING_LABELS,
  grade_to: 'Новый грейд',
  grade_from: 'Прежний грейд',
  type: 'Согласие',
  reason: 'Причина',
  status: 'Статус',
  role: 'Роль',
  events: 'События',
  leak_score: 'Отклонение z',
  block_company: 'Блокировка компании',
  min_responses: 'Минимум ответов',
  id: 'Код',
  new: 'Новый код',
}

const VALUE_LABELS: Record<string, Record<string, string>> = {
  grade_to: GRADE_LABELS,
  grade_from: GRADE_LABELS,
  role: ROLE_LABELS,
  type: { publication: 'публикация профиля', processing: 'обработка персональных данных' },
  reason: { ...REPORT_REASON_LABELS, cheating: 'Списывание в тесте' },
  status: { ...ITEM_STATUS_LABELS, ...REPORT_STATUS_LABELS },
  events: { 'invitation.accepted': 'кандидат принял приглашение', 'application.created': 'новый отклик' },
}

function show(key: string, v: unknown): string {
  if (v == null) return '—'
  if (typeof v === 'boolean') return v ? 'да' : 'нет'
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : num(v)
  return VALUE_LABELS[key]?.[String(v)] ?? String(v)
}

/**
 * Подробности записи одной строкой. Пары [было, стало] показываем стрелкой; вложенные объекты
 * (пороги, веса) — только названием поля, полные значения есть в summary и в API.
 */
function details(e: AuditEntry): string {
  const parts: string[] = []
  for (const [k, v] of Object.entries(e.details ?? {})) {
    if (REF_LABELS[k] && scalar(v)) {
      parts.push(`${REF_LABELS[k]} #${String(v)}`)
      continue
    }
    const label = DETAIL_LABELS[k] ?? k
    if (Array.isArray(v) && v.length === 2 && v.every(scalar) && k !== 'events') parts.push(`${label}: ${show(k, v[0])} → ${show(k, v[1])}`)
    else if (Array.isArray(v) && v.every(scalar)) parts.push(`${label}: ${v.map((x) => show(k, x)).join(', ')}`)
    else if (scalar(v)) parts.push(`${label}: ${show(k, v)}`)
    else parts.push(`${label}: изменено`)
  }
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
            mobileCards
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
                    {details(e) && <p className="text-xs text-muted">{details(e)}</p>}
                  </div>
                ),
              },
              {
                key: 'actor',
                header: 'Кто',
                hideOnMobile: true,
                render: (e) => (
                  <span className="whitespace-nowrap">{e.actor_role ? `${ROLE_LABELS[e.actor_role]}${e.actor_user_id ? ` #${e.actor_user_id}` : ''}` : 'Система'}</span>
                ),
              },
              {
                key: 'target',
                header: 'Объект',
                hideOnMobile: true,
                render: (e) => (
                  <span className="whitespace-nowrap">{`${TARGET_TYPE_LABELS[e.target_type] ?? e.target_type}${e.target_id != null ? ` #${e.target_id}` : ''}`}</span>
                ),
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
