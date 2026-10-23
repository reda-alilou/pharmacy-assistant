import { defineConfig,devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
const artifacts=fileURLToPath(new URL('../../artifacts/platform-cp3/browser/',import.meta.url))
export default defineConfig({
  testDir:'./tests/browser',testMatch:'**/real-analytics.spec.ts',workers:1,retries:0,timeout:180000,expect:{timeout:15000},
  reporter:[['list'],['json',{outputFile:`${artifacts}/analytics.json`}]],outputDir:`${artifacts}/results`,
  use:{actionTimeout:15000,baseURL:process.env.DEPLOYMENT_ORIGIN??'http://127.0.0.1:5181',...devices['Desktop Chrome'],channel:process.env.PLAYWRIGHT_CHANNEL??(process.platform==='win32'?'msedge':undefined),trace:'off',screenshot:'only-on-failure'},
  webServer:process.env.DEPLOYMENT_ORIGIN?undefined:{command:'npm run dev -- --port 5181 --strictPort',url:'http://127.0.0.1:5181',reuseExistingServer:false,env:{DEV_PLATFORM_ORIGIN:'http://127.0.0.1:3004'}},
})
