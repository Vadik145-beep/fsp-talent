/** Моки MSW включены, если VITE_USE_MOCKS не равен 'false' (прототип запускается без бэкенда). */
export const USE_MOCKS = import.meta.env.VITE_USE_MOCKS !== 'false'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export const APP_NAME = 'ФСП · Таланты'
