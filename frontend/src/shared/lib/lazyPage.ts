import type { ComponentType } from 'react'
import type { RouteObject } from 'react-router'

const RELOAD_KEY = 'fsp.chunkReloadAt'

/**
 * Если после выкладки новой версии старая вкладка просит уже удалённый чанк,
 * один раз перезагружаем страницу (не чаще раза в минуту, чтобы не зациклиться).
 */
function reloadOnceForNewVersion(error: unknown): never {
  let last = 0
  try {
    last = Number(window.sessionStorage.getItem(RELOAD_KEY) ?? 0)
  } catch {
    // хранилище недоступно — просто не перезагружаем повторно
  }
  if (Date.now() - last > 60_000) {
    try {
      window.sessionStorage.setItem(RELOAD_KEY, String(Date.now()))
    } catch {
      // без хранилища перезагрузка всё равно поможет
    }
    window.location.reload()
  }
  throw error
}

/**
 * Ленивая загрузка страницы маршрута (отдельный чанк на экран).
 * Пример: { path: 'profile', ...lazyPage(() => import('./ProfilePage')) }
 */
export function lazyPage(
  load: () => Promise<{ default: ComponentType }>,
): Pick<RouteObject, 'lazy'> {
  return {
    lazy: async () => {
      try {
        return { Component: (await load()).default }
      } catch (error) {
        return reloadOnceForNewVersion(error)
      }
    },
  }
}
