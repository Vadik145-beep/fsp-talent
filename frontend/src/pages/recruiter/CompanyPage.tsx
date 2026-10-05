import { useState, type FormEvent, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Globe, Mail, MapPin, Pencil, Phone } from 'lucide-react'
import { useAuth } from '@/app/auth/AuthContext'
import { api, isApiError } from '@/shared/api'
import { Avatar, Badge, Button, Card, CardHeader, Input, PageHeader, Table, Textarea, useToast } from '@/shared/ui'
import { rk, useCompany, useCompanyRecruiters, type Company, type S } from './api'
import { ContactRules } from './components/ContactRules'
import { QueryState } from './components/QueryState'
import { QuotaMeter } from './components/QuotaMeter'

/** Профиль компании, рекрутеры, квота и правила. */
export default function RecruiterCompanyPage() {
  const { user } = useAuth()
  const company = useCompany()
  const recruiters = useCompanyRecruiters()
  const [editing, setEditing] = useState(false)
  const me = recruiters.data?.find((r) => r.user_id === user?.userId)
  const canEdit = Boolean(me?.is_company_admin)

  return (
    <>
      <PageHeader
        title="Компания"
        description="Так компанию видят кандидаты в приглашениях и вакансиях."
        actions={
          canEdit && !editing && company.data ? (
            <Button variant="secondary" onClick={() => setEditing(true)} leftIcon={<Pencil className="size-4" aria-hidden />}>
              Редактировать
            </Button>
          ) : undefined
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <div className="flex flex-col gap-4">
          <QueryState query={company} loading={<Card><div className="h-40" /></Card>}>
            {(c) => (editing ? <CompanyForm company={c} onDone={() => setEditing(false)} /> : <CompanyView company={c} />)}
          </QueryState>
          <Card padding="none">
            <div className="px-5 pt-5">
              <CardHeader title="Рекрутеры компании" />
            </div>
            <QueryState query={recruiters}>
              {(list) => (
                <Table
                  className="rounded-none border-x-0 border-b-0"
                  caption="Рекрутеры"
                  rows={list}
                  rowKey={(r) => r.id}
                  columns={[
                    {
                      key: 'full_name',
                      header: 'Имя',
                      render: (r: S['Recruiter']) => (
                        <span className="flex items-center gap-2">
                          <Avatar name={r.full_name} size="sm" />
                          <span>
                            <span className="block font-semibold">{r.full_name}</span>
                            <span className="block text-[13px] text-muted">{r.position}</span>
                          </span>
                        </span>
                      ),
                    },
                    { key: 'email', header: 'Почта', hideOnMobile: true },
                    {
                      key: 'role',
                      header: '',
                      align: 'right',
                      render: (r: S['Recruiter']) => (r.is_company_admin ? <Badge tone="violet">Администратор</Badge> : null),
                    },
                  ]}
                />
              )}
            </QueryState>
          </Card>
        </div>
        <div className="flex flex-col gap-4">
          <Card>
            <QuotaMeter />
          </Card>
          <ContactRules />
        </div>
      </div>
    </>
  )
}

function CompanyView({ company: c }: { company: Company }) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-bold">{c.name}</h2>
        {c.industry && <Badge tone="violet">{c.industry}</Badge>}
        {c.verified_domain && <Badge tone="success">Домен почты подтверждён</Badge>}
      </div>
      <p className="mt-3 text-[15px] whitespace-pre-line">{c.description || 'Описание не заполнено.'}</p>
      <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
        <Item icon={<Mail aria-hidden />} label="Почта" value={c.contact_email} />
        <Item icon={<Phone aria-hidden />} label="Телефон" value={c.contact_phone} />
        <Item icon={<Globe aria-hidden />} label="Сайт" value={c.website} />
        <Item icon={<MapPin aria-hidden />} label="Город" value={c.city} />
      </dl>
    </Card>
  )
}

function Item({ icon, label, value }: { icon: ReactNode; label: string; value?: string | null }) {
  return (
    <div className="flex items-start gap-2">
      <span className="mt-0.5 text-fsp-plum [&>svg]:size-4">{icon}</span>
      <div className="min-w-0">
        <dt className="text-xs text-muted">{label}</dt>
        <dd className="truncate font-medium">{value || '—'}</dd>
      </div>
    </div>
  )
}

function CompanyForm({ company, onDone }: { company: Company; onDone: () => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [form, setForm] = useState<S['CompanyUpdate']>({
    name: company.name,
    description: company.description,
    industry: company.industry,
    website: company.website ?? '',
    city: company.city ?? '',
    contact_email: company.contact_email,
    contact_phone: company.contact_phone ?? '',
  })
  const [errors, setErrors] = useState<Record<string, string>>({})
  const save = useMutation({
    mutationFn: (body: S['CompanyUpdate']) => api.put<Company>('/companies/my', body),
    onSuccess: () => {
      toast({ tone: 'success', title: 'Профиль компании сохранён' })
      void qc.invalidateQueries({ queryKey: rk.all })
      onDone()
    },
    onError: (e) => {
      if (isApiError(e) && e.details?.fields) setErrors(e.details.fields as Record<string, string>)
      else toast({ tone: 'error', title: 'Не удалось сохранить', description: isApiError(e) ? e.message : undefined })
    },
  })
  const set = (k: keyof S['CompanyUpdate'], v: string) => setForm((f) => ({ ...f, [k]: v }))
  function submit(e: FormEvent) {
    e.preventDefault()
    const next: Record<string, string> = {}
    if (form.name.trim().length < 2) next.name = 'Название — не короче 2 символов'
    if (!/^\S+@\S+\.\S+$/.test(form.contact_email)) next.contact_email = 'Укажите почту'
    setErrors(next)
    if (!Object.keys(next).length) save.mutate(form)
  }
  return (
    <Card>
      <form onSubmit={submit} noValidate className="grid gap-4 sm:grid-cols-2">
        <Input label="Название" required value={form.name} onChange={(e) => set('name', e.target.value)} error={errors.name} />
        <Input label="Направление деятельности" value={form.industry ?? ''} onChange={(e) => set('industry', e.target.value)} />
        <Textarea label="Описание" containerClassName="sm:col-span-2" rows={4} maxLength={3000} value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} />
        <Input label="Почта для кандидатов" required type="email" value={form.contact_email} onChange={(e) => set('contact_email', e.target.value)} error={errors.contact_email} />
        <Input label="Телефон" value={form.contact_phone ?? ''} onChange={(e) => set('contact_phone', e.target.value)} />
        <Input label="Сайт" value={form.website ?? ''} onChange={(e) => set('website', e.target.value)} />
        <Input label="Город" value={form.city ?? ''} onChange={(e) => set('city', e.target.value)} />
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={onDone}>
            Отмена
          </Button>
          <Button type="submit" loading={save.isPending}>
            Сохранить
          </Button>
        </div>
      </form>
    </Card>
  )
}
