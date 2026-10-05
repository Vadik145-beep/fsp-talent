import { Link } from 'react-router'
import { Briefcase, Search } from 'lucide-react'
import { PageHeader } from '@/shared/ui'

/** Заглушка лендинга. Трек 1a заменяет содержимым из карты экранов. */
export default function LandingPage() {
  return (
    <div className="mx-auto max-w-5xl py-6 sm:py-12">
      <PageHeader
        title="Работодатель приходит к вам сам"
        description="Платформа подбора IT-специалистов: профиль подтверждён тестом и достижениями ФСП, зарплата видна сразу."
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          to="/register?role=candidate"
          className="group rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)] transition-[border-color,box-shadow] hover:border-fsp-lavender hover:shadow-[var(--shadow-pop)]"
        >
          <Search className="size-8 text-primary" aria-hidden />
          <p className="mt-4 text-xl font-bold">Ищу работу</p>
          <p className="mt-1 text-muted">Пройдите тест, получите категорию и ждите приглашений с зарплатой.</p>
        </Link>
        <Link
          to="/register?role=recruiter"
          className="group rounded-xl border border-line bg-surface p-6 shadow-[var(--shadow-card)] transition-[border-color,box-shadow] hover:border-fsp-lavender hover:shadow-[var(--shadow-pop)]"
        >
          <Briefcase className="size-8 text-fsp-plum" aria-hidden />
          <p className="mt-4 text-xl font-bold">Ищу специалистов</p>
          <p className="mt-1 text-muted">Опишите потребность — получите подборку проверенных кандидатов.</p>
        </Link>
      </div>
      <p className="mt-8 text-center text-sm text-muted">Экран в работе: лендинг наполнит трек 1a.</p>
    </div>
  )
}
