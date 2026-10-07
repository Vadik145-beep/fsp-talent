import { useEffect, type ReactNode } from 'react'
import { Link } from 'react-router'
import {
  ArrowRight,
  BadgeCheck,
  Briefcase,
  Check,
  EyeOff,
  FileText,
  Gauge,
  HandCoins,
  Lock,
  MessagesSquare,
  Search,
  Shuffle,
  ShieldCheck,
  Sparkles,
  Target,
  UserRoundSearch,
} from 'lucide-react'
import { FspVerifiedBadge, StatusPill } from '@/shared/ui'
import { APP_NAME } from '@/shared/config/env'
import { formatSalaryRange } from '@/shared/lib/format'

const ctaPrimary =
  'inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary px-6 text-base font-semibold text-white shadow-sm transition-colors hover:bg-primary-hover focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]'
const ctaSecondary =
  'inline-flex h-12 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-line-strong bg-surface px-6 text-base font-semibold text-fsp-plum transition-colors hover:border-fsp-lavender hover:bg-violet-soft focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]'

/** Лендинг: два входа и три отличия сервиса. */
export default function LandingPage() {
  useEffect(() => {
    document.title = `${APP_NAME} — работодатель приходит к вам сам`
  }, [])

  return (
    <div className="-mt-6 pb-10">
      {/* Первый экран */}
      <section className="grid items-center gap-10 py-10 lg:grid-cols-[1.1fr_0.9fr] lg:py-16">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-violet-soft px-3 py-1 text-[13px] font-semibold text-fsp-plum">
            <Sparkles className="size-4" aria-hidden />
            Спецтрек ФСП · подбор IT-специалистов
          </p>
          <h1 className="mt-4 text-[34px] leading-[1.1] font-bold tracking-tight text-fsp-night sm:text-5xl">
            Работодатель приходит к&nbsp;вам сам —{' '}
            <span className="text-primary">сразу с&nbsp;зарплатой</span>
          </h1>
          <p className="mt-5 max-w-xl text-lg text-muted">
            Пройдите адаптивный тест, получите подтверждённую категорию и ждите приглашений. Без рассылки резюме и
            без «зарплата по итогам собеседования».
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link to="/register?role=candidate" className={ctaPrimary}>
              <Search className="size-5" aria-hidden />
              Ищу работу
            </Link>
            <Link to="/register?role=recruiter" className={ctaSecondary}>
              <Briefcase className="size-5" aria-hidden />
              Ищу специалистов
            </Link>
          </div>
          <p className="mt-4 text-sm text-muted">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="font-semibold text-fsp-plum underline-offset-2 hover:underline">
              Войти
            </Link>
          </p>
        </div>
        <InvitationPreview />
      </section>

      {/* Три отличия */}
      <section aria-labelledby="diff-title" className="py-8">
        <h2 id="diff-title" className="text-2xl font-bold sm:text-3xl">
          Чем мы отличаемся от сайтов с вакансиями
        </h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <Feature
            icon={<HandCoins aria-hidden />}
            title="Работодатель приходит сам — и сразу с зарплатой"
            text="В каждом приглашении — вилка «от–до» в рублях. Если она ниже ваших ожиданий, приглашение просто не отправится."
          />
          <Feature
            icon={<BadgeCheck aria-hidden />}
            title="Профиль подтверждён тестом и ФСП"
            text="Адаптивный тест определяет категорию — например, «Backend · Middle». Достижения из реестра ФСП отмечены «подтверждено ФСП»."
          />
          <Feature
            icon={<EyeOff aria-hidden />}
            title="Контакты скрыты до вашего согласия"
            text="Работодатель видит навыки и результаты теста, но не имя и телефон. Контакты откроются, только когда вы примете приглашение."
          />
        </div>
      </section>

      {/* Как это работает */}
      <section aria-labelledby="how-title" className="py-8">
        <h2 id="how-title" className="text-2xl font-bold sm:text-3xl">
          Как это работает
        </h2>
        <div className="mt-6 grid gap-4 lg:grid-cols-2">
          <Steps
            title="Соискателю"
            icon={<UserRoundSearch aria-hidden />}
            steps={[
              ['Профиль за 5 минут', 'Заполните вручную или загрузите PDF-резюме — поля заполнятся сами.'],
              ['Опрос и тест', 'Короткий опрос подскажет специализацию, адаптивный тест — до 20 задач.'],
              ['Категория', 'Специализация × грейд. Работодатели ищут по категориям, а не по ключевым словам.'],
              ['Приглашения с зарплатой', 'Принимаете — открываются контакты. Отказываетесь — указываете причину.'],
            ]}
            cta={
              <Link to="/register?role=candidate" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                Создать профиль <ArrowRight className="size-4" aria-hidden />
              </Link>
            }
          />
          <Steps
            title="Работодателю"
            icon={<Briefcase aria-hidden />}
            steps={[
              ['Опишите, кого ищете', 'Формой или своими словами: «нужен сеньор на Go в финтех, 300–400к».'],
              ['Подборка по категориям', 'Кандидаты ранжированы, у каждого — «почему в подборке».'],
              ['Приглашение с вилкой', 'Квота приглашений защищает кандидатов от спама — каждое приглашение ценно.'],
              ['Контакты после согласия', 'Кандидат принял — вы видите имя, почту и телефон.'],
            ]}
            cta={
              <Link to="/register?role=recruiter" className="inline-flex items-center gap-1 font-semibold text-primary hover:underline">
                Подключить компанию <ArrowRight className="size-4" aria-hidden />
              </Link>
            }
          />
        </div>
      </section>

      {/* Тест */}
      <section aria-labelledby="test-title" className="py-8">
        <div className="rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)] sm:p-8">
          <h2 id="test-title" className="text-2xl font-bold sm:text-3xl">
            Тест, который нельзя «слить»
          </h2>
          <p className="mt-2 max-w-3xl text-muted">
            Категория что-то значит, только если её нельзя получить по шпаргалке. Поэтому:
          </p>
          <ul className="mt-6 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
            <TestPoint icon={<Shuffle aria-hidden />} title="У каждого свой вариант">
              Числа, имена и порядок ответов меняются — чужой ответ к вашему варианту не подойдёт.
            </TestPoint>
            <TestPoint icon={<Target aria-hidden />} title="Адаптивность">
              Ответили верно — следующая задача сложнее, ошиблись — проще. Обычно хватает 12–20 задач.
            </TestPoint>
            <TestPoint icon={<Gauge aria-hidden />} title="Честная точность">
              Показываем уровень с погрешностью: «0,42 ± 0,28 → Middle».
            </TestPoint>
            <TestPoint icon={<ShieldCheck aria-hidden />} title="Без принудительного понижения">
              Не подтвердили грейд — предложим тест ниже. Менять грейд можно раз в 90 дней.
            </TestPoint>
          </ul>
        </div>
      </section>

      {/* Финальный призыв */}
      <section className="mt-6 overflow-hidden rounded-xl bg-fsp-night px-6 py-10 text-white sm:px-10">
        <div className="flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
          <div>
            <h2 className="text-2xl font-bold text-white sm:text-3xl">Начните с профиля — это бесплатно</h2>
            <p className="mt-2 max-w-xl text-on-nav-muted">
              Участникам соревнований ФСП — бонус: привяжите ФСП ID, и достижения появятся в профиле автоматически.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Link to="/register?role=candidate" className={ctaPrimary}>
              Создать профиль
            </Link>
            <Link
              to="/register?role=recruiter"
              className="inline-flex h-12 items-center justify-center whitespace-nowrap rounded-md border border-white/40 px-6 text-base font-semibold text-white transition-colors hover:bg-white/10 focus-visible:outline-none focus-visible:shadow-[var(--shadow-focus)]"
            >
              Подключить компанию
            </Link>
          </div>
        </div>
      </section>
    </div>
  )
}

function Feature({ icon, title, text }: { icon: ReactNode; title: string; text: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)]">
      <div className="flex size-11 items-center justify-center rounded-lg bg-primary-soft text-primary [&>svg]:size-6">{icon}</div>
      <h3 className="mt-4 text-lg leading-snug font-bold">{title}</h3>
      <p className="mt-2 text-[15px] text-muted">{text}</p>
    </div>
  )
}

function Steps({ title, icon, steps, cta }: { title: string; icon: ReactNode; steps: [string, string][]; cta: ReactNode }) {
  return (
    <div className="flex flex-col rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)]">
      <div className="flex items-center gap-3">
        <span className="flex size-10 items-center justify-center rounded-lg bg-violet-soft text-fsp-plum [&>svg]:size-5">{icon}</span>
        <h3 className="text-xl font-bold">{title}</h3>
      </div>
      <ol className="mt-5 grid gap-4">
        {steps.map(([head, text], i) => (
          <li key={head} className="flex gap-3">
            <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-fsp-night text-sm font-bold text-white">
              {i + 1}
            </span>
            <span>
              <span className="block font-semibold text-ink">{head}</span>
              <span className="block text-[15px] text-muted">{text}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-5 pt-1">{cta}</div>
    </div>
  )
}

function TestPoint({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <li>
      <span className="flex size-9 items-center justify-center rounded-md bg-fsp-night text-fsp-blush [&>svg]:size-5">{icon}</span>
      <p className="mt-3 font-semibold text-ink">{title}</p>
      <p className="mt-1 text-[15px] text-muted">{children}</p>
    </li>
  )
}

/** Иллюстрация: так выглядит приглашение у соискателя (не интерактивная). */
function InvitationPreview() {
  return (
    <div className="relative mx-auto w-full max-w-md" aria-hidden>
      <div className="absolute -top-4 -right-3 h-40 w-40 rounded-full bg-fsp-blush blur-3xl" />
      <div className="absolute -bottom-6 -left-4 h-40 w-40 rounded-full bg-primary-tint blur-3xl" />
      <div className="relative rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-pop)]">
        <div className="flex items-center justify-between gap-3">
          <span className="text-sm font-semibold text-muted">Новое приглашение</span>
          <StatusPill status="sent" />
        </div>
        <p className="mt-4 text-[28px] leading-tight font-bold text-fsp-night tabular-nums">
          {formatSalaryRange(200000, 280000)}
        </p>
        <p className="mt-1 text-sm text-muted">в месяц, до вычета налогов</p>
        <div className="mt-5 flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-md bg-fsp-plum text-sm font-bold text-white">СК</span>
          <div>
            <p className="font-semibold">Северный код</p>
            <p className="text-sm text-muted">Финтех · Backend · Middle</p>
          </div>
        </div>
        <ul className="mt-5 space-y-2 text-sm">
          <li className="flex items-center gap-2">
            <Check className="size-4 text-success" /> Платёжный шлюз, команда 6 человек
          </li>
          <li className="flex items-center gap-2">
            <MessagesSquare className="size-4 text-fsp-plum" /> Созвон в Telegram
          </li>
          <li className="flex items-center gap-2">
            <FileText className="size-4 text-fsp-plum" /> Короткое задание — по желанию
          </li>
        </ul>
        <div className="mt-5 flex items-center gap-2 rounded-md bg-violet-soft px-3 py-2 text-[13px] text-fsp-plum">
          <Lock className="size-4 shrink-0" />
          Ваши контакты откроются, только если вы примете
        </div>
        <div className="mt-5 grid grid-cols-2 gap-2">
          <span className="inline-flex h-10 items-center justify-center rounded-md bg-primary text-sm font-semibold text-white">Принять</span>
          <span className="inline-flex h-10 items-center justify-center rounded-md border border-line-strong text-sm font-semibold text-fsp-plum">
            Отклонить
          </span>
        </div>
      </div>
      <div className="relative -mt-3 ml-6 inline-flex rounded-lg border border-line bg-surface px-3 py-2 shadow-[var(--shadow-card)]">
        <FspVerifiedBadge label="Призёр всероссийского · подтверждено ФСП" />
      </div>
    </div>
  )
}
