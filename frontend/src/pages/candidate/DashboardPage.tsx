import { Link } from 'react-router'
import { ArrowRight, Award, ClipboardList, GraduationCap, Lightbulb, Mail, Rocket, UserRoundPen } from 'lucide-react'
import { Badge, Card, CardHeader, EmptyState, ProgressBar, Skeleton, StatusPill } from '@/shared/ui'
import { formatDate, formatSalaryRange, plural } from '@/shared/lib/format'
import { useDashboard } from './api'
import { QueryView } from './components/QueryView'
import { FspLinkButton } from './components/FspLinkButton'
import { formatTheta } from './labels'
import { PageHeader } from '@/shared/ui'

const linkCls = 'inline-flex items-center gap-1 text-sm font-semibold text-fsp-plum hover:underline'

export default function CandidateDashboardPage() {
  const q = useDashboard()
  const firstName = q.data?.full_name.split(' ')[0]
  return (
    <>
      <PageHeader title={firstName ? `Здравствуйте, ${firstName}` : 'Главная'} description="Категория, приглашения и задания — всё в одном месте." />
      <QueryView
        query={q}
        loading={
          <div className="grid gap-4 md:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Card key={i}>
                <Skeleton className="h-4 w-1/3" />
                <Skeleton className="mt-4 h-8 w-2/3" />
                <Skeleton className="mt-3 h-3 w-1/2" />
              </Card>
            ))}
          </div>
        }
      >
        {(d) => (
          <div className="grid gap-4">
            {!d.onboarding_completed && (
              <Card className="border-0 bg-fsp-night text-white" padding="lg">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex gap-4">
                    <span className="flex size-12 shrink-0 items-center justify-center rounded-lg bg-white/10 text-fsp-blush">
                      <Rocket className="size-6" aria-hidden />
                    </span>
                    <div>
                      <h2 className="text-xl font-bold text-white">Получите категорию — и работодатели начнут писать</h2>
                      <p className="mt-1 text-on-nav-muted">Профиль, короткий опрос и адаптивный тест — около 25 минут.</p>
                    </div>
                  </div>
                  <Link
                    to="/candidate/onboarding"
                    className="inline-flex h-12 shrink-0 items-center justify-center rounded-md bg-primary px-6 font-semibold text-white hover:bg-primary-hover"
                  >
                    Начать
                  </Link>
                </div>
              </Card>
            )}

            <div className="grid gap-4 md:grid-cols-2">
              {/* Категория */}
              <Card>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <GraduationCap className="size-5 text-fsp-plum" aria-hidden /> Категория
                    </span>
                  }
                  actions={
                    <Link to="/candidate/grade" className={linkCls}>
                      Подробнее <ArrowRight className="size-4" aria-hidden />
                    </Link>
                  }
                />
                {d.category_label ? (
                  <>
                    <p className="text-3xl font-bold text-fsp-night">{d.category_label}</p>
                    {typeof d.theta === 'number' && (
                      <p className="mt-1 text-sm text-muted">Уровень по тесту: {formatTheta(d.theta)}</p>
                    )}
                  </>
                ) : (
                  <p className="text-[15px] text-muted">Пока нет — пройдите тест, чтобы попасть в выдачу работодателям.</p>
                )}
              </Card>

              {/* Приглашения */}
              <Card>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <Mail className="size-5 text-fsp-plum" aria-hidden /> Приглашения
                      {d.new_invitations_count > 0 && <Badge tone="accent">{d.new_invitations_count} новых</Badge>}
                    </span>
                  }
                  actions={
                    <Link to="/candidate/invitations" className={linkCls}>
                      Все <ArrowRight className="size-4" aria-hidden />
                    </Link>
                  }
                />
                {d.recent_invitations.length ? (
                  <ul className="-mx-2 grid gap-1">
                    {d.recent_invitations.map((inv) => (
                      <li key={inv.id}>
                        <Link
                          to={`/candidate/invitations/${inv.id}`}
                          className="flex items-center justify-between gap-3 rounded-md px-2 py-2 hover:bg-violet-soft"
                        >
                          <span className="min-w-0">
                            <span className="block truncate font-semibold text-ink">{inv.company_name}</span>
                            <span className="block text-sm text-muted tabular-nums">{formatSalaryRange(inv.salary_from, inv.salary_to)}</span>
                          </span>
                          <StatusPill status={inv.status} />
                        </Link>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <EmptyState compact title="Приглашений пока нет" description="Они появятся, когда работодатель найдёт вас по категории." />
                )}
              </Card>

              {/* Задание */}
              <Card>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <ClipboardList className="size-5 text-fsp-plum" aria-hidden /> Задание недели
                    </span>
                  }
                  actions={
                    <Link to="/candidate/tasks" className={linkCls}>
                      Все задания <ArrowRight className="size-4" aria-hidden />
                    </Link>
                  }
                />
                {d.active_task ? (
                  <div>
                    <p className="text-lg font-semibold text-ink">{d.active_task.title}</p>
                    <p className="mt-1 text-sm text-muted">Ответить до {formatDate(d.active_task.due_at)}</p>
                    <Link
                      to="/candidate/tasks"
                      className="mt-4 inline-flex h-10 items-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
                    >
                      Ответить
                    </Link>
                  </div>
                ) : (
                  <p className="text-[15px] text-muted">Активного задания нет. Новое придёт в течение недели.</p>
                )}
              </Card>

              {/* Профиль */}
              <Card>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <UserRoundPen className="size-5 text-fsp-plum" aria-hidden /> Профиль
                    </span>
                  }
                  actions={
                    <Link to="/candidate/profile" className={linkCls}>
                      Редактировать <ArrowRight className="size-4" aria-hidden />
                    </Link>
                  }
                />
                <ProgressBar
                  label="Заполненность"
                  value={d.profile_completeness}
                  tone={d.profile_completeness >= 80 ? 'success' : 'primary'}
                />
                <p className="mt-2 text-sm text-muted">
                  {d.profile_completeness >= 100
                    ? 'Профиль заполнен полностью.'
                    : 'Чем полнее профиль, тем выше вы в подборке работодателя.'}
                </p>
              </Card>
            </div>

            {!d.fsp_linked && (
              <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex gap-3">
                  <Award className="mt-0.5 size-6 shrink-0 text-fsp-plum" aria-hidden />
                  <div>
                    <p className="font-semibold text-ink">Участвовали в соревнованиях ФСП?</p>
                    <p className="text-sm text-muted">
                      Привяжите ФСП ID — достижения появятся с отметкой «подтверждено ФСП». Нет истории — это не минус.
                    </p>
                  </div>
                </div>
                <FspLinkButton variant="secondary" returnTo="/candidate/fsp" />
              </Card>
            )}

            {d.hints.length > 0 && (
              <Card>
                <CardHeader
                  title={
                    <span className="inline-flex items-center gap-2">
                      <Lightbulb className="size-5 text-fsp-plum" aria-hidden /> Что улучшить
                    </span>
                  }
                  description={`${d.hints.length} ${plural(d.hints.length, ['совет', 'совета', 'советов'])}`}
                />
                <ul className="grid gap-2">
                  {d.hints.map((h) => (
                    <li key={h} className="flex gap-2 text-[15px] text-ink">
                      <span className="mt-2 size-1.5 shrink-0 rounded-full bg-primary" aria-hidden />
                      {h}
                    </li>
                  ))}
                </ul>
              </Card>
            )}
          </div>
        )}
      </QueryView>
    </>
  )
}
