import { expect, test } from '@playwright/test'
import { apiPlan, expectNoSeriousA11y, loadExample } from './helpers'

test.describe.configure({ mode: 'serial' })

test('Example student: stepping depth 1 to max shows the verdict the graph computes at each depth', async ({ page, request }) => {
  const sid = await loadExample(page)
  const ex = await (await request.get(`/api/students/${sid}`)).json()
  const scheme = ex.data.targets[0].scheme_id
  const full = await apiPlan(request, sid, scheme, 8)
  const max = full.max_depth
  expect(max).toBeGreaterThan(1)
  await expect(page.getByTestId('depth-1')).toHaveAttribute('aria-pressed', 'true')
  const stamps: string[] = []
  for (let d = 1; d <= max; d++) {
    if (d > 1) await page.getByTestId('depth-next').click()
    await expect(page.getByTestId(`depth-${d}`)).toHaveAttribute('aria-pressed', 'true')
    const expected = await apiPlan(request, sid, scheme, d)
    await expect(page.getByTestId('stamp')).toContainText(expected.verdict.stamp)
    // every needed document at this depth is a slip on the timeline
    for (const id of expected.needed) await expect(page.getByTestId(`slip-${id}`)).toBeVisible()
    stamps.push(expected.verdict.stamp)
  }
  // the data says the hidden steps change the verdict for this profile
  expect(stamps[0]).not.toEqual(stamps[stamps.length - 1])
  expect(stamps[0]).toContain('ON TIME')
  expect(stamps[stamps.length - 1]).toContain('AT LEAST')
})

test('"I have this" saves to memory and the plan recomputes', async ({ page, request }) => {
  const sid = await loadExample(page)
  const ex = await (await request.get(`/api/students/${sid}`)).json()
  const scheme = ex.data.targets[0].scheme_id
  await page.getByTestId('depth-2').click()
  const before = await apiPlan(request, sid, scheme, 2)
  const first = before.start_today[0].id
  await expect(page.getByTestId(`todo-${first}`)).toBeVisible()
  await page.getByTestId(`have-${first}`).click()
  await expect(page.getByTestId(`todo-${first}`)).toHaveCount(0)
  const after = await apiPlan(request, sid, scheme, 2)
  expect(after.held).toContain(first)
  expect(after.verdict.stamp).not.toEqual(before.verdict.stamp)
  await expect(page.getByTestId('stamp')).toContainText(after.verdict.stamp)
  // memory survives a reload: it comes back from the student graph
  await page.reload()
  await expect(page.getByTestId('stamp')).toContainText(after.verdict.stamp)
})

test('Why panel shows the path with a source link', async ({ page }) => {
  await loadExample(page)
  await page.getByTestId('depth-2').click()
  const slip = page.locator('[data-testid^="slip-"]').first()
  await slip.click()
  const panel = page.getByTestId('why-panel')
  await expect(panel).toBeVisible()
  const src = panel.getByTestId('why-source').first()
  await expect(src).toHaveAttribute('href', /^https?:\/\//)
  await expect(panel.getByTestId('why-chips')).toBeVisible()
  await expect(panel.locator('pre.cypher')).toContainText('MATCH p = (s:Scheme')
  await expectNoSeriousA11y(page, 'why panel')
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
})

test('Ask works with no LLM key (name search) and shows outcome and trace', async ({ page }) => {
  await page.goto('/#/ask')
  await expect(page.getByText('No language model key is set')).toBeVisible()
  await page.getByTestId('ask-input').fill('Does Fee Reimbursement for Minorities need a caste and income certificate?')
  await page.getByTestId('ask-submit').click()
  const ans = page.getByTestId('ask-answer')
  await expect(ans).toBeVisible()
  await expect(ans.getByTestId('outcome')).toHaveText(/Answered with a path|No official time found/)
  await expect(ans.getByTestId('trace')).toContainText('explain')
  await page.getByTestId('ask-input').fill('How do I get a domicile certificate?')
  await page.getByTestId('ask-submit').click()
  await expect(page.getByTestId('ask-answer').getByTestId('outcome')).toHaveText('Unknown name')
})

test('Benchmark page shows only real results or the honest empty state', async ({ page, request }) => {
  const b = await (await request.get('/api/benchmark')).json()
  await page.goto('/#/benchmark')
  if (!b.llm_run) {
    await expect(page.getByTestId('bench-empty')).toContainText('Benchmark not run yet. Add an LLM key and run make bench.')
  } else {
    await expect(page.getByTestId('bench-meta')).toContainText(b.llm_run.model)
  }
  if (b.deterministic_run) {
    await expect(page.getByTestId('det-meta')).toContainText(b.deterministic_run_file)
  }
})

const SCREENS: [string, string][] = [
  ['start', '/#/'], ['ask', '/#/ask'], ['benchmark', '/#/benchmark'], ['sources', '/#/sources'], ['graph', '/#/graph'],
]

for (const [name, url] of SCREENS) {
  test(`axe: ${name} has no serious or critical violations`, async ({ page }) => {
    await page.goto(url)
    await page.waitForLoadState('networkidle')
    await expectNoSeriousA11y(page, name)
  })
}

test('axe: chain screen (light and dark)', async ({ page }) => {
  await loadExample(page)
  await page.getByTestId('depth-2').click()
  await page.waitForLoadState('networkidle')
  await expectNoSeriousA11y(page, 'chain light')
  await page.emulateMedia({ colorScheme: 'dark' })
  await page.waitForTimeout(500) // let the 200 ms theme colour transition finish before measuring contrast
  console.log('dark colours', await page.evaluate(() => {
    const el = document.querySelector('.mini-stamp.late')
    return el ? [getComputedStyle(el).color, getComputedStyle(document.body).backgroundColor] : null
  }))
  await expectNoSeriousA11y(page, 'chain dark')
})

test('keyboard: depth stepper and slips are reachable and work', async ({ page }) => {
  await loadExample(page)
  await page.getByTestId('depth-2').focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('depth-2')).toHaveAttribute('aria-pressed', 'true')
  const slip = page.locator('[data-testid^="slip-"]').first()
  await slip.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByTestId('why-panel')).toBeVisible()
})

test('390 px wide: no screen scrolls sideways (the timeline scrolls inside its own frame)', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  for (const url of ['/#/', '/#/ask', '/#/benchmark', '/#/sources', '/#/graph']) {
    await page.goto(url)
    await page.waitForLoadState('networkidle')
    expect(await page.evaluate(() => document.documentElement.scrollWidth), url).toBeLessThanOrEqual(390)
  }
  await loadExample(page)
  await expect(page.getByTestId('alternatives')).toBeVisible()
  for (const d of [1, 2]) {
    await page.getByTestId(`depth-${d}`).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth), `chain depth ${d}`).toBeLessThanOrEqual(390)
  }
})

test('second rule pack: switch to the company pack and load the Example founder', async ({ page, request }) => {
  const packs = await (await request.get('/api/packs')).json()
  expect(packs.map((p: { id: string }) => p.id)).toContain('in-ka-company')
  await page.goto('/#/')
  // the default pack's own words show before any switch (regression: wording once came from the wrong pack)
  await expect(page.getByRole('heading', { name: 'Pick a scholarship' })).toBeVisible()
  await expect(page.getByTestId('load-example')).toHaveText('Load the Example student')
  await page.getByTestId('pack-in-ka-company').click()
  await expect(page.getByRole('heading', { name: 'Pick a goal' })).toBeVisible()
  await page.getByTestId('load-example').click()
  await expect(page.getByTestId('stamp')).toBeVisible()
  await expect(page.getByText('Example founder (made up, not a real person)')).toBeVisible()
  const fid = await page.evaluate(() => JSON.parse(localStorage.getItem('kaagaz.student') ?? '{}').id as string)
  const ex = await (await request.get(`/api/students/${fid}?pack=in-ka-company`)).json()
  const scheme = ex.data.targets[0].scheme_id
  const max = (await (await request.get(`/api/plan?student_id=${fid}&scheme_id=${scheme}&depth=8&remember=false&pack=in-ka-company`)).json()).data.max_depth
  await page.getByTestId(`depth-${max}`).click()
  const plan = (await (await request.get(`/api/plan?student_id=${fid}&scheme_id=${scheme}&depth=${max}&remember=false&pack=in-ka-company`)).json()).data
  await expect(page.getByTestId('stamp')).toContainText(plan.verdict.stamp)
  await expectNoSeriousA11y(page, 'company chain')
})

test('"This applies to me" adds a conditional requirement to the chain, and removing it takes it out', async ({ page, request }) => {
  const s = (await (await request.post('/api/students', { data: { label: 'Student' } })).json()).id
  await request.put(`/api/students/${s}/target`, { data: { scheme_id: 'nsp-csss' } })
  await page.addInitScript(id => { try { localStorage.setItem('kaagaz.student', JSON.stringify({ id, scheme_id: 'nsp-csss' })) } catch { /* ignore */ } }, s)
  await page.goto('/#/chain')
  await expect(page.getByTestId('conditional')).toBeVisible()
  await expect(page.getByTestId('slip-disability-certificate')).toHaveCount(0)
  await page.getByTestId('applies-disability-certificate').click()
  await expect(page.getByTestId('applies-disability-certificate')).toHaveAttribute('aria-pressed', 'true')
  await expect(page.getByTestId('slip-disability-certificate')).toBeVisible()
  await page.getByTestId('applies-disability-certificate').click()
  await expect(page.getByTestId('slip-disability-certificate')).toHaveCount(0)
  await request.delete(`/api/students/${s}`)
})

test('"As on the submission day" counts from that date, says so, and switches back to today', async ({ page, request }) => {
  const health = await (await request.get('/api/health')).json()
  const snapshot: string = health.snapshot_date
  await page.addInitScript(d => { if (!sessionStorage.getItem('asof-set')) { localStorage.setItem('kaagaz.asOf', d); sessionStorage.setItem('asof-set', '1') } }, snapshot)
  const sid = await loadExample(page)
  await expect(page.getByTestId('as-of-bar')).toBeVisible()
  const ex = await (await request.get(`/api/students/${sid}`)).json()
  const scheme = ex.data.targets[0].scheme_id
  const r = await request.get(`/api/plan?student_id=${sid}&scheme_id=${scheme}&depth=1&remember=false`, { headers: { 'X-Kaagaz-As-Of': snapshot } })
  const asOfPlan = (await r.json()).data
  expect(asOfPlan.today).toBe(snapshot)
  await expect(page.getByTestId('stamp')).toContainText(asOfPlan.verdict.stamp)
  await expectNoSeriousA11y(page, 'chain as on the submission day')
  await page.getByTestId('as-of-off').click()
  await expect(page.getByTestId('as-of-bar')).toHaveCount(0)
  expect(await page.evaluate(() => localStorage.getItem('kaagaz.asOf'))).toBeNull()
  const today = await apiPlan(request, sid, scheme, 1)
  await expect(page.getByTestId('stamp')).toContainText(today.verdict.stamp)
})
