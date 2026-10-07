import type { RouteObject } from 'react-router'
import { lazyPage } from '@/shared/lib/lazyPage'

/**
 * Публичные маршруты (лендинг, вход, регистрация). Layout задаёт корневой роутер.
 * Правит только трек 1a.
 */
export const publicRoutes: RouteObject[] = [
  { index: true, ...lazyPage(() => import('./LandingPage')) },
  { path: 'login', ...lazyPage(() => import('./LoginPage')) },
  { path: 'register', ...lazyPage(() => import('./RegisterPage')) },
  { path: 'verify-email', ...lazyPage(() => import('./VerifyEmailPage')) },
  { path: 'reset-password', ...lazyPage(() => import('./ResetPasswordPage')) },
  { path: 'auth/fsp-callback', ...lazyPage(() => import('./FspCallbackPage')) },
]
