import type { LucideIcon } from 'lucide-react'

/** Пункт бокового меню кабинета. Списки лежат в src/pages/<role>/nav.ts. */
export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Активен только при точном совпадении пути (для «Главной»). */
  end?: boolean
}

/**
 * handle маршрута (route.handle). Читается layout'ом кабинета.
 * focus: true — экран без бокового меню (мастер онбординга, прохождение теста).
 */
export interface RouteHandle {
  focus?: boolean
}
