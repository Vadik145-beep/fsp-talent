import { useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Archive, Pencil, RotateCcw } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { Button, Modal, useToast } from '@/shared/ui'
import { refreshRecruiter, rk, upsertInList, type Need, type S } from '../api'

const secondaryLink =
  'inline-flex h-10 items-center gap-2 rounded-md border border-line-strong bg-surface px-4 text-sm font-semibold text-fsp-plum hover:bg-violet-soft'

/** Тело PUT: те же поля, что при создании, плюс статус. */
function updateBody(n: Need, status: S['NeedStatus']): S['NeedUpdate'] {
  return {
    title: n.title,
    raw_text: n.raw_text ?? null,
    specialization: n.specialization,
    grade: n.grade,
    skills_required: n.skills_required ?? [],
    skills_desired: n.skills_desired ?? [],
    team_description: n.team_description ?? '',
    work_format: n.work_format,
    city: n.city ?? null,
    salary_from: n.salary_from,
    salary_to: n.salary_to,
    status,
  }
}

/** «Изменить» и «Закрыть потребность» / «Вернуть в работу» в шапке подборки. */
export function NeedActions({ need }: { need: Need }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const [confirming, setConfirming] = useState(false)
  const closed = need.status === 'closed'
  const setStatus = useMutation({
    mutationFn: (status: S['NeedStatus']) => api.put<Need>(`/matching/needs/${need.id}`, updateBody(need, status)),
    onSuccess: (saved) => {
      qc.setQueryData(rk.need(saved.id), saved)
      upsertInList(qc, rk.needs, saved)
      void refreshRecruiter(qc, rk.need(saved.id), rk.needs)
      setConfirming(false)
      toast(
        saved.status === 'closed'
          ? { tone: 'success', title: 'Поиск закрыт', description: 'Он во вкладке «Закрытые». Отправленные приглашения остаются в силе.' }
          : { tone: 'success', title: 'Поиск снова в работе' },
      )
    },
    onError: (e) => toast({ tone: 'error', title: 'Не удалось сменить статус', description: getErrorMessage(e) }),
  })
  return (
    <>
      <Link to={`/recruiter/needs/${need.id}/edit`} className={secondaryLink}>
        <Pencil className="size-4" aria-hidden />
        Изменить
      </Link>
      {closed ? (
        <Button variant="secondary" loading={setStatus.isPending} onClick={() => setStatus.mutate('active')} leftIcon={<RotateCcw className="size-4" aria-hidden />}>
          Вернуть в работу
        </Button>
      ) : (
        <Button variant="secondary" onClick={() => setConfirming(true)} leftIcon={<Archive className="size-4" aria-hidden />}>
          Закрыть поиск
        </Button>
      )}
      <Modal
        open={confirming}
        onClose={() => setConfirming(false)}
        size="sm"
        title="Закрыть поиск?"
        description={`«${need.title}»`}
        footer={
          <>
            <Button variant="secondary" onClick={() => setConfirming(false)}>
              Отмена
            </Button>
            <Button loading={setStatus.isPending} onClick={() => setStatus.mutate('closed')}>
              Закрыть поиск
            </Button>
          </>
        }
      >
        <p className="text-[15px] text-ink">
          Поиск уйдёт во вкладку «Закрытые» и пропадёт с главной. Отправленные по нему приглашения останутся в силе. Вернуть в работу
          можно в любой момент.
        </p>
      </Modal>
    </>
  )
}
