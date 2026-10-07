import { useRef, useState, type ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, Download, FlaskConical, Play, Upload } from 'lucide-react'
import { api } from '@/shared/api'
import { Badge, Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, SkeletonCard, Table } from '@/shared/ui'
import { useAdminMutation, type MatchingEvalResult, type ValidationChart, type ValidationOverview } from './api'
import { ValidationChartView, type ChartViewOptions } from './components/charts'
import { StatTile } from './components/common'
import { num, pct } from './labels'

type Summary = ValidationChart['summary']
type FactKind = 'pct' | 'num'
type Fact = [key: string, label: string, kind: FactKind]

interface ChartMeta {
  /** Вывод одной фразой из цифр графика; null — цифр нет, показываем описание графика. */
  headline: (s: Summary, chart: ValidationChart) => string | null
  /** Как читать график человеку без статистики. Без чисел: числа — в выводе, фактах и описании бэкенда. */
  howTo?: (chart: ValidationChart) => string
  options?: ChartViewOptions
  /** Ключевые числа из summary. Показываем только те, что прислал бэкенд. */
  facts: Fact[] | ((s: Summary) => Fact[])
}

/** Доля в процентах: целые без дробной части, остальное — с одним знаком. */
const P = (v: number) => pct(v, Math.round(v * 1000) % 10 === 0 ? 0 : 1)

/** Точки серии по имени (или первая серия). */
function seriesPoints(chart: ValidationChart, name?: string) {
  const s = chart.series.find((x) => x.name === name) ?? chart.series[0]
  return s?.points ?? []
}

/** Тексты без зашитых цифр: числа берутся из summary и серий, чтобы совпадать с данными бэкенда. */
const META: Record<string, ChartMeta> = {
  precision_at_10: {
    headline: (s) => {
      if (s.precision_at_10 == null) return null
      const vs = [
        s.baseline_precision_at_10 != null ? `${P(s.baseline_precision_at_10)} у поиска по ключевым словам` : null,
        s.random_precision_at_10 != null ? `${P(s.random_precision_at_10)} при случайном порядке` : null,
      ].filter(Boolean)
      return `В первой десятке выдачи ${P(s.precision_at_10)} подходящих кандидатов${vs.length ? ` — против ${vs.join(' и ')}` : ''}`
    },
    howTo: () =>
      'precision@10 — какая доля первых 10 кандидатов действительно подходит. nDCG@10 — то же с учётом порядка: подходящие выше — лучше. recall@50 — какую долю всех подходящих выдача находит в первых 50. Группы столбцов — способы ранжирования: платформа, поиск по ключевым словам резюме, только категория из теста и случайный порядок.',
    options: { percent: true, height: 300 },
    facts: [
      ['precision_at_10', 'precision@10', 'pct'],
      ['ndcg_at_10', 'nDCG@10', 'pct'],
      ['recall_at_50', 'recall@50', 'pct'],
      ['baseline_precision_at_10', 'precision@10 поиска по словам', 'pct'],
      ['random_precision_at_10', 'precision@10 случайно', 'pct'],
    ],
  },
  matching_ablation: {
    headline: (_s, chart) => {
      const pts = seriesPoints(chart, 'precision@10')
      if (pts.length < 2) return null
      const [full, ...rest] = pts
      const worst = rest.reduce((a, b) => (b.y < a.y ? b : a))
      return `Сильнее всего выдача проседает в варианте «${worst.x}»: precision@10 ${P(full.y)} → ${P(worst.y)}`
    },
    howTo: (chart) => {
      const pts = seriesPoints(chart, 'precision@10')
      const [full, ...rest] = pts
      const above = full ? rest.filter((p) => p.y > full.y).map((p) => `«${p.x}»`) : []
      return (
        'Первая группа — вся формула подбора. Каждая следующая — та же выдача, но без одного компонента. Чем ниже столбцы, тем важнее убранный компонент.' +
        (above.length
          ? ` Варианты выше всей формулы (${above.join(', ')}) значат, что компонент не улучшает совпадение с эталонной разметкой; разбор — в отчёте, раздел 6.3.`
          : '')
      )
    },
    options: { percent: true, height: 320 },
    facts: [['precision_at_10', 'precision@10 всей формулы', 'pct']],
  },
  grade_accuracy: {
    headline: (s) =>
      s.exact != null
        ? `Тест ставит правильный грейд в ${P(s.exact)} случаев${s.within_one != null ? `, с ошибкой не больше одного грейда — в ${P(s.within_one)}` : ''}`
        : null,
    howTo: () =>
      'Первый столбец — грейд угадан точно, второй — ошибка не больше чем на один грейд. Промахи — в основном у кандидатов на границе двух грейдов: вдали от границы точность выше.',
    options: { percent: true },
    facts: [
      ['exact', 'Грейд точно', 'pct'],
      ['within_one', 'Ошибка не больше 1 грейда', 'pct'],
      ['exact_far_from_threshold', 'Точно, если уровень не у границы', 'pct'],
    ],
  },
  theta_recovery: {
    headline: (s) => (s.correlation != null ? `Оценка теста совпадает с настоящим уровнем: корреляция ${num(s.correlation)}` : null),
    howTo: () =>
      'По горизонтали — настоящий уровень кандидата, по вертикали — что намерил тест. Пунктир — идеальное совпадение: чем плотнее точки к нему, тем точнее тест. Корреляция 1 — полное совпадение.',
    // Пороги грейдов по умолчанию на шкале θ (стажёр | junior | middle | senior).
    options: { diagonal: true, height: 300, thresholds: [-1, 0, 1] },
    facts: [
      ['correlation', 'Корреляция с истинным уровнем', 'num'],
      ['rmse', 'Средняя ошибка (RMSE)', 'num'],
      ['mean_test_length', 'Задач в тесте', 'num'],
    ],
  },
  retest_stability: {
    headline: (s) => {
      if (s.agreement == null) return null
      return `Повтор с другими задачами даёт ту же категорию в ${P(s.agreement)} случаев${s.cohen_kappa != null ? ` (каппа Коэна ${num(s.cohen_kappa)})` : ''}`
    },
    howTo: () =>
      'Тех же кандидатов проверяют второй раз, с другими задачами и вариантами. Столбец — у какой доли результат совпал. Каппа Коэна — согласие сверх случайного: 0 — как подбросить монету, больше 0,6 — существенное согласие.',
    options: { percent: true },
    facts: [
      ['agreement', 'Та же категория', 'pct'],
      ['decision_agreement', 'То же решение «подтвердил грейд / нет»', 'pct'],
      ['cohen_kappa', 'Каппа Коэна', 'num'],
      ['theta_retest_corr', 'Корреляция оценок двух тестов', 'num'],
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
      'Каждая точка — шаблон задачи. По горизонтали — различающая сила a из модели, по вертикали — насколько ответ на задачу совпадает с общим баллом. Выше пунктира — задача работает, ниже — кандидат на доработку.',
    options: { referenceY: { y: 0.2, label: 'порог 0,2' } },
    facts: [
      ['mean_point_biserial', 'Средняя связь с баллом', 'num'],
      ['mean_a', 'Средняя различающая сила a', 'num'],
      ['share_above_02', 'Доля задач выше порога', 'pct'],
      ['adaptive_mean_point_biserial', 'Связь с баллом в адаптивном тесте', 'num'],
    ],
  },
  test_length: {
    headline: (s) => {
      if (s.share_stopped_by_se != null && s.share_stopped_by_se < 0.05 && s.max_length != null)
        return `Тест идёт до предела в ${num(s.max_length, 0)} задач; погрешность оценки в конце — в среднем ${num(s.mean_se ?? NaN)}`
      if (s.share_stopped_by_se != null && s.mean != null)
        return `${P(s.share_stopped_by_se)} тестов останавливаются досрочно; в среднем ${num(s.mean, 1)} задач`
      return null
    },
    howTo: () =>
      'Тест останавливается, когда погрешность оценки уровня (SE) стала достаточно малой, или на предельном числе задач. Столбец — сколько кандидатов закончили тест с такой погрешностью: чем левее, тем точнее.',
    facts: [
      ['mean', 'Задач в среднем', 'num'],
      ['mean_se', 'Средняя SE в конце', 'num'],
      ['share_stopped_by_se', 'Остановились досрочно', 'pct'],
    ],
  },
  bank_size: {
    headline: (_s, chart) => {
      const pts = seriesPoints(chart)
      if (pts.length < 2) return null
      const a = pts[0]
      const b = pts[pts.length - 1]
      return `Чем больше банк, тем точнее тест: корреляция ${num(a.y)} при ${a.x} шаблонах → ${num(b.y)} при ${b.x}`
    },
    howTo: () =>
      'Тот же тест на урезанном банке шаблонов одного направления. Если линии ещё растут на правом краю, расширение банка даст дальше прирост точности.',
    facts: (s) =>
      Object.keys(s)
        .filter((k) => /^se_at_\d+$/.test(k))
        .sort((a, b) => Number(a.slice(6)) - Number(b.slice(6)))
        .map((k): Fact => [k, `SE при ${k.slice(6)} шаблонах`, 'num']),
  },
  leak_detector: {
    headline: (s) =>
      s.inflated_no_protection != null && s.inflated_parametrized != null
        ? `Утечка без защиты завышает грейд ${P(s.inflated_no_protection)} читеров, с параметризацией задач — ${P(s.inflated_parametrized)}`
        : s.recall != null
          ? `Детектор находит ${P(s.recall)} слитых задач`
          : null,
    howTo: () =>
      'Часть задач слили, часть кандидатов списывает. Строки — режимы защиты, длина столбца — у какой доли грейд по тесту выше настоящего. У честных кандидатов это фон ошибки измерения; защита работает, если у читеров доля опускается к этому фону.',
    options: { percent: true, height: 300 },
    facts: [
      ['recall', 'Детектор находит слитых задач', 'pct'],
      ['precision', 'Точность детектора', 'pct'],
      ['cheater_recall', 'Находит читеров (без параметризации)', 'pct'],
    ],
  },
}

const ORDER = Object.keys(META)

function fmtFact(v: number | undefined, kind: FactKind): string {
  if (v == null) return '—'
  return kind === 'pct' ? P(v) : num(v, v >= 10 ? 1 : 2)
}

function ChartCard({ chart }: { chart: ValidationChart }) {
  const meta = META[chart.id]
  const allFacts = typeof meta?.facts === 'function' ? meta.facts(chart.summary) : (meta?.facts ?? [])
  const facts = allFacts.filter(([k]) => chart.summary[k] != null)
  const headline = meta?.headline(chart.summary, chart)
  return (
    <Card className="flex min-w-0 flex-col" data-testid={`chart-${chart.id}`}>
      <div className="mb-1 flex flex-wrap items-center gap-2">
        <span className="text-[13px] font-semibold tracking-wide text-muted uppercase">{chart.title}</span>
        {chart.is_stub && (
          <Badge tone="neutral" title="Предварительные цифры; пересчёт — python scripts/validation/run_all.py">
            предварительно
          </Badge>
        )}
      </div>
      <h3 className="mb-2 text-base font-semibold">{headline ?? chart.title}</h3>
      {facts.length > 0 && (
        <dl className="mb-3 flex flex-wrap gap-x-6 gap-y-2">
          {facts.map(([k, label, kind]) => (
            <div key={k}>
              <dd className="font-mono text-xl font-bold tabular-nums text-fsp-plum">{fmtFact(chart.summary[k], kind)}</dd>
              <dt className="text-xs text-muted">{label}</dt>
            </div>
          ))}
        </dl>
      )}
      <ValidationChartView chart={chart} options={meta?.options} />
      <p className="mt-3 text-[13px] leading-relaxed text-muted">
        <b className="text-ink">Как получено. </b>
        {chart.description}
      </p>
      {meta?.howTo && (
        <p className="mt-2 text-[13px] leading-relaxed text-muted">
          <b className="text-ink">Как читать. </b>
          {meta.howTo(chart)}
        </p>
      )}
    </Card>
  )
}

/** Главные числа сверху: из summary графиков, без зашитых значений. */
function KeyNumbers({ charts }: { charts: ValidationChart[] }) {
  const s = (id: string) => charts.find((c) => c.id === id)?.summary ?? {}
  const m = s('precision_at_10')
  const g = s('grade_accuracy')
  const t = s('theta_recovery')
  const l = s('leak_detector')
  const tiles: Array<{ label: string; value: string; hint?: string }> = []
  if (m.precision_at_10 != null)
    tiles.push({
      label: 'Подходящих в топ-10 подбора',
      value: P(m.precision_at_10),
      hint: m.baseline_precision_at_10 != null ? `поиск по словам: ${P(m.baseline_precision_at_10)}` : undefined,
    })
  if (g.exact != null) tiles.push({ label: 'Грейд определён точно', value: P(g.exact), hint: g.within_one != null ? `±1 грейд: ${P(g.within_one)}` : undefined })
  if (t.correlation != null) tiles.push({ label: 'Корреляция оценки с уровнем', value: num(t.correlation), hint: t.rmse != null ? `RMSE ${num(t.rmse)}` : undefined })
  if (l.inflated_no_protection != null && l.inflated_parametrized != null)
    tiles.push({
      label: 'Читерам завышен грейд при утечке',
      value: `${P(l.inflated_no_protection)} → ${P(l.inflated_parametrized)}`,
      hint: 'без защиты → с параметризацией',
    })
  if (!tiles.length) return null
  return (
    <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {tiles.map((x) => (
        <StatTile key={x.label} label={x.label} value={x.value} hint={x.hint} />
      ))}
    </div>
  )
}

function Code({ children }: { children: ReactNode }) {
  return <code className="rounded-xs bg-surface px-1 font-mono text-[12px] text-ink">{children}</code>
}

/** Процедура — по docs/validation/report.md (разделы 2–6, 9). */
function Procedure({ seed, generatedAt }: { seed: number; generatedAt?: string }) {
  const rows: Array<[string, ReactNode]> = [
    [
      'Данные',
      'Синтетика с известной правдой: 1200 кандидатов. Истинный уровень и реальный стек каждого заданы заранее, но платформа их не видит — только резюме (с пропусками, сленгом и приписками), заявленный грейд (часть завышает или занижает) и ответы в тесте.',
    ],
    [
      'Тест',
      'Настоящий адаптивный движок платформы по банку из 192 шаблонов (32 на направление): до 20 задач, остановка при достаточной точности. Онбординг — по правилам платформы: тест на заявленный грейд, при провале — на грейд ниже.',
    ],
    ['Повтор', 'Те же кандидаты проходят онбординг второй раз — с другими задачами и вариантами.'],
    [
      'Утечка',
      'Часть шаблонов «сливается» (чаще те, что чаще показывали), часть кандидатов — читеры. Сравниваем режимы: без защиты, параметризация, детектор утечек и обе защиты.',
    ],
    [
      'Подбор',
      'Для 100 потребностей с эталонной разметкой выдачу строит настоящая формула подбора. Сравнение — с поиском по ключевым словам резюме (BM25) и случайным порядком; абляция убирает по одному компоненту формулы.',
    ],
    [
      'Правило разметки',
      'Эталон строится только по скрытой правде: подходит, если совпадает направление, кандидат реально владеет всеми обязательными технологиями, его минимальная зарплата не выше вилки и истинный грейд равен грейду потребности; грейд на ступень выше — подходит частично. Резюме, тест и ФСП эталон не видит, поэтому он не повторяет формулу ранжирования.',
    ],
    [
      'Воспроизведение',
      <span key="cmd">
        Фиксированный seed <b>{seed}</b>, из корня репозитория: <Code>python scripts/validation/run_all.py</Code>. Скрипт пересчитывает графики и отчёт{' '}
        <Code>docs/validation/report.md</Code>
        {generatedAt ? `; текущий прогон — ${generatedAt.slice(0, 10)}` : ''}.
      </span>,
    ],
  ]
  return (
    <Card className="mb-6">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <FlaskConical className="size-5 text-fsp-plum" aria-hidden /> Как проверено
          </span>
        }
        description="Готовой разметки «кто какого уровня и кто кому подходит» нет, поэтому тест и подбор проверяем на синтетике, где правильный ответ известен. Всё считает настоящий код платформы."
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

const EXAMPLE_CSV = `${import.meta.env.BASE_URL}example_pairs.csv`

const RANKING_LABELS: Record<string, string> = {
  synthetic: 'Ранжировала платформа · синтетический набор',
  platform: 'Ранжировала платформа · данные стенда',
  file_order: 'Оценён порядок строк файла',
}

function MatchingUpload() {
  const input = useRef<HTMLInputElement>(null)
  const [fileName, setFileName] = useState('')
  const [loadingExample, setLoadingExample] = useState(false)
  const m = useAdminMutation(
    (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<MatchingEvalResult>('/eval/matching', form)
    },
    { success: (r) => `Посчитано: ${r.pairs_count} пар, ${r.needs_count} потребностей` },
  )

  function upload(file: File) {
    setFileName(file.name)
    m.mutate(file)
  }

  function downloadExample() {
    const a = document.createElement('a')
    a.href = EXAMPLE_CSV
    a.download = 'example_pairs.csv'
    a.click()
  }

  async function tryExample() {
    setLoadingExample(true)
    try {
      const res = await fetch(EXAMPLE_CSV)
      if (!res.ok) throw new Error(String(res.status))
      upload(new File([await res.blob()], 'example_pairs.csv', { type: 'text/csv' }))
    } catch {
      setFileName('Пример не загрузился — скачайте его и загрузите вручную')
    } finally {
      setLoadingExample(false)
    }
  }

  const r = m.data
  const fileOrder = r?.ranking === 'file_order'
  const baseName = fileOrder ? 'исходный порядок' : 'поиск по словам'
  return (
    <Card id="matching-upload">
      <CardHeader
        title="Проверка подбора на своих парах"
        description="Загрузите CSV пар «потребность — кандидат». Порядок строк не важен: кандидатов каждой потребности ранжирует сама платформа, а метрики показывают, сколько подходящих оказалось наверху."
        actions={
          <Button variant="ghost" size="sm" leftIcon={<Download className="size-4" aria-hidden />} onClick={downloadExample}>
            Скачать пример
          </Button>
        }
      />
      <div className="mb-4 rounded-md bg-surface-muted p-3 text-sm text-muted">
        <p>
          Формат: <Code>need_id,candidate_id[,relevant]</Code>, UTF-8, разделитель <Code>,</Code> или <Code>;</Code>.
        </p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>
            <Code>need_id</Code> — синтетическая потребность (<Code>N001</Code>…) или потребность на стенде (число);
          </li>
          <li>
            <Code>candidate_id</Code> — синтетический кандидат (<Code>C0001</Code>…) или профиль на стенде (число);
          </li>
          <li>
            <Code>relevant</Code> — 1 подходит, 0 нет (или 0/1/2, где 1 — частично). Без колонки: для синтетики берётся эталон, для стенда —
            совпадение категории кандидата с категорией потребности.
          </li>
        </ul>
        <p className="mt-2">
          Если id не найдены ни в синтетике, ни на стенде, оценивается порядок строк файла как готовая выдача — тогда нужна колонка relevant.
          Пример <Code>example_pairs.csv</Code>: 6 потребностей по одной на направление, по 40 кандидатов, отобранных независимо от выдачи.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          aria-label="CSV-файл с парами"
          className="sr-only"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) upload(f)
            e.target.value = ''
          }}
        />
        <Button leftIcon={<Upload className="size-4" aria-hidden />} loading={m.isPending && !loadingExample} onClick={() => input.current?.click()}>
          Загрузить CSV
        </Button>
        <Button variant="secondary" leftIcon={<Play className="size-4" aria-hidden />} loading={loadingExample} disabled={m.isPending} onClick={() => void tryExample()}>
          Проверить на примере
        </Button>
        <span className="text-sm text-muted">{fileName || 'Файл не выбран · до 10 МБ'}</span>
      </div>

      {r && (
        <div className="mt-5" data-testid="matching-result">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone={fileOrder ? 'warning' : 'violet'}>{RANKING_LABELS[r.ranking] ?? r.ranking}</Badge>
            <span className="text-sm text-muted">
              {r.filename} · {r.pairs_count} пар · {r.needs_count} потребностей
            </span>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile
              label="precision@10"
              value={P(r.precision_at_10)}
              hint={`${baseName}: ${P(r.baseline_precision_at_10)} · случайно: ${P(r.random_precision_at_10)}`}
            />
            <StatTile label="nDCG@10" value={P(r.ndcg_at_10)} hint={`${baseName}: ${P(r.baseline_ndcg_at_10)} · случайно: ${P(r.random_ndcg_at_10)}`} />
            <StatTile label="recall@50" value={P(r.recall_at_50)} hint="доля подходящих в первых 50" />
            <StatTile label="Подходящих попало в топ-10" value={P(r.relevant_in_top_share)} hint="от всех подходящих в файле" />
          </div>
          {r.note && <p className="mt-3 text-[13px] text-muted">{r.note}</p>}
          {r.is_stub && <p className="mt-1 text-[13px] text-muted">Цифры предварительные: расчёт по файлу на сервере — заглушка.</p>}
          {(r.warnings ?? []).length > 0 && (
            <ul className="mt-3 space-y-1 rounded-md bg-warning-soft p-3 text-sm text-warning" aria-label="Предупреждения">
              {(r.warnings ?? []).map((w) => (
                <li key={w} className="flex items-start gap-2">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
                  {w}
                </li>
              ))}
            </ul>
          )}
          <Table
            className="mt-3"
            caption="Метрики по потребностям"
            rows={r.per_need}
            rowKey={(x) => x.need_id}
            empty={<p className="px-4 py-6 text-center text-muted">Разбивки по потребностям в ответе нет.</p>}
            columns={[
              { key: 'need_id', header: 'Потребность' },
              { key: 'candidates_total', header: 'Кандидатов', align: 'right', sortable: true, hideOnMobile: true },
              { key: 'relevant_total', header: 'Подходящих', align: 'right', sortable: true },
              { key: 'precision_at_10', header: 'precision@10', align: 'right', sortable: true, render: (x) => P(x.precision_at_10) },
              {
                key: 'baseline_precision_at_10',
                header: fileOrder ? 'precision@10 (исх.)' : 'precision@10 (слова)',
                align: 'right',
                sortable: true,
                hideOnMobile: true,
                render: (x) => P(x.baseline_precision_at_10),
              },
              { key: 'ndcg_at_10', header: 'nDCG@10', align: 'right', sortable: true, render: (x) => P(x.ndcg_at_10) },
              {
                key: 'baseline_ndcg_at_10',
                header: fileOrder ? 'nDCG@10 (исх.)' : 'nDCG@10 (слова)',
                align: 'right',
                sortable: true,
                hideOnMobile: true,
                render: (x) => P(x.baseline_ndcg_at_10),
              },
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
        description="Насколько тесту и подбору можно доверять: проверка на синтетических данных с известной правдой."
        actions={
          <Button
            variant="secondary"
            leftIcon={<Upload className="size-4" aria-hidden />}
            onClick={() => document.getElementById('matching-upload')?.scrollIntoView({ behavior: 'smooth' })}
          >
            Проверить свой CSV
          </Button>
        }
      />
      {charts.length > 0 && <KeyNumbers charts={charts} />}
      <Procedure seed={q.data?.seed ?? 20261011} generatedAt={q.data?.generated_at} />
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
          <EmptyState
            icon={<FlaskConical aria-hidden />}
            title="Графиков пока нет"
            description="Запустите python scripts/validation/run_all.py (или make validate) — графики появятся здесь."
          />
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
