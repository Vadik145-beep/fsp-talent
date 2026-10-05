import { useEffect, useRef, useState } from 'react'
import { Clock } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { formatDuration } from '@/shared/lib/format'

export interface TimerProps {
  /** Сколько секунд на задачу. Смена значения (или key) перезапускает таймер. */
  durationSec: number
  /** Когда время вышло. */
  onExpire?: () => void
  paused?: boolean
  /** С какого остатка (сек) подсвечивать предупреждением. По умолчанию — последние 20 %. */
  warnAtSec?: number
  className?: string
}

/** Обратный отсчёт для задачи теста. Считает от реального времени, а не по «тикам». */
export function Timer({ durationSec, onExpire, paused, warnAtSec, className }: TimerProps) {
  const [left, setLeft] = useState(durationSec)
  const [prevDuration, setPrevDuration] = useState(durationSec)
  const remainingRef = useRef(durationSec)
  const expiredRef = useRef(false)
  const onExpireRef = useRef(onExpire)

  // Новая длительность — начать заново (корректировка состояния во время рендера).
  if (prevDuration !== durationSec) {
    setPrevDuration(durationSec)
    setLeft(durationSec)
  }

  useEffect(() => {
    onExpireRef.current = onExpire
  }, [onExpire])

  useEffect(() => {
    remainingRef.current = durationSec
    expiredRef.current = false
  }, [durationSec])

  useEffect(() => {
    if (paused) return
    // Продолжаем с остатка (после паузы) или с начала (новая длительность).
    const end = Date.now() + remainingRef.current * 1000
    const tick = () => {
      const rest = Math.max(0, Math.ceil((end - Date.now()) / 1000))
      remainingRef.current = rest
      setLeft(rest)
      if (rest === 0 && !expiredRef.current) {
        expiredRef.current = true
        onExpireRef.current?.()
      }
    }
    const t = setInterval(tick, 250)
    return () => clearInterval(t)
  }, [paused, durationSec])

  const warnAt = warnAtSec ?? Math.max(10, Math.round(durationSec * 0.2))
  const state = left === 0 ? 'over' : left <= warnAt ? 'warn' : 'ok'

  return (
    <div
      role="timer"
      aria-label={`Осталось ${formatDuration(left)}`}
      className={cn(
        'inline-flex items-center gap-2 rounded-full px-3 py-1.5 font-mono text-base font-semibold tabular-nums transition-colors',
        state === 'ok' && 'bg-violet-soft text-fsp-plum',
        state === 'warn' && 'bg-warning-soft text-warning',
        state === 'over' && 'bg-danger-soft text-danger',
        className,
      )}
    >
      <Clock className={cn('size-4', state === 'warn' && 'animate-pulse')} aria-hidden />
      {formatDuration(left)}
    </div>
  )
}
