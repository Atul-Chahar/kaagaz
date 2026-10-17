// Plain formatting: dates as "21 Nov 2026", days as "21 days".

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return ''
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  if (!y || !m || !d) return iso
  return `${d} ${MONTHS[m - 1]} ${y}`
}

export function fmtDays(n: number | null | undefined, unit = 'days'): string {
  if (n === null || n === undefined) return 'unknown time'
  const u = unit === 'working days' ? (n === 1 ? 'working day' : 'working days') : n === 1 ? 'day' : 'days'
  return `${n} ${u}`
}

export function hostOf(url: string): string {
  try { return new URL(url).hostname.replace(/^www\./, '') } catch { return url }
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

// Short display name: drops a trailing "(…)" qualifier, which the Why panel still shows in full.
export function shortName(name: string): string {
  const s = name.replace(/\s*\([^()]*\)\s*$/, '').trim()
  return s.length >= 6 ? s : name
}
