/**
 * Типы и запросы кабинета администратора. Типы — из контракта (schema.ts, генерируется из OpenAPI).
 * Ключи запросов начинаются с 'admin', после любой правки сбрасываем весь кэш админки.
 */
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { components } from '@/shared/api/schema'
import { getErrorMessage } from '@/shared/api'
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
export type VacancyTestResult = S['VacancyTestResult']
export type ItemDraft = S['ItemDraft']
export type Report = S['Report']
export type ReportStatus = S['ReportStatus']
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
