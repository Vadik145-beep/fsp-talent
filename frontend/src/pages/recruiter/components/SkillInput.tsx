import type { ReactNode } from 'react'
import { TagInput } from '@/shared/ui'
import { useSkills } from '../api'

export interface SkillInputProps {
  /** Коды технологий из справочника (python, postgresql…). */
  value: string[]
  onChange: (value: string[]) => void
  label?: ReactNode
  hint?: ReactNode
  placeholder?: string
  id?: string
  className?: string
}

/** Выбор стека: показывает подписи справочника, хранит коды. */
export function SkillInput({ value, onChange, label, hint, placeholder, id, className }: SkillInputProps) {
  const skills = useSkills()
  return (
    <TagInput
      id={id}
      label={label}
      hint={hint}
      placeholder={placeholder ?? 'Python, React, Kubernetes…'}
      value={value.map(skills.label)}
      options={skills.list.map((s) => s.label)}
      allowCustom={false}
      onChange={(labels) => onChange(labels.map(skills.idOf))}
      className={className}
    />
  )
}
