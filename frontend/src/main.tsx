import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { USE_MOCKS } from '@/shared/config/env'
import { App } from '@/app/App'

async function bootstrap() {
  if (USE_MOCKS) {
    const { startMocks } = await import('@/mocks/browser')
    await startMocks()
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <App />
    </StrictMode>,
  )
}

void bootstrap()
