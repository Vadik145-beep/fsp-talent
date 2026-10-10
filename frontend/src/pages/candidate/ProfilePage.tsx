import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Download, Eye, FileUp, X } from 'lucide-react'
import { api, getErrorMessage, isApiError } from '@/shared/api'
import { Button, Card, CardHeader, PageHeader, ProgressBar, useToast } from '@/shared/ui'
import { invalidateCandidate, qk, useProfile, type CandidateProfile, type S } from './api'
import { ProfileForm } from './components/ProfileForm'
import { QueryView } from './components/QueryView'
import { ResumeUpload } from './components/ResumeUpload'
import { downloadProfilePdf } from './components/downloadPdf'
import { GradeConfirmedBadge, UnconfirmedGrade } from './components/GradeStatus'
import { applyParsedResume, formFromProfile, toUpdate, type ParsedConfidence, type ProfileFormState, type ResumeClaim } from './components/profileFormModel'
import { ResumeClaimNote, hasClaim, writeResumeClaim } from './components/ResumeClaim'

export default function ProfilePage() {
  const q = useProfile()
  const { toast } = useToast()
  const [pdfLoading, setPdfLoading] = useState(false)

  async function download() {
    setPdfLoading(true)
    try {
      await downloadProfilePdf()
      toast({ tone: 'success', title: 'PDF-профиль скачан' })
    } catch (err) {
      toast({ tone: 'error', title: 'Не удалось скачать PDF', description: getErrorMessage(err) })
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <>
      <PageHeader
        title="Профиль и резюме"
        description="Эти данные видны только вам. Работодатель видит обезличенную карточку — до тех пор, пока вы не примете приглашение."
        actions={
          <Button variant="secondary" leftIcon={<Download className="size-4" aria-hidden />} onClick={download} loading={pdfLoading}>
            Скачать PDF-профиль
          </Button>
        }
      />
      <QueryView query={q}>{(profile) => <ProfileEditor key={profile.id} profile={profile} />}</QueryView>
    </>
  )
}

function ProfileEditor({ profile }: { profile: CandidateProfile }) {
  const client = useQueryClient()
  const { toast } = useToast()
  const [form, setForm] = useState<ProfileFormState>(() => formFromProfile(profile))
  const [confidence, setConfidence] = useState<ParsedConfidence>({})
  const [uploadOpen, setUploadOpen] = useState(false)
  const [claim, setClaim] = useState<ResumeClaim | null>(null)

  const save = useMutation({
    mutationFn: async () => {
      const updated = await api.put<CandidateProfile>('/candidates/me/profile', toUpdate(form))
      // Специализация и грейд из резюме — только заявка (статус «не подтверждён»); подтверждённый грейд не трогаем.
      if (claim?.specialization && claim.grade && profile.grade_status !== 'confirmed') {
        await api
          .put('/candidates/me/declared-grade', { specialization: claim.specialization.value, grade: claim.grade.value })
          .catch(() => undefined)
      }
      return updated
    },
    onSuccess: (updated) => {
      client.setQueryData(qk.profile, updated)
      void invalidateCandidate(client)
      if (hasClaim(claim)) writeResumeClaim(claim)
      setConfidence({})
      toast({ tone: 'success', title: 'Профиль сохранён' })
    },
    onError: (err) => toast({ tone: 'error', title: 'Не сохранилось', description: getErrorMessage(err) }),
  })

  function onParsed(result: S['ResumeParseResponse']) {
    const applied = applyParsedResume(form, result)
    setForm(applied.form)
    setConfidence(applied.confidence)
    setClaim(hasClaim(applied.claim) ? applied.claim : null)
    setUploadOpen(false)
    toast({
      tone: 'info',
      title: 'Поля заполнены из резюме',
      description: ['Проверьте подсвеченные поля и сохраните профиль.', ...(result.warnings ?? [])].join(' '),
    })
  }

  const serverErrors =
    isApiError(save.error) && save.error.code === 'validation_error'
      ? (save.error.details.fields as Record<string, string> | undefined)
      : undefined

  return (
    <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div className="grid gap-5">
        {uploadOpen ? (
          <Card>
            <CardHeader
              title="Загрузить PDF-резюме"
              description="Распознаем ФИО, контакты, стек, стаж и роли — и подставим в форму. Вы проверите и сохраните."
              actions={
                <Button variant="ghost" size="sm" aria-label="Закрыть загрузку" onClick={() => setUploadOpen(false)}>
                  <X className="size-4" aria-hidden />
                </Button>
              }
            />
            <ResumeUpload onParsed={onParsed} />
          </Card>
        ) : null}
        {claim && <ResumeClaimNote claim={claim} onboarding={false} />}
        <ProfileForm

          value={form}
          onChange={setForm}
          onSubmit={() => save.mutate()}
          submitting={save.isPending}
          confidence={confidence}
          serverErrors={serverErrors}
          email={profile.email}
        />
      </div>

      <aside className="grid gap-4 lg:sticky lg:top-20">
        <Card>
          <p className="font-semibold text-ink">Категория и грейд</p>
          {profile.grade_status === 'confirmed' && profile.category_label ? (
            <div className="mt-1 grid gap-1.5">
              <p className="text-lg font-bold text-fsp-night">{profile.category_label}</p>
              <GradeConfirmedBadge at={profile.grade_confirmed_at} className="justify-self-start" />
            </div>
          ) : profile.grade_status === 'unconfirmed' && profile.declared_grade ? (
            <UnconfirmedGrade className="mt-1" compact specialization={profile.declared_specialization} grade={profile.declared_grade} />
          ) : (
            <p className="mt-1 text-[13px] text-muted">
              Грейда пока нет.{' '}
              <Link to="/candidate/onboarding" className="font-semibold text-fsp-plum hover:underline">
                Пройти опрос и тест
              </Link>
            </p>
          )}
        </Card>
        <Card>
          <ProgressBar label="Профиль заполнен" value={profile.profile_completeness} tone={profile.profile_completeness >= 80 ? 'success' : 'primary'} />
          <p className="mt-2 text-[13px] text-muted">Полный профиль выше в подборке работодателя.</p>
        </Card>
        {!uploadOpen && (
          <Card>
            <p className="font-semibold text-ink">Есть резюме в PDF?</p>
            <p className="mt-1 text-[13px] text-muted">Загрузите — поля заполнятся сами.</p>
            <Button className="mt-3" variant="secondary" size="sm" leftIcon={<FileUp className="size-4" aria-hidden />} onClick={() => setUploadOpen(true)}>
              Загрузить PDF
            </Button>
          </Card>
        )}
        <Card>
          <p className="font-semibold text-ink">Как вас видит работодатель</p>
          <p className="mt-1 text-[13px] text-muted">Обезличенная карточка: без имени и контактов.</p>
          <Link to="/candidate/settings" className="mt-3 inline-flex items-center gap-1.5 text-sm font-semibold text-fsp-plum hover:underline">
            <Eye className="size-4" aria-hidden /> Посмотреть и настроить
          </Link>
        </Card>
      </aside>
    </div>
  )
}
