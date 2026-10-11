import { useState } from 'react'

export type FieldErrors<K extends string> = Partial<Record<K, string>>

/**
 * Ошибки полей формы — как в окне приглашения: ошибка поля уходит при его правке, а после
 * первой попытки отправить форму поле проверяется на лету. Поля одной группы (вилка «от/до»)
 * пересчитываются вместе: поправили «до» — ошибка пары на «от» тоже обновится.
 */
export function useFieldErrors<V, K extends string>(validate: (values: V) => FieldErrors<K>, groups: K[][] = []) {
  const [errors, setErrors] = useState<FieldErrors<K>>({})
  const [submitted, setSubmitted] = useState(false)

  /** Поле изменилось; `values` — форма уже с новым значением. */
  function touch(field: K, values: V) {
    const fields = groups.find((g) => g.includes(field)) ?? [field]
    setErrors((prev) => {
      const next = { ...prev }
      for (const f of fields) delete next[f]
      if (!submitted) return next
      const fresh = validate(values)
      for (const f of fields) if (fresh[f]) next[f] = fresh[f]
      return next
    })
  }

  /** Проверка перед отправкой: true — ошибок нет, можно отправлять. */
  function check(values: V): boolean {
    const next = validate(values)
    setSubmitted(true)
    setErrors(next)
    return Object.keys(next).length === 0
  }

  return { errors, setErrors, touch, check }
}
