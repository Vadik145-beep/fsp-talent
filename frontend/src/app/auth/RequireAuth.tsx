import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Spinner } from '@/shared/ui'
import type { Role } from '@/shared/config/roles'
import { useAuth } from './AuthContext'
import { resolveCabinetAccess } from './guard'

/**
 * Защита маршрутов кабинета (настоящий API): нет сессии → /login?next=…, чужая роль → свой кабинет,
 * пока сессия проверяется — индикатор загрузки. В режиме моков пропускает как есть:
 * демо-пользователя роли подставляет CabinetLayout.
 *
 * Пример: { path: 'candidate', element: <RequireAuth role="candidate"><CabinetLayout … /></RequireAuth> }
 */
export function RequireAuth({ role, children }: { role: Role; children: ReactNode }) {
  const { status, role: userRole, isMock } = useAuth()
  const location = useLocation()
  if (isMock) return <>{children}</>
  const decision = resolveCabinetAccess(status, userRole, role, `${location.pathname}${location.search}`)
  if (decision.type === 'redirect') return <Navigate to={decision.to} replace />
  if (decision.type === 'wait') {
    return (
      <div className="flex justify-center py-24 text-fsp-plum">
        <Spinner size={28} label="Проверяем вход" />
      </div>
    )
  }
  return <>{children}</>
}
