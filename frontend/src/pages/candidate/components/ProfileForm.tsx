import { useState, type FormEvent, type ReactNode } from 'react'
import { Plus, Sparkles, Trash2 } from 'lucide-react'
import { Button, Card, CardHeader, Input, Select, Tag, TagInput, Textarea } from '@/shared/ui'
import { useSkills, type S } from '../api'
import { LINK_TYPE_LABELS, WORK_FORMAT_OPTIONS } from '../labels'
import { normalizeUrl, validateProfile, type ParsedConfidence, type ProfileFormState } from './profileFormModel'

const ROLE_SUGGESTIONS = ['Разработчик', 'Тимлид', 'Ментор', 'Архитектор', 'Аналитик', 'Ревьюер', 'Наставник']
const SOFT_SUGGESTIONS = [
  'Коммуникация',
  'Ответственность',
  'Работа в команде',
  'Наставничество',
  'Критическое мышление',
  'Публичные выступления',
  'Самоорганизация',
]

export interface ProfileFormProps {
  value: ProfileFormState
  onChange: (value: ProfileFormState) => void
  onSubmit: () => void
  submitting?: boolean
  submitLabel?: string
  /** Поля из резюме: подсветка и уверенность распознавания. */
  confidence?: ParsedConfidence
  /** Ошибки полей с сервера (422). */
  serverErrors?: Record<string, string>
  email?: string
  /** Кнопки слева от «Сохранить» (например, «Назад»). */
  secondary?: ReactNode
}

/** Форма профиля соискателя: контакты, формат, стек, опыт, ссылки, минимальная зарплата. */
export function ProfileForm({
  value,
  onChange,
  onSubmit,
  submitting,
  submitLabel = 'Сохранить',
  confidence = {},
  serverErrors,
  email,
  secondary,
}: ProfileFormProps) {
  const skills = useSkills()
  const [errors, setErrors] = useState<Record<string, string>>({})
  const allErrors = { ...serverErrors, ...errors }
  const set = <K extends keyof ProfileFormState>(key: K, v: ProfileFormState[K]) => {
    onChange({ ...value, [key]: v })
    if (errors[key]) setErrors(({ [key]: _, ...rest }) => rest)
  }

  const skillLabel = (id: string) => skills.data?.find((s) => s.id === id)?.label ?? id
  const skillId = (label: string) =>
    skills.data?.find((s) => s.label.toLowerCase() === label.toLowerCase() || s.id === label.toLowerCase())?.id ??
    label.trim().toLowerCase()

  function submit(e: FormEvent) {
    e.preventDefault()
    const found = validateProfile(value)
    setErrors(found)
    if (Object.keys(found).length) {
      document.getElementById(`pf-${Object.keys(found)[0]}`)?.focus()
      return
    }
    onSubmit()
  }

  const parsedHint = (key: keyof ProfileFormState) => {
    const c = confidence[key]
    if (c === undefined) return undefined
    return c < 0.7 ? (
      <span className="font-medium text-warning">Распознано неуверенно — проверьте</span>
    ) : (
      <span className="inline-flex items-center gap-1 text-fsp-plum">
        <Sparkles className="size-3.5" aria-hidden /> Из резюме
      </span>
    )
  }
  const parsedClass = (key: keyof ProfileFormState) =>
    confidence[key] === undefined ? undefined : confidence[key]! < 0.7 ? 'border-warning bg-warning-soft/40' : 'border-fsp-lavender bg-violet-soft/40'

  return (
    <form onSubmit={submit} noValidate className="grid gap-5">
      <Card>
        <CardHeader title="Контакты" description="Работодатель увидит их только после того, как вы примете приглашение." />
        <div className="grid gap-4 sm:grid-cols-2">
          <Input
            id="pf-full_name"
            label="Имя и фамилия"
            required
            value={value.full_name}
            onChange={(e) => set('full_name', e.target.value)}
            error={allErrors.full_name}
            hint={parsedHint('full_name')}
            className={parsedClass('full_name')}
            containerClassName="sm:col-span-2"
          />
          {email && <Input label="Почта для входа" value={email} disabled hint="Меняется через поддержку" />}
          <Input
            id="pf-phone"
            label="Телефон"
            type="tel"
            autoComplete="tel"
            value={value.phone}
            onChange={(e) => set('phone', e.target.value)}
            hint={parsedHint('phone')}
            className={parsedClass('phone')}
          />
          <Input
            id="pf-telegram"
            label="Telegram"
            placeholder="@nickname"
            value={value.telegram}
            onChange={(e) => set('telegram', e.target.value)}
            error={allErrors.telegram}
            hint={parsedHint('telegram')}
            className={parsedClass('telegram')}
          />
          <Input
            id="pf-city"
            label="Город"
            value={value.city}
            onChange={(e) => set('city', e.target.value)}
            hint={parsedHint('city') ?? 'Скрыть город от работодателя можно в настройках'}
            className={parsedClass('city')}
          />
        </div>
      </Card>

      <Card>
        <CardHeader title="Опыт и навыки" />
        <div className="grid gap-4">
          <fieldset>
            <legend className="mb-1.5 text-sm font-medium text-ink">
              Формат работы<span className="ml-0.5 text-primary" aria-hidden>*</span>
            </legend>
            <div className="flex flex-wrap gap-2" id="pf-work_formats" tabIndex={-1}>
              {WORK_FORMAT_OPTIONS.map((o) => (
                <Tag
                  key={o.value}
                  selected={value.work_formats.includes(o.value)}
                  onClick={() =>
                    set(
                      'work_formats',
                      value.work_formats.includes(o.value)
                        ? value.work_formats.filter((x) => x !== o.value)
                        : [...value.work_formats, o.value],
                    )
                  }
                >
                  {o.label}
                </Tag>
              ))}
            </div>
            {allErrors.work_formats ? (
              <p className="mt-1.5 text-[13px] text-danger" role="alert">
                {allErrors.work_formats}
              </p>
            ) : (
              parsedHint('work_formats') && <p className="mt-1.5 text-[13px]">{parsedHint('work_formats')}</p>
            )}
          </fieldset>
          <TagInput
            id="pf-stack"
            label="Стек"
            value={value.stack.map(skillLabel)}
            onChange={(labels) => set('stack', labels.map(skillId))}
            options={skills.data?.map((s) => s.label) ?? []}
            placeholder="Python, PostgreSQL, Docker…"
            hint={parsedHint('stack') ?? 'Из справочника — так работодатели найдут вас по стеку'}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Input
              id="pf-experience_years"
              label="Коммерческий стаж, лет"
              required
              inputMode="decimal"
              value={value.experience_years}
              onChange={(e) => set('experience_years', e.target.value)}
              error={allErrors.experience_years}
              hint={parsedHint('experience_years') ?? 'Например, 2,5'}
              className={parsedClass('experience_years')}
            />
            <Input
              id="pf-min_salary"
              label="Минимальная зарплата, ₽ в месяц"
              inputMode="numeric"
              value={value.min_salary}
              onChange={(e) => set('min_salary', e.target.value.replace(/[^\d\s]/g, ''))}
              error={allErrors.min_salary}
              hint="Видна только системе: приглашения ниже этой суммы не придут. Работодатель её не увидит."
            />
          </div>
          <TagInput
            id="pf-roles_in_team"
            label="Роли в команде"
            value={value.roles_in_team}
            onChange={(v) => set('roles_in_team', v)}
            options={ROLE_SUGGESTIONS}
            hint={parsedHint('roles_in_team')}
          />
          <TagInput
            id="pf-soft_skills"
            label="Софт-скиллы"
            value={value.soft_skills}
            onChange={(v) => set('soft_skills', v)}
            options={SOFT_SUGGESTIONS}
            hint={parsedHint('soft_skills')}
          />
          <Textarea
            id="pf-about"
            label="О себе"
            rows={3}
            value={value.about}
            onChange={(e) => set('about', e.target.value)}
            hint={parsedHint('about') ?? 'Пара предложений: чем занимаетесь и что нравится'}
            className={parsedClass('about')}
          />
        </div>
      </Card>

      <Card>
        <CardHeader title="Ссылки" description="GitHub, портфолио — работодатель увидит их, если разрешите в настройках." />
        <div className="grid gap-3" id="pf-links" tabIndex={-1}>
          {value.links.map((link, i) => (
            <div key={i} className="grid grid-cols-[minmax(0,9rem)_minmax(0,1fr)_auto] items-start gap-2">
              <Select
                aria-label="Тип ссылки"
                value={link.type}
                options={(Object.keys(LINK_TYPE_LABELS) as S['LinkType'][]).map((t) => ({ value: t, label: LINK_TYPE_LABELS[t] }))}
                onChange={(e) => set('links', value.links.map((l, j) => (j === i ? { ...l, type: e.target.value as S['LinkType'] } : l)))}
              />
              <Input
                aria-label="Адрес ссылки"
                placeholder="https://github.com/…"
                value={link.url}
                onChange={(e) => set('links', value.links.map((l, j) => (j === i ? { ...l, url: e.target.value } : l)))}
                onBlur={() => {
                  const url = normalizeUrl(link.url)
                  if (url !== link.url) set('links', value.links.map((l, j) => (j === i ? { ...l, url } : l)))
                }}
                className={parsedClass('links')}
              />
              <Button
                variant="ghost"
                aria-label="Удалить ссылку"
                onClick={() => set('links', value.links.filter((_, j) => j !== i))}
                className="px-2.5"
              >
                <Trash2 className="size-4" aria-hidden />
              </Button>
            </div>
          ))}
          {allErrors.links && (
            <p className="text-[13px] text-danger" role="alert">
              {allErrors.links}
            </p>
          )}
          <div>
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<Plus className="size-4" aria-hidden />}
              onClick={() => set('links', [...value.links, { type: value.links.length ? 'portfolio' : 'github', url: '' }])}
            >
              Добавить ссылку
            </Button>
          </div>
        </div>
      </Card>

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-end">
        {secondary}
        <Button type="submit" size="lg" loading={submitting}>
          {submitLabel}
        </Button>
      </div>
    </form>
  )
}
