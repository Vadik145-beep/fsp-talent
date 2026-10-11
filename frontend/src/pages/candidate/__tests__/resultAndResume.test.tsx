import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'
import { renderApp } from '@/test/renderApp'
import type { S, TestResult } from '../api'
import { applyParsedResume, formFromProfile, normalizeUrl, toUpdate, validateProfile } from '../components/profileFormModel'
import { setupMockServer } from './mswTestServer'

const server = setupMockServer()
const T = { timeout: 8000 }

/** Ответ бэкенда для первого теста на Middle с θ выше порога Senior (решение suggest_higher). */
const SUGGEST_HIGHER: TestResult = {
  session_id: 901,
  specialization: 'backend',
  target_grade: 'middle',
  result_grade: 'middle',
  category: 'backend:middle',
  category_label: 'Backend · Middle',
  theta: 1.62,
  se: 0.29,
  ci_low: 1.14,
  ci_high: 2.1,
  passed: true,
  items_answered: 12,
  finished_at: '2026-10-07T12:00:00+03:00',
  topic_scores: [],
  strong_topics: [],
  weak_topics: [],
  recommendation: {
    action: 'offer_higher',
    message: 'Грейд Middle подтверждён, причём уверенно выше порога Senior: можно пройти тест на грейд Senior.',
    available_at: null,
    target_grade: 'senior',
  },
  outcome: 'suggest_higher',
  measured_grade: null,
  can_accept_measured: false,
  measured_accepted: false,
}

/** Новичок не сдал Junior: тест показал уровень «Стажёр» — категорию можно взять сразу. */
const MEASURED: TestResult = {
  ...SUGGEST_HIGHER,
  session_id: 903,
  specialization: 'frontend',
  target_grade: 'junior',
  result_grade: 'intern',
  category: 'frontend:intern',
  category_label: 'Frontend · Стажёр',
  theta: -1.8,
  ci_low: -2.3,
  ci_high: -1.3,
  passed: false,
  recommendation: {
    action: 'offer_lower',
    message: 'Результат ниже порога грейда Junior. Можно пройти тест на грейд «Стажёр».',
    available_at: null,
    target_grade: 'intern',
  },
  outcome: 'suggest_lower',
  measured_grade: 'intern',
  can_accept_measured: true,
}

describe('результат теста: присвоенная категория и совет отдельно', () => {
  it('suggest_higher: категория Middle, уровень выше — отдельной строкой, Senior как категории нет', async () => {
    server.use(http.get('*/api/testing/sessions/901/result', () => HttpResponse.json(SUGGEST_HIGHER)))
    renderApp('/candidate/test/901/result', { role: 'candidate' })
    expect(await screen.findByText('Backend · Middle', {}, T)).toBeInTheDocument()
    expect(screen.getByText('Ваша категория')).toBeInTheDocument()
    expect(screen.getByText('Грейд Middle подтверждён')).toBeInTheDocument()
    expect(screen.getByText('Ваш уровень выше Middle — можно пройти тест на грейд «Senior»')).toBeInTheDocument()
    expect(screen.queryByText('Backend · Senior')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Пройти тест на грейд «Senior»' })).toBeInTheDocument()
  }, 20_000)

  it('несданный первичный тест: кнопка «Получить категорию» присваивает категорию по уровню', async () => {
    let accepted = false
    const done: TestResult = {
      ...MEASURED,
      can_accept_measured: false,
      measured_accepted: true,
      recommendation: { action: 'retry_later', message: 'Категория присвоена.', available_at: null, target_grade: null },
    }
    server.use(
      http.get('*/api/testing/sessions/903/result', () => HttpResponse.json(accepted ? done : MEASURED)),
      http.post('*/api/testing/sessions/903/accept-measured', () => {
        accepted = true
        return HttpResponse.json(done)
      }),
    )
    const user = userEvent.setup()
    renderApp('/candidate/test/903/result', { role: 'candidate' })
    expect(
      await screen.findByText('Грейд Junior не подтверждён. Тест показал уровень «Стажёр» — получить категорию Frontend · Стажёр?', {}, T),
    ).toBeInTheDocument()
    // тест на грейд ниже — второй вариант
    expect(screen.getByRole('button', { name: 'Пройти тест на грейд «Стажёр»' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Получить категорию Frontend · Стажёр' }))
    expect(await screen.findByTestId('measured-accepted', {}, T)).toHaveTextContent('Категория по результату теста')
    expect(screen.getByText('Ваша категория')).toBeInTheDocument()
    expect(screen.queryByTestId('measured-offer')).not.toBeInTheDocument()
  }, 20_000)
})

/** Задача «один вариант» с кодом в условии: код виден над вариантами (раньше рисовался только у «что выведет»). */
const SESSION_WITH_CODE: S['TestSessionState'] = {
  session: {
    id: 902,
    candidate_id: 1,
    specialization: 'backend',
    target_grade: 'middle',
    kind: 'placement',
    status: 'in_progress',
    started_at: '2026-10-07T12:00:00+03:00',
    items_answered: 0,
    max_items: 20,
  },
  current_item: {
    instance_id: 'it-1-s1',
    format: 'single_choice',
    topic: 'backend.python',
    topic_label: 'Python',
    prompt: 'Что вернёт функция для пустого списка?',
    code: 'def first(items):\n    return items[0] if items else None',
    code_language: 'python',
    options: [
      { id: 'a', text: 'None' },
      { id: 'b', text: 'IndexError' },
    ],
    time_limit_sec: 120,
  },
  item_number: 1,
  time_left_sec: 120,
}

describe('экран теста', () => {
  it('код к задаче виден и у формата «один вариант»', async () => {
    server.use(http.get('*/api/testing/sessions/902', () => HttpResponse.json(SESSION_WITH_CODE)))
    renderApp('/candidate/test/902', { role: 'candidate' })
    expect(await screen.findByText('Что вернёт функция для пустого списка?', {}, T)).toBeInTheDocument()
    // код подсвечен по токенам — проверяем текст блока целиком
    expect(document.body.textContent).toContain('return items[0] if items else None')
    expect(screen.getByText('IndexError')).toBeInTheDocument()
  }, 20_000)

  it('адрес с неверным id — «Тест не найден», а не пустая страница', async () => {
    renderApp('/candidate/test/abc', { role: 'candidate' })
    expect(await screen.findByText('Тест не найден', {}, T)).toBeInTheDocument()
  }, 20_000)
})

const parsed = (fields: Record<string, { value: unknown; confidence: number }>) =>
  ({ resume_id: 1, filename: 'r.pdf', parser: 'rules', fields, unmatched_skills: [], warnings: [] }) as unknown as S['ResumeParseResponse']

describe('подстановка разобранного PDF в форму профиля', () => {
  const base = formFromProfile({ full_name: 'Денис Морозов', experience_years: 4 })

  it('формат работы из PDF попадает в форму, форма валидна', () => {
    const { form, confidence } = applyParsedResume(
      base,
      parsed({
        work_formats: { value: ['hybrid'], confidence: 0.8 },
        links: { value: ['https://github.com/denis-morozov-dev'], confidence: 0.95 },
      }),
    )
    expect(form.work_formats).toEqual(['hybrid'])
    expect(confidence.work_formats).toBe(0.8)
    expect(validateProfile(form)).toEqual({})
    expect(toUpdate(form).work_formats).toEqual(['hybrid'])
  })

  it('специализация и грейд из PDF не теряются: возвращаются как заявка, форму не меняют', () => {
    const { claim, form } = applyParsedResume(
      base,
      parsed({ specialization: { value: 'frontend', confidence: 0.92 }, grade: { value: 'Senior', confidence: 0.85 } }),
    )
    expect(claim).toEqual({ specialization: { value: 'frontend', confidence: 0.92 }, grade: { value: 'senior', confidence: 0.85 } })
    expect(form).toEqual(base)
    expect(applyParsedResume(base, parsed({ grade: { value: 'guru', confidence: 0.9 } })).claim).toEqual({})
    expect(applyParsedResume(base, parsed({ grade: { value: null, confidence: 0 } })).claim).toEqual({})
  })

  it('формат одной строкой и мусорные коды тоже разбираются', () => {
    expect(applyParsedResume(base, parsed({ work_formats: { value: 'Remote', confidence: 0.8 } })).form.work_formats).toEqual(['remote'])
    const junk = applyParsedResume(base, parsed({ work_formats: { value: ['space'], confidence: 0.8 } }))
    expect(junk.form.work_formats).toEqual([])
    expect(junk.confidence.work_formats).toBeUndefined()
  })

  it('ссылка без схемы получает https:// при подстановке, проверке и сохранении', () => {
    const { form } = applyParsedResume(
      { ...base, work_formats: ['remote'] },
      parsed({ links: { value: ['github.com/denis-morozov-dev'], confidence: 0.95 } }),
    )
    expect(form.links).toEqual([{ type: 'github', url: 'https://github.com/denis-morozov-dev' }])
    const typed = { ...form, links: [{ type: 'portfolio' as const, url: ' habr.com/ru/users/denis ' }] }
    expect(validateProfile(typed)).toEqual({})
    expect(toUpdate(typed).links).toEqual([{ type: 'portfolio', url: 'https://habr.com/ru/users/denis' }])
    expect(validateProfile({ ...form, links: [{ type: 'portfolio', url: 'abc' }] }).links).toBeTruthy()
  })

  it('normalizeUrl не трогает ссылки со схемой и пустую строку', () => {
    expect(normalizeUrl('http://example.com')).toBe('http://example.com')
    expect(normalizeUrl('HTTPS://GitHub.com/x')).toBe('HTTPS://GitHub.com/x')
    expect(normalizeUrl('//t.me/x')).toBe('https://t.me/x')
    expect(normalizeUrl('   ')).toBe('')
  })
})
