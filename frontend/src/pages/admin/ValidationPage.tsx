import { useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, FlaskConical, Upload } from 'lucide-react'
import { api } from '@/shared/api'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, SkeletonCard, Table } from '@/shared/ui'
import { useAdminMutation, type MatchingEvalResult, type ValidationChart, type ValidationOverview } from './api'
import { ValidationChartView, type ChartViewOptions } from './components/charts'
import { StatTile } from './components/common'
import { num, pct } from './labels'

type Summary = ValidationChart['summary']

interface ChartMeta {
  /** Вывод простыми словами из цифр графика; null — цифр нет, берём описание графика. */
  headline: (s: Summary) => string | null
  /** Как читать график человеку без статистики (зависит от вида графика). */
  howTo: (chart: ValidationChart) => string
  options?: ChartViewOptions
  /** Ключевые числа из summary: [ключ, подпись, формат]. Показываем только те, что прислал бэкенд. */
  facts: Array<[string, string, 'pct' | 'num']>
}

const P = (v: number) => pct(v, Math.round(v * 1000) % 10 === 0 ? 0 : 1)

/** Тексты без зашитых цифр: числа берутся из summary, чтобы совпадать с данными бэкенда. */
const META: Record<string, ChartMeta> = {
  grade_accuracy: {
    headline: (s) =>
      s.exact != null
        ? `Тест ставит правильный грейд в ${P(s.exact)} случаев${s.within_one != null ? `, с ошибкой не больше одного грейда — в ${P(s.within_one)}` : ''}`
        : null,
    howTo: () =>
      'Синтетические кандидаты с заранее известным уровнем прошли настоящий тест. Первый столбец — грейд угадан точно, второй — ошибка не больше чем на один грейд. Промахи почти всегда у кандидатов на границе двух грейдов.',
    options: { percent: true },
    facts: [
      ['exact', 'Грейд точно', 'pct'],
      ['within_one', 'Ошибка не больше 1 грейда', 'pct'],
      ['exact_far_from_threshold', 'Точно, если уровень не у самой границы', 'pct'],
    ],
  },
  theta_recovery: {
    headline: (s) => (s.correlation != null ? `Оценка теста совпадает с настоящим уровнем: корреляция ${num(s.correlation)}` : null),
    howTo: () =>
      'Каждая точка — кандидат: по горизонтали его настоящий уровень, по вертикали — что намерил тест. Пунктир — идеальное совпадение. Чем плотнее точки к пунктиру, тем точнее тест. Корреляция 1,0 — полное совпадение.',
    options: { diagonal: true, height: 300 },
    facts: [
      ['correlation', 'Корреляция с истинным уровнем', 'num'],
      ['rmse', 'Средняя ошибка (RMSE)', 'num'],
      ['mean_test_length', 'Задач в среднем', 'num'],
    ],
  },
  retest_stability: {
    headline: (s) => {
      const v = s.decision_agreement ?? s.agreement
      return v != null ? `Повторный тест с другими задачами даёт тот же результат в ${P(v)} случаев` : null
    },
    howTo: () =>
      'Тех же кандидатов тестируют второй раз, с другими вариантами задач. Столбец — у какой доли результат совпал. Каппа Коэна — согласие сверх случайного: больше 0,6 — хорошее. Более длинный тест стабильнее — это настройка, а не переделка.',
    options: { percent: true },
    facts: [
      ['decision_agreement', 'То же решение по грейду', 'pct'],
      ['agreement', 'Тот же грейд', 'pct'],
      ['cohen_kappa', 'Каппа Коэна (согласие сверх случайного)', 'num'],
    ],
  },
  item_discrimination: {
    headline: (s) =>
      s.share_above_02 != null
        ? `${P(s.share_above_02)} задач хорошо отличают сильных кандидатов от слабых`
        : s.mean_point_biserial != null
          ? `Задачи отличают сильных кандидатов от слабых: средняя связь с баллом ${num(s.mean_point_biserial)}`
          : null,
    howTo: () =>
      'Каждая точка — шаблон. По горизонтали — различающая сила a из модели, по вертикали — насколько ответ на задачу совпадает с итоговым баллом. Выше пунктира (0,2) — задача работает. Ниже — кандидат на доработку.',
    options: { referenceY: { y: 0.2, label: 'порог 0,2' } },
    facts: [
      ['mean_point_biserial', 'Средняя связь с баллом', 'num'],
      ['mean_a', 'Средняя различающая сила a', 'num'],
      ['share_above_02', 'Доля задач выше порога', 'pct'],
    ],
  },
  test_length: {
    headline: (s) => (s.mean != null ? `Хватает в среднем ${num(s.mean, 1)} задач вместо длинной анкеты` : null),
    howTo: () =>
      'Тест останавливается, как только уровень измерен достаточно точно. Столбец — сколько кандидатов закончили тест на этом числе задач. Последний столбец — те, кому понадобился максимум.',
    facts: [
      ['mean', 'Задач в среднем', 'num'],
      ['share_stopped_by_se', 'Остановились досрочно (точность набрана)', 'pct'],
      ['share_max_length', 'Дошли до максимума задач', 'pct'],
    ],
  },
  leak_detector: {
    headline: (s) => (s.recall != null ? `Детектор находит ${P(s.recall)} слитых задач, читерам слив почти не помогает` : null),
    howTo: (c) =>
      c.chart_type === 'line'
        ? 'Симуляция: часть задач слили в интернет, часть кандидатов списывает. Линия — у какой доли кандидатов грейд оказался выше настоящего, по неделям. Красная — без защиты: доля завышенных растёт. Синяя — с защитой (у каждого свой вариант задачи и детектор утечек): остаётся на уровне фона.'
        : 'Симуляция: часть задач слили в интернет, часть кандидатов списывает. Столбцы — режимы защиты, высота — у какой доли кандидатов грейд оказался выше настоящего. Без защиты читерам завышают грейд чаще всего; параметризация (у каждого свои числа) и детектор утечек возвращают долю к фону честных кандидатов.',
    options: { percent: true },
    facts: [
      ['recall', 'Детектор находит слитых задач', 'pct'],
      ['precision', 'Точность детектора', 'pct'],
      ['cheater_recall', 'Находит читеров (без параметризации)', 'pct'],
    ],
  },
  precision_at_10: {
    headline: (s) =>
      s.precision_at_10 != null && s.baseline_precision_at_10 != null
        ? `Подбор находит подходящих лучше поиска по словам: ${P(s.precision_at_10)} против ${P(s.baseline_precision_at_10)} в первой десятке`
        : null,
    howTo: () =>
      'precision@10 — сколько из первых 10 кандидатов в подборке действительно подходят. nDCG@10 — то же, но с учётом порядка: подходящие выше — лучше. Серый столбец — поиск по ключевым словам резюме для сравнения.',
    options: { percent: true },
    facts: [
      ['precision_at_10', 'precision@10', 'pct'],
      ['ndcg_at_10', 'nDCG@10', 'pct'],
      ['baseline_precision_at_10', 'precision@10 у поиска по словам', 'pct'],
    ],
  },
  bank_size: {
    headline: () => 'Почему в банке 30+ шаблонов на специализацию',
    howTo: () =>
      'Точность теста при разном размере банка. На маленьком банке тест показывает все задачи подряд и теряет адаптивность. Чем больше банк, тем точнее и короче тест.',
    options: { yDomain: [0.6, 1] },
    facts: [],
  },
}

const ORDER = ['grade_accuracy', 'theta_recovery', 'retest_stability', 'item_discrimination', 'leak_detector', 'test_length', 'precision_at_10', 'bank_size']

const SAMPLE_CSV = [
  'need_id,candidate_id,relevant',
  '1,1,1', '1,6,1', '1,2,0', '1,11,1', '1,3,0', '1,16,1', '1,21,0', '1,4,1', '1,26,0', '1,8,0',
  '2,7,1', '2,12,0', '2,1,1', '2,17,1', '2,22,0', '2,5,0',
  '3,4,1', '3,9,1', '3,14,0', '3,19,1', '3,24,0',
].join('\n')

function fmtFact(v: number | undefined, kind: 'pct' | 'num'): string {
  if (v == null) return '—'
  return kind === 'pct' ? pct(v, Math.round(v * 1000) % 10 === 0 ? 0 : 1) : num(v, v >= 10 ? 1 : 2)
}

function ChartCard({ chart }: { chart: ValidationChart }) {
  const meta = META[chart.id]
  const facts = (meta?.facts ?? []).filter(([k]) => chart.summary[k] != null)
  return (
    <Card className="flex min-w-0 flex-col">
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold tracking-wide text-muted uppercase">{chart.title}</span>
        {chart.is_stub && (
          <Badge tone="neutral" title="Предварительные цифры; итоговый пересчёт — make validate">
            предварительно
          </Badge>
        )}
      </div>
      <h3 className="mb-2 text-base font-semibold">{meta?.headline(chart.summary) ?? chart.description}</h3>
      {facts.length > 0 && (
        <dl className="mb-3 flex flex-wrap gap-x-6 gap-y-2">
          {facts.map(([k, label, kind]) => (
            <div key={k}>
              <dd className="text-xl font-bold tabular-nums text-fsp-plum">{fmtFact(chart.summary[k], kind)}</dd>
              <dt className="text-xs text-muted">{label}</dt>
            </div>
          ))}
        </dl>
      )}
      <ValidationChartView chart={chart} options={meta?.options} />
      <p className="mt-3 text-[13px] leading-relaxed text-muted">
        <b className="text-ink">Как читать. </b>
        {meta?.howTo(chart) ?? chart.description}
      </p>
    </Card>
  )
}

function Procedure({ seed }: { seed: number }) {
  const rows: Array<[string, ReactNode]> = [
    ['Кандидаты', '1000 синтетических кандидатов. Настоящий уровень каждого известен заранее (θ из нормального распределения), поэтому есть с чем сравнить оценку теста.'],
    ['Ответы', 'Кандидат отвечает верно с вероятностью из модели IRT по своему настоящему уровню; время ответа тоже моделируется.'],
    ['Тест', 'Каждый проходит настоящий адаптивный тест движка с правилами по умолчанию (банк 240 задач, 8 тем).'],
    ['Повтор', 'Те же кандидаты проходят тест второй раз с другими вариантами задач.'],
    ['Утечка', '20% задач «сливаются» (чаще те, что чаще показывали), 10% кандидатов — читеры. Сравниваем режимы: без защиты, параметризация, детектор.'],
    ['Подбор', 'Потребности с эталонной разметкой подходящих кандидатов (правило разметки не совпадает с формулой ранжирования); сравнение с поиском по ключевым словам.'],
    ['Воспроизведение', <span key="cmd">фиксированный seed <b>{seed}</b>: <code className="rounded-xs bg-surface px-1 font-mono text-[12px]">PYTHONPATH=backend python -m app.testing.engine.simulate --seed {seed}</code></span>],
  ]
  return (
    <Card className="mb-6">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <FlaskConical className="size-5 text-fsp-plum" aria-hidden /> Как проверено
          </span>
        }
        description="Реальной разметки «кто какого уровня» нет ни у кого, поэтому тест проверяем на синтетике, где правильный ответ известен."
      />
      <dl className="grid gap-x-6 gap-y-3 text-sm md:grid-cols-2">
        {rows.map(([k, v]) => (
          <div key={k} className="rounded-md bg-surface-muted p-3">
            <dt className="font-semibold text-ink">{k}</dt>
            <dd className="text-muted">{v}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}

function MatchingUpload() {
  const input = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState('')
  const m = useAdminMutation(
    (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<MatchingEvalResult>('/eval/matching', form)
    },
    { success: (r) => `Посчитано: ${r.pairs_count} пар, ${r.needs_count} потребностей` },
  )

  function downloadSample() {
    const url = URL.createObjectURL(new Blob([SAMPLE_CSV], { type: 'text/csv;charset=utf-8' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'pairs_example.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const r = m.data
  return (
    <Card id="matching-upload">
      <CardHeader
        title="Проверка подбора для жюри"
        description="Загрузите CSV пар «потребность — кандидат» в порядке выдачи: колонки need_id, candidate_id и необязательно relevant (1 — подходит, 0 — нет). Без relevant кандидат считается подходящим, если его категория совпала с категорией потребности."
        actions={
          <Button variant="ghost" size="sm" leftIcon={<Download className="size-4" aria-hidden />} onClick={downloadSample}>
            Пример CSV
          </Button>
        }
      />
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          aria-label="CSV-файл с парами"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (!f) return
            setFileName(f.name)
            m.mutate(f)
            e.target.value = ''
          }}
        />
        <Button leftIcon={<Upload className="size-4" aria-hidden />} loading={m.isPending} onClick={() => input.current?.click()}>
          Загрузить CSV
        </Button>
        <span className="text-sm text-muted">{fileName || 'Файл не выбран · до 10 МБ, UTF-8'}</span>
      </div>

      {r && (
        <div className="mt-5">
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="precision@10" value={pct(r.precision_at_10)} hint={`поиск по словам: ${pct(r.baseline_precision_at_10)}`} tone="success" />
            <StatTile label="nDCG@10" value={pct(r.ndcg_at_10)} hint={`поиск по словам: ${pct(r.baseline_ndcg_at_10)}`} tone="success" />
            <StatTile label="Подходящих в топ-10" value={pct(r.relevant_in_top_share)} hint="от всех подходящих в файле" />
            <StatTile label="Пар / потребностей" value={`${r.pairs_count} / ${r.needs_count}`} hint={r.filename} />
          </div>
          <p className="mt-3 text-[13px] text-muted">
            Порядок строк внутри потребности — наша выдача. Поиск по словам ранжирует тех же кандидатов по числу совпавших технологий стека.
            {r.is_stub ? ' Цифры предварительные: настоящий расчёт по файлу подключается в модуле eval.' : ''}
          </p>
          <Table
            className="mt-3"
            caption="Метрики по потребностям"
            rows={r.per_need}
            rowKey={(x) => x.need_id}
            empty={<p className="px-4 py-6 text-center text-muted">Разбивки по потребностям в ответе нет.</p>}
            columns={[
              { key: 'need_id', header: 'Потребность' },
              { key: 'precision_at_10', header: 'precision@10', align: 'right', sortable: true, render: (x) => pct(x.precision_at_10) },
              { key: 'ndcg_at_10', header: 'nDCG@10', align: 'right', sortable: true, render: (x) => pct(x.ndcg_at_10) },
              { key: 'relevant_total', header: 'Подходящих всего', align: 'right', sortable: true },
            ]}
          />
        </div>
      )}
    </Card>
  )
}

export default function AdminValidationPage() {
  const q = useQuery({ queryKey: ['admin', 'validation'], queryFn: () => api.get<ValidationOverview>('/eval/validation') })
  const charts = [...(q.data?.charts ?? [])].sort((a, b) => {
    const ia = ORDER.indexOf(a.id)
    const ib = ORDER.indexOf(b.id)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })

  return (
    <>
      <PageHeader
        title="Валидация"
        description="Насколько тесту и подбору можно доверять: проверка на синтетических кандидатах с известным уровнем."
        actions={
          <Button variant="secondary" leftIcon={<Upload className="size-4" aria-hidden />} onClick={() => document.getElementById('matching-upload')?.scrollIntoView({ behavior: 'smooth' })}>
            Проверить свой CSV
          </Button>
        }
      />
      <Procedure seed={q.data?.seed ?? 20261011} />
      {q.isPending ? (
        <div className="grid gap-6 xl:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : q.isError ? (
        <Card padding="none">
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        </Card>
      ) : charts.length === 0 ? (
        <Card padding="none">
          <EmptyState icon={<FlaskConical aria-hidden />} title="Графиков пока нет" description="Запустите make validate — графики появятся здесь." />
        </Card>
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {charts.map((c) => (
            <ChartCard key={c.id} chart={c} />
          ))}
        </div>
      )}
      <div className="mt-6">
        <MatchingUpload />
      </div>
    </>
  )
}
