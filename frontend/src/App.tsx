import { useCallback, useEffect, useState } from 'react'
import { InkFilter, Mark } from './components/common'
import { getAsOfStored, getStudent, getTheme, setAsOfStored, setStudent, setTheme } from './store'
import Start from './screens/Start'
import Chain from './screens/Chain'
import Ask from './screens/Ask'
import Benchmark from './screens/Benchmark'
import Sources from './screens/Sources'
import About from './screens/About'
import Agents from './screens/Agents'
import type { Session } from './nav'
import { t, type MessageKey } from './i18n'
import { api, setAsOf, setPack } from './api'
import DateBar from './components/DateBar'

const ROUTES: { path: string; key: MessageKey }[] = [
  { path: '/', key: 'nav.start' },
  { path: '/chain', key: 'nav.chain' },
  { path: '/ask', key: 'nav.ask' },
  { path: '/agents', key: 'nav.agents' },
  { path: '/benchmark', key: 'nav.benchmark' },
  { path: '/sources', key: 'nav.sources' },
  { path: '/graph', key: 'nav.graph' },
]

function currentPath(): string {
  const h = window.location.hash.replace(/^#/, '')
  return h.split('?')[0] || '/'
}

export default function App() {
  const [path, setPath] = useState(currentPath())
  const [session, setSessionState] = useState<Session | null>(() => { const s = getStudent(); setPack(s?.pack ?? null); return s })
  const [asOf, setAsOfState] = useState<string | null>(() => { const d = getAsOfStored(); setAsOf(d); return d })
  const [snapshot, setSnapshot] = useState<string | null>(null)
  const [theme, setThemeState] = useState<'light' | 'dark' | null>(() => getTheme())

  useEffect(() => {
    const on = () => { setPath(currentPath()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    const route = ROUTES.find(r => r.path === path)
    const label = route ? t(route.key) : 'Kaagaz'
    document.title = path === '/' ? 'Kaagaz' : `${label} · Kaagaz`
    document.getElementById('main')?.focus({ preventScroll: true })
  }, [path])

  useEffect(() => { api.health().then(h => setSnapshot(h.snapshot_date ?? null)).catch(() => setSnapshot(null)) }, [])

  const changeAsOf = useCallback((d: string | null) => { setAsOf(d); setAsOfStored(d); setAsOfState(d) }, [])

  const setSession = useCallback((s: Session | null) => { setSessionState(s); setStudent(s) }, [])

  const effective = theme ?? (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  const toggleTheme = () => {
    const next = effective === 'dark' ? 'light' : 'dark'
    document.documentElement.setAttribute('data-theme', next)
    setTheme(next)
    setThemeState(next)
  }

  let screen
  switch (path) {
    case '/chain': screen = <Chain session={session} setSession={setSession} />; break
    case '/ask': screen = <Ask session={session} />; break
    case '/agents': screen = <Agents />; break
    case '/benchmark': screen = <Benchmark />; break
    case '/sources': screen = <Sources />; break
    case '/graph': screen = <About session={session} />; break
    default: screen = <Start session={session} setSession={setSession} />
  }

  return (
    <>
      <InkFilter />
      <a className="skip" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus() }}>{t('skip')}</a>
      <header className="topbar">
        <div className="topbar-in">
          <a className="wordmark" href="#/" aria-label="Kaagaz, start page"><Mark /> Kaagaz</a>
          <nav className="nav" aria-label={t('nav.label')}>
            {ROUTES.map(r => (
              <a key={r.path} href={`#${r.path}`} aria-current={path === r.path ? 'page' : undefined}>{t(r.key)}</a>
            ))}
          </nav>
          <button className="theme-btn" type="button" onClick={toggleTheme} title={`Switch to ${effective === 'dark' ? 'light' : 'dark'} colours`}>
            {effective === 'dark' ? t('theme.toLight') : t('theme.toDark')}
          </button>
        </div>
      </header>
      <DateBar asOf={asOf} snapshot={snapshot} onChange={changeAsOf} />
      <main id="main" key={asOf ?? 'today'} tabIndex={-1} style={{ outline: 'none' }}>{screen}</main>
      <footer className="foot">
        <span>{t('foot.sources')}</span>
        <span>{t('foot.advice')}</span>
        <span>{t('foot.ai')}</span>
      </footer>
    </>
  )
}
