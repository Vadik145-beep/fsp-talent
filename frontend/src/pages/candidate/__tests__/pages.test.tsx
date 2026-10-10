import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { db } from '@/mocks/db'
import { setApiRole } from '@/shared/api/client'
import { renderApp } from '@/test/renderApp'
import { setupMockServer } from './mswTestServer'

setupMockServer()

const T = { timeout: 8000 }

describe('экраны соискателя', () => {
  it('приглашение: принять → контакты рекрутера, статус в базе меняется', async () => {
    const user = userEvent.setup()
    renderApp('/candidate/invitations/2', { role: 'candidate' })
    await user.click(await screen.findByRole('button', { name: 'Принять' }, T))
    const dialog = await screen.findByRole('dialog')
    await user.click(within(dialog).getByRole('button', { name: 'Принять и открыть контакты' }))
    expect(await screen.findByText('Контакты открыты', {}, T)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'm.titova.hr@example.com' })).toBeInTheDocument()
    expect(db.data.invitations.find((i) => i.id === 2)?.status).toBe('accepted')
  }, 20_000)

  it('приглашение: отклонить с причиной', async () => {
    const user = userEvent.setup()
    renderApp('/candidate/invitations/21', { role: 'candidate' })
    await user.click(await screen.findByRole('button', { name: 'Отклонить' }, T))
    const dialog = await screen.findByRole('dialog')
    await user.click(await within(dialog).findByLabelText('Не тот стек', {}, T))
    await user.click(within(dialog).getByRole('button', { name: 'Отклонить' }))
    expect(await screen.findByText('Вы отклонили приглашение', {}, T)).toBeInTheDocument()
    expect(db.data.invitations.find((i) => i.id === 21)?.decline_reason).toBe('wrong_stack')
  }, 20_000)

  it('категория и грейд: при кулдауне кнопки неактивны и видна дата', async () => {
    renderApp('/candidate/grade', { role: 'candidate' })
    const buttons = await screen.findAllByRole('button', { name: 'Пока недоступно' }, T)
    expect(buttons).toHaveLength(2)
    buttons.forEach((b) => expect(b).toBeDisabled())
    expect(screen.getAllByText(/Станет доступно 9 декабря 2026/)).toHaveLength(2)
  }, 20_000)

  it('кандидат без ФСП: экран достижений — нейтральное пустое состояние и привязка', async () => {
    renderApp('/candidate/fsp', { role: 'candidate' })
    setApiRole('candidate', 26)
    expect(await screen.findByText('ФСП ID не привязан', {}, T)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Привязать ФСП ID' })).toBeInTheDocument()
    expect(screen.getByText(/не снижает позицию в выдаче/)).toBeInTheDocument()
  }, 20_000)

  it('кандидат без ФСП: главная и настройки открываются без ошибок', async () => {
    renderApp('/candidate', { role: 'candidate' })
    setApiRole('candidate', 26)
    expect(await screen.findByText('Frontend · Junior', {}, T)).toBeInTheDocument()
    expect(screen.getByText('Участвовали в соревнованиях ФСП?')).toBeInTheDocument()
  }, 20_000)

  it('настройки: превью «так вас видит работодатель» меняется от переключателя', async () => {
    const user = userEvent.setup()
    renderApp('/candidate/settings', { role: 'candidate' })
    expect(await screen.findByText('Казань', {}, T)).toBeInTheDocument()
    await user.click(screen.getByRole('switch', { name: 'Город' }))
    await waitFor(() => expect(screen.getByText('Город скрыт')).toBeInTheDocument())
    await waitFor(() => expect(db.data.candidates.find((c) => c.id === 1)?.privacy.show_city).toBe(false))
  }, 20_000)
})

describe('публичные экраны', () => {
  it('лендинг объясняет три отличия', async () => {
    renderApp('/')
    expect(await screen.findByText('Работодатель приходит сам — и сразу с зарплатой', {}, T)).toBeInTheDocument()
    expect(screen.getByText('Профиль подтверждён тестом и ФСП')).toBeInTheDocument()
    expect(screen.getByText('Контакты скрыты до вашего согласия')).toBeInTheDocument()
  })

  it('регистрация не проходит без согласия на обработку ПДн', async () => {
    const user = userEvent.setup()
    renderApp('/register')
    await user.type(await screen.findByLabelText(/Имя и фамилия/, {}, T), 'Пётр Петров')
    await user.type(screen.getByLabelText(/^Почта/), 'petr@example.com')
    await user.type(screen.getByLabelText(/^Пароль/), 'secret123')
    await user.click(screen.getByRole('button', { name: 'Зарегистрироваться' }))
    expect(await screen.findByText('Без согласия на обработку данных регистрация невозможна')).toBeInTheDocument()
  }, 20_000)
})
