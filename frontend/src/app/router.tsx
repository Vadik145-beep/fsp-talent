import { createBrowserRouter, type RouteObject } from 'react-router'
import { lazyPage } from '@/shared/lib/lazyPage'
import { publicRoutes } from '@/pages/public/routes'
import { candidateRoutes } from '@/pages/candidate/routes'
import { candidateNav } from '@/pages/candidate/nav'
import { recruiterRoutes } from '@/pages/recruiter/routes'
import { recruiterNav } from '@/pages/recruiter/nav'
import { adminRoutes } from '@/pages/admin/routes'
import { adminNav } from '@/pages/admin/nav'
import { CabinetLayout } from './layouts/CabinetLayout'
import { PublicLayout } from './layouts/PublicLayout'
import { AppLoader, NotFoundPage, RouteErrorPage } from './SystemPages'

/**
 * Корневой роутер. Только собирает маршруты ролей — сами маршруты и меню
 * лежат в src/pages/<role>/routes.tsx и nav.ts. В волне 1 этот файл не правится.
 */
export const appRoutes: RouteObject[] = [
  {
    path: '/',
    errorElement: <RouteErrorPage />,
    HydrateFallback: AppLoader,
    children: [
      {
        element: <PublicLayout />,
        children: [
          ...publicRoutes,
          { path: 'ui-kit', ...lazyPage(() => import('@/pages/ui-kit/UiKitPage')) },
          { path: '*', element: <NotFoundPage /> },
        ],
      },
      {
        path: 'candidate',
        element: <CabinetLayout role="candidate" nav={candidateNav} />,
        children: [...candidateRoutes, { path: '*', element: <NotFoundPage /> }],
      },
      {
        path: 'recruiter',
        element: <CabinetLayout role="recruiter" nav={recruiterNav} />,
        children: [...recruiterRoutes, { path: '*', element: <NotFoundPage /> }],
      },
      {
        path: 'admin',
        element: <CabinetLayout role="admin" nav={adminNav} />,
        children: [...adminRoutes, { path: '*', element: <NotFoundPage /> }],
      },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(appRoutes)
}
