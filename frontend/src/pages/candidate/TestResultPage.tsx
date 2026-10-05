import { useEffect, type ReactNode } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CircleCheck, Info, PartyPopper, TrendingDown, TrendingUp, TriangleAlert } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import { GRADE_LABELS, GRADES, type Grade } from '@/shared/config/dictionaries'
import { formatDate, formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, EmptyState, PageHeader, ProgressBar, Stepper, useToast } from '@/shared/ui'
import { qk, useStartTest, type TestResult } from './api'
import { QueryView } from './components/QueryView'
import { ThetaScale } from './components/ThetaScale'
import { ONBOARDING_STEPS, writeOnboarding } from './components/onboardingSteps'
import { TOPIC_LEVEL, formatTheta } from './labels'

const linkBtn =
  'inline-flex h-10 items-center justify-center gap-1.5 rounded-md px-4 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]'

/** Результат теста: категория, уровень с интервалом, разбор по темам, что дальше. */
export default function TestResultPage() {
  const { sessionId } = useParams()
  const id = Number(sessionId)
  const [params] = useSearchParams()
  const onboarding = params.get('onboarding') === '1'
  const q = useQuery({
    queryKey: qk.result(id),
    queryFn: () => api.get<TestResult>(`/testing/sessions/${id}/result`),
    enabled: Number.isInteger(id),
  })

  useEffect(() => {
    if (onboarding && q.isSuccess) writeOnboarding(null)
  }, [onboarding, q.isSuccess])

  const notFinished = isApiError(q.error) && q.error.code === 'session_not_finished'

  return (
    <>
      {onboarding && (
        <Card className="mb-5" padding="sm">
          <Stepper steps={ONBOARDING_STEPS} current={4} />
        </Card>
      )}
      <PageHeader title="Результат теста" back={onboarding ? undefined : { to: '/candidate/grade', label: 'Категория и грейд' }} />
      {notFinished ? (
        <Card padding="none">
          <EmptyState
            title="Тест ещё не завершён"
            description="Результат появится сразу после последней задачи."
            action={
              <Link to={`/candidate/test/${id}${onboarding ? '?onboarding=1' : ''}`} className={`${linkBtn} bg-primary text-white hover:bg-primary-hover`}>
                Продолжить тест
              </Link>
            }
          />
        </Card>
      ) : (
        <QueryView query={q} errorTitle="Не удалось загрузить результат">
          {(r) => <ResultView result={r} onboarding={onboarding} />}
        </QueryView>
      )}
    </>
  )
}

function ResultView({ result: r, onboarding }: { result: TestResult; onboarding: boolean }) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const start = useStartTest()
  const plusMinus = Math.abs(r.ci_high - r.theta)
  const rec = r.recommendation
  const recGrade: Grade | null =
    rec.action === 'offer_lower'
      ? (GRADES[GRADES.indexOf(r.target_grade) - 1] ?? null)
      : rec.action === 'offer_higher'
        ? (GRADES[GRADES.indexOf(r.target_grade) + 1] ?? null)
        : null
  const canStartNow = recGrade && !rec.available_at

  return (
    <div className="grid gap-5">
      {/* Категория */}
      <Card padding="lg" className={r.passed ? 'border-success/30' : 'border-warning/30'}>
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {onboarding && r.passed && (
              <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-success">
                <PartyPopper className="size-4" aria-hidden /> Знакомство завершено
              </p>
            )}
            <p className="text-sm font-semibold text-muted">{r.passed ? 'Ваша категория' : 'Уровень по тесту соответствует'}</p>
            <p className="mt-1 text-4xl leading-tight font-bold text-fsp-night sm:text-5xl">{r.category_label}</p>
            <p className="mt-2 text-sm text-muted">
              Решено задач: {r.items_answered} · {formatDateTime(r.finished_at)}
            </p>
          </div>
          {r.passed ? (
            <Badge tone="success" icon={<CircleCheck />} className="self-start px-3 py-1 text-sm">
              Грейд {GRADE_LABELS[r.target_grade]} подтверждён
            </Badge>
          ) : (
            <Badge tone="warning" icon={<TriangleAlert />} className="self-start px-3 py-1 text-sm">
              Грейд {GRADE_LABELS[r.target_grade]} не подтверждён
            </Badge>
          )}
        </div>
        {!r.passed && (
          <p className="mt-4 rounded-md bg-warning-soft px-3 py-2 text-sm text-warning">
            Категория не меняется принудительно: прежний грейд (если был) остаётся. Чтобы получить категорию, пройдите тест
            на грейд ниже.
          </p>
        )}
      </Card>

      {/* Уровень */}
      <Card>
        <CardHeader title="Ваш уровень" description="Оценка по модели IRT: чем выше число, тем сложнее задачи вы решаете." />
        <p className="text-2xl font-bold text-ink tabular-nums">
          {formatTheta(r.theta)} ± {formatTheta(plusMinus)}{' '}
          <ArrowRight className="inline size-6 align-[-3px] text-subtle" aria-hidden /> {GRADE_LABELS[r.result_grade]}
        </p>
        <p className="mt-1 text-[15px] text-muted">
          С вероятностью 95 % ваш уровень между {formatTheta(r.ci_low)} и {formatTheta(r.ci_high)}. Пороги: Junior от −1, Middle от 0,
          Senior от 1.
        </p>
        <ThetaScale className="mt-4" theta={r.theta} ciLow={r.ci_low} ciHigh={r.ci_high} />
      </Card>

      {/* Темы */}
      <Card>
        <CardHeader title="Разбор по темам" description="Правильные ответы не показываем — так задачи не утекают и тест остаётся честным." />
        <div className="grid gap-4">
          {r.topic_scores.map((t) => (
            <div key={t.topic}>
              <div className="mb-1.5 flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-medium text-ink">{t.label}</span>
                <Badge tone={TOPIC_LEVEL[t.level].tone}>{TOPIC_LEVEL[t.level].label}</Badge>
              </div>
              <ProgressBar value={Math.round(t.score * 100)} tone={TOPIC_LEVEL[t.level].bar} showValue={false} size="sm" />
            </div>
          ))}
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-2">
          <TopicList title="Сильные стороны" icon={<TrendingUp className="size-4 text-success" aria-hidden />} items={r.strong_topics} empty="Явно сильных тем нет — ровный результат" />
          <TopicList title="Что подтянуть" icon={<TrendingDown className="size-4 text-warning" aria-hidden />} items={r.weak_topics} empty="Слабых тем не нашли" />
        </div>
      </Card>

      {/* Что дальше */}
      <Card className="border-fsp-lavender bg-violet-soft/40">
        <div className="flex gap-3">
          <Info className="mt-0.5 size-5 shrink-0 text-fsp-plum" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="font-semibold text-ink">Что дальше</p>
            <p className="mt-1 text-[15px] text-ink">{rec.message}</p>
            {rec.available_at && recGrade && (
              <p className="mt-1 text-sm text-muted">
                Тест на {GRADE_LABELS[recGrade]} станет доступен {formatDate(rec.available_at)}.
              </p>
            )}
            <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
              {canStartNow && (
                <Button
                  loading={start.isPending}
                  onClick={() =>
                    start.mutate(
                      { specialization: r.specialization, target_grade: recGrade, kind: rec.action === 'offer_lower' ? 'lower' : 'higher' },
                      {
                        onSuccess: (s) => navigate(`/candidate/test/${s.session.id}`),
                        onError: (err) => toast({ tone: 'error', title: 'Тест не запустился', description: getErrorMessage(err) }),
                      },
                    )
                  }
                >
                  Пройти тест на {GRADE_LABELS[recGrade]}
                </Button>
              )}
              <Link to="/candidate" className={`${linkBtn} ${canStartNow ? 'border border-line-strong bg-surface text-fsp-plum hover:bg-violet-soft' : 'bg-primary text-white hover:bg-primary-hover'}`}>
                На главную
              </Link>
              <Link to="/candidate/invitations" className={`${linkBtn} text-fsp-plum hover:bg-violet-soft`}>
                Приглашения
              </Link>
              <Link to="/candidate/grade" className={`${linkBtn} text-fsp-plum hover:bg-violet-soft`}>
                Категория и грейд
              </Link>
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}

function TopicList({ title, icon, items, empty }: { title: string; icon: ReactNode; items: string[]; empty: string }) {
  return (
    <div className="rounded-md border border-line p-4">
      <p className="flex items-center gap-2 text-sm font-semibold text-ink">
        {icon}
        {title}
      </p>
      {items.length ? (
        <ul className="mt-2 grid gap-1 text-[15px] text-ink">
          {items.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      )}
    </div>
  )
}
