import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { Eye, EyeOff, Mail } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { safeNext } from '@/app/auth/guard'
import { api, apiFieldErrors, getErrorMessage, isApiError, looksLikeEmail } from '@/shared/api'
import type { components } from '@/shared/api/schema'
import { USE_MOCKS } from '@/shared/config/env'
import { ROLE_HOME } from '@/shared/config/roles'
import { Button, Input, Modal, useToast } from '@/shared/ui'
import { AuthCard, FormAlert } from './components/AuthCard'
import { DEMO_LOGINS, DEMO_PASSWORD, takeOnboardingPending } from './authFlags'

type S = components['schemas']

export default function LoginPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { toast } = useToast()
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [resetOpen, setResetOpen] = useState(false)
  // Проверка до отправки: пустые поля и почта без «@» — сразу у поля, без запроса.
  const [localErrors, setLocalErrors] = useState<Record<string, string>>({})

  const { login: signIn } = useAuth()
  const login = useMutation({
    mutationFn: (body: S['LoginRequest']) => signIn(body.email, body.password),
    onSuccess: (user) => {
      const next = safeNext(params.get('next'))
      if (next) navigate(next, { replace: true })
      else if (user.role === 'candidate' && takeOnboardingPending()) navigate('/candidate/onboarding', { replace: true })
      else navigate(ROLE_HOME[user.role], { replace: true })
    },
  })

  const error = login.error
  const notVerified = isApiError(error) && error.code === 'email_not_verified'
  const apiErrors = apiFieldErrors(error)
  const fieldErrors = Object.keys(localErrors).length ? localErrors : Object.keys(apiErrors).length ? apiErrors : undefined

  function submit(e: FormEvent) {
    e.preventDefault()
    const errs: Record<string, string> = {}
    if (!email.trim()) errs.email = 'Введите почту'
    else if (!looksLikeEmail(email)) errs.email = 'Введите почту в формате name@example.com'
    if (!password) errs.password = 'Введите пароль'
    setLocalErrors(errs)
    if (Object.keys(errs).length) {
      login.reset()
      return
    }
    login.mutate({ email: email.trim(), password })
  }

  return (
    <AuthCard
      title="Вход"
      description="Войдите по почте и паролю."
      footer={
        <>
          Нет аккаунта?{' '}
          <Link to="/register" className="font-semibold text-fsp-plum hover:underline">
            Зарегистрироваться
          </Link>
        </>
      }
    >
      {error && !fieldErrors && (
        <FormAlert>
          {getErrorMessage(error)}
          {notVerified && (
            <>
              {' '}
              <Link to={`/verify-email?email=${encodeURIComponent(email.trim())}`} className="font-semibold underline">
                Отправить письмо ещё раз
              </Link>
            </>
          )}
        </FormAlert>
      )}

      <form onSubmit={submit} noValidate className="grid gap-4">
        <Input
          label="Почта"
          type="email"
          autoComplete="email"
          leftIcon={<Mail />}
          value={email}
          onChange={(e) => {
            setEmail(e.target.value)
            if (localErrors.email) setLocalErrors(({ email: _drop, ...rest }) => rest)
          }}
          error={fieldErrors?.email}
          required
        />
        <Input
          label="Пароль"
          type={showPassword ? 'text' : 'password'}
          autoComplete="current-password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value)
            if (localErrors.password) setLocalErrors(({ password: _drop, ...rest }) => rest)
          }}
          error={fieldErrors?.password}
          required
          rightSlot={
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="rounded-sm p-1.5 text-subtle hover:text-ink"
              aria-label={showPassword ? 'Скрыть пароль' : 'Показать пароль'}
            >
              {showPassword ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          }
        />
        <div className="-mt-1 text-right">
          <button type="button" onClick={() => setResetOpen(true)} className="text-sm font-medium text-fsp-plum hover:underline">
            Забыли пароль?
          </button>
        </div>
        <Button type="submit" size="lg" fullWidth loading={login.isPending}>
          Войти
        </Button>
      </form>


      {USE_MOCKS && (
        <div className="mt-6 rounded-md border border-dashed border-fsp-blush bg-primary-soft p-3">
          <p className="text-[13px] font-semibold text-accent">Прототип: демо-учётки (пароль {DEMO_PASSWORD})</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {DEMO_LOGINS.map((d) => (
              <button
                key={d.role}
                type="button"
                onClick={() => {
                  setEmail(d.email)
                  setPassword(DEMO_PASSWORD)
                  login.reset()
                }}
                className="rounded-full bg-white px-3 py-1 text-[13px] font-semibold text-fsp-plum ring-1 ring-fsp-blush hover:bg-violet-soft"
              >
                {d.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <ResetPasswordModal
        open={resetOpen}
        initialEmail={email}
        onClose={() => setResetOpen(false)}
        onSent={(message) => {
          setResetOpen(false)
          toast({ tone: 'success', title: 'Письмо отправлено', description: message })
        }}
      />
    </AuthCard>
  )
}

function ResetPasswordModal({
  open,
  initialEmail,
  onClose,
  onSent,
}: {
  open: boolean
  initialEmail: string
  onClose: () => void
  onSent: (message: string) => void
}) {
  const [email, setEmail] = useState(initialEmail)
  const [localError, setLocalError] = useState<string | null>(null)
  const [prevOpen, setPrevOpen] = useState(open)
  if (prevOpen !== open) {
    setPrevOpen(open)
    if (open) {
      setEmail(initialEmail)
      setLocalError(null)
    }
  }
  const reset = useMutation({
    mutationFn: () => api.post<S['MessageResponse']>('/auth/password-reset/request', { email: email.trim() }),
    onSuccess: (res) => onSent(res.message),
  })
  function close() {
    reset.reset()
    onClose()
  }
  function send() {
    const err = !email.trim() ? 'Введите почту, на которую зарегистрирован аккаунт' : !looksLikeEmail(email) ? 'Введите почту в формате name@example.com' : null
    setLocalError(err)
    if (err) {
      reset.reset()
      return
    }
    reset.mutate()
  }
  const resetError = localError ?? (reset.isError ? (apiFieldErrors(reset.error).email ?? getErrorMessage(reset.error)) : undefined)
  return (
    <Modal
      open={open}
      onClose={close}
      size="sm"
      title="Сброс пароля"
      description="Пришлём ссылку для нового пароля на почту."
      footer={
        <>
          <Button variant="ghost" onClick={close}>
            Отмена
          </Button>
          <Button onClick={send} loading={reset.isPending}>
            Отправить ссылку
          </Button>
        </>
      }
    >
      <Input
        label="Почта"
        type="email"
        value={email}
        onChange={(e) => {
          setEmail(e.target.value)
          setLocalError(null)
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            send()
          }
        }}
        error={resetError}
      />
    </Modal>
  )
}
