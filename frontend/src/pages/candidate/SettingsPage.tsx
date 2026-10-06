import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Eye, ShieldCheck, Unlink } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { api, getErrorMessage } from '@/shared/api'
import { formatDate } from '@/shared/lib/format'
import { Badge, Button, Card, CardHeader, Modal, PageHeader, Skeleton, Switch, useToast } from '@/shared/ui'
import {
  invalidateCandidate,
  qk,
  useConsents,
  useProfile,
  useSettings,
  useSkillLabel,
  type CandidateSettings,
  type PrivacySettings,
} from './api'
import { EmployerPreview } from './components/EmployerPreview'
import { FspLinkButton } from './components/FspLinkButton'
import { QueryView } from './components/QueryView'

const PRIVACY_FIELDS: Array<{ key: keyof PrivacySettings; label: string; description: string }> = [
  { key: 'show_city', label: 'Город', description: 'Помогает работодателям из вашего города' },
  { key: 'show_experience', label: 'Стаж', description: 'Сколько лет коммерческого опыта' },
  { key: 'show_links', label: 'Ссылки', description: 'GitHub, портфолио' },
  { key: 'show_fsp_achievements', label: 'Достижения ФСП', description: 'Бейджи «подтверждено ФСП» и ФСП-скор' },
]

export default function SettingsPage() {
  const settings = useSettings()
  return (
    <>
      <PageHeader title="Настройки" description="Что видит работодатель до принятия приглашения, согласия и ФСП ID." />
      <QueryView query={settings}>{(s) => <SettingsView s={s} />}</QueryView>
    </>
  )
}

function SettingsView({ s }: { s: CandidateSettings }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const profile = useProfile()
  const consents = useConsents()
  const skillLabel = useSkillLabel()
  const [confirm, setConfirm] = useState<'publication' | 'unlink' | null>(null)
  const { reloadUser } = useAuth()

  const setSettings = (next: CandidateSettings) => client.setQueryData(qk.settings, next)
  const onFail = (title: string) => (err: unknown) => {
    void client.invalidateQueries({ queryKey: qk.settings })
    toast({ tone: 'error', title, description: getErrorMessage(err) })
  }

  const privacy = useMutation({
    mutationFn: (p: PrivacySettings) => api.put<CandidateSettings>('/candidates/me/settings/privacy', p),
    onMutate: (p) => setSettings({ ...s, privacy: p }),
    onSuccess: (next) => {
      setSettings(next)
      void client.invalidateQueries({ queryKey: qk.profile })
    },
    onError: onFail('Настройка не сохранилась'),
  })

  const jobSearch = useMutation({
    mutationFn: (paused: boolean) => api.put<CandidateSettings>('/candidates/me/settings/job-search', { paused }),
    onMutate: (paused) => setSettings({ ...s, job_search_paused: paused }),
    onSuccess: (next) => {
      setSettings(next)
      void client.invalidateQueries({ queryKey: qk.dashboard })
      toast({ tone: 'info', title: next.job_search_paused ? 'Поиск на паузе' : 'Поиск снова включён', description: next.job_search_paused ? 'Профиль скрыт из выдачи работодателям.' : 'Профиль снова виден в выдаче.' })
    },
    onError: onFail('Не удалось изменить статус поиска'),
  })

  const publication = useMutation({
    mutationFn: (granted: boolean) => api.put<CandidateSettings>('/candidates/me/settings/publication', { granted }),
    onMutate: (granted) => setSettings({ ...s, publication_consent: granted }),
    onSuccess: (next) => {
      setConfirm(null)
      setSettings(next)
      void invalidateCandidate(client)
      toast({ tone: next.publication_consent ? 'success' : 'info', title: next.publication_consent ? 'Согласие дано' : 'Согласие отозвано', description: next.publication_consent ? 'Профиль появится в выдаче.' : 'Профиль скрыт из выдачи.' })
    },
    onError: onFail('Не удалось изменить согласие'),
  })

  const unlink = useMutation({
    mutationFn: () => api.delete('/auth/fsp-link'),
    onSuccess: () => {
      setConfirm(null)
      void invalidateCandidate(client)
      void reloadUser().catch(() => undefined)
      toast({ tone: 'info', title: 'ФСП ID отвязан', description: 'Достижения скрыты из профиля и выдачи.' })
    },
    onError: onFail('Не удалось отвязать ФСП ID'),
  })

  const processing = consents.data?.find((c) => c.type === 'processing')
  const pub = consents.data?.find((c) => c.type === 'publication')

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="grid gap-5">
        <Card>
          <CardHeader title="Что видно до принятия приглашения" description="ФИО и контакты скрыты всегда — их работодатель увидит только после вашего согласия." />
          <div className="grid divide-y divide-line">
            {PRIVACY_FIELDS.map((f) => (
              <Switch
                key={f.key}
                className="py-3 first:pt-0 last:pb-0"
                label={f.label}
                description={f.description}
                checked={!!s.privacy[f.key]}
                onChange={(v) => privacy.mutate({ ...s.privacy, [f.key]: v })}
              />
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Поиск работы" />
          <Switch
            label="Не ищу работу"
            description="Профиль пропадёт из выдачи, новые приглашения не придут. Категория и история сохранятся."
            checked={s.job_search_paused}
            onChange={(v) => jobSearch.mutate(v)}
          />
        </Card>

        <Card>
          <CardHeader title="Согласия" description="Версия текста и дата хранятся — по 152-ФЗ." />
          {consents.isPending ? (
            <Skeleton className="h-16 w-full" />
          ) : (
            <div className="grid divide-y divide-line">
              <div className="flex items-start justify-between gap-4 pb-3">
                <div>
                  <p className="text-sm font-medium text-ink">Обработка персональных данных</p>
                  <p className="text-[13px] text-muted">
                    {processing?.granted_at ? `Дано ${formatDate(processing.granted_at)}, версия ${processing.version}. ` : ''}
                    Обязательно для работы сервиса; отозвать — через удаление аккаунта.
                  </p>
                </div>
                <Badge tone="success">Дано</Badge>
              </div>
              <Switch
                className="pt-3"
                label="Публикация профиля работодателям"
                description={
                  s.publication_consent
                    ? `Обезличенный профиль виден в поиске${pub?.granted_at ? ` · дано ${formatDate(pub.granted_at)}` : ''}.`
                    : 'Без этого согласия вас нет в поиске — только отклики на вакансии.'
                }
                checked={s.publication_consent}
                onChange={(v) => (v ? publication.mutate(true) : setConfirm('publication'))}
              />
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="ФСП ID" description="Для входа через ФСП ID и подтверждённых достижений." />
          {s.fsp_linked ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="inline-flex items-center gap-2 text-[15px] text-ink">
                <ShieldCheck className="size-5 text-success" aria-hidden />
                Привязан: <span className="font-mono font-semibold">{s.fsp_id}</span>
              </p>
              <Button variant="secondary" leftIcon={<Unlink className="size-4" aria-hidden />} onClick={() => setConfirm('unlink')}>
                Отвязать
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[15px] text-muted">Не привязан. Без ФСП ID всё работает — просто без бонуса за достижения.</p>
              <FspLinkButton returnTo="/candidate/settings" />
            </div>
          )}
        </Card>
      </div>

      <aside className="lg:sticky lg:top-20">
        <p className="mb-2 inline-flex items-center gap-2 text-sm font-semibold text-ink">
          <Eye className="size-4 text-fsp-plum" aria-hidden /> Так вас видит работодатель
        </p>
        {profile.data ? (
          <EmployerPreview
            profile={profile.data}
            privacy={s.privacy}
            hidden={{ paused: s.job_search_paused, noConsent: !s.publication_consent }}
            skillLabel={skillLabel}
          />
        ) : (
          <Card>
            <Skeleton className="h-10 w-2/3" />
            <Skeleton className="mt-4 h-24 w-full" />
          </Card>
        )}
        <p className="mt-2 text-[13px] text-muted">Превью меняется сразу, как только вы переключаете настройки.</p>
      </aside>

      <Modal
        open={confirm === 'publication'}
        onClose={() => setConfirm(null)}
        size="sm"
        title="Отозвать согласие на публикацию?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Отмена
            </Button>
            <Button variant="danger" loading={publication.isPending} onClick={() => publication.mutate(false)}>
              Отозвать
            </Button>
          </>
        }
      >
        <p className="text-[15px] text-ink">Профиль сразу пропадёт из поиска работодателей. Уже принятые приглашения останутся.</p>
      </Modal>
      <Modal
        open={confirm === 'unlink'}
        onClose={() => setConfirm(null)}
        size="sm"
        title="Отвязать ФСП ID?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Отмена
            </Button>
            <Button variant="danger" loading={unlink.isPending} onClick={() => unlink.mutate()}>
              Отвязать
            </Button>
          </>
        }
      >
        <p className="text-[15px] text-ink">Достижения ФСП скроются из профиля и выдачи. Вход по почте не изменится. Привязать снова можно в любой момент.</p>
      </Modal>
    </div>
  )
}
