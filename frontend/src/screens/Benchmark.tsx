import { useEffect, useState } from 'react'
import { api, ApiError, type BenchResponse, type BenchRun, type BenchSystemScore } from '../api'
import { Loading, StateBox } from '../components/common'
import { fmtDate } from '../format'

const METRICS: { key: keyof BenchSystemScore; label: string; better: 'higher' | 'lower' }[] = [
  { key: 'document_recall', label: 'Document recall', better: 'higher' },
  { key: 'invented_documents', label: 'Invented documents per answer', better: 'lower' },
  { key: 'verdict_accuracy', label: 'Verdict accuracy', better: 'higher' },
  { key: 'first_step_accuracy', label: 'First-step accuracy', better: 'higher' },
]
const NAMES: Record<string, string> = {
  llm_alone: 'LLM alone',
  plain_rag: 'Plain RAG (BM25, top 8)',
  kaagaz: 'Kaagaz',
  kaagaz_deterministic: 'Kaagaz planner (no LLM)',
}

function pct(v: number | null, key: string): string {
  if (v === null || v === undefined) return 'n/a'
  return key === 'invented_documents' ? v.toFixed(2) : `${Math.round(v * 100)}%`
}

function RunTable({ run }: { run: BenchRun }) {
  return (
    <div className="table-wrap">
      <table data-testid="bench-table">
        <caption className="sr-only">Benchmark scores by system</caption>
        <thead>
          <tr><th scope="col">System</th>{METRICS.map(m => <th key={m.key} scope="col">{m.label}{m.better === 'lower' ? ' (lower is better)' : ''}</th>)}</tr>
        </thead>
        <tbody>
          {run.systems.map(s => (
            <tr key={s.system}>
              <th scope="row" style={{ textTransform: 'none', fontSize: '0.93rem', color: 'var(--ink)', letterSpacing: 0 }}>{NAMES[s.system] ?? s.system}</th>
              {METRICS.map(m => <td key={m.key} className="days">{pct(s[m.key] as number | null, m.key)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Bars({ run, metric }: { run: BenchRun; metric: typeof METRICS[number] }) {
  const vals = run.systems.map(s => s[metric.key] as number | null)
  const max = metric.key === 'invented_documents' ? Math.max(1, ...vals.map(v => v ?? 0)) : 1
  return (
    <figure style={{ margin: 0 }}>
      <figcaption style={{ fontWeight: 500, marginBottom: 8 }}>{metric.label}{metric.better === 'lower' ? ' (lower is better)' : ''}</figcaption>
      <div className="bars" style={{ marginTop: 0 }}>
        {run.systems.map(s => {
          const v = s[metric.key] as number | null
          return (
            <div className="bar-row" key={s.system} title={`${NAMES[s.system] ?? s.system}: ${pct(v, metric.key)}`}>
              <span>{NAMES[s.system] ?? s.system}</span>
              <span className="bar-track"><span className={`bar-fill ${s.system.startsWith('kaagaz') ? 'kaagaz' : ''}`} style={{ width: `${((v ?? 0) / max) * 100}%` }} /></span>
              <span className="days">{pct(v, metric.key)}</span>
            </div>
          )
        })}
      </div>
    </figure>
  )
}

export default function Benchmark() {
  const [b, setB] = useState<BenchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.benchmark().then(setB).catch((e: ApiError) => setError(e.message)) }, [])
  return (
    <div>
      <p className="eyebrow">Benchmark</p>
      <h1>Does the graph beat plain approaches?</h1>
      <p className="lede" style={{ marginTop: 12 }}>The same questions, written from the saved sources, go to three systems that use the same model: the model alone, the model with plain text search over the same sources, and Kaagaz.</p>
      {error && <StateBox title="Benchmark results could not be loaded" error><p>{error}</p></StateBox>}
      {!b && !error && <Loading label="Loading the latest results" />}
      {b && (
        <>
          <hr className="hair" />
          <section aria-labelledby="llm-h">
            <h2 id="llm-h" style={{ marginBottom: 12 }}>Three systems, same model</h2>
            {b.llm_run ? (
              <>
                <p className="note" style={{ marginBottom: 16 }} data-testid="bench-meta">
                  Run {fmtDate(b.llm_run.started_at)} with model <code>{b.llm_run.model}</code> on {b.llm_run.questions} questions. File <code>bench/results/{b.llm_run_file}</code>.
                </p>
                <RunTable run={b.llm_run} />
                <div style={{ marginTop: 24, maxWidth: 640 }}><Bars run={b.llm_run} metric={METRICS[0]} /></div>
              </>
            ) : (
              <StateBox title="Benchmark not run yet." testid="bench-empty">
                <p>Benchmark not run yet. Add an LLM key and run <code>make bench</code>.</p>
                <p style={{ marginTop: 8 }}>No numbers are shown here until a real run writes a results file.{b.llm_configured ? ' A key is configured on this server, so the run can be started.' : ''}</p>
              </StateBox>
            )}
          </section>
          <hr className="hair" />
          <section aria-labelledby="det-h">
            <h2 id="det-h" style={{ marginBottom: 12 }}>Kaagaz planner on its own (no LLM)</h2>
            {b.deterministic_run ? (
              <>
                <p className="note" style={{ marginBottom: 16 }} data-testid="det-meta">
                  These are Kaagaz's own deterministic scores: the planner answers each question straight from the graph, with no language model. Run {fmtDate(b.deterministic_run.started_at)} on {b.deterministic_run.questions} questions, file <code>bench/results/{b.deterministic_run_file}</code>. The graph and the ground truth come from the same saved sources, so these numbers show how often the engine agrees with an independent reading of those sources. They are not a comparison with other systems.
                </p>
                <RunTable run={b.deterministic_run} />
                {b.deterministic_run.disagreements && (
                  <p className="note" style={{ marginTop: 12 }} data-testid="det-disagreements">
                    On {b.deterministic_run.disagreements.length} of {b.deterministic_run.questions} questions the graph's answer differs from the answer written from the sources. Each one is listed in the results file with both answers. They come from three things: which income or caste certificate a scheme's source names (a generic one or the Karnataka one), the order of first steps when no official time limit decides it, and rules that apply only to some students, which Kaagaz leaves out unless the student says they apply.
                  </p>
                )}
              </>
            ) : (
              <StateBox title="Not run yet"><p>Run <code>make bench-deterministic</code> to score the planner on its own.</p></StateBox>
            )}
          </section>
        </>
      )}
    </div>
  )
}
