import { ScreenStub } from '@/shared/ui'

export default function FspCallbackPage() {
  return (
    <ScreenStub
      title="Вход через ФСП ID"
      description="Возврат из Keycloak после входа через ФСП ID."
      route="/auth/fsp-callback"
    />
  )
}
