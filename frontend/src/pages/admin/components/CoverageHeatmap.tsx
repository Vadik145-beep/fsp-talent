import { Fragment } from 'react'
import { Link } from 'react-router'
import { cn } from '@/shared/lib/cn'
import { GRADES, GRADE_LABELS, SPECIALIZATIONS, SPECIALIZATION_LABELS } from '@/shared/config/dictionaries'
import { plural } from '@/shared/lib/format'
import type { CoverageCell } from '../api'

/** Последовательная шкала фирменного синего на токенах: светлее — меньше шаблонов, 0 — пустая клетка с пунктиром. */
const STEPS = [
  { min: 0, cls: 'bg-surface-muted border-dashed border-line-strong text-subtle' },
  { min: 1, cls: 'bg-fsp-blue-pale border-fsp-blue-pale text-fsp-blue-deep' },
  { min: 2, cls: 'bg-fsp-blue-light border-fsp-blue-light text-fsp-black' },
  { min: 3, cls: 'bg-fsp-blue border-fsp-blue text-on-primary' },
  { min: 5, cls: 'bg-fsp-blue-deep border-fsp-blue-deep text-on-primary' },
]

function stepFor(n: number) {
  return [...STEPS].reverse().find((s) => n >= s.min) ?? STEPS[0]
}

export function CoverageHeatmap({ cells, specialization }: { cells: CoverageCell[]; specialization?: string }) {
  const specs = SPECIALIZATIONS.filter((s) => !specialization || s === specialization)
  const visible = cells.filter((c) => specs.includes(c.specialization))
  const empty = visible.filter((c) => c.active === 0).length

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-muted">
          Клетка — сколько <b className="text-ink">активных</b> шаблонов есть по теме для грейда. Пустых клеток:{' '}
          <b className="text-ink">{empty}</b> из {visible.length} — туда нужно добавить шаблоны (вручную или из вакансий).
        </p>
        <div className="flex items-center gap-1.5 text-xs text-muted" aria-label="Легенда">
          <span>0</span>
          {STEPS.map((s) => (
            <span key={s.min} className={cn('size-4 rounded-xs border', s.cls)} aria-hidden />
          ))}
          <span>5+</span>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line bg-surface">
        <table className="w-full min-w-[560px] border-separate border-spacing-1 p-2 text-sm">
          <caption className="sr-only">Покрытие банка задач: темы по строкам, грейды по столбцам</caption>
          <thead>
            <tr>
              <th scope="col" className="px-2 py-1 text-left text-xs font-semibold tracking-wide text-muted uppercase">
                Тема
              </th>
              {GRADES.map((g) => (
                <th key={g} scope="col" className="w-[17%] px-2 py-1 text-center text-xs font-semibold tracking-wide text-muted uppercase">
                  {GRADE_LABELS[g]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {specs.map((spec) => {
              const topics = [...new Map(visible.filter((c) => c.specialization === spec).map((c) => [c.topic, c.topic_label])).entries()]
              if (!topics.length) return null
              return (
                <Fragment key={spec}>
                  {!specialization && (
                    <tr>
                      <th colSpan={5} scope="rowgroup" className="px-2 pt-3 pb-1 text-left text-[13px] font-semibold text-fsp-plum">
                        {SPECIALIZATION_LABELS[spec]}
                      </th>
                    </tr>
                  )}
                  {topics.map(([topic, label]) => (
                    <tr key={topic}>
                      <th scope="row" className="max-w-56 px-2 py-1 text-left font-medium text-ink">
                        {label}
                      </th>
                      {GRADES.map((g) => {
                        const c = visible.find((x) => x.topic === topic && x.grade === g)
                        const active = c?.active ?? 0
                        const pilot = c?.pilot ?? 0
                        const st = stepFor(active)
                        const text = `${label}, ${GRADE_LABELS[g]}: ${active} ${plural(active, ['активный шаблон', 'активных шаблона', 'активных шаблонов'])}${pilot ? `, ${pilot} в пилоте` : ''}`
                        return (
                          <td key={g} className="p-0">
                            <Link
                              to={`/admin/items?specialization=${spec}&topic=${encodeURIComponent(topic)}&grade=${g}`}
                              title={text}
                              aria-label={text}
                              className={cn(
                                'flex h-11 flex-col items-center justify-center rounded-sm border text-base font-bold tabular-nums transition-[filter] hover:brightness-95 focus-visible:shadow-[var(--shadow-focus)] focus-visible:outline-none',
                                st.cls,
                              )}
                            >
                              {active}
                              {pilot > 0 && <span className="text-[10px] leading-none font-semibold">+{pilot} пилот</span>}
                            </Link>
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </Fragment>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
