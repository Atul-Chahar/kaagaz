import { useEffect, useRef, useState } from 'react'
import { api, ApiError, type Plan, type PlanItem } from '../api'
import { fmtDate, fmtDays, hostOf, shortName } from '../format'
import { Cypher, Loading, OutcomeBadge, StateBox } from './common'

type Explain = Awaited<ReturnType<typeof api.explain>>

export default function WhyPanel({ schemeId, item, plan, onClose, onToggle, pending }: {
  schemeId: string; item: PlanItem | undefined; plan: Plan; onClose: () => void
  onToggle: (id: string, has: boolean) => void; pending: boolean
}) {
  const [res, setRes] = useState<Explain | null>(null)
  const [error, setError] = useState<string | null>(null)
  const head = useRef<HTMLHeadingElement>(null)
  const panel = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!item) return
    api.explain(schemeId, item.id).then(setRes).catch((e: ApiError) => setError(e.message))
  }, [schemeId, item])

  useEffect(() => {
    head.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && panel.current) {
        const f = panel.current.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])')
        if (!f.length) return
        const first = f[0], last = f[f.length - 1]
        if (e.shiftKey && document.activeElement === first) { last.focus(); e.preventDefault() }
        else if (!e.shiftKey && document.activeElement === last) { first.focus(); e.preventDefault() }
      }
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  if (!item) return null
  const path = res?.data.paths[0]
  const days = item.days
  const ds = item.days_source
  const issues = res?.data.detail?.issues
  const crit = new Set(plan.critical_path)

  return (
    <>
      <div className="scrim" onClick={onClose} aria-hidden="true" />
      <div className="why" role="dialog" aria-modal="true" aria-labelledby="why-title" ref={panel} data-testid="why-panel">
        <div className="why-head">
          <div>
            <p className="eyebrow">Why this is in your chain</p>
            <h2 id="why-title" tabIndex={-1} ref={head} style={{ outline: 'none' }}>{shortName(item.name)}</h2>
            {shortName(item.name) !== item.name && <p className="note" style={{ marginTop: 4 }}>{item.name}</p>}
          </div>
          <button type="button" className="close" onClick={onClose} aria-label="Close the why panel">Close</button>
        </div>

        <dl className="kv">
          <dt>Legal time</dt>
          <dd className="days">{days !== null ? `${fmtDays(days, plan.day_unit)}` : <span className="tag blue">No official time limit found</span>}</dd>
          <dt>Issued by</dt>
          <dd>{item.office_name ?? 'Not stated in the saved sources'}</dd>
          <dt>Status</dt>
          <dd>{item.held ? <span className="tag ok">You hold this</span> : item.on_critical ? <span className="tag late">On the critical path</span> : 'Still needed'}</dd>
        </dl>
        <button type="button" className="toggle" aria-pressed={item.held} disabled={pending} onClick={() => onToggle(item.id, item.held)} data-testid="why-have">
          <span className="box" aria-hidden="true" /> I have this
        </button>

        {error && <div style={{ marginTop: 16 }}><StateBox title="Couldn't load the path" error><p>{error}</p></StateBox></div>}
        {!res && !error && <Loading label="Asking the graph for the path" />}
        {res && (
          <>
            <div style={{ marginTop: 24 }}><OutcomeBadge outcome={res.outcome} /></div>
            {path && (
              <div className="path" style={{ marginTop: 8, fontSize: '0.88rem' }} data-testid="why-chips">
                {path.nodes.map((n, i) => (
                  <span key={n.id + i} style={{ display: 'contents' }}>
                    {i > 0 && <span className="arrow" aria-hidden="true">→</span>}
                    <span className="hop">{n.label === 'AnyOf' ? `One of: ${n.name}` : n.label === 'Scheme' ? 'Scholarship' : shortName(n.name)}</span>
                  </span>
                ))}
              </div>
            )}
            <h3 style={{ marginTop: 24 }}>Each step and its source</h3>
            <ol className="hops">
              {path?.rules.map((r, i) => (
                <li key={i} className={crit.has(path.nodes[i + 1].id) && crit.has(path.nodes[i].id) ? 'crit' : ''}>
                  <div className="from-to">{path.nodes[i].name} {path.types[i] === 'OPTION' ? 'can use' : 'needs'} {path.nodes[i + 1].name}</div>
                  {r.condition && <div className="note">Only if: {r.condition}</div>}
                  <blockquote>"{r.excerpt}"</blockquote>
                  <div className="src">
                    <a href={r.source_url} target="_blank" rel="noreferrer" data-testid="why-source">{r.source_title}</a>
                    <span>{hostOf(r.source_url)}</span>
                    <span>Retrieved {fmtDate(r.retrieved_at)}</span>
                    {r.confidence === 'secondary' ? <span className="tag secondary">Secondary source</span> : <span className="tag">Official</span>}
                  </div>
                </li>
              ))}
              {ds && (
                <li>
                  <div className="from-to">Legal time for {item.name}: {fmtDays(days, plan.day_unit)}</div>
                  <blockquote>"{ds.excerpt}"</blockquote>
                  <div className="src">
                    <a href={ds.source_url} target="_blank" rel="noreferrer">{ds.source_title}</a>
                    <span>Retrieved {fmtDate(ds.retrieved_at)}</span>
                    {ds.confidence === 'secondary' ? <span className="tag secondary">Secondary source</span> : <span className="tag">Official</span>}
                  </div>
                </li>
              )}
              {issues?.excerpt && (
                <li>
                  <div className="from-to">Issued by {res.data.detail.office_name}</div>
                  <blockquote>"{issues.excerpt}"</blockquote>
                  <div className="src">
                    <a href={issues.source_url} target="_blank" rel="noreferrer">{issues.source_title}</a>
                    <span>Retrieved {fmtDate(issues.retrieved_at)}</span>
                    {issues.confidence === 'secondary' ? <span className="tag secondary">Secondary source</span> : <span className="tag">Official</span>}
                  </div>
                </li>
              )}
            </ol>
            {item.note && <p className="note">Note from the sources: {item.note}</p>}
            <h3 style={{ marginTop: 24, marginBottom: 8 }}>The Cypher that found this</h3>
            <Cypher label="explain.cypher" text={`// params: {scheme_id: "${schemeId}", doc_id: "${item.id}"}\n${res.cypher?.explain ?? ''}`} />
            <p style={{ marginTop: 12 }}>
              <a href={res.browser_url} target="_blank" rel="noreferrer">Open in FalkorDB Browser</a>
              <span className="note"> · graph <code>{res.rules_graph}</code></span>
            </p>
          </>
        )}
      </div>
    </>
  )
}
