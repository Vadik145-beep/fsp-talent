import { useState } from 'react'
import { Link } from 'react-router'
import { RefreshCw } from 'lucide-react'
import { api } from '@/shared/api'
import { Button, Modal, Table } from '@/shared/ui'
import { useAdminMutation, type RecalibrationResult } from '../api'
import { num } from '../labels'

/** Кнопка «Пересчитать калибровку» с окном результата: что изменилось в a и b. */
export function RecalibrateButton({ focusItemId, variant = 'secondary' }: { focusItemId?: number; variant?: 'secondary' | 'primary' }) {
  const [result, setResult] = useState<RecalibrationResult | null>(null)
  const m = useAdminMutation(() => api.post<RecalibrationResult>('/admin/items/recalibrate'), {
    onSuccess: (r) => setResult(r),
  })
  const changes = result
    ? [...result.changes].sort((a, b) => (a.item_id === focusItemId ? -1 : b.item_id === focusItemId ? 1 : a.item_id - b.item_id))
    : []

  return (
    <>
      <Button variant={variant} leftIcon={<RefreshCw className="size-4" aria-hidden />} loading={m.isPending} onClick={() => m.mutate(undefined)}>
        Пересчитать калибровку
      </Button>
      <Modal
        open={result !== null}
        onClose={() => setResult(null)}
        size="lg"
        title="Калибровка пересчитана"
        description="Сложность b и различающая сила a обновлены по накопленным ответам. Слитые шаблоны не пересчитываются: их ответы искажены."
        footer={<Button onClick={() => setResult(null)}>Готово</Button>}
      >
        {result && (
          <>
            <p className="mb-3 text-sm">
              Изменено шаблонов: <b>{result.items_recalibrated}</b>. Переведено из пилота в рабочие: <b>{result.pilot_promoted}</b>{' '}
              <span className="text-muted">(нужно не меньше 150 ответов, a ≥ 0,4, |b| ≤ 3,5).</span>
            </p>
            <Table
              caption="Изменения калибровки"
              rows={changes}
              rowKey={(r) => r.item_id}
              empty={<p className="px-4 py-6 text-center text-muted">Параметры уже соответствуют ответам — менять нечего.</p>}
              columns={[
                {
                  key: 'item_id',
                  header: 'Шаблон',
                  render: (r) => (
                    <Link to={`/admin/items/${r.item_id}`} onClick={() => setResult(null)} className="font-semibold text-fsp-plum hover:underline">
                      #{r.item_id}
                      {r.item_id === focusItemId ? ' (этот)' : ''}
                    </Link>
                  ),
                },
                { key: 'b', header: 'Сложность b', align: 'right', render: (r) => `${num(r.b_before)} → ${num(r.b_after)}` },
                { key: 'a', header: 'Различающая сила a', align: 'right', render: (r) => `${num(r.a_before)} → ${num(r.a_after)}` },
              ]}
            />
          </>
        )}
      </Modal>
    </>
  )
}
