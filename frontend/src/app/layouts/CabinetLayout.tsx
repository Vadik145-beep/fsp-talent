import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useMatches, useNavigation } from 'react-router'
import { Menu } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import { ROLE_HOME, ROLE_LABELS, type Role } from '@/shared/config/roles'
import type { NavItem, RouteHandle } from '@/shared/config/nav'
import { Drawer, Spinner } from '@/shared/ui'
import { useAuth } from '../auth/AuthContext'
import { DemoBar } from './DemoBar'
import { Logo } from './Logo'
import { UserMenu } from './UserMenu'

function SideNav({ items, onNavigate }: { items: NavItem[]; onNavigate?: () => void }) {
  return (
    <nav aria-label="Меню кабинета" className="flex flex-col gap-0.5 p-3">
      {items.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'group relative flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'bg-white/12 text-white'
                : 'text-on-nav-muted hover:bg-white/6 hover:text-white',
            )
          }
        >
          {({ isActive }) => (
            <>
              <span
                className={cn(
                  'absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-fsp-pink transition-opacity',
                  isActive ? 'opacity-100' : 'opacity-0',
                )}
                aria-hidden
              />
              <Icon className={cn('size-[18px] shrink-0', isActive ? 'text-fsp-blush' : 'opacity-80')} aria-hidden />
              <span className="truncate">{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}

/** Тонкая полоска загрузки при переходе между экранами (ленивые чанки, загрузчики). */
function NavigationProgress() {
  const navigation = useNavigation()
  if (navigation.state === 'idle') return null
  return (
    <div className="fixed inset-x-0 top-0 z-[70] h-0.5 overflow-hidden" role="progressbar" aria-label="Загрузка экрана">
      <div className="h-full w-1/3 animate-pulse bg-fsp-pink" />
    </div>
  )
}

export interface CabinetLayoutProps {
  role: Role
  nav: NavItem[]
}

/**
 * Каркас кабинета: шапка (логотип, роль, меню пользователя) + боковое меню роли + контент.
 * На мобильном меню открывается кнопкой в шапке. Экраны с handle.focus — без бокового меню.
 */
export function CabinetLayout({ role, nav }: CabinetLayoutProps) {
  const { user, switchRole } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const location = useLocation()
  const matches = useMatches()
  const focus = matches.some((m) => (m.handle as RouteHandle | undefined)?.focus)

  // Демо-авторизация: зашли по ссылке в кабинет другой роли — входим демо-пользователем этой роли.
  // В волнах 2–4 здесь будет проверка настоящей сессии и редирект на /login.
  const roleMismatch = user?.role !== role
  useEffect(() => {
    if (roleMismatch) switchRole(role)
  }, [roleMismatch, role, switchRole])

  // Прокрутка наверх при смене экрана
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [location.pathname])

  return (
    <div className="flex min-h-screen flex-col bg-nav">
      <NavigationProgress />
      <DemoBar />
      <header className="sticky top-0 z-30 bg-nav">
        <div className="flex h-14 items-center gap-3 px-3 sm:px-4">
          {!focus && (
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              className="rounded-md p-2 text-white hover:bg-nav-hover lg:hidden"
              aria-label="Открыть меню"
            >
              <Menu className="size-5" aria-hidden />
            </button>
          )}
          <Logo to={ROLE_HOME[role]} tone="light" />
          <span className="hidden rounded-full bg-white/10 px-2.5 py-0.5 text-xs font-semibold text-on-nav-muted sm:inline">
            {ROLE_LABELS[role]}
          </span>
          <div className="ml-auto flex items-center gap-2">{user && !roleMismatch && <UserMenu user={user} />}</div>
        </div>
      </header>

      <div className="flex flex-1">
        {!focus && (
          <aside className="sticky top-14 hidden h-[calc(100vh-3.5rem)] w-64 shrink-0 overflow-y-auto lg:block">
            <SideNav items={nav} />
          </aside>
        )}
        <main
          id="main"
          className={cn(
            'min-w-0 flex-1 bg-canvas',
            !focus && 'lg:rounded-tl-2xl',
          )}
        >
          <div className={cn('mx-auto w-full px-4 py-6 sm:px-6 lg:px-8 lg:py-8', focus ? 'max-w-4xl' : 'max-w-6xl')}>
            {roleMismatch ? (
              <div className="flex justify-center py-24 text-fsp-plum">
                <Spinner size={28} label="Загрузка кабинета" />
              </div>
            ) : (
              <Outlet />
            )}
          </div>
        </main>
      </div>

      <Drawer
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        side="left"
        widthClass="w-72 max-w-[85vw]"
        panelClassName="bg-nav"
        hideHeader
        ariaLabel="Меню кабинета"
      >
        <div className="flex h-14 items-center px-4">
          <Logo to={ROLE_HOME[role]} tone="light" />
        </div>
        <p className="px-6 pb-1 text-xs font-semibold tracking-wide text-on-nav-muted uppercase">{ROLE_LABELS[role]}</p>
        <SideNav items={nav} onNavigate={() => setMenuOpen(false)} />
      </Drawer>
    </div>
  )
}
