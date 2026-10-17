import { useEffect, useState } from 'react'
import { api, ApiError } from '../api'
import { Loading, StateBox } from '../components/common'
import { fmtDate, hostOf } from '../format'

type Row = Awaited<ReturnType<typeof api.sources>>['sources'][number]

export default function Sources() {
  const [rows, setRows] = useState<Row[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.sources().then(r => setRows(r.sources)).catch((e: ApiError) => setError(e.message)) }, [])
  const used = rows?.filter(r => r.rules_citing > 0) ?? []
  const secondary = used.filter(r => r.confidence === 'secondary').length
  return (
    <div>
      <p className="eyebrow">Sources</p>
      <h1>Every source in this rule pack</h1>
      <p className="lede" style={{ marginTop: 12 }}>Each rule in the graph quotes a sentence from one of these pages or PDFs. Every file was saved on the day shown, with a SHA-256 hash so anyone can check it has not changed.</p>
      {error && <StateBox title="Sources could not be loaded" error><p>{error}</p></StateBox>}
      {!rows && !error && <Loading label="Loading the source index" />}
      {rows && (
        <>
          <p className="note" style={{ margin: '24px 0 12px' }}>{rows.length} saved sources. {used.length} are cited by rules in the graph; {secondary} of those are secondary sources (used only where no official one was found).</p>
          <div className="table-wrap">
            <table data-testid="sources-table">
              <caption className="sr-only">Saved sources with retrieval date, hash and how many rules cite each</caption>
              <thead><tr><th scope="col">Title</th><th scope="col">Retrieved</th><th scope="col">Rules citing</th><th scope="col">Kind</th><th scope="col">SHA-256</th></tr></thead>
              <tbody>
                {rows.map(r => (
                  <tr key={r.id}>
                    <td><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a><br /><span className="note">{hostOf(r.url)} · {r.content_type === 'application/pdf' ? 'PDF' : 'web page'}</span></td>
                    <td className="days">{fmtDate(r.retrieved_at)}</td>
                    <td className="days">{r.rules_citing}</td>
                    <td>{r.confidence === 'secondary' ? <span className="tag secondary">Secondary</span> : r.confidence === 'official' ? <span className="tag">Official</span> : <span className="muted">Not cited</span>}</td>
                    <td className="mono" style={{ fontSize: '0.72rem' }} title={r.sha256}>{r.sha256.slice(0, 16)}…</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  )
}
