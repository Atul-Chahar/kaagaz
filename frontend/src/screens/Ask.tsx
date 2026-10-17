import { useEffect, useState } from 'react'
import { api, ApiError, type AskResponse } from '../api'
import { Loading, OutcomeBadge, StateBox, TraceTable } from '../components/common'
import type { Session } from '../nav'

const EXAMPLES = [
  'What do I need for Vidyasiri for Minorities?',
  'Does PostMatric for OBC Students need a caste and income certificate?',
  'Does PM YASASVI Top Class need a hostel certificate?',
  'Do I need a PAN card for Vidyasiri?',
  'How do I get a domicile certificate?',
]

export default function Ask({ session }: { session: Session | null }) {
  const [q, setQ] = useState('')
  const [res, setRes] = useState<AskResponse | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [llm, setLlm] = useState<{ on: boolean; model: string | null } | null>(null)

  useEffect(() => { api.health().then(h => setLlm({ on: h.llm, model: h.llm_model })).catch(() => setLlm(null)) }, [])

  async function ask(question: string) {
    if (!question.trim()) return
    setBusy(true); setError(null)
    try {
      setRes(await api.ask(question, session?.id, session?.scheme_id))
    } catch (e) {
      setError((e as ApiError).message)
    } finally { setBusy(false) }
  }

  return (
    <div style={{ maxWidth: 900 }}>
      <p className="eyebrow">Ask</p>
      <h1>Ask about a document or a scholarship</h1>
      <p className="lede" style={{ marginTop: 12 }}>
        {llm?.on
          ? `A language model (${llm.model}) picks one tool from a fixed list. It never writes database queries. Its one-sentence answer is checked against the result before you see it.`
          : 'No language model key is set, so this box searches scheme and document names in the graph and runs the matching tool. Everything else works the same.'}
      </p>
      <form className="ask-form" onSubmit={e => { e.preventDefault(); ask(q) }}>
        <label htmlFor="ask-q" className="sr-only">Your question</label>
        <input id="ask-q" type="text" value={q} onChange={e => setQ(e.target.value)} placeholder="For example: does Vidyasiri need a ration card?" maxLength={500} data-testid="ask-input" />
        <button className="btn" type="submit" disabled={busy || !q.trim()} data-testid="ask-submit">Ask</button>
      </form>
      <div className="examples" aria-label="Example questions">
        {EXAMPLES.map(x => <button key={x} type="button" onClick={() => { setQ(x); ask(x) }}>{x}</button>)}
      </div>
      {busy && <Loading label="Running the tool against FalkorDB" />}
      {error && <div style={{ marginTop: 24 }}><StateBox title="The question could not be answered" error><p>{error}</p></StateBox></div>}
      {res && !busy && (
        <section className="answer" aria-live="polite" data-testid="ask-answer">
          <OutcomeBadge outcome={res.outcome} />
          <p className="text">{res.answer}</p>
          <p className="note">
            {res.mode === 'llm' ? 'Routed by the language model'
              : res.route_error ? `Routed by name search, because the language model call failed (${res.route_error})`
              : 'Routed by name search (no language model)'} to the tool <code>{res.tool}</code>.{' '}
            {res.answer_source === 'llm_checked' && 'The sentence was written by the model and passed the check.'}
            {res.answer_source === 'built_from_result' && 'The sentence was built directly from the tool result.'}
            {res.answer_source === 'built_from_result_after_failed_check' && `The model's sentence failed the check (${res.check?.problems.join('; ')}), so this sentence was built from the result instead.`}
          </p>
          <h2 style={{ fontSize: '1.1rem', margin: '24px 0 8px' }}>Trace</h2>
          <TraceTable rows={res.trace} />
        </section>
      )}
    </div>
  )
}
