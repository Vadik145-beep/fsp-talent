import { useState } from 'react'
import { ArrowDown, ArrowUp, Check, GripVertical } from 'lucide-react'
import { Input } from '@/shared/ui'
import { cn } from '@/shared/lib/cn'
import type { AnswerPayload, ItemView } from '../api'
import { CodeBlock } from './CodeBlock'
import { codeOutputHint, numericHint } from './testAnswer'

export type AnswerDraft = AnswerPayload & { raw?: string }

export interface ItemAnswerProps {
  item: ItemView
  value: AnswerDraft
  onChange: (value: AnswerDraft) => void
  disabled?: boolean
}

/** Поле ответа под формат задачи теста. Правильный ответ кандидату не показывается. */
export function ItemAnswer({ item, value, onChange, disabled }: ItemAnswerProps) {
  switch (item.format) {
    case 'single_choice':
    case 'multiple_choice':
      return <ChoiceAnswer item={item} value={value} onChange={onChange} disabled={disabled} />
    case 'numeric':
      return (
        <Input
          label="Ваш ответ"
          inputMode="decimal"
          autoComplete="off"
          placeholder="Например, 42"
          value={value.raw ?? ''}
          onChange={(e) => onChange({ raw: e.target.value })}
          disabled={disabled}
          hint={numericHint(item.prompt)}
          rightSlot={item.unit ? <span className="pr-1 text-sm text-muted">{item.unit}</span> : undefined}
          className={item.unit ? 'pr-24' : undefined}
          containerClassName="max-w-sm"
          data-autofocus
        />
      )
    case 'short_text':
      return (
        <Input
          label="Ваш ответ"
          autoComplete="off"
          value={value.text ?? ''}
          onChange={(e) => onChange({ text: e.target.value })}
          disabled={disabled}
          containerClassName="max-w-md"
        />
      )
    case 'code_output':
      return (
        <div className="space-y-4">
          {item.code && <CodeBlock code={item.code} />}
          <Input
            label="Ваш ответ"
            autoComplete="off"
            spellCheck={false}
            value={value.text ?? ''}
            onChange={(e) => onChange({ text: e.target.value })}
            disabled={disabled}
            className="font-mono"
            containerClassName="max-w-md"
            hint={codeOutputHint(item.prompt)}
          />
        </div>
      )
    case 'find_error_line':
      return (
        <div className="space-y-2">
          <p className="text-sm text-muted">Нажмите на строку, в которой ошибка.</p>
          {item.code && (
            <CodeBlock
              code={item.code}
              selectable
              selectedLine={value.line ?? null}
              onSelectLine={(line) => !disabled && onChange({ line })}
              ariaLabel="Код: выберите строку с ошибкой"
            />
          )}
          <p className="text-sm font-medium text-ink" aria-live="polite">
            {value.line ? `Выбрана строка ${value.line}` : 'Строка не выбрана'}
          </p>
        </div>
      )
    case 'ordering':
      return <OrderingAnswer item={item} value={value} onChange={onChange} disabled={disabled} />
    default:
      return <p className="text-muted">Формат задачи не поддерживается.</p>
  }
}

function ChoiceAnswer({ item, value, onChange, disabled }: ItemAnswerProps) {
  const multiple = item.format === 'multiple_choice'
  const selected = new Set(value.choice_ids ?? [])
  function toggle(id: string) {
    if (disabled) return
    if (!multiple) return onChange({ choice_ids: [id] })
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange({ choice_ids: [...next] })
  }
  return (
    <fieldset>
      <legend className="mb-2 text-sm text-muted">{multiple ? 'Выберите все верные варианты' : 'Выберите один вариант'}</legend>
      <div className="grid gap-2">
        {(item.options ?? []).map((o, i) => {
          const checked = selected.has(o.id)
          return (
            <label
              key={o.id}
              className={cn(
                'flex cursor-pointer items-center gap-3 rounded-lg border bg-surface px-4 py-3 transition-colors',
                checked ? 'border-primary bg-primary-soft' : 'border-line hover:border-fsp-lavender',
                disabled && 'cursor-not-allowed opacity-70',
              )}
            >
              <input
                type={multiple ? 'checkbox' : 'radio'}
                name={item.instance_id}
                checked={checked}
                onChange={() => toggle(o.id)}
                disabled={disabled}
                className="sr-only"
              />
              <span
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center border-2 text-xs font-bold',
                  multiple ? 'rounded-sm' : 'rounded-full',
                  checked ? 'border-primary bg-primary text-white' : 'border-line-strong text-muted',
                )}
                aria-hidden
              >
                {checked ? <Check className="size-4" /> : String.fromCharCode(65 + i)}
              </span>
              <span className="text-[15px] text-ink">{o.text}</span>
            </label>
          )
        })}
      </div>
    </fieldset>
  )
}

function OrderingAnswer({ item, value, onChange, disabled }: ItemAnswerProps) {
  const steps = item.steps ?? []
  const order = value.order ?? steps.map((s) => s.id)
  const byId = new Map(steps.map((s) => [s.id, s]))
  const [dragIndex, setDragIndex] = useState<number | null>(null)
  const [overIndex, setOverIndex] = useState<number | null>(null)

  function move(from: number, to: number) {
    if (disabled || to < 0 || to >= order.length || from === to) return
    const next = [...order]
    const [x] = next.splice(from, 1)
    next.splice(to, 0, x)
    onChange({ order: next })
  }

  return (
    <div>
      <p className="mb-2 text-sm text-muted">Перетащите шаги мышью или двигайте стрелками.</p>
      <ol className="grid gap-2" aria-label="Шаги по порядку">
        {order.map((id, i) => {
          const step = byId.get(id)
          if (!step) return null
          return (
            <li
              key={id}
              draggable={!disabled}
              onDragStart={(e) => {
                setDragIndex(i)
                e.dataTransfer.effectAllowed = 'move'
                e.dataTransfer.setData('text/plain', id)
              }}
              onDragOver={(e) => {
                e.preventDefault()
                setOverIndex(i)
              }}
              onDragLeave={() => setOverIndex((cur) => (cur === i ? null : cur))}
              onDrop={(e) => {
                e.preventDefault()
                if (dragIndex !== null) move(dragIndex, i)
                setDragIndex(null)
                setOverIndex(null)
              }}
              onDragEnd={() => {
                setDragIndex(null)
                setOverIndex(null)
              }}
              className={cn(
                'flex items-center gap-3 rounded-lg border bg-surface py-2 pr-2 pl-3 transition-[border-color,box-shadow,opacity]',
                overIndex === i && dragIndex !== null && dragIndex !== i ? 'border-primary shadow-[var(--shadow-pop)]' : 'border-line',
                dragIndex === i && 'opacity-50',
                !disabled && 'cursor-grab active:cursor-grabbing',
              )}
            >
              <GripVertical className="size-4 shrink-0 text-subtle" aria-hidden />
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-violet-soft text-sm font-bold text-fsp-plum">
                {i + 1}
              </span>
              <span className="min-w-0 flex-1 text-[15px] text-ink">{step.text}</span>
              <span className="flex shrink-0 gap-1">
                <button
                  type="button"
                  onClick={() => move(i, i - 1)}
                  disabled={disabled || i === 0}
                  aria-label={`Поднять шаг «${step.text}»`}
                  className="rounded-sm p-1.5 text-fsp-plum hover:bg-violet-soft disabled:opacity-30"
                >
                  <ArrowUp className="size-4" aria-hidden />
                </button>
                <button
                  type="button"
                  onClick={() => move(i, i + 1)}
                  disabled={disabled || i === order.length - 1}
                  aria-label={`Опустить шаг «${step.text}»`}
                  className="rounded-sm p-1.5 text-fsp-plum hover:bg-violet-soft disabled:opacity-30"
                >
                  <ArrowDown className="size-4" aria-hidden />
                </button>
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
