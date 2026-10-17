export interface Session { id: string; scheme_id?: string; example?: boolean; pack?: string }

export function go(path: string) {
  window.location.hash = path
}
