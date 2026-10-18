import { fmtDate } from '../format'

// Today's date where the student is (both rule packs are in Karnataka).
function realToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date())
}

// Kaagaz plans from today. Most 2026-27 windows close soon after the submission day, so a later visitor can switch
// to "as on the submission day" to see the plan with open windows. Only the start date changes; it is always labelled.
export default function DateBar({ asOf, snapshot, onChange }: { asOf: string | null; snapshot: string | null; onChange: (d: string | null) => void }) {
  if (asOf) {
    return (
      <div className="datebar as-of" role="status" data-testid="as-of-bar">
        <div className="datebar-in">
          <p>
            <b>Counting from {fmtDate(asOf)}{asOf === snapshot ? ', the day Kaagaz was submitted' : ''}, not today.</b>{' '}
            The rules and deadlines are the real ones from the sources; only the start date is set back.
          </p>
          <button className="btn ghost small" type="button" onClick={() => onChange(null)} data-testid="as-of-off">Use today's date</button>
        </div>
      </div>
    )
  }
  if (!snapshot || realToday() <= snapshot) return null
  return (
    <div className="datebar" data-testid="as-of-offer">
      <div className="datebar-in">
        <p>Counting from today, {fmtDate(realToday())}. Kaagaz was submitted on {fmtDate(snapshot)}; many 2026-27 application windows have closed since then.</p>
        <button className="btn ghost small" type="button" onClick={() => onChange(snapshot)} data-testid="as-of-on">See it as on {fmtDate(snapshot)}</button>
      </div>
    </div>
  )
}
