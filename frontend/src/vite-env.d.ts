/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 'false' — выключить моки и ходить в настоящий API. По умолчанию моки включены. */
  readonly VITE_USE_MOCKS?: string
  /** База API для fetch-клиента. По умолчанию '/api'. */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
