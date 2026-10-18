// Per-viewer conveniences only (which student id this browser uses, theme). The real memory is in FalkorDB.

const KEY = 'kaagaz.student'

export function getStudent(): { id: string; scheme_id?: string; example?: boolean; pack?: string; label?: string } | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setStudent(v: { id: string; scheme_id?: string; example?: boolean; pack?: string; label?: string } | null): void {
  try {
    if (v) localStorage.setItem(KEY, JSON.stringify(v))
    else localStorage.removeItem(KEY)
  } catch { /* storage blocked: the session still works for this visit */ }
}

export function getTheme(): 'light' | 'dark' | null {
  try {
    const t = localStorage.getItem('kaagaz.theme')
    return t === 'light' || t === 'dark' ? t : null
  } catch {
    return null
  }
}

export function setTheme(t: 'light' | 'dark'): void {
  try { localStorage.setItem('kaagaz.theme', t) } catch { /* ignore */ }
}

// "See it as on the submission day": a per-viewer view setting, not data.
export function getAsOfStored(): string | null {
  try {
    const v = localStorage.getItem('kaagaz.asOf')
    return v && /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null
  } catch {
    return null
  }
}

export function setAsOfStored(v: string | null): void {
  try {
    if (v) localStorage.setItem('kaagaz.asOf', v)
    else localStorage.removeItem('kaagaz.asOf')
  } catch { /* ignore */ }
}
