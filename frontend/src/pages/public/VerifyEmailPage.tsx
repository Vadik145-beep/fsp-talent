import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, CircleX, MailCheck } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import type { components } from '@/shared/api/schema'
import { USE_MOCKS } from '@/shared/config/env'
import { Button, Input, Spinner } from '@/shared/ui'
import { AuthCard, FormAlert } from './components/AuthCard'
import { MOCK_VERIFY_PREFIX } from './authFlags'

type S = components['schemas']
const RESEND_COOLDOWN_SEC = 60

/** «Проверьте почту» и обработка ссылки из письма (?token=). */
export default function VerifyEmailPage() {
  const [params] = useSearchParams()
  const token = params.get('token')
  return token ? <TokenCheck token={token} /> : <CheckInbox />
}

function TokenCheck({ token }: { token: string }) {
  const verify = useMutation({
    mutationFn: () => api.post<S['MessageResponse']>('/auth/verify-email', { token }),
  })
  const started = useRef(false)
  useEffect(() => {
    // StrictMode вызывает эффект дважды — отправляем токен один раз.
    if (started.current) return
    started.current = true
    verify.mutate()
  }, [verify])

  if (verify.isPending || verify.isIdle) {
    return (
      <AuthCard title="Подтверждаем почту">
        <div className="flex items-center gap-3 text-muted">
          <Spinner size={20} className="text-fsp-plum" />
          Проверяем ссылку…
        </div>
      </AuthCard>
    )
  }
  if (verify.isError) {
    const expired = isApiError(verify.error) && verify.error.status === 410
    return (
      <AuthCard title={expired ? 'Ссылка устарела' : 'Ссылка не сработала'}>
        <div className="flex gap-3">
          <CircleX className="size-6 shrink-0 text-danger" aria-hidden />
          <p className="text-[15px] text-ink">{getErrorMessage(verify.error)}</p>
        </div>
        <div className="mt-6 flex flex-col gap-2 sm:flex-row">
          <Link
            to="/verify-email"
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            Отправить письмо ещё раз
          </Link>
          <Link to="/login" className="inline-flex h-10 items-center justify-center rounded-md px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft">
            Ко входу
          </Link>
        </div>
      </AuthCard>
    )
  }
  return (
    <AuthCard title="Почта подтверждена">
      <div className="flex gap-3">
        <CircleCheck className="size-6 shrink-0 text-success" aria-hidden />
        <p className="text-[15px] text-ink">{verify.data.message}</p>
      </div>
      <Link
        to="/login"
        className="mt-6 inline-flex h-12 w-full items-center justify-center rounded-md bg-primary px-6 text-base font-semibold text-white hover:bg-primary-hover"
      >
        Войти
      </Link>
    </AuthCard>
  )
}

function CheckInbox() {
  const [params] = useSearchParams()
  const initialEmail = params.get('email') ?? ''
  const uid = params.get('uid')
  const [email, setEmail] = useState(initialEmail)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  const resend = useMutation({
    mutationFn: () => api.post<S['MessageResponse']>('/auth/resend-verification', { email: email.trim() }),
    onSuccess: () => setCooldown(RESEND_COOLDOWN_SEC),
    onError: (err) => {
      if (isApiError(err) && err.status === 429) setCooldown(RESEND_COOLDOWN_SEC)
    },
  })

  return (
    <AuthCard
      title="Проверьте почту"
      footer={
        <Link to="/login" className="font-semibold text-fsp-plum hover:underline">
          Уже подтвердили? Войти
        </Link>
      }
    >
      <div className="flex gap-4">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-full bg-primary-soft text-primary">
          <MailCheck className="size-6" aria-hidden />
        </span>
        <p className="text-[15px] text-ink">
          {initialEmail ? (
            <>
              Мы отправили письмо на <span className="font-semibold">{initialEmail}</span>.{' '}
            </>
          ) : (
            'Мы отправили письмо на вашу почту. '
          )}
          Откройте его и нажмите на ссылку — она действует 24 часа.
        </p>
      </div>

      {resend.isSuccess && <div className="mt-5"><FormAlert tone="success">{resend.data.message}</FormAlert></div>}
      {resend.isError && <div className="mt-5"><FormAlert>{getErrorMessage(resend.error)}</FormAlert></div>}

      <div className="mt-6 grid gap-3">
        {!initialEmail && <Input label="Почта" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}
        <p className="text-sm text-muted">Письма нет? Проверьте «Спам» или отправьте ещё раз.</p>
        <Button
          variant="secondary"
          onClick={() => resend.mutate()}
          loading={resend.isPending}
          disabled={cooldown > 0 || !email.trim()}
        >
          {cooldown > 0 ? `Отправить ещё раз через ${cooldown} с` : 'Отправить письмо ещё раз'}
        </Button>
      </div>

      {USE_MOCKS && (
        <div className="mt-6 rounded-md border border-dashed border-fsp-blush bg-primary-soft p-3 text-[13px]">
          <p className="font-semibold text-[#9c0034]">Прототип: письма не отправляются</p>
          {uid ? (
            <Link to={`/verify-email?token=${MOCK_VERIFY_PREFIX}${uid}`} className="mt-1 inline-block font-semibold text-fsp-plum underline">
              Открыть ссылку из письма
            </Link>
          ) : (
            <p className="mt-1 text-muted">Для входа используйте демо-учётку на странице входа.</p>
          )}
        </div>
      )}
    </AuthCard>
  )
}
