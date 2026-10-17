import { expect, type Page, type APIRequestContext } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

// Loads the Example student (a private copy per visitor) and returns its student id.
export async function loadExample(page: Page): Promise<string> {
  await page.goto('/#/')
  await page.getByTestId('load-example').click()
  await expect(page.getByTestId('stamp')).toBeVisible()
  return page.evaluate(() => JSON.parse(localStorage.getItem('kaagaz.student') ?? '{}').id as string)
}

export async function apiPlan(request: APIRequestContext, sid: string, scheme: string, depth: number) {
  const r = await request.get(`/api/plan?student_id=${sid}&scheme_id=${scheme}&depth=${depth}&remember=false`)
  expect(r.ok()).toBeTruthy()
  return (await r.json()).data
}

export async function expectNoSeriousA11y(page: Page, name: string) {
  const res = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze()
  const bad = res.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
  if (bad.length) console.log(name, JSON.stringify(bad.map(v => ({ id: v.id, impact: v.impact, nodes: v.nodes.slice(0, 3).map(n => n.target) })), null, 1))
  expect(bad, `${name}: serious or critical axe violations`).toEqual([])
}
