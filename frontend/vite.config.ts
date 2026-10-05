/// <reference types="vitest/config" />
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const root = fileURLToPath(new URL('.', import.meta.url))
const seedDir = fileURLToPath(new URL('../data/seed', import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, root, '')
  // Куда проксировать /api, когда моки выключены. Локально — бэкенд на хосте,
  // в docker compose задаётся VITE_PROXY_TARGET=http://backend:8000.
  const proxyTarget = env.VITE_PROXY_TARGET || 'http://localhost:18000'

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
        '@seed': seedDir,
      },
    },
    server: {
      port: 15173,
      strictPort: true,
      fs: { allow: [root, seedDir] },
      proxy: {
        '/api': { target: proxyTarget, changeOrigin: true },
      },
    },
    preview: { port: 15173 },
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      css: false,
    },
  }
})
