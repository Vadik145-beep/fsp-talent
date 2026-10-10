import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { setupServer } from 'msw/node'
import { afterAll, beforeAll, beforeEach, describe, expect, it } from 'vitest'
import { recruiterHandlers } from '@/mocks/handlers/recruiter'
import { db } from '@/mocks/db'
import { renderApp } from '@/test/renderApp'

/** Экраны рекрутера на моках: видимость, подборка с фильтрами, модалка приглашения. */
const server = setupServer(...recruiterHandlers)
// Под нагрузкой (полный прогон в 2 потока) ответ мока с отрисовкой приходит дольше 8 с.
const WAIT = { timeout: 15000 }

beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }))
afterAll(() => server.close())
beforeEach(() => db.reset())

describe('экраны рекрутера', () => {
  it('обезличенный профиль: псевдоним вместо ФИО, контакты скрыты', async () => {
    renderApp('/recruiter/candidates/32', { role: 'recruiter' })
    expect(await screen.findByRole('heading', { level: 1, name: 'Кандидат #4BF1' }, WAIT)).toBeInTheDocument()
    expect(screen.getByTestId('contacts-hidden')).toBeInTheDocument()
    expect(screen.queryByText(/Степанова/)).not.toBeInTheDocument()
    expect(screen.queryByText(/v\.stepanova/)).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Пригласить' })).toBeEnabled()
  }, 20000)

  it('подборка: фильтр из URL сужает список, «Вернуть исходную подборку» возвращает', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/recruiter/needs/1?skills=kafka', { role: 'recruiter' })
    const summary = await screen.findByTestId('match-summary', {}, WAIT)
    await waitFor(() => expect(summary).toHaveTextContent('Показано 4 из 18'), WAIT)
    expect(screen.getAllByTestId('match-card')).toHaveLength(4)
    await user.click(screen.getByRole('button', { name: 'Вернуть исходную подборку' }))
    await waitFor(() => expect(screen.getByTestId('match-summary')).toHaveTextContent('18 кандидатов'), WAIT)
    expect(screen.getAllByTestId('match-card')).toHaveLength(18)
    expect(router.state.location.search).not.toContain('skills')
    // «Почему в подборке» и полоски счёта — у каждой карточки.
    for (const card of screen.getAllByTestId('match-card')) {
      expect(within(card).getByRole('region', { name: 'Почему в подборке' })).toBeInTheDocument()
      expect(within(card).getAllByRole('meter').length).toBeGreaterThanOrEqual(5)
    }
  }, 30000)

  it('модалка приглашения: вилка ниже ожиданий → ошибка, корректная → приглашение в базе', async () => {
    const user = userEvent.setup()
    renderApp('/recruiter/candidates/32', { role: 'recruiter' })
    await user.click(await screen.findByRole('button', { name: 'Пригласить' }, WAIT))
    const dialog = await screen.findByRole('dialog', {}, WAIT)
    await within(dialog).findByTestId('quota-meter', {}, WAIT)
    // контакт рекрутера подставляется из списка рекрутеров компании — ждём, пока он придёт
    await waitFor(() => expect(within(dialog).getByLabelText(/^Контакт/)).not.toHaveValue(''), WAIT)
    const from = within(dialog).getByLabelText('От')
    const to = within(dialog).getByLabelText('До')
    await user.type(from, '180000')
    await user.type(to, '220000')
    await user.click(screen.getByRole('button', { name: 'Отправить приглашение' }))
    expect(await within(dialog).findByText(/Вилка ниже ожиданий кандидата/, {}, WAIT)).toBeInTheDocument()
    // Сумма ожиданий кандидата в ошибках не раскрывается.
    for (const alert of within(dialog).getAllByRole('alert')) expect(alert).not.toHaveTextContent(/230\s000/)
    expect(within(dialog).getByText('Ниже ожиданий кандидата')).toBeInTheDocument()
    await user.clear(to)
    await user.type(to, '300000')
    await user.click(screen.getByRole('button', { name: 'Отправить приглашение' }))
    expect(await screen.findByText('Приглашение отправлено', {}, WAIT)).toBeInTheDocument()
    const rows = db.data.invitations as unknown as Array<{ candidate_id: number; status: string; salary_to: number }>
    expect(rows.at(-1)).toMatchObject({ candidate_id: 32, status: 'sent', salary_to: 300000 })
  }, 40000)
})
