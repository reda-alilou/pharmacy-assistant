import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'

const artifacts = fileURLToPath(new URL('../../artifacts/web/', import.meta.url))

export default defineConfig({
  testDir: './tests/browser', fullyParallel: true, forbidOnly: !!process.env.CI, retries: 0,
  testIgnore: ['**/real-accounts.spec.ts','**/real-datasets.spec.ts','**/real-analytics.spec.ts','**/real-dashboards.spec.ts'],
  workers: 2, reporter: [['list'], ['json', { outputFile: `${artifacts}/browser-tests.json` }]],
  outputDir: `${artifacts}/results`,
  use: { baseURL: 'http://127.0.0.1:5177', trace: 'retain-on-failure', screenshot: 'only-on-failure', ...devices['Desktop Chrome'],
    channel: process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined) },
  webServer: process.env.DEPLOYMENT_ORIGIN ? undefined : { command: 'npm run dev -- --port 5177 --strictPort', url: 'http://127.0.0.1:5177', reuseExistingServer: false },
})
