/**
 * Типы и запросы кабинета администратора. Типы — из контракта (schema.ts, генерируется из OpenAPI).
 * Ключи запросов начинаются с 'admin', после любой правки сбрасываем весь кэш админки.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { components } from '@/shared/api/schema'
import { api, getErrorMessage, isApiError, type QueryParams } from '@/shared/api'
import { useToast } from '@/shared/ui'

type S = components['schemas']

export type AdminDashboard = S['AdminDashboard']
export type UserRecord = S['UserRecord']
export type UserPage = S['Page_UserRecord_']
export type AuditEntry = S['AuditEntry']
export type AuditPage = S['Page_AuditEntry_']
export type AdminCompany = S['AdminCompany']
export type PlatformSettings = S['PlatformSettings']
export type PlatformSettingsUpdate = S['PlatformSettingsUpdate']
export type GradeThreshold = S['GradeThreshold']
export type RankingWeights = S['RankingWeights']
export type Specialization = S['Specialization']
export type Grade = S['Grade']
export type Skill = S['Skill']
export type Topic = S['Topic']
export type ItemSummary = S['ItemSummary']
export type ItemPage = S['Page_ItemSummary_']
export type ItemDetail = S['ItemDetail']
export type ItemVariantPreview = S['ItemVariantPreview']
export type ItemStatus = S['ItemStatus']
export type ItemFormat = S['ItemFormat']
export type CoverageCell = S['CoverageCell']
export type RecalibrationResult = S['RecalibrationResult']
export type LeakScanResult = S['LeakScanResult']
export type VacancyTestResult = S['VacancyTestOut']
/** Черновик шаблона из вакансии: item_id — id черновика в банке (если нет — ищем шаблон по теме и названию). */
export type ItemDraft = S['ItemDraftOut']
export type Report = S['Report']
export type ReportStatus = S['ReportStatus']
export type ReportDecision = S['ReportDecision']
export type ReportReason = S['ReportReason']
export type ValidationOverview = S['ValidationOverview']
export type ValidationChart = S['ValidationChart']
export type MatchingEvalResult = S['MatchingEvalResult']
export type Role = S['Role']
export type SpecCode = S['SpecializationCode']
export type GradeCode = S['GradeCode']

/** Мутация с тостом об успехе/ошибке и сбросом кэша админки. */
export function useAdminMutation<TVars, TResult = unknown>(
  fn: (vars: TVars) => Promise<TResult>,
  opts: { success?: string | ((r: TResult, v: TVars) => string); onSuccess?: (r: TResult, v: TVars) => void } = {},
) {
  const qc = useQueryClient()
  const { toast } = useToast()
  return useMutation({
    mutationFn: fn,
    onSuccess: async (result, vars) => {
      await qc.invalidateQueries({ queryKey: ['admin'] })
      if (opts.success) {
        const title = typeof opts.success === 'function' ? opts.success(result, vars) : opts.success
        toast({ title, tone: 'success' })
      }
      opts.onSuccess?.(result, vars)
    },
    onError: (error) => toast({ title: 'Не получилось', description: getErrorMessage(error), tone: 'error' }),
  })
}

// --- Банк задач: все страницы ------------------------------------------------------------
const ITEMS_PAGE = 200

/** Все шаблоны под фильтр (бэкенд отдаёт не больше 200 за раз — проходим по страницам). */
export async function fetchAllItems(query: QueryParams = {}): Promise<ItemPage> {
  const first = await api.get<ItemPage>('/admin/items', { query: { ...query, page: 1, page_size: ITEMS_PAGE } })
  const pages = Math.ceil(first.total / ITEMS_PAGE)
  if (pages <= 1) return first
  const rest = await Promise.all(
    Array.from({ length: pages - 1 }, (_, i) =>
      api.get<ItemPage>('/admin/items', { query: { ...query, page: i + 2, page_size: ITEMS_PAGE } }),
    ),
  )
  return { ...first, items: [first.items, ...rest.map((p) => p.items)].flat(), page_size: first.total }
}

// --- Ошибки валидации по полям -------------------------------------------------------------
/** Где показать доменную ошибку бэкенда (код → поле формы). */
const CODE_FIELDS: Record<string, string> = {
  invalid_thresholds: 'grade_thresholds',
  invalid_weights: 'ranking_weights',
  skill_exists: 'id',
  id_mismatch: 'id',
  unknown_specialization: 'specializations',
  topic_exists: 'id',
  topic_code_invalid: 'id',
  specialization_exists: 'id',
}

interface PydanticError {
  loc?: Array<string | number>
  msg?: string
  type?: string
  ctx?: Record<string, unknown>
}

const fmtNum = (v: unknown) => String(v).replace('.', ',')

/** Сообщение pydantic по-русски (по типу ошибки), иначе — как прислал бэкенд. */
function pydanticMessage(e: PydanticError): string {
  const c = e.ctx ?? {}
  switch (e.type) {
    case 'missing':
      return 'Обязательное поле'
    case 'less_than_equal':
      return `Не больше ${fmtNum(c.le)}`
    case 'less_than':
      return `Меньше ${fmtNum(c.lt)}`
    case 'greater_than_equal':
      return `Не меньше ${fmtNum(c.ge)}`
    case 'greater_than':
      return `Больше ${fmtNum(c.gt)}`
    case 'int_parsing':
    case 'int_type':
    case 'int_from_float':
      return 'Нужно целое число'
    case 'float_parsing':
    case 'float_type':
      return 'Нужно число'
    case 'string_too_short':
      return c.min_length === 1 ? 'Не может быть пустым' : `Не короче ${String(c.min_length)} символов`
    case 'string_too_long':
      return `Не длиннее ${String(c.max_length)} символов`
    case 'string_pattern_mismatch':
      return 'Недопустимые символы: латиница в нижнем регистре, цифры и _+.#-'
    case 'too_short':
      return 'Выберите хотя бы один вариант'
    case 'enum':
    case 'literal_error':
      return 'Недопустимое значение'
    default:
      return e.msg ?? 'Неверное значение'
  }
}

/**
 * Ошибки по полям формы из ответа API.
 * - 422 validation_error бэкенда: details.errors = [{loc: ['body', поле, ...], type, ctx, msg}];
 * - доменные коды (invalid_thresholds, invalid_weights, skill_exists…) → сообщение на нужное поле;
 * - старый формат моков: details = {поле: сообщение}.
 * Ключ '_' — ошибка без поля.
 */
export function fieldErrors(error: unknown): Record<string, string> {
  if (!isApiError(error)) return {}
  const out: Record<string, string> = {}
  const list = error.details.errors
  if (Array.isArray(list)) {
    for (const raw of list as PydanticError[]) {
      const loc = (raw.loc ?? []).filter((p) => p !== 'body')
      const field = loc.length ? String(loc[0]) : '_'
      if (!out[field]) out[field] = pydanticMessage(raw)
    }
    return out
  }
  const field = CODE_FIELDS[error.code]
  if (field) {
    out[field] = error.message
    return out
  }
  if (error.code === 'validation_error') for (const [k, v] of Object.entries(error.details)) if (typeof v === 'string') out[k] = v
  if (!Object.keys(out).length) out._ = error.message
  return out
}
