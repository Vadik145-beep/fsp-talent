import { act, renderHook } from '@testing-library/react'
import { useFieldErrors } from './useFieldErrors'

interface V {
  title: string
  from: number | null
  to: number | null
}
type K = 'title' | 'from' | 'to'

function validate(v: V) {
  const e: Partial<Record<K, string>> = {}
  if (v.title.length < 3) e.title = 'Коротко'
  if (!v.from) e.from = 'Укажите «от»'
  if (v.from && v.to && v.from > v.to) e.from = '«От» больше «до»'
  return e
}

describe('useFieldErrors', () => {
  it('до отправки правка поля только снимает его ошибку', () => {
    const { result } = renderHook(() => useFieldErrors<V, K>(validate, [['from', 'to']]))
    act(() => result.current.setErrors({ title: 'С сервера' }))
    act(() => result.current.touch('title', { title: 'a', from: null, to: null }))
    expect(result.current.errors).toEqual({})
  })

  it('после первой отправки поля проверяются на лету, пара «от/до» — вместе', () => {
    const { result } = renderHook(() => useFieldErrors<V, K>(validate, [['from', 'to']]))
    let ok = true
    act(() => {
      ok = result.current.check({ title: 'ab', from: 300, to: 200 })
    })
    expect(ok).toBe(false)
    expect(result.current.errors).toEqual({ title: 'Коротко', from: '«От» больше «до»' })
    // правка «до» снимает ошибку пары на «от»
    act(() => result.current.touch('to', { title: 'ab', from: 300, to: 400 }))
    expect(result.current.errors).toEqual({ title: 'Коротко' })
    // и снова ставит её, если пара опять неверна
    act(() => result.current.touch('to', { title: 'ab', from: 300, to: 100 }))
    expect(result.current.errors.from).toBe('«От» больше «до»')
    act(() => result.current.touch('title', { title: 'abc', from: 300, to: 100 }))
    expect(result.current.errors.title).toBeUndefined()
  })
})
