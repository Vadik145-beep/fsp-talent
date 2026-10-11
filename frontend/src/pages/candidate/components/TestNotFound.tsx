import { Link } from 'react-router'
import { SearchX } from 'lucide-react'
import { Card, EmptyState } from '@/shared/ui'

/** Нет такого теста (опечатка в адресе, чужая сессия). */
export function TestNotFound() {
  return (
    <Card padding="none">
      <EmptyState
        icon={<SearchX aria-hidden />}
        title="Тест не найден"
        description="Проверьте ссылку. Свои тесты и результаты — в разделе «Категория и грейд»."
        action={
          <Link
            to="/candidate/grade"
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            Категория и грейд
          </Link>
        }
      />
    </Card>
  )
}
