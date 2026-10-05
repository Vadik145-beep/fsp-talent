import {
  Award,
  Briefcase,
  FileUser,
  GraduationCap,
  LayoutDashboard,
  ListChecks,
  Mail,
  Send,
  Settings,
} from 'lucide-react'
import type { NavItem } from '@/shared/config/nav'

/** Боковое меню соискателя (порядок — как в карте экранов). */
export const candidateNav: NavItem[] = [
  { to: '/candidate', label: 'Главная', icon: LayoutDashboard, end: true },
  { to: '/candidate/profile', label: 'Профиль и резюме', icon: FileUser },
  { to: '/candidate/grade', label: 'Категория и грейд', icon: GraduationCap },
  { to: '/candidate/invitations', label: 'Приглашения', icon: Mail },
  { to: '/candidate/vacancies', label: 'Вакансии', icon: Briefcase },
  { to: '/candidate/applications', label: 'Мои отклики', icon: Send },
  { to: '/candidate/tasks', label: 'Задания', icon: ListChecks },
  { to: '/candidate/fsp', label: 'Достижения ФСП', icon: Award },
  { to: '/candidate/settings', label: 'Настройки', icon: Settings },
]
