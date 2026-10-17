import { useCallback, useEffect, useState } from 'react'
import { InkFilter, Mark } from './components/common'
import { getStudent, getTheme, setStudent, setTheme } from './store'
import Start from './screens/Start'
import Chain from './screens/Chain'
import Ask from './screens/Ask'
import Benchmark from './screens/Benchmark'
import Sources from './screens/Sources'
import About from './screens/About'
import type { Session } from './nav'

const ROUTES = [
  { path: '/', label: 'Start' },
  { path: '/chain', label: 'Your chain' },
  { path: '/ask', label: 'Ask' },
  { path: '/benchmark', label: 'Benchmark' },
  { path: '/sources', label: 'Sources' },
  { path: '/graph', label: 'About the graph' },
]

function currentPath(): string {
  const h = window.location.hash.replace(/^#/, '')
  return h.split('?')[0] || '/'
}

export default function App() {
  const [path, setPath] = useState(currentPath())
  const [session, setSessionState] = useState<Session | null>(() => getStudent())
  const [theme, setThemeState] = useState<'light' | 'dark' | null>(() => getTheme())

  useEffect(() => {
    const on = () => { setPath(currentPath()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  useEffect(() => {
    const label = ROUTES.find(r => r.path === path)?.label ?? 'Kaagaz'
    document.title = path === '/' ? 'Kaagaz' : `${label} · Kaagaz`
    document.getElementById('main')?.focus({ preventScroll: true })
  }, [path])

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
    case '/benchmark': screen = <Benchmark />; break
    case '/sources': screen = <Sources />; break
    case '/graph': screen = <About session={session} />; break
    default: screen = <Start session={session} setSession={setSession} />
  }

  return (
    <>
      <InkFilter />
      <a className="skip" href="#main" onClick={e => { e.preventDefault(); document.getElementById('main')?.focus() }}>Skip to content</a>
      <header className="topbar">
        <div className="topbar-in">
          <a className="wordmark" href="#/" aria-label="Kaagaz, start page"><Mark /> Kaagaz</a>
          <nav className="nav" aria-label="Main">
            {ROUTES.map(r => (
              <a key={r.path} href={`#${r.path}`} aria-current={path === r.path ? 'page' : undefined}>{r.label}</a>
            ))}
          </nav>
          <button className="theme-btn" type="button" onClick={toggleTheme} aria-label={`Switch to ${effective === 'dark' ? 'day' : 'night'} mode`}>
            {effective === 'dark' ? 'Day office' : 'Night office'}
          </button>
        </div>
      </header>
      <main id="main" tabIndex={-1} style={{ outline: 'none' }}>{screen}</main>
      <footer className="foot">
        <span>Kaagaz. Rules come from saved official sources; every line links to its source.</span>
        <span>Not legal advice. Check the official portal before you apply.</span>
        <span>Built with Claude Code.</span>
      </footer>
    </>
  )
}
