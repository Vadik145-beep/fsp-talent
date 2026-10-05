import {
  BookOpen,
  Building,
  ChartLine,
  Flag,
  Gauge,
  Library,
  ScrollText,
  Sparkles,
  Users,
} from 'lucide-react'
import type { NavItem } from '@/shared/config/nav'

/** Боковое меню администратора (порядок — как в карте экранов). */
export const adminNav: NavItem[] = [
  { to: '/admin', label: 'Дашборд', icon: Gauge, end: true },
  { to: '/admin/users', label: 'Пользователи', icon: Users },
  { to: '/admin/companies', label: 'Компании', icon: Building },
  { to: '/admin/catalog', label: 'Справочники', icon: BookOpen },
  { to: '/admin/items', label: 'Банк задач', icon: Library },
  { to: '/admin/vacancy-tests', label: 'Задания из вакансий', icon: Sparkles },
  { to: '/admin/validation', label: 'Валидация', icon: ChartLine },
  { to: '/admin/reports', label: 'Жалобы', icon: Flag },
  { to: '/admin/audit', label: 'Журнал', icon: ScrollText },
]
