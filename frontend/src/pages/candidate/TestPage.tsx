import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useParams, useSearchParams } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { GRADE_LABELS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { APP_NAME } from '@/shared/config/env'
import { Button, Card, ProgressBar, Skeleton, Stepper, Tag, Timer, useToast } from '@/shared/ui'
import { invalidateCandidate, qk, type AnswerAck, type ItemView, type TestSessionState } from './api'
import { ItemAnswer, type AnswerDraft } from './components/ItemAnswer'
import { QueryView } from './components/QueryView'
import { ONBOARDING_STEPS } from './components/onboardingSteps'
import { isAnswerReady, normalizeAnswer } from './components/testAnswer'
import { ITEM_FORMAT_LABELS } from './labels'

/** Если бэкенд не прислал max_items — верхняя граница адаптивного теста. */
const DEFAULT_MAX_ITEMS = 20

/** Экран теста: задача, таймер, прогресс. Верно/неверно не показываем. */
export default function TestPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [params] = useSearchParams()
  const onboarding = params.get('onboarding') === '1'
  const q = useQuery({
    queryKey: qk.session(id),
    queryFn: () => api.get<TestSessionState>(`/testing/sessions/${id}`),
    enabled: Number.isInteger(id),
    staleTime: Infinity,
    gcTime: 0,
  })

  return (
    <>
      {onboarding && (
        <Card className="mb-5" padding="sm">
          <Stepper steps={ONBOARDING_STEPS} current={3} />
        </Card>
      )}
      <QueryView
        query={q}
        loading={
          <Card padding="lg">
            <Skeleton className="h-5 w-1/3" />
            <Skeleton className="mt-6 h-7 w-3/4" />
            <Skeleton className="mt-6 h-12 w-full" />
            <Skeleton className="mt-3 h-12 w-full" />
          </Card>
        }
        errorTitle="Не удалось открыть тест"
      >
        {(state) =>
          state.session.status !== 'in_progress' || !state.current_item ? (
            <Navigate to={`/candidate/test/${id}/result${onboarding ? '?onboarding=1' : ''}`} replace />
          ) : (
            <TestRunner key={state.session.id} state={state} onboarding={onboarding} />
          )
        }
      </QueryView>
    </>
  )
}

function TestRunner({ state, onboarding }: { state: TestSessionState; onboarding: boolean }) {
  const navigate = useNavigate()
  const client = useQueryClient()
  const { toast } = useToast()
  const session = state.session
  const [item, setItem] = useState<ItemView>(state.current_item!)
  const [number, setNumber] = useState(state.item_number)
  const [duration, setDuration] = useState(state.time_left_sec ?? state.current_item!.time_limit_sec)
  const [draft, setDraft] = useState<AnswerDraft>({})

  useEffect(() => {
    document.title = `Тест: задача ${number} · ${APP_NAME}`
  }, [number])

  const answer = useMutation({
    mutationFn: (payload: { instance_id: string; answer: ReturnType<typeof normalizeAnswer> }) =>
      api.post<AnswerAck>(`/testing/sessions/${session.id}/answers`, payload),
    onSuccess: (ack) => {
      if (ack.time_expired) toast({ tone: 'warning', title: 'Время на задачу вышло', description: 'Ответ засчитан как неверный.' })
      if (ack.finished || !ack.next_item) {
        void invalidateCandidate(client)
        navigate(`/candidate/test/${session.id}/result${onboarding ? '?onboarding=1' : ''}`, { replace: true })
        return
      }
      setItem(ack.next_item)
      setDuration(ack.next_item.time_limit_sec)
      setNumber(ack.answered + 1)
      setDraft({})
      window.scrollTo(0, 0)
    },
    onError: (err) => toast({ tone: 'error', title: 'Ответ не отправился', description: getErrorMessage(err) }),
  })

  function send(value: AnswerDraft) {
    if (answer.isPending) return
    answer.mutate({ instance_id: item.instance_id, answer: normalizeAnswer(item, value) })
  }

  function submit(e: FormEvent) {
    e.preventDefault()
    if (isAnswerReady(item, draft)) send(draft)
  }

  const ready = isAnswerReady(item, draft)

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm text-muted">Тест · {SPECIALIZATION_LABELS[session.specialization]}</p>
          <h1 className="text-xl font-bold">Задача {number}</h1>
        </div>
        <Timer key={item.instance_id} durationSec={duration} onExpire={() => send(draft)} paused={answer.isPending} />
      </div>
      <ProgressBar
        className="mb-5"
        value={number - 1}
        max={session.max_items ?? DEFAULT_MAX_ITEMS}
        label={`Отвечено ${number - 1} · не больше ${session.max_items ?? DEFAULT_MAX_ITEMS} задач`}
        showValue={false}
        tone="violet"
        size="sm"
      />

      <Card padding="lg">
        <form onSubmit={submit}>
          <div className="mb-4 flex flex-wrap gap-2">
            <Tag tone="violet">{item.topic_label}</Tag>
            <Tag tone="neutral">{ITEM_FORMAT_LABELS[item.format]}</Tag>
          </div>
          <p className="mb-5 text-lg leading-relaxed font-semibold whitespace-pre-line text-ink">{item.prompt}</p>
          <ItemAnswer item={item} value={draft} onChange={setDraft} disabled={answer.isPending} />
          <div className="mt-8 flex flex-col-reverse gap-3 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-[13px] text-muted">После отправки ответ изменить нельзя.</p>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Button variant="ghost" onClick={() => send({})} disabled={answer.isPending}>
                Не знаю
              </Button>
              <Button type="submit" size="lg" disabled={!ready} loading={answer.isPending} rightIcon={<Send className="size-4" aria-hidden />}>
                Ответить
              </Button>
            </div>
          </div>
        </form>
      </Card>
      <p className="mt-4 text-center text-[13px] text-muted">
        Заявленный грейд: {GRADE_LABELS[session.target_grade]}.{' '}
        <Link to="/candidate" className="font-medium text-fsp-plum hover:underline">
          Выйти
        </Link>{' '}
        — тест можно продолжить позже, таймер задачи не остановится.
      </p>
    </div>
  )
}
