import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query'
import { Copy, Download, KeyRound, Plug, Send, Trash2, Webhook as WebhookIcon } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { formatDateTime, pluralize } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, Checkbox, EmptyState, ErrorState, Input, SkeletonText, useToast, type Tone } from '@/shared/ui'
import { apiFieldErrors, type S } from '../api'

/**
 * Интеграция с ATS (администратор компании): API-токены, вебхуки и выгрузка данных компании.
 * Только существующие эндпоинты `/api/companies/my/api-tokens`, `/my/webhooks`, `/ats/export`.
 */

type ApiToken = S['ApiToken']
type ApiTokenIssued = S['ApiTokenIssued']
type Webhook = S['Webhook']
type WebhookCreated = S['WebhookCreated']
type Delivery = S['WebhookDeliveryOut']
type CompanyExport = S['CompanyExport']
type WebhookEvent = S['WebhookCreate']['events'][number]

const ik = {
  tokens: ['recruiter', 'integrations', 'tokens'] as const,
  webhooks: ['recruiter', 'integrations', 'webhooks'] as const,
  deliveries: (id: number) => ['recruiter', 'integrations', 'deliveries', id] as const,
}

const EVENT_LABELS: Record<string, string> = {
  'invitation.accepted': 'Кандидат принял приглашение',
  'application.created': 'Новый отклик на вакансию',
  ping: 'Проверка адреса',
}
const EVENT_HINTS: Record<WebhookEvent, string> = {
  'invitation.accepted': 'Придут контакты кандидата и условия приглашения',
  'application.created': 'Придут вакансия и контакты откликнувшегося',
}
const EVENTS = Object.keys(EVENT_HINTS) as WebhookEvent[]

const DELIVERY_LABELS: Record<Delivery['status'], { label: string; tone: Tone }> = {
  pending: { label: 'В очереди', tone: 'warning' },
  delivered: { label: 'Доставлено', tone: 'success' },
  failed: { label: 'Не доставлено', tone: 'danger' },
}

const STATUS_HINTS: Record<number, string> = {
  400: 'адрес отклонил запрос',
  401: 'адрес требует авторизацию',
  403: 'доступ к адресу запрещён',
  404: 'адрес не найден',
  405: 'адрес не принимает POST-запросы',
  408: 'адрес не дождался запроса',
  413: 'адрес не принял размер запроса',
  429: 'слишком много запросов',
  500: 'ошибка на стороне ATS',
  502: 'шлюз ATS не отвечает',
  503: 'ATS временно недоступна',
  504: 'ATS не ответила вовремя',
}

/** Текст ответа ATS для показа: без HTML-тегов (у страницы ошибки — её заголовок), не длиннее 120 символов. */
function plainResponseText(raw: string, limit = 120): string {
  let text = raw
  if (/<[a-z!/][^>]*>/i.test(text)) {
    const title = /<title[^>]*>([\s\S]*?)(<\/title>|$)/i.exec(text)
    text = title ? title[1] : text.replace(/<(script|style)[^>]*>[\s\S]*?<\/\1>/gi, ' ').replace(/<[^>]*>?/g, ' ')
  }
  text = text
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/\s+/g, ' ')
    .trim()
  return text.length <= limit ? text : `${text.slice(0, limit - 1).trimEnd()}…`
}

/** Почему доставка не прошла: «HTTP 405 — адрес не принимает POST-запросы» или ошибка сети. */
function deliveryProblem(d: Pick<Delivery, 'last_error' | 'last_status_code'>): string | null {
  const code = d.last_status_code
  if (code != null && (code < 200 || code >= 300)) {
    const hint = STATUS_HINTS[code] ?? (code >= 500 ? 'ошибка на стороне ATS' : 'адрес отклонил запрос')
    const body = plainResponseText((d.last_error ?? '').replace(/^HTTP \d+:?\s*/, ''))
    const extra = body && !body.toLowerCase().includes(hint.toLowerCase()) ? `: ${body}` : ''
    return `HTTP ${code} — ${hint}${extra}`
  }
  return d.last_error ? plainResponseText(d.last_error) : null
}

function useCopy() {
  const { toast } = useToast()
  return async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text)
      toast({ tone: 'success', title: `${what} скопирован` })
    } catch {
      toast({ tone: 'error', title: 'Не удалось скопировать', description: 'Выделите текст и скопируйте вручную.' })
    }
  }
}

/** Секрет или токен, который показывается один раз. */
function OneTimeSecret({ label, note, value, onHide }: { label: string; note: string; value: string; onHide: () => void }) {
  const copy = useCopy()
  return (
    <div className="mb-4 rounded-md border border-warning bg-warning-soft p-3" role="status">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <p className="mt-0.5 text-[13px] text-muted">{note}</p>
      <code className="mt-2 block rounded-xs border border-line bg-surface px-2 py-1.5 font-mono text-[13px] break-all text-ink select-all">{value}</code>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" leftIcon={<Copy className="size-3.5" aria-hidden />} onClick={() => void copy(value, label.split(' ')[0])}>
          Скопировать
        </Button>
        <Button size="sm" variant="ghost" onClick={onHide}>
          Я сохранил, скрыть
        </Button>
      </div>
    </div>
  )
}

function ListState<T>({ q, empty, children }: { q: UseQueryResult<T[]>; empty: ReactNode; children: (rows: T[]) => ReactNode }) {
  if (q.isPending) return <SkeletonText lines={3} />
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} retrying={q.isFetching} />
  if (!q.data.length) return <>{empty}</>
  return <>{children(q.data)}</>
}

// ---------------- API-токены ----------------

function TokensCard({ onIssued }: { onIssued: (token: string) => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [name, setName] = useState('')
  const [error, setError] = useState<string>()
  const [issued, setIssued] = useState<ApiTokenIssued | null>(null)
  const [revoking, setRevoking] = useState<number | null>(null)
  const tokens = useQuery({ queryKey: ik.tokens, queryFn: () => api.get<ApiToken[]>('/companies/my/api-tokens') })

  const issue = useMutation({
    mutationFn: (n: string) => api.post<ApiTokenIssued>('/companies/my/api-tokens', { name: n }),
    onSuccess: (t) => {
      setIssued(t)
      setName('')
      onIssued(t.token)
      void qc.invalidateQueries({ queryKey: ik.tokens })
    },
    onError: (e) => {
      const f = apiFieldErrors(e)
      if (f.name) setError(f.name)
      else toast({ tone: 'error', title: 'Токен не выпущен', description: getErrorMessage(e) })
    },
  })
  const revoke = useMutation({
    mutationFn: (id: number) => api.delete(`/companies/my/api-tokens/${id}`),
    onSuccess: () => {
      setRevoking(null)
      toast({ tone: 'success', title: 'Токен отозван', description: 'ATS с этим токеном больше не получит данные.' })
      void qc.invalidateQueries({ queryKey: ik.tokens })
    },
    onError: (e) => toast({ tone: 'error', title: 'Токен не отозван', description: getErrorMessage(e) }),
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (!name.trim()) {
      setError('Подпишите токен, например «Хантфлоу»')
      return
    }
    setError(undefined)
    issue.mutate(name.trim())
  }

  return (
    <Card className="min-w-0" data-testid="api-tokens">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <KeyRound className="size-5 text-fsp-plum" aria-hidden /> API-токены
          </span>
        }
        description="ATS забирает по токену вакансии, приглашения и отклики компании. Токен даёт доступ только к данным вашей компании."
      />
      {issued && (
        <OneTimeSecret
          label={`Токен «${issued.name}»`}
          note="Сохраните его сейчас: платформа хранит только хеш токена, показать его ещё раз не сможет. Потеряли — выпустите новый и отзовите старый."
          value={issued.token}
          onHide={() => setIssued(null)}
        />
      )}
      <form onSubmit={submit} noValidate className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-start">
        <Input
          label="Для чего токен"
          containerClassName="min-w-0 flex-1"
          placeholder="Например, Хантфлоу"
          maxLength={100}
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={error}
        />
        <Button type="submit" className="sm:mt-[26px]" loading={issue.isPending}>
          Выпустить токен
        </Button>
      </form>
      <ListState
        q={tokens}
        empty={<EmptyState compact icon={<KeyRound aria-hidden />} title="Токенов нет" description="Выпустите токен и вставьте его в настройки ATS." />}
      >
        {(rows) => (
          <ul className="divide-y divide-line rounded-md border border-line" aria-label="Выпущенные токены">
            {rows.map((t) => {
              const active = t.active && !t.revoked_at
              return (
                <li key={t.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
                  <div className="min-w-0 flex-1">
                    <p className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold break-words text-ink">{t.name}</span>
                      <Badge tone={active ? 'success' : 'neutral'}>{active ? 'Действует' : 'Отозван'}</Badge>
                    </p>
                    <p className="text-[13px] text-muted">
                      <code className="font-mono">{t.token_prefix}…</code> · выпущен {formatDateTime(t.created_at)}
                      {' · '}
                      {t.revoked_at
                        ? `отозван ${formatDateTime(t.revoked_at)}`
                        : t.last_used_at
                          ? `последний запрос ${formatDateTime(t.last_used_at)}`
                          : 'ещё не использовался'}
                    </p>
                  </div>
                  {active &&
                    (revoking === t.id ? (
                      <span className="flex flex-wrap items-center gap-2" role="group" aria-label="Подтверждение отзыва">
                        <span className="text-[13px] text-muted">ATS перестанет получать данные.</span>
                        <Button size="sm" variant="danger" loading={revoke.isPending} onClick={() => revoke.mutate(t.id)}>
                          Отозвать
                        </Button>
                        <Button size="sm" variant="ghost" disabled={revoke.isPending} onClick={() => setRevoking(null)}>
                          Отмена
                        </Button>
                      </span>
                    ) : (
                      <Button size="sm" variant="ghost" onClick={() => setRevoking(t.id)}>
                        Отозвать
                      </Button>
                    ))}
                </li>
              )
            })}
          </ul>
        )}
      </ListState>
    </Card>
  )
}

// ---------------- Вебхуки ----------------

function Deliveries({ webhookId }: { webhookId: number }) {
  const q = useQuery({
    queryKey: ik.deliveries(webhookId),
    queryFn: () => api.get<Delivery[]>(`/companies/my/webhooks/${webhookId}/deliveries`, { query: { limit: 10 } }),
  })
  return (
    <div className="mt-2 rounded-md bg-surface-muted p-3">
      <p className="mb-2 text-[13px] font-semibold text-ink">Последние доставки</p>
      <ListState q={q} empty={<p className="text-[13px] text-muted">Событий ещё не было. Нажмите «Проверить» — придёт тестовое событие.</p>}>
        {(rows) => (
          <ul className="flex flex-col gap-1.5 text-[13px]">
            {rows.map((d) => {
              const st = DELIVERY_LABELS[d.status]
              const problem = d.status === 'delivered' ? null : deliveryProblem(d)
              return (
                <li key={d.id} className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                  <Badge tone={st.tone}>{st.label}</Badge>
                  <span className="text-ink">{EVENT_LABELS[d.event] ?? d.event}</span>
                  <span className="w-full text-muted">
                    {formatDateTime(d.delivered_at ?? d.created_at)}
                    {d.last_status_code != null && !problem ? ` · ответ ${d.last_status_code}` : ''}
                    {` · ${pluralize(d.attempts, ['попытка', 'попытки', 'попыток'])}`}
                  </span>
                  {problem && <span className="w-full break-words text-danger">{problem}</span>}
                </li>
              )
            })}
          </ul>
        )}
      </ListState>
    </div>
  )
}

function WebhookRow({ hook }: { hook: Webhook }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [open, setOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const ping = useMutation({
    mutationFn: () => api.post<Delivery>(`/companies/my/webhooks/${hook.id}/ping`),
    onSuccess: (d) => {
      setOpen(true)
      void qc.invalidateQueries({ queryKey: ik.deliveries(hook.id) })
      if (d.status === 'delivered') toast({ tone: 'success', title: 'Адрес отвечает', description: `Тестовое событие доставлено (ответ ${d.last_status_code ?? 200}).` })
      else
        toast({
          tone: 'error',
          title: 'Адрес не принял событие',
          description: `${deliveryProblem(d) ?? 'Нет ответа'}. Платформа повторит отправку позже.`,
        })
    },
    onError: (e) => toast({ tone: 'error', title: 'Проверка не отправлена', description: getErrorMessage(e) }),
  })
  const remove = useMutation({
    mutationFn: () => api.delete(`/companies/my/webhooks/${hook.id}`),
    onSuccess: () => {
      toast({ tone: 'success', title: 'Вебхук удалён' })
      void qc.invalidateQueries({ queryKey: ik.webhooks })
    },
    onError: (e) => toast({ tone: 'error', title: 'Вебхук не удалён', description: getErrorMessage(e) }),
  })
  return (
    <li className="px-3 py-2.5">
      <p className="font-mono text-[13px] break-all text-ink">{hook.url}</p>
      <p className="mt-1 flex flex-wrap gap-1.5">
        {hook.events.map((e) => (
          <Badge key={e} tone="violet">
            {EVENT_LABELS[e] ?? e}
          </Badge>
        ))}
      </p>
      <p className="mt-1 text-[13px] text-muted">Добавлен {formatDateTime(hook.created_at)}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <Button size="sm" variant="secondary" leftIcon={<Send className="size-3.5" aria-hidden />} loading={ping.isPending} onClick={() => ping.mutate()}>
          Проверить
        </Button>
        <Button size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
          {open ? 'Скрыть доставки' : 'Доставки'}
        </Button>
        {deleting ? (
          <span className="flex flex-wrap items-center gap-2" role="group" aria-label="Подтверждение удаления">
            <Button size="sm" variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>
              Удалить
            </Button>
            <Button size="sm" variant="ghost" disabled={remove.isPending} onClick={() => setDeleting(false)}>
              Отмена
            </Button>
          </span>
        ) : (
          <Button size="sm" variant="ghost" leftIcon={<Trash2 className="size-3.5" aria-hidden />} onClick={() => setDeleting(true)}>
            Удалить
          </Button>
        )}
      </div>
      {open && <Deliveries webhookId={hook.id} />}
    </li>
  )
}

function WebhooksCard() {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState<WebhookEvent[]>([...EVENTS])
  const [secret, setSecret] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [created, setCreated] = useState<WebhookCreated | null>(null)
  const hooks = useQuery({ queryKey: ik.webhooks, queryFn: () => api.get<Webhook[]>('/companies/my/webhooks') })

  const create = useMutation({
    mutationFn: (body: S['WebhookCreate']) => api.post<WebhookCreated>('/companies/my/webhooks', body),
    onSuccess: (w) => {
      setCreated(w)
      setUrl('')
      setSecret('')
      void qc.invalidateQueries({ queryKey: ik.webhooks })
    },
    onError: (e) => {
      const f = apiFieldErrors(e)
      if (Object.keys(f).length) setErrors(f)
      else toast({ tone: 'error', title: 'Вебхук не добавлен', description: getErrorMessage(e) })
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (!/^https?:\/\/\S+\.\S+|^https?:\/\/localhost/i.test(url.trim())) next.url = 'Укажите адрес вида https://ats.example.com/hooks'
    if (!events.length) next.events = 'Выберите хотя бы одно событие'
    if (secret && secret.length < 16) next.secret = 'Секрет — не короче 16 символов, или оставьте пустым'
    setErrors(next)
    if (Object.keys(next).length) return
    create.mutate({ url: url.trim(), events, secret: secret || null })
  }

  const toggle = (ev: WebhookEvent, on: boolean) => setEvents((list) => (on ? [...new Set([...list, ev])] : list.filter((x) => x !== ev)))

  return (
    <Card className="min-w-0" data-testid="webhooks">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <WebhookIcon className="size-5 text-fsp-plum" aria-hidden /> Вебхуки
          </span>
        }
        description="Платформа сама отправит POST-запрос в вашу ATS, когда кандидат примет приглашение или откликнется на вакансию. Не дошло — повторим до 5 раз с паузами."
      />
      {created && (
        <OneTimeSecret
          label="Секрет подписи вебхука"
          note="Сохраните его и укажите в ATS для проверки подписи. Платформа хранит секрет, чтобы подписывать каждое событие, но в интерфейсе больше его не покажет. Потеряли — удалите вебхук и добавьте заново."
          value={created.secret}
          onHide={() => setCreated(null)}
        />
      )}
      <form onSubmit={submit} noValidate className="mb-4 flex flex-col gap-3">
        <Input
          label="Адрес приёма событий"
          type="url"
          inputMode="url"
          placeholder="https://ats.example.com/hooks/fsp"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          error={errors.url}
        />
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink">События</legend>
          <div className="flex flex-col gap-2">
            {EVENTS.map((ev) => (
              <Checkbox key={ev} label={EVENT_LABELS[ev]} description={EVENT_HINTS[ev]} checked={events.includes(ev)} onChange={(e) => toggle(ev, e.target.checked)} />
            ))}
          </div>
          {errors.events && <p className="mt-1 text-[13px] text-danger">{errors.events}</p>}
        </fieldset>
        <Input
          label="Секрет подписи (необязательно)"
          hint="Пусто — сгенерируем сами и покажем один раз"
          value={secret}
          maxLength={128}
          onChange={(e) => setSecret(e.target.value)}
          error={errors.secret}
        />
        <div>
          <Button type="submit" loading={create.isPending}>
            Добавить вебхук
          </Button>
        </div>
      </form>
      <ListState
        q={hooks}
        empty={<EmptyState compact icon={<WebhookIcon aria-hidden />} title="Вебхуков нет" description="Добавьте адрес, и события начнут приходить в ATS сами." />}
      >
        {(rows) => (
          <ul className="divide-y divide-line rounded-md border border-line" aria-label="Вебхуки компании">
            {rows.map((h) => (
              <WebhookRow key={h.id} hook={h} />
            ))}
          </ul>
        )}
      </ListState>
      <details className="mt-3 text-[13px] text-muted">
        <summary className="cursor-pointer font-medium text-ink">Как проверить подпись</summary>
        <p className="mt-1.5">
          Тело — JSON <code className="font-mono">{'{id, event, company_id, created_at, data}'}</code>. Заголовки <code className="font-mono">X-FSP-Event</code>,{' '}
          <code className="font-mono">X-FSP-Delivery</code>, <code className="font-mono">X-FSP-Timestamp</code> и{' '}
          <code className="font-mono break-all">X-FSP-Signature: sha256=HMAC-SHA256(секрет, timestamp + &quot;.&quot; + тело)</code>. Посчитайте подпись своим
          секретом и сравните; запрос старше нескольких минут лучше отклонить.
        </p>
      </details>
    </Card>
  )
}

// ---------------- Выгрузка ----------------

function ExportCard({ token: issuedToken }: { token: string }) {
  const { toast } = useToast()
  const copy = useCopy()
  const [token, setToken] = useState('')
  const [since, setSince] = useState('')
  const [result, setResult] = useState<CompanyExport | null>(null)
  const value = token || issuedToken
  const exp = useMutation({
    mutationFn: () =>
      api.get<CompanyExport>('/companies/ats/export', {
        headers: { 'X-Api-Token': value.trim() },
        query: { since: since ? new Date(since).toISOString() : undefined },
        skipAuthRefresh: true,
      }),
    onSuccess: (data) => {
      setResult(data)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = `ats-export-${new Date().toISOString().slice(0, 10)}.json`
      a.click()
      URL.revokeObjectURL(a.href)
    },
    onError: (e) => {
      setResult(null)
      toast({ tone: 'error', title: 'Выгрузка не получена', description: getErrorMessage(e) })
    },
  })
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  const curl = `curl -H "X-Api-Token: ${value.trim() || '<токен>'}" "${origin}/api/companies/ats/export?since=2026-10-01T00:00:00%2B03:00"`

  return (
    <Card className="min-w-0 lg:col-span-2" data-testid="ats-export">
      <CardHeader
        title={
          <span className="inline-flex items-center gap-2">
            <Download className="size-5 text-fsp-plum" aria-hidden /> Выгрузка для ATS
          </span>
        }
        description="JSON с данными компании: вакансии, приглашения (контакты — только у принятых) и отклики с контактами кандидатов. С параметром since — только изменения после этой даты, для регулярной синхронизации."
      />
      <form
        noValidate
        className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-start"
        onSubmit={(e) => {
          e.preventDefault()
          if (value.trim()) exp.mutate()
        }}
      >
        <Input
          label="API-токен"
          containerClassName="min-w-0 sm:flex-1"
          placeholder={issuedToken ? 'Токен из блока выше' : 'fspt_…'}
          value={token}
          onChange={(e) => setToken(e.target.value)}
          hint={issuedToken && !token ? 'Возьмём только что выпущенный токен' : 'Вставьте токен; в браузере он не сохраняется'}
        />
        <Input
          label="Изменения после"
          hint="Необязательно"
          type="datetime-local"
          containerClassName="sm:w-60"
          value={since}
          onChange={(e) => setSince(e.target.value)}
        />
        <Button type="submit" className="sm:mt-[26px]" disabled={!value.trim()} loading={exp.isPending} leftIcon={<Download className="size-4" aria-hidden />}>
          Скачать выгрузку
        </Button>
      </form>
      {result && (
        <p className="mt-3 rounded-md bg-success-soft px-3 py-2 text-sm text-success" role="status">
          Файл скачан: {pluralize(result.vacancies.length, ['вакансия', 'вакансии', 'вакансий'])},{' '}
          {pluralize(result.invitations.length, ['приглашение', 'приглашения', 'приглашений'])},{' '}
          {pluralize(result.applications.length, ['отклик', 'отклика', 'откликов'])}.
        </p>
      )}
      <div className="mt-4 rounded-md bg-surface-muted p-3 text-[13px] text-muted">
        <p className="font-medium text-ink">Запрос из ATS</p>
        <p className="mt-1">
          <code className="font-mono">GET /api/companies/ats/export</code>, заголовок <code className="font-mono">X-Api-Token</code>, необязательный параметр{' '}
          <code className="font-mono">since</code> (ISO-время). Полное описание полей — в Swagger, раздел companies.
        </p>
        <div className="mt-2 flex items-start gap-2">
          <code className="min-w-0 flex-1 rounded-xs border border-line bg-surface px-2 py-1.5 font-mono break-all text-ink">{curl}</code>
          <Button size="sm" variant="ghost" aria-label="Скопировать команду" onClick={() => void copy(curl, 'Запрос')}>
            <Copy className="size-4" aria-hidden />
          </Button>
        </div>
      </div>
    </Card>
  )
}

/** Раздел «Интеграции» на странице компании — только для администратора компании. */
export function CompanyIntegrations() {
  const [issuedToken, setIssuedToken] = useState('')
  return (
    <section id="integrations" aria-labelledby="integrations-title" className="mt-8">
      <div className="mb-4">
        <h2 id="integrations-title" className="inline-flex items-center gap-2 text-xl font-bold">
          <Plug className="size-5 text-fsp-plum" aria-hidden /> Интеграции с ATS
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted">
          Передавайте кандидатов и отклики в свою систему подбора (Хантфлоу, Talantix, E-Staff и другие): ATS забирает данные по API-токену, а о новых событиях
          платформа сообщает вебхуком. Управляет интеграциями администратор компании.
        </p>
      </div>
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2">
        <TokensCard onIssued={setIssuedToken} />
        <WebhooksCard />
        <ExportCard token={issuedToken} />
      </div>
    </section>
  )
}
