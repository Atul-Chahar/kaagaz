import type { Outcome, Plan, Scheme, VerdictKind } from './api'
import { fmtDate, fmtDays } from './format'

export const OUTCOME_LABEL: Record<Outcome, string> = {
  answered_with_path: 'Answered with a path',
  answered_from_memory: 'Answered from memory',
  not_in_graph: 'Not in the graph',
  unknown_name: 'Unknown name',
  no_official_time: 'No official time found',
}

export function stampClass(kind: VerdictKind): string {
  if (kind === 'on_time') return 'ok'
  if (kind === 'late' || kind === 'late_at_least') return ''
  return 'blue'
}

export function windowLine(s: Scheme): { text: string; cls: string } {
  if (!s.window_end) return { text: 'No deadline published', cls: 'muted' }
  const left = s.days_left ?? 0
  if (left < 0) return { text: `Closed ${fmtDate(s.window_end)}`, cls: 'muted' }
  const prefix = s.window_is_last_published ? 'Last published window ended' : 'Closes'
  return { text: `${prefix} ${fmtDate(s.window_end)}`, cls: left <= 21 ? 'late' : '' }
}

export function verdictSentence(p: Plan): string {
  const v = p.verdict
  const u = p.day_unit
  const dl = p.deadline.date ? fmtDate(p.deadline.date) : ''
  const left = p.days_left ?? 0
  switch (v.kind) {
    case 'late':
      return `This chain takes ${fmtDays(v.critical_days, u)}, but only ${fmtDays(left, u)} are left before ${dl}.`
    case 'on_time':
      return `This chain takes ${fmtDays(v.critical_days, u)}. You have ${fmtDays(left, u)} before ${dl}, so ${v.margin} to spare.`
    case 'late_at_least':
      return `The steps with a legal time limit alone take ${fmtDays(v.critical_days, u)}, and only ${fmtDays(left, u)} are left before ${dl}.`
    case 'at_least':
      return `This chain takes at least ${fmtDays(v.critical_days, u)}. Some steps have no official time limit, so it could take longer. You have ${fmtDays(left, u)} before ${dl}.`
    case 'closed':
      return `The application window closed on ${dl}.`
    case 'no_deadline':
      return `No deadline is published for this scheme. The chain needs ${v.exact ? '' : 'at least '}${fmtDays(v.critical_days, u)}.`
    default:
      return "The time needed can't be computed, because none of the steps left has an official time limit."
  }
}
