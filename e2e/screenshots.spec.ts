import { expect, test, type Page } from '@playwright/test'

// Saves every screen at 1440 px and 390 px, light and dark, into docs/screenshots/.
const OUT = '../docs/screenshots'
const VARIANTS = [
  { w: 1440, h: 900, theme: 'light' }, { w: 1440, h: 900, theme: 'dark' },
  { w: 390, h: 844, theme: 'light' }, { w: 390, h: 844, theme: 'dark' },
] as const

async function prep(page: Page, theme: string) {
  await page.addInitScript(t => { try { localStorage.setItem('kaagaz.theme', t) } catch { /* ignore */ } }, theme)
  await page.emulateMedia({ colorScheme: theme as 'light' | 'dark', reducedMotion: 'reduce' })
}

async function example(page: Page) {
  await page.goto('/#/')
  await page.getByTestId('load-example').click()
  await expect(page.getByTestId('stamp')).toBeVisible()
  await expect(page.getByTestId('alternatives')).toBeVisible()
}

for (const v of VARIANTS) {
  const tag = `${v.w}-${v.theme}`
  test.describe(`screens ${tag}`, () => {
    test.use({ viewport: { width: v.w, height: v.h } })

    test(`start ${tag}`, async ({ page }) => {
      await prep(page, v.theme)
      await page.goto('/#/')
      await page.locator('.scheme-opt').nth(1).click()
      await expect(page.locator('.hold').first()).toBeVisible()
      await page.screenshot({ path: `${OUT}/start-${tag}.png`, fullPage: true, animations: 'disabled' })
    })

    test(`chain ${tag}`, async ({ page }) => {
      await prep(page, v.theme)
      await example(page)
      await page.waitForTimeout(600)
      await page.screenshot({ path: `${OUT}/chain-depth1-${tag}.png`, fullPage: true, animations: 'disabled' })
      await page.getByTestId('depth-2').click()
      await page.waitForTimeout(600)
      await page.screenshot({ path: `${OUT}/chain-depth2-${tag}.png`, fullPage: true, animations: 'disabled' })
      await page.locator('[data-testid^="slip-"]').first().click()
      await expect(page.getByTestId('why-panel').getByTestId('why-source').first()).toBeVisible()
      await page.waitForTimeout(600) // the panel fades in over 200 ms
      await page.screenshot({ path: `${OUT}/why-${tag}.png`, animations: 'disabled' })
    })

    test(`late ${tag}`, async ({ page, request }) => {
      await prep(page, v.theme)
      const s = (await (await request.post('/api/students', { data: { label: 'Student' } })).json()).id
      await request.put(`/api/students/${s}/target`, { data: { scheme_id: 'ka-ssp-pms-obc' } })
      for (const d of ['aadhaar', 'bank-account', 'bank-account-aadhaar-seeded', 'sslc-marks-card', 'ssp-student-account', 'nsp-otr', 'university-registration-number', 'ssp-e-attested-documents', 'proof-of-identity', 'proof-of-residence']) {
        await request.post(`/api/students/${s}/holdings`, { data: { doc_id: d } })
      }
      await page.addInitScript(id => { try { localStorage.setItem('kaagaz.student', JSON.stringify({ id, scheme_id: 'ka-ssp-pms-obc' })) } catch { /* ignore */ } }, s)
      await page.goto('/#/chain')
      await expect(page.getByTestId('stamp')).toBeVisible()
      await expect(page.getByTestId('alternatives')).toBeVisible()
      await page.waitForTimeout(600)
      await page.screenshot({ path: `${OUT}/chain-late-${tag}.png`, fullPage: true, animations: 'disabled' })
      await request.delete(`/api/students/${s}`)
    })

    test(`ask ${tag}`, async ({ page }) => {
      await prep(page, v.theme)
      await page.goto('/#/ask')
      await page.getByTestId('ask-input').fill('Does PM YASASVI Top Class need a hostel certificate?')
      await page.getByTestId('ask-submit').click()
      await expect(page.getByTestId('ask-answer')).toBeVisible()
      await page.screenshot({ path: `${OUT}/ask-${tag}.png`, fullPage: true, animations: 'disabled' })
    })

    for (const [name, url] of [['benchmark', '/#/benchmark'], ['sources', '/#/sources'], ['graph', '/#/graph']] as const) {
      test(`${name} ${tag}`, async ({ page }) => {
        await prep(page, v.theme)
        await page.goto(url)
        await page.waitForLoadState('networkidle')
        await page.screenshot({ path: `${OUT}/${name}-${tag}.png`, fullPage: true, animations: 'disabled' })
      })
    }
  })
}
