import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const artifacts = fileURLToPath(new URL('../../artifacts/platform-cp1/browser/', import.meta.url))
export default defineConfig({
  testDir: './tests/browser', testMatch: '**/real-accounts.spec.ts', workers: 1,
  retries: 0, timeout: 60000,
  expect: { timeout: 15000 },
  reporter: [['list'], ['json', { outputFile: `${artifacts}/real-accounts.json` }]],
  outputDir: `${artifacts}/results`,
  use: { baseURL: 'http://127.0.0.1:5178', ...devices['Desktop Chrome'],
    channel: process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined),
    // Account tests contain credentials in request bodies: no network traces.
    trace: 'off', screenshot: 'only-on-failure' },
  webServer: { command: 'npm run dev -- --port 5178 --strictPort', url: 'http://127.0.0.1:5178',
    reuseExistingServer: false, env: { DEV_PLATFORM_ORIGIN: 'http://127.0.0.1:3002' } },
})
