import { useEffect, useState } from 'react'
import { api, getPack, type PackInfo } from './api'

// Words a pack uses for its targets ("scholarship", "goal"). Defaults match the scholarship pack.
export interface PackUi { target: string; targets: string; example?: string }

let cache: PackInfo[] | null = null

export function usePackUi(): PackUi {
  const [packs, setPacks] = useState<PackInfo[] | null>(cache)
  useEffect(() => {
    if (cache) return
    api.packs().then(p => { cache = p; setPacks(p) }).catch(() => setPacks([]))
  }, [])
  const id = getPack()
  const ui = (packs ?? []).find(p => p.id === id)?.ui ?? (packs ?? []).find(p => p.default)?.ui ?? {}
  const target = ui.target ?? 'scholarship'
  return { target, targets: ui.targets ?? `${target}s`, example: ui.example }
}
