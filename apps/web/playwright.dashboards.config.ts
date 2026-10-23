import { defineConfig,devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
const artifacts=fileURLToPath(new URL('../../artifacts/platform-cp4/browser/',import.meta.url))
export default defineConfig({
  testDir:'./tests/browser',testMatch:'**/real-dashboards.spec.ts',workers:1,retries:0,timeout:240000,expect:{timeout:15000},
  reporter:[['list'],['json',{outputFile:`${artifacts}/dashboards.json`}]],outputDir:`${artifacts}/results`,
  use:{actionTimeout:15000,baseURL:process.env.DEPLOYMENT_ORIGIN??'http://127.0.0.1:5182',...devices['Desktop Chrome'],channel:process.env.PLAYWRIGHT_CHANNEL??(process.platform==='win32'?'msedge':undefined),trace:'off',screenshot:'only-on-failure'},
  webServer:process.env.DEPLOYMENT_ORIGIN?undefined:{command:'npm run dev -- --port 5182 --strictPort',url:'http://127.0.0.1:5182',reuseExistingServer:false,env:{DEV_PLATFORM_ORIGIN:'http://127.0.0.1:3005'}},
})
