/** localStorage, который не падает в приватном режиме или при заблокированном хранилище. */
export function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) window.localStorage.removeItem(key)
    else window.localStorage.setItem(key, value)
  } catch {
    // хранилище недоступно — просто не запоминаем
  }
}
