import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '@/test/renderApp'
import { getApiRole } from '@/shared/api/client'

// Все маршруты из карты экранов (_волны/КАРТА_ЭКРАНОВ.md).
const cabinetRoutes = [
  '/candidate',
  '/candidate/onboarding',
  '/candidate/test/s1',
  '/candidate/test/s1/result',
  '/candidate/profile',
  '/candidate/grade',
  '/candidate/invitations',
  '/candidate/invitations/1',
  '/candidate/vacancies',
  '/candidate/applications',
  '/candidate/tasks',
  '/candidate/fsp',
  '/candidate/settings',
  '/recruiter',
  '/recruiter/company',
  '/recruiter/needs',
  '/recruiter/needs/new',
  '/recruiter/needs/1',
  '/recruiter/candidates',
  '/recruiter/candidates/1',
  '/recruiter/invitations',
  '/recruiter/vacancies',
  '/recruiter/vacancies/1',
  '/recruiter/tasks',
  '/admin',
  '/admin/users',
  '/admin/companies',
  '/admin/catalog',
  '/admin/items',
  '/admin/items/1',
  '/admin/vacancy-tests',
  '/admin/validation',
  '/admin/reports',
  '/admin/audit',
]

/** Экран отрисовался: есть заголовок или индикатор загрузки (данные моков в этом тесте не нужны). */
async function waitForScreen() {
  await waitFor(() =>
    expect(document.querySelector('h1, h2, [role="status"], [aria-busy="true"], .animate-pulse')).not.toBeNull(),
  )
}

const publicRoutes = ['/login', '/register', '/verify-email', '/auth/fsp-callback']

describe('роутинг', () => {
  // Экраны уже настоящие (волна 1): проверяем, что маршрут есть и рисует экран, а не 404.
  it.each(cabinetRoutes)('%s открывает экран', async (path) => {
    renderApp(path)
    await waitForScreen()
    expect(screen.queryByText('Страница не найдена')).not.toBeInTheDocument()
  })

  it.each(publicRoutes)('%s открывает публичный экран', async (path) => {
    renderApp(path)
    await waitForScreen()
    expect(screen.queryByText('Страница не найдена')).not.toBeInTheDocument()
  })

  it('лендинг открывается', async () => {
    renderApp('/')
    expect(await screen.findByText('Ищу работу')).toBeInTheDocument()
    expect(screen.getByText('Ищу специалистов')).toBeInTheDocument()
  })

  it('неизвестный адрес — 404', async () => {
    renderApp('/nope')
    expect(await screen.findByText('Страница не найдена')).toBeInTheDocument()
  })

  it('экран онбординга — без бокового меню', async () => {
    renderApp('/candidate/onboarding', { role: 'candidate' })
    await screen.findAllByRole('heading')
    expect(screen.queryByRole('navigation', { name: 'Меню кабинета' })).not.toBeInTheDocument()
  })
})

describe('кабинеты и переключатель ролей', () => {
  it('в кабинете соискателя меню соискателя', async () => {
    renderApp('/candidate', { role: 'candidate' })
    const nav = await screen.findByRole('navigation', { name: 'Меню кабинета' })
    for (const label of ['Главная', 'Профиль и резюме', 'Приглашения', 'Достижения ФСП', 'Настройки']) {
      expect(within(nav).getByRole('link', { name: label })).toBeInTheDocument()
    }
  })

  it('вход по ссылке в чужой кабинет переключает демо-роль', async () => {
    renderApp('/admin/users', { role: 'candidate' })
    const nav = await screen.findByRole('navigation', { name: 'Меню кабинета' })
    expect(within(nav).getByRole('link', { name: 'Банк задач' })).toBeInTheDocument()
    expect(getApiRole()).toBe('admin')
  })

  it('плашка «Смотреть как» переводит в кабинет выбранной роли', async () => {
    const user = userEvent.setup()
    const { router } = renderApp('/candidate', { role: 'candidate' })
    await screen.findByRole('navigation', { name: 'Меню кабинета' })

    const group = screen.getByRole('group', { name: 'Смотреть как' })
    await user.click(within(group).getByRole('button', { name: 'рекрутер' }))

    await waitFor(() => expect(router.state.location.pathname).toBe('/recruiter'))
    const nav = await screen.findByRole('navigation', { name: 'Меню кабинета' })
    expect(within(nav).getByRole('link', { name: 'Банк кандидатов' })).toBeInTheDocument()
    expect(within(group).getByRole('button', { name: 'рекрутер' })).toHaveAttribute('aria-pressed', 'true')
    expect(getApiRole()).toBe('recruiter')
    expect(window.localStorage.getItem('fsp.demoRole')).toBe('recruiter')
  })
})
