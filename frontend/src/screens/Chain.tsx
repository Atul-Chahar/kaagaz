import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, type Plan, type PlanItem, type ToolResponse } from '../api'
import { Loading, StateBox, Stamp, TraceTable } from '../components/common'
import { fmtDate, fmtDays, hostOf, legalTime, plural, shortName } from '../format'
import { go, type Session } from '../nav'
import { verdictSentence } from '../labels'
import { usePackUi } from '../packui'
import WhyPanel from '../components/WhyPanel'
import Timeline from '../components/Timeline'

type Cache = Record<number, ToolResponse<Plan>>

function deadlineLabel(p: Plan): string {
  const s = p.scheme
  if (p.deadline.source === 'student') return 'your own date'
  if (p.deadline.source === 'example_own_date') return "the example's own made-up date"
  if (p.deadline.source === 'last_published_window') return `last published window (${s.window_year ?? ''})`
  if (p.deadline.source === 'published_window') return `published window ${s.window_year ?? ''}`
  return 'none published'
}

export default function Chain({ session, setSession }: { session: Session | null; setSession: (s: Session | null) => void }) {
  const [cache, setCache] = useState<Cache>({})
  const [depth, setDepth] = useState<number | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [why, setWhy] = useState<string | null>(null)
  const [pending, setPending] = useState<Set<string>>(new Set())
  const [memoryNote, setMemoryNote] = useState<string | null>(null)
  const [alts, setAlts] = useState<Awaited<ReturnType<typeof api.alternatives>> | null>(null)
  const [pressKey, setPressKey] = useState(0)
  const whyTrigger = useRef<HTMLElement | null>(null)
  const ui = usePackUi()
  const sid = session?.id
  const scheme = session?.scheme_id

  const loadAll = useCallback(async (keepDepth?: number) => {
    if (!sid || !scheme) return
    try {
      const full = await api.plan(sid, scheme, 8, true)
      const max = Math.max(1, full.data.max_depth)
      const next: Cache = { [max]: full }
      if (max < 8) next[8] = full
      const rest = await Promise.all(
        Array.from({ length: max - 1 }, (_, i) => i + 1).map(d => api.plan(sid, scheme, d, false).then(r => [d, r] as const)),
      )
      rest.forEach(([d, r]) => { next[d] = r })
      setError(null)
      setCache(next)
      setDepth(prev => {
        const want = keepDepth ?? prev ?? (session?.example ? 1 : max)
        return Math.min(want, max)
      })
      setPressKey(k => k + 1)
      api.alternatives(sid, scheme).then(setAlts).catch(() => setAlts(null))
    } catch (e) {
      setError(e as ApiError)
    }
  }, [sid, scheme, session?.example])

  // oxlint-disable-next-line react/set-state-in-effect -- loadAll sets state only after an awaited fetch
  useEffect(() => { loadAll() }, [loadAll])

  useEffect(() => {
    if (!sid) return
    api.recall(sid).then(r => {
      if (r.outcome === 'answered_from_memory') {
        const snaps = r.data.snapshots ?? []
        const prev = snaps.length > 1 ? snaps[1] : null
        const n = r.data.holdings?.length ?? 0
        setMemoryNote(`Answered from memory: ${plural(n, 'document', 'documents')} held, saved ${fmtDate(r.data.student?.created_at)}.` +
          (prev ? ` Last plan before this one: ${fmtDate(prev.at)}, ${prev.critical_days} days on the critical path.` : ''))
      }
    }).catch(() => setMemoryNote(null))
  }, [sid, cache])

  const plan = depth !== null ? cache[depth]?.data : undefined
  const maxDepth = plan?.max_depth ?? 1
  const itemsById = useMemo(() => Object.fromEntries((plan?.items ?? []).map(i => [i.id, i])), [plan])

  async function toggleHeld(docId: string, has: boolean) {
    if (!sid) return
    setPending(p => new Set(p).add(docId))
    try {
      if (has) await api.removeHolding(sid, docId)
      else await api.addHolding(sid, docId)
      await loadAll(depth ?? undefined)
    } catch (e) {
      setError(e as ApiError)
    } finally {
      setPending(p => { const n = new Set(p); n.delete(docId); return n })
    }
  }

  async function toggleApplies(docId: string, on: boolean) {
    if (!sid) return
    setPending(p => new Set(p).add(`applies:${docId}`))
    try {
      if (on) await api.removeApplies(sid, docId)
      else await api.addApplies(sid, docId)
      await loadAll(depth ?? undefined)
    } catch (e) {
      setError(e as ApiError)
    } finally {
      setPending(p => { const n = new Set(p); n.delete(`applies:${docId}`); return n })
    }
  }

  function openWhy(id: string, el: HTMLElement | null) {
    whyTrigger.current = el
    setWhy(id)
  }

  function closeWhy() {
    setWhy(null)
    whyTrigger.current?.focus()
  }

  if (!session || !scheme) {
    return (
      <StateBox title="No plan yet" testid="no-session">
        <p>Pick a {ui.target} and tick what you hold on the <a href="#/">Start page</a>, or load the Example there.</p>
      </StateBox>
    )
  }
  if (error) {
    return (
      <StateBox title={error.code === 'falkordb_unreachable' ? "FalkorDB isn't reachable" : 'This plan could not be computed'} error>
        <p>{error.message}</p>
        {error.status === 404 && <p style={{ marginTop: 8 }}><button className="btn ghost small" onClick={() => { setSession(null); go('/') }}>Start again</button></p>}
      </StateBox>
    )
  }
  if (!plan || depth === null) return <Loading label="Walking the requirement graph in FalkorDB" />

  const v = plan.verdict
  const needed = plan.items.filter(i => i.label === 'Document' && i.needed)
  const heldItems = plan.items.filter(i => i.label === 'Document' && i.held)
  const unknownCount = plan.unknown.length
  const stampSub = v.kind === 'closed' || v.kind === 'no_deadline' ? undefined
    : `${plan.day_unit === 'working days' ? 'Working days' : 'Days'} · ${depth} of ${maxDepth} steps`

  return (
    <div>
      <div className="chain-head">
        <div>
          <p className="eyebrow">{session.example ? `${session.label ?? 'Example student'} (made up, not a real person)` : 'Your chain'}</p>
          <h1 style={{ fontSize: 'clamp(1.8rem, 4vw, 2.6rem)' }}>{plan.scheme.name}</h1>
          <p className="who">{plan.scheme.authority}{plan.scheme.portal ? ` · ${plan.scheme.portal}` : ''}</p>
        </div>
        <a className="btn ghost small" href="#/">Change {ui.target} or documents</a>
      </div>

      <section className="verdict-bar" aria-labelledby="verdict-h">
        <div className="verdict-text">
          <h2 id="verdict-h" className="sr-only">Verdict</h2>
          <p className="big" aria-live="polite" data-testid="verdict-sentence">{verdictSentence(plan)}</p>
          <div className="facts">
            <span>Today <b>{fmtDate(plan.today)}</b></span>
            <span>Deadline <b>{plan.deadline.date ? fmtDate(plan.deadline.date) : 'none'}</b> ({deadlineLabel(plan)}{plan.scheme.window_source_url ? <>, <a href={plan.scheme.window_source_url} target="_blank" rel="noreferrer">source</a></> : null})</span>
            {plan.days_left !== null && plan.days_left >= 0 && <span>Left <b>{fmtDays(plan.days_left, plan.day_unit)}</b></span>}
            <span>Critical path <b data-testid="critical-days">{v.exact ? '' : 'at least '}{fmtDays(v.critical_days, plan.day_unit)}</b></span>
            {unknownCount > 0 && <span><b>{unknownCount}</b> steps with no official time limit</span>}
          </div>
          {!plan.calendar_complete && plan.deadline.date && (
            <p className="note" style={{ marginTop: 8 }}>Holidays after {fmtDate(plan.calendar_covers_until)} are not published yet, so the working days left may be slightly fewer than shown.</p>
          )}
          {plan.day_unit === 'working days' && (
            <p className="note" style={{ marginTop: 8 }}>The legal time limits here count working days. Sundays, second and fourth Saturdays and the {plural(plan.holidays_ahead.length, 'government holiday', 'government holidays')} before the deadline are not counted. A limit given in calendar days is converted on the same calendar.</p>
          )}
        </div>
        <div className="stamp-slot">
          <Stamp key={`${pressKey}-${depth}-${v.stamp}`} kind={v.kind} text={v.stamp} sub={stampSub} press />
        </div>
      </section>

      <div className="depth" role="group" aria-labelledby="depth-label">
        <span id="depth-label" className="label">Show hidden steps</span>
        <div className="depth-steps">
          {Array.from({ length: maxDepth }, (_, i) => i + 1).map(d => (
            <button key={d} type="button" aria-pressed={d === depth} onClick={() => setDepth(d)} data-testid={`depth-${d}`}
              aria-label={`Depth ${d}${d === 1 ? ', direct documents only' : ''}`}>{d}</button>
          ))}
        </div>
        <button type="button" className="btn ghost small" disabled={depth >= maxDepth} onClick={() => setDepth(Math.min(maxDepth, depth + 1))} data-testid="depth-next">One step deeper</button>
        <span className={`hint ${plan.hidden_more ? 'more' : ''}`} data-testid="depth-hint">
          {depth === 1 ? 'Depth 1 shows only the documents the scholarship asks for directly.' : `Depth ${depth} also shows documents you need to get those documents.`}
          {plan.hidden_more ? ` More steps are hidden below this depth.` : ' Nothing is hidden below this depth.'}
        </span>
      </div>

      <Timeline plan={plan} onOpen={openWhy} />

      {heldItems.length > 0 && (
        <div className="held-row" aria-label="Documents you already hold">
          <span className="muted">Already held:</span>
          {heldItems.map(h => <span key={h.id} className="chip held" title={h.name}>{shortName(h.name)}</span>)}
        </div>
      )}

      {plan.conditional.length > 0 && (
        <section className="conditional" aria-labelledby="cond-h" data-testid="conditional">
          <h2 id="cond-h" style={{ fontSize: '1.1rem', margin: '24px 0 4px' }}>Only if it applies to you</h2>
          <p className="note" style={{ marginBottom: 8 }}>The sources say these are needed only in some cases. Kaagaz leaves them out of your chain unless you say they apply to you.</p>
          <ul className="opts">
            {[...new Map(plan.conditional.map(c => [c.doc_id, c])).values()].map(c => (
              <li key={c.doc_id}>
                <div>
                  <div className="name">{shortName(c.name)}</div>
                  <div className="sub">Only if: {c.condition}{c.held ? ' · you hold this' : ''}</div>
                </div>
                <button type="button" className="toggle" aria-pressed={c.applies} disabled={pending.has(`applies:${c.doc_id}`)}
                  onClick={() => toggleApplies(c.doc_id, c.applies)} data-testid={`applies-${c.doc_id}`}>
                  <span className="box" aria-hidden="true" /> This applies to me
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      <hr className="hair" />

      <div className="grid2">
        <section aria-labelledby="today-h">
          <div className="section-head">
            <h2 id="today-h">Start today</h2>
            <p>Things you can apply for now, in order. The first ones shorten your critical path the most.</p>
          </div>
          {plan.start_today.length === 0 && <p className="note">Nothing can be started at this depth. Every document left needs another one first, or you hold everything.</p>}
          <ol className="todo" data-testid="start-today">
            {plan.start_today.map(s => {
              const it = itemsById[s.id] as PlanItem | undefined
              const src = it?.days_source ?? it?.rule
              const group = plan.items.find(a => a.label === 'AnyOf' && a.chosen === s.id)
              const others = group?.options?.filter(o => o !== s.id).map(o => shortName(itemsById[o]?.name ?? o))
              return (
                <li key={s.id} data-testid={`todo-${s.id}`}>
                  <div>
                    <div className="doc" title={s.name}>{shortName(s.name)}</div>
                    <div className="sub">
                      <span>{s.office_name ?? 'Issuing office not in the sources'}</span>
                      <span className="days">{s.days ? `${legalTime(s.days, s.days_unit, plan.day_unit, s.span)} by law` : 'No official time limit found'}</span>
                      {s.on_critical && <span className="tag late">critical path</span>}
                      {s.reduction > 0 && <span>Cuts {fmtDays(s.reduction, plan.day_unit)} off your chain</span>}
                    </div>
                    {others && others.length > 0 && <div className="sub">Or any one of: {others.join(', ')}</div>}
                    <div className="path" aria-label="Why: path through the graph">
                      {s.path.map((pid, i) => (
                        <span key={pid + i} style={{ display: 'contents' }}>
                          {i > 0 && <span className="arrow" aria-hidden="true">→</span>}
                          <span className="hop">{pid === plan.scheme.id ? ui.target[0].toUpperCase() + ui.target.slice(1) : shortName(itemsById[pid]?.name ?? pid)}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                  <div className="right">
                    <button type="button" className="toggle" aria-pressed={false} disabled={pending.has(s.id)} onClick={() => toggleHeld(s.id, false)} data-testid={`have-${s.id}`}>
                      <span className="box" aria-hidden="true" /> I have this
                    </button>
                    <button type="button" className="btn ghost small" onClick={e => openWhy(s.id, e.currentTarget)}>Why?</button>
                    {src?.source_url && <a href={src.source_url} target="_blank" rel="noreferrer" className="note">Source: {hostOf(src.source_url)}</a>}
                  </div>
                </li>
              )
            })}
          </ol>
          {needed.length > plan.start_today.length && (
            <p className="note" style={{ marginTop: 12 }}>{plural(needed.length - plan.start_today.length, 'more document waits', 'more documents wait')} for one of these first. Click any slip in the chain to see why it is there.</p>
          )}
        </section>

        <section aria-labelledby="alt-h">
          <div className="section-head">
            <h2 id="alt-h">Other options</h2>
            <p>Other {ui.targets}, ranked by whether you can still make them with the documents you hold. Kaagaz does not check eligibility, so check that on the official portal.</p>
          </div>
          {!alts && <Loading label="Comparing other schemes" />}
          {alts && (
            <ul className="opts" data-testid="alternatives">
              {alts.data.options.slice(0, 8).map(o => {
                const k = o.verdict.kind
                const cls = k === 'on_time' ? 'ok' : k === 'late' || k === 'late_at_least' ? 'late' : k === 'closed' ? 'closed' : 'blue'
                return (
                  <li key={o.scheme_id}>
                    <div>
                      <div className="name">{o.name}</div>
                      <div className="sub">
                        {o.deadline.date ? `Deadline ${fmtDate(o.deadline.date)}` : 'No deadline published'}
                        {o.shared_count > 0 ? ` · reuses ${plural(o.shared_count, 'document', 'documents')} you still need` : ''}
                      </div>
                    </div>
                    <span className={`mini-stamp ${cls}`}>{o.verdict.stamp}</span>
                  </li>
                )
              })}
            </ul>
          )}
        </section>
      </div>

      <hr className="hair" />
      <details>
        <summary style={{ cursor: 'pointer' }}><span className="eyebrow">How this was computed</span></summary>
        <div style={{ marginTop: 16, display: 'grid', gap: 16 }}>
          {memoryNote && <p className="note" data-testid="memory-note">{memoryNote}</p>}
          <p className="note">Graph check: <code>chain_days.cypher</code> found a longest all-of chain of {plan.chain_check.chain_days_cypher} days and the planner found {plan.chain_check.planner_all_of}. {plan.chain_check.agree ? 'They agree.' : 'They disagree, which is a bug.'}</p>
          <TraceTable rows={cache[depth]?.trace ?? []} />
        </div>
      </details>

      {why && <WhyPanel key={why} schemeId={plan.scheme.id} item={itemsById[why]} plan={plan} onClose={closeWhy}
        onToggle={(id, has) => toggleHeld(id, has)} pending={pending.has(why)} />}
    </div>
  )
}
