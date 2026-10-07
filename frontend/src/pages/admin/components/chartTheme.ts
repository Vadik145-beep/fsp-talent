/**
 * Общие настройки графиков админки в цветах ФСП.
 *
 * Палитра предложена треком ребрендинга (фирменный #402FFF + цвета Okabe–Ito, различимые при дальтонизме).
 * Recharts рисует SVG и принимает цвет строкой, поэтому значения здесь — hex; совпадающие с токенами
 * index.css отмечены в комментариях. Для обычной вёрстки (теплокарта, полоски) — классы токенов Tailwind.
 *
 * Проверка валидатором dataviz (OKLab, модель Machado 2009), фон белый:
 *   - #402FFF, #E69F00, #009E73, #56B4E9: яркость и цветность в норме; худшая соседняя пара при
 *     протанопии ΔE 11,4 (цель ≥ 8), при обычном зрении ΔE 18,4 (порог 15); первые три различимы
 *     попарно (точечные графики) — ΔE 11,4;
 *   - контраст с белым: #402FFF 6,8; #009E73 3,4; #EC1D35 4,4; #55565E 7,3 — ≥ 3:1.
 *     #E69F00 (2,25) и #56B4E9 (2,31) ниже 3:1 — поэтому на графиках с ними есть легенда, подписи
 *     значений на столбцах и ключевые числа над графиком.
 */

/** Категориальные цвета: цвет закреплён за порядком серии, не за значением. */
export const CHART_COLORS = [
  '#402FFF', // --color-fsp-blue
  '#E69F00',
  '#009E73',
  '#56B4E9',
]

/** Фирменный цвет — основная (единственная) серия. */
export const BRAND = '#402FFF' // --color-fsp-blue
/** Красный ФСП — только «плохо / утечка / отклонено / без защиты». */
export const BAD = '#EC1D35' // --color-fsp-red
/** Нейтральный: ориентир (поиск по словам), «истекло», «отозвано». */
export const NEUTRAL = '#55565E' // --color-muted

/** Шесть различимых цветов для составных полосок (веса ранжирования): палитра + нейтральный + светло-синий. */
export const SIX_COLORS = [...CHART_COLORS, NEUTRAL, '#7D72FF' /* --color-fsp-blue-light */]

/** Цвета статусов приглашений: принято — зелёный, отклонено — красный, истекло/отозвано — нейтральные. */
export const INVITATION_STATUS_COLORS: Record<string, string> = {
  sent: '#56B4E9',
  viewed: BRAND,
  accepted: '#009E73',
  declined: BAD,
  expired: NEUTRAL,
  withdrawn: '#E69F00',
}

/**
 * Цвета серий графика валидации: «без защиты» — красный, ориентир (поиск по ключевым словам) —
 * нейтральный, остальные — по порядку палитры, начиная с фирменного.
 */
export function seriesColors(names: string[]): string[] {
  let next = 0
  return names.map((name) => {
    const n = name.toLowerCase()
    if (n.startsWith('без защиты')) return BAD
    if (n.includes('ключевые слова') || n.includes('поиск по словам')) return NEUTRAL
    return CHART_COLORS[Math.min(next++, CHART_COLORS.length - 1)]
  })
}

const INK = '#1B1C21' // --color-ink / --color-fsp-black
const MUTED = '#55565E' // --color-muted

export const AXIS = { stroke: '#C8C9CA' /* --color-line-strong */, tick: { fill: MUTED, fontSize: 12 } }
export const AXIS_LABEL = { fill: MUTED, fontSize: 12 }
export const GRID = { stroke: '#EDEDED' /* --color-fsp-gray */, strokeDasharray: '0' }
export const REFERENCE = INK
export const VALUE_LABEL = { fill: INK, fontSize: 11 }
export const CURSOR_FILL = 'rgb(64 47 255 / 0.06)'
export const TOOLTIP_STYLE = {
  contentStyle: { borderRadius: 8, border: '1px solid #C8C9CA', fontSize: 13, boxShadow: '0 4px 14px rgb(27 28 33 / .10)' },
  labelStyle: { color: INK, fontWeight: 600 },
  itemStyle: { color: INK },
}
