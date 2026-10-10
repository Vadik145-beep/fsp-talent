import { Mail, MessageCircle, Phone, Send } from 'lucide-react'
import type { S } from '../api'
import { CONTACT_TYPE_LABELS } from '../labels'

const CONTACT_ICON: Record<S['ContactMethodType'], typeof Mail> = { email: Mail, phone: Phone, telegram: Send, other: MessageCircle }

/** Ссылка, по которой контакт открывается в один клик: почта, звонок, Telegram. */
function contactHref({ type, value }: S['ContactMethod']): string | null {
  const v = (value ?? '').trim()
  if (!v) return null
  if (type === 'email') return `mailto:${v}`
  if (type === 'phone') return `tel:${v.replace(/[^\d+]/g, '')}`
  if (type === 'telegram') {
    const name = v.replace(/^(https?:\/\/)?(t\.me\/|telegram\.me\/)?@?/i, '')
    return /^\w{3,}$/.test(name) ? `https://t.me/${name}` : null
  }
  return /^https?:\/\//i.test(v) ? v : null
}

/** Приглашение по отклику: как связаться с рекрутером и что он написал. */
export function InviteContact({ contact, message }: { contact: S['ContactMethod'] | null | undefined; message?: string | null }) {
  if (!contact?.value) {
    return (
      <p className="mt-3 rounded-md bg-success-soft p-3 text-sm text-ink">Рекрутер свяжется с вами сам — ваши контакты у него есть.</p>
    )
  }
  const Icon = CONTACT_ICON[contact.type]
  const href = contactHref(contact)
  const external = href?.startsWith('http')
  return (
    <div className="mt-3 flex flex-col gap-2 rounded-md bg-success-soft p-3" data-testid="invite-contact">
      <p className="text-sm font-semibold text-ink">Как связаться с рекрутером</p>
      <div className="flex items-center gap-2.5">
        <span className="flex size-9 shrink-0 items-center justify-center rounded-md bg-surface text-success">
          <Icon className="size-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-[13px] text-muted">{CONTACT_TYPE_LABELS[contact.type]}</p>
          {href ? (
            <a
              href={href}
              {...(external ? { target: '_blank', rel: 'noreferrer' } : {})}
              className="font-semibold break-all text-fsp-plum hover:underline"
            >
              {contact.value}
            </a>
          ) : (
            <p className="font-semibold break-all text-ink">{contact.value}</p>
          )}
        </div>
      </div>
      {message && <p className="text-sm whitespace-pre-line text-ink">«{message}»</p>}
      <p className="text-[13px] text-muted">Напишите рекрутеру сами или дождитесь, пока он свяжется с вами.</p>
    </div>
  )
}
