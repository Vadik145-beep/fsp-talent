import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

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
