import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, type Scheme } from '../api'
import { Loading, StateBox } from '../components/common'
import { fmtDays } from '../format'
import { go, type Session } from '../nav'
import { windowLine } from '../labels'

interface Doc { id: string; name: string; days: number | null; office_name: string | null; group: string }

export default function Start({ session, setSession }: { session: Session | null; setSession: (s: Session | null) => void }) {
  const [schemes, setSchemes] = useState<Scheme[] | null>(null)
  const [docs, setDocs] = useState<Doc[]>([])
  const [groups, setGroups] = useState<string[]>([])
  const [error, setError] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [picked, setPicked] = useState<string | null>(session && !session.example ? session.scheme_id ?? null : null)
  const [treeState, setTreeState] = useState<{ scheme: string; ids: Set<string> } | null>(null)
  const tree = treeState && treeState.scheme === picked ? treeState.ids : null
  const [held, setHeld] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([api.schemes(), api.documents()])
      .then(([s, d]) => { setSchemes(s.schemes); setDocs(d.documents); setGroups(d.groups) })
      .catch((e: ApiError) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!session || session.example) return
    api.recall(session.id).then(r => {
      if (r.data.holdings) setHeld(new Set(r.data.holdings.map(h => h.doc_id)))
    }).catch(() => { /* new student: nothing remembered yet */ })
  }, [session])

  useEffect(() => {
    if (!picked) return
    let live = true
    api.prerequisites(picked, 8).then(r => {
      if (live) setTreeState({ scheme: picked, ids: new Set(r.data.nodes.filter(n => n.label === 'Document').map(n => n.id)) })
    }).catch((e: ApiError) => setError(e.message))
    return () => { live = false }
  }, [picked])

  const shown = useMemo(() => {
    const words = q.toLowerCase().split(/\s+/).filter(Boolean)
    return (schemes ?? []).filter(s => words.every(w => `${s.name} ${s.authority ?? ''} ${s.portal ?? ''}`.toLowerCase().includes(w)))
  }, [schemes, q])

  const pickedScheme = schemes?.find(s => s.id === picked) ?? null

  async function loadExample() {
    setBusy(true)
    try {
      const ex = await api.example()
      setSession({ id: ex.student_id, scheme_id: ex.scheme_id, example: true })
      go('/chain')
    } catch (e) {
      setError((e as ApiError).message)
    } finally { setBusy(false) }
  }

  async function goPlan() {
    if (!picked) return
    setBusy(true)
    try {
      let id = session && !session.example ? session.id : null
      if (!id) id = (await api.newStudent()).id
      await api.setTarget(id, picked)
      const before = new Set<string>()
      try {
        const r = await api.recall(id)
        r.data.holdings?.forEach(h => before.add(h.doc_id))
      } catch { /* none */ }
      for (const d of held) if (!before.has(d)) await api.addHolding(id, d)
      for (const d of before) if (!held.has(d)) await api.removeHolding(id, d)
      setSession({ id, scheme_id: picked })
      go('/chain')
    } catch (e) {
      setError((e as ApiError).message)
    } finally { setBusy(false) }
  }

  const treeDocs = docs.filter(d => tree?.has(d.id))

  return (
    <div>
      <section className="start-head">
        <div>
          <p className="eyebrow">Scholarship paperwork, laid out</p>
          <h1>Are you already too late?</h1>
          <p className="promise">Every scheme finder tells you what you are eligible for. Kaagaz tells you <em>whether you are already too late</em>, and which certificate to apply for today.</p>
        </div>
        <div className="example-card">
          <h2 style={{ fontSize: '1.15rem' }}>See it with the Example student</h2>
          <p>A made-up student profile (not a real person) applying for a Karnataka scholarship. It shows the hidden certificate chain and the verdict in one click.</p>
          <button className="btn" type="button" onClick={loadExample} disabled={busy} data-testid="load-example">Load the Example student</button>
        </div>
      </section>

      {error && <div style={{ marginTop: 24 }}><StateBox title="Something went wrong" error>{error.includes('docker') ? <p>{error}</p> : <p>{error}</p>}</StateBox></div>}

      <div className="steps">
        <section className="step" aria-labelledby="step1">
          <span className="step-n">Step 1 of 3</span>
          <h2 id="step1">Pick a scholarship</h2>
          <label htmlFor="scheme-search" className="sr-only">Search scholarships</label>
          <input id="scheme-search" type="search" placeholder="Search by name, department or portal" value={q} onChange={e => setQ(e.target.value)} />
          {!schemes && !error && <Loading label="Reading scholarships from the graph" />}
          {schemes && shown.length === 0 && <p className="note" style={{ marginTop: 12 }}>No scholarship in this rule pack matches "{q}".</p>}
          <ul className="scheme-list" role="radiogroup" aria-labelledby="step1">
            {shown.map(s => {
              const w = windowLine(s)
              return (
                <li key={s.id}>
                  <label className="scheme-opt">
                    <input type="radio" name="scheme" value={s.id} checked={picked === s.id} onChange={() => setPicked(s.id)} />
                    <span>
                      <span className="name">{s.name}</span><br />
                      <span className="meta">{s.authority}{s.portal ? ` · ${s.portal}` : ''}</span>
                    </span>
                    <span className="when">
                      <span className={w.cls === 'late' ? 'tag late' : w.cls === 'muted' ? 'muted' : ''}>{w.text}</span>
                      {s.window_end && (s.days_left ?? -1) >= 0 && <><br /><span className="muted">{fmtDays(s.days_left ?? 0)} left</span></>}
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>
        </section>

        <section className="step" aria-labelledby="step2">
          <span className="step-n">Step 2 of 3</span>
          <h2 id="step2">Tick what you already hold</h2>
          {!picked && <p className="note">Pick a scholarship first. Then you will see every document it needs, including the documents you need to get those documents.</p>}
          {picked && !tree && <Loading label="Walking the requirement graph" />}
          {picked && tree && (
            <div>
              <p className="note" style={{ marginBottom: 16 }}>{treeDocs.length} documents appear somewhere in the chain for {pickedScheme?.name}.</p>
              {groups.map(g => {
                const list = treeDocs.filter(d => d.group === g)
                if (!list.length) return null
                return (
                  <fieldset key={g} className="hold-group" style={{ border: 0, padding: 0, margin: '0 0 24px' }}>
                    <legend className="eyebrow" style={{ marginBottom: 4 }}>{g}</legend>
                    {list.map(d => (
                      <label key={d.id} className="hold">
                        <input type="checkbox" checked={held.has(d.id)} onChange={e => {
                          const n = new Set(held)
                          if (e.target.checked) n.add(d.id); else n.delete(d.id)
                          setHeld(n)
                        }} />
                        <span>{d.name}</span>
                        <span className="days">{d.days ? fmtDays(d.days, 'working days') : ''}</span>
                      </label>
                    ))}
                  </fieldset>
                )
              })}
            </div>
          )}
        </section>

        <aside className="go-box" aria-labelledby="step3">
          <span className="step-n">Step 3 of 3</span>
          <h2 id="step3" style={{ fontSize: '1.3rem' }}>Go</h2>
          <p>{picked ? `${held.size} document${held.size === 1 ? '' : 's'} ticked. Kaagaz remembers this for your next visit.` : 'Pick a scholarship to continue.'}</p>
          <button className="btn" type="button" disabled={!picked || busy} onClick={goPlan} data-testid="go">Show my chain</button>
        </aside>
      </div>
    </div>
  )
}
