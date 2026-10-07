import { screen } from '@testing-library/react'
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
}

describe('результат теста: присвоенная категория и совет отдельно', () => {
  it('suggest_higher: категория Middle, уровень выше — отдельной строкой, Senior как категории нет', async () => {
    server.use(http.get('*/api/testing/sessions/901/result', () => HttpResponse.json(SUGGEST_HIGHER)))
    renderApp('/candidate/test/901/result', { role: 'candidate' })
    expect(await screen.findByText('Backend · Middle', {}, T)).toBeInTheDocument()
    expect(screen.getByText('Ваша категория')).toBeInTheDocument()
    expect(screen.getByText('Грейд Middle подтверждён')).toBeInTheDocument()
    expect(screen.getByText('Ваш уровень выше Middle — можно пройти тест на Senior')).toBeInTheDocument()
    expect(screen.queryByText('Backend · Senior')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Пройти тест на Senior' })).toBeInTheDocument()
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
