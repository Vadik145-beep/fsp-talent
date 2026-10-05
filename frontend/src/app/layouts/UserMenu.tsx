import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router'
import { ChevronDown, LogOut } from 'lucide-react'
import { Avatar } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import type { DemoUser } from '../auth/demoUsers'

/** Меню пользователя в шапке кабинета. */
export function UserMenu({ user }: { user: DemoUser }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDoc)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex items-center gap-2 rounded-md py-1 pr-1.5 pl-1 text-left text-white transition-colors hover:bg-nav-hover"
      >
        <Avatar name={user.name} size="sm" className="ring-2 ring-white/20" />
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-40 truncate text-sm leading-tight font-semibold">{user.name}</span>
          <span className="block max-w-40 truncate text-xs leading-tight text-on-nav-muted">{user.subtitle}</span>
        </span>
        <ChevronDown className={cn('size-4 text-on-nav-muted transition-transform', open && 'rotate-180')} aria-hidden />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-64 animate-pop-in rounded-md border border-line bg-surface py-1 shadow-[var(--shadow-pop)]"
        >
          <div className="border-b border-line px-4 py-3">
            <p className="truncate text-sm font-semibold text-ink">{user.name}</p>
            <p className="truncate text-[13px] text-muted">{user.email}</p>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false)
              // Выход выполняет публичный layout после перехода (state.logout): если выйти прямо здесь,
              // ещё не размонтированный кабинет снова войдёт демо-пользователем.
              navigate('/', { state: { logout: true } })
            }}
            className="flex w-full items-center gap-2 px-4 py-2.5 text-sm text-ink hover:bg-violet-soft"
          >
            <LogOut className="size-4 text-muted" aria-hidden />
            Выйти
          </button>
        </div>
      )}
    </div>
  )
}
