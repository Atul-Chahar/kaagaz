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

// A legal time in its own unit, plus what it means in the plan's unit when they differ.
// unit: 'working_days' | 'calendar_days' | undefined (same as the plan); planUnit: 'working days' | 'days'
export function legalTime(days: number | null | undefined, unit: string | null | undefined, planUnit: string, span?: number): string {
  if (days === null || days === undefined) return 'unknown time'
  const own = unit === 'calendar_days' ? (days === 1 ? 'calendar day' : 'calendar days')
    : unit === 'working_days' ? (days === 1 ? 'working day' : 'working days')
    : planUnit === 'working days' ? (days === 1 ? 'working day' : 'working days') : (days === 1 ? 'day' : 'days')
  const sameUnit = !unit || (unit === 'working_days') === (planUnit === 'working days')
  if (sameUnit || span === undefined) return `${days} ${own}`
  return `${days} ${own} (${fmtDays(span, planUnit)})`
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
