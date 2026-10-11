import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router'
import { ArrowUp, CalendarClock, ClipboardCheck, ClipboardX, GraduationCap, Info, MessageSquareText, Sparkles, TrendingDown, TrendingUp } from 'lucide-react'
import { getErrorMessage, isApiError } from '@/shared/api'
import { GRADE_LABELS, GRADES, SPECIALIZATION_LABELS, type Grade } from '@/shared/config/dictionaries'
import { formatDate } from '@/shared/lib/format'
import { cn } from '@/shared/lib/cn'
import { Badge, Button, Card, CardHeader, EmptyState, Modal, PageHeader, Table, useToast, type TableColumn } from '@/shared/ui'
import { useGradeStatus, useStartTest, type GradeStatus, type S, type TestSession } from './api'
import { QueryView } from './components/QueryView'
import { GradeConfirmedBadge, UnconfirmedGrade } from './components/GradeStatus'
import { ThetaScale } from './components/ThetaScale'
import { GRADE_EVENT_LABELS, TEST_KIND_LABELS, formatTheta, gradeTestLabel, ruThetaText } from './labels'

export default function GradePage() {
  const q = useGradeStatus()
  return (
    <>
      <PageHeader title="Категория и грейд" description="Текущий статус, история тестов и правила пересдачи." />
      <QueryView query={q}>{(g) => <GradeView g={g} />}</QueryView>
    </>
  )
}

const EVENT_ICON: Record<S['GradeEventType'], typeof Sparkles> = {
  survey: MessageSquareText,
  test_passed: ClipboardCheck,
  test_failed: ClipboardX,
  grade_changed: GraduationCap,
  offer_lower: TrendingDown,
  offer_higher: TrendingUp,
}

const testColumns: TableColumn<TestSession>[] = [
  { key: 'started_at', header: 'Дата', render: (s) => formatDate(s.started_at), sortable: true },
  { key: 'kind', header: 'Тест', render: (s) => TEST_KIND_LABELS[s.kind], hideOnMobile: true },
  { key: 'target_grade', header: 'Заявлен', render: (s) => GRADE_LABELS[s.target_grade] },
  {
    key: 'result',
    header: 'Итог',
    render: (s) =>
      s.status === 'in_progress' ? (
        <Badge tone="info">Идёт</Badge>
      ) : s.status === 'abandoned' ? (
        <Badge>Прерван</Badge>
      ) : s.passed ? (
        <Badge tone="success">Подтверждён</Badge>
      ) : (
        <Badge tone="warning">Не подтверждён</Badge>
      ),
  },
  { key: 'theta', header: 'Уровень', align: 'right', render: (s) => (typeof s.theta === 'number' ? formatTheta(s.theta) : '—'), hideOnMobile: true },
  {
    key: 'link',
    header: '',
    align: 'right',
    render: (s) =>
      s.status === 'in_progress' ? (
        <Link to={`/candidate/test/${s.id}`} className="font-semibold text-primary hover:underline">
          Продолжить
        </Link>
      ) : s.status === 'finished' ? (
        <Link to={`/candidate/test/${s.id}/result`} className="font-semibold text-fsp-plum hover:underline">
          Результат
        </Link>
      ) : null,
  },
]

function GradeHistory({ g }: { g: GradeStatus }) {
  return (
    <Card>
      <CardHeader title="История" />
      {g.history.length ? (
        <ol className="relative grid gap-4 border-l-2 border-line pl-6">
          {g.history.map((h) => {
            const Icon = EVENT_ICON[h.event]
            return (
              <li key={h.id} className="relative">
                <span className="absolute top-0 -left-[37px] flex size-6 items-center justify-center rounded-full border-2 border-white bg-violet-soft text-fsp-plum">
                  <Icon className="size-3.5" aria-hidden />
                </span>
                <p className="text-sm font-semibold text-ink">{GRADE_EVENT_LABELS[h.event]}</p>
                {h.comment && <p className="text-[15px] text-ink">{ruThetaText(h.comment)}</p>}
                <p className="text-[13px] text-muted">{formatDate(h.at)}</p>
              </li>
            )
          })}
        </ol>
      ) : (
        <EmptyState compact title="Событий пока нет" />
      )}
    </Card>
  )
}

function GradeView({ g }: { g: GradeStatus }) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const start = useStartTest()
  const [confirm, setConfirm] = useState<{ kind: 'lower' | 'higher'; grade: Grade } | null>(null)
  const idx = g.grade ? GRADES.indexOf(g.grade) : -1
  // Соседние грейды: бэкенд присылает их в lower/higher вместе с причиной, почему тест недоступен.
  const higher = g.higher?.target_grade ?? (idx >= 0 && idx < GRADES.length - 1 ? GRADES[idx + 1] : null)

  if ((!g.grade || !g.specialization) && g.grade_status === 'unconfirmed' && g.declared_grade) {
    return (
      <div className="grid grid-cols-1 gap-5">
        <Card padding="lg">
          <p className="mb-1 text-sm font-semibold text-muted">Заявленная категория</p>
          <UnconfirmedGrade specialization={g.declared_specialization} grade={g.declared_grade} />
        </Card>
        <GradeHistory g={g} />
        <div>
          <h2 className="mb-3 text-lg font-semibold">Тесты</h2>
          <Table mobileCards columns={testColumns} rows={g.tests} rowKey={(s) => s.id} empty={<EmptyState compact title="Тестов пока не было" />} caption="Мои тесты" />
        </div>
      </div>
    )
  }

  if (!g.grade || !g.specialization) {
    return (
      <Card padding="none">
        <EmptyState
          icon={<GraduationCap aria-hidden />}
          title="Категории пока нет"
          description="Пройдите опрос и адаптивный тест — категория появится сразу после теста."
          action={
            <Link to="/candidate/onboarding" className="inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover">
              Пройти тест
            </Link>
          }
        />
      </Card>
    )
  }


  const inProgress = g.tests.find((s) => s.status === 'in_progress')

  return (
    <div className="grid grid-cols-1 gap-5">
      <Card padding="lg">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-muted">Текущая категория</p>
            <p className="mt-1 text-4xl font-bold text-fsp-night">{g.category_label}</p>
            {g.grade_status === 'confirmed' && <GradeConfirmedBadge at={g.grade_confirmed_at} className="mt-2" />}
            <p className="mt-2 text-sm text-muted">
              {g.grade_changed_at ? `Присвоена ${formatDate(g.grade_changed_at)}` : 'Присвоена по первому тесту'}
              {typeof g.theta === 'number' && ` · уровень ${formatTheta(g.theta)}`}
            </p>
          </div>
          <Badge tone="violet" className="self-start px-3 py-1 text-sm">
            {SPECIALIZATION_LABELS[g.specialization]}
          </Badge>
        </div>
        {typeof g.theta === 'number' && <ThetaScale className="mt-5" theta={g.theta} />}
      </Card>

      <Card>
        <CardHeader title="Пересдача" description="Хотите грейд выше — пройдите тест на уровень выше." />
        {inProgress && (
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-md border border-primary/30 bg-primary-soft p-3 text-sm" data-testid="test-in-progress">
            <span>
              Начат {gradeTestLabel(inProgress.target_grade)}, ответов: {inProgress.items_answered}. Новый можно начать после него.
            </span>
            <Link to={`/candidate/test/${inProgress.id}`} className="inline-flex h-9 items-center rounded-md bg-primary px-4 font-semibold text-white hover:bg-primary-hover">
              Продолжить тест
            </Link>
          </div>
        )}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <RetakeOption
            icon={<ArrowUp className="size-5" aria-hidden />}
            title={higher ? gradeTestLabel(higher, true) : 'Грейд выше'}
            unavailableText={higher ? undefined : 'Senior — максимальный грейд'}
            can={g.can_test_higher}
            availableAt={g.higher_available_at}
            reason={g.higher?.allowed === false ? g.higher.reason : undefined}
            onStart={() => higher && setConfirm({ kind: 'higher', grade: higher })}
          />
        </div>
        <div className="mt-4 flex gap-3 rounded-md bg-surface-muted p-3 text-sm text-ink">
          <Info className="mt-0.5 size-4 shrink-0 text-fsp-plum" aria-hidden />
          <ul className="grid gap-1">
            <li>Сменить грейд можно не чаще раза в {g.grade_change_cooldown_days ?? 90} дней.</li>
            <li>Повторить неудачную попытку на тот же грейд — через {g.retry_cooldown_days ?? 30} дней.</li>
            <li>Принудительно грейд не понижаем: не подтвердили новый — остаётся прежний.</li>
          </ul>
        </div>
      </Card>

      <GradeHistory g={g} />

      <div>
        <h2 className="mb-3 text-lg font-semibold">Тесты</h2>
        <Table mobileCards columns={testColumns} rows={g.tests} rowKey={(s) => s.id} empty={<EmptyState compact title="Тестов пока не было" />} caption="Мои тесты" />
      </div>

      <Modal
        open={!!confirm}
        onClose={() => setConfirm(null)}
        size="sm"
        title={confirm ? gradeTestLabel(confirm.grade, true) : ''}
        description="До 20 задач, время на каждую ограничено."
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Отмена
            </Button>
            <Button
              loading={start.isPending}
              onClick={() =>
                confirm &&
                start.mutate(
                  { specialization: g.specialization!, target_grade: confirm.grade, kind: confirm.kind },
                  {
                    onSuccess: (s) => navigate(`/candidate/test/${s.session.id}`),
                    onError: (err) => {
                      setConfirm(null)
                      const running = runningTestId(err)
                      if (running) {
                        toast({ title: 'У вас есть начатый тест', description: 'Открываем его — закончите, потом можно начать новый.' })
                        navigate(`/candidate/test/${running}`)
                      } else toast({ tone: 'error', title: 'Тест не запустился', description: getErrorMessage(err) })
                    },
                  },
                )
              }
            >
              Начать
            </Button>
          </>
        }
      >
        <p className="text-[15px] text-ink">
          Подтвердите уровень — категория сменится на «{SPECIALIZATION_LABELS[g.specialization]} · {confirm ? GRADE_LABELS[confirm.grade] : ''}». Не
          подтвердите — останется текущая, повторить можно через {g.retry_cooldown_days ?? 30} дней.
        </p>
      </Modal>
    </div>
  )
}

function RetakeOption({
  icon,
  title,
  can,
  availableAt,
  unavailableText,
  reason,
  onStart,
}: {
  icon: ReactNode
  title: string
  can: boolean
  availableAt: string | null
  unavailableText?: string
  /** Почему тест недоступен — текст правила от бэкенда. */
  reason?: string
  onStart: () => void
}) {
  return (
    <div className={cn('flex flex-col gap-3 rounded-lg border p-4', can ? 'border-line' : 'border-line bg-surface-muted')}>
      <div className="flex items-center gap-2 font-semibold text-ink">
        <span className="flex size-8 items-center justify-center rounded-md bg-violet-soft text-fsp-plum">{icon}</span>
        {title}
      </div>
      {unavailableText ? (
        <p className="text-sm text-muted">{unavailableText}</p>
      ) : (
        <>
          <Button variant="secondary" disabled={!can} onClick={onStart} className="self-start">
            {can ? 'Пройти тест' : 'Пока недоступно'}
          </Button>
          {!can && availableAt && (
            <p className="inline-flex items-center gap-1.5 text-sm text-muted">
              <CalendarClock className="size-4" aria-hidden /> Станет доступно {formatDate(availableAt)}
            </p>
          )}
          {!can && reason && <p className="text-[13px] text-muted">{reason}</p>}
        </>
      )}
    </div>
  )
}

/** 409 session_in_progress: id уже начатого теста — его открываем вместо ошибки. */
function runningTestId(err: unknown): number | null {
  return isApiError(err) && err.code === 'session_in_progress' && err.details.session_id ? Number(err.details.session_id) : null
}
