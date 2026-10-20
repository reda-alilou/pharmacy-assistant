import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests', fullyParallel: true, forbidOnly: !!process.env.CI, retries: 0,
  workers: 2, reporter: [['list'], ['json', { outputFile: '../reports/architecture_checkpoint5_browser_tests.json' }]],
  outputDir: '../tmp/checkpoint5-playwright',
  use: { baseURL: 'http://127.0.0.1:5177', trace: 'retain-on-failure', screenshot: 'only-on-failure', ...devices['Desktop Chrome'],
    channel: process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined) },
  webServer: process.env.DEPLOYMENT_ORIGIN ? undefined : { command: 'npm run dev -- --port 5177 --strictPort', url: 'http://127.0.0.1:5177', reuseExistingServer: false },
})
