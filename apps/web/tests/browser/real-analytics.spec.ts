import { test,expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { randomUUID } from 'node:crypto'
import type { Server } from 'node:http'
import { createApp } from '../../../../services/platform/src/app'
import { createPool } from '../../../../services/platform/src/database'
import { migrate,grantRuntime } from '../../../../services/platform/src/migrations'
import { PostgresStore } from '../../../../services/platform/src/store'
import { DatasetService } from '../../../../services/platform/src/datasets/service'
import { columnId } from '../../../../services/platform/src/datasets/csv'

const cluster=createPool('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database='platform_cp3_'+randomUUID().replaceAll('-','')
let admin:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,server:Server|undefined,created=false
test.beforeAll(async()=>{
  if(process.env.DEPLOYMENT_ORIGIN)return
  expect((await cluster.query('SELECT current_user,current_database()')).rows[0]).toEqual({current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
  if(!/^platform_cp3_[a-f0-9]{32}$/.test(database))throw new Error('Invalid test identity')
  await cluster.query(`CREATE DATABASE "${database}"`);created=true
  admin=createPool(`postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/${database}`)
  await migrate(admin);await grantRuntime(admin,'platform-test-runtime-password-at-least-32-characters')
  runtime=createPool(`postgresql://pharmacy_platform:platform-test-runtime-password-at-least-32-characters@127.0.0.1:55433/${database}`)
  const app=createApp(new PostgresStore(runtime),{origin:'http://127.0.0.1:5181',secureCookie:false,trustProxy:false},new DatasetService(runtime))
  server=await new Promise((resolve,reject)=>{const listening=app.listen(3004,'127.0.0.1',()=>resolve(listening));listening.on('error',reject)})
})
test.afterAll(async()=>{if(server)server.closeAllConnections();if(server)await new Promise<void>((resolve,reject)=>server!.close(error=>error?reject(error):resolve()));await runtime?.end();await admin?.end();if(created)await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`);await cluster.end()})
async function register(page:Page,email:string){await page.goto('/inscription');await page.getByLabel('Nom affiché').fill('Analyste calcul');await page.getByLabel('Adresse e-mail').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill('analytics-browser-password');await page.getByRole('button',{name:'Créer mon compte'}).click();await expect(page).toHaveURL(/\/espace$/)}
async function importCsv(page:Page,csv:string,title:string,target?:string){
  const origin=new URL(page.url()).origin,session=await (await page.request.get('/platform-api/auth/session')).json()
  const headers={'Origin':origin,'X-CSRF-Token':session.csrfToken}
  const upload=await page.request.post('/platform-api/imports',{data:Buffer.from(csv),headers:{...headers,'Content-Type':'application/octet-stream','X-Filename':'analytics.csv'}});expect(upload.status()).toBe(201)
  const uploaded=await upload.json(),preview=await (await page.request.get('/platform-api/imports/'+uploaded.id)).json()
  const{columns,...options}=preview.configuration
  const validation=await page.request.post(`/platform-api/imports/${uploaded.id}/validate`,{data:{revision:0,options,columns},headers});expect(validation.status()).toBe(200)
  const validated=await validation.json();expect(validated.validation.valid).toBe(true)
  const published=await page.request.post(`/platform-api/imports/${uploaded.id}/publish`,{data:{revision:validated.revision,metadata:{title,description:'Synthetic browser fixture',category:'Tests',source:'Synthetic',observationDate:null},...(target?{datasetId:target}:{})},headers});expect(published.status()).toBe(201)
  return await published.json() as {datasetId:string;versionId:string}
}
async function run(page:Page){await page.getByRole('button',{name:'Calculer l’analyse',exact:true}).click();await expect(page.getByRole('heading',{name:'Résultats de l’analyse',exact:true})).toBeVisible()}
const fixture='id,group,amount,second,empty,day,form,ppv_price_mad,recorded_conflicts,source\n'+[
  '001,A,0,10,,2026-01-01,Tablet,0,0,Alpha','002,A,1,11,,2026-01-02,Tablet,1,1,Alpha','003,A,2,12,,2026-02-01,Tablet,2,0,Beta',
  '004,A,3,13,,2026-02-02,Tablet,3,0,Beta','005,A,100,110,,2026-03-01,Tablet,100,2,Alpha','006,A,,14,,2026-03-02,Tablet,,0,Beta',
  '007,B,4,14,,2026-01-03,Capsule,4,0,Alpha','008,B,4,14,,2026-02-03,Capsule,4,0,Beta','009,B,4,14,,2026-03-03,Capsule,4,0,Alpha',
  '010,B,4,14,,2026-03-04,Capsule,4,0,Beta','011,C,5,15,,2026-03-05,Syrup,5,0,Alpha','012,C,,16,,2026-03-06,Syrup,,0,Beta',
].join('\n')+'\n'

test('aggregation → private save/reopen → all four advanced features; accessible and version-pinned',async({page,context},info)=>{
  await register(page,'analytics-browser@example.test')
  const first=await importCsv(page,fixture,'Golden analytics')
  await page.goto(`/analyses/nouvelle?dataset=${first.datasetId}&version=${first.versionId}`)
  await page.getByLabel('Opération de la mesure 1',{exact:true}).selectOption('mean')
  await page.getByLabel('Colonne de la mesure 1',{exact:true}).selectOption(columnId('amount'))
  await page.getByLabel('Groupe 1',{exact:true}).selectOption(columnId('form'))
  await page.getByLabel('Visualisation',{exact:true}).selectOption('bar')
  await run(page)
  const aggregates=page.getByRole('region',{name:'Agrégats exacts du serveur',exact:true})
  await expect(aggregates).toContainText('Moyenne')
  await expect(aggregates).toContainText('21.2')
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('analytics-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('analytics-mobile.png'),fullPage:true});await page.setViewportSize({width:1280,height:900})
  await page.getByLabel('Titre de l’analyse',{exact:true}).fill('Analyse épinglée')
  let releaseSave!:()=>void;const gate=new Promise<void>(resolve=>{releaseSave=resolve})
  await page.route('**/platform-api/analyses',async route=>{if(route.request().method()!=='POST'){await route.continue();return}const response=await route.fetch();await gate;await route.fulfill({response})})
  await page.getByRole('button',{name:'Enregistrer l’analyse',exact:true}).click()
  try{await expect(page.getByLabel('Titre de l’analyse',{exact:true})).toBeDisabled();await expect(page.getByLabel('Type d’analyse',{exact:true})).toBeDisabled()}finally{releaseSave()}
  await expect(page).toHaveURL(/\/analyses\/[a-f0-9-]{36}$/);await page.unroute('**/platform-api/analyses')
  const savedUrl=page.url()
  const second=await importCsv(page,'id,amount\n001,20\n','Version 2',first.datasetId)
  const duplicates=await importCsv(page,'id,amount\n001,1\n001,2\n','Duplicate keys',first.datasetId)
  await page.reload();await expect(page.getByLabel('Version (Source)',{exact:true})).toHaveValue(first.versionId);await run(page);await expect(page.getByRole('region',{name:'Agrégats exacts du serveur',exact:true})).toContainText('21.2')
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('missing')
  await page.getByRole('checkbox',{name:/^id ·/}).uncheck();await page.getByRole('checkbox',{name:/^amount ·/}).check()
  await page.getByLabel('Groupe comparable',{exact:true}).selectOption(columnId('group'))
  await run(page);await expect(page.getByRole('region',{name:'Complétude par groupe',exact:true})).toContainText('16,67 %');await expect(page.getByRole('region',{name:'Lignes affectées · valeurs interprétées et originales',exact:true}).locator('tbody tr')).toHaveCount(2)
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('outliers');await page.getByLabel('Groupe comparable',{exact:true}).selectOption(columnId('group'));await run(page)
  await expect(page.getByRole('region',{name:'Seuils IQR par groupe',exact:true})).toContainText('IQR nul')
  await expect(page.getByRole('region',{name:'Lignes affectées · valeurs interprétées et originales',exact:true}).locator('tbody tr')).toHaveCount(1)
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('recommend');await page.getByRole('checkbox',{name:/^form ·/}).check();await run(page)
  await page.getByRole('button',{name:'Créer cette configuration : Mesure par catégorie',exact:true}).click();await expect(page.getByLabel('Type d’analyse',{exact:true})).toHaveValue('aggregate');await expect(page.getByLabel('Visualisation',{exact:true})).toHaveValue('bar')
  await page.getByLabel('Unité',{exact:true}).fill('MAD');await run(page)
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('compare')
  await page.getByLabel('Version (Droite)',{exact:true}).selectOption(second.versionId)
  await page.getByRole('button',{name:'Ajouter une correspondance (Correspondances statistiques)',exact:true}).click()
  await page.getByLabel('Correspondances statistiques · gauche 1',{exact:true}).selectOption(columnId('amount'));await page.getByLabel('Correspondances statistiques · droite 1',{exact:true}).selectOption(columnId('amount'))
  await page.getByRole('button',{name:'Ajouter une correspondance (Clés uniques de comparaison (facultatif))',exact:true}).click()
  await page.getByLabel('Clés uniques de comparaison (facultatif) · gauche 1',{exact:true}).selectOption(columnId('id'));await page.getByLabel('Clés uniques de comparaison (facultatif) · droite 1',{exact:true}).selectOption(columnId('id'))
  await run(page);await expect(page.getByRole('region',{name:'Différences par clé unique',exact:true})).toContainText('Modifiée')
  await page.getByLabel('Version (Droite)',{exact:true}).selectOption(duplicates.versionId);await page.getByRole('button',{name:'Calculer l’analyse',exact:true}).click();await expect(page.getByRole('alert')).toContainText('complètes et uniques');await expect(page.getByRole('heading',{name:'Résultats de l’analyse',exact:true})).toHaveCount(0)
  const otherContext=await context.browser()!.newContext(),other=await otherContext.newPage();await register(other,'analytics-other@example.test');await other.goto(savedUrl);await expect(other.getByRole('alert')).toContainText('introuvable');await otherContext.close()
  await page.getByRole('link',{name:'Mes analyses',exact:true}).click();await page.getByRole('link',{name:'Analyse épinglée',exact:true}).click()
  await page.getByRole('button',{name:'Supprimer cette analyse',exact:true}).click();await page.getByRole('button',{name:'Confirmer la suppression de l’analyse',exact:true}).click();await expect(page).toHaveURL(/\/analyses$/)
})

test('histogram/scatter preserve large exact decimals; templates use the same engine',async({page},info)=>{
  await register(page,'analytics-charts@example.test')
  const exact=await importCsv(page,'id,x,y\n001,90071992547409931234567890.01,0\n002,90071992547409931234567890.03,2\n','Exact decimals')
  await page.goto(`/analyses/nouvelle?dataset=${exact.datasetId}&version=${exact.versionId}`)
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('histogram');await page.getByLabel('Colonne numérique',{exact:true}).selectOption(columnId('x'));await page.getByLabel('Nombre d’intervalles',{exact:true}).fill('2');await run(page)
  await expect(page.getByRole('region',{name:'Intervalles de distribution',exact:true})).toContainText('90071992547409931234567890.01')
  await page.getByLabel('Recherche (Source)',{exact:true}).fill('aucune-observation');await run(page);await expect(page.getByText('Aucune valeur présente à représenter dans la distribution.',{exact:true})).toBeVisible();await page.getByLabel('Recherche (Source)',{exact:true}).fill('')
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('scatter');await run(page);await expect(page.getByRole('region',{name:'Paires numériques exactes',exact:true})).toContainText('90071992547409931234567890.03')
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([]);await page.screenshot({path:info.outputPath('scatter-exact.png'),fullPage:true})
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('aggregate');await page.getByLabel('Groupe 1',{exact:true}).selectOption(columnId('id'));await page.getByLabel('Visualisation',{exact:true}).selectOption('pie');await run(page)
  await expect(page.getByRole('img',{name:'Lignes · 2 contributions',exact:true})).toBeVisible()
  await page.getByLabel('Groupe 1',{exact:true}).selectOption('');await page.getByLabel('Visualisation',{exact:true}).selectOption('kpi');await page.getByLabel('Unité',{exact:true}).fill('MAD');await run(page);await expect(page.getByLabel('Indicateurs',{exact:true})).toContainText('2,00');await expect(page.getByLabel('Indicateurs',{exact:true})).not.toContainText('MAD')
  await expect(page.getByRole('button',{name:'Appliquer le modèle : Distribution des prix publics',exact:true})).toBeDisabled()
  await page.getByLabel('Recherche (Source)',{exact:true}).fill('ancien-périmètre')
  const pharmaceutical=await importCsv(page,fixture,'Pharmaceutical templates')
  await page.getByRole('button',{name:'Actualiser les sources (Source)',exact:true}).click()
  await page.getByLabel('Jeu de données (Source)',{exact:true}).selectOption(pharmaceutical.datasetId);await page.getByLabel('Version (Source)',{exact:true}).selectOption(pharmaceutical.versionId)
  await expect(page.getByLabel('Recherche (Source)',{exact:true})).toHaveValue('')
  await page.getByLabel('Type d’analyse',{exact:true}).selectOption('aggregate');await page.getByLabel('Groupe 1',{exact:true}).selectOption(columnId('day'));await page.getByLabel('Regroupement de Groupe 1',{exact:true}).selectOption('month');await page.getByLabel('Visualisation',{exact:true}).selectOption('line');await run(page)
  await expect(page.getByRole('img',{name:'Lignes · première mesure',exact:true})).toBeVisible();expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.getByRole('button',{name:'Appliquer le modèle : Désaccords entre sources',exact:true}).click();await run(page);await expect(page.getByRole('region',{name:'Agrégats exacts du serveur',exact:true})).toContainText('Alpha')
  await expect(page.getByText('2 lignes après filtrage',{exact:false})).toBeVisible()
})
