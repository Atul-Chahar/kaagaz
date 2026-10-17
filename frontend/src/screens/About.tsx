import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { Cypher, Loading, StateBox } from '../components/common'
import type { Session } from '../nav'

type Q = Awaited<ReturnType<typeof api.queries>>[number]
type LB = Awaited<ReturnType<typeof api.loadBearing>>
type Stats = Awaited<ReturnType<typeof api.graphStats>>

function ModelDiagram() {
  return (
    <figure className="model" style={{ margin: 0 }}>
      <svg viewBox="0 0 860 330" role="img" aria-labelledby="model-title model-desc">
        <title id="model-title">Kaagaz graph model</title>
        <desc id="model-desc">One rules graph per pack holds Pack, Scheme, Document, AnyOf and Office nodes. A Scheme REQUIRES Documents or AnyOf groups, a Document REQUIRES other Documents or AnyOf groups, an AnyOf has OPTION edges to Documents, and an Office ISSUES Documents. A separate graph per student holds Student, Holding, Target and PlanSnapshot nodes.</desc>
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0 0 L10 5 L0 10 z" fill="var(--ink-soft)" />
          </marker>
        </defs>
        <rect className="box" x="6" y="6" width="560" height="318" />
        <text className="lbl" x="18" y="26">graph kaagaz:rules:&lt;pack-id&gt; (one per rule pack, shared)</text>
        <rect className="node" x="30" y="130" width="110" height="44" /><text x="62" y="157">Scheme</text>
        <rect className="node" x="240" y="70" width="120" height="44" /><text x="268" y="97">Document</text>
        <rect className="node" x="240" y="210" width="120" height="44" /><text x="282" y="237">AnyOf</text>
        <rect className="node" x="430" y="70" width="110" height="44" /><text x="466" y="97">Office</text>
        <rect className="node" x="30" y="50" width="110" height="36" /><text x="70" y="73">Pack</text>
        <path className="edge req" d="M140 145 C 190 120, 200 100, 238 94" /><text className="lbl" x="150" y="112">REQUIRES</text>
        <path className="edge req" d="M140 160 C 190 190, 200 225, 238 230" /><text className="lbl" x="150" y="214">REQUIRES</text>
        <path className="edge req" d="M330 114 C 360 150, 360 175, 330 208" /><text className="lbl" x="352" y="165">REQUIRES</text>
        <path className="edge" d="M270 208 C 240 175, 240 150, 270 116" /><text className="lbl" x="186" y="165">OPTION</text>
        <path className="edge req" d="M300 70 C 330 30, 380 30, 352 68" /><text className="lbl" x="372" y="40">REQUIRES</text>
        <path className="edge" d="M430 92 L 362 92" /><text className="lbl" x="376" y="132">ISSUES</text>
        <text className="lbl" x="30" y="290">Every REQUIRES and OPTION edge stores source_url, source_title,</text>
        <text className="lbl" x="30" y="306">retrieved_at, excerpt and confidence. Document.days may be null.</text>
        <rect className="box" x="586" y="6" width="268" height="318" />
        <text className="lbl" x="598" y="26">graph kaagaz:student:&lt;id&gt; (one per student)</text>
        <rect className="node student" x="660" y="50" width="120" height="40" /><text x="692" y="75">Student</text>
        <rect className="node student" x="600" y="150" width="110" height="40" /><text x="626" y="175">Holding</text>
        <rect className="node student" x="730" y="150" width="110" height="40" /><text x="760" y="175">Target</text>
        <rect className="node student" x="640" y="250" width="160" height="40" /><text x="672" y="275">PlanSnapshot</text>
        <path className="edge" d="M700 90 L 660 148" /><text className="lbl" x="640" y="124">HOLDS</text>
        <path className="edge" d="M740 90 L 782 148" /><text className="lbl" x="770" y="124">TARGETS</text>
        <path className="edge" d="M720 90 C 850 150, 830 220, 760 248" /><text className="lbl" x="806" y="230">PLANNED</text>
      </svg>
      <figcaption className="note" style={{ marginTop: 8 }}>
        A Cypher query runs on one graph. The planner reads the student's holdings from the student graph and passes the held document ids as a parameter into the rules graph query, so one student's data can never be read by a query about another student.
      </figcaption>
    </figure>
  )
}

export default function About({ session }: { session: Session | null }) {
  const [qs, setQs] = useState<Q[] | null>(null)
  const [lb, setLb] = useState<LB | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    api.queries().then(setQs).catch((e: ApiError) => setError(e.message))
    api.loadBearing(session?.id).then(setLb).catch(() => setLb(null))
    api.graphStats().then(setStats).catch(() => setStats(null))
  }, [session?.id])
  const product = qs?.filter(q => !q.name.startsWith('seed_')) ?? []
  const seed = qs?.filter(q => q.name.startsWith('seed_')) ?? []
  return (
    <div>
      <p className="eyebrow">About the graph</p>
      <h1>How FalkorDB does the work</h1>
      <p className="lede" style={{ marginTop: 12 }}>Kaagaz is a graph problem: each document can need other documents, at any depth, with "any one of these" choices on the way. Without the graph there is no chain to walk, no critical path and no verdict.</p>
      <hr className="hair" />
      <section>
        <h2 style={{ marginBottom: 16 }}>Data model</h2>
        <ModelDiagram />
        {stats && (
          <p className="note" style={{ marginTop: 16 }} data-testid="graph-stats">
            Live counts in <code>{stats.graph}</code>: {stats.rows.map(r => `${r.n} ${r.name}`).join(', ')}.
          </p>
        )}
      </section>
      <hr className="hair" />
      <div className="grid2">
        <section>
          <h2 style={{ marginBottom: 16 }}>How the hackathon rules are met</h2>
          <ul style={{ paddingLeft: 18, margin: 0, display: 'grid', gap: 10 }}>
            <li><b>Track 1, Agents That Act on Connected Data.</b> Cross-session memory (one graph per student) also touches Track 2.</li>
            <li><b>The graph does real work.</b> Variable-length traversal finds hidden prerequisites; <code>reduce()</code> sums legal days along chains; shared-document and load-bearing queries rank options.</li>
            <li><b>The model never writes Cypher.</b> It may only call one of seven fixed tools, and names are checked against the graph before any other query runs.</li>
            <li><b>Every answer carries its path</b> and the source sentence for each step. When no rule connects two things, Kaagaz says "not in the graph".</li>
            <li><b>Data is public.</b> Rules come from saved government pages and PDFs. The Example student is made up.</li>
            <li><b>AI disclosure.</b> Built with Claude Code (Anthropic).</li>
          </ul>
        </section>
        <section>
          <h2 style={{ marginBottom: 16 }}>Load-bearing documents</h2>
          {lb ? (
            <>
              <p className="note">Documents that sit in the most scholarship chains{session ? ' you target' : ''} (<code>load_bearing.cypher</code>), and the top PageRank scores over REQUIRES edges on the whole pack (<code>load_bearing_pagerank.cypher</code>).</p>
              <div className="table-wrap" style={{ marginTop: 8 }}>
                <table>
                  <thead><tr><th scope="col">Document</th><th scope="col">Schemes</th></tr></thead>
                  <tbody>{lb.by_scheme_count.slice(0, 5).map(r => <tr key={r.doc_id}><td>{r.name}</td><td className="days">{r.scheme_count}</td></tr>)}</tbody>
                </table>
                <table style={{ marginTop: 12 }}>
                  <thead><tr><th scope="col">Document</th><th scope="col">PageRank</th></tr></thead>
                  <tbody>{lb.pagerank.slice(0, 5).map(r => <tr key={r.doc_id}><td>{r.name}</td><td className="days">{r.score.toFixed(3)}</td></tr>)}</tbody>
                </table>
              </div>
            </>
          ) : <Loading label="Ranking documents" />}
        </section>
      </div>
      <hr className="hair" />
      <h2 style={{ marginBottom: 8 }}>Every Cypher query the product runs</h2>
      <p className="note" style={{ marginBottom: 16 }}>Each one lives in its own file in <code>backend/kaagaz/queries/</code> and takes parameters, never pasted-in text.</p>
      {error && <StateBox title="Queries could not be loaded" error><p>{error}</p></StateBox>}
      {!qs && !error && <Loading label="Loading queries" />}
      <ul className="qlist" data-testid="query-list">
        {product.map(q => (
          <li key={q.name}>
            <details>
              <summary><span className="qname">{q.name}.cypher</span><span className="qabout">{q.about}</span></summary>
              <Cypher label={q.file} text={q.cypher} />
            </details>
          </li>
        ))}
      </ul>
      {seed.length > 0 && <p className="note" style={{ marginTop: 16 }}>Plus {seed.length} seed queries that load a rule pack: {seed.map(s => s.name).join(', ')}.</p>}
    </div>
  )
}
