import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, type AgentInfo, type AgentRun, type Finding, type SourceCheck } from '../api'
import { Loading, StateBox } from '../components/common'
import { fmtDate, hostOf, plural } from '../format'

const KIND: Record<Finding['kind'], { label: string; cls: string; what: string }> = {
  date_changed: { label: 'Date changed', cls: 'late', what: 'Approving changes the last date in the graph and re-plans every student who targets the scheme.' },
  wording_changed: { label: 'Reworded', cls: 'blue', what: 'Approving makes the rule cite the new sentence. The rule itself does not change.' },
  value_changed: { label: 'Number changed', cls: 'late', what: 'Approving marks the rule for review. A person has to update the rule pack; Kaagaz does not change a legal time on its own.' },
  excerpt_missing: { label: 'Sentence gone', cls: 'blue', what: 'Approving keeps the rule but marks it for review, and tells every student it affects.' },
}

const STATUS_LABEL: Record<string, string> = {
  same_text: 'same text', text_changed: 'text changed', unreachable: 'unreachable', http_error: 'error from site',
  robots_disallowed: 'robots.txt says no', no_text: 'no text', archived_copy: 'archived copy (never changes)', skipped_large: 'skipped (over 5 MB)',
}

function when(iso?: string | null): string {
  if (!iso) return ''
  const d = new Date(iso)
  return `${fmtDate(iso)}, ${d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })} IST`
}

function FindingCard({ f, onDecide, busy }: { f: Finding; onDecide: (f: Finding, approve: boolean, note: string) => void; busy: boolean }) {
  const [note, setNote] = useState('')
  const k = KIND[f.kind]
  return (
    <li className={`finding ${f.status}`} data-testid="finding">
      <div className="finding-head">
        <span className={`tag ${k.cls}`}>{k.label}</span>
        <span className="tag">{f.status}</span>
        <span className="note">{plural(f.rule_count, 'rule', 'rules')} · {plural(f.schemes.length, 'scheme', 'schemes')} · {plural(f.students, 'student targets', 'students target')} them</span>
      </div>
      <p className="src"><a href={f.source_url} target="_blank" rel="noreferrer">{f.source_title}</a> <span className="note">{hostOf(f.source_url)} · checked {fmtDate(f.checked_on)}{f.seen_count > 1 ? ` · seen in ${f.seen_count} runs` : ''}</span></p>
      <div className="diff">
        <div><span className="eyebrow">Saved sentence</span><blockquote>{f.old_excerpt}</blockquote></div>
        <div><span className="eyebrow">Closest on the page now</span>
          <blockquote className={f.new_excerpt ? '' : 'none'}>{f.kind === 'excerpt_missing' ? (f.new_excerpt ? `No close match. Nearest words: "${f.new_excerpt}"` : 'No close match') : f.new_excerpt}</blockquote>
          {f.score !== undefined && <span className="note">Similarity {Math.round((f.score ?? 0) * 100)}% (numbers masked)</span>}
        </div>
      </div>
      {f.new_value && <p><b>{f.old_value} → {f.new_value}</b></p>}
      {f.note && <p className="note warn">{f.note}</p>}
      <details><summary>Rules it covers</summary><p className="mono">{f.rule_keys.join(', ')}</p></details>
      {f.status === 'open' ? (
        <div className="decide">
          <p className="note">{k.what}</p>
          <label className="sr-only" htmlFor={`note-${f.id}`}>Note for this decision</label>
          <input id={`note-${f.id}`} type="text" placeholder="Note (optional): why you decided" value={note} maxLength={300} onChange={e => setNote(e.target.value)} />
          <div className="pair">
            <button className="btn small" type="button" disabled={busy} onClick={() => onDecide(f, true, note)} data-testid="finding-approve">Approve</button>
            <button className="btn ghost small" type="button" disabled={busy} onClick={() => onDecide(f, false, note)} data-testid="finding-reject">Reject</button>
          </div>
        </div>
      ) : (
        <p className="note">{f.status === 'approved' ? 'Approved' : 'Rejected'} {fmtDate(f.decided_at)}{f.decided_note ? `: ${f.decided_note}` : ''}</p>
      )}
    </li>
  )
}

export default function Agents() {
  const [data, setData] = useState<Awaited<ReturnType<typeof api.agents>> | null>(null)
  const [checks, setChecks] = useState<SourceCheck[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const d = await api.agents()
      setData(d)
      const last = d.runs.find(r => r.agent === 'watcher')
      if (last) setChecks((await api.agentRun(last.id)).checks)
      setError(null)
    } catch (e) { setError((e as ApiError).message) }
  }, [])

  // oxlint-disable-next-line react/set-state-in-effect -- load sets state only after an awaited fetch
  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (!data?.running) return
    const id = window.setInterval(load, 3000)
    return () => window.clearInterval(id)
  }, [data?.running, load])

  async function runWatcher() {
    setBusy(true); setMsg(null)
    try { await api.startWatch(); setMsg('The watcher is fetching the sources, one request per second per site.'); await load() }
    catch (e) { setMsg((e as ApiError).message) } finally { setBusy(false) }
  }

  async function decide(f: Finding, approve: boolean, note: string) {
    setBusy(true); setMsg(null)
    try {
      const r = await api.decideFinding(f.id, approve, note)
      const n = r.propagation?.notified.length ?? 0
      setMsg(approve ? `Approved. The rules graph was rebuilt with the change and the caseworker re-planned ${plural(n, 'student', 'students')}.` : 'Rejected. Nothing in the rules changed.')
      await load()
    } catch (e) { setMsg((e as ApiError).message) } finally { setBusy(false) }
  }

  if (error) return <StateBox title="The agents graph could not be read" error><p>{error}</p></StateBox>
  if (!data) return <Loading label="Reading the agents graph in FalkorDB" />

  const watch = data.runs.find(r => r.agent === 'watcher')
  const open = data.findings.filter(f => f.status === 'open')
  const done = data.findings.filter(f => f.status !== 'open')
  const s = (watch?.summary ?? {}) as Record<string, number>

  return (
    <div>
      <p className="eyebrow">Agents</p>
      <h1>Three agents, one shared graph</h1>
      <p className="lede">Government pages change. The watcher re-checks every rule's proof sentence on the live page, you decide what it found, and the caseworker tells every student the change affects. They coordinate through one FalkorDB graph, <code>{data.graph}</code>.</p>

      <ol className="agent-flow" data-testid="agent-flow">
        {(['watcher', 'reviewer', 'caseworker'] as const).map(id => {
          const a = data.agents.find(x => x.id === id) as AgentInfo | undefined
          return (
            <li key={id}>
              <span className="eyebrow">{id === 'reviewer' ? 'You' : 'Agent'}</span>
              <b>{a?.name ?? id}</b>
              <span className="note">{a?.role}</span>
              <span className="mono note">{id === 'reviewer' ? plural(a?.decisions ?? 0, 'decision', 'decisions') : plural(a?.runs ?? 0, 'run', 'runs')}{a?.last_run ? `, last ${when(a.last_run)}` : ''}</span>
            </li>
          )
        })}
      </ol>

      <section aria-labelledby="watch-h" className="block">
        <div className="section-head">
          <h2 id="watch-h">Watcher</h2>
          <p>Fetches each saved source again (robots.txt respected, one request per second per site) and looks for every rule's exact sentence on the page.</p>
        </div>
        <button className="btn" type="button" onClick={runWatcher} disabled={busy || data.running} data-testid="watch-run">{data.running ? 'Watcher is running' : 'Run the watcher now'}</button>
        {msg && <p className="note" role="status" style={{ marginTop: 8 }} data-testid="agents-msg">{msg}</p>}
        {!watch && <StateBox title="The watcher has not run yet"><p>Press the button, or run <code>uv run python -m kaagaz.watcher</code>. Until then there is nothing to show.</p></StateBox>}
        {watch && (
          <div className="run-summary" data-testid="watch-summary">
            <p><b>{watch.status === 'running' ? 'Running since' : 'Last run'} {when(watch.started_at)}</b>{watch.trigger ? <span className="note"> · started from {watch.trigger}</span> : null}</p>
            {watch.status === 'done' && (
              <p>{plural(s.sources ?? 0, 'source', 'sources')} and {plural(s.rules ?? 0, 'rule', 'rules')} checked: {s.same_text ?? 0} with the same text, {s.text_changed ?? 0} changed{s.unreachable ? `, ${s.unreachable} unreachable` : ''}{s.http_error ? `, ${s.http_error} returned an error` : ''}{s.skipped_large ? `, ${s.skipped_large} skipped (over 5 MB)` : ''}. {plural(s.findings ?? 0, 'finding', 'findings')}.</p>
            )}
            {watch.status === 'failed' && <p className="late-text">The run failed: {String(watch.summary?.error ?? 'unknown error')}</p>}
            {checks && checks.length > 0 && (
              <details>
                <summary>Every source in this run</summary>
                <div className="table-wrap">
                  <table className="trace">
                    <caption className="sr-only">Sources the watcher checked</caption>
                    <thead><tr><th scope="col">Source</th><th scope="col">Result</th><th scope="col">Rules</th><th scope="col">Sentence not found</th></tr></thead>
                    <tbody>
                      {checks.map(c => (
                        <tr key={c.source_id}>
                          <td><a href={c.url} target="_blank" rel="noreferrer">{c.title}</a></td>
                          <td>{STATUS_LABEL[c.status] ?? c.status}{c.tls_verified === false ? ' (TLS not verified)' : ''}{c.warning ? ' · most rules missing' : ''}</td>
                          <td>{c.rules_checked}</td>
                          <td>{c.rules_missing}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            )}
          </div>
        )}
      </section>

      <section aria-labelledby="find-h" className="block">
        <div className="section-head">
          <h2 id="find-h">Waiting for you</h2>
          <p>Nothing in the rules changes until a person approves a finding. Each one shows the saved sentence next to what the page says now.</p>
        </div>
        {open.length === 0 && <StateBox title="Nothing waiting" testid="no-findings"><p>{watch ? 'Every proof sentence the watcher could check is still on its page, or every finding has been decided.' : 'Run the watcher first.'}</p></StateBox>}
        <ul className="findings">{open.map(f => <FindingCard key={f.id} f={f} onDecide={decide} busy={busy} />)}</ul>
      </section>

      {done.length > 0 && (
        <section aria-labelledby="done-h" className="block">
          <div className="section-head"><h2 id="done-h">Decided</h2></div>
          <ul className="findings">{done.map(f => <FindingCard key={f.id} f={f} onDecide={decide} busy={busy} />)}</ul>
        </section>
      )}

      <section aria-labelledby="runs-h" className="block">
        <div className="section-head"><h2 id="runs-h">Recent runs</h2><p>Each run is a node in the agents graph, linked to the agent that ran it and to what it found.</p></div>
        {data.runs.length === 0 ? <p className="note">No runs yet.</p> : (
          <ul className="opts">
            {data.runs.slice(0, 8).map((r: AgentRun) => (
              <li key={r.id}><div><div className="name">{r.agent} · {r.status}</div><div className="sub">{when(r.started_at)} · {r.trigger}</div></div>
                <span className="mono note">{r.summary ? Object.entries(r.summary).filter(([k]) => k !== 'error').map(([k, v]) => `${k.replace(/_/g, ' ')} ${v}`).slice(0, 3).join(' · ') : ''}</span></li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
