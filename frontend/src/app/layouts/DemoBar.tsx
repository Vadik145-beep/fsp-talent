import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { FlaskConical } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { USE_MOCKS } from '@/shared/config/env'
import { ROLE_HOME, ROLE_SHORT_LABELS, ROLES, type Role } from '@/shared/config/roles'
import {
  getMockScenario,
  MOCK_SCENARIO_LABELS,
  setMockScenario,
  type MockScenario,
} from '@/mocks/scenario'
import { useAuth } from '../auth/AuthContext'

/**
 * Плашка прототипа: «Смотреть как: соискатель / рекрутер / админ» и режим данных моков.
 * Показывается только при включённых моках.
 */
export function DemoBar() {
  const { role } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [scenario, setScenario] = useState<MockScenario>(getMockScenario)

  if (!USE_MOCKS) return null

  function pick(next: Role) {
    // Только переход: демо-пользователя роли подставит layout кабинета (CabinetLayout).
    // Если сменить роль прямо здесь, текущий кабинет успеет вернуть свою.
    navigate(ROLE_HOME[next])
  }

  function changeScenario(next: MockScenario) {
    setMockScenario(next)
    setScenario(next)
    void queryClient.resetQueries()
  }

  function resetData() {
    // Динамический импорт: база моков (все фикстуры) не попадает в основной бандл.
    void import('@/mocks/db').then(({ db }) => {
      db.reset()
      void queryClient.resetQueries()
    })
  }

  return (
    <div className="relative z-40 border-b border-line bg-neutral-soft text-[13px] text-ink">
      <div className="mx-auto flex max-w-[1600px] flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-1.5">
        <span className="hidden items-center gap-1.5 font-semibold text-neutral md:inline-flex">
          <FlaskConical className="size-4" aria-hidden />
          Прототип на моках
        </span>
        <div className="flex items-center gap-2" role="group" aria-label="Смотреть как">
          <span className="font-medium text-muted">Смотреть как:</span>
          <div className="inline-flex rounded-full bg-white p-0.5 ring-1 ring-line-strong">
            {ROLES.map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => pick(r)}
                aria-pressed={role === r}
                className={cn(
                  'rounded-full px-2.5 py-0.5 font-semibold transition-colors',
                  role === r ? 'bg-ink text-white' : 'text-ink hover:bg-neutral-soft',
                )}
              >
                {ROLE_SHORT_LABELS[r]}
              </button>
            ))}
          </div>
        </div>
        <label className="flex items-center gap-2 sm:ml-auto">
          <span className="font-medium text-muted">Данные:</span>
          <select
            value={scenario}
            onChange={(e) => changeScenario(e.target.value as MockScenario)}
            className="h-7 cursor-pointer rounded-full border border-line-strong bg-white px-2 font-semibold text-ink focus:outline-none focus-visible:shadow-[var(--shadow-focus)]"
          >
            {(Object.keys(MOCK_SCENARIO_LABELS) as MockScenario[]).map((s) => (
              <option key={s} value={s}>
                {MOCK_SCENARIO_LABELS[s]}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={resetData}
          title="Вернуть исходные демо-данные (приглашения, отклики, ответы)"
          className="rounded-full px-2.5 py-0.5 bg-white font-semibold text-ink ring-1 ring-line-strong hover:bg-nav-hover"
        >
          Сбросить данные
        </button>
      </div>
    </div>
  )
}
