import { ScreenStub } from '@/shared/ui'

export default function CandidateTestResultPage() {
  return (
    <ScreenStub
      title="Результат теста"
      description="Категория, оценка уровня и интервал, разбор по темам."
      route="/candidate/test/:sessionId/result"
    />
  )
}
