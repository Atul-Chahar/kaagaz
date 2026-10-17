import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { Plan, PlanItem } from '../api'
import { fmtDate, fmtDays, shortName } from '../format'

const ROW = 56
const TOP = 64
const LABEL_W = 130

function shortDate(iso: string | undefined): string {
  if (!iso) return ''
  const s = fmtDate(iso)
  return s.split(' ').slice(0, 2).join(' ')
}

export default function Timeline({ plan, onOpen }: { plan: Plan; onOpen: (id: string, el: HTMLElement | null) => void }) {
  const frame = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(1100)
  const seen = useRef<Set<string>>(new Set())
  const [entering, setEntering] = useState<Set<string>>(new Set())

  useLayoutEffect(() => {
    const el = frame.current
    if (!el) return
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    setWidth(el.clientWidth)
    return () => ro.disconnect()
  }, [])

  const docs = plan.items.filter(i => i.label === 'Document' && i.needed)
  const crit = plan.critical_path.filter(id => docs.some(d => d.id === id))
  const critOrder = [...crit].reverse() // deepest prerequisite first (it starts first)
  const others = docs.filter(d => !crit.includes(d.id)).sort((a, b) => (a.start ?? 0) - (b.start ?? 0) || (b.end ?? 0) - (a.end ?? 0) || a.name.localeCompare(b.name))
  const rows: PlanItem[] = [...critOrder.map(id => docs.find(d => d.id === id)!), ...others]

  useEffect(() => {
    const ids = new Set(rows.map(r => r.id))
    const fresh = new Set([...ids].filter(id => !seen.current.has(id)))
    seen.current = ids
    setEntering(fresh)
    const t = setTimeout(() => setEntering(new Set()), 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [plan.depth, plan.items.length, plan.held.join(',')])

  const left = plan.days_left !== null && plan.days_left >= 0 ? plan.days_left : null
  const maxEnd = Math.max(plan.verdict.critical_days, ...rows.map(r => r.end ?? 0), 1)
  const span = Math.max(maxEnd, left ?? 0) + 4
  const narrow = width < 640
  const px = Math.max(narrow ? 14 : 18, Math.min(44, (width - 24) / span))
  const inner = Math.max(width, span * px + LABEL_W + 120)
  const height = TOP + Math.max(rows.length, 1) * ROW + 16
  const step = [1, 2, 5, 10, 20, 30].find(s => s * px >= 64) ?? 30
  const ticks = Array.from({ length: Math.floor(span / step) + 1 }, (_, i) => i * step)

  const geom = (r: PlanItem, i: number) => {
    const x = 12 + (r.start ?? 0) * px
    const known = r.days !== null && r.days !== undefined
    const w = known ? Math.max(r.days! * px, 6) : Math.max(0.8 * px, 14)
    return { x, w, y: TOP + i * ROW, known }
  }

  // red tape: through every critical slip, deepest first, then a knot at the end
  // the tape runs along the lower edge of each critical slip (below the text) and is tied between slips with a curve
  let tape = ''
  let knot: { x: number; y: number } | null = null
  critOrder.forEach((id, k) => {
    const i = rows.findIndex(r => r.id === id)
    const g = geom(rows[i], i)
    const cy = g.y + 47 // just under the slip, so the tape never crosses its text
    const end = g.x + Math.max(g.w, 14) + 6
    if (k === 0) tape += `M ${g.x - 6} ${cy} `
    else if (knot) {
      const mx = Math.max(knot.x, g.x - 6) + 10
      tape += `C ${mx} ${knot.y}, ${mx} ${cy}, ${Math.max(g.x - 6, knot.x)} ${cy} `
    }
    tape += `L ${end} ${cy} `
    knot = { x: end, y: cy }
  })

  const late = plan.verdict.kind === 'late' || plan.verdict.kind === 'late_at_least'
  const overrunFrom = left !== null ? 12 + left * px : 0
  const overrunTo = 12 + plan.verdict.critical_days * px

  return (
    <div>
      <div className="timeline-frame" ref={frame} data-testid="timeline">
        <div className="timeline" style={{ width: inner, height }} role="list" aria-label={`Timeline of ${rows.length} documents still needed, in ${plan.day_unit}`}>
          <div className="tl-axis" aria-hidden="true">
            {ticks.map(t => (
              <div key={t} className="tl-tick" style={{ left: 12 + t * px }}>{t === 0 ? 'Today' : shortDate(plan.dates[t])}</div>
            ))}
          </div>
          {ticks.slice(1).map(t => <div key={t} className="tl-grid" style={{ left: 12 + t * px }} aria-hidden="true" />)}
          {late && left !== null && overrunTo > overrunFrom && (
            <div className="tl-overrun" style={{ left: overrunFrom, width: overrunTo - overrunFrom }} aria-hidden="true" data-testid="overrun" />
          )}
          <div className="tl-today" style={{ left: 12 }} aria-hidden="true"><span>{fmtDate(plan.today)}</span></div>
          {left !== null && plan.deadline.date && (
            <div className="tl-deadline" style={{ left: 12 + left * px }} data-testid="deadline-line">
              <span style={12 + left * px > width - 190 ? { left: 'auto', right: 8 } : undefined}>Deadline {fmtDate(plan.deadline.date)}</span>
            </div>
          )}
          {rows.length === 0 && (
            <p className="note" style={{ position: 'absolute', top: TOP + 12, left: 24 }}>Nothing left to get at this depth. You hold every document shown.</p>
          )}
          {rows.map((r, i) => {
            const g = geom(r, i)
            const inside = g.w >= 140
            // the accessible name starts with exactly the visible text (short name, then days), then adds detail
            const label = `${shortName(r.name)} ${g.known ? `${fmtDays(r.days, plan.day_unit)} by law` : 'unknown time, no official time limit found'}. Starts ${r.start === 0 ? 'today' : `after ${fmtDays(r.start ?? 0, plan.day_unit)}`}.${r.on_critical ? ' On the critical path.' : ''} Full name: ${r.name}.`
            const cls = `slip ${r.on_critical ? 'crit' : ''} ${g.known ? '' : 'unknown'} ${entering.has(r.id) ? 'enter' : ''}`
            return (
              <div key={r.id} role="listitem" style={{ display: 'contents' }}>
                <button type="button" className={cls} style={{ left: g.x, top: g.y, width: inside ? g.w : Math.max(g.w, 14) }}
                  onClick={e => onOpen(r.id, e.currentTarget)} aria-label={label} data-testid={`slip-${r.id}`} data-critical={r.on_critical}>
                  {inside && <>
                    <span className="t">{shortName(r.name)}</span>{' '}
                    <span className="d">{g.known ? fmtDays(r.days, plan.day_unit) : 'unknown time'}</span>
                  </>}
                </button>
                {!inside && (
                  <button type="button" className={`slip-label ${entering.has(r.id) ? 'enter' : ''}`} tabIndex={-1} aria-hidden="true"
                    onClick={e => onOpen(r.id, e.currentTarget)}
                    style={{ position: 'absolute', left: g.x + Math.max(g.w, 14) + 8, top: g.y + 4, border: 0, background: 'transparent', textAlign: 'left', cursor: 'pointer', padding: 0, maxWidth: 260 }}>
                    <span style={{ display: 'block', fontSize: '0.8rem', fontWeight: 500, whiteSpace: 'nowrap' }}>{shortName(r.name)}</span>
                    <span className="days" style={{ fontSize: '0.7rem', color: g.known ? 'var(--ink-soft)' : 'var(--stamp-blue)' }}>{g.known ? fmtDays(r.days, plan.day_unit) : 'unknown time'}</span>
                  </button>
                )}
              </div>
            )
          })}
          {tape && (
            <svg className="tape" width={inner} height={height} aria-hidden="true" data-testid="red-tape">
              <path d={tape} />
              {knot && <circle className="knot" cx={(knot as { x: number }).x} cy={(knot as { y: number }).y} r="5" />}
            </svg>
          )}
        </div>
      </div>
      <div className="tl-legend" aria-hidden="true">
        <span><i />Paper slip: length is the legal processing time</span>
        <span><i className="tape-k" />Red tape: the critical path</span>
        <span><i className="unk" />Dashed: no official time limit found</span>
        {late && <span><i className="over" />Past the deadline</span>}
      </div>
    </div>
  )
}
