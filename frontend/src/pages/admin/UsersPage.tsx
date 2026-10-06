import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Ban, CircleCheck, Users } from 'lucide-react'
import { api } from '@/shared/api'
import { ROLE_LABELS, ROLES, type Role } from '@/shared/config/roles'
import { formatDate, formatDateTime } from '@/shared/lib/format'
import {
  Avatar,
  Badge,
  Button,
  Drawer,
  EmptyState,
  ErrorState,
  FilterBar,
  PageHeader,
  Pagination,
  Select,
  SkeletonText,
  Table,
  type TableColumn,
} from '@/shared/ui'
import { useAdminMutation, type AuditEntry, type UserPage, type UserRecord } from './api'
import { AuditList } from './components/AuditList'
import { ConfirmModal } from './components/common'

const PAGE_SIZE = 15
const ROLE_OPTIONS = ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] }))
const ROLE_TONES = { candidate: 'violet', recruiter: 'info', admin: 'accent' } as const

export default function AdminUsersPage() {
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [blocked, setBlocked] = useState('')
  const [page, setPage] = useState(1)
  // Открытый пользователь: берём свежую запись из списка, а если после действия он выпал из фильтра — последнюю известную.
  const [openUser, setOpenUser] = useState<UserRecord | null>(null)

  const list = useQuery({
    queryKey: ['admin', 'users', { q, role, blocked, page }],
    queryFn: () => api.get<UserPage>('/admin/users', { query: { q: q.trim(), role, blocked, page, page_size: PAGE_SIZE } }),
    placeholderData: (prev) => prev,
  })
  const active = [q, role, blocked].filter(Boolean).length
  const reset = () => {
    setQ('')
    setRole('')
    setBlocked('')
    setPage(1)
  }

  const columns: TableColumn<UserRecord>[] = [
    {
      key: 'full_name',
      header: 'Пользователь',
      render: (u) => (
        <div className="flex items-center gap-3">
          <Avatar name={u.full_name} size="sm" />
          <div className="min-w-0">
            <p className="font-semibold text-ink">{u.full_name}</p>
            <p className="truncate text-[13px] text-muted">{u.email}</p>
          </div>
        </div>
      ),
    },
    { key: 'role', header: 'Роль', render: (u) => <Badge tone={ROLE_TONES[u.role]}>{ROLE_LABELS[u.role]}</Badge> },
    {
      key: 'status',
      header: 'Статус',
      render: (u) =>
        u.blocked ? (
          <Badge tone="danger">Заблокирован</Badge>
        ) : u.email_verified ? (
          <Badge tone="success">Активен</Badge>
        ) : (
          <Badge tone="warning">Почта не подтверждена</Badge>
        ),
    },
    { key: 'created_at', header: 'Регистрация', hideOnMobile: true, render: (u) => formatDate(u.created_at) },
    { key: 'last_login_at', header: 'Последний вход', hideOnMobile: true, render: (u) => (u.last_login_at ? formatDateTime(u.last_login_at) : '—') },
  ]

  return (
    <>
      <PageHeader title="Пользователи" description="Поиск, смена роли, блокировка и журнал действий по человеку." />
      <FilterBar
        search={{ value: q, onChange: (v) => (setQ(v), setPage(1)), placeholder: 'Почта или ФИО' }}
        activeCount={active}
        onReset={reset}
      >
        <Select aria-label="Роль" containerClassName="sm:w-44" placeholder="Все роли" options={ROLE_OPTIONS} value={role} onChange={(e) => (setRole(e.target.value), setPage(1))} />
        <Select
          aria-label="Блокировка"
          containerClassName="sm:w-48"
          placeholder="Все"
          options={[
            { value: 'false', label: 'Активные' },
            { value: 'true', label: 'Заблокированные' },
          ]}
          value={blocked}
          onChange={(e) => (setBlocked(e.target.value), setPage(1))}
        />
      </FilterBar>
      {list.isError ? (
        <div className="rounded-lg border border-line bg-surface">
          <ErrorState error={list.error} onRetry={() => list.refetch()} />
        </div>
      ) : (
        <>
          <Table
            caption="Пользователи"
            columns={columns}
            rows={list.data?.items ?? []}
            rowKey={(u) => u.id}
            loading={list.isPending}
            onRowClick={(u) => setOpenUser(u)}
            empty={
              <EmptyState
                icon={<Users aria-hidden />}
                title={active ? 'Никого не нашли' : 'Пользователей пока нет'}
                action={active ? <Button variant="secondary" onClick={reset}>Сбросить фильтры</Button> : undefined}
              />
            }
          />
          {list.data && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
              <p className="text-[13px] text-muted">Найдено: {list.data.total}</p>
              <Pagination page={page} pageCount={Math.ceil(list.data.total / PAGE_SIZE)} onChange={setPage} />
            </div>
          )}
        </>
      )}
      <UserDrawer
        user={openUser ? (list.data?.items.find((u) => u.id === openUser.id) ?? openUser) : null}
        onChange={setOpenUser}
        onClose={() => setOpenUser(null)}
      />
    </>
  )
}

function UserDrawer({ user, onChange, onClose }: { user: UserRecord | null; onChange: (u: UserRecord) => void; onClose: () => void }) {
  const [confirmBlock, setConfirmBlock] = useState(false)
  const [roleDraft, setRoleDraft] = useState<{ id: number; role: Role } | null>(null)
  const audit = useQuery({
    queryKey: ['admin', 'user-audit', user?.id],
    queryFn: () => api.get<AuditEntry[]>(`/admin/users/${user!.id}/audit`),
    enabled: user !== null,
  })
  const patch = useAdminMutation(
    (body: { role?: Role; blocked?: boolean }) => api.patch<UserRecord>(`/admin/users/${user!.id}`, body),
    {
      success: (u, v) => (v.blocked !== undefined ? (u.blocked ? `${u.full_name} заблокирован` : `${u.full_name} разблокирован`) : `Роль изменена: ${ROLE_LABELS[u.role]}`),
      onSuccess: (u) => {
        setConfirmBlock(false)
        setRoleDraft(null)
        onChange(u)
      },
    },
  )
  const role = roleDraft && user && roleDraft.id === user.id ? roleDraft.role : user?.role

  return (
    <Drawer open={user !== null} onClose={onClose} title={user?.full_name ?? 'Пользователь'}>
      {user && (
        <div className="flex flex-col gap-6 p-5">
          <div className="flex items-center gap-3">
            <Avatar name={user.full_name} size="lg" />
            <div className="min-w-0">
              <p className="font-semibold">{user.full_name}</p>
              <p className="truncate text-sm text-muted">{user.email}</p>
              <p className="text-xs text-muted">id {user.id} · с {formatDate(user.created_at)}</p>
            </div>
          </div>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Роль</h3>
            <div className="flex items-end gap-2">
              <Select
                aria-label="Роль пользователя"
                containerClassName="flex-1"
                options={ROLE_OPTIONS}
                value={role}
                onChange={(e) => setRoleDraft({ id: user.id, role: e.target.value as Role })}
              />
              <Button variant="secondary" disabled={role === user.role} loading={patch.isPending && patch.variables?.role !== undefined} onClick={() => patch.mutate({ role })}>
                Сохранить
              </Button>
            </div>
            <p className="mt-1 text-[13px] text-muted">Повысить до администратора может только администратор. Себя понизить нельзя.</p>
          </section>

          <section>
            <h3 className="mb-2 text-sm font-semibold">Доступ</h3>
            {user.blocked ? (
              <Button variant="secondary" leftIcon={<CircleCheck className="size-4" aria-hidden />} loading={patch.isPending} onClick={() => patch.mutate({ blocked: false })}>
                Разблокировать
              </Button>
            ) : (
              <Button variant="danger" leftIcon={<Ban className="size-4" aria-hidden />} onClick={() => setConfirmBlock(true)}>
                Заблокировать
              </Button>
            )}
          </section>

          <section>
            <h3 className="mb-3 text-sm font-semibold">Журнал по пользователю</h3>
            {audit.isPending ? (
              <SkeletonText lines={3} />
            ) : audit.isError ? (
              <ErrorState error={audit.error} onRetry={() => audit.refetch()} />
            ) : audit.data.length ? (
              <AuditList entries={audit.data} />
            ) : (
              <p className="text-sm text-muted">Записей нет.</p>
            )}
          </section>
        </div>
      )}
      <ConfirmModal
        open={confirmBlock}
        onClose={() => setConfirmBlock(false)}
        onConfirm={() => patch.mutate({ blocked: true })}
        loading={patch.isPending}
        danger
        title={`Заблокировать ${user?.full_name ?? ''}?`}
        description="Пользователь не сможет войти. Его профиль пропадёт из подборок, приглашения не будут отправляться. Запись попадёт в журнал."
        confirmLabel="Заблокировать"
      />
    </Drawer>
  )
}
