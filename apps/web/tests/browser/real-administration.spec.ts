import { test,expect,type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { randomUUID } from 'node:crypto'
import type { Server } from 'node:http'
import { createApp } from '../../../../services/platform/src/app'
import { createPool } from '../../../../services/platform/src/database'
import { migrate,grantRuntime } from '../../../../services/platform/src/migrations'
import { provision } from '../../../../services/platform/src/administration'
import { PostgresStore } from '../../../../services/platform/src/store'
import { DatasetService } from '../../../../services/platform/src/datasets/service'

const cluster=createPool('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database='platform_cp5_'+randomUUID().replaceAll('-',''),adminEmail=process.env.DEPLOYMENT_ADMIN_EMAIL??'cp5-browser-admin@example.test',adminPassword=process.env.DEPLOYMENT_ADMIN_PASSWORD??'cp5-browser-admin-password'
let admin:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,server:Server|undefined,created=false
test.beforeAll(async()=>{
  if(process.env.DEPLOYMENT_ORIGIN){expect(process.env.DEPLOYMENT_ADMIN_EMAIL).toBeTruthy();expect(process.env.DEPLOYMENT_ADMIN_PASSWORD).toBeTruthy();return}
  expect((await cluster.query('SELECT current_user,current_database()')).rows[0]).toEqual({current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
  if(!/^platform_cp5_[a-f0-9]{32}$/.test(database))throw Error('Invalid fixture database')
  await cluster.query(`CREATE DATABASE "${database}"`);created=true
  admin=createPool(`postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/${database}`)
  await migrate(admin);await grantRuntime(admin,'platform-test-runtime-password-at-least-32-characters');await provision(admin,adminEmail,'Administration test',adminPassword)
  runtime=createPool(`postgresql://pharmacy_platform:platform-test-runtime-password-at-least-32-characters@127.0.0.1:55433/${database}`)
  const app=createApp(new PostgresStore(runtime),{origin:'http://127.0.0.1:5183',secureCookie:false,trustProxy:false},new DatasetService(runtime))
  server=await new Promise((resolve,reject)=>{const running=app.listen(3006,'127.0.0.1',()=>resolve(running));running.on('error',reject)})
})
test.afterAll(async()=>{if(server)server.closeAllConnections();if(server)await new Promise<void>((resolve,reject)=>server!.close(error=>error?reject(error):resolve()));await runtime?.end();await admin?.end();if(created)await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`);await cluster.end()})
async function login(page:Page,email=adminEmail,password=adminPassword){await page.goto('/connexion');await page.getByLabel('Adresse e-mail').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page).toHaveURL(/\/(?:espace|administration(?:\?[^#]*)?)$/);await expect(page.getByRole('button',{name:'Se déconnecter',exact:true})).toBeVisible()}
async function register(page:Page,email:string){await page.goto('/inscription');await page.getByLabel('Nom affiché').fill('Analyste CP5');await page.getByLabel('Adresse e-mail').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill('cp5-browser-analyst-password');await page.getByRole('button',{name:'Créer mon compte'}).click();await expect(page).toHaveURL(/\/espace$/)}
async function mutation(page:Page,path:string,body:unknown,method='POST'){
  const session=await (await page.request.get('/platform-api/auth/session')).json()
  return page.request.fetch('/platform-api'+path,{method,headers:{Origin:new URL(page.url()).origin,'X-CSRF-Token':session.csrfToken},data:body})
}
async function selectUser(page:Page,email:string){await page.goto('/administration?tab=users');await page.getByLabel('Rechercher un compte').fill(email);await page.getByRole('button',{name:'Rechercher les utilisateurs'}).click();await page.getByRole('button',{name:'Gérer '+email,exact:true}).click()}
async function confirmPermissions(page:Page){await page.getByRole('button',{name:'Vérifier la modification des droits'}).click();await Promise.all([page.waitForResponse(response=>response.url().endsWith('/permissions')&&response.request().method()==='PATCH'),page.getByRole('button',{name:'Confirmer les droits et déconnecter les sessions'}).click()])}

test('administrator manages accounts with last-admin, confirmation and immediate session boundaries',async({page,browser},info)=>{
  const analystContext=await browser.newContext(),analyst=await analystContext.newPage(),email='cp5-account-'+randomUUID()+'@example.test'
  try{
    await register(analyst,email)
    const analystId=(await (await analyst.request.get('/platform-api/auth/session')).json()).user.id
    expect((await analyst.request.get('/platform-api/admin/overview')).status()).toBe(403)
    await analyst.goto('/administration');await expect(analyst.getByRole('heading',{name:'Accès non autorisé'})).toBeVisible()
    await login(page);await page.getByRole('link',{name:'Administration',exact:true}).click();await expect(page.getByRole('heading',{name:'Vue globale'})).toBeVisible()
    await selectUser(page,adminEmail);await page.getByLabel('Nouveau rôle').selectOption('analyst');await confirmPermissions(page)
    await expect(page.getByRole('alert')).toContainText('dernier administrateur actif')
    await page.getByRole('button',{name:'Fermer sans modifier'}).click()
    await selectUser(page,email);await page.getByLabel('Compte actif',{exact:true}).uncheck()
    await page.getByRole('button',{name:'Vérifier la modification des droits'}).click()
    expect((await (await analyst.request.get('/platform-api/auth/session')).json()).user.id).toBe(analystId) // confirmation is still pending
    await page.getByRole('button',{name:'Confirmer les droits et déconnecter les sessions'}).click()
    await expect(page.getByRole('heading',{name:'Modifier les droits de '+email})).toHaveCount(0)
    expect((await (await analyst.request.get('/platform-api/auth/session')).json()).user).toBeNull()
    await selectUser(page,email);await page.getByLabel('Compte actif',{exact:true}).check();await confirmPermissions(page)
    await login(analyst,email,'cp5-browser-analyst-password')
    await selectUser(page,email);await page.getByLabel('Nouveau rôle').selectOption('admin');await confirmPermissions(page)
    expect((await (await analyst.request.get('/platform-api/auth/session')).json()).user).toBeNull()
    await login(analyst,email,'cp5-browser-analyst-password');await analyst.goto('/administration');await expect(analyst.getByRole('heading',{name:'Vue globale'})).toBeVisible()
    await selectUser(page,adminEmail);await page.getByLabel('Nouveau rôle').selectOption('analyst');await confirmPermissions(page)
    await expect(page).toHaveURL(/\/connexion$/)
    await selectUser(analyst,adminEmail);await analyst.getByLabel('Nouveau rôle').selectOption('admin');await confirmPermissions(analyst)
    await login(page);await selectUser(page,email);await page.getByLabel('Nouveau rôle').selectOption('analyst');await confirmPermissions(page)
    await page.goto('/administration?tab=activity');await page.getByRole('combobox',{name:'Action',exact:true}).selectOption('account.permissions_changed');await page.getByLabel('Identifiant de la ressource').fill(analystId);await page.getByRole('button',{name:'Filtrer l’activité'}).click()
    await expect(page.getByRole('heading',{name:'Droits du compte modifiés'}).first()).toBeVisible()
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
    await page.screenshot({path:info.outputPath('administration-accounts-activity-desktop.png'),fullPage:true})
    await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
    await page.screenshot({path:info.outputPath('administration-activity-mobile.png'),fullPage:true})
  }finally{await analystContext.close()}
})

test('dataset supervision requires logged inspection; suspension blocks shared results and restores only valid access',async({page,browser},info)=>{
  const ownerContext=await browser.newContext(),owner=await ownerContext.newPage(),email='cp5-data-'+randomUUID()+'@example.test'
  try{
    await register(owner,email)
    const csv='id,amount,private_note\n'+Array.from({length:31},(_,i)=>`${String(i+1).padStart(3,'0')},${i+1},synthetic-private-cell-${i+1}`).join('\n')+'\n'
    const session=await (await owner.request.get('/platform-api/auth/session')).json(),headers={Origin:new URL(owner.url()).origin,'X-CSRF-Token':session.csrfToken}
    const uploaded=await owner.request.post('/platform-api/imports',{headers:{...headers,'Content-Type':'application/octet-stream','X-Filename':'cp5.csv'},data:Buffer.from(csv)});expect(uploaded.status()).toBe(201)
    const upload=await uploaded.json(),preview=await (await owner.request.get('/platform-api/imports/'+upload.id)).json(),{columns,...options}=preview.configuration
    const validation=await (await mutation(owner,'/imports/'+upload.id+'/validate',{revision:0,options,columns})).json()
    const published=await mutation(owner,'/imports/'+upload.id+'/publish',{revision:validation.revision,metadata:{title:'CP5 supervised dataset '+randomUUID(),description:'Synthetic fixture',category:'Tests',source:'Synthetic source',observationDate:null}});expect(published.status()).toBe(201)
    const source=await published.json(),widgetId=randomUUID(),definition={kind:'aggregate',source,measures:[{operation:'rows'}],chart:'kpi'}
    const saved=await mutation(owner,'/dashboards',{title:'CP5 dependent dashboard',configuration:{widgets:[{id:widgetId,title:'Supervised rows',definition}]}});expect(saved.status()).toBe(201)
    const dashboard=(await saved.json()).dashboard
    expect((await mutation(owner,'/dashboards/'+dashboard.id+'/shares',{email:adminEmail})).status()).toBe(201)
    await login(page)
    const metadata=await page.request.get('/platform-api/admin/datasets/'+source.datasetId);expect(metadata.status()).toBe(200);expect(await metadata.text()).not.toContain('synthetic-private-cell-')
    let inspections=0;page.on('request',req=>{if(req.url().endsWith('/inspect'))inspections++})
    await page.goto('/administration?tab=datasets&dataset='+source.datasetId)
    await expect(page.getByRole('heading',{name:'Inspection explicite du contenu'})).toBeVisible();expect(inspections).toBe(0)
    await page.getByLabel('Motif de l’inspection').fill('Contrôle de qualité du dataset')
    await Promise.all([page.waitForEvent('dialog').then(d=>d.dismiss()),page.getByRole('button',{name:'Confirmer et inspecter le contenu'}).click()]);expect(inspections).toBe(0)
    await Promise.all([page.waitForEvent('dialog').then(d=>d.accept()),page.getByRole('button',{name:'Confirmer et inspecter le contenu'}).click()])
    await expect(page.getByRole('region',{name:'Contenu inspecté'})).toContainText('synthetic-private-cell-1');expect(inspections).toBe(1)
    await Promise.all([page.waitForEvent('dialog').then(d=>d.accept()),page.getByRole('region',{name:'Contenu inspecté'}).locator('..').getByRole('button',{name:'Page suivante',exact:true}).click()])
    await expect(page.getByRole('region',{name:'Contenu inspecté'})).toContainText('synthetic-private-cell-31');expect(inspections).toBe(2)
    await page.getByLabel('Motif de la décision').fill('Suspendu pour contrôle administratif');await page.getByRole('button',{name:'Vérifier la décision'}).click();await page.getByRole('button',{name:'Confirmer la suspension',exact:true}).click()
    await expect(page.getByText('Suspendu',{exact:true})).toBeVisible()
    await owner.goto('/donnees/'+source.datasetId);await expect(owner.getByRole('alert')).toContainText('dataset suspendu')
    expect((await mutation(owner,'/dashboards/'+dashboard.id+'/widgets/'+widgetId+'/execute',{revision:1,values:[]})).status()).toBe(423)
    expect((await mutation(page,'/dashboards/'+dashboard.id+'/widgets/'+widgetId+'/execute',{revision:1,values:[]})).status()).toBe(423)
    await owner.goto('/tableaux/'+dashboard.id)
    await expect(owner.getByRole('alert')).toContainText('Source indisponible')
    const ownerCurrent=await (await owner.request.get('/platform-api/auth/session')).json()
    expect((await owner.request.get('/platform-api/admin/datasets')).status()).toBe(403)
    // Independent failed inspection clears old cells and leaves a retryable draft.
    await page.getByLabel('Motif de l’inspection').fill('Inspection pendant suspension')
    await page.route('**/platform-api/admin/datasets/*/versions/*/inspect',route=>route.fulfill({status:503,json:{error:{code:'platform_unavailable',message:'Inspection temporairement indisponible.'}}}),{times:1})
    await Promise.all([page.waitForEvent('dialog').then(d=>d.accept()),page.getByRole('button',{name:'Confirmer et inspecter le contenu'}).click()]);await expect(page.getByRole('alert')).toContainText('Inspection temporairement indisponible')
    await expect(page.getByRole('region',{name:'Contenu inspecté'})).toHaveCount(0)
    await expect(page.getByLabel('Motif de l’inspection')).toHaveValue('Inspection pendant suspension')
    await Promise.all([page.waitForEvent('dialog').then(d=>d.accept()),page.getByRole('button',{name:'Confirmer et inspecter le contenu'}).click()]);await expect(page.getByRole('region',{name:'Contenu inspecté'})).toBeVisible()
    expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
    await page.screenshot({path:info.outputPath('administration-suspended-inspection.png'),fullPage:true})
    await page.getByLabel('Motif de la décision').fill('Contrôle terminé, utilisation rétablie');await page.getByRole('button',{name:'Vérifier la décision'}).click();await page.getByRole('button',{name:'Confirmer le rétablissement',exact:true}).click();await expect(page.getByText('Non suspendu',{exact:true})).toBeVisible()
    expect((await mutation(owner,'/dashboards/'+dashboard.id+'/widgets/'+widgetId+'/execute',{revision:1,values:[]})).status()).toBe(200)
    await page.goto('/tableaux/'+dashboard.id);await expect(page.getByText('Supervised rows',{exact:true}).first()).toBeVisible()
    await page.goto('/administration?tab=activity');await page.getByRole('combobox',{name:'Action',exact:true}).selectOption('dataset.inspected');await page.getByLabel('Identifiant de l’acteur').fill((await (await page.request.get('/platform-api/auth/session')).json()).user.id);await page.getByLabel('Identifiant de la ressource').fill(source.datasetId);await page.getByRole('button',{name:'Filtrer l’activité'}).click()
    await expect(page.getByRole('heading',{name:'Contenu inspecté'}).first()).toBeVisible()
    expect(await page.locator('main').innerText()).not.toContain('synthetic-private-cell-')
    expect(ownerCurrent.user.email).toBe(email)
  }finally{await ownerContext.close()}
})
