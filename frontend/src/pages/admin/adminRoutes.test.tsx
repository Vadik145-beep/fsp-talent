import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '@/test/renderApp'

// Экраны админки открываются по своим маршрутам (без 404). Данные здесь не грузятся — проверяем заголовок.
const screens: Array<[string, string]> = [
  ['/admin', 'Дашборд'],
  ['/admin/users', 'Пользователи'],
  ['/admin/companies', 'Компании'],
  ['/admin/catalog', 'Справочники и настройки'],
  ['/admin/items', 'Банк задач'],
  ['/admin/vacancy-tests', 'Задания из вакансий'],
  ['/admin/validation', 'Валидация'],
  ['/admin/reports', 'Жалобы'],
  ['/admin/audit', 'Журнал'],
]

describe('маршруты админки', () => {
  it.each(screens)('%s открывает экран «%s»', { timeout: 30000 }, async (path, title) => {
    renderApp(path, { role: 'admin' })
    expect(await screen.findByRole('heading', { level: 1, name: title }, { timeout: 20000 })).toBeInTheDocument()
    expect(screen.queryByText('Страница не найдена')).not.toBeInTheDocument()
  })
})
