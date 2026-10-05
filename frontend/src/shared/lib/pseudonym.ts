/**
 * Код псевдонима кандидата для обезличенного профиля: 4 hex-символа из id («A7F2»).
 * Если бэкенд отдаёт свой код — используйте его; это запасной вариант для моков.
 */
export function pseudonymCode(id: string | number): string {
  const str = String(id)
  let h = 2166136261
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return ((h >>> 0) & 0xffff).toString(16).toUpperCase().padStart(4, '0')
}
