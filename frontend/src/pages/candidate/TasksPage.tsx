import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { CalendarClock, ClipboardList, Sparkles } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import { formatDate, plural } from '@/shared/lib/format'
import { cn } from '@/shared/lib/cn'
import { Badge, Button, Card, EmptyState, PageHeader, ProgressBar, Tabs, Textarea, useToast } from '@/shared/ui'
import { qk, useTaskInbox, type S, type TaskSubmission } from './api'
import { QueryView } from './components/QueryView'
import { ANSWER_KIND_LABELS, SUBMISSION_STATUS } from './labels'

export default function TasksPage() {
  const q = useTaskInbox()
  return (
    <>
      <PageHeader
        title="Задания"
        description="Раз в неделю — короткая задача от работодателей вашей категории. Ответы держат профиль «свежим» и поднимают вас в подборке."
      />
      <QueryView query={q}>
        {(inbox) => (
          <div className="grid gap-5">
            <Card>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-6">
                <div className="flex items-center gap-3 sm:w-64">
                  <Sparkles className="size-6 shrink-0 text-fsp-plum" aria-hidden />
                  <div>
                    <p className="font-semibold text-ink">Свежесть профиля</p>
                    <p className="text-[13px] text-muted">Входит в ранжирование выдачи</p>
                  </div>
                </div>
                <ProgressBar className="flex-1" value={Math.round(inbox.freshness * 100)} tone={inbox.freshness >= 0.6 ? 'success' : 'warning'} />
              </div>
            </Card>
            {inbox.active ? (
              <ActiveTask task={inbox.active} />
            ) : (
              <Card padding="none">
                <EmptyState
                  icon={<ClipboardList aria-hidden />}
                  title="Активного задания нет"
                  description="Новое придёт в течение недели — мы пришлём уведомление."
                />
              </Card>
            )}
            <div>
              <h2 className="mb-3 text-lg font-semibold">История</h2>
              {inbox.history.length ? (
                <ul className="grid gap-3">
                  {inbox.history.map((t) => (
                    <li key={t.id}>
                      <HistoryItem task={t} />
                    </li>
                  ))}
                </ul>
              ) : (
                <Card padding="none">
                  <EmptyState compact title="Пока пусто" description="Здесь появятся ваши ответы и оценки." />
                </Card>
              )}
            </div>
          </div>
        )}
      </QueryView>
    </>
  )
}

function ActiveTask({ task }: { task: TaskSubmission }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const [kind, setKind] = useState<S['AnswerKind']>('approach')
  const [text, setText] = useState('')
  const [now] = useState(() => Date.now())
  const daysLeft = Math.max(0, Math.ceil((new Date(task.due_at).getTime() - now) / 86_400_000))
  const submit = useMutation({
    mutationFn: () => api.post<TaskSubmission>(`/tasks/submissions/${task.id}/answer`, { answer_kind: kind, answer_text: text.trim() }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: qk.tasks })
      void client.invalidateQueries({ queryKey: qk.dashboard })
      toast({ tone: 'success', title: 'Ответ отправлен', description: 'Работодатель оценит его по шкале 0–3.' })
    },
  })
  const fieldError = isApiError(submit.error) && submit.error.code === 'validation_error' ? getErrorMessage(submit.error) : undefined

  return (
    <Card padding="lg" className="border-fsp-lavender">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">Задание недели</Badge>
        <span className="inline-flex items-center gap-1 text-sm text-warning">
          <CalendarClock className="size-4" aria-hidden /> До {formatDate(task.due_at)} · {daysLeft} {plural(daysLeft, ['день', 'дня', 'дней'])}
        </span>
      </div>
      <h2 className="mt-3 text-xl font-bold">{task.task_title}</h2>
      <p className="text-sm text-muted">от {task.company_name}</p>
      <p className="mt-4 rounded-md bg-surface-muted p-4 text-[15px] leading-relaxed text-ink">{task.statement}</p>
      <form
        className="mt-5 grid gap-3"
        onSubmit={(e) => {
          e.preventDefault()
          submit.mutate()
        }}
      >
        <div>
          <p className="mb-1.5 text-sm font-medium text-ink">Как ответите</p>
          <Tabs
            variant="pills"
            value={kind}
            onChange={(v) => setKind(v as S['AnswerKind'])}
            ariaLabel="Тип ответа"
            items={(Object.keys(ANSWER_KIND_LABELS) as S['AnswerKind'][]).map((k) => ({ id: k, label: ANSWER_KIND_LABELS[k] }))}
          />
        </div>
        <Textarea
          label="Ответ"
          rows={kind === 'code' ? 8 : 5}
          value={text}
          onChange={(e) => setText(e.target.value)}
          className={cn(kind === 'code' && 'font-mono text-[14px]')}
          spellCheck={kind !== 'code'}
          placeholder={kind === 'code' ? '// ваш код' : kind === 'approach' ? 'Опишите подход по шагам' : 'Ваш ответ'}
          hint="Решать полностью не обязательно — достаточно подхода. Оценка 0–3."
          error={fieldError}
        />
        {submit.isError && !fieldError && (
          <p className="text-sm text-danger" role="alert">
            {getErrorMessage(submit.error)}
          </p>
        )}
        <div className="flex justify-end">
          <Button type="submit" size="lg" loading={submit.isPending} disabled={!text.trim()}>
            Отправить ответ
          </Button>
        </div>
      </form>
    </Card>
  )
}

function ScoreDots({ score }: { score: number }) {
  return (
    <span className="inline-flex items-center gap-1" aria-label={`Оценка ${score} из 3`}>
      {[1, 2, 3].map((i) => (
        <span key={i} className={cn('size-2.5 rounded-full', i <= score ? 'bg-primary' : 'bg-line')} aria-hidden />
      ))}
      <span className="ml-1 text-sm font-semibold text-ink tabular-nums">{score}/3</span>
    </span>
  )
}

function HistoryItem({ task }: { task: TaskSubmission }) {
  const st = SUBMISSION_STATUS[task.status]
  return (
    <Card>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <p className="font-semibold text-ink">{task.task_title}</p>
          <p className="text-sm text-muted">
            {task.company_name} · {formatDate(task.submitted_at ?? task.assigned_at)}
          </p>
        </div>
        <div className="flex items-center gap-3">
          {typeof task.score === 'number' && <ScoreDots score={task.score} />}
          <Badge tone={st.tone}>{st.label}</Badge>
        </div>
      </div>
      {task.grader_comment && <p className="mt-2 text-sm text-ink">Комментарий: «{task.grader_comment}»</p>}
      {task.answer_text && (
        <details className="mt-3 group">
          <summary className="cursor-pointer text-sm font-medium text-fsp-plum">
            Мой ответ{task.answer_kind ? ` · ${ANSWER_KIND_LABELS[task.answer_kind].toLowerCase()}` : ''}
          </summary>
          <pre className={cn('mt-2 rounded-md bg-surface-muted p-3 text-sm whitespace-pre-wrap text-ink', task.answer_kind === 'code' ? 'font-mono' : 'font-sans')}>
            {task.answer_text}
          </pre>
        </details>
      )}
    </Card>
  )
}
