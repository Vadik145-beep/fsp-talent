import { useState } from 'react'
import { useNavigate } from 'react-router'
import { ShieldCheck } from 'lucide-react'
import { getErrorMessage } from '@/shared/api'
import { Button, useToast, type ButtonProps } from '@/shared/ui'
import { startFspAuth } from '@/pages/public/fspAuth'

/** Кнопка «Привязать ФСП ID»: уводит на Keycloak (в прототипе — экран выбора участника). */
export function FspLinkButton({
  returnTo = '/candidate/fsp',
  children = 'Привязать ФСП ID',
  ...rest
}: Omit<ButtonProps, 'onClick'> & { returnTo?: string }) {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [loading, setLoading] = useState(false)
  return (
    <Button
      leftIcon={<ShieldCheck className="size-4" aria-hidden />}
      loading={loading}
      onClick={async () => {
        setLoading(true)
        try {
          await startFspAuth('link', navigate, returnTo)
        } catch (err) {
          toast({ tone: 'error', title: 'ФСП ID недоступен', description: getErrorMessage(err) })
          setLoading(false)
        }
      }}
      {...rest}
    >
      {children}
    </Button>
  )
}
