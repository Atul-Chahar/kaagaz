export interface Session { id: string; scheme_id?: string; example?: boolean }

export function go(path: string) {
  window.location.hash = path
}
