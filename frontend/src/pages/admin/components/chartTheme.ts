/**
 * Общие настройки графиков админки в цветах ФСП (брендбук: #402FFF, #EC1D35, #EDEDED, #C8C9CA, #1B1C21).
 *
 * Категориальная палитра: первый цвет — фирменный #402FFF, остальные подобраны так, чтобы
 * соседние серии различались при протанопии и дейтеранопии. Проверено валидатором dataviz
 * (OKLab, модель Machado 2009) на белом фоне:
 *   - яркость L 0.43–0.77 и цветность C ≥ 0.10 у всех 6 цветов;
 *   - худшая соседняя пара при дальтонизме ΔE 9,1 (цель ≥ 8), при обычном зрении ΔE 22,1 (порог 15);
 *   - первые три цвета различимы попарно (для точечных графиков): ΔE 11,2;
 *   - контраст с белым ≥ 3:1 у всех (#402FFF 6,8; #C77700 3,5; #0B8A7A 4,3; #9C3FA8 5,7; #2B8FD6 3,5; #6F7F00 4,5).
 * Цвет закреплён за порядком серии, не за значением.
 */
export const CHART_COLORS = ['#402FFF', '#C77700', '#0B8A7A', '#9C3FA8', '#2B8FD6', '#6F7F00']

/** Фирменный цвет — основная (единственная) серия. */
export const BRAND = '#402FFF'
/** Красный ФСП — только для «плохо / утечка / без защиты». Контраст с белым 4,4. */
export const BAD = '#EC1D35'
/** Нейтральный для серии-ориентира (поиск по словам, базовая линия). Контраст с белым 4,2. */
export const BASELINE = '#7A7C82'

/**
 * Последовательная шкала одного оттенка (#402FFF): светлее — меньше. Для теплокарты покрытия и долей грейдов.
 * text — цвет подписи поверх заливки (контраст ≥ 4,5).
 */
export const BRAND_RAMP = [
  { bg: '#E4E1FF', text: '#2A1DB8' },
  { bg: '#C3BCFF', text: '#1B1C21' },
  { bg: '#9A8FFF', text: '#1B1C21' },
  { bg: '#6E60FF', text: '#FFFFFF' },
  { bg: '#402FFF', text: '#FFFFFF' },
  { bg: '#2A1DB8', text: '#FFFFFF' },
]

/**
 * Цвета серий графика: «без защиты» — красный, ориентир (поиск по ключевым словам) — серый,
 * остальные — по порядку палитры, начиная с фирменного.
 */
export function seriesColors(names: string[]): string[] {
  let next = 0
  return names.map((name) => {
    const n = name.toLowerCase()
    if (n.startsWith('без защиты')) return BAD
    if (n.includes('ключевые слова') || n.includes('поиск по словам')) return BASELINE
    return CHART_COLORS[Math.min(next++, CHART_COLORS.length - 1)]
  })
}

export const AXIS = { stroke: '#C8C9CA', tick: { fill: '#55565C', fontSize: 12 } }
export const AXIS_LABEL = { fill: '#55565C', fontSize: 12 }
export const GRID = { stroke: '#EDEDED', strokeDasharray: '0' }
export const CURSOR_FILL = 'rgb(64 47 255 / 0.06)'
export const TOOLTIP_STYLE = {
  contentStyle: { borderRadius: 8, border: '1px solid #C8C9CA', fontSize: 13, boxShadow: '0 4px 14px rgb(27 28 33 / .10)' },
  labelStyle: { color: '#1B1C21', fontWeight: 600 },
  itemStyle: { color: '#1B1C21' },
}
