import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, ArrowRight, Clock, FileUp, Info, ListChecks, PencilLine, Shuffle, Sparkles, Undo2 } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import {
  GRADE_LABELS,
  GRADES,
  SPECIALIZATION_LABELS,
  SPECIALIZATIONS,
  type Grade,
  type Specialization,
} from '@/shared/config/dictionaries'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/cn'
import { Badge, Button, Card, CardHeader, Checkbox, PageHeader, RadioGroup, ScoreBar, Stepper, Tag, Textarea, useToast } from '@/shared/ui'
import { invalidateCandidate, qk, useProfile, useStartTest, type CandidateProfile, type S, type SurveyQuestion } from './api'
import { ProfileForm } from './components/ProfileForm'
import { QueryView } from './components/QueryView'
import { ResumeUpload } from './components/ResumeUpload'
import { ONBOARDING_STEPS, readOnboarding, writeOnboarding, type OnboardingProgress } from './components/onboardingSteps'
import { applyParsedResume, formFromProfile, toUpdate, type ParsedConfidence, type ProfileFormState, type ResumeClaim } from './components/profileFormModel'
import { ResumeClaimNote } from './components/ResumeClaim'
import { hasClaim, writeResumeClaim } from './components/resumeClaimStore'
import { ITEM_FORMAT_LABELS } from './labels'

/** Мастер: 1 профиль → 2 опрос → 3 грейд → 4 тест (отдельный экран) → 5 результат. */
export default function OnboardingPage() {
  const [progress, setProgressState] = useState<OnboardingProgress>(() => {
    const p = readOnboarding()
    return { ...p, step: Math.min(p.step, 3) }
  })
  const setProgress = (patch: Partial<OnboardingProgress>) => {
    setProgressState((prev) => {
      const next = { ...prev, ...patch }
      writeOnboarding(next)
      return next
    })
    window.scrollTo(0, 0)
  }

  return (
    <>
      <PageHeader title="Знакомство" description="Пять коротких шагов — и у вас будет категория, по которой вас найдут работодатели." />
      <Card className="mb-6" padding="sm">
        <Stepper steps={ONBOARDING_STEPS} current={progress.step} onStepClick={(i) => setProgress({ step: i })} />
      </Card>
      {progress.step === 0 && (
        <StepProfile onDone={(claim) => setProgress({ step: 1, ...(claim ? { resume: claim, specialization: null, grade: null } : {}) })} />
      )}
      {progress.step === 1 && (
        <StepSurvey
          initial={progress.survey ?? null}
          initialSpec={progress.specialization ?? null}
          resume={progress.resume ?? null}
          onBack={() => setProgress({ step: 0 })}
          onDone={(survey, specialization) =>
            setProgress({ step: 2, survey, specialization, grade: progress.grade ?? progress.resume?.grade?.value ?? survey.suggested_grade })
          }
        />
      )}
      {progress.step === 2 && (
        <StepGrade
          suggested={progress.survey?.suggested_grade ?? null}
          resume={progress.resume ?? null}
          initial={progress.grade ?? progress.resume?.grade?.value ?? progress.survey?.suggested_grade ?? 'junior'}
          specialization={progress.specialization ?? 'backend'}
          onBack={() => setProgress({ step: 1 })}
          onDone={(grade) => setProgress({ step: 3, grade })}
        />
      )}
      {progress.step === 3 && (
        <StepTest
          specialization={progress.specialization ?? 'backend'}
          grade={progress.grade ?? 'junior'}
          onBack={() => setProgress({ step: 2 })}
          onStarted={() => setProgress({ step: 3 })}
        />
      )}
    </>
  )
}

function StepActions({ onBack, children }: { onBack?: () => void; children: ReactNode }) {
  return (
    <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:items-center sm:justify-between">
      {onBack ? (
        <Button variant="ghost" leftIcon={<ArrowLeft className="size-4" aria-hidden />} onClick={onBack}>
          Назад
        </Button>
      ) : (
        <span />
      )}
      <div className="flex flex-col gap-2 sm:flex-row">{children}</div>
    </div>
  )
}

// --- Шаг 1. Профиль -----------------------------------------------------------------------
function StepProfile({ onDone }: { onDone: (claim: ResumeClaim | null) => void }) {
  const q = useProfile()
  const [mode, setMode] = useState<'choose' | 'manual' | 'pdf'>('choose')
  return (
    <QueryView query={q}>
      {(profile) =>
        mode === 'choose' ? (
          <div>
            <h2 className="mb-1 text-xl font-bold">Как заполним профиль?</h2>
            <p className="mb-4 text-muted">Контакты увидит только работодатель, чьё приглашение вы примете.</p>
            <div className="grid gap-4 sm:grid-cols-2">
              <ChoiceCard
                icon={<FileUp aria-hidden />}
                title="Загрузить PDF-резюме"
                text="Распознаем ФИО, контакты, стек и опыт. Останется проверить."
                badge="Быстрее"
                onClick={() => setMode('pdf')}
              />
              <ChoiceCard
                icon={<PencilLine aria-hidden />}
                title="Заполнить вручную"
                text="Около 5 минут: контакты, формат работы, стек и опыт."
                onClick={() => setMode('manual')}
              />
            </div>
          </div>
        ) : (
          <ProfileStepForm profile={profile} pdf={mode === 'pdf'} onBack={() => setMode('choose')} onDone={onDone} />
        )
      }
    </QueryView>
  )
}

function ChoiceCard({ icon, title, text, badge, onClick }: { icon: ReactNode; title: string; text: string; badge?: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex flex-col items-start rounded-xl border border-line bg-surface p-6 text-left shadow-[var(--shadow-card)] transition-[border-color,box-shadow] hover:border-fsp-lavender hover:shadow-[var(--shadow-pop)] focus-visible:shadow-[var(--shadow-focus)] focus-visible:outline-none"
    >
      <span className="flex w-full items-start justify-between">
        <span className="flex size-11 items-center justify-center rounded-lg bg-primary-soft text-primary [&>svg]:size-6">{icon}</span>
        {badge && <Badge tone="accent">{badge}</Badge>}
      </span>
      <span className="mt-4 text-lg font-bold text-ink">{title}</span>
      <span className="mt-1 text-[15px] text-muted">{text}</span>
      <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-primary">
        Выбрать <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" aria-hidden />
      </span>
    </button>
  )
}

function ProfileStepForm({
  profile,
  pdf,
  onBack,
  onDone,
}: {
  profile: CandidateProfile
  pdf: boolean
  onBack: () => void
  onDone: (claim: ResumeClaim | null) => void
}) {
  const client = useQueryClient()
  const [form, setForm] = useState<ProfileFormState>(() => formFromProfile(profile))
  const [confidence, setConfidence] = useState<ParsedConfidence>({})
  const [parsed, setParsed] = useState<S['ResumeParseResponse'] | null>(null)
  const [claim, setClaim] = useState<ResumeClaim | null>(null)
  const save = useMutation({
    mutationFn: async () => {
      const updated = await api.put<CandidateProfile>('/candidates/me/profile', toUpdate(form))
      // В резюме есть и специализация, и грейд — запоминаем их как заявленный грейд (статус «не подтверждён»).
      // Официальный грейд это не меняет: его присваивает только тест.
      if (claim?.specialization && claim.grade && profile.grade_status !== 'confirmed') {
        await api
          .put('/candidates/me/declared-grade', { specialization: claim.specialization.value, grade: claim.grade.value })
          .catch(() => undefined)
      }
      return updated
    },
    onSuccess: (updated) => {
      client.setQueryData(qk.profile, updated)
      void invalidateCandidate(client)
      if (hasClaim(claim)) writeResumeClaim(claim)
      onDone(hasClaim(claim) ? claim : null)
    },
  })
  const serverErrors =
    isApiError(save.error) && save.error.code === 'validation_error'
      ? (save.error.details.fields as Record<string, string> | undefined)
      : undefined

  if (pdf && !parsed) {
    return (
      <Card>
        <CardHeader title="Загрузите PDF-резюме" description="Подойдёт выгрузка с hh.ru или своё резюме. Файл до 5 МБ." />
        <ResumeUpload
          onParsed={(result) => {
            const applied = applyParsedResume(form, result)
            setForm(applied.form)
            setConfidence(applied.confidence)
            setClaim(applied.claim)
            setParsed(result)
          }}
        />
        <StepActions onBack={onBack}>
          <span />
        </StepActions>
      </Card>
    )
  }

  return (
    <div>
      {parsed && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-fsp-lavender bg-violet-soft px-4 py-3 text-sm text-fsp-plum" role="status">
          <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
          <span>
            Заполнили из «{parsed.filename}». Поля с пометкой «Из резюме» проверьте, жёлтые — распознаны неуверенно.
            {parsed.unmatched_skills?.length ? ` Не нашли в справочнике: ${parsed.unmatched_skills.join(', ')}.` : ''}
            {parsed.warnings?.length ? ` ${parsed.warnings.join(' ')}` : ''}
          </span>
        </div>
      )}
      {claim && <ResumeClaimNote claim={claim} className="mb-4" />}
      {save.isError && !serverErrors && (
        <p className="mb-4 rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
          {getErrorMessage(save.error)}
        </p>
      )}
      <ProfileForm
        value={form}
        onChange={setForm}
        onSubmit={() => save.mutate()}
        submitting={save.isPending}
        submitLabel="Сохранить и продолжить"
        confidence={confidence}
        serverErrors={serverErrors}
        email={profile.email}
        secondary={
          <Button variant="ghost" leftIcon={<ArrowLeft className="size-4" aria-hidden />} onClick={onBack} className="sm:mr-auto">
            Назад
          </Button>
        }
      />
    </div>
  )
}

// --- Шаг 2. Опрос -------------------------------------------------------------------------
type Answers = Record<string, { option_ids: string[]; text: string }>

function StepSurvey({
  initial,
  initialSpec,
  resume,
  onBack,
  onDone,
}: {
  initial: S['SurveyResult'] | null
  initialSpec: Specialization | null
  resume: ResumeClaim | null
  onBack: () => void
  onDone: (survey: S['SurveyResult'], spec: Specialization) => void
}) {
  const questions = useQuery({ queryKey: qk.survey, queryFn: () => api.get<SurveyQuestion[]>('/testing/survey') })
  const [answers, setAnswers] = useState<Answers>({})
  const [missing, setMissing] = useState<string[]>([])
  const [result, setResult] = useState<S['SurveyResult'] | null>(initial)
  const resumeSpec = resume?.specialization?.value ?? null
  const [spec, setSpec] = useState<Specialization | null>(initialSpec ?? (initial ? (resumeSpec ?? initial.recommended_specialization) : null))
  const topics = useQuery({
    queryKey: ['candidate', 'catalog', 'topics'],
    queryFn: () => api.get<S['Topic'][]>('/catalog/topics'),
    staleTime: 10 * 60_000,
  })
  const topicLabel = (id: string) => topics.data?.find((t) => t.id === id)?.label ?? id

  const submit = useMutation({
    mutationFn: () =>
      api.post<S['SurveyResult']>('/testing/survey', {
        answers: Object.entries(answers).map(([question_id, a]) => ({
          question_id,
          option_ids: a.option_ids,
          text: a.text.trim() || null,
        })),
      }),
    onSuccess: (res) => {
      setResult(res)
      // Предзаполняем специализацией из резюме (если есть), рекомендация опроса — рядом.
      setSpec(resumeSpec ?? res.recommended_specialization)
      window.scrollTo(0, 0)
    },
  })

  if (result && spec) {
    return (
      <div className="grid gap-5">
        <Card padding="lg">
          <p className="text-sm font-semibold text-muted">Рекомендуем специализацию</p>
          <p className="mt-1 text-3xl font-bold text-fsp-night">{SPECIALIZATION_LABELS[result.recommended_specialization]}</p>
          <ul className="mt-4 grid gap-1.5">
            {result.explanation.map((line) => (
              <li key={line} className="flex gap-2 text-[15px] text-ink">
                <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                {line}
              </li>
            ))}
          </ul>
          {result.alternatives.length > 1 && (
            <div className="mt-5 grid max-w-md gap-3">
              {result.alternatives.map((a) => (
                <ScoreBar key={a.specialization} label={SPECIALIZATION_LABELS[a.specialization]} value={a.score} hint={`${Math.round(a.score * 100)} % ответов`} />
              ))}
            </div>
          )}
          {result.topics.length > 0 && (
            <div className="mt-5">
              <p className="mb-2 text-sm font-medium text-ink">Темы теста</p>
              <div className="flex flex-wrap gap-1.5">
                {result.topics.map((t) => (
                  <Tag key={t} tone="neutral">
                    {topicLabel(t)}
                  </Tag>
                ))}
              </div>
            </div>
          )}
        </Card>
        <Card>
          <CardHeader
            title="Подтвердите специализацию"
            description={
              resumeSpec
                ? 'Выбрали специализацию из резюме. Можно выбрать другую — тест будет по выбранной.'
                : 'Можно выбрать другую — опрос только подсказывает.'
            }
          />
          {resumeSpec && resumeSpec !== result.recommended_specialization && (
            <p className="mb-3 text-sm text-muted">
              В резюме — {SPECIALIZATION_LABELS[resumeSpec]}, по ответам опроса ближе {SPECIALIZATION_LABELS[result.recommended_specialization]}.
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            {SPECIALIZATIONS.map((s) => (
              <Tag key={s} selected={spec === s} onClick={() => setSpec(s)}>
                {SPECIALIZATION_LABELS[s]}
                {s === result.recommended_specialization ? ' · рекомендуем' : ''}
                {s === resumeSpec ? ' · из резюме' : ''}
              </Tag>
            ))}
          </div>
        </Card>
        <StepActions onBack={() => setResult(null)}>
          <Button size="lg" rightIcon={<ArrowRight className="size-4" aria-hidden />} onClick={() => onDone(result, spec)}>
            Дальше: выбор грейда
          </Button>
        </StepActions>
      </div>
    )
  }

  return (
    <QueryView query={questions}>
      {(list) => {
        const required = list.filter((q) => q.required)
        const answeredRequired = required.filter((q) => isAnswered(answers[q.id])).length
        return (
          <div className="grid gap-4">
            {resume && <ResumeClaimNote claim={resume} />}
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-xl font-bold">Опрос по специализации</h2>
              <p className="text-sm text-muted">
                Обязательных отвечено: {answeredRequired} из {required.length} · баллом не оценивается
              </p>
            </div>
            {list.map((q, i) => (
              <Card key={q.id} className={cn(missing.includes(q.id) && 'border-danger')}>
                <SurveyQuestionField
                  index={i + 1}
                  question={q}
                  value={answers[q.id] ?? { option_ids: [], text: '' }}
                  onChange={(v) => {
                    setAnswers((prev) => ({ ...prev, [q.id]: v }))
                    setMissing((m) => m.filter((id) => id !== q.id))
                  }}
                  error={missing.includes(q.id)}
                />
              </Card>
            ))}
            {submit.isError && (
              <p className="rounded-md bg-danger-soft px-3 py-2 text-sm text-danger" role="alert">
                {getErrorMessage(submit.error)}
              </p>
            )}
            <StepActions onBack={onBack}>
              <Button
                size="lg"
                loading={submit.isPending}
                rightIcon={<ArrowRight className="size-4" aria-hidden />}
                onClick={() => {
                  const notAnswered = required.filter((q) => !isAnswered(answers[q.id])).map((q) => q.id)
                  setMissing(notAnswered)
                  if (notAnswered.length) {
                    document.getElementById(`survey-${notAnswered[0]}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
                    return
                  }
                  submit.mutate()
                }}
              >
                Узнать рекомендацию
              </Button>
            </StepActions>
          </div>
        )
      }}
    </QueryView>
  )
}


function isAnswered(a: { option_ids: string[]; text: string } | undefined) {
  return !!a && (a.option_ids.length > 0 || a.text.trim().length > 0)
}

function SurveyQuestionField({
  index,
  question,
  value,
  onChange,
  error,
}: {
  index: number
  question: SurveyQuestion
  value: { option_ids: string[]; text: string }
  onChange: (v: { option_ids: string[]; text: string }) => void
  error: boolean
}) {
  const title = (
    <span id={`survey-${question.id}`} className="flex gap-2 text-base font-semibold text-ink">
      <span className="text-muted tabular-nums">{index}.</span>
      <span>
        {question.text}
        {question.required ? (
          <span className="ml-0.5 text-primary" aria-label="обязательный вопрос">
            *
          </span>
        ) : (
          <span className="ml-2 text-sm font-normal text-muted">необязательно</span>
        )}
      </span>
    </span>
  )
  const errorText = error ? (
    <p className="mt-2 text-[13px] text-danger" role="alert">
      Ответьте на этот вопрос
    </p>
  ) : null

  if (question.kind === 'text') {
    return (
      <div>
        <Textarea label={title} rows={2} value={value.text} onChange={(e) => onChange({ ...value, text: e.target.value })} />
        {errorText}
      </div>
    )
  }
  if (question.kind === 'single') {
    return (
      <div>
        <RadioGroup
          label={title}
          value={value.option_ids[0] ?? null}
          onChange={(id) => onChange({ ...value, option_ids: [id] })}
          options={(question.options ?? []).map((o) => ({ value: o.id, label: o.label }))}
          orientation="horizontal"
          className="[&_label]:rounded-md [&_label]:border [&_label]:border-line [&_label]:px-3 [&_label]:py-2"
        />
        {errorText}
      </div>
    )
  }
  return (
    <fieldset>
      <legend className="mb-1.5">{title}</legend>
      <p className="mb-2 text-sm text-muted">Можно выбрать несколько</p>
      <div className="flex flex-wrap gap-2">
        {(question.options ?? []).map((o) => (
          <Checkbox
            key={o.id}
            label={o.label}
            checked={value.option_ids.includes(o.id)}
            onChange={(e) =>
              onChange({
                ...value,
                option_ids: e.target.checked ? [...value.option_ids, o.id] : value.option_ids.filter((x) => x !== o.id),
              })
            }
            className="rounded-md border border-line px-3 py-2"
          />
        ))}
      </div>
      {errorText}
    </fieldset>
  )
}

// --- Шаг 3. Грейд -------------------------------------------------------------------------
const GRADE_DESCRIPTIONS: Record<Grade, string> = {
  intern: 'Учитесь или только начинаете, коммерческого опыта нет',
  junior: 'До 2 лет опыта, решаете задачи с подсказками старших',
  middle: '2–5 лет, самостоятельно ведёте задачи от начала до конца',
  senior: 'Больше 5 лет, проектируете решения и отвечаете за результат команды',
}

function StepGrade({
  suggested,
  resume,
  initial,
  specialization,
  onBack,
  onDone,
}: {
  suggested: Grade | null
  resume: ResumeClaim | null
  initial: Grade
  specialization: Specialization
  onBack: () => void
  onDone: (grade: Grade) => void
}) {
  const [grade, setGrade] = useState<Grade>(initial)
  const resumeGrade = resume?.grade?.value ?? null
  const client = useQueryClient()
  const { toast } = useToast()
  // Заявленный грейд сохраняется сразу: до теста статус «грейд не подтверждён» (FTT.4)
  const declare = useMutation({
    mutationFn: () => api.put<S['CandidateGradeStatus']>('/candidates/me/declared-grade', { specialization, grade }),
    onSuccess: (status) => {
      client.setQueryData(qk.grade, status)
      void invalidateCandidate(client)
      onDone(grade)
    },
    onError: (err) => toast({ tone: 'error', title: 'Грейд не сохранился', description: getErrorMessage(err) }),
  })
  return (
    <div className="grid gap-5">
      <Card>
        <CardHeader
          title={`На какой грейд претендуете в ${SPECIALIZATION_LABELS[specialization]}?`}
          description="Тест начнётся с задач этого уровня и подстроится под ваши ответы."
        />
        <RadioGroup
          value={grade}
          onChange={(v) => setGrade(v as Grade)}
          variant="cards"
          orientation="horizontal"
          options={GRADES.map((g) => ({
            value: g,
            label: (
              <span className="inline-flex flex-wrap items-center gap-2">
                {GRADE_LABELS[g]}
                {g === suggested && <Badge tone="accent">По опросу</Badge>}
                {g === resumeGrade && <Badge tone="violet">Из резюме</Badge>}
              </span>
            ),
            description: GRADE_DESCRIPTIONS[g],
          }))}
        />
      </Card>
      <Card className="border-fsp-lavender bg-violet-soft/50">
        <div className="flex gap-3">
          <Info className="mt-0.5 size-5 shrink-0 text-fsp-plum" aria-hidden />
          <div className="grid gap-1.5 text-[15px] text-ink">
            <p className="font-semibold">Как присваивается категория</p>
            {resumeGrade && (
              <p>
                По резюме заявлен {GRADE_LABELS[resumeGrade]}. Категорию определяет тест, а не резюме: если тест покажет другой
                уровень, в профиле будет он.
              </p>
            )}

            <p>
              Подтвердите уровень — получите категорию «{SPECIALIZATION_LABELS[specialization]} · {GRADE_LABELS[grade]}».
            </p>
            <p>
              До теста грейд — «не подтверждён»: официально он присваивается только по результату теста, и только тогда профиль
              попадает в подборку работодателей.
            </p>
            <p>Не подтвердите — предложим тест на грейд ниже. Принудительно грейд не понижаем.</p>
            <p className="text-muted">Сменить грейд можно раз в 90 дней, повторить неудачную попытку — через 30 дней.</p>
          </div>
        </div>
      </Card>
      <StepActions onBack={onBack}>
        <Button size="lg" loading={declare.isPending} rightIcon={<ArrowRight className="size-4" aria-hidden />} onClick={() => declare.mutate()}>
          Дальше: тест
        </Button>
      </StepActions>
    </div>
  )
}

// --- Шаг 4. Тест (вступление) -------------------------------------------------------------
function StepTest({
  specialization,
  grade,
  onBack,
  onStarted,
}: {
  specialization: Specialization
  grade: Grade
  onBack: () => void
  onStarted: () => void
}) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const start = useStartTest()
  const conflict = isApiError(start.error) ? start.error : null
  const runningId = conflict?.code === 'session_in_progress' ? Number(conflict.details.session_id) : null
  const cooldownAt = conflict?.code === 'cooldown_active' ? String(conflict.details.available_at ?? '') : null

  return (
    <div className="grid gap-5">
      <Card padding="lg">
        <p className="text-sm font-semibold text-muted">Адаптивный тест</p>
        <h2 className="mt-1 text-2xl font-bold">
          {SPECIALIZATION_LABELS[specialization]} · {GRADE_LABELS[grade]}
        </h2>
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          <Rule icon={<ListChecks aria-hidden />} title="До 20 задач">
            Тест закончится, когда уровень станет понятен.
          </Rule>
          <Rule icon={<Clock aria-hidden />} title="Время на задачу ограничено">
            Таймер на экране. Не успели — засчитаем то, что выбрано.
          </Rule>
          <Rule icon={<Undo2 aria-hidden />} title="Назад вернуться нельзя">
            Ответ отправляется сразу. Не знаете — нажмите «Не знаю».
          </Rule>
          <Rule icon={<Shuffle aria-hidden />} title="Свой вариант у каждого">
            Правильные ответы не показываем — так задачи не утекают.
          </Rule>
        </ul>
        <div className="mt-6">
          <p className="mb-2 text-sm font-medium text-ink">Форматы задач</p>
          <div className="flex flex-wrap gap-1.5">
            {Object.values(ITEM_FORMAT_LABELS).map((label) => (
              <Tag key={label} tone="neutral">
                {label}
              </Tag>
            ))}
          </div>
        </div>
      </Card>
      {conflict && (
        <div className="rounded-lg border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning" role="alert">
          {conflict.message}
          {cooldownAt && ` Станет доступно ${formatDate(cooldownAt)}`}
          {runningId ? (
            <Button className="ml-3" size="sm" variant="secondary" onClick={() => navigate(`/candidate/test/${runningId}?onboarding=1`)}>
              Продолжить начатый тест
            </Button>
          ) : null}
        </div>
      )}
      <StepActions onBack={onBack}>
        <Button
          size="lg"
          loading={start.isPending}
          onClick={() =>
            start.mutate(
              { specialization, target_grade: grade, kind: 'placement' },
              {
                onSuccess: (state) => {
                  onStarted()
                  navigate(`/candidate/test/${state.session.id}?onboarding=1`)
                },
                onError: (err) => {
                  if (!isApiError(err) || err.status !== 409) {
                    toast({ tone: 'error', title: 'Тест не запустился', description: getErrorMessage(err) })
                  }
                },
              },
            )
          }
        >
          Начать тест
        </Button>
      </StepActions>
    </div>
  )
}

function Rule({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-violet-soft text-fsp-plum [&>svg]:size-5">{icon}</span>
      <span>
        <span className="block font-semibold text-ink">{title}</span>
        <span className="block text-[15px] text-muted">{children}</span>
      </span>
    </li>
  )
}
