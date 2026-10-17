import { useState, type ReactNode } from 'react'
import type { Outcome, TraceRow, VerdictKind } from '../api'
import { OUTCOME_LABEL, stampClass } from '../labels'

export function OutcomeBadge({ outcome }: { outcome: Outcome }) {
  return <span className={`outcome ${outcome}`} data-testid="outcome">{OUTCOME_LABEL[outcome]}</span>
}

export function InkFilter() {
  // SVG noise used by the rubber stamp to look like real ink on paper.
  return (
    <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden="true" focusable="false">
      <filter id="ink" x="-10%" y="-10%" width="120%" height="120%">
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
        <feColorMatrix in="noise" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.1 1.4" result="speckle" />
        <feComposite in="SourceGraphic" in2="speckle" operator="in" />
      </filter>
    </svg>
  )
}

export function Stamp({ kind, text, sub, press }: { kind: VerdictKind; text: string; sub?: string; press?: boolean }) {
  return (
    <div className={`stamp ${stampClass(kind)} ${press ? 'press' : ''}`} data-testid="stamp" data-kind={kind}>
      <span className="main">{text}</span>
      {sub && <span className="sub">{sub}</span>}
    </div>
  )
}

export function TraceTable({ rows }: { rows: TraceRow[] }) {
  if (!rows.length) return null
  return (
    <div className="table-wrap">
      <table className="trace" data-testid="trace">
        <caption className="sr-only">Tool calls and queries that produced this answer</caption>
        <thead><tr><th scope="col">Tool or query</th><th scope="col">Arguments</th><th scope="col">ms</th><th scope="col">Rows</th></tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td>{r.kind === 'tool' ? <b>{r.tool}</b> : r.tool}</td>
              <td className="args">{JSON.stringify(r.args)}</td>
              <td>{r.ms.toFixed(1)}</td>
              <td>{r.rows}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Cypher({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span className="eyebrow">{label}</span>
        <button className="btn ghost small" type="button" onClick={async () => {
          try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { setCopied(false) }
        }}>{copied ? 'Copied' : 'Copy Cypher'}</button>
      </div>
      <pre className="cypher" tabIndex={0} aria-label={`Cypher query ${label}`}>{text}</pre>
    </div>
  )
}

export function StateBox({ title, children, error, testid }: { title: string; children?: ReactNode; error?: boolean; testid?: string }) {
  return (
    <div className={`state ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'} data-testid={testid}>
      <h3>{title}</h3>
      {children}
    </div>
  )
}

export function Loading({ label }: { label: string }) {
  return (
    <div role="status" aria-live="polite" style={{ padding: '24px 0' }}>
      <div className="loading-line" />
      <p className="note" style={{ marginTop: 8 }}>{label}</p>
    </div>
  )
}

export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect x="5" y="3" width="22" height="26" rx="1" fill="var(--paper-slip)" stroke="var(--ink)" strokeWidth="1.5" />
      <path d="M9 10h14M9 15h14M9 20h9" stroke="var(--ink-soft)" strokeWidth="1.5" />
      <path d="M3 22 L29 12" stroke="var(--red-tape)" strokeWidth="3" />
    </svg>
  )
}
