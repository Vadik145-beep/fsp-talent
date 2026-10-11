import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router'
import { useMutation } from '@tanstack/react-query'
import { Eye, EyeOff } from 'lucide-react'
import { api, apiFieldErrors, getErrorMessage, isApiError, looksLikeEmail } from '@/shared/api'
import type { components } from '@/shared/api/schema'
import { Button, Checkbox, Input, Modal, RadioGroup, Switch } from '@/shared/ui'
import { AuthCard, FormAlert } from './components/AuthCard'
import { markOnboardingPending } from './authFlags'

type S = components['schemas']
type RegRole = 'candidate' | 'recruiter'

const CONSENT_VERSION = '2026-10-01'

export default function RegisterPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [role, setRole] = useState<RegRole>(params.get('role') === 'recruiter' ? 'recruiter' : 'candidate')
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [hasInvite, setHasInvite] = useState(false)
  const [companyName, setCompanyName] = useState('')
  const [inn, setInn] = useState('')
  const [inviteCode, setInviteCode] = useState('')
  const [consent, setConsent] = useState(false)
  const [consentOpen, setConsentOpen] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const register = useMutation({
    mutationFn: (body: S['RegisterRequest']) => api.post<S['RegisterResponse']>('/auth/register', body),
    onSuccess: (res) => {
      if (role === 'candidate') markOnboardingPending(res.email)
      navigate(`/verify-email?email=${encodeURIComponent(res.email)}&uid=${res.user_id}`)
    },
    onError: (err) => {
      const fields = apiFieldErrors(err)
      if (isApiError(err) && err.code === 'validation_error' && Object.keys(fields).length) {
        // company.name / company.inn приходят как поле company
        setErrors(fields)
      } else if (isApiError(err) && err.code === 'email_taken') {
        setErrors({ email: 'Эта почта уже зарегистрирована' })
      } else if (isApiError(err) && err.code === 'company_invite_not_found') {
        setErrors({ invite_code: 'Код не найден. Уточните его у администратора компании.' })
      }
    },
  })

  function validate(): Record<string, string> {
    const e: Record<string, string> = {}
    if (fullName.trim().length < 2) e.full_name = 'Укажите имя и фамилию'
    if (!looksLikeEmail(email)) e.email = 'Укажите почту в формате name@example.com'
    if (password.length < 8) e.password = 'Пароль — не короче 8 символов'
    if (role === 'recruiter' && !hasInvite && companyName.trim().length < 2) e.company = 'Укажите название компании'
    if (role === 'recruiter' && hasInvite && !inviteCode.trim()) e.invite_code = 'Введите код приглашения'
    if (!consent) e.consent_processing = 'Без согласия на обработку данных регистрация невозможна'
    return e
  }

  function submit(ev: FormEvent) {
    ev.preventDefault()
    const e = validate()
    setErrors(e)
    if (Object.keys(e).length) return
    register.mutate({
      role,
      full_name: fullName.trim(),
      email: email.trim(),
      password,
      consent_processing: true,
      consent_version: CONSENT_VERSION,
      company:
        role === 'recruiter'
          ? hasInvite
            ? { invite_code: inviteCode.trim() }
            : { name: companyName.trim(), inn: inn.trim() || null }
          : null,
    })
  }

  const generalError =
    register.isError &&
    !(isApiError(register.error) && ['email_taken', 'company_invite_not_found'].includes(register.error.code)) &&
    !Object.keys(apiFieldErrors(register.error)).length

  return (
    <AuthCard
      title="Регистрация"
      description="Займёт минуту. Потом подтвердите почту по ссылке из письма."
      footer={
        <>
          Уже есть аккаунт?{' '}
          <Link to="/login" className="font-semibold text-fsp-plum hover:underline">
            Войти
          </Link>
        </>
      }
    >
      {generalError && <FormAlert>{getErrorMessage(register.error)}</FormAlert>}
      <form onSubmit={submit} noValidate className="grid gap-4">
        <RadioGroup
          label="Кто вы"
          value={role}
          onChange={(v) => setRole(v as RegRole)}
          variant="cards"
          orientation="horizontal"
          options={[
            { value: 'candidate', label: 'Ищу работу', description: 'Соискатель' },
            { value: 'recruiter', label: 'Ищу специалистов', description: 'Рекрутер компании' },
          ]}
        />
        <Input
          label="Имя и фамилия"
          autoComplete="name"
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={errors.full_name}
          required
        />
        <Input
          label="Почта"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={
            errors.email &&
            (errors.email === 'Эта почта уже зарегистрирована' ? (
              <>
                {errors.email}.{' '}
                <Link to={`/login?email=${encodeURIComponent(email.trim())}`} className="font-semibold underline">
                  Войти
                </Link>
              </>
            ) : (
              errors.email
            ))
          }
          required
        />
        <Input
          label="Пароль"
          type={showPassword ? 'text' : 'password'}
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="Не короче 8 символов"
          error={errors.password}
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

        {role === 'recruiter' && (
          <div className="grid gap-4 rounded-lg border border-line bg-surface-muted p-4">
            <Switch
              checked={hasInvite}
              onChange={setHasInvite}
              label="У меня есть код приглашения в компанию"
              description="Код выдаёт администратор компании"
            />
            {hasInvite ? (
              <Input
                label="Код приглашения"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                error={errors.invite_code}
                placeholder="INVITE-1"
              />
            ) : (
              <>
                <Input
                  label="Название компании"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  error={errors.company}
                  required
                />
                <Input
                  label="ИНН"
                  inputMode="numeric"
                  value={inn}
                  onChange={(e) => setInn(e.target.value)}
                  hint="Необязательно. С ИНН компании доверяют больше"
                />
              </>
            )}
          </div>
        )}

        <div>
          <Checkbox
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            label={
              <>
                Согласен на обработку персональных данных{' '}
                <button type="button" onClick={() => setConsentOpen(true)} className="font-semibold text-fsp-plum underline">
                  (текст согласия)
                </button>
              </>
            }
            description="Обязательно. Публиковать профиль работодателям — отдельное согласие, его можно дать позже."
            aria-invalid={errors.consent_processing ? true : undefined}
          />
          {errors.consent_processing && (
            <p className="mt-1 text-[13px] text-danger" role="alert">
              {errors.consent_processing}
            </p>
          )}
        </div>

        <Button type="submit" size="lg" fullWidth loading={register.isPending}>
          Зарегистрироваться
        </Button>
      </form>

      <Modal
        open={consentOpen}
        onClose={() => setConsentOpen(false)}
        title="Согласие на обработку персональных данных"
        description={`Версия от ${CONSENT_VERSION.split('-').reverse().join('.')}`}
        footer={
          <Button
            onClick={() => {
              setConsent(true)
              setConsentOpen(false)
            }}
          >
            Согласен
          </Button>
        }
      >
        <div className="space-y-3 text-[15px] text-ink">
          <p>
            Я даю согласие оператору платформы «ФСП · Таланты» на обработку моих персональных данных: ФИО, почты,
            телефона, города, сведений об опыте и навыках, результатов тестирования и достижений ФСП.
          </p>
          <p>Цель — подбор работы и связь с работодателями, которых я сам выберу. Срок — до отзыва согласия.</p>
          <p>
            Работодатели не видят мои ФИО и контакты, пока я не приму их приглашение. Публикация обезличенного профиля
            требует отдельного согласия, его можно отозвать в настройках в любой момент.
          </p>
        </div>
      </Modal>
    </AuthCard>
  )
}
