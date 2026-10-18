// Typed client for the Kaagaz API. Every call goes to the FastAPI backend, which queries FalkorDB.

export type Outcome = 'answered_with_path' | 'answered_from_memory' | 'not_in_graph' | 'unknown_name' | 'no_official_time'

export interface Cite {
  source_url: string
  source_title: string
  retrieved_at: string
  excerpt: string
  confidence: 'official' | 'secondary'
  note?: string
  condition?: string
}

export interface TraceRow {
  kind: 'tool' | 'query'
  tool: string
  graph?: string
  args: Record<string, unknown>
  ms: number
  rows: number
  outcome?: Outcome
}

export interface Scheme {
  id: string
  name: string
  authority?: string
  portal?: string
  note?: string
  window_start?: string
  window_end?: string
  window_year?: string
  window_is_last_published?: boolean
  window_note?: string
  window_renewals_only?: boolean
  window_source_url?: string
  window_source_title?: string
  window_retrieved_at?: string
  window_excerpt?: string
  window_confidence?: string
  days_left?: number | null
  day_unit?: string
  direct_requirements?: number
}

export interface PlanItem {
  id: string
  label: 'Document' | 'AnyOf'
  name: string
  days: number | null
  depth: number
  path: string[]
  rule: Cite | null
  office_id: string | null
  office_name: string | null
  held: boolean
  needed: boolean
  on_critical: boolean
  days_source: Cite | null
  days_unit?: string
  span?: number
  note?: string | null
  hidden_below: boolean
  start?: number
  end?: number
  exact?: boolean
  satisfied?: boolean
  chosen?: string | null
  options?: string[]
}

export type VerdictKind = 'on_time' | 'late' | 'at_least' | 'late_at_least' | 'closed' | 'no_deadline' | 'cannot_compute'

export interface Plan {
  scheme: Scheme
  student_id: string
  depth: number
  max_depth: number
  today: string
  deadline: { date: string | null; source: string; renewal_window_end?: string }
  days_left: number | null
  day_unit: string
  calendar_complete: boolean
  calendar_covers_until: string | null
  holidays_ahead: { date: string; name: string }[]
  dates: string[]
  verdict: { kind: VerdictKind; stamp: string; critical_days: number; exact: boolean; margin: number | null }
  critical_path: string[]
  needed: string[]
  held: string[]
  unknown: string[]
  hidden_more: boolean
  applies: string[]
  conditional: { from: string; doc_id: string; name: string; condition: string; applies: boolean; held: boolean }[]
  items: PlanItem[]
  start_today: { id: string; name: string; days: number | null; days_unit?: string; span?: number; office_name: string | null; reduction: number; on_critical: boolean; path: string[] }[]
  chain_check: { chain_days_cypher: number; planner_all_of: number; agree: boolean }
  option_checks: { anyof_id: string; cypher_choice: string | null; cypher_days: number | null; planner_choice: string | null; planner_days: number; comparable: boolean; agree: boolean | null }[]
  saved_at?: string
}

export interface ToolResponse<T> {
  tool: string
  outcome: Outcome
  message: string
  data: T
  trace: TraceRow[]
  cypher?: Record<string, string>
  browser_url?: string
  rules_graph?: string
}

export class ApiError extends Error {
  status: number
  code?: string
  constructor(status: number, message: string, code?: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

// The rule pack every call reads. Set by the Start screen's pack switcher (shown only when more than one pack exists).
let currentPack: string | null = null
export function setPack(id: string | null) { currentPack = id }
export function getPack(): string | null { return currentPack }

// The date every count starts from. null means today. Set by the date bar ("see it as on the submission day");
// the server only changes "today", never the rules or deadlines.
let currentAsOf: string | null = null
export function setAsOf(day: string | null) { currentAsOf = day }
export function getAsOf(): string | null { return currentAsOf }

function withPack(path: string): string {
  if (!currentPack || path.startsWith('/api/health') || path === '/api/packs') return path
  return `${path}${path.includes('?') ? '&' : '?'}pack=${encodeURIComponent(currentPack)}`
}

async function req<T>(rawPath: string, init?: RequestInit): Promise<T> {
  const path = withPack(rawPath)
  let r: Response
  try {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (currentAsOf) headers['X-Kaagaz-As-Of'] = currentAsOf
    r = await fetch(path, { headers, ...init })
  } catch {
    throw new ApiError(0, "The Kaagaz server isn't reachable. Start it with `docker compose up`.", 'api_unreachable')
  }
  if (!r.ok) {
    let body: { message?: string; error?: string; detail?: unknown } = {}
    try { body = await r.json() } catch { /* not JSON */ }
    const msg = body.message || (typeof body.detail === 'string' ? body.detail : `Request failed (${r.status}).`)
    throw new ApiError(r.status, msg, body.error)
  }
  return r.json() as Promise<T>
}

export interface PackInfo { id: string; name: string; jurisdiction: string; version: string; default?: boolean; ui?: Record<string, string> }

export const api = {
  packs: () => req<PackInfo[]>('/api/packs'),
  health: () => req<{ ok: boolean; falkordb: boolean; message?: string; llm: boolean; llm_model: string | null; browser_url: string; packs?: Record<string, boolean>; snapshot_date?: string }>('/api/health'),
  schemes: () => req<{ today: string; schemes: Scheme[] }>('/api/schemes'),
  documents: () => req<{ documents: { id: string; name: string; days: number | null; days_unit?: string | null; office_name: string | null; group: string }[]; groups: string[] }>('/api/documents'),
  prerequisites: (scheme_id: string, depth = 8) =>
    req<ToolResponse<{ nodes: { id: string; label: string; name: string; days: number | null; depth: number }[] }>>(`/api/schemes/${encodeURIComponent(scheme_id)}/prerequisites?depth=${depth}`),
  newStudent: () => req<{ id: string; label: string }>('/api/students', { method: 'POST', body: JSON.stringify({ label: 'Student' }) }),
  example: (replace?: string) => req<{ student_id: string; label: string; scheme_id: string; holdings: string[]; about?: string }>(`/api/students/example${replace ? `?replace=${encodeURIComponent(replace)}` : ''}`, { method: 'POST' }),
  recall: (sid: string) => req<ToolResponse<{ student: { id: string; label: string; created_at: string } | null; holdings?: { doc_id: string; name: string; issued_on: string | null; added_at: string }[]; targets?: { scheme_id: string; deadline: string | null; added_at: string }[]; snapshots?: { at: string; scheme_id: string; verdict: string; critical_days: number }[] }>>(`/api/students/${sid}`),
  setTarget: (sid: string, scheme_id: string, deadline?: string) => req(`/api/students/${sid}/target`, { method: 'PUT', body: JSON.stringify({ scheme_id, deadline: deadline || null }) }),
  addHolding: (sid: string, doc_id: string) => req<ToolResponse<unknown>>(`/api/students/${sid}/holdings`, { method: 'POST', body: JSON.stringify({ doc_id }) }),
  addApplies: (sid: string, doc_id: string) => req(`/api/students/${sid}/applies`, { method: 'POST', body: JSON.stringify({ doc_id }) }),
  removeApplies: (sid: string, doc_id: string) => req(`/api/students/${sid}/applies/${encodeURIComponent(doc_id)}`, { method: 'DELETE' }),
  removeHolding: (sid: string, doc_id: string) => req(`/api/students/${sid}/holdings/${encodeURIComponent(doc_id)}`, { method: 'DELETE' }),
  plan: (sid: string, scheme_id: string, depth: number, remember: boolean) =>
    req<ToolResponse<Plan>>(`/api/plan?student_id=${sid}&scheme_id=${encodeURIComponent(scheme_id)}&depth=${depth}&remember=${remember}`),
  explain: (scheme_id: string, doc_id: string) =>
    req<ToolResponse<{ scheme: { id: string; name: string }; doc: { id: string; name: string }; paths: { nodes: { id: string; name: string; label: string }[]; rules: Cite[]; types: string[] }[]; detail: { doc?: Record<string, unknown>; office_id?: string; office_name?: string; issues?: Cite & { days?: number }; requires?: { id: string; name: string; label: string }[] } }>>(`/api/explain?scheme_id=${encodeURIComponent(scheme_id)}&doc_id=${encodeURIComponent(doc_id)}`),
  alternatives: (sid: string, scheme_id: string) =>
    req<ToolResponse<{ options: { scheme_id: string; name: string; verdict: Plan['verdict']; deadline: Plan['deadline']; days_left: number | null; calendar_complete: boolean; shared: string[]; shared_count: number; needed_count: number }[] }>>(`/api/alternatives?student_id=${sid}&scheme_id=${encodeURIComponent(scheme_id)}`),
  ask: (question: string, student_id?: string, scheme_id?: string) =>
    req<AskResponse>('/api/ask', { method: 'POST', body: JSON.stringify({ question, student_id, scheme_id }) }),
  benchmark: () => req<BenchResponse>('/api/benchmark'),
  sources: () => req<{ sources: { id: string; title: string; url: string; retrieved_at: string; sha256: string; content_type: string; size: number; rules_citing: number; confidence: string | null }[] }>('/api/sources'),
  queries: () => req<{ name: string; file: string; about: string; cypher: string }[]>('/api/queries'),
  graphStats: () => req<{ graph: string; rows: { kind: string; name: string; n: number }[]; ms: number }>('/api/graph-stats'),
  reviewCase: (sid: string, scheme_id?: string) => req<CaseReview>(`/api/students/${sid}/case`, { method: 'POST', body: JSON.stringify({ scheme_id: scheme_id ?? null }) }),
  caseState: (sid: string) => req<{ review: StoredReview | null; proposals: Proposal[]; tasks: Task[]; alerts: Alert[] }>(`/api/students/${sid}/case`),
  decideProposal: (sid: string, pid: string, approve: boolean) =>
    req<{ proposal: Proposal; done: unknown; plan_after?: { scheme_id: string; stamp: string; kind: VerdictKind } }>(`/api/students/${sid}/proposals/${encodeURIComponent(pid)}`, { method: 'POST', body: JSON.stringify({ approve }) }),
  setTask: (sid: string, tid: string, status: 'open' | 'done') => req<{ task: Task }>(`/api/students/${sid}/tasks/${encodeURIComponent(tid)}`, { method: 'POST', body: JSON.stringify({ status }) }),
  alertsSeen: (sid: string) => req<{ marked: number }>(`/api/students/${sid}/alerts/seen`, { method: 'POST' }),
  agents: () => req<{ agents: AgentInfo[]; runs: AgentRun[]; running: boolean; findings: Finding[]; graph: string }>('/api/agents'),
  agentRun: (id: string) => req<{ run: AgentRun; checks: SourceCheck[]; findings: string[] }>(`/api/agents/runs/${encodeURIComponent(id)}`),
  startWatch: (limit?: number) => req<{ started: boolean }>('/api/agents/watcher/run', { method: 'POST', body: JSON.stringify(limit ? { limit } : {}) }),
  decideFinding: (id: string, approve: boolean, note?: string) =>
    req<{ finding: Finding; applied: unknown; propagation?: { notified: { student_id: string; before?: string; after: string }[] } }>(`/api/agents/findings/${encodeURIComponent(id)}`, { method: 'POST', body: JSON.stringify({ approve, note: note || null }) }),
  loadBearing: (sid?: string) => req<{ scheme_ids: string[]; by_scheme_count: { doc_id: string; name: string; days: number | null; scheme_count: number }[]; pagerank: { doc_id: string; name: string; score: number }[] }>(`/api/load-bearing${sid ? `?student_id=${sid}` : ''}`),
}

export interface CaseStep { n: number; tool: string; why: string; found: string; outcome?: Outcome | null }
export interface Proposal {
  id: string; kind: 'apply' | 'gather' | 'checkpoint' | 'switch_target'; title: string; reason: string
  doc_id?: string | null; scheme_id: string; due?: string | null
  status: 'pending' | 'approved' | 'rejected' | 'replaced'; case_id: string; created_at: string; decided_at?: string
}
export interface Task {
  id: string; kind: string; title: string; reason?: string; doc_id?: string | null; scheme_id: string; due?: string | null
  status: 'open' | 'done'; created_at: string
}
export interface Alert {
  id: string; at: string; kind: string; scheme_id: string; finding_id: string; message: string
  before?: string; after?: string; seen: boolean
}
export interface Since {
  last_review: string; last_today?: string; working_days_passed: number; stamp_before?: string; stamp_now: string
  verdict_before?: string; verdict_now: string; new_holdings: string[]; dropped_holdings: string[]; scheme_changed: boolean
}
export interface CaseReview {
  case_id: string; scheme: { id: string; name: string }; today: string; as_of: boolean
  verdict: Plan['verdict']; decision: { kind: string; text: string }; since: Since | null; steps: CaseStep[]
  proposals: Proposal[]; note: { text: string | null; ok: boolean; problems: string[] } | null; trace: TraceRow[]
}
export interface StoredReview {
  id: string; at: string; scheme_id: string; today: string; verdict: VerdictKind; stamp: string; decision: string
  json: { steps: CaseStep[]; decision: { kind: string; text: string }; since: Since | null; as_of?: boolean; note?: CaseReview['note'] }
}
export interface Finding {
  id: string; pack: string; kind: 'date_changed' | 'wording_changed' | 'value_changed' | 'excerpt_missing'
  rule_keys: string[]; rule_count: number; rule_kind: string; from_ids: string[]; to_id: string; source_id: string; source_url: string
  source_title: string; old_excerpt: string; old_value?: string; new_excerpt?: string; new_value?: string
  score?: number; note?: string; checked_on: string; status: 'open' | 'approved' | 'rejected'
  created_at: string; last_seen: string; seen_count: number; decided_at?: string; decided_note?: string
  tls_verified?: boolean; schemes: string[]; students: number
}
export interface AgentRun {
  id: string; agent: string; pack: string; started_at: string; finished_at?: string; status: 'running' | 'done' | 'failed'
  trigger: string; summary: Record<string, number | string> | null
}
export interface SourceCheck {
  source_id: string; url: string; title: string; at: string; status: string; rules_checked: number; rules_missing: number
  http?: number; tls_verified?: boolean; same_file?: boolean; error?: string; warning?: string
}
export interface AgentInfo { id: string; name: string; role: string; cursor?: string | null; runs: number; last_run?: string | null; decisions: number }

export interface AskResponse {
  mode: 'llm' | 'name_search'
  question: string
  tool: string
  args: Record<string, unknown>
  outcome: Outcome
  answer: string
  answer_source: string
  check?: { ok: boolean; problems: string[] } | null
  route_error?: string | null
  data: Record<string, unknown> | null
  trace: TraceRow[]
}

export interface BenchSystemScore {
  system: string
  document_recall: number | null
  invented_documents: number | null
  verdict_accuracy: number | null
  first_step_accuracy: number | null
  n: Record<string, number>
}

export interface BenchRun {
  kind: 'llm' | 'deterministic'
  started_at: string
  finished_at?: string
  model: string | null
  provider?: string | null
  questions: number
  pack: string
  systems: BenchSystemScore[]
  note?: string
  disagreements?: Record<string, unknown>[]
}

export interface BenchResponse {
  llm_run: BenchRun | null
  llm_run_file: string | null
  deterministic_run: BenchRun | null
  deterministic_run_file: string | null
  llm_configured: boolean
}
