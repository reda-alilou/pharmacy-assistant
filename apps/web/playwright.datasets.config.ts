import { defineConfig,devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
const artifacts=fileURLToPath(new URL('../../artifacts/platform-cp2/browser/',import.meta.url))
export default defineConfig({
  testDir:'./tests/browser',testMatch:'**/real-datasets.spec.ts',workers:1,retries:0,timeout:120000,expect:{timeout:15000},
  reporter:[['list'],['json',{outputFile:`${artifacts}/datasets.json`}]],outputDir:`${artifacts}/results`,
  use:{actionTimeout:15000,baseURL:process.env.DEPLOYMENT_ORIGIN??'http://127.0.0.1:5179',...devices['Desktop Chrome'],channel:process.env.PLAYWRIGHT_CHANNEL??(process.platform==='win32'?'msedge':undefined),trace:'off',screenshot:'only-on-failure'},
  webServer:process.env.DEPLOYMENT_ORIGIN?undefined:{command:'npm run dev -- --port 5179 --strictPort',url:'http://127.0.0.1:5179',reuseExistingServer:false,env:{DEV_PLATFORM_ORIGIN:'http://127.0.0.1:3003'}},
})
