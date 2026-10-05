import { ScreenStub } from '@/shared/ui'

export default function AdminItemPage() {
  return (
    <ScreenStub
      title="Шаблон задачи"
      description="Предпросмотр вариантов, метрики, вывод из оборота / одобрение черновика."
      route="/admin/items/:id"
    />
  )
}
