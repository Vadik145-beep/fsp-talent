import type { RouteObject } from 'react-router'
import type { RouteHandle } from '@/shared/config/nav'
import { lazyPage } from '@/shared/lib/lazyPage'

const focus: RouteHandle = { focus: true }

/**
 * Маршруты кабинета соискателя (/candidate/*). Пути — относительные, layout задаёт корневой роутер.
 * Правит только трек 1a. handle: { focus: true } — экран без бокового меню.
 */
export const candidateRoutes: RouteObject[] = [
  { index: true, ...lazyPage(() => import('./DashboardPage')) },
  { path: 'onboarding', handle: focus, ...lazyPage(() => import('./OnboardingPage')) },
  { path: 'test/:sessionId', handle: focus, ...lazyPage(() => import('./TestPage')) },
  { path: 'test/:sessionId/result', ...lazyPage(() => import('./TestResultPage')) },
  { path: 'profile', ...lazyPage(() => import('./ProfilePage')) },
  { path: 'grade', ...lazyPage(() => import('./GradePage')) },
  { path: 'invitations', ...lazyPage(() => import('./InvitationsPage')) },
  { path: 'invitations/:id', ...lazyPage(() => import('./InvitationPage')) },
  { path: 'vacancies', ...lazyPage(() => import('./VacanciesPage')) },
  { path: 'applications', ...lazyPage(() => import('./ApplicationsPage')) },
  { path: 'tasks', ...lazyPage(() => import('./TasksPage')) },
  { path: 'fsp', ...lazyPage(() => import('./FspPage')) },
  { path: 'settings', ...lazyPage(() => import('./SettingsPage')) },
]
