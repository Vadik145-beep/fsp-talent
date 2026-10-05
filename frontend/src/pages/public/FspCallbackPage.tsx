import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { CircleX, ShieldCheck, UserRound } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { api, getErrorMessage } from '@/shared/api'
import type { components } from '@/shared/api/schema'
import { ROLE_HOME } from '@/shared/config/roles'
import { Spinner, useToast } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import { AuthCard } from './components/AuthCard'
import { clearPendingFspAuth, readPendingFspAuth, type FspPurpose } from './fspAuth'

type S = components['schemas']

/** Тестовые участники ФСП для экрана-заглушки Keycloak в прототипе. */
const MOCK_PARTICIPANTS = [
  { fspId: 'FSP-000001', title: 'Участник с историей', note: '3 соревнования в реестре ФСП' },
  { fspId: 'FSP-000036', title: 'Участник без истории', note: 'Зарегистрирован в ФСП, соревнований пока нет' },
]

/** Возврат из Keycloak: ?code&state → вход или привязка ФСП ID. */
export default function FspCallbackPage() {
  const [params] = useSearchParams()
  if (params.get('mock_idp') === '1') return <MockIdentityProvider />
  const error = params.get('error')
  const code = params.get('code')
  const state = params.get('state')
  if (error || !code || !state) {
    return (
      <CallbackError
        message={
          error
            ? params.get('error_description') || 'Вход через ФСП ID отменён.'
            : 'Не хватает данных авторизации. Начните вход через ФСП ID заново.'
        }
      />
    )
  }
  return <CodeExchange code={code} state={state} />
}

function CodeExchange({ code, state }: { code: string; state: string }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  const { switchRole } = useAuth()
  const { toast } = useToast()
  const [pending] = useState(readPendingFspAuth)
  const stateMismatch = !!pending && pending.state !== state
  const purpose: FspPurpose = pending?.purpose ?? 'login'
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return
    started.current = true
    if (stateMismatch) {
      clearPendingFspAuth()
      return
    }
    const mode = purpose
    const body: S['FspCodeExchange'] = {
      code,
      state,
      code_verifier: pending?.codeVerifier ?? 'x'.repeat(43),
      redirect_uri: pending?.redirectUri ?? `${window.location.origin}/auth/fsp-callback`,
    }
    const run = async () => {
      try {
        if (mode === 'link') {
          const status = await api.post<S['FspStatus']>('/auth/fsp-link', body)
          clearPendingFspAuth()
          await client.invalidateQueries({ queryKey: ['candidate'] })
          toast({
            tone: 'success',
            title: 'ФСП ID привязан',
            description: status.has_history
              ? `Нашли достижений: ${status.achievements_count ?? 0}. Они уже в профиле.`
              : 'В реестре ФСП пока нет соревнований — это не влияет на подбор.',
          })
          navigate(pending?.returnTo ?? '/candidate/fsp', { replace: true })
        } else {
          const res = await api.post<S['TokenResponse']>('/auth/fsp/login', body)
          clearPendingFspAuth()
          switchRole(res.user.role)
          navigate(ROLE_HOME[res.user.role], { replace: true })
        }
      } catch (err) {
        clearPendingFspAuth()
        setError(getErrorMessage(err))
      }
    }
    void run()
  }, [code, state, pending, purpose, stateMismatch, client, navigate, switchRole, toast])

  if (stateMismatch) {
    return <CallbackError message="Ответ ФСП ID не совпал с запросом (state). Попробуйте ещё раз." purpose={purpose} />
  }
  if (error) return <CallbackError message={error} purpose={purpose} />
  return (
    <AuthCard title={purpose === 'link' ? 'Привязываем ФСП ID' : 'Входим через ФСП ID'}>
      <div className="flex items-center gap-3 text-muted">
        <Spinner size={20} className="text-fsp-plum" />
        Проверяем данные ФСП ID…
      </div>
    </AuthCard>
  )
}

function CallbackError({ message, purpose = 'login' }: { message: string; purpose?: FspPurpose }) {
  return (
    <AuthCard title={purpose === 'link' ? 'Не удалось привязать ФСП ID' : 'Не удалось войти через ФСП ID'}>
      <div className="flex gap-3">
        <CircleX className="size-6 shrink-0 text-danger" aria-hidden />
        <p className="text-[15px] text-ink">{message}</p>
      </div>
      <div className="mt-6 flex flex-col gap-2 sm:flex-row">
        {purpose === 'link' ? (
          <Link
            to="/candidate/settings"
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            Вернуться в настройки
          </Link>
        ) : (
          <Link
            to="/login"
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            Войти по почте
          </Link>
        )}
        <Link to="/" className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft">
          На главную
        </Link>
      </div>
    </AuthCard>
  )
}

/** Прототип: вместо страницы Keycloak — выбор тестового участника ФСП. */
function MockIdentityProvider() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const state = params.get('state') ?? ''
  const purpose = params.get('purpose') === 'link' ? 'link' : 'login'
  const [selected, setSelected] = useState(MOCK_PARTICIPANTS[0].fspId)

  return (
    <AuthCard
      title="ФСП ID"
      description={purpose === 'link' ? 'Подтвердите привязку профиля к ФСП ID.' : 'Вход для участников соревнований ФСП.'}
      footer="Прототип: это заглушка страницы Keycloak (realm fsp). На сервере здесь будет настоящий вход ФСП ID."
    >
      <fieldset>
        <legend className="mb-2 text-sm font-medium text-ink">Тестовый участник</legend>
        <div className="grid gap-2">
          {MOCK_PARTICIPANTS.map((p) => (
            <label
              key={p.fspId}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-lg border p-3 transition-colors',
                selected === p.fspId ? 'border-primary bg-primary-soft' : 'border-line hover:border-fsp-lavender',
              )}
            >
              <input
                type="radio"
                name="participant"
                checked={selected === p.fspId}
                onChange={() => setSelected(p.fspId)}
                className="size-[18px] accent-primary"
              />
              <UserRound className="size-5 text-fsp-plum" aria-hidden />
              <span className="min-w-0">
                <span className="block text-sm font-semibold text-ink">
                  {p.fspId} · {p.title}
                </span>
                <span className="block text-[13px] text-muted">{p.note}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <button
        type="button"
        onClick={() =>
          navigate(`/auth/fsp-callback?code=${encodeURIComponent(`mock:${selected}`)}&state=${encodeURIComponent(state)}`, {
            replace: true,
          })
        }
        className="mt-6 inline-flex h-12 w-full items-center justify-center gap-2 rounded-md bg-fsp-night px-6 text-base font-semibold text-white hover:bg-fsp-plum"
      >
        <ShieldCheck className="size-5 text-fsp-blush" aria-hidden />
        {purpose === 'link' ? 'Разрешить привязку' : 'Войти'}
      </button>
    </AuthCard>
  )
}
