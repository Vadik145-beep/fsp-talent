import { useRef, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/shared/lib/cn'

/**
 * Блок кода с номерами строк и простой подсветкой синтаксиса (без зависимостей).
 * selectable — строки становятся кнопками (формат «найди строку с ошибкой»), стрелки ↑/↓ двигают выбор.
 * Кандидат на перенос в shared/ui.
 */
export interface CodeBlockProps {
  code: string
  selectable?: boolean
  selectedLine?: number | null
  onSelectLine?: (line: number) => void
  className?: string
  ariaLabel?: string
}

const KEYWORDS = new Set([
  'def', 'return', 'for', 'in', 'range', 'if', 'elif', 'else', 'while', 'class', 'import', 'from', 'as', 'with',
  'try', 'except', 'finally', 'raise', 'lambda', 'yield', 'pass', 'break', 'continue', 'and', 'or', 'not', 'is',
  'None', 'True', 'False', 'print', 'len', 'async', 'await', 'const', 'let', 'var', 'function', 'new', 'this',
  'true', 'false', 'null', 'undefined', 'typeof', 'export', 'interface', 'type', 'fun', 'val', 'when', 'println',
  'func', 'package', 'go', 'select', 'from', 'where', 'join', 'SELECT', 'FROM', 'WHERE', 'JOIN', 'GROUP', 'BY',
  'ORDER', 'INSERT', 'UPDATE', 'DELETE', 'console', 'log', 'map', 'filter', 'reduce', 'self', 'static', 'public',
])

const TOKEN_RE =
  /(#[^\n]*|\/\/[^\n]*)|("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)/g

/** Разбить строку кода на подсвеченные фрагменты. */
function highlightLine(line: string): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let m: RegExpExecArray | null
  TOKEN_RE.lastIndex = 0
  while ((m = TOKEN_RE.exec(line))) {
    if (m.index > last) out.push(line.slice(last, m.index))
    const [text, comment, str, num, word] = m
    const key = `${m.index}-${text}`
    if (comment) out.push(<span key={key} className="text-fsp-silver italic">{text}</span>)
    else if (str) out.push(<span key={key} className="text-success-soft">{text}</span>)
    else if (num) out.push(<span key={key} className="text-warning-soft">{text}</span>)
    else if (word && KEYWORDS.has(word)) out.push(<span key={key} className="text-fsp-blue-light font-semibold">{text}</span>)
    else out.push(text)
    last = m.index + text.length
  }
  if (last < line.length) out.push(line.slice(last))
  return out
}

export function CodeBlock({ code, selectable, selectedLine, onSelectLine, className, ariaLabel }: CodeBlockProps) {
  const lines = code.replace(/\n$/, '').split('\n')
  const refs = useRef<Array<HTMLButtonElement | null>>([])
  const gutter = String(lines.length).length

  function onKeyDown(e: KeyboardEvent<HTMLButtonElement>, index: number) {
    let next = -1
    if (e.key === 'ArrowDown') next = Math.min(lines.length - 1, index + 1)
    else if (e.key === 'ArrowUp') next = Math.max(0, index - 1)
    if (next < 0) return
    e.preventDefault()
    refs.current[next]?.focus()
    onSelectLine?.(next + 1)
  }

  return (
    <div
      className={cn('overflow-x-auto rounded-lg bg-fsp-black py-3 font-mono text-[14px] leading-6 text-fsp-gray', className)}
      role={selectable ? 'group' : undefined}
      aria-label={ariaLabel ?? (selectable ? 'Код: выберите строку' : 'Код')}
    >
      <div className="min-w-max">
        {lines.map((line, i) => {
          const n = i + 1
          const content = (
            <>
              <span
                className={cn('inline-block shrink-0 pr-4 pl-4 text-right text-fsp-silver select-none', selectable && 'group-hover:text-white')}
                style={{ width: `${gutter + 3}ch` }}
                aria-hidden
              >
                {n}
              </span>
              <span className="pr-6 whitespace-pre">{line ? highlightLine(line) : ' '}</span>
            </>
          )
          if (!selectable) {
            return (
              <div key={i} className="flex">
                {content}
              </div>
            )
          }
          const selected = selectedLine === n
          return (
            <button
              key={i}
              ref={(el) => {
                refs.current[i] = el
              }}
              type="button"
              aria-pressed={selected}
              aria-label={`Строка ${n}: ${line.trim() || 'пустая'}`}
              tabIndex={selected || (selectedLine == null && i === 0) ? 0 : -1}
              onClick={() => onSelectLine?.(n)}
              onKeyDown={(e) => onKeyDown(e, i)}
              className={cn(
                'group flex w-full items-center border-l-4 text-left transition-colors focus-visible:outline-none',
                selected
                  ? 'border-fsp-pink bg-fsp-pink/25'
                  : 'border-transparent hover:bg-white/8 focus-visible:bg-white/10',
              )}
            >
              {content}
            </button>
          )
        })}
      </div>
    </div>
  )
}
