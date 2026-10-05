/** Общие настройки графиков админки (палитра, оси, сетка, подсказки). */
/**
 * Категориальная палитра графиков (проверена валидатором dataviz: яркость, цветность,
 * различимость при дальтонизме, контраст ≥ 3:1 на белом). Цвет закреплён за порядком серии.
 */
export const CHART_COLORS = ['#6B3FC4', '#E0004B', '#00897B', '#C27100', '#2F7FD1']
export const AXIS = { stroke: '#cfcadb', tick: { fill: '#5c5869', fontSize: 12 } }
export const GRID = { stroke: '#ece9f2', strokeDasharray: '0' }
export const TOOLTIP_STYLE = {
  contentStyle: { borderRadius: 10, border: '1px solid #e6e3ee', fontSize: 13, boxShadow: '0 4px 14px rgb(49 15 83 / .12)' },
  labelStyle: { color: '#1c1d22', fontWeight: 600 },
  itemStyle: { color: '#1c1d22' },
}
