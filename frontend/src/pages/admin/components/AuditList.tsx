import { formatDateTime } from '@/shared/lib/format'
import { Badge } from '@/shared/ui'
import type { AuditEntry } from '../api'
import { AUDIT_ACTION_LABELS, AUDIT_ACTION_TONES } from '../labels'

/** Компактный список записей журнала (для карточки пользователя). */
export function AuditList({ entries }: { entries: AuditEntry[] }) {
  return (
    <ol className="flex flex-col gap-3">
      {entries.map((e) => (
        <li key={e.id} className="border-l-2 border-line pl-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={AUDIT_ACTION_TONES[e.action] ?? 'violet'}>{AUDIT_ACTION_LABELS[e.action] ?? e.action}</Badge>
            <span className="text-xs text-muted">{formatDateTime(e.at)}</span>
          </div>
          <p className="mt-1 text-sm text-ink">{e.summary}</p>
        </li>
      ))}
    </ol>
  )
}
