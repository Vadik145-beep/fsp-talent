import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ListChecks, Plus } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { cn } from '@/shared/lib/cn'
import { formatDate, plural } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, EmptyState, Input, Modal, PageHeader, Pseudonym, Select, Textarea, useToast } from '@/shared/ui'
import { apiFieldErrors, pseudonymCodeOf, refreshRecruiter, rk, upsertInList, useCategories, type RegularTask, type S, type TaskSubmission } from './api'
import { ANSWER_KIND_LABELS, SCORE_LABELS, SUBMISSION_STATUS } from './labels'
import { QueryState } from './components/QueryState'

/** Регулярные задания: создать короткую задачу, смотреть ответы, оценивать 0–3. */
export default function RecruiterTasksPage() {
  const [sp, setSp] = useSearchParams()
  const [createOpen, setCreateOpen] = useState(false)
  const tasks = useQuery({ queryKey: rk.tasks, queryFn: () => api.get<RegularTask[]>('/tasks') })
  const selectedId = Number(sp.get('task')) || tasks.data?.[0]?.id || null
  const selected = tasks.data?.find((t) => t.id === selectedId) ?? null

  return (
    <>
      <PageHeader
        title="Задания"
        description="Короткие задачи «решить или предложить подход». Система раздаёт их кандидатам категории; оценка освежает профиль и поднимает его в подборке."
        actions={
          <Button onClick={() => setCreateOpen(true)} leftIcon={<Plus className="size-4" aria-hidden />}>
            Создать задание
          </Button>
        }
      />
      <QueryState
        query={tasks}
        isEmpty={(d) => d.length === 0}
        empty={
          <Card padding="none">
            <EmptyState
              icon={<ListChecks aria-hidden />}
              title="Заданий пока нет"
              description="Создайте короткую задачу — её получат кандидаты выбранной категории."
              action={<Button onClick={() => setCreateOpen(true)}>Создать задание</Button>}
            />
          </Card>
        }
      >
        {(data) => (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
            <ul className="flex flex-col gap-2" aria-label="Задания компании">
              {data.map((t) => {
                const active = t.id === selectedId
                return (
                  <li key={t.id}>
                    <button
                      type="button"
                      onClick={() => setSp({ task: String(t.id) }, { replace: true })}
                      aria-current={active ? 'true' : undefined}
                      className={cn(
                        'w-full rounded-lg border p-3 text-left transition-colors',
                        active ? 'border-fsp-plum bg-violet-soft' : 'border-line bg-surface hover:border-fsp-lavender',
                      )}
                    >
                      <span className="block font-semibold">{t.title}</span>
                      <span className="mt-0.5 block text-[13px] text-muted">
                        {t.category_label} · {t.submissions_count ?? 0} {plural(t.submissions_count ?? 0, ['кандидат', 'кандидата', 'кандидатов'])}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
            {selected && <TaskSubmissions task={selected} />}
          </div>
        )}
      </QueryState>
      <CreateTaskModal open={createOpen} onClose={() => setCreateOpen(false)} onCreated={(t) => setSp({ task: String(t.id) }, { replace: true })} />
    </>
  )
}

function TaskSubmissions({ task }: { task: RegularTask }) {
  const subs = useQuery({ queryKey: rk.submissions(task.id), queryFn: () => api.get<TaskSubmission[]>(`/tasks/${task.id}/submissions`) })
  return (
    <section aria-label="Ответы кандидатов" className="min-w-0">
      <Card className="mb-4">
        <CardHeader
          title={task.title}
          description={`${task.category_label} · срок ${task.deadline_days} ${plural(task.deadline_days, ['день', 'дня', 'дней'])} · создано ${formatDate(task.created_at)}`}
        />
        <p className="text-sm whitespace-pre-line">{task.statement}</p>
      </Card>
      <QueryState
        query={subs}
        isEmpty={(d) => d.length === 0}
        empty={
          <Card padding="none">
            <EmptyState compact title="Ответов пока нет" description="Задание в очереди раздачи — ответы появятся здесь." />
          </Card>
        }
      >
        {(data) => (
          <ul className="flex flex-col gap-3">
            {data.map((s) => (
              <li key={s.id}>
                <SubmissionCard sub={s} />
              </li>
            ))}
          </ul>
        )}
      </QueryState>
    </section>
  )
}

function SubmissionCard({ sub }: { sub: TaskSubmission }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [editing, setEditing] = useState(false)
  const [score, setScore] = useState<number | null>(sub.score ?? null)
  const [comment, setComment] = useState(sub.grader_comment ?? '')
  const grade = useMutation({
    mutationFn: (body: S['SubmissionGrade']) => api.post<TaskSubmission>(`/tasks/submissions/${sub.id}/grade`, body),
    onSuccess: (s) => {
      toast({ tone: 'success', title: `Оценка ${s.score} — ${SCORE_LABELS[s.score ?? 0]}`, description: 'Свежесть профиля кандидата обновлена.' })
      setEditing(false)
      upsertInList(qc, rk.submissions(s.task_id), s)
      void refreshRecruiter(qc, rk.submissions(s.task_id))
    },
    onError: (e) => toast({ tone: 'error', title: 'Не удалось оценить', description: getErrorMessage(e) }),
  })
  const st = SUBMISSION_STATUS[sub.status]
  const canGrade = sub.status === 'submitted' || (sub.status === 'graded' && editing)
  return (
    <Card padding="sm" className="flex flex-col gap-3" data-testid="submission">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {sub.candidate ? (
          <Pseudonym size="sm" code={pseudonymCodeOf(sub.candidate.pseudonym)} subtitle={sub.candidate.category_label ?? undefined} />
        ) : (
          <span>Кандидат</span>
        )}
        <span className="flex items-center gap-2">
          {sub.answer_kind && <Badge tone="neutral">{ANSWER_KIND_LABELS[sub.answer_kind]}</Badge>}
          <Badge tone={st.tone}>{st.label}</Badge>
        </span>
      </div>
      {sub.answer_text ? (
        <p className={cn('rounded-md bg-surface-muted p-3 text-sm whitespace-pre-wrap', sub.answer_kind === 'code' && 'font-mono text-[13px]')}>{sub.answer_text}</p>
      ) : (
        <p className="text-sm text-muted">
          {sub.status === 'expired' ? 'Кандидат не ответил в срок.' : `Ждём ответ до ${formatDate(sub.due_at)}`}
        </p>
      )}
      {sub.status === 'graded' && !editing && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <span>
            <b>
              Оценка {sub.score} из 3 — {SCORE_LABELS[sub.score ?? 0]}
            </b>
            {sub.grader_comment && <span className="text-muted"> · {sub.grader_comment}</span>}
          </span>
          <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>
            Изменить оценку
          </Button>
        </div>
      )}
      {canGrade && (
        <div className="flex flex-col gap-2 border-t border-line pt-3">
          <div role="radiogroup" aria-label="Оценка от 0 до 3" className="flex flex-wrap gap-1.5">
            {SCORE_LABELS.map((label, value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={score === value}
                onClick={() => setScore(value)}
                className={cn(
                  'h-9 rounded-md border px-3 text-sm font-semibold transition-colors',
                  score === value ? 'border-fsp-plum bg-fsp-plum text-on-primary' : 'border-line-strong bg-surface text-ink hover:border-fsp-lavender',
                )}
              >
                {value} · {label}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <Input
              aria-label="Комментарий к оценке"
              containerClassName="flex-1"
              placeholder="Комментарий (необязательно)"
              maxLength={1000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <Button disabled={score === null} loading={grade.isPending} onClick={() => score !== null && grade.mutate({ score, comment: comment.trim() || null })}>
              Оценить
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function CreateTaskModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (t: RegularTask) => void }) {
  if (!open) return null
  return <CreateTaskForm onClose={onClose} onCreated={onCreated} />
}

function CreateTaskForm({ onClose, onCreated }: { onClose: () => void; onCreated: (t: RegularTask) => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const categories = useCategories()
  const [title, setTitle] = useState('')
  const [statement, setStatement] = useState('')
  const [category, setCategory] = useState('')
  const [days, setDays] = useState('7')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const create = useMutation({
    mutationFn: (body: S['RegularTaskCreate']) => api.post<RegularTask>('/tasks', body),
    onSuccess: (t) => {
      toast({ tone: 'success', title: 'Задание создано', description: `Получат кандидаты категории ${t.category_label}.` })
      upsertInList(qc, rk.tasks, t)
      // Ответов у нового задания ещё нет — не ходим за пустым списком.
      if (!t.submissions_count) qc.setQueryData(rk.submissions(t.id), [])
      void refreshRecruiter(qc, rk.tasks)
      onCreated(t)
      onClose()
    },
    onError: (e) => {
      const fields = apiFieldErrors(e)
      if (Object.keys(fields).length) setErrors(fields)
      else toast({ tone: 'error', title: 'Не удалось создать', description: getErrorMessage(e) })
    },
  })
  function submit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (title.trim().length < 3) next.title = 'Название — не короче 3 символов'
    if (statement.trim().length < 10) next.statement = 'Условие — не короче 10 символов'
    if (!category) next.category = 'Выберите категорию'
    const d = Number(days)
    if (!Number.isInteger(d) || d < 1 || d > 30) next.deadline_days = 'От 1 до 30 дней'
    setErrors(next)
    if (Object.keys(next).length) return
    create.mutate({ title: title.trim(), statement: statement.trim(), category, deadline_days: d })
  }
  return (
    <Modal
      open
      onClose={onClose}
      title="Новое задание"
      description="Короткая задача на 15–30 минут: решить или предложить подход."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" form="task-form" loading={create.isPending}>
            Создать
          </Button>
        </>
      }
    >
      <form id="task-form" onSubmit={submit} noValidate className="flex flex-col gap-4">
        <Input label="Название" required value={title} onChange={(e) => setTitle(e.target.value)} error={errors.title} placeholder="Кэш для медленного API" />
        <Textarea
          label="Условие"
          required
          rows={4}
          maxLength={5000}
          value={statement}
          onChange={(e) => setStatement(e.target.value)}
          error={errors.statement}
          placeholder="Сервис отвечает 2 секунды. Как ускорить ответы без потери актуальности данных?"
        />
        <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
          <Select
            label="Категория"
            required
            placeholder="Выберите…"
            options={(categories.data ?? []).map((c) => ({ value: c.id, label: c.label }))}
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            error={errors.category}
          />
          <Input label="Срок, дней" type="number" min={1} max={30} value={days} onChange={(e) => setDays(e.target.value)} error={errors.deadline_days} />
        </div>
      </form>
    </Modal>
  )
}
