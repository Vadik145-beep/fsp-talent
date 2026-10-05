# fsp-talent — фронтенд

React 18 + TypeScript (strict) + Vite, React Router 7 (data router), TanStack Query 5, Tailwind CSS 4,
MSW 2 (моки API), Recharts, vitest + Testing Library. Шрифт Montserrat из `@fontsource` — без внешних CDN.

## Запуск

```bash
npm ci
npm run dev          # http://localhost:15173, прототип на моках (бэкенд не нужен)
```

| Скрипт | Что делает |
|---|---|
| `npm run dev` | dev-сервер Vite на порту 15173 |
| `npm run build` | проверка типов + сборка в `dist/` |
| `npm run preview` | просмотр собранной версии |
| `npm run lint` | eslint |
| `npm run typecheck` | tsc без сборки |
| `npm test` | vitest (`npm test -- --run` — один прогон без watch) |
| `npm run gen:api` | типы API из `../docs/api/openapi.json` → `src/shared/api/schema.ts` |

### Переменные окружения (`.env`, см. `.env.example`)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `VITE_USE_MOCKS` | моки включены | `false` — выключить MSW, `/api` идёт на бэкенд |
| `VITE_PROXY_TARGET` | `http://localhost:18000` | куда Vite проксирует `/api` (в docker compose — `http://backend:8000`) |
| `VITE_API_BASE` | `/api` | база для fetch-клиента |

Моки включены, если `VITE_USE_MOCKS` не равен `false`, — чтобы `npm run dev` сразу показывал прототип.

### Docker

`Dockerfile` — dev-образ (node:22-alpine, `npm run dev -- --host 0.0.0.0 --port 5173`). Рабочая папка
`/app/frontend`, поэтому alias `@seed` (`../data/seed`) указывает на `/app/data/seed` — compose монтирует туда `./data/seed`.

## Структура

```
src/
  app/                 каркас: провайдеры, корневой роутер, layout'ы, демо-авторизация
    router.tsx         только импортирует маршруты ролей
    layouts/           CabinetLayout (шапка + меню роли), PublicLayout, DemoBar («Смотреть как»)
    auth/              AuthContext (useAuth), демо-пользователи
  pages/
    public/            routes.tsx + экраны /, /login, /register, /verify-email, /auth/fsp-callback
    candidate/         routes.tsx, nav.ts + экраны /candidate/*
    recruiter/         routes.tsx, nav.ts + экраны /recruiter/*
    admin/             routes.tsx, nav.ts + экраны /admin/*
    ui-kit/            витрина компонентов /ui-kit
  shared/
    ui/                UI-кит (import { Button, Card } from '@/shared/ui')
    api/               fetch-клиент, ApiError, queryClient
    config/            роли, справочники (специализации, грейды, статусы), env, типы меню
    lib/               форматирование (зарплата, даты), cn, lazyPage, localStorage
  mocks/
    browser.ts         запуск MSW
    handlers/          public.ts, candidate.ts, recruiter.ts, admin.ts, common.ts
    utils.ts           withScenario, apiError, mockLatency
    scenario.ts        режим данных из демо-плашки (обычные / пусто / ошибка / медленно)
```

Алиасы: `@/…` → `src/…`, `@seed/…` → `../data/seed/…` (фикстуры JSON для моков).

## Правило волны 1: каждый трек — только в своей папке

Трек роли X правит **только**:

- `src/pages/X/**` — экраны, компоненты экранов, хуки запросов, `routes.tsx`, `nav.ts`;
- `src/mocks/handlers/X.ts` — моки своих запросов.

Публичные экраны (`src/pages/public/**`, `src/mocks/handlers/public.ts`) — у трека 1a.

**Не трогать:** `src/app/**`, `src/shared/**`, `src/mocks/{browser,utils,scenario}.ts`,
`src/mocks/handlers/{index,common}.ts`, `src/pages/ui-kit/**`, конфиги и `package.json`.
Не хватает компонента или нужна правка общего — сделайте локальную версию в своей папке
(`src/pages/X/components/…`) и напишите об этом в отчёте; дирижёр перенесёт в `shared` при слиянии.
Новая npm-зависимость — тоже только через отчёт.

Маршруты и пункты меню из карты экранов уже зарегистрированы, на каждом экране заглушка «Экран в работе».
Заменяйте содержимое файла экрана, имена файлов и пути не меняйте. Дополнительные экраны/маршруты — в своём `routes.tsx`.

### Как устроен маршрут

```tsx
// src/pages/candidate/routes.tsx
{ path: 'invitations/:id', ...lazyPage(() => import('./InvitationPage')) },
{ path: 'onboarding', handle: { focus: true }, ...lazyPage(() => import('./OnboardingPage')) },
```

- пути относительные (`/candidate` добавляет корневой роутер);
- экран — `export default` компонент, грузится отдельным чанком;
- `handle: { focus: true }` — экран без бокового меню (мастер, тест).

### Как написать мок

```ts
// src/mocks/handlers/candidate.ts
import { http, type HttpHandler } from 'msw'
import invitations from '@seed/invitations.json'
import { withScenario, apiError } from '../utils'

export const candidateHandlers: HttpHandler[] = [
  http.get('/api/candidates/me/invitations', withScenario({ data: () => invitations, empty: () => [] })),
  http.post('/api/invitations/:id/decline', () => apiError(409, 'invitation_expired', 'Приглашение истекло')),
]
```

`withScenario` учитывает переключатель «Данные» в демо-плашке — так на согласовании видны
пустые списки, ошибка и загрузка без правки кода. Пути и формы ответов — по контракту `docs/api/openapi.json`.

### Как запросить данные

```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '@/shared/api'
import { ErrorState, SkeletonCard, EmptyState } from '@/shared/ui'

const q = useQuery({ queryKey: ['candidate', 'invitations'], queryFn: () => api.get<Invitation[]>('/candidates/me/invitations') })
if (q.isPending) return <SkeletonCard />
if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />
if (!q.data.length) return <EmptyState title="Приглашений пока нет" />
```

Ключи запросов начинайте с имени роли (`['recruiter', …]`), чтобы треки не пересекались.
Клиент сам добавляет заголовок `X-Demo-Role` (текущая роль) и превращает ошибки `{code, message, details}` в `ApiError`.

## Демо-режим

- Плашка «Смотреть как: соискатель / рекрутер / админ» (только при моках) ведёт в кабинет роли.
- Роль хранится в `localStorage` (`fsp.demoRole`); открытие ссылки на кабинет другой роли
  входит демо-пользователем этой роли. `useAuth()` отдаёт `{ user, role, switchRole, logout }`.
- В волнах 2–4 демо-авторизация заменяется настоящей; интерфейс `useAuth()` стоит сохранить.

## Дизайн

Токены — в `src/index.css` (`@theme`): доступны как классы Tailwind (`bg-primary`, `text-muted`,
`bg-nav`, `text-fsp-plum`…) и как CSS-переменные (`var(--color-primary)`). Фирменные цвета ФСП —
`fsp-*`. Фон главной кнопки `#E0004B` вместо `#FF0053`: у `#FF0053` с белым текстом контраст 3,9:1,
ниже WCAG AA. Все компоненты — на `/ui-kit`.
