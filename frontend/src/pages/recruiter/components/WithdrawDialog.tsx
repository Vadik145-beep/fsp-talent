import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api, getErrorMessage } from '@/shared/api'
import { Button, Modal, useToast } from '@/shared/ui'
import { rk, type Invitation } from '../api'

/** Подтверждение отзыва приглашения. */
export function WithdrawDialog({ id, onClose }: { id: number | null; onClose: () => void }) {
  const qc = useQueryClient()
  const { toast } = useToast()
  const withdraw = useMutation({
    mutationFn: (invId: number) => api.post<Invitation>(`/invitations/${invId}/withdraw`),
    onSuccess: () => {
      toast({ tone: 'success', title: 'Приглашение отозвано', description: 'Место в квоте освободилось.' })
      void qc.invalidateQueries({ queryKey: rk.all })
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
