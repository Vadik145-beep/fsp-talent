import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Pencil, Plus, RotateCcw, Save, Scale, Trash2 } from 'lucide-react'
import { api, isApiError } from '@/shared/api'
import { SPECIALIZATION_LABELS, SPECIALIZATION_OPTIONS, type Specialization as SpecCodeT } from '@/shared/config/dictionaries'
import {
  Button,
  Card,
  CardHeader,
  Checkbox,
  EmptyState,
  ErrorState,
  FilterBar,
  Input,
  Modal,
  PageHeader,
  Select,
  SkeletonText,
  Switch,
  Table,
  Tabs,
  Tag,
} from '@/shared/ui'
import {
  fieldErrors,
  useAdminMutation,
  type Grade,
  type GradeThreshold,
  type PlatformSettings,
  type PlatformSettingsUpdate,
  type RankingWeights,
  type Skill,
  type SpecCode,
  type Specialization,
  type Topic,
} from './api'
import { SIX_COLORS } from './components/chartTheme'
import { pct } from './labels'

export default function AdminCatalogPage() {
  const [tab, setTab] = useState('settings')
  return (
    <>
      <PageHeader title="Справочники и настройки" description="Правила платформы: пороги грейдов, кулдауны, квота приглашений, веса ранжирования, справочники." />
      <Tabs
        className="mb-5"
        ariaLabel="Разделы"
        value={tab}
        onChange={setTab}
        items={[
          { id: 'settings', label: 'Правила и пороги' },
          { id: 'dicts', label: 'Специализации и грейды' },
          { id: 'skills', label: 'Стек' },
          { id: 'topics', label: 'Темы теста' },
        ]}
      />
      {tab === 'settings' && <SettingsTab />}
      {tab === 'dicts' && <DictsTab />}
      {tab === 'skills' && <SkillsTab />}
      {tab === 'topics' && <TopicsTab />}
    </>
  )
}

// --- Правила и пороги -----------------------------------------------------------------------
function SettingsTab() {
  const q = useQuery({ queryKey: ['admin', 'settings'], queryFn: () => api.get<PlatformSettings>('/admin/settings') })
  if (q.isPending)
    return (
      <Card>
        <SkeletonText lines={8} />
      </Card>
    )
  if (q.isError)
    return (
      <Card padding="none">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </Card>
    )
  // key: после сохранения форма пересоздаётся от свежих данных.
  return <SettingsForm key={JSON.stringify(q.data)} settings={q.data} />
}

const WEIGHT_LABELS: Record<keyof RankingWeights, { label: string; hint: string }> = {
  stack: { label: 'Совпадение стека', hint: 'обязательные и желательные технологии потребности' },
  theta: { label: 'Результат теста', hint: 'уровень θ внутри категории' },
  fsp: { label: 'Достижения ФСП', hint: 'подтверждённые соревнования' },
  freshness: { label: 'Свежесть профиля', hint: 'давно ли обновлял профиль и проходил тест' },
  salary: { label: 'Зарплата в вилке', hint: 'ожидания кандидата попадают в вилку' },
  work_format: { label: 'Формат работы', hint: 'офис / гибрид / удалёнка совпадают' },
}

/** Функция распределения стандартного нормального (для подсказки «сколько людей в каждом грейде»). */
function normCdf(x: number): number {
  const t = 1 / (1 + 0.3275911 * (Math.abs(x) / Math.SQRT2))
  const y = 1 - ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-(x * x) / 2)
  return x >= 0 ? (1 + y) / 2 : (1 - y) / 2
}

function NumberField(props: {
  id: string
  label: string
  hint: string
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
  max?: number
  suffix?: string
  error?: string
}) {
  return (
    <Input
      id={props.id}
      type="number"
      label={props.label}
      hint={props.hint}
      error={props.error}
      value={Number.isNaN(props.value) ? '' : props.value}
      step={props.step ?? 1}
      min={props.min}
      max={props.max}
      onChange={(e) => props.onChange(e.target.value === '' ? NaN : Number(e.target.value))}
      rightSlot={props.suffix ? <span className="pr-2 text-sm text-muted">{props.suffix}</span> : undefined}
    />
  )
}

/** Доли грейдов — порядковая шкала фирменного синего (токены): Стажёр светлее, Senior темнее. */
const SHARE_RAMP = ['bg-fsp-blue-pale text-fsp-blue-deep', 'bg-fsp-blue-light text-fsp-black', 'bg-fsp-blue text-on-primary', 'bg-fsp-blue-deep text-on-primary']

function SettingsForm({ settings }: { settings: PlatformSettings }) {
  const [draft, setDraft] = useState<PlatformSettings>(() => structuredClone(settings))
  const [errors, setErrors] = useState<Record<string, string>>({})
  /** Специализация, на которую указал бэкенд в invalid_thresholds. */
  const [badSpec, setBadSpec] = useState<string | null>(null)
  const set = <K extends keyof PlatformSettings>(key: K, value: PlatformSettings[K]) => setDraft((d) => ({ ...d, [key]: value }))
  const setThreshold = (spec: string, key: keyof Omit<GradeThreshold, 'specialization'>, value: number) =>
    set('grade_thresholds', draft.grade_thresholds.map((t) => (t.specialization === spec ? { ...t, [key]: value } : t)))
  const setWeight = (key: keyof RankingWeights, value: number) => set('ranking_weights', { ...draft.ranking_weights, [key]: value })

  const changed = useMemo(() => {
    const out: PlatformSettingsUpdate = {}
    for (const key of Object.keys(draft) as Array<keyof PlatformSettings>) {
      if (key === 'id' || key === 'consent_version') continue
      if (JSON.stringify(draft[key]) !== JSON.stringify(settings[key])) (out as Record<string, unknown>)[key] = draft[key]
    }
    return out
  }, [draft, settings])
  const changedCount = Object.keys(changed).length
  const weightSum = Object.values(draft.ranking_weights).reduce((s, v) => s + (Number.isNaN(v) ? 0 : v), 0)
  const weightsOff = Math.abs(weightSum - 1) > 0.001
  // Пустые числовые поля не отправляем: бэкенд принял бы null за «не менять».
  const emptyFields = (Object.keys(changed) as Array<keyof PlatformSettingsUpdate>).filter((k) => typeof changed[k] === 'number' && Number.isNaN(changed[k]))
  // Сумму 100% просим нормировать; нулевые веса пропускаем — их отклонит бэкенд (invalid_weights).
  const mustNormalize = weightsOff && weightSum > 0

  const save = useAdminMutation((body: PlatformSettingsUpdate) => api.put<PlatformSettings>('/admin/settings', body), {
    success: 'Настройки сохранены — применяются сразу',
    onSuccess: () => (setErrors({}), setBadSpec(null)),
  })

  function submit() {
    if (emptyFields.length) {
      setErrors(Object.fromEntries(emptyFields.map((k) => [k, 'Введите число'])))
      return
    }
    save.mutate(changed, {
      onError: (e) => {
        setErrors(fieldErrors(e))
        const spec = isApiError(e) && e.code === 'invalid_thresholds' ? e.details.specialization : null
        setBadSpec(typeof spec === 'string' ? spec : null)
      },
    })
  }

  return (
    <div className="flex flex-col gap-6 pb-20">
      <Card>
        <CardHeader
          title="Пороги грейдов по уровню θ"
          description="Уровень θ из теста переводится в грейд по этим порогам. Ниже порога Junior — Стажёр. Поднимете порог — грейд будет получить труднее. Справа — какая доля людей попадёт в каждый грейд при обычном распределении уровней."
        />
        {errors.grade_thresholds && (
          <p role="alert" className="mb-3 text-sm text-danger">
            {errors.grade_thresholds}
            {badSpec ? ` (${SPECIALIZATION_LABELS[badSpec as SpecCodeT] ?? badSpec})` : ''}
          </p>
        )}
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs font-semibold tracking-wide text-muted uppercase">
                <th className="py-2 pr-3">Специализация</th>
                <th className="px-2 py-2">Junior от</th>
                <th className="px-2 py-2">Middle от</th>
                <th className="px-2 py-2">Senior от</th>
                <th className="py-2 pl-3">Стажёр · Junior · Middle · Senior</th>
              </tr>
            </thead>
            <tbody>
              {draft.grade_thresholds.map((t) => {
                const shares = [normCdf(t.junior_from), normCdf(t.middle_from) - normCdf(t.junior_from), normCdf(t.senior_from) - normCdf(t.middle_from), 1 - normCdf(t.senior_from)]
                const bad = !(t.junior_from < t.middle_from && t.middle_from < t.senior_from) || badSpec === t.specialization
                return (
                  <tr key={t.specialization} className="border-t border-line">
                    <th scope="row" className="py-2 pr-3 text-left font-medium">{SPECIALIZATION_LABELS[t.specialization as SpecCodeT]}</th>
                    {(['junior_from', 'middle_from', 'senior_from'] as const).map((k) => (
                      <td key={k} className="px-2 py-2">
                        <input
                          type="number"
                          step={0.1}
                          aria-label={`${SPECIALIZATION_LABELS[t.specialization as SpecCodeT]}: ${k.replace('_from', '')} от`}
                          aria-invalid={bad || undefined}
                          value={t[k]}
                          onChange={(e) => setThreshold(t.specialization, k, Number(e.target.value))}
                          className="h-9 w-20 rounded-md border border-line-strong px-2 tabular-nums focus:border-fsp-pink focus:shadow-[var(--shadow-focus)] focus:outline-none aria-[invalid=true]:border-danger"
                        />
                      </td>
                    ))}
                    <td className="py-2 pl-3">
                      <div className="flex h-5 gap-0.5 overflow-hidden rounded-sm" aria-label={shares.map((s) => pct(Math.max(0, s))).join(' · ')}>
                        {shares.map((s, i) => (
                          <span key={i} className={`flex items-center justify-center text-[10px] font-semibold ${SHARE_RAMP[i]}`} style={{ width: `${Math.max(0, s) * 100}%` }}>
                            {s > 0.08 ? Math.round(s * 100) : ''}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Грейд и пересдачи" />
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField id="cooldown" label="Смена грейда не чаще" suffix="дней" value={draft.grade_change_cooldown_days} min={0} max={365}
              error={errors.grade_change_cooldown_days} onChange={(v) => set('grade_change_cooldown_days', v)}
              hint="По ТЗ — раз в три месяца. Защищает от «подбора» грейда пересдачами." />
            <NumberField id="retry" label="Повтор неудачной попытки через" suffix="дней" value={draft.retry_cooldown_days} min={0} max={365}
              error={errors.retry_cooldown_days} onChange={(v) => set('retry_cooldown_days', v)}
              hint="Сколько ждать, чтобы снова сдавать тот же грейд." />
          </div>
        </Card>
        <Card>
          <CardHeader title="Приглашения" />
          <div className="grid gap-4 sm:grid-cols-2">
            <NumberField id="quota" label="Квота активных приглашений" suffix="шт." value={draft.invitation_quota} min={1} max={500}
              error={errors.invitation_quota} onChange={(v) => set('invitation_quota', v)}
              hint="Столько приглашений рекрутер может держать без ответа. Меньше квота — приглашение ценнее, спама нет." />
            <NumberField id="ttl" label="Приглашение истекает через" suffix="дней" value={draft.invitation_ttl_days} min={1} max={60}
              error={errors.invitation_ttl_days} onChange={(v) => set('invitation_ttl_days', v)}
              hint="Без ответа кандидата приглашение уходит в «истекло» и освобождает квоту." />
          </div>
        </Card>
        <Card>
          <CardHeader title="Адаптивный тест" />
          <div className="grid gap-4 sm:grid-cols-3">
            <NumberField id="se" label="Точность для остановки" value={draft.cat_se_stop} step={0.01} min={0.05} max={2}
              error={errors.cat_se_stop} onChange={(v) => set('cat_se_stop', v)}
              hint="Тест заканчивается, когда погрешность ниже. Меньше — точнее, но длиннее." />
            <NumberField id="maxitems" label="Максимум задач" value={draft.cat_max_items} min={5} max={50}
              error={errors.cat_max_items} onChange={(v) => set('cat_max_items', v)} hint="Потолок длины теста." />
            <NumberField id="exposure" label="Лимит показов задачи" suffix="%" value={Math.round(draft.exposure_max_share * 100)} min={1} max={100}
              error={errors.exposure_max_share} onChange={(v) => set('exposure_max_share', v / 100)}
              hint="Задачу видят не больше чем в этой доле тестов — её труднее слить." />
          </div>
        </Card>
        <Card>
          <CardHeader
            title="Веса ранжирования кандидатов"
            description="Из чего складывается место кандидата в подборке. Сумма весов — 100%."
            actions={
              mustNormalize ? (
                <Button size="sm" variant="secondary" leftIcon={<Scale className="size-4" aria-hidden />}
                  onClick={() => set('ranking_weights', Object.fromEntries(Object.entries(draft.ranking_weights).map(([k, v]) => [k, Math.round((v / weightSum) * 100) / 100])) as RankingWeights)}>
                  Нормировать
                </Button>
              ) : undefined
            }
          />
          <div className="mb-4 flex h-3 gap-0.5 overflow-hidden rounded-full" aria-hidden>
            {(Object.keys(WEIGHT_LABELS) as Array<keyof RankingWeights>).map((k, i) => (
              <span key={k} style={{ width: `${(draft.ranking_weights[k] / (weightSum || 1)) * 100}%`, background: SIX_COLORS[i] }} />
            ))}
          </div>
          <div className="flex flex-col gap-3">
            {(Object.keys(WEIGHT_LABELS) as Array<keyof RankingWeights>).map((k, i) => (
              <label key={k} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-sm">
                <span>
                  <span className="mr-2 inline-block size-2.5 rounded-full" style={{ background: SIX_COLORS[i] }} aria-hidden />
                  <span className="font-medium text-ink">{WEIGHT_LABELS[k].label}</span>
                  <span className="block pl-[18px] text-[13px] text-muted">{WEIGHT_LABELS[k].hint}</span>
                </span>
                <b className="w-12 text-right tabular-nums">{Math.round(draft.ranking_weights[k] * 100)}%</b>
                <input type="range" min={0} max={1} step={0.05} value={draft.ranking_weights[k]} aria-label={WEIGHT_LABELS[k].label}
                  onChange={(e) => setWeight(k, Number(e.target.value))} className="col-span-2 accent-primary" />
              </label>
            ))}
          </div>
          <p role={weightsOff ? 'alert' : undefined} className={`mt-3 text-sm ${weightsOff ? 'text-warning' : 'text-muted'}`}>
            Сумма: {Math.round(weightSum * 100)}%{mustNormalize ? ' — нажмите «Нормировать», чтобы получилось 100%.' : ''}
          </p>
          {errors.ranking_weights && <p role="alert" className="text-sm text-danger">{errors.ranking_weights}</p>}
        </Card>
      </div>

      <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap items-center justify-end gap-3 border-t border-line bg-surface/95 px-4 py-3 backdrop-blur sm:mx-0 sm:rounded-lg sm:border">
        <span className="mr-auto text-sm text-muted">
          {changedCount ? `Изменено настроек: ${changedCount}` : 'Изменений нет'}
          {errors._ && <span role="alert" className="ml-2 text-danger">{errors._}</span>}
        </span>
        <Button variant="ghost" leftIcon={<RotateCcw className="size-4" aria-hidden />} disabled={!changedCount} onClick={() => (setDraft(structuredClone(settings)), setErrors({}), setBadSpec(null))}>
          Отменить
        </Button>
        <Button leftIcon={<Save className="size-4" aria-hidden />} disabled={!changedCount || mustNormalize} loading={save.isPending} onClick={submit}>
          Сохранить
        </Button>
      </div>
    </div>
  )
}

// --- Специализации и грейды -------------------------------------------------------------------
function DictsTab() {
  const specs = useQuery({ queryKey: ['admin', 'catalog', 'specializations'], queryFn: () => api.get<Specialization[]>('/catalog/specializations') })
  const grades = useQuery({ queryKey: ['admin', 'catalog', 'grades'], queryFn: () => api.get<Grade[]>('/catalog/grades') })
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader title="Специализации" description="Код фиксирован, меняются подпись, описание и видимость." />
        {specs.isPending ? <SkeletonText lines={6} /> : specs.isError ? <ErrorState error={specs.error} onRetry={() => specs.refetch()} /> : (
          <div className="flex flex-col divide-y divide-line">
            {specs.data.map((s) => <SpecRow key={JSON.stringify(s)} spec={s} />)}
          </div>
        )}
      </Card>
      <Card>
        <CardHeader title="Грейды" description="Порядок и коды фиксированы, меняется подпись." />
        {grades.isPending ? <SkeletonText lines={4} /> : grades.isError ? <ErrorState error={grades.error} onRetry={() => grades.refetch()} /> : (
          <div className="flex flex-col gap-3">
            {[...grades.data].sort((a, b) => a.order - b.order).map((g) => <GradeRow key={JSON.stringify(g)} grade={g} />)}
          </div>
        )}
      </Card>
    </div>
  )
}

function SpecRow({ spec }: { spec: Specialization }) {
  const [label, setLabel] = useState(spec.label)
  const [active, setActive] = useState(spec.active ?? true)
  const m = useAdminMutation((body: { label: string; active: boolean }) => api.patch<Specialization>(`/admin/catalog/specializations/${spec.id}`, body), {
    success: (r) => `Специализация «${r.label}» сохранена`,
  })
  const dirty = label !== spec.label || active !== (spec.active ?? true)
  return (
    <div className="flex flex-col gap-2 py-3 sm:flex-row sm:items-end">
      <Input label={<span>Подпись <span className="font-mono text-xs text-muted">{spec.id}</span></span>} value={label} onChange={(e) => setLabel(e.target.value)} containerClassName="flex-1" hint={spec.description} />
      <Switch checked={active} onChange={setActive} label="Показывать" className="sm:mb-6 sm:w-36" />
      <Button size="sm" variant="secondary" className="sm:mb-6" disabled={!dirty || !label.trim()} loading={m.isPending} onClick={() => m.mutate({ label, active })}>
        Сохранить
      </Button>
    </div>
  )
}

function GradeRow({ grade }: { grade: Grade }) {
  const [label, setLabel] = useState(grade.label)
  const m = useAdminMutation((body: { label: string }) => api.patch<Grade>(`/admin/catalog/grades/${grade.id}`, body), { success: (r) => `Грейд «${r.label}» сохранён` })
  return (
    <div className="flex items-end gap-2">
      <Input label={<span>Подпись <span className="font-mono text-xs text-muted">{grade.id}</span></span>} value={label} onChange={(e) => setLabel(e.target.value)} containerClassName="flex-1" />
      <Button size="md" variant="secondary" disabled={label === grade.label || !label.trim()} loading={m.isPending} onClick={() => m.mutate({ label })}>
        Сохранить
      </Button>
    </div>
  )
}

// --- Стек --------------------------------------------------------------------------------------
function SkillsTab() {
  const [search, setSearch] = useState('')
  const [spec, setSpec] = useState('')
  const [editing, setEditing] = useState<Skill | 'new' | null>(null)
  const q = useQuery({ queryKey: ['admin', 'catalog', 'skills'], queryFn: () => api.get<Skill[]>('/catalog/skills') })
  const del = useAdminMutation((id: string) => api.delete(`/admin/catalog/skills/${id}`), { success: 'Технология удалена' })
  const rows = (q.data ?? []).filter(
    (s) => (!spec || s.specializations.includes(spec as SpecCode)) && (!search.trim() || s.label.toLowerCase().includes(search.trim().toLowerCase())),
  )

  return (
    <>
      <FilterBar
        search={{ value: search, onChange: setSearch, placeholder: 'Технология' }}
        activeCount={[search, spec].filter(Boolean).length}
        onReset={() => (setSearch(''), setSpec(''))}
        actions={<Button leftIcon={<Plus className="size-4" aria-hidden />} onClick={() => setEditing('new')}>Добавить</Button>}
      >
        <Select aria-label="Специализация" containerClassName="sm:w-52" placeholder="Все специализации" options={SPECIALIZATION_OPTIONS} value={spec} onChange={(e) => setSpec(e.target.value)} />
      </FilterBar>
      {q.isError ? (
        <Card padding="none"><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>
      ) : (
        <Table
          caption="Справочник стека"
          rows={rows}
          rowKey={(s) => s.id}
          loading={q.isPending}
          defaultSort={{ key: 'label', direction: 'asc' }}
          empty={<EmptyState compact title="Технологий не найдено" />}
          columns={[
            { key: 'label', header: 'Технология', sortable: true, render: (s) => <span className="font-medium">{s.label}</span> },
            { key: 'id', header: 'Код', hideOnMobile: true, render: (s) => <span className="font-mono text-xs text-muted">{s.id}</span> },
            { key: 'specializations', header: 'Специализации', render: (s) => <div className="flex flex-wrap gap-1">{s.specializations.map((x) => <Tag key={x}>{SPECIALIZATION_LABELS[x]}</Tag>)}</div> },
            {
              key: 'actions', header: '', align: 'right',
              render: (s) => (
                <div className="flex justify-end gap-1">
                  <Button size="sm" variant="ghost" aria-label={`Изменить ${s.label}`} onClick={() => setEditing(s)}>
                    <Pencil className="size-4" aria-hidden />
                  </Button>
                  <Button size="sm" variant="ghost" aria-label={`Удалить ${s.label}`} loading={del.isPending && del.variables === s.id} onClick={() => del.mutate(s.id)}>
                    <Trash2 className="size-4" aria-hidden />
                  </Button>
                </div>
              ),
            },
          ]}
        />
      )}
      <p className="mt-2 text-[13px] text-muted">Технологию, которая уже указана в профилях, вакансиях или потребностях, удалить нельзя.</p>
      {editing && <SkillModal skill={editing === 'new' ? null : editing} onClose={() => setEditing(null)} />}
    </>
  )
}

/** Добавить технологию (skill = null) или изменить подпись и специализации существующей (код не меняется). */
function SkillModal({ skill, onClose }: { skill: Skill | null; onClose: () => void }) {
  const [label, setLabel] = useState(skill?.label ?? '')
  const [id, setId] = useState('')
  const [specs, setSpecs] = useState<SpecCode[]>(skill?.specializations ?? [])
  const [errors, setErrors] = useState<Record<string, string>>({})
  const autoId = label.trim().toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9_+.#-]/g, '')
  const m = useAdminMutation(
    (body: Skill) => (skill ? api.put<Skill>(`/admin/catalog/skills/${skill.id}`, body) : api.post<Skill>('/admin/catalog/skills', body)),
    { success: (s) => (skill ? `Технология «${s.label}» сохранена` : `Добавлена технология «${s.label}»`), onSuccess: onClose },
  )
  const finalId = skill ? skill.id : id.trim() || autoId
  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title={skill ? `Технология «${skill.label}»` : 'Новая технология'}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Отмена</Button>
          <Button
            loading={m.isPending}
            disabled={!label.trim() || !specs.length || !finalId}
            onClick={() => m.mutate({ id: finalId, label: label.trim(), specializations: specs }, { onError: (e) => setErrors(fieldErrors(e)) })}
          >
            {skill ? 'Сохранить' : 'Добавить'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errors._ && <p role="alert" className="text-sm text-danger">{errors._}</p>}
        <Input label="Название" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Например, Svelte" error={errors.label} required />
        {skill ? (
          <p className="text-sm text-muted">Код <span className="font-mono text-ink">{skill.id}</span> не меняется: на него ссылаются профили и вакансии.</p>
        ) : (
          <Input label="Код" value={id} onChange={(e) => setId(e.target.value)} placeholder={autoId || 'svelte'} hint="Латиница в нижнем регистре; пусто — из названия" error={errors.id} />
        )}
        <fieldset>
          <legend className="mb-2 text-sm font-medium">Специализации</legend>
          <div className="grid grid-cols-2 gap-2">
            {SPECIALIZATION_OPTIONS.map((o) => (
              <Checkbox key={o.value} label={o.label} checked={specs.includes(o.value)}
                onChange={(e) => setSpecs((s) => (e.target.checked ? [...s, o.value] : s.filter((x) => x !== o.value)))} />
            ))}
          </div>
          {errors.specializations && <p role="alert" className="mt-1 text-[13px] text-danger">{errors.specializations}</p>}
        </fieldset>
      </div>
    </Modal>
  )
}

// --- Темы теста ----------------------------------------------------------------------------------
function TopicsTab() {
  const [spec, setSpec] = useState('')
  const [adding, setAdding] = useState(false)
  const q = useQuery({ queryKey: ['admin', 'catalog', 'topics'], queryFn: () => api.get<Topic[]>('/catalog/topics') })
  const del = useAdminMutation((id: string) => api.delete(`/admin/catalog/topics/${id}`), { success: 'Тема удалена' })
  const rows = (q.data ?? []).filter((t) => !spec || t.specialization === spec)

  return (
    <>
      <FilterBar
        activeCount={spec ? 1 : 0}
        onReset={() => setSpec('')}
        actions={<Button leftIcon={<Plus className="size-4" aria-hidden />} onClick={() => setAdding(true)}>Добавить тему</Button>}
      >
        <Select aria-label="Специализация" containerClassName="sm:w-52" placeholder="Все специализации" options={SPECIALIZATION_OPTIONS} value={spec} onChange={(e) => setSpec(e.target.value)} />
      </FilterBar>
      {q.isPending ? (
        <Card><SkeletonText lines={6} /></Card>
      ) : q.isError ? (
        <Card padding="none"><ErrorState error={q.error} onRetry={() => q.refetch()} /></Card>
      ) : rows.length === 0 ? (
        <Card padding="none"><EmptyState compact title="Тем не найдено" /></Card>
      ) : (
        <Card padding="none">
          <ul className="divide-y divide-line">
            {rows.map((t) => (
              <TopicRow key={JSON.stringify(t)} topic={t} deleting={del.isPending && del.variables === t.id} onDelete={() => del.mutate(t.id)} />
            ))}
          </ul>
        </Card>
      )}
      <p className="mt-2 text-[13px] text-muted">
        Тема — раздел теста внутри специализации, по ней строится покрытие банка задач. Тему, по которой есть шаблоны задач, удалить нельзя.
      </p>
      {adding && <AddTopicModal defaultSpec={(spec || 'backend') as SpecCode} onClose={() => setAdding(false)} />}
    </>
  )
}

function TopicRow({ topic, deleting, onDelete }: { topic: Topic; deleting: boolean; onDelete: () => void }) {
  const [label, setLabel] = useState(topic.label)
  const [error, setError] = useState<string>()
  const m = useAdminMutation((body: { label: string }) => api.patch<Topic>(`/admin/catalog/topics/${topic.id}`, body), {
    success: (r) => `Тема «${r.label}» сохранена`,
    onSuccess: () => setError(undefined),
  })
  return (
    <li className="flex flex-col gap-2 px-5 py-3 sm:flex-row sm:items-start">
      <Input
        label={
          <span>
            {SPECIALIZATION_LABELS[topic.specialization as SpecCodeT] ?? topic.specialization} <span className="font-mono text-xs text-muted">{topic.id}</span>
          </span>
        }
        value={label}
        onChange={(e) => setLabel(e.target.value)}
        error={error}
        containerClassName="flex-1"
      />
      <div className="flex gap-1 sm:mt-6">
        <Button size="sm" variant="secondary" disabled={label === topic.label || !label.trim()} loading={m.isPending}
          onClick={() => m.mutate({ label: label.trim() }, { onError: (e) => setError(fieldErrors(e).label) })}>
          Сохранить
        </Button>
        <Button size="sm" variant="ghost" aria-label={`Удалить тему ${topic.label}`} loading={deleting} onClick={onDelete}>
          <Trash2 className="size-4" aria-hidden />
        </Button>
      </div>
    </li>
  )
}

function AddTopicModal({ defaultSpec, onClose }: { defaultSpec: SpecCode; onClose: () => void }) {
  const [spec, setSpec] = useState<SpecCode>(defaultSpec)
  const [label, setLabel] = useState('')
  const [code, setCode] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const m = useAdminMutation((body: { id: string; specialization: SpecCode; label: string }) => api.post<Topic>('/admin/catalog/topics', body), {
    success: (t) => `Добавлена тема «${t.label}»`,
    onSuccess: onClose,
  })
  const suffix = code.trim().toLowerCase()
  return (
    <Modal
      open
      onClose={onClose}
      size="sm"
      title="Новая тема теста"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Отмена</Button>
          <Button loading={m.isPending} disabled={!label.trim() || !suffix}
            onClick={() => m.mutate({ id: `${spec}.${suffix}`, specialization: spec, label: label.trim() }, { onError: (e) => setErrors(fieldErrors(e)) })}>
            Добавить
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {errors._ && <p role="alert" className="text-sm text-danger">{errors._}</p>}
        <Select label="Специализация" options={SPECIALIZATION_OPTIONS} value={spec} onChange={(e) => setSpec(e.target.value as SpecCode)} error={errors.specialization} />
        <Input label="Название" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Например, Кэширование" error={errors.label} required />
        <Input
          label="Код"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="caching"
          hint={`Полный код: ${spec}.${suffix || '…'} — латиница в нижнем регистре, цифры и _`}
          error={errors.id}
          required
        />
      </div>
    </Modal>
  )
}
