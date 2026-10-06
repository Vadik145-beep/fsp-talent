/** Файлы бренда ФСП лежат в public/brand: fsp-logo.svg (знак + «ФСП»), fsp-logo-full.svg (с названием), fsp-mark.svg (знак). */
export type BrandAsset = 'fsp-logo.svg' | 'fsp-logo-full.svg' | 'fsp-mark.svg'

export function brandAsset(name: BrandAsset): string {
  return `${import.meta.env.BASE_URL}brand/${name}`
}
