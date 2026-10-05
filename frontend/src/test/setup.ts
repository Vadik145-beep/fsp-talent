import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// Моки отвечают с задержкой «как у сети» (250–450 мс), а при параллельном прогоне
// тяжёлые экраны рендерятся дольше: стандартной секунды ожидания findBy не хватает.
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
  try {
    window.localStorage.clear()
  } catch {
    // нет хранилища — не страшно
  }
})

// jsdom не умеет scrollTo — layout кабинета вызывает его при смене экрана.
window.scrollTo = (() => {}) as typeof window.scrollTo
