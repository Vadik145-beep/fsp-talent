import { useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, Send, TrendingUp, TriangleAlert } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { api, isApiError } from '@/shared/api'
import { cn } from '@/shared/lib/cn'
import { formatMoney, formatPercent, formatSalaryRange } from '@/shared/lib/format'
import { Button, Checkbox, Input, Modal, Pseudonym, Select, Skeleton, Textarea, useToast } from '@/shared/ui'
import {
  pseudonymCodeOf,
  rk,
  useCompany,
  useCompanyRecruiters,
  useDebounced,
  useQuota,
  type ContactMethodType,
  type Invitation,
  type InvitationCreate,
  type MarketHint,
  type Vacancy,
} from '../api'
import { CONTACT_TYPE_LABELS } from '../labels'
import { MoneyInput } from './MoneyInput'
import { QuotaMeter } from './QuotaMeter'

export interface InviteTarget {
  id: number
  pseudonym: string
  category?: string | null
  category_label?: string | null
}

export interface InviteModalProps {
  open: boolean
  onClose: () => void
  candidate: InviteTarget
  /** Потребность, из подборки которой приглашаем (вилка подставится из неё). */
  need?: { id: number; title: string; salary_from: number; salary_to: number } | null
  onSent?: (invitation: Invitation) => void
}

/** Модалка приглашения: описание, вилка с рыночной подсказкой, способ связи, вакансия, задание, квота. */
export function InviteModal(props: InviteModalProps) {
  if (!props.open) return null
  return <InviteModalInner {...props} />
}

type FieldErrors = Partial<Record<'description' | 'salary_from' | 'salary_to' | 'contact_method' | 'task_text', string>>

function InviteModalInner({ onClose, candidate, need, onSent }: InviteModalProps) {
  const { toast } = useToast()
  const qc = useQueryClient()
  const { user } = useAuth()
  const company = useCompany()
  const recruiters = useCompanyRecruiters()
  const quota = useQuota()
  const vacancies = useQuery({ queryKey: rk.vacancies, queryFn: () => api.get<Vacancy[]>('/vacancies') })
  const me = recruiters.data?.find((r) => r.user_id === user?.userId) ?? recruiters.data?.[0]

  const position = need?.title ? `«${need.title}»` : (candidate.category_label ?? 'вакансию')
  const [description, setDescription] = useState('')
  const [descTouched, setDescTouched] = useState(false)
  const defaultDescription = `${company.data?.name ?? 'Мы'} приглашает вас на позицию ${position}. Расскажем о задачах и команде на коротком созвоне.`
  const descriptionValue = descTouched ? description : defaultDescription

  const [salaryFrom, setSalaryFrom] = useState<number | null>(need?.salary_from ?? null)
  const [salaryTo, setSalaryTo] = useState<number | null>(need?.salary_to ?? null)
  const [contactType, setContactType] = useState<ContactMethodType>('email')
  const [contactValue, setContactValue] = useState<string | null>(null)
  const [vacancyId, setVacancyId] = useState('')
  const [withTask, setWithTask] = useState(false)
  const [taskText, setTaskText] = useState('')
  const [errors, setErrors] = useState<FieldErrors>({})
  const [banner, setBanner] = useState<{ code: string; message: string } | null>(null)

  const contactDefault = useMemo(() => {
    if (!me) return ''
    if (contactType === 'email') return me.email
    if (contactType === 'phone') return me.phone ?? ''
    if (contactType === 'telegram') return me.telegram ?? ''
    return ''
  }, [me, contactType])
  const contact = contactValue ?? contactDefault

  // Рыночная подсказка обновляется при вводе вилки (с задержкой).
  const hintParams = useDebounced({ category: candidate.category ?? '', salary_from: salaryFrom, salary_to: salaryTo }, 350)
  const hint = useQuery({
    queryKey: rk.marketHint(hintParams),
    queryFn: () => api.get<MarketHint>('/invitations/market-hint', { query: hintParams }),
    enabled: Boolean(hintParams.category),
    placeholderData: (prev) => prev,
  })

  const send = useMutation({
    mutationFn: (body: InvitationCreate) => api.post<Invitation>('/invitations', body),
    onSuccess: (inv) => {
      toast({
        tone: 'success',
        title: 'Приглашение отправлено',
        description: 'Кандидат сразу увидит вилку и описание. Контакты откроются, когда он примет приглашение.',
      })
      void qc.invalidateQueries({ queryKey: rk.all })
      onSent?.(inv)
      onClose()
    },
    onError: (error) => {
      if (!isApiError(error)) {
        setBanner({ code: 'unknown', message: 'Не удалось отправить. Попробуйте ещё раз.' })
        return
      }
      const fields = (error.details?.fields ?? {}) as FieldErrors
      if (error.code === 'salary_below_expectations') {
        setErrors({ salary_to: 'Ниже ожиданий кандидата' })
        setBanner({
          code: error.code,
          message: 'Вилка ниже ожиданий кандидата. Поднимите верхнюю границу — сумму ожиданий мы не раскрываем.',
        })
      } else if (error.code === 'validation_error' || error.code === 'salary_range_invalid') {
        setErrors(fields)
        setBanner(null)
      } else {
        setBanner({ code: error.code, message: error.message })
      }
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    const next: FieldErrors = {}
    if (descriptionValue.trim().length < 10) next.description = 'Опишите предложение (от 10 символов)'
    if (!salaryFrom) next.salary_from = 'Укажите сумму «от»'
    if (!salaryTo) next.salary_to = 'Укажите сумму «до»'
    if (salaryFrom && salaryTo && salaryFrom > salaryTo) next.salary_from = '«От» не может быть больше «до»'
    if (contact.trim().length < 2) next.contact_method = 'Укажите контакт для связи'
    setErrors(next)
    setBanner(null)
    if (Object.keys(next).length) return
    send.mutate({
      candidate_id: candidate.id,
      need_id: need?.id ?? null,
      vacancy_id: vacancyId ? Number(vacancyId) : null,
      description: descriptionValue.trim(),
      salary_from: salaryFrom!,
      salary_to: salaryTo!,
      contact_method: { type: contactType, value: contact.trim() },
      task_text: withTask && taskText.trim() ? taskText.trim() : null,
    })
  }

  const quotaLeft = quota.data?.left ?? 1
  const h = hint.data
  const prob = h?.acceptance_probability ?? null

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title="Приглашение кандидату"
      description="Кандидат увидит компанию, вилку и описание до начала общения."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button
            type="submit"
            form="invite-form"
            loading={send.isPending}
            disabled={quotaLeft <= 0}
            leftIcon={<Send className="size-4" aria-hidden />}
          >
            Отправить приглашение
          </Button>
        </>
      }
    >
      <form id="invite-form" onSubmit={submit} noValidate className="flex flex-col gap-5">
        <div className="flex flex-col gap-3 rounded-md border border-line bg-surface-muted p-3 sm:flex-row sm:items-center sm:justify-between">
          <Pseudonym code={pseudonymCodeOf(candidate.pseudonym)} subtitle={candidate.category_label ?? undefined} />
          <QuotaMeter compact className="sm:w-64" />
        </div>

        {banner && (
          <div role="alert" className="flex gap-2.5 rounded-md border border-danger/30 bg-danger-soft p-3 text-sm text-danger">
            <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
            <div>
              <p className="font-semibold">{banner.message}</p>
              {banner.code === 'quota_exceeded' && (
                <Link to="/recruiter/invitations" className="mt-1 inline-block font-semibold underline" onClick={onClose}>
                  Открыть приглашения и отозвать неактуальные
                </Link>
              )}
            </div>
          </div>
        )}
        {quotaLeft <= 0 && !banner && (
          <div role="status" className="rounded-md bg-warning-soft p-3 text-sm font-medium text-warning">
            Квота исчерпана. Отзовите неактуальные приглашения, чтобы отправить новое.
          </div>
        )}

        <Textarea
          label="Описание предложения"
          required
          rows={3}
          maxLength={3000}
          value={descriptionValue}
          onChange={(e) => {
            setDescTouched(true)
            setDescription(e.target.value)
          }}
          error={errors.description}
        />

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1.5 text-sm font-medium text-ink">
            Зарплата в месяц, ₽<span className="ml-0.5 text-primary" aria-hidden>*</span>
          </legend>
          <div className="grid grid-cols-2 gap-3">
            <MoneyInput label="От" value={salaryFrom} onChange={setSalaryFrom} error={errors.salary_from} placeholder="200 000" />
            <MoneyInput label="До" value={salaryTo} onChange={setSalaryTo} error={errors.salary_to} placeholder="280 000" />
          </div>
          <MarketHintBox
            loading={hint.isPending && Boolean(hintParams.category)}
            hint={h}
            probability={prob}
            onApply={
              h?.median_accepted_from && h.median_accepted_to
                ? () => {
                    setSalaryFrom(h.median_accepted_from)
                    setSalaryTo(h.median_accepted_to)
                  }
                : undefined
            }
          />
        </fieldset>

        <div className="grid gap-3 sm:grid-cols-[180px_1fr]">
          <Select
            label="Способ связи"
            value={contactType}
            options={(Object.keys(CONTACT_TYPE_LABELS) as ContactMethodType[]).map((v) => ({ value: v, label: CONTACT_TYPE_LABELS[v] }))}
            onChange={(e) => {
              setContactType(e.target.value as ContactMethodType)
              setContactValue(null)
            }}
          />
          <Input
            label="Контакт"
            required
            value={contact}
            onChange={(e) => setContactValue(e.target.value)}
            error={errors.contact_method}
            hint="Кандидат увидит его после принятия приглашения"
          />
        </div>

        <Select
          label="Вакансия (необязательно)"
          placeholder="Без привязки к вакансии"
          value={vacancyId}
          onChange={(e) => setVacancyId(e.target.value)}
          options={(vacancies.data ?? [])
            .filter((v) => v.status === 'published')
            .map((v) => ({ value: String(v.id), label: `${v.title} · ${formatSalaryRange(v.salary_from, v.salary_to)}` }))}
        />

        <div className="flex flex-col gap-2">
          <Checkbox
            label="Добавить короткое задание"
            description="Необязательно: 1–2 вопроса, на которые кандидат ответит при принятии."
            checked={withTask}
            onChange={(e) => setWithTask(e.target.checked)}
          />
          {withTask && (
            <Textarea
              aria-label="Текст задания"
              rows={2}
              maxLength={2000}
              placeholder="Например: как бы вы ускорили API, который отвечает 2 секунды?"
              value={taskText}
              onChange={(e) => setTaskText(e.target.value)}
              error={errors.task_text}
            />
          )}
        </div>

        <p className="flex items-center gap-1.5 text-[13px] text-muted">
          <Lock className="size-3.5 shrink-0" aria-hidden />
          ФИО и контакты кандидата откроются только после того, как он примет приглашение.
        </p>
      </form>
    </Modal>
  )
}

function MarketHintBox({
  hint,
  probability,
  loading,
  onApply,
}: {
  hint: MarketHint | undefined
  probability: number | null
  loading: boolean
  onApply?: () => void
}) {
  if (loading) return <Skeleton className="h-20 w-full" />
  if (!hint) return null
  const tone = probability === null ? 'bg-fsp-plum' : probability < 0.4 ? 'bg-danger' : probability < 0.65 ? 'bg-[#c27100]' : 'bg-success'
  return (
    <div className="rounded-md bg-violet-soft p-3 text-sm" aria-live="polite" data-testid="market-hint">
      <p className="flex gap-2 font-medium text-ink">
        <TrendingUp className="mt-0.5 size-4 shrink-0 text-fsp-plum" aria-hidden />
        <span>
          {hint.median_accepted_from
            ? `В категории ${hint.category_label} обычно принимают от ${formatMoney(hint.median_accepted_from)}`
            : `По категории ${hint.category_label} пока мало данных`}
        </span>
      </p>
      {probability !== null && (
        <div className="mt-2.5">
          <div className="mb-1 flex justify-between text-[13px]">
            <span className="text-muted">Вероятность принятия с такой вилкой</span>
            <b className="tabular-nums text-ink">{formatPercent(probability)}</b>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white" role="meter" aria-label="Вероятность принятия" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(probability * 100)}>
            <div className={cn('h-full rounded-full transition-[width]', tone)} style={{ width: `${probability * 100}%` }} />
          </div>
        </div>
      )}
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted">
        <span>
          {hint.median_accepted_from && hint.median_accepted_to
            ? `Типичная вилка: ${formatSalaryRange(hint.median_accepted_from, hint.median_accepted_to)} · данных: ${hint.sample_size}`
            : `Данных: ${hint.sample_size}`}
        </span>
        {onApply && (
          <button type="button" onClick={onApply} className="font-semibold text-fsp-plum underline-offset-2 hover:underline">
            Подставить типичную вилку
          </button>
        )}
      </div>
    </div>
  )
}
