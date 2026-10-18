import { useCallback, useEffect, useState } from 'react'
import { api, ApiError, getAsOf, type Alert, type CaseReview, type CaseStep, type Proposal, type Since, type StoredReview, type Task } from '../api'
import { fmtDate, plural } from '../format'

const TOOL_LABEL: Record<string, string> = {
  recall: 'recall', plan: 'plan', explain: 'explain', alternatives: 'alternatives', decide: 'decide', propose: 'propose',
}

interface View { steps: CaseStep[]; decision: { kind: string; text: string }; since: Since | null; at: string; today: string; asOf: boolean; note?: CaseReview['note'] }

function fromStored(r: StoredReview): View {
  return { steps: r.json.steps ?? [], decision: r.json.decision, since: r.json.since ?? null, at: r.at, today: r.today, asOf: !!r.json.as_of, note: r.json.note }
}

function SinceLine({ s, names }: { s: Since; names: Record<string, string> }) {
  const parts: string[] = []
  parts.push(s.working_days_passed > 0 ? `${plural(s.working_days_passed, 'working day has', 'working days have')} passed` : 'no working day has passed')
  if (s.stamp_before && s.stamp_before !== s.stamp_now) parts.push(`the stamp went from ${s.stamp_before} to ${s.stamp_now}`)
  else parts.push(`the stamp is still ${s.stamp_now}`)
  if (s.new_holdings.length) parts.push(`you now hold ${s.new_holdings.map(d => names[d] ?? d).join(', ')}`)
  if (s.dropped_holdings.length) parts.push(`you removed ${s.dropped_holdings.map(d => names[d] ?? d).join(', ')}`)
  if (s.scheme_changed) parts.push('the target scheme changed')
  return <p className="since" data-testid="case-since">Since my last review on {fmtDate(s.last_review)}: {parts.join('; ')}.</p>
}

export function AgentAlerts({ sid }: { sid: string }) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  useEffect(() => { api.caseState(sid).then(s => setAlerts(s.alerts)).catch(() => setAlerts([])) }, [sid])
  const unseen = alerts.filter(a => !a.seen)
  if (!unseen.length) return null
  return (
    <section className="alerts" role="status" data-testid="alerts" aria-labelledby="alerts-h">
      <h2 id="alerts-h">{plural(unseen.length, 'change from the agents', 'changes from the agents')}</h2>
      <ul>
        {unseen.map(a => <li key={a.id}><span className="eyebrow">{fmtDate(a.at)}</span> {a.message}</li>)}
      </ul>
      <button className="btn ghost small" type="button" onClick={async () => { await api.alertsSeen(sid); setAlerts(alerts.map(a => ({ ...a, seen: true }))) }}>Mark as read</button>
    </section>
  )
}

export default function Caseworker({ sid, schemeId, names, onChanged }: { sid: string; schemeId: string; names: Record<string, string>; onChanged: () => void }) {
  const [view, setView] = useState<View | null>(null)
  const [proposals, setProposals] = useState<Proposal[]>([])
  const [tasks, setTasks] = useState<Task[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const s = await api.caseState(sid)
      setProposals(s.proposals)
      setTasks(s.tasks)
      if (s.review) setView(v => v ?? fromStored(s.review as StoredReview))
    } catch { /* nothing saved yet */ }
  }, [sid])

  // oxlint-disable-next-line react/set-state-in-effect -- refresh sets state only after an awaited fetch
  useEffect(() => { refresh() }, [refresh])

  async function review() {
    setBusy('review'); setError(null); setResult(null)
    try {
      const r = await api.reviewCase(sid, schemeId)
      setView({ steps: r.steps, decision: r.decision, since: r.since, at: new Date().toISOString(), today: r.today, asOf: r.as_of, note: r.note })
      setProposals(r.proposals)
    } catch (e) { setError((e as ApiError).message) } finally { setBusy(null) }
  }

  async function decide(p: Proposal, approve: boolean) {
    setBusy(p.id); setError(null)
    try {
      const r = await api.decideProposal(sid, p.id, approve)
      setResult(approve ? `Done: ${p.title}.${r.plan_after ? ` Checked the plan again: ${r.plan_after.stamp}.` : ''}` : `Rejected: ${p.title}.`)
      await refresh()
      if (approve) onChanged()
    } catch (e) { setError((e as ApiError).message) } finally { setBusy(null) }
  }

  async function toggleTask(t: Task) {
    setBusy(t.id)
    try { await api.setTask(sid, t.id, t.status === 'done' ? 'open' : 'done'); await refresh() } finally { setBusy(null) }
  }

  const pending = proposals.filter(p => p.status === 'pending')
  const decided = proposals.filter(p => p.status === 'approved' || p.status === 'rejected').slice(0, 6)
  const openTasks = tasks.filter(t => t.status === 'open')

  return (
    <section className="case" aria-labelledby="case-h" data-testid="caseworker">
      <div className="section-head">
        <h2 id="case-h">Caseworker</h2>
        <p>An agent that reads your chain, checks other schemes when it needs to, decides what to do, and proposes it. Nothing is done until you approve it.</p>
      </div>
      <button className="btn" type="button" onClick={review} disabled={busy !== null} data-testid="case-review">
        {busy === 'review' ? 'Reviewing your case' : view ? 'Review my case again' : 'Review my case'}
      </button>
      {error && <p className="note late-text" role="alert" style={{ marginTop: 8 }}>{error}</p>}

      {view && (
        <div className="case-body">
          {view.asOf && <p className="note"><span className="tag blue">As on {fmtDate(view.today)}</span> This review counts from the submission day, not today.</p>}
          {view.since && <SinceLine s={view.since} names={names} />}
          <div className="decision" data-testid="case-decision">
            <span className="eyebrow">Decision, {fmtDate(view.at)}</span>
            <p>{view.decision.text}</p>
            {view.note?.text && <p className="note">Case note written by the model and checked against the data: {view.note.text}</p>}
          </div>
          <details className="case-steps" open>
            <summary>How the caseworker got there ({plural(view.steps.length, 'step', 'steps')})</summary>
            <ol data-testid="case-steps">
              {view.steps.map(s => (
                <li key={s.n}>
                  <span className="tool">{TOOL_LABEL[s.tool] ?? s.tool}</span>
                  <div><div>{s.why}</div><div className="note">{s.found}</div></div>
                </li>
              ))}
            </ol>
          </details>
        </div>
      )}

      {pending.length > 0 && (
        <>
          <h3 className="case-sub">Proposed, waiting for you</h3>
          <ul className="opts" data-testid="proposals">
            {pending.map(p => (
              <li key={p.id} data-testid={`proposal-${p.kind}`}>
                <div>
                  <div className="name">{p.title}</div>
                  <div className="sub">{p.due ? `By ${fmtDate(p.due)} · ` : ''}{p.reason}</div>
                </div>
                <div className="pair">
                  <button className="btn small" type="button" disabled={busy !== null} onClick={() => decide(p, true)} data-testid="proposal-approve">Approve</button>
                  <button className="btn ghost small" type="button" disabled={busy !== null} onClick={() => decide(p, false)}>Reject</button>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
      {result && <p className="note" role="status" style={{ marginTop: 8 }} data-testid="proposal-result">{result}</p>}

      {(tasks.length > 0 || decided.length > 0) && (
        <>
          <h3 className="case-sub">Your tasks</h3>
          {tasks.length === 0 && <p className="note">No tasks yet. Approve a proposal to add one.</p>}
          <ul className="tasks" data-testid="tasks">
            {tasks.map(t => (
              <li key={t.id} className={t.status}>
                <label>
                  <input type="checkbox" checked={t.status === 'done'} disabled={busy !== null} onChange={() => toggleTask(t)} />
                  <span>{t.title}</span>
                </label>
                {t.due && <span className="due">{fmtDate(t.due)}</span>}
              </li>
            ))}
          </ul>
          {openTasks.length > 0 && (
            <p style={{ marginTop: 8 }}><a href={`/api/students/${sid}/tasks.ics`} download data-testid="ics">Add {plural(openTasks.length, 'task', 'tasks')} to your calendar (.ics)</a>
              {getAsOf() ? <span className="note"> Due dates count from {fmtDate(getAsOf())}.</span> : null}</p>
          )}
        </>
      )}
    </section>
  )
}
