// Phase 0 static review only. Uses existing Playwright; no server, API or storage.
import { createRequire } from 'node:module';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
const out = dirname(fileURLToPath(import.meta.url));
const require = createRequire(resolve(out, '../../..', 'apps/web/package.json'));
const { chromium } = require('@playwright/test');
let AxeBuilder; try { AxeBuilder = require('@axe-core/playwright').default; } catch {}
await mkdir(resolve(out, 'screenshots'), { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const report = { kind: 'isolated static fixtures; no production or API verification', captures: [], interactions: [], externalRequests: [], errors: [], accessibility: [] };
for (const direction of ['a', 'b', 'c']) {
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  await context.route(/^https?:/, route => { report.externalRequests.push(route.request().url()); return route.abort(); });
  const page = await context.newPage();
  page.on('pageerror', error => report.errors.push({ direction, message: error.message }));
  for (const view of ['analysis', 'dashboard', 'assistant', 'system']) {
    for (const [label, width, height] of [['desktop',1440,1000], ['mobile',390,844], ['narrow',320,720], ['tablet',768,1024]]) {
      await page.setViewportSize({ width, height });
      await page.goto(pathToFileURL(resolve(out, `direction-${direction}.html`)).href + `?view=${view}`);
      await page.evaluate(() => document.fonts.ready);
      const metrics = await page.evaluate(() => ({
        documentWidth: document.documentElement.scrollWidth, viewport: innerWidth,
        heading: document.querySelector('h1')?.textContent,
        horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        smallText: [...document.querySelectorAll('main *')].filter(el => el.children.length === 0 && el.textContent.trim() && el.getBoundingClientRect().height > 0 && parseFloat(getComputedStyle(el).fontSize) < 12).map(el => ({text:el.textContent.trim().slice(0,50),size:getComputedStyle(el).fontSize})),
        tables: [...document.querySelectorAll('table')].map(el=>({width:el.getBoundingClientRect().width,scrollRegion:el.parentElement.scrollWidth>el.parentElement.clientWidth})),
      }));
      const file = `screenshots/${direction}-${view}-${label}.png`;
      if (label === 'desktop' || label === 'mobile') await page.screenshot({path:resolve(out,file),fullPage:true});
      report.captures.push({direction,view,label,width,height,...metrics,screenshot:['desktop','mobile'].includes(label)?file:null});
      if (AxeBuilder && ['desktop','mobile'].includes(label)) {
        const result = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
        report.accessibility.push({direction,view,label,violations:result.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))}))});
      }
    }
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(pathToFileURL(resolve(out, `direction-${direction}.html`)).href + '?view=analysis');
  const parameterButton=page.getByRole('button',{name:/^Paramètres$/});
  if(await parameterButton.count()) await parameterButton.click();
  const selects = page.locator('main select:visible');
  for (let i=0;i<await selects.count();i++) {
    const values=await selects.nth(i).locator('option').evaluateAll(els=>els.map(el=>el.value));
    if(values.length>1){await selects.nth(i).selectOption(values[1]);break;}
  }
  const link=page.locator('a[href*="view=dashboard"]').first();
  if(await link.count()){
    await link.click();
    const opened=await page.locator('dialog[open]').count();
    if(opened){
      await page.getByRole('button',{name:/Rester/}).click();
      const stayed=page.url().includes('view=analysis');
      await link.click();
      await page.getByRole('button',{name:/Abandonner/}).click();
      await page.waitForURL(/view=dashboard/);
      report.interactions.push({direction,warning:true,stayRetainsView:stayed,discardNavigates:true});
    }else report.interactions.push({direction,warning:false});
  }else report.interactions.push({direction,note:'navigation label differs; manual check required'});
  await context.close();
}
await browser.close();
await writeFile(resolve(out,'browser-verification.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({captures:report.captures.length,screenshots:report.captures.filter(x=>x.screenshot).length,overflow:report.captures.filter(x=>x.horizontalOverflow),smallText:report.captures.filter(x=>x.smallText.length).map(x=>({direction:x.direction,view:x.view,label:x.label,smallText:x.smallText})),errors:report.errors,externalRequests:report.externalRequests,accessibility:report.accessibility.filter(x=>x.violations.length),interactions:report.interactions},null,2));
