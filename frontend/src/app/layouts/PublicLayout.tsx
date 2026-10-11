import { useEffect } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router'
import { useAuth } from '../auth/AuthContext'
import { ROLE_HOME } from '@/shared/config/roles'
import { brandAsset } from '@/shared/ui'
import { DemoBar } from './DemoBar'
import { Logo } from './Logo'

const linkBtn =
  'inline-flex h-9 items-center rounded-md px-3 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]'

/** Публичный каркас: лендинг, вход, регистрация, витрина UI-кита. */
export function PublicLayout() {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const logoutRequested = (location.state as { logout?: boolean } | null)?.logout === true

  // Выход из меню пользователя: кабинет уже размонтирован, можно сбрасывать роль.
  useEffect(() => {
    if (!logoutRequested) return
    logout()
    navigate(location.pathname, { replace: true, state: null })
  }, [logoutRequested, logout, navigate, location.pathname])

  return (
    <div className="flex min-h-screen flex-col bg-canvas">
      <DemoBar />
      <header className="sticky top-0 z-30 border-b border-line bg-nav/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4 sm:px-6">
          <Logo compact="mobile" />
          <nav className="ml-auto flex items-center gap-1 sm:gap-2" aria-label="Вход">
            {user ? (
              <Link to={ROLE_HOME[user.role]} className={`${linkBtn} bg-primary text-white hover:bg-primary-hover`}>
                В кабинет
              </Link>
            ) : (
              <>
                <Link to="/login" className={`${linkBtn} text-primary hover:bg-primary-soft`}>
                  Войти
                </Link>
                <Link to="/register" className={`${linkBtn} bg-primary text-white hover:bg-primary-hover`}>
                  Регистрация
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
        <Outlet />
      </main>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-3 px-4 py-5 text-[13px] text-muted sm:px-6">
          <img
            src={brandAsset('fsp-logo-full.svg')}
            alt="Федерация спортивного программирования России"
            className="h-7 w-auto max-w-full"
            width={224}
            height={28}
          />
          <span>Таланты — платформа подбора IT-специалистов, спецтрек ФСП</span>
        </div>
      </footer>
    </div>
  )
}
