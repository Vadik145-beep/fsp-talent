/** Отчество: Сергеевна, Ильич, Ахмед оглы… */
const PATRONYMIC_RE = /(ич|вна|ична|оглы|кызы|улы|гызы)$/i
/** Типичные окончания фамилий (для «Фамилия Имя» без отчества). */
const SURNAME_RE = /(ова|ева|ёва|ина|ына|ская|цкая|ов|ев|ёв|ин|ын|ский|цкий|ко|ук|юк|ян|дзе|швили)$/i

/**
 * Имя для приветствия из ФИО. Профиль заполняют по-разному: «Анна Колесникова» (форма регистрации),
 * «Колесникова Анна Сергеевна» (разбор PDF-резюме). Три слова с отчеством в конце — имя второе;
 * два слова, где первое похоже на фамилию, а второе нет, — тоже второе; иначе — первое.
 */
export function greetingName(fullName: string | null | undefined): string | null {
  const words = (fullName ?? '').trim().split(/\s+/).filter(Boolean)
  if (!words.length) return null
  if (words.length >= 3 && PATRONYMIC_RE.test(words[words.length - 1])) return words[words.length - 2]
  if (words.length === 2 && SURNAME_RE.test(words[0]) && !SURNAME_RE.test(words[1])) return words[1]
  return words[0]
}
