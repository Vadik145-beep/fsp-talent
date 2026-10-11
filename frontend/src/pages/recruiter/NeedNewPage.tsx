import { useState, type FormEvent, type ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, Save, Sparkles, WandSparkles } from 'lucide-react'
import { api, isApiError } from '@/shared/api'
import { GRADE_OPTIONS, SPECIALIZATION_OPTIONS, type Grade, type Specialization } from '@/shared/config/dictionaries'
import { Badge, Button, Card, CardHeader, Input, PageHeader, RadioGroup, Select, Skeleton, SkeletonCard, Textarea, useToast } from '@/shared/ui'
import { apiFieldErrors, refreshRecruiter, rk, upsertInList, useSkills, type Need, type NeedCreate, type NeedParseResult, type S, type WorkFormat } from './api'
import { WORK_FORMAT_OPTIONS } from './labels'
import { MoneyInput } from './components/MoneyInput'
import { QueryState } from './components/QueryState'
import { SkillInput } from './components/SkillInput'
import { useFieldErrors } from './useFieldErrors'

const EXAMPLES = [
  'Нужен сеньор на Go в финтех, удалёнка, 300–400к',
  'Ищем мидл фронтендера на React и TypeScript, гибрид в Москве, 200–260 тыс. Желательно Next.js',
  'Джун тестировщик: автотесты на Python и pytest, офис в Казани, до 120к',
]

const FIELD_NAMES: Record<string, string> = {
  specialization: 'специализация',
  grade: 'грейд',
  skills_required: 'стек',
  skills_desired: 'желательный стек',
  work_format: 'формат',
  salary: 'вилка',
  salary_from: 'вилка',
  salary_to: 'вилка',
  city: 'город',
  team_description: 'сфера',
}

interface FormState {
  title: string
  specialization: Specialization | ''
  grade: Grade | ''
  skills_required: string[]
  skills_desired: string[]
  team_description: string
  work_format: WorkFormat | ''
  city: string
  salary_from: number | null
  salary_to: number | null
}

const EMPTY: FormState = {
  title: '',
  specialization: '',
  grade: '',
  skills_required: [],
  skills_desired: [],
  team_description: '',
  work_format: '',
  city: '',
  salary_from: null,
  salary_to: null,
}

type Errors = Partial<Record<keyof FormState, string>>

function validateNeed(form: FormState): Errors {
  const next: Errors = {}
  if (form.title.trim().length < 3) next.title = 'Название — не короче 3 символов'
  if (!form.specialization) next.specialization = 'Выберите специализацию'
  if (!form.grade) next.grade = 'Выберите грейд'
  if (!form.work_format) next.work_format = 'Выберите формат'
  if (!form.salary_from) next.salary_from = 'Укажите «от»'
  if (!form.salary_to) next.salary_to = 'Укажите «до»'
  if (form.salary_from && form.salary_to && form.salary_from > form.salary_to) next.salary_from = '«От» больше «до»'
  return next
}

const SALARY_PAIR: Array<Array<keyof FormState>> = [['salary_from', 'salary_to']]

function formOf(n: Need): FormState {
  return {
    title: n.title,
    specialization: n.specialization,
    grade: n.grade,
    skills_required: n.skills_required ?? [],
    skills_desired: n.skills_desired ?? [],
    team_description: n.team_description ?? '',
    work_format: n.work_format,
    city: n.city ?? '',
    salary_from: n.salary_from,
    salary_to: n.salary_to,
  }
}

const REQUIRED_FIELDS: Array<['specialization' | 'grade' | 'work_format' | 'salary', string]> = [
  ['specialization', 'специализация'],
  ['grade', 'грейд'],
  ['work_format', 'формат'],
  ['salary', 'вилка'],
]

/**
 * Создание потребности: свободный текст → «Разобрать» → правка полей → «Подобрать кандидатов».
 * С `:id` в адресе (`/recruiter/needs/:id/edit`) — та же форма для изменения потребности.
 */
export default function RecruiterNeedNewPage() {
  const id = Number(useParams().id) || null
  const need = useQuery({
    queryKey: rk.need(id ?? 0),
    queryFn: () => api.get<Need>(`/matching/needs/${id}`),
    enabled: id !== null,
  })
  if (id === null) return <NeedForm />
  if (need.isSuccess) return <NeedForm need={need.data} />
  return (
    <>
      <PageHeader title="Изменить поиск" back={{ to: `/recruiter/needs/${id}`, label: 'Подборка' }} />
      {need.isPending ? (
        <>
          <Skeleton className="mb-6 h-10 w-2/3" />
          <SkeletonCard />
        </>
      ) : (
        <QueryState query={need}>{() => null}</QueryState>
      )}
    </>
  )
}

function NeedForm({ need }: { need?: Need }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { toast } = useToast()
  const skills = useSkills()
  const [text, setText] = useState(need?.raw_text ?? '')
  const [textError, setTextError] = useState<string | null>(null)
  const [form, setForm] = useState<FormState>(need ? formOf(need) : EMPTY)
  const { errors, setErrors, touch, check } = useFieldErrors<FormState, keyof FormState>(validateNeed, SALARY_PAIR)
  const [parsed, setParsed] = useState<NeedParseResult | null>(null)
  // В контракте вилка — salary_from / salary_to, в старых ответах — salary: приводим к одному.
  const fromText = new Set((parsed?.recognized_fields ?? []).map((f) => (f === 'salary_from' || f === 'salary_to' ? 'salary' : f)))
  const recognizedNames = [...new Set([...fromText].map((f) => FIELD_NAMES[f] ?? f))]
  // unrecognized: по контракту — фрагменты текста, которые не разобрали; имена полей тоже допускаем.
  const unrecognized = (parsed?.unrecognized ?? []).filter((x) => !(x in FIELD_NAMES))
  const missing = parsed
    ? REQUIRED_FIELDS.filter(([f]) => (f === 'salary' ? !form.salary_from || !form.salary_to : !form[f])).map(([, label]) => label)
    : []

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    const next = { ...form, [key]: value }
    setForm(next)
    touch(key, next)
  }

  const parse = useMutation({
    mutationFn: (t: string) => api.post<NeedParseResult>('/matching/needs/parse', { text: t }),
    onSuccess: (res) => {
      const d = res.draft
      setParsed(res)
      setErrors({})
      setForm((f) => ({
        title: d.title ?? f.title,
        specialization: d.specialization ?? f.specialization,
        grade: d.grade ?? f.grade,
        skills_required: d.skills_required?.length ? d.skills_required : f.skills_required,
        skills_desired: d.skills_desired?.length ? d.skills_desired : f.skills_desired,
        team_description: d.team_description ?? f.team_description,
        work_format: d.work_format ?? f.work_format,
        city: d.city ?? f.city,
        salary_from: d.salary_from ?? f.salary_from,
        salary_to: d.salary_to ?? f.salary_to,
      }))
    },
    onError: (e) => setTextError(apiFieldErrors(e).text ?? (isApiError(e) ? e.message : 'Не удалось разобрать текст')),
  })

  const create = useMutation({
    mutationFn: (body: NeedCreate) =>
      need
        ? api.put<Need>(`/matching/needs/${need.id}`, { ...body, status: need.status } satisfies S['NeedUpdate'])
        : api.post<Need>('/matching/needs', body),
    onSuccess: (saved) => {
      // Потребность из ответа — в кэш: экран подборки откроется без лишнего запроса.
      upsertInList(qc, rk.needs, saved)
      // список уже обновлён; подборка и категории изменённой потребности — заново
      void refreshRecruiter(qc, (k) => k.length === rk.needs.length && k[1] === rk.needs[1])
      qc.setQueryData(rk.need(saved.id), saved)
      toast(
        need
          ? { tone: 'success', title: 'Поиск сохранён', description: 'Подборка пересчитана по новым полям.' }
          : { tone: 'success', title: 'Поиск создан', description: `В основной категории ${saved.candidates_count} канд.` },
      )
      navigate(`/recruiter/needs/${saved.id}`)
    },
    onError: (e) => {
      const fields = apiFieldErrors(e) as Errors
      const unknownSkills = isApiError(e) && e.code === 'unknown_skills' && Array.isArray(e.details?.skills) ? (e.details.skills as string[]) : []
      if (Object.keys(fields).length) setErrors(fields)
      else
        toast({
          tone: 'error',
          title: 'Не удалось сохранить',
          description: isApiError(e) ? `${e.message}${unknownSkills.length ? `: ${unknownSkills.join(', ')}` : ''}` : undefined,
        })
    },
  })

  function onParse() {
    if (text.trim().length < 5) {
      setTextError('Опишите, кого ищете, хотя бы парой слов')
      return
    }
    setTextError(null)
    parse.mutate(text.trim())
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!check(form)) return
    create.mutate({
      title: form.title.trim(),
      raw_text: text.trim() || null,
      specialization: form.specialization as Specialization,
      grade: form.grade as Grade,
      skills_required: form.skills_required,
      skills_desired: form.skills_desired,
      team_description: form.team_description.trim(),
      work_format: form.work_format as WorkFormat,
      city: form.city.trim() || null,
      salary_from: form.salary_from!,
      salary_to: form.salary_to!,
    })
  }

  const mark = (field: string): ReactNode =>
    fromText.has(field) ? (
      <Badge tone="success" className="ml-2 align-middle" icon={<Sparkles aria-hidden />}>
        из текста
      </Badge>
    ) : null

  return (
    <>
      {need ? (
        <PageHeader
          title="Изменить поиск"
          back={{ to: `/recruiter/needs/${need.id}`, label: 'Подборка' }}
          description="Поправьте поля — подборка пересчитается. Можно заново разобрать текст."
        />
      ) : (
        <PageHeader
          title="Новый поиск"
          back={{ to: '/recruiter/needs', label: 'Поиск кандидатов' }}
          description="Опишите, кого ищете, своими словами — мы разложим текст по полям. Потом поправьте и запустите подбор."
        />
      )}

      <Card className="mb-6">
        <Textarea
          label="Опишите, кого ищете"
          rows={4}
          maxLength={3000}
          placeholder="Например: нужен сеньор на Go в финтех, удалёнка, 300–400к"
          value={text}
          onChange={(e) => setText(e.target.value)}
          error={textError}
          className="text-base"
        />
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-muted">Примеры:</span>
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              type="button"
              onClick={() => setText(ex)}
              className="max-w-full rounded-2xl border border-line px-3 py-1 text-left text-[13px] text-fsp-plum hover:border-fsp-lavender hover:bg-violet-soft sm:truncate sm:rounded-full"
            >
              {ex}
            </button>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={onParse} loading={parse.isPending} leftIcon={<WandSparkles className="size-4" aria-hidden />}>
            Разобрать
          </Button>
          {parsed && (
            <p className="text-sm text-muted" role="status">
              Распознано: <b className="text-ink">{recognizedNames.length ? recognizedNames.join(', ') : 'ничего'}</b>
              {missing.length > 0 && <> · заполните вручную: {missing.join(', ')}</>}
              {unrecognized.length > 0 && <> · не разобрали: {unrecognized.map((x) => `«${x}»`).join(', ')}</>}
            </p>
          )}
        </div>
      </Card>

      <form onSubmit={onSubmit} noValidate>
        <Card>
          <CardHeader title="Параметры поиска" description="Проверьте и при необходимости поправьте." />
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label={<>Название {mark('specialization')}</>}
              required
              containerClassName="md:col-span-2"
              value={form.title}
              onChange={(e) => set('title', e.target.value)}
              error={errors.title}
              placeholder="Senior Backend-разработчик (Go)"
            />
            <Select
              label={<>Специализация {mark('specialization')}</>}
              required
              placeholder="Выберите…"
              options={SPECIALIZATION_OPTIONS}
              value={form.specialization}
              onChange={(e) => set('specialization', e.target.value as Specialization)}
              error={errors.specialization}
            />
            <Select
              label={<>Грейд {mark('grade')}</>}
              required
              placeholder="Выберите…"
              options={GRADE_OPTIONS}
              value={form.grade}
              onChange={(e) => set('grade', e.target.value as Grade)}
              error={errors.grade}
            />
            <SkillInput
              label={<>Обязательный стек {mark('skills_required')}</>}
              value={form.skills_required}
              onChange={(v) => set('skills_required', v)}
            />
            <SkillInput
              label={<>Желательный стек {mark('skills_desired')}</>}
              value={form.skills_desired}
              onChange={(v) => set('skills_desired', v)}
              placeholder="Будет плюсом"
            />
            <Textarea
              label={<>Чем занимается команда {mark('team_description')}</>}
              containerClassName="md:col-span-2"
              rows={2}
              maxLength={2000}
              value={form.team_description}
              onChange={(e) => set('team_description', e.target.value)}
              placeholder="Платёжный шлюз, команда 6 человек"
            />
            <RadioGroup
              label={<>Формат работы {mark('work_format')}</>}
              orientation="horizontal"
              options={WORK_FORMAT_OPTIONS}
              value={form.work_format || null}
              onChange={(v) => set('work_format', v as WorkFormat)}
              error={errors.work_format}
            />
            <Input
              label={<>Город {mark('city')}</>}
              value={form.city}
              onChange={(e) => set('city', e.target.value)}
              placeholder="Не важно"
            />
            <fieldset className="md:col-span-2">
              <legend className="mb-1.5 text-sm font-medium text-ink">
                Вилка в месяц, ₽<span className="ml-0.5 text-primary" aria-hidden>*</span> {mark('salary')}
              </legend>
              <div className="grid max-w-md grid-cols-2 gap-3">
                <MoneyInput label="От" value={form.salary_from} onChange={(v) => set('salary_from', v)} error={errors.salary_from} placeholder="300 000" />
                <MoneyInput label="До" value={form.salary_to} onChange={(v) => set('salary_to', v)} error={errors.salary_to} placeholder="400 000" />
              </div>
              <p className="mt-1.5 text-[13px] text-muted">Вилка обязательна: кандидат видит зарплату до начала общения.</p>
            </fieldset>
          </div>
          {skills.isLoading && <p className="mt-2 text-[13px] text-muted">Загружаем справочник стека…</p>}
          <div className="mt-6 flex justify-end border-t border-line pt-4">
            {need ? (
              <Button type="submit" size="lg" loading={create.isPending} leftIcon={<Save className="size-5" aria-hidden />}>
                Сохранить
              </Button>
            ) : (
              <Button type="submit" size="lg" loading={create.isPending} rightIcon={<ArrowRight className="size-5" aria-hidden />}>
                Подобрать кандидатов
              </Button>
            )}
          </div>
        </Card>
      </form>
    </>
  )
}
