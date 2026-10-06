import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { CircleCheck, Eye, EyeOff } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import type { components } from '@/shared/api/schema'
import { Button, Input } from '@/shared/ui'
import { AuthCard, FormAlert } from './components/AuthCard'

type S = components['schemas']

/** Новый пароль по ссылке из письма: /reset-password?token=… */
export default function ResetPasswordPage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [repeat, setRepeat] = useState('')
  const [show, setShow] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const confirm = useMutation({
    mutationFn: () =>
      api.post<S['MessageResponse']>('/auth/password-reset/confirm', { token, new_password: password }),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (password.length < 8) next.password = 'Пароль — не короче 8 символов'
    if (repeat !== password) next.repeat = 'Пароли не совпадают'
    setErrors(next)
    if (!Object.keys(next).length) confirm.mutate()
  }

  if (!token) {
    return (
      <AuthCard title="Ссылка неполная">
        <p className="text-[15px] text-ink">В ссылке нет кода сброса. Запросите новую ссылку на странице входа.</p>
        <Link
          to="/login"
          className="mt-6 inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
        >
          Ко входу
        </Link>
      </AuthCard>
    )
  }

  if (confirm.isSuccess) {
    return (
      <AuthCard title="Пароль изменён">
        <div className="flex gap-3">
          <CircleCheck className="size-6 shrink-0 text-success" aria-hidden />
          <p className="text-[15px] text-ink">{confirm.data.message} Войдите с новым паролем.</p>
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

  const tokenProblem = isApiError(confirm.error) && (confirm.error.status === 400 || confirm.error.status === 410)

  return (
    <AuthCard title="Новый пароль" description="Придумайте пароль не короче 8 символов.">
      {confirm.isError && (
        <FormAlert>
          {getErrorMessage(confirm.error)}
          {tokenProblem && (
            <>
              {' '}
              <Link to="/login" className="font-semibold underline">
                Запросить новую ссылку
              </Link>
            </>
          )}
        </FormAlert>
      )}
      <form onSubmit={submit} noValidate className="grid gap-4">
        <Input
          label="Новый пароль"
          type={show ? 'text' : 'password'}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
          required
          rightSlot={
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              className="rounded-sm p-1.5 text-subtle hover:text-ink"
              aria-label={show ? 'Скрыть пароль' : 'Показать пароль'}
            >
              {show ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
            </button>
          }
        />
        <Input
          label="Повторите пароль"
          type={show ? 'text' : 'password'}
          autoComplete="new-password"
          value={repeat}
          onChange={(e) => setRepeat(e.target.value)}
          error={errors.repeat}
          required
        />
        <Button type="submit" size="lg" fullWidth loading={confirm.isPending}>
          Сохранить пароль
        </Button>
      </form>
    </AuthCard>
  )
}
