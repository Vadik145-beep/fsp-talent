import { useState } from 'react'
import { Link } from 'react-router'
import { ScanSearch } from 'lucide-react'
import { api } from '@/shared/api'
import { formatDateTime } from '@/shared/lib/format'
import { Badge, Button, Modal, Table } from '@/shared/ui'
import { useAdminMutation, type LeakScanResult } from '../api'
import { num, pct } from '../labels'

/**
 * «Проверить на утечки»: POST /api/admin/items/leak-scan. Детектор сравнивает долю верных с ожидаемой
 * по IRT и ищет быстрые верные ответы; помеченные шаблоны выводятся из оборота (это действие меняет банк),
 * поэтому сначала спрашиваем подтверждение.
 */
export function LeakScanButton({ variant = 'secondary' }: { variant?: 'secondary' | 'ghost' }) {
  const [confirm, setConfirm] = useState(false)
  const [result, setResult] = useState<LeakScanResult | null>(null)
  const m = useAdminMutation(() => api.post<LeakScanResult>('/admin/items/leak-scan'), {
    onSuccess: (r) => (setConfirm(false), setResult(r)),
  })

  return (
    <>
      <Button variant={variant} leftIcon={<ScanSearch className="size-4" aria-hidden />} onClick={() => setConfirm(true)}>
        Проверить на утечки
      </Button>
      <Modal
        open={confirm}
        onClose={() => setConfirm(false)}
        size="sm"
        title="Запустить детектор утечек?"
        description="Детектор проверит ответы по каждому шаблону: доля верных против ожидаемой моделью и подозрительно быстрые верные ответы. Шаблоны с признаками утечки будут выведены из оборота, событие попадёт в журнал."
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirm(false)}>
              Отмена
            </Button>
            <Button loading={m.isPending} onClick={() => m.mutate(undefined)}>
              Запустить
            </Button>
          </>
        }
      />
      <Modal
        open={result !== null}
        onClose={() => setResult(null)}
        size="lg"
        title="Проверка на утечки завершена"
        description={result ? `${formatDateTime(result.scanned_at)} · проверено ответов: ${result.answers_checked}, шаблонов: ${result.items_checked}` : undefined}
        footer={<Button onClick={() => setResult(null)}>Готово</Button>}
      >
        {result && (
          <div className="flex flex-col gap-5">
            <section>
              <h3 className="mb-2 text-sm font-semibold">Выведены из оборота: {result.retired.length}</h3>
              <Table
                mobileCards
                caption="Шаблоны с признаками утечки"
                rows={result.retired}
                rowKey={(r) => r.item_id}
                empty={<p className="px-4 py-6 text-center text-muted">Утечек не найдено — все шаблоны решают так, как ожидает модель.</p>}
                columns={[
                  {
                    key: 'title',
                    header: 'Шаблон',
                    render: (r) => (
                      <Link to={`/admin/items/${r.item_id}`} onClick={() => setResult(null)} className="font-semibold text-fsp-blue hover:underline">
                        {r.title}
                      </Link>
                    ),
                  },
                  { key: 'n', header: 'Ответов', align: 'right' },
                  { key: 'rate', header: 'Верных / ожидалось', align: 'right', render: (r) => `${pct(r.observed_rate)} / ${pct(r.expected_rate)}` },
                  { key: 'z', header: <span className="normal-case">z</span>, align: 'right', render: (r) => <Badge tone="danger">{num(r.z, 1)}</Badge> },
                  { key: 'fast', header: 'Быстрых верных', align: 'right', render: (r) => r.fast_correct },
                  { key: 'reasons', header: 'Почему', hideOnMobile: true, render: (r) => r.reasons.join('; ') },
                ]}
              />
            </section>
            <section>
              <h3 className="mb-1 text-sm font-semibold">Кандидаты для ручной проверки: {result.flagged_candidates.length}</h3>
              <p className="mb-2 text-[13px] text-muted">Аномалия ответов (lz) — повод посмотреть сессию, а не автоматическое наказание.</p>
              {result.flagged_candidates.length ? (
                <ul className="flex flex-col gap-1.5 text-sm">
                  {result.flagged_candidates.map((c) => (
                    <li key={`${c.candidate_id}-${c.session_id}`} className="rounded-md border border-line px-3 py-2">
                      <b>Кандидат #{c.candidate_id}</b>, сессия #{c.session_id} · lz = {num(c.lz, 1)}
                      {c.suspicious_item_ids.length ? ` · шаблоны ${c.suspicious_item_ids.map((id) => `#${id}`).join(', ')}` : ''}
                      {c.reasons.length ? <span className="block text-[13px] text-muted">{c.reasons.join('; ')}</span> : null}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted">Подозрительных сессий нет.</p>
              )}
            </section>
          </div>
        )}
      </Modal>
    </>
  )
}
