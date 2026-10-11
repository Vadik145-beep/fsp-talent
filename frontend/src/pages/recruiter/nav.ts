import {
  Briefcase,
  Building,
  LayoutDashboard,
  ListChecks,
  Mail,
  Target,
  Users,
} from 'lucide-react'
import type { NavItem } from '@/shared/config/nav'

/** Боковое меню рекрутера (порядок — как в карте экранов). */
export const recruiterNav: NavItem[] = [
  { to: '/recruiter', label: 'Главная', icon: LayoutDashboard, end: true },
  { to: '/recruiter/company', label: 'Компания', icon: Building },
  { to: '/recruiter/needs', label: 'Поиск кандидатов', icon: Target },
  { to: '/recruiter/candidates', label: 'Банк кандидатов', icon: Users },
  { to: '/recruiter/invitations', label: 'Приглашения', icon: Mail },
  { to: '/recruiter/vacancies', label: 'Вакансии', icon: Briefcase },
  { to: '/recruiter/tasks', label: 'Задания', icon: ListChecks },
]
