/** Чистые помощники кабинета рекрутера (без React). */

/** θ → доля прошедших тест с уровнем ниже (θ в шкале IRT ~ N(0, 1)). */
export function thetaPercentile(theta: number): number {
  const z = Math.abs(theta) / Math.SQRT2
  const t = 1 / (1 + 0.3275911 * z)
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-z * z)
  return 0.5 * (1 + (theta < 0 ? -1 : 1) * y)
}

export function thetaLevel(theta: number): string {
  if (theta < -1) return 'начальный уровень'
  if (theta < 0) return 'чуть ниже среднего'
  if (theta < 1) return 'выше среднего'
  return 'высокий уровень'
}

export function thetaSummary(theta: number | null | undefined): string {
  if (theta == null) return 'Тест не пройден'
  return `Сильнее, чем ${Math.round(thetaPercentile(theta) * 100)} % прошедших тест`
}
