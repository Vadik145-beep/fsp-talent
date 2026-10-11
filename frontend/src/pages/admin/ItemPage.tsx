import { useState } from 'react'
import { useParams } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Archive, CheckCircle2, Shuffle, ShieldAlert } from 'lucide-react'
import { api, isApiError } from '@/shared/api'
import { GRADE_LABELS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { formatDate } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, ErrorState, PageHeader, SkeletonCard, SkeletonText } from '@/shared/ui'
import { useAdminMutation, type ItemDetail, type ItemStatus } from './api'
import { ConfirmModal, ItemStatusBadge, LeakBadge, StatTile } from './components/common'
import { RecalibrateButton } from './components/RecalibrateButton'
import { VariantPreview } from './components/VariantPreview'
import { ITEM_FORMAT_LABELS, ITEM_STATUS_HINTS, num, pct } from './labels'

/** P(верно) по модели 2PL для уровня θ. */
const p2pl = (theta: number, a: number, b: number) => 1 / (1 + Math.exp(-a * (theta - b)))

export default function AdminItemPage() {
  const { id } = useParams()
  const [confirm, setConfirm] = useState<'retire' | 'approve' | null>(null)
  const [acted, setActed] = useState<{ id: number; status: ItemStatus } | null>(null)
  const q = useQuery({ queryKey: ['admin', 'item', id], queryFn: () => api.get<ItemDetail>(`/admin/items/${id}`) })

  const retire = useAdminMutation(() => api.post<ItemDetail>(`/admin/items/${id}/retire`), {
    success: 'Шаблон выведен из оборота',
    onSuccess: (r) => (setConfirm(null), setActed({ id: r.id, status: r.status })),
  })
  const approve = useAdminMutation(() => api.post<ItemDetail>(`/admin/items/${id}/approve`), {
    success: 'Черновик одобрен: шаблон в пилоте',
    onSuccess: (r) => (setConfirm(null), setActed({ id: r.id, status: r.status })),
  })

  if (q.isPending) {
    return (
      <>
        <PageHeader title="Шаблон задачи" back={{ to: '/admin/items', label: 'Банк задач' }} />
        <SkeletonCard />
        <div className="mt-4 grid gap-4 lg:grid-cols-3">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </>
    )
  }
  if (q.isError) {
    const missing = isApiError(q.error) && q.error.status === 404
    return (
      <>
        <PageHeader title="Шаблон задачи" back={{ to: '/admin/items', label: 'Банк задач' }} />
        <Card padding="none">
          <ErrorState title={missing ? 'Шаблон не найден' : undefined} error={q.error} onRetry={missing ? undefined : () => q.refetch()} />
        </Card>
      </>
    )
  }

  // После действия показываем статус из ответа сервера (на заглушке бэкенда он не сохраняется до волны 3a).
  const item = acted && acted.id === q.data.id ? { ...q.data, status: acted.status } : q.data
  const gap = item.correct_rate != null && item.expected_correct_rate != null ? item.correct_rate - item.expected_correct_rate : null

  return (
    <>
      <PageHeader
        title={item.title}
        back={{ to: '/admin/items', label: 'Банк задач' }}
        meta={
          <>
            <ItemStatusBadge status={item.status} />
            {item.leak_flag && <LeakBadge score={item.leak_score} />}
          </>
        }
        description={
          <>
            <span className="font-mono">{item.code}</span> · {SPECIALIZATION_LABELS[item.specialization]} · {item.topic_label} · {GRADE_LABELS[item.target_grade]} ·{' '}
            {ITEM_FORMAT_LABELS[item.format]}
          </>
        }
        actions={
          <>
            {item.status === 'draft' && (
              <Button leftIcon={<CheckCircle2 className="size-4" aria-hidden />} onClick={() => setConfirm('approve')}>
                Одобрить черновик
              </Button>
            )}
            <RecalibrateButton focusItemId={item.id} />
            {item.status !== 'retired' && (
              <Button variant="danger" leftIcon={<Archive className="size-4" aria-hidden />} onClick={() => setConfirm('retire')}>
                Вывести из оборота
              </Button>
            )}
          </>
        }
      />

      {item.leak_flag && (
        <div role="alert" className="mb-5 flex gap-3 rounded-lg border border-danger/30 bg-danger-soft p-4 text-sm">
          <ShieldAlert className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
          <div>
            <p className="font-semibold text-danger">Возможная утечка</p>
            <p className="text-ink">
              Задачу решают верно в {pct(item.correct_rate)} случаев, а модель при уровне отвечавших ожидает {pct(item.expected_correct_rate)}. Отклонение z ={' '}
              {num(item.leak_score, 1)} (порог 3,5). Скорее всего, ответ разошёлся.{' '}
              {item.status === 'retired' ? 'Шаблон уже выведен из оборота.' : 'Выведите шаблон из оборота — тесты переключатся на другие задачи темы.'}
            </p>
          </div>
        </div>
      )}

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatTile label="Сложность b" value={num(item.b)} hint={`${pct(0.5)} верных при θ = ${num(item.b)}`} />
        <StatTile label="Различающая сила a" value={num(item.a)} hint={item.a >= 1 ? 'хорошо разделяет' : item.a >= 0.6 ? 'средне' : 'слабо разделяет'} />
        <StatTile label="Показов" value={item.exposures} hint={item.status === 'pilot' ? `до рабочего: ${Math.max(0, 150 - item.exposures)}` : undefined} />
        <StatTile label="Доля верных" value={pct(item.correct_rate)} tone={gap != null && gap >= 0.1 ? 'accent' : 'default'} hint={`ожидается ${pct(item.expected_correct_rate)}`} />
        <StatTile label="Сигнал утечки z" value={num(item.leak_score, 1)} tone={item.leak_flag ? 'accent' : 'default'} hint="флаг при z ≥ 3,5" />
        <StatTile label="Вариантов" value={`${item.variants_count}+`} hint="разных у генератора" />
      </div>

      <Card className="mb-6">
        <CardHeader
          title={
            <span className="inline-flex items-center gap-2">
              <Shuffle className="size-5 text-fsp-plum" aria-hidden />
              Три кандидата — три разных варианта
            </span>
          }
          description="Один шаблон, разные seed: подсвечено то, что у кандидатов отличается (числа, имена, код, порядок ответов). Ответ одного кандидата не подходит к варианту другого, поэтому слитый ответ почти бесполезен."
        />
        {item.preview_variants.length ? (
          <VariantPreview variants={item.preview_variants} />
        ) : (
          <SkeletonText lines={3} />
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Как задача работает в тесте" />
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
            <dt className="text-muted">Статус</dt>
            <dd>{ITEM_STATUS_HINTS[item.status]}</dd>
            <dt className="text-muted">Источник</dt>
            <dd>{item.source === 'llm_vacancy' ? 'Черновик из текста вакансии' : 'Эксперт'}</dd>
            <dt className="text-muted">Создан</dt>
            <dd>{formatDate(item.created_at)}</dd>
            <dt className="text-muted">Описание</dt>
            <dd>{item.description}</dd>
          </dl>
        </Card>
        <Card>
          <CardHeader title="Шанс решить по уровню" description="Вероятность верного ответа по модели для кандидатов разного уровня." />
          <ul className="flex flex-col gap-2.5">
            {(
              [
                ['Стажёр', -1.5],
                ['Junior', -0.5],
                ['Middle', 0.5],
                ['Senior', 1.5],
              ] as const
            ).map(([label, theta]) => {
              const p = p2pl(theta, item.a, item.b)
              return (
                <li key={label} className="grid grid-cols-[72px_1fr_48px] items-center gap-3 text-sm">
                  <span className="text-muted">{label}</span>
                  <span className="h-2.5 overflow-hidden rounded-full bg-line">
                    <span className="block h-full rounded-full bg-fsp-blue" style={{ width: `${p * 100}%` }} />
                  </span>
                  <b className="text-right tabular-nums">{pct(p)}</b>
                </li>
              )
            })}
          </ul>
          {item.status === 'pilot' && (
            <Badge tone="info" className="mt-4">
              Пилот: ответы идут в калибровку, на балл не влияют
            </Badge>
          )}
        </Card>
      </div>

      <ConfirmModal
        open={confirm === 'retire'}
        onClose={() => setConfirm(null)}
        onConfirm={() => retire.mutate(undefined)}
        loading={retire.isPending}
        danger
        title="Вывести шаблон из оборота?"
        description="Шаблон перестанет попадать в тесты. Уже пройденные тесты не пересчитываются."
        confirmLabel="Вывести из оборота"
      />
      <ConfirmModal
        open={confirm === 'approve'}
        onClose={() => setConfirm(null)}
        onConfirm={() => approve.mutate(undefined)}
        loading={approve.isPending}
        title="Одобрить черновик?"
        description="Шаблон пойдёт в тесты как непроверочный (пилот): кандидаты будут его решать, но на балл он не повлияет, пока не наберёт 150 ответов и не пройдёт калибровку."
        confirmLabel="Одобрить"
      />
    </>
  )
}
