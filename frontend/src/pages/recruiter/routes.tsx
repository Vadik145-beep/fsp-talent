import type { RouteObject } from 'react-router'
import { lazyPage } from '@/shared/lib/lazyPage'

/**
 * Маршруты кабинета рекрутера (/recruiter/*). Пути — относительные, layout задаёт корневой роутер.
 * Правит только трек 1b. Модалка приглашения — компонент внутри src/pages/recruiter, не маршрут.
 */
export const recruiterRoutes: RouteObject[] = [
  { index: true, ...lazyPage(() => import('./DashboardPage')) },
  { path: 'company', ...lazyPage(() => import('./CompanyPage')) },
  { path: 'needs', ...lazyPage(() => import('./NeedsPage')) },
  { path: 'needs/new', ...lazyPage(() => import('./NeedNewPage')) },
  { path: 'needs/:id', ...lazyPage(() => import('./NeedPage')) },
  { path: 'needs/:id/edit', ...lazyPage(() => import('./NeedNewPage')) },
  { path: 'candidates', ...lazyPage(() => import('./CandidatesPage')) },
  { path: 'candidates/:id', ...lazyPage(() => import('./CandidatePage')) },
  { path: 'invitations', ...lazyPage(() => import('./InvitationsPage')) },
  { path: 'vacancies', ...lazyPage(() => import('./VacanciesPage')) },
  { path: 'vacancies/:id', ...lazyPage(() => import('./VacancyPage')) },
  { path: 'tasks', ...lazyPage(() => import('./TasksPage')) },
]
