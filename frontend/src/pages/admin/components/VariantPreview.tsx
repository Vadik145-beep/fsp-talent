import type { ReactNode } from 'react'
import { Check, Clock } from 'lucide-react'
import { cn } from '@/shared/lib/cn'
import type { ItemVariantPreview } from '../api'

const SPLIT = /([\s,.;:!?()«»"'`{}[\]=<>+*/|-]+)/

function tokens(text: string): string[] {
  return text.split(SPLIT).filter((t) => t !== '')
}

const isWord = (t: string) => !SPLIT.test(t) || /^[\p{L}\d_]+$/u.test(t)

/** Слова, которые встречаются не во всех вариантах, — их подсвечиваем. */
function varyingWords(texts: string[]): Set<string> {
  const sets = texts.map((t) => new Set(tokens(t)))
  const out = new Set<string>()
  for (const s of sets) for (const t of s) if (isWord(t) && !sets.every((x) => x.has(t))) out.add(t)
  return out
}

function Highlighted({ text, varying }: { text: string; varying: Set<string> }) {
  return (
    <>
      {tokens(text).map((t, i) =>
        varying.has(t) ? (
          <mark key={i} className="rounded-xs bg-fsp-blush px-0.5 text-ink">
            {t}
          </mark>
        ) : (
          <span key={i}>{t}</span>
        ),
      )}
    </>
  )
}

function answerText(v: ItemVariantPreview): ReactNode {
  const a = v.correct_answer
  if (a.value != null) return `${String(a.value).replace('.', ',')}${v.unit ? ` ${v.unit}` : ''}`
  if (a.line != null) return `строка ${a.line}`
  if (a.text) return a.text
  if (a.order?.length && v.steps) return a.order.map((id) => v.steps!.findIndex((s) => s.id === id) + 1).join(' → ')
  if (a.choice_ids?.length) return a.choice_ids.map((id) => id.toUpperCase()).join(', ')
  return '—'
}

/** Три варианта одного шаблона рядом: что отличается у разных кандидатов. */
export function VariantPreview({ variants }: { variants: ItemVariantPreview[] }) {
  const promptVarying = varyingWords(variants.map((v) => v.prompt))
  const codeVarying = varyingWords(variants.map((v) => v.code ?? ''))
  const optionVarying = varyingWords(variants.map((v) => (v.options ?? v.steps ?? []).map((o) => o.text).join(' ')))

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {variants.map((v, idx) => (
        <article key={v.instance_id} className="flex min-w-0 flex-col rounded-lg border border-line bg-surface p-4 shadow-[var(--shadow-card)]">
          <header className="mb-3 flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold text-fsp-plum">Кандидат {idx + 1}</h3>
            <span className="font-mono text-xs text-muted">seed {v.seed}</span>
          </header>
          <p className="text-[15px] leading-relaxed text-ink">
            <Highlighted text={v.prompt} varying={promptVarying} />
          </p>
          {v.code && (
            <pre className="mt-3 overflow-x-auto rounded-md bg-fsp-ink p-3 font-mono text-[12.5px] leading-relaxed text-[#f3f0fa]">
              {v.code.split('\n').map((line, i) => (
                <div key={i} className="flex gap-3">
                  <span className="w-5 shrink-0 text-right text-[#9b95ad] select-none">{i + 1}</span>
                  <span className="[&_mark]:bg-[#7a2b4f] [&_mark]:text-white">
                    <Highlighted text={line} varying={codeVarying} />
                  </span>
                </div>
              ))}
            </pre>
          )}
          {v.options && (
            <ul className="mt-3 flex flex-col gap-1.5">
              {v.options.map((o) => {
                const right = v.correct_answer.choice_ids?.includes(o.id)
                return (
                  <li
                    key={o.id}
                    className={cn(
                      'flex items-start gap-2 rounded-md border px-2.5 py-1.5 text-sm',
                      right ? 'border-success bg-success-soft' : 'border-line',
                    )}
                  >
                    <span className="font-mono font-semibold text-muted uppercase">{o.id}</span>
                    <span className="min-w-0 flex-1 break-words">
                      <Highlighted text={o.text} varying={optionVarying} />
                    </span>
                    {right && <Check className="size-4 shrink-0 text-success" aria-label="верный ответ" />}
                  </li>
                )
              })}
            </ul>
          )}
          {v.steps && (
            <ol className="mt-3 flex flex-col gap-1.5">
              {v.steps.map((s, i) => (
                <li key={s.id} className="flex gap-2 rounded-md border border-line px-2.5 py-1.5 text-sm">
                  <span className="font-semibold text-muted">{i + 1}.</span>
                  <span className="min-w-0 break-words">
                    <Highlighted text={s.text} varying={optionVarying} />
                  </span>
                </li>
              ))}
            </ol>
          )}
          <footer className="mt-auto flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3 text-[13px]">
            <span>
              <span className="text-muted">Ответ: </span>
              <b className="text-success">{answerText(v)}</b>
            </span>
            <span className="inline-flex items-center gap-1 text-muted">
              <Clock className="size-3.5" aria-hidden />
              {v.time_limit_sec} с
            </span>
          </footer>
        </article>
      ))}
    </div>
  )
}
