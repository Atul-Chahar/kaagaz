import { defineConfig } from '@playwright/test'

// The e2e suite runs against the real API (which serves the built frontend) and a real FalkorDB.
const PORT = Number(process.env.KAAGAZ_E2E_PORT ?? 8010)

export default defineConfig({
  testDir: '.',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: { baseURL: `http://127.0.0.1:${PORT}`, trace: 'retain-on-failure' },
  webServer: {
    command: `cd ../backend && uv run uvicorn kaagaz.api:app --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
    env: { FALKORDB_HOST: process.env.FALKORDB_HOST ?? 'localhost', FALKORDB_PORT: process.env.FALKORDB_PORT ?? '6380',
           LLM_PROVIDER: '', LLM_API_KEY: '', LLM_MODEL: '', LLM_BASE_URL: '' },
  },
})
