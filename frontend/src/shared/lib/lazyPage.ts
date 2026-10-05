import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router'

/**
 * Ленивая загрузка страницы маршрута (отдельный чанк на экран).
 * Пример: { path: 'profile', ...lazyPage(() => import('./ProfilePage')) }
 */
export function lazyPage(
  load: () => Promise<{ default: ComponentType }>,
): Pick<RouteObject, 'lazy'> {
  return {
    lazy: async () => ({ Component: (await load()).default }),
  }
}
