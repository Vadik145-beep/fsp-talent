import { useRef, useState, type DragEvent } from 'react'
import { useMutation } from '@tanstack/react-query'
import { FileUp, FileText } from 'lucide-react'
import { api, getErrorMessage } from '@/shared/api'
import { Button, Spinner } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import type { S } from '../api'

const MAX_BYTES = 5 * 1024 * 1024

/** Загрузка PDF-резюме: перетаскивание или выбор файла → разбор на сервере → предзаполнение формы. */
export function ResumeUpload({ onParsed, className }: { onParsed: (result: S['ResumeParseResult']) => void; className?: string }) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragOver, setDragOver] = useState(false)
  const [localError, setLocalError] = useState<string | null>(null)

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return api.post<S['ResumeParseResult']>('/candidates/me/resume', form)
    },
    onSuccess: onParsed,
  })

  function pick(file: File | undefined) {
    if (!file) return
    setLocalError(null)
    if (!/\.pdf$/i.test(file.name) && file.type !== 'application/pdf') {
      setLocalError('Нужен файл PDF')
      return
    }
    if (file.size > MAX_BYTES) {
      setLocalError('Файл больше 5 МБ')
      return
    }
    upload.mutate(file)
  }

  function onDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    pick(e.dataTransfer.files[0])
  }

  const error = localError ?? (upload.isError ? getErrorMessage(upload.error) : null)

  return (
    <div className={className}>
      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors',
          dragOver ? 'border-primary bg-primary-soft' : 'border-line-strong bg-surface-muted',
        )}
      >
        {upload.isPending ? (
          <>
            <Spinner size={28} className="text-fsp-plum" />
            <p className="font-semibold text-ink">Распознаём резюме…</p>
            <p className="text-sm text-muted">Ищем ФИО, контакты, стек, стаж и роли</p>
          </>
        ) : (
          <>
            <span className="flex size-12 items-center justify-center rounded-full bg-violet-soft text-fsp-plum">
              <FileUp className="size-6" aria-hidden />
            </span>
            <div>
              <p className="font-semibold text-ink">Перетащите PDF сюда</p>
              <p className="text-sm text-muted">или выберите файл · до 5 МБ</p>
            </div>
            <Button variant="secondary" leftIcon={<FileText className="size-4" aria-hidden />} onClick={() => inputRef.current?.click()}>
              Выбрать PDF
            </Button>
          </>
        )}
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          aria-label="Файл резюме в формате PDF"
          onChange={(e) => {
            pick(e.target.files?.[0])
            e.target.value = ''
          }}
        />
      </div>
      {error && (
        <p className="mt-2 text-sm text-danger" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
