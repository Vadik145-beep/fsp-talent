import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { db } from '@/mocks/db'
import { adminHandlers } from '@/mocks/handlers/admin'
import { publicHandlers } from '@/mocks/handlers/public'
import { renderApp } from '@/test/renderApp'
import type { VacancyTestResult } from './api'

// Черновик задачи от локальной нейросети: пометка модели, варианты с правильным ответом, объяснение.
const LLM_RESULT: VacancyTestResult = {
  id: 501,
  vacancy_title: 'Senior Go-разработчик (платформа)',
  vacancy_text: 'Senior Go-разработчик (платформа)\nПишем сервисы на Go, общаемся по gRPC и protobuf.',
  specialization: 'backend',
  grade: 'senior',
  parser: 'llm',
  topics: [{ topic: 'backend.grpc', label: 'gRPC и контракты API', matched_by: ['gRPC', 'protobuf'], confidence: 0.85, covered: false }],
  items: [],
  drafts: [
    {
      item_id: 9001,
      topic: 'backend.grpc',
      label: 'gRPC и контракты API',
      title: 'Обратная совместимость protobuf',
      format: 'single_choice',
      prompt: 'Что нельзя делать с полем сообщения protobuf, чтобы не сломать старых клиентов?',
      status: 'draft',
      origin: 'llm',
      reused: false,
      options: ['Добавлять новое поле', 'Менять номер поля', 'Менять комментарий', 'Переименовывать поле'],
      answer: 'Менять номер поля',
      explanation: 'Клиенты читают поля по номеру.',
      model: 'Qwen2.5-1.5B',
      model_local: true,
    },
  ],
  explanation: ['Черновики написала нейросеть Qwen2.5-1.5B локально на нашем сервере'],
  created_at: '2026-10-10T12:00:00+03:00',
}

const server = setupServer(...publicHandlers, ...adminHandlers)
let originalFetch: typeof fetch
beforeAll(() => {
  server.listen({ onUnhandledRequest: 'bypass' })
  originalFetch = globalThis.fetch
  globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) =>
    originalFetch(typeof input === 'string' && input.startsWith('/') ? `${window.location.origin}${input}` : input, init)) as typeof fetch
})
beforeEach(() => db.reset())
afterEach(() => server.resetHandlers())
afterAll(() => {
  globalThis.fetch = originalFetch
  server.close()
})

describe('задания из вакансий: черновик от нейросети', () => {
  it('показывает пометку модели, варианты с правильным ответом и объяснение', async () => {
    server.use(http.post('*/api/admin/vacancy-tests', () => HttpResponse.json(LLM_RESULT)))
    renderApp('/admin/vacancy-tests', { role: 'admin' })
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Текст вакансии', {}, { timeout: 8000 }), LLM_RESULT.vacancy_text)
    await user.click(screen.getByRole('button', { name: 'Сформировать тест' }))

    expect(await screen.findByText('Написано нейросетью Qwen2.5-1.5B (локально на сервере)', {}, { timeout: 8000 })).toBeInTheDocument()
    const options = screen.getByRole('list', { name: 'Варианты ответа' })
    expect(within(options).getAllByRole('listitem')).toHaveLength(4)
    expect(within(options).getByText('— правильный ответ', { exact: false }).closest('li')).toHaveTextContent('Менять номер поля')
    expect(screen.getByText('Клиенты читают поля по номеру.')).toBeInTheDocument()
    expect(screen.getByText(/черновики новых задач написала нейросеть/)).toBeInTheDocument()
  }, 20_000)
})
