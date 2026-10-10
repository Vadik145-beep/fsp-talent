/**
 * Коды навыков в тексте вакансии («Стек: kotlin, jetpack_compose, android_sdk») → подписи из справочника
 * («Стек: Kotlin, Jetpack Compose, Android SDK»). `label` возвращает сам код, если навык неизвестен.
 */
export function humanizeSkillCodes(text: string, label: (id: string) => string): string {
  const known = (code: string) => {
    const l = label(code)
    return l && l !== code ? l : null
  }
  // 1) Перечень после «Стек:» до точки или конца строки — каждый элемент по справочнику.
  let out = text.replace(/(Стек:\s*)([^.\n]+)/g, (_, head: string, list: string) =>
    head +
    list
      .split(',')
      .map((part) => {
        const code = part.trim()
        const l = known(code)
        return l ? part.replace(code, l) : part
      })
      .join(','),
  )
  // 2) Коды с подчёркиванием в любом месте текста — это точно коды, не слова.
  out = out.replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g, (code) => known(code) ?? code)
  return out
}
