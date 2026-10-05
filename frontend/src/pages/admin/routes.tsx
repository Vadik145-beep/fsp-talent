import type { RouteObject } from 'react-router'
import { lazyPage } from '@/shared/lib/lazyPage'

/**
 * Маршруты кабинета администратора (/admin/*). Пути — относительные, layout задаёт корневой роутер.
 * Правит только трек 1c.
 */
export const adminRoutes: RouteObject[] = [
  { index: true, ...lazyPage(() => import('./DashboardPage')) },
  { path: 'users', ...lazyPage(() => import('./UsersPage')) },
  { path: 'companies', ...lazyPage(() => import('./CompaniesPage')) },
  { path: 'catalog', ...lazyPage(() => import('./CatalogPage')) },
  { path: 'items', ...lazyPage(() => import('./ItemsPage')) },
  { path: 'items/:id', ...lazyPage(() => import('./ItemPage')) },
  { path: 'vacancy-tests', ...lazyPage(() => import('./VacancyTestsPage')) },
  { path: 'validation', ...lazyPage(() => import('./ValidationPage')) },
  { path: 'reports', ...lazyPage(() => import('./ReportsPage')) },
  { path: 'audit', ...lazyPage(() => import('./AuditPage')) },
]
