import { CalendarClock, Gauge, Lock, ShieldAlert, Wallet } from 'lucide-react'
import { Card, CardHeader } from '@/shared/ui'
import { useQuota } from '../api'

/** Правила выхода на контакт — коротко, для рекрутера. */
export function ContactRules({ className }: { className?: string }) {
  const quota = useQuota()
  const limit = quota.data?.limit ?? 20
  const rules = [
    { icon: Wallet, text: 'В приглашении всегда есть вилка «от–до» в рублях. Ниже ожиданий кандидата отправить нельзя.' },
    { icon: Gauge, text: `Не больше ${limit} активных приглашений на рекрутера — каждое приглашение заметно.` },
    { icon: CalendarClock, text: 'Кандидат отвечает 7 дней, потом приглашение истекает. Отказ приходит с причиной.' },
    { icon: Lock, text: 'ФИО и контакты открываются после принятия приглашения или отклика на вакансию.' },
    { icon: ShieldAlert, text: 'Кандидат может пожаловаться на недобросовестное предложение — жалобы разбирает модератор.' },
  ]
  return (
    <Card className={className}>
      <CardHeader title="Правила выхода на контакт" />
      <ul className="flex flex-col gap-2.5">
        {rules.map(({ icon: Icon, text }) => (
          <li key={text} className="flex gap-2.5 text-sm">
            <Icon className="mt-0.5 size-4 shrink-0 text-fsp-plum" aria-hidden />
            <span>{text}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}
