import { useEffect, useMemo, useState } from 'react'
import { api, ApiError, getPack, setPack, type PackInfo, type Scheme } from '../api'
import { Loading, StateBox } from '../components/common'
import { fmtDays, legalTime } from '../format'
import { go, type Session } from '../nav'
import { windowLine } from '../labels'

interface Doc { id: string; name: string; days: number | null; days_unit?: string | null; office_name: string | null; group: string }

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
  const [ownDate, setOwnDate] = useState('')
  const [packs, setPacks] = useState<PackInfo[]>([])
  const [pack, setPackState] = useState<string | null>(getPack())
  const ui = packs.find(p => p.id === (pack ?? packs[0]?.id))?.ui ?? {}
  const target = ui.target ?? 'scholarship'

  useEffect(() => { api.packs().then(setPacks).catch(() => setPacks([])) }, [])

  useEffect(() => {
    Promise.all([api.schemes(), api.documents()])
      .then(([s, d]) => { setSchemes(s.schemes); setDocs(d.documents); setGroups(d.groups) })
      .catch((e: ApiError) => setError(e.message))
  }, [pack])

  function switchPack(id: string) {
    setPack(id)
    setPackState(id)
    setPicked(null)
    setHeld(new Set())
    setSchemes(null)
  }

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
      const ex = await api.example(session?.example ? session.id : undefined)
      setSession({ id: ex.student_id, scheme_id: ex.scheme_id, example: true, pack: getPack() ?? undefined, label: ex.label })
      go('/chain')
    } catch (e) {
      setError((e as ApiError).message)
    } finally { setBusy(false) }
  }

  async function goPlan() {
    if (!picked) return
    setBusy(true)
    try {
      let id = session && !session.example && (session.pack ?? null) === getPack() ? session.id : null
      if (!id) id = (await api.newStudent()).id
      await api.setTarget(id, picked, ownDate || undefined)
      const before = new Set<string>()
      try {
        const r = await api.recall(id)
        r.data.holdings?.forEach(h => before.add(h.doc_id))
      } catch { /* none */ }
      for (const d of held) if (!before.has(d)) await api.addHolding(id, d)
      for (const d of before) if (!held.has(d)) await api.removeHolding(id, d)
      setSession({ id, scheme_id: picked, pack: getPack() ?? undefined })
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
          <h2 style={{ fontSize: '1.15rem' }}>See it with the {ui.example_label ?? 'Example student'}</h2>
          <p>{ui.example ?? 'A made-up student profile (not a real person) applying for a Karnataka scholarship. It shows the hidden certificate chain and the verdict in one click.'}</p>
          <button className="btn" type="button" onClick={loadExample} disabled={busy} data-testid="load-example">Load the {ui.example_label ?? 'Example student'}</button>
        </div>
      </section>

      {error && <div style={{ marginTop: 24 }}><StateBox title="Something went wrong" error>{error.includes('docker') ? <p>{error}</p> : <p>{error}</p>}</StateBox></div>}

      {packs.length > 1 && (
        <div className="depth" role="group" aria-label="Rule pack" style={{ marginTop: 24 }}>
          <span className="label">Rule pack</span>
          <div className="depth-steps">
            {packs.map(p => (
              <button key={p.id} type="button" style={{ padding: '0 14px', fontFamily: 'var(--font-body)' }}
                aria-pressed={(pack ?? packs[0].id) === p.id} onClick={() => switchPack(p.id)} data-testid={`pack-${p.id}`}>{p.name}</button>
            ))}
          </div>
          <span className="hint">The engine is the same; only the rules change.</span>
        </div>
      )}

      <div className="steps">
        <section className="step" aria-labelledby="step1">
          <span className="step-n">Step 1 of 3</span>
          <h2 id="step1">Pick a {target}</h2>
          <label htmlFor="scheme-search" className="sr-only">Search {target}s</label>
          <input id="scheme-search" type="search" placeholder={`Search ${target}s by name`} value={q} onChange={e => setQ(e.target.value)} />
          {!schemes && !error && <Loading label={`Reading ${target}s from the graph`} />}
          {schemes && shown.length === 0 && <p className="note" style={{ marginTop: 12 }}>No {target} in this rule pack matches "{q}".</p>}
          <ul className="scheme-list" aria-label="Scholarships in this rule pack">
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
                      <span className={w.cls === 'soon' ? 'tag blue' : w.cls === 'muted' ? 'muted' : ''}>{w.text}</span>
                      {s.window_end && (s.days_left ?? -1) >= 0 && <><br /><span className="muted">{fmtDays(s.days_left ?? 0, s.day_unit)} left</span></>}
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
          {!picked && <p className="note">Pick a {target} first. Then you will see every document it needs, including the documents you need to get those documents.</p>}
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
                        <span className="days">{d.days ? legalTime(d.days, d.days_unit, 'working days') : ''}</span>
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
          <p>{picked ? `${held.size} document${held.size === 1 ? '' : 's'} ticked. Kaagaz remembers this for your next visit.` : `Pick a ${target} to continue.`}</p>
          <label htmlFor="own-date" style={{ display: 'block', fontSize: '0.9rem', margin: '0 0 6px' }}>
            Your own deadline <span className="muted">({pickedScheme?.window_end ? 'optional; the published one is used if empty' : 'no deadline is published for this one'})</span>
          </label>
          <input id="own-date" type="date" value={ownDate} onChange={e => setOwnDate(e.target.value)} style={{ marginBottom: 16 }} />
          <button className="btn" type="button" disabled={!picked || busy} onClick={goPlan} data-testid="go">Show my chain</button>
        </aside>
      </div>
    </div>
  )
}
