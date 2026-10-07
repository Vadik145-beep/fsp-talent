import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, getErrorMessage } from '@/shared/api'
import { Button, Modal, useToast } from '@/shared/ui'
import { refreshRecruiter, rk, upsertInList, type Invitation, type InvitationDetail } from '../api'

/** Подтверждение отзыва приглашения. */
export function WithdrawDialog({ id, onClose }: { id: number | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const withdraw = useMutation({
    mutationFn: (invId: number) => api.post<Invitation>(`/invitations/${invId}/withdraw`),
    onSuccess: (inv) => {
      toast({ tone: 'success', title: 'Приглашение отозвано', description: 'Место в квоте освободилось.' })
      // Статус из ответа — в список и в открытую карточку (с записью в журнале).
      upsertInList(qc, rk.invitations, inv)
      qc.setQueryData<InvitationDetail>(rk.invitation(inv.id), (old) =>
        old
          ? {
              ...old,
              ...inv,
              events: [
                ...(old.events ?? []),
                { id: -Date.now(), invitation_id: inv.id, type: 'withdrawn', at: inv.withdrawn_at ?? new Date().toISOString(), actor_role: 'recruiter' },
              ],
            }
          : old,
      )
      void refreshRecruiter(qc, rk.invitations)
      onClose()
    },
    onError: (e) => {
      toast({ tone: 'error', title: 'Не удалось отозвать', description: getErrorMessage(e) })
      void qc.invalidateQueries({ queryKey: rk.invitations })
      onClose()
    },
  })
  return (
    <Modal
      open={id !== null}
      onClose={onClose}
      size="sm"
      title="Отозвать приглашение?"
      description="Кандидат увидит, что приглашение отозвано. Место в квоте освободится."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button variant="danger" loading={withdraw.isPending} onClick={() => id !== null && withdraw.mutate(id)}>
            Отозвать
          </Button>
        </>
      }
    />
  )
}
