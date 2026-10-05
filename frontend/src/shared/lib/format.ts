const NBSP = '\u00A0'

/** 250000 → «250 000» (неразрывные пробелы между разрядами). */
export function formatNumber(value: number): string {
  const sign = value < 0 ? '-' : ''
  const [int, frac] = Math.abs(value).toString().split('.')
  const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP)
  return sign + grouped + (frac ? ',' + frac : '')
}

/** 250000 → «250 000 ₽». */
export function formatMoney(value: number, currency = '₽'): string {
  return `${formatNumber(Math.round(value))}${NBSP}${currency}`
}

/**
 * Вилка зарплаты: «от 250 000 до 350 000 ₽», «от 250 000 ₽», «до 350 000 ₽».
 * Если границ нет — «Зарплата не указана».
 */
export function formatSalaryRange(
  from?: number | null,
  to?: number | null,
  currency = '₽',
): string {
  const hasFrom = typeof from === 'number'
  const hasTo = typeof to === 'number'
  if (hasFrom && hasTo) {
    if (from === to) return formatMoney(from, currency)
    return `от ${formatNumber(from)} до ${formatNumber(to)}${NBSP}${currency}`
  }
  if (hasFrom) return `от ${formatMoney(from, currency)}`
  if (hasTo) return `до ${formatMoney(to, currency)}`
  return 'Зарплата не указана'
}

/** 0.324 → «+0,32»; знак показывается всегда. */
export function formatSigned(value: number, digits = 2): string {
  const s = Math.abs(value).toFixed(digits).replace('.', ',')
  return (value < 0 ? '−' : '+') + s
}

/** 0.873 → «87 %». */
export function formatPercent(value: number, digits = 0): string {
  return `${(value * 100).toFixed(digits).replace('.', ',')}${NBSP}%`
}

/** Секунды → «mm:ss» (или «h:mm:ss», если больше часа). */
export function formatDuration(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const pad = (n: number) => n.toString().padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(sec)}` : `${pad(m)}:${pad(sec)}`
}

/** ISO-дата → «6 октября 2026 г.». */
export function formatDate(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

/** ISO-дата → «06.10.2026, 14:05». */
export function formatDateTime(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso
  return d.toLocaleString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

/** Склонение: plural(5, ['кандидат', 'кандидата', 'кандидатов']) → «кандидатов». */
export function plural(n: number, forms: [string, string, string]): string {
  const n10 = Math.abs(n) % 10
  const n100 = Math.abs(n) % 100
  if (n10 === 1 && n100 !== 11) return forms[0]
  if (n10 >= 2 && n10 <= 4 && (n100 < 12 || n100 > 14)) return forms[1]
  return forms[2]
}
