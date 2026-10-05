import { ScreenStub } from '@/shared/ui'

export default function CandidateTestPage() {
  return (
    <ScreenStub
      title="Тест"
      description="Задача, таймер, прогресс, разные форматы задач."
      route="/candidate/test/:sessionId"
    />
  )
}
