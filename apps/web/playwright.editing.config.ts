import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
const artifacts = fileURLToPath(new URL('../../artifacts/redesign/phase-1/', import.meta.url))
export default defineConfig({
  testDir: './tests/browser', testMatch: ['**/editing.spec.ts','**/accounts.spec.ts','**/datasets.spec.ts','**/chat.spec.ts'],
  workers: 2, retries: 0, timeout: 45000, expect: { timeout: 10000 },
  reporter: [['list'], ['json', { outputFile: artifacts + '/browser-tests.json' }]], outputDir: artifacts + '/results',
  use: { baseURL: 'http://127.0.0.1:5190', ...devices['Desktop Chrome'], channel: process.platform === 'win32' ? 'msedge' : undefined, viewport: { width: 1440, height: 1000 }, trace: 'off', screenshot: 'only-on-failure' },
  // Frontend only. Tests intercept every platform/assistant request locally.
  webServer: { command: 'npm run dev -- --port 5190 --strictPort', url: 'http://127.0.0.1:5190', reuseExistingServer: true },
})
