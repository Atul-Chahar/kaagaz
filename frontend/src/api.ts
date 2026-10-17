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
  window_source_url?: string
  window_source_title?: string
  window_retrieved_at?: string
  window_excerpt?: string
  window_confidence?: string
  days_left?: number | null
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
  deadline: { date: string | null; source: string }
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
  items: PlanItem[]
  start_today: { id: string; name: string; days: number | null; office_name: string | null; reduction: number; on_critical: boolean; path: string[] }[]
  chain_check: { chain_days_cypher: number; planner_all_of: number; agree: boolean }
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

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response
  try {
    r = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...init })
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

export const api = {
  health: () => req<{ ok: boolean; falkordb: boolean; message?: string; llm: boolean; llm_model: string | null; browser_url: string; packs?: Record<string, boolean> }>('/api/health'),
  schemes: () => req<{ today: string; schemes: Scheme[] }>('/api/schemes'),
  documents: () => req<{ documents: { id: string; name: string; days: number | null; office_name: string | null; group: string }[]; groups: string[] }>('/api/documents'),
  prerequisites: (scheme_id: string, depth = 8) =>
    req<ToolResponse<{ nodes: { id: string; label: string; name: string; days: number | null; depth: number }[] }>>(`/api/schemes/${encodeURIComponent(scheme_id)}/prerequisites?depth=${depth}`),
  newStudent: () => req<{ id: string; label: string }>('/api/students', { method: 'POST', body: JSON.stringify({ label: 'Student' }) }),
  example: () => req<{ student_id: string; label: string; scheme_id: string; holdings: string[]; about?: string }>('/api/students/example', { method: 'POST' }),
  recall: (sid: string) => req<ToolResponse<{ student: { id: string; label: string; created_at: string } | null; holdings?: { doc_id: string; name: string; issued_on: string | null; added_at: string }[]; targets?: { scheme_id: string; deadline: string | null; added_at: string }[]; snapshots?: { at: string; scheme_id: string; verdict: string; critical_days: number }[] }>>(`/api/students/${sid}`),
  setTarget: (sid: string, scheme_id: string) => req(`/api/students/${sid}/target`, { method: 'PUT', body: JSON.stringify({ scheme_id }) }),
  addHolding: (sid: string, doc_id: string) => req<ToolResponse<unknown>>(`/api/students/${sid}/holdings`, { method: 'POST', body: JSON.stringify({ doc_id }) }),
  removeHolding: (sid: string, doc_id: string) => req(`/api/students/${sid}/holdings/${encodeURIComponent(doc_id)}`, { method: 'DELETE' }),
  plan: (sid: string, scheme_id: string, depth: number, remember: boolean) =>
    req<ToolResponse<Plan>>(`/api/plan?student_id=${sid}&scheme_id=${encodeURIComponent(scheme_id)}&depth=${depth}&remember=${remember}`),
  explain: (scheme_id: string, doc_id: string) =>
    req<ToolResponse<{ scheme: { id: string; name: string }; doc: { id: string; name: string }; paths: { nodes: { id: string; name: string; label: string }[]; rules: Cite[]; types: string[] }[]; detail: { doc?: Record<string, unknown>; office_id?: string; office_name?: string; issues?: Cite & { days?: number }; requires?: { id: string; name: string; label: string }[] } }>>(`/api/explain?scheme_id=${encodeURIComponent(scheme_id)}&doc_id=${encodeURIComponent(doc_id)}`),
  alternatives: (sid: string, scheme_id: string) =>
    req<ToolResponse<{ options: { scheme_id: string; name: string; verdict: Plan['verdict']; deadline: Plan['deadline']; days_left: number | null; shared: string[]; shared_count: number; needed_count: number }[] }>>(`/api/alternatives?student_id=${sid}&scheme_id=${encodeURIComponent(scheme_id)}`),
  ask: (question: string, student_id?: string, scheme_id?: string) =>
    req<AskResponse>('/api/ask', { method: 'POST', body: JSON.stringify({ question, student_id, scheme_id }) }),
  benchmark: () => req<BenchResponse>('/api/benchmark'),
  sources: () => req<{ sources: { id: string; title: string; url: string; retrieved_at: string; sha256: string; content_type: string; size: number; rules_citing: number; confidence: string | null }[] }>('/api/sources'),
  queries: () => req<{ name: string; file: string; about: string; cypher: string }[]>('/api/queries'),
  graphStats: () => req<{ graph: string; rows: { kind: string; name: string; n: number }[]; ms: number }>('/api/graph-stats'),
  loadBearing: (sid?: string) => req<{ scheme_ids: string[]; by_scheme_count: { doc_id: string; name: string; days: number | null; scheme_count: number }[]; pagerank: { doc_id: string; name: string; score: number }[] }>(`/api/load-bearing${sid ? `?student_id=${sid}` : ''}`),
}

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
}

export interface BenchResponse {
  llm_run: BenchRun | null
  llm_run_file: string | null
  deterministic_run: BenchRun | null
  deterministic_run_file: string | null
  llm_configured: boolean
}
