import { useMemo, useState, type FormEvent } from 'react'
import { Send } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { Button, Input, Modal, Select, Textarea } from '@/shared/ui'
import { useCompanyRecruiters, type Application, type ContactMethodType } from '../api'
import { CONTACT_TYPE_LABELS } from '../labels'

export interface ApplicationInviteBody {
  contact_method: { type: ContactMethodType; value: string }
  message: string
}

/** Пригласить по отклику: как с вами связаться и пара слов кандидату. Кандидат увидит это в отклике. */
export function ApplicationInviteModal({
  app,
  error,
  pending,
  onClose,
  onSubmit,
}: {
  app: Application
  error?: string
  pending: boolean
  onClose: () => void
  onSubmit: (body: ApplicationInviteBody) => void
}) {
  const { user } = useAuth()
  const recruiters = useCompanyRecruiters()
  const me = recruiters.data?.find((r) => r.user_id === user?.userId) ?? recruiters.data?.[0]

  const prev = app.contact_method
  const [contactType, setContactType] = useState<ContactMethodType>(prev?.type ?? 'email')
  const [contactValue, setContactValue] = useState<string | null>(prev?.value ?? null)
  const [message, setMessage] = useState(app.invite_message ?? '')
  const [localError, setLocalError] = useState<string>()

  const contactDefault = useMemo(() => {
    if (!me) return ''
    if (contactType === 'email') return me.email
    if (contactType === 'phone') return me.phone ?? ''
    if (contactType === 'telegram') return me.telegram ?? ''
    return ''
  }, [me, contactType])
  const contact = contactValue ?? contactDefault
  const name = app.candidate_contacts?.full_name ?? app.candidate?.pseudonym ?? 'Кандидат'

  function submit(e: FormEvent) {
    e.preventDefault()
    if (contact.trim().length < 2) {
      setLocalError('Укажите контакт для связи')
      return
    }
    setLocalError(undefined)
    onSubmit({ contact_method: { type: contactType, value: contact.trim() }, message: message.trim() })
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Пригласить на разговор"
      description={`${name} увидит, как с вами связаться, в своих откликах и получит письмо.`}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" form="application-invite-form" loading={pending} leftIcon={<Send className="size-4" aria-hidden />}>
            Пригласить
          </Button>
        </>
      }
    >
      <form id="application-invite-form" onSubmit={submit} noValidate className="flex flex-col gap-4">
        <div className="grid gap-3 sm:grid-cols-[160px_1fr]">
          <Select
            label="Способ связи"
            value={contactType}
            options={(Object.keys(CONTACT_TYPE_LABELS) as ContactMethodType[]).map((v) => ({ value: v, label: CONTACT_TYPE_LABELS[v] }))}
            onChange={(e) => {
              setContactType(e.target.value as ContactMethodType)
              setContactValue(null)
            }}
          />
          <Input
            label="Контакт"
            required
            value={contact}
            onChange={(e) => setContactValue(e.target.value)}
            error={localError ?? error}
          />
        </div>
        <Textarea
          label="Сообщение кандидату (необязательно)"
          rows={3}
          maxLength={1000}
          placeholder="Например: давайте созвонимся в четверг в 15:00 — напишите, удобно ли."
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
      </form>
    </Modal>
  )
}
