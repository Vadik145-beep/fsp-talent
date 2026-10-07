import { useState } from 'react'
import { Link } from 'react-router'
import { RefreshCw } from 'lucide-react'
import { api } from '@/shared/api'
import { Button, Input, Modal, Table } from '@/shared/ui'
import { useAdminMutation, type RecalibrationResult } from '../api'
import { num } from '../labels'

/**
 * «Пересчитать калибровку»: POST /api/admin/items/recalibrate?min_responses=N.
 * Сначала окно с порогом ответов (пусто — по умолчанию сервера, 30), потом — что изменилось в a и b.
 */
export function RecalibrateButton({ focusItemId, variant = 'secondary' }: { focusItemId?: number; variant?: 'secondary' | 'primary' }) {
  const [asking, setAsking] = useState(false)
  const [minResponses, setMinResponses] = useState('')
  const [result, setResult] = useState<RecalibrationResult | null>(null)
  const min = minResponses.trim() ? Number(minResponses) : undefined
  const invalid = min !== undefined && (!Number.isInteger(min) || min < 1 || min > 100000)
  const m = useAdminMutation(
    (n: number | undefined) => api.post<RecalibrationResult>('/admin/items/recalibrate', undefined, { query: { min_responses: n } }),
    { onSuccess: (r) => (setAsking(false), setResult(r)) },
  )
  const changes = result
    ? [...result.changes].sort((a, b) => (a.item_id === focusItemId ? -1 : b.item_id === focusItemId ? 1 : a.item_id - b.item_id))
    : []

  return (
    <>
      <Button variant={variant} leftIcon={<RefreshCw className="size-4" aria-hidden />} onClick={() => setAsking(true)}>
        Пересчитать калибровку
      </Button>
      <Modal
        open={asking}
        onClose={() => setAsking(false)}
        size="sm"
        title="Пересчитать калибровку?"
        description="Сложность b и различающая сила a пересчитываются по накопленным ответам. Пилотные шаблоны с достаточным числом ответов становятся рабочими. Изменения попадут в журнал."
        footer={
          <>
            <Button variant="secondary" onClick={() => setAsking(false)}>
              Отмена
            </Button>
            <Button loading={m.isPending} disabled={invalid} onClick={() => m.mutate(min)}>
              Пересчитать
            </Button>
          </>
        }
      >
        <Input
          type="number"
          label="Минимум ответов на шаблон"
          placeholder="30"
          min={1}
          value={minResponses}
          onChange={(e) => setMinResponses(e.target.value)}
          error={invalid ? 'Целое число от 1' : undefined}
          hint="Шаблоны с меньшим числом ответов не трогаем: оценка по ним неустойчива. Пусто — по умолчанию (30)."
        />
      </Modal>
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
              empty={<p className="px-4 py-6 text-center text-muted">Ответов пока мало или параметры уже соответствуют ответам — менять нечего.</p>}
              columns={[
                {
                  key: 'item_id',
                  header: 'Шаблон',
                  render: (r) => (
                    <Link to={`/admin/items/${r.item_id}`} onClick={() => setResult(null)} className="font-semibold text-fsp-blue hover:underline">
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
