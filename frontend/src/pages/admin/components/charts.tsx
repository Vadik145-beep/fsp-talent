import type { ReactNode } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { ValidationChart } from '../api'
import { num, pct } from '../labels'
import { AXIS, AXIS_LABEL, CURSOR_FILL, GRID, NEUTRAL, REFERENCE, TOOLTIP_STYLE, VALUE_LABEL, seriesColors } from './chartTheme'

/** Контейнер графика фиксированной высоты (ширина — по родителю). */
export function ChartBox({ height = 260, children, label }: { height?: number; children: ReactNode; label: string }) {
  return (
    <div role="img" aria-label={label} style={{ width: '100%', height }} className="min-w-0">
      <ResponsiveContainer width="100%" height="100%" minWidth={200} initialDimension={{ width: 520, height }}>
        {children as never}
      </ResponsiveContainer>
    </div>
  )
}

export interface ChartViewOptions {
  /** Значения — доли (0…1), показывать в процентах. */
  percent?: boolean
  height?: number
  /** Горизонтальная линия-ориентир (например, порог «хорошей» различающей силы). */
  referenceY?: { y: number; label: string }
  /** Диагональ y = x для графиков «оценка против истины». */
  diagonal?: boolean
  yDomain?: [number, number]
  /** Серые линии-пороги по обеим осям точечного графика (например, пороги грейдов на шкале θ). */
  thresholds?: number[]
}

/** Подпись категории слева от горизонтальных столбцов: переносим по словам, не длиннее ~22 символов в строке. */
function WrappedTick(props: { x?: number; y?: number; payload?: { value: string | number } }) {
  const { x = 0, y = 0, payload } = props
  const words = String(payload?.value ?? '').split(' ')
  const lines: string[] = []
  for (const w of words) {
    const last = lines[lines.length - 1]
    if (last && (last + ' ' + w).length <= 22) lines[lines.length - 1] = `${last} ${w}`
    else lines.push(w)
  }
  return (
    <text x={x - 6} y={y} textAnchor="end" fill={AXIS.tick.fill} fontSize={11}>
      {lines.map((l, i) => (
        <tspan key={i} x={x - 6} dy={i === 0 ? `${0.35 - (lines.length - 1) * 0.55}em` : '1.1em'}>
          {l}
        </tspan>
      ))}
    </text>
  )
}

/** Подпись на оси X: числа по-русски (запятая, минус «−»), в текстовых интервалах — тоже. */
function axisTick(v: unknown): string {
  if (typeof v === 'number') return num(v, Number.isInteger(v) ? 0 : Math.min(2, String(v).split('.')[1]?.length ?? 2))
  return String(v)
    .replace(/(\d)\.(\d)/g, '$1,$2')
    .replace(/(^|[\s([–—])-(?=\d)/g, '$1−')
}

function fmt(v: unknown, percent?: boolean): string {
  if (typeof v !== 'number') return String(v)
  return percent ? pct(v, v < 0.995 && v > 0.005 && Math.round(v * 100) !== v * 100 ? 1 : 0) : num(v, Number.isInteger(v) ? 0 : 2)
}

/** Универсальный рендер графика валидации по chart_type (bar / histogram / line / scatter). */
export function ValidationChartView({ chart, options = {} }: { chart: ValidationChart; options?: ChartViewOptions }) {
  const { percent, height = 260, referenceY, diagonal, yDomain, thresholds = [] } = options
  const yTick = (v: number) => (percent ? `${Math.round(v * 100)}%` : num(v, Number.isInteger(v) ? 0 : Math.abs(v) < 1 ? 2 : 1))
  const multi = chart.series.length > 1
  const colors = seriesColors(chart.series.map((s) => s.name))

  if (chart.chart_type === 'scatter') {
    const all = chart.series.flatMap((s) => s.points)
    const xs = all.map((p) => Number(p.x))
    const ys = all.map((p) => p.y)
    const lo = Math.floor(Math.min(...xs, ...(diagonal ? ys : [])) * 2) / 2
    const hi = Math.ceil(Math.max(...xs, ...(diagonal ? ys : [])) * 2) / 2
    return (
      <ChartBox height={height} label={`${chart.title}: ${chart.x_label} против ${chart.y_label}`}>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 4 }}>
          <CartesianGrid {...GRID} />
          <XAxis type="number" dataKey="x" name={chart.x_label} domain={diagonal ? [lo, hi] : ['auto', 'auto']} {...AXIS} tickFormatter={axisTick}
            label={{ value: chart.x_label, position: 'insideBottom', offset: -16, ...AXIS_LABEL }} />
          <YAxis type="number" dataKey="y" name={chart.y_label} domain={diagonal ? [lo, hi] : yDomain ?? ['auto', 'auto']} width={44} {...AXIS} tickFormatter={yTick} />
          <Tooltip {...TOOLTIP_STYLE} cursor={{ strokeDasharray: '3 3' }} formatter={(v) => fmt(v, percent)} />
          {thresholds.flatMap((t) => [
            <ReferenceLine key={`x${t}`} x={t} stroke={AXIS.stroke} />,
            <ReferenceLine key={`y${t}`} y={t} stroke={AXIS.stroke} />,
          ])}
          {diagonal && (
            <ReferenceLine segment={[{ x: lo, y: lo }, { x: hi, y: hi }]} stroke={NEUTRAL} strokeDasharray="5 4" ifOverflow="extendDomain" />
          )}
          {referenceY && (
            <ReferenceLine y={referenceY.y} stroke={REFERENCE} strokeDasharray="5 4"
              label={{ value: referenceY.label, position: 'insideBottomRight', fill: REFERENCE, fontSize: 11 }} />
          )}
          {chart.series.map((s, i) => (
            <Scatter key={s.name} name={s.name} data={s.points} fill={colors[i]} fillOpacity={0.7} stroke="#fff" strokeWidth={1} />
          ))}
        </ScatterChart>
      </ChartBox>
    )
  }

  // bar / histogram / line: точки серий сводим в строки по x.
  const xs: Array<string | number> = []
  for (const s of chart.series) for (const p of s.points) if (!xs.includes(p.x)) xs.push(p.x)
  const rows = xs.map((x) => {
    const row: Record<string, string | number> = { x }
    for (const s of chart.series) {
      const p = s.points.find((pt) => pt.x === x)
      if (p) row[s.name] = p.y
    }
    return row
  })
  const longLabels = xs.some((x) => String(x).length > 14)
  const labelBars = xs.length * chart.series.length <= 12

  if (chart.chart_type === 'line') {
    return (
      <ChartBox height={height} label={chart.title}>
        <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 28, left: 4 }}>
          <CartesianGrid {...GRID} vertical={false} />
          <XAxis dataKey="x" {...AXIS} tickFormatter={axisTick} label={{ value: chart.x_label, position: 'insideBottom', offset: -16, ...AXIS_LABEL }} />
          <YAxis width={44} {...AXIS} tickFormatter={yTick} domain={yDomain ?? ['auto', 'auto']} />
          <Tooltip {...TOOLTIP_STYLE} formatter={(v) => fmt(v, percent)} labelFormatter={(l) => `${chart.x_label}: ${axisTick(l)}`} />
          {multi && <Legend itemSorter={null} verticalAlign="top" height={28} iconType="plainline" wrapperStyle={{ fontSize: 12 }} />}
          {chart.series.map((s, i) => (
            <Line key={s.name} type="monotone" dataKey={s.name} stroke={colors[i]} strokeWidth={2}
              dot={{ r: 4, fill: colors[i], stroke: '#fff', strokeWidth: 2 }} activeDot={{ r: 6 }} />
          ))}
        </LineChart>
      </ChartBox>
    )
  }

  // Длинные подписи категорий не помещаются под столбцами — кладём столбцы горизонтально, подписи слева.
  if (longLabels && chart.chart_type === 'bar') {
    const perCategory = chart.series.length * 16 + 18
    const h = Math.max(height, xs.length * perCategory + (multi ? 64 : 36))
    return (
      <ChartBox height={h} label={chart.title}>
        <BarChart layout="vertical" data={rows} margin={{ top: 4, right: 48, bottom: 8, left: 4 }} barGap={2} barCategoryGap="18%">
          <CartesianGrid {...GRID} horizontal={false} />
          <XAxis type="number" {...AXIS} tickFormatter={yTick} domain={yDomain ?? (percent ? [0, 1] : [0, 'auto'])} />
          <YAxis type="category" dataKey="x" width={150} interval={0} {...AXIS} tick={<WrappedTick />} />
          <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: CURSOR_FILL }} formatter={(v) => fmt(v, percent)} />
          {multi && <Legend itemSorter={null} verticalAlign="top" height={28} iconType="square" wrapperStyle={{ fontSize: 12 }} />}
          {chart.series.map((s, i) => (
            <Bar key={s.name} dataKey={s.name} fill={colors[i]} radius={[0, 4, 4, 0]} maxBarSize={14}>
              <LabelList dataKey={s.name} position="right" {...VALUE_LABEL} formatter={(v: unknown) => fmt(v, percent)} />
            </Bar>
          ))}
        </BarChart>
      </ChartBox>
    )
  }

  const dense = chart.chart_type === 'histogram' && xs.length > 8
  return (
    <ChartBox height={height} label={chart.title}>
      <BarChart data={rows} margin={{ top: labelBars ? 20 : 8, right: 8, bottom: longLabels ? 8 : 28, left: 4 }} barGap={2} barCategoryGap={chart.chart_type === 'histogram' ? 2 : '22%'}>
        <CartesianGrid {...GRID} vertical={false} />
        <XAxis dataKey="x" {...AXIS} interval={dense ? 1 : 0} height={longLabels ? 48 : 30} tickFormatter={axisTick}
          tick={longLabels || dense ? { ...AXIS.tick, fontSize: 11 } : AXIS.tick}
          label={longLabels ? undefined : { value: chart.x_label, position: 'insideBottom', offset: -16, ...AXIS_LABEL }} />
        <YAxis width={44} {...AXIS} tickFormatter={yTick} domain={yDomain ?? (percent ? [0, 1] : [0, 'auto'])} />
        <Tooltip {...TOOLTIP_STYLE} cursor={{ fill: CURSOR_FILL }} formatter={(v) => fmt(v, percent)} />
        {multi && <Legend itemSorter={null} verticalAlign="top" height={28} iconType="square" wrapperStyle={{ fontSize: 12 }} />}
        {referenceY && <ReferenceLine y={referenceY.y} stroke={REFERENCE} strokeDasharray="5 4" />}
        {chart.series.map((s, i) => (
          <Bar key={s.name} dataKey={s.name} fill={colors[i]} radius={[4, 4, 0, 0]} maxBarSize={chart.chart_type === 'histogram' ? 48 : 40}>
            {/* Подписи значений: светлые цвета палитры (оранжевый, голубой) не дотягивают до контраста 3:1 с фоном. */}
            {labelBars && <LabelList dataKey={s.name} position="top" {...VALUE_LABEL} formatter={(v: unknown) => fmt(v, percent)} />}
          </Bar>
        ))}
      </BarChart>
    </ChartBox>
  )
}
