import { useState, type FormEvent } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, getErrorMessage } from '@/shared/api'
import { GRADE_OPTIONS, SPECIALIZATION_OPTIONS, type Grade, type Specialization } from '@/shared/config/dictionaries'
import { Button, Input, Modal, RadioGroup, Select, Textarea, useToast } from '@/shared/ui'
import { apiFieldErrors, refreshRecruiter, rk, upsertInList, type Vacancy, type VacancyCreate, type WorkFormat } from '../api'
import { WORK_FORMAT_OPTIONS } from '../labels'
import { useFieldErrors } from '../useFieldErrors'
import { MoneyInput } from './MoneyInput'
import { SkillInput } from './SkillInput'

type Errors = Partial<Record<keyof VacancyCreate, string>>

interface VacancyValues {
  title: string
  description: string
  specialization: Specialization | ''
  grade: Grade | ''
  work_format: WorkFormat | ''
  salary_from: number | null
  salary_to: number | null
}

function validateVacancy(v: VacancyValues): Errors {
  const next: Errors = {}
  if (v.title.trim().length < 3) next.title = 'Название — не короче 3 символов'
  if (v.description.trim().length < 10) next.description = 'Описание — не короче 10 символов'
  if (!v.specialization) next.specialization = 'Выберите специализацию'
  if (!v.grade) next.grade = 'Выберите грейд'
  if (!v.work_format) next.work_format = 'Выберите формат'
  if (!v.salary_from) next.salary_from = 'Укажите «от»'
  if (!v.salary_to) next.salary_to = 'Укажите «до»'
  if (v.salary_from && v.salary_to && v.salary_from > v.salary_to) next.salary_from = '«От» больше «до»'
  return next
}

const SALARY_PAIR: Array<Array<keyof VacancyCreate>> = [['salary_from', 'salary_to']]

/** Создание и редактирование вакансии. Вилка от–до обязательна. */
export function VacancyFormModal({ open, vacancy, onClose, onSaved }: { open: boolean; vacancy?: Vacancy | null; onClose: () => void; onSaved?: (v: Vacancy) => void }) {
  if (!open) return null
  return <VacancyForm vacancy={vacancy} onClose={onClose} onSaved={onSaved} />
}

function VacancyForm({ vacancy, onClose, onSaved }: { vacancy?: Vacancy | null; onClose: () => void; onSaved?: (v: Vacancy) => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [title, setTitle] = useState(vacancy?.title ?? '')
  const [description, setDescription] = useState(vacancy?.description ?? '')
  const [team, setTeam] = useState(vacancy?.team_description ?? '')
  const [spec, setSpec] = useState<Specialization | ''>(vacancy?.specialization ?? '')
  const [grade, setGrade] = useState<Grade | ''>(vacancy?.grade ?? '')
  const [required, setRequired] = useState<string[]>(vacancy?.skills_required ?? [])
  const [desired, setDesired] = useState<string[]>(vacancy?.skills_desired ?? [])
  const [format, setFormat] = useState<WorkFormat | ''>(vacancy?.work_format ?? '')
  const [city, setCity] = useState(vacancy?.city ?? '')
  const [from, setFrom] = useState<number | null>(vacancy?.salary_from ?? null)
  const [to, setTo] = useState<number | null>(vacancy?.salary_to ?? null)
  const { errors, setErrors, touch, check } = useFieldErrors<VacancyValues, keyof VacancyCreate>(validateVacancy, SALARY_PAIR)
  const values: VacancyValues = { title, description, specialization: spec, grade, work_format: format, salary_from: from, salary_to: to }
  /** Поле изменилось: снять его ошибку, после первой отправки — проверить на лету. */
  const changed = (field: keyof VacancyCreate, patch: Partial<VacancyValues>) => touch(field, { ...values, ...patch })

  const save = useMutation({
    mutationFn: (body: VacancyCreate) =>
      vacancy ? api.put<Vacancy>(`/vacancies/${vacancy.id}`, body) : api.post<Vacancy>('/vacancies', body),
    onSuccess: (v) => {
      toast({ tone: 'success', title: vacancy ? 'Вакансия сохранена' : 'Черновик вакансии создан', description: vacancy ? undefined : 'Опубликуйте его, когда будете готовы.' })
      // Вакансия из ответа — в список и в карточку.
      upsertInList(qc, rk.vacancies, v)
      qc.setQueryData(rk.vacancy(v.id), v)
      // У нового черновика откликов нет — не ходим за пустым списком.
      if (!vacancy && !v.applications_count) qc.setQueryData(rk.vacancyApplications(v.id), [])
      void refreshRecruiter(qc, rk.vacancies)
      onSaved?.(v)
      onClose()
    },
    onError: (e) => {
      const fields = apiFieldErrors(e) as Errors
      if (Object.keys(fields).length) setErrors(fields)
      else toast({ tone: 'error', title: 'Не удалось сохранить', description: getErrorMessage(e) })
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!check(values)) return
    save.mutate({
      title: title.trim(),
      description: description.trim(),
      team_description: team.trim(),
      specialization: spec as Specialization,
      grade: grade as Grade,
      skills_required: required,
      skills_desired: desired,
      work_format: format as WorkFormat,
      city: city.trim() || null,
      salary_from: from!,
      salary_to: to!,
    })
  }

  return (
    <Modal
      open
      onClose={onClose}
      size="lg"
      title={vacancy ? 'Редактировать вакансию' : 'Новая вакансия'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" form="vacancy-form" loading={save.isPending}>
            {vacancy ? 'Сохранить' : 'Создать черновик'}
          </Button>
        </>
      }
    >
      <form id="vacancy-form" onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Название"
          required
          containerClassName="sm:col-span-2"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value)
            changed('title', { title: e.target.value })
          }}
          error={errors.title}
        />
        <Select
          label="Специализация"
          required
          placeholder="Выберите…"
          options={SPECIALIZATION_OPTIONS}
          value={spec}
          onChange={(e) => {
            setSpec(e.target.value as Specialization)
            changed('specialization', { specialization: e.target.value as Specialization })
          }}
          error={errors.specialization}
        />
        <Select
          label="Грейд"
          required
          placeholder="Выберите…"
          options={GRADE_OPTIONS}
          value={grade}
          onChange={(e) => {
            setGrade(e.target.value as Grade)
            changed('grade', { grade: e.target.value as Grade })
          }}
          error={errors.grade}
        />
        <Textarea
          label="Описание"
          required
          containerClassName="sm:col-span-2"
          rows={4}
          maxLength={10000}
          value={description}
          onChange={(e) => {
            setDescription(e.target.value)
            changed('description', { description: e.target.value })
          }}
          error={errors.description}
        />
        <Textarea label="Чем занимается команда" containerClassName="sm:col-span-2" rows={2} maxLength={2000} value={team} onChange={(e) => setTeam(e.target.value)} placeholder="Например: платёжный шлюз, команда 6 человек" />
        <SkillInput label="Обязательный стек" value={required} onChange={setRequired} />
        <SkillInput label="Желательный стек" value={desired} onChange={setDesired} />
        <RadioGroup
          label="Формат работы"
          orientation="horizontal"
          options={WORK_FORMAT_OPTIONS}
          value={format || null}
          onChange={(v) => {
            setFormat(v as WorkFormat)
            changed('work_format', { work_format: v as WorkFormat })
          }}
          error={errors.work_format}
        />
        <Input label="Город" value={city} onChange={(e) => setCity(e.target.value)} placeholder="Не важно" />
        <MoneyInput
          label="Зарплата от, ₽"
          required
          value={from}
          onChange={(v) => {
            setFrom(v)
            changed('salary_from', { salary_from: v })
          }}
          error={errors.salary_from}
        />
        <MoneyInput
          label="Зарплата до, ₽"
          required
          value={to}
          onChange={(v) => {
            setTo(v)
            changed('salary_to', { salary_to: v })
          }}
          error={errors.salary_to}
        />
      </form>
    </Modal>
  )
}
