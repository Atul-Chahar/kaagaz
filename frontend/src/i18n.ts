// i18n structure. English only for now: Hindi strings are not added because nobody could check them carefully.
// To add a language: copy `en`, translate every value, add it to MESSAGES, and set <html lang>.
// Today the app shell (navigation, footer, theme button) reads from here; screen copy is still inline in screens/.

const en = {
  'nav.start': 'Start',
  'nav.chain': 'Your chain',
  'nav.ask': 'Ask',
  'nav.agents': 'Agents',
  'nav.benchmark': 'Benchmark',
  'nav.sources': 'Sources',
  'nav.graph': 'About the graph',
  'nav.label': 'Main',
  'skip': 'Skip to content',
  'theme.toDark': 'Night office',
  'theme.toLight': 'Day office',
  'foot.sources': 'Kaagaz. Rules come from saved official sources; every line links to its source.',
  'foot.advice': 'Not legal advice. Check the official portal before you apply.',
  'foot.ai': 'Built with Claude Code.',
} as const

export type MessageKey = keyof typeof en
const MESSAGES: Record<string, Record<MessageKey, string>> = { en }
const LANG = 'en'

export function t(key: MessageKey): string {
  return MESSAGES[LANG]?.[key] ?? en[key]
}
