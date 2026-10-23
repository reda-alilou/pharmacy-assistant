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
const database='platform_cp4_'+randomUUID().replaceAll('-','')
let admin:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,server:Server|undefined,created=false
test.beforeAll(async()=>{
  if(process.env.DEPLOYMENT_ORIGIN)return
  expect((await cluster.query('SELECT current_user,current_database()')).rows[0]).toEqual({current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
  if(!/^platform_cp4_[a-f0-9]{32}$/.test(database))throw new Error('Invalid test identity')
  await cluster.query(`CREATE DATABASE "${database}"`);created=true
  admin=createPool(`postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/${database}`)
  await migrate(admin);await grantRuntime(admin,'platform-test-runtime-password-at-least-32-characters')
  runtime=createPool(`postgresql://pharmacy_platform:platform-test-runtime-password-at-least-32-characters@127.0.0.1:55433/${database}`)
  const app=createApp(new PostgresStore(runtime),{origin:'http://127.0.0.1:5182',secureCookie:false,trustProxy:false},new DatasetService(runtime))
  server=await new Promise((resolve,reject)=>{const listening=app.listen(3005,'127.0.0.1',()=>resolve(listening));listening.on('error',reject)})
})
test.afterAll(async()=>{if(server)server.closeAllConnections();if(server)await new Promise<void>((resolve,reject)=>server!.close(error=>error?reject(error):resolve()));await runtime?.end();await admin?.end();if(created)await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`);await cluster.end()})
async function register(page:Page,email:string){await page.goto('/inscription');await page.getByLabel('Nom affiché').fill('Analyste tableaux');await page.getByLabel('Adresse e-mail').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill('dashboards-browser-password');await page.getByRole('button',{name:'Créer mon compte'}).click();await expect(page).toHaveURL(/\/espace$/)}
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

const fixture='id,category,amount,day,private_note\n001,A,1,2026-01-01,private-alpha\n002,A,2,2026-01-02,private-beta\n003,B,3,2026-02-01,private-gamma\n004,B,4,2026-02-02,private-delta\n005,C,5,2026-03-01,private-epsilon\n006,C,6,2026-03-02,private-zeta\n'
async function mutation(page:Page,path:string,body:unknown,method:'POST'|'PATCH'|'DELETE'='POST'){
  const origin=new URL(page.url()).origin,session=await (await page.request.get('/platform-api/auth/session')).json()
  return page.request.fetch('/platform-api'+path,{method,headers:{Origin:origin,'X-CSRF-Token':session.csrfToken},data:body})
}
async function seedAnalysis(page:Page,source:{datasetId:string;versionId:string},title:string){
  const response=await mutation(page,'/analyses',{title,description:'Synthetic browser chart',definition:{kind:'aggregate',source,measures:[{operation:'rows',label:'Lignes'}],groupBy:[{column:columnId('category')}],chart:'bar'}})
  expect(response.status()).toBe(201);return (await response.json()).analysis
}
async function openSharing(page:Page){await page.getByRole('button',{name:'Gérer les destinataires',exact:true}).click()}
async function share(page:Page,email:string){await page.getByLabel('Adresse exacte du destinataire',{exact:true}).fill(email);await page.getByRole('button',{name:'Accorder un accès en lecture',exact:true}).click();await expect(page.getByRole('button',{name:'Révoquer l’accès de '+email,exact:true})).toBeVisible()}

test('dashboard builder saves layout, keyboard/pointer edits, mapped filters and accessible results',async({page},info)=>{
  await register(page,'dashboards-builder@example.test')
  const source=await importCsv(page,fixture,'Dashboard source'),analysis=await seedAnalysis(page,source,'Comptes par catégorie')
  await page.goto('/tableaux/nouveau?analysis='+analysis.id)
  await page.getByLabel('Titre du tableau de bord',{exact:true}).fill('Mon tableau pharmaceutique')
  await page.getByRole('button',{name:'Ajouter cette analyse au tableau',exact:true}).click()
  await page.getByRole('button',{name:'Prévisualiser ce widget',exact:true}).click()
  await expect(page.getByRole('region',{name:'Contenu de Comptes par catégorie',exact:true})).toContainText('6 lignes après filtrage')
  await page.getByRole('button',{name:'Dupliquer Comptes par catégorie',exact:true}).click()
  await page.getByLabel('Titre du widget',{exact:true}).fill('Deuxième indicateur')
  await page.getByLabel('Largeur du widget',{exact:true}).selectOption('4')
  await page.getByRole('button',{name:'Déplacer Comptes par catégorie',exact:true}).press('ArrowDown')
  await expect(page.locator('.dashboard-widget > header > h3')).toHaveText(['Deuxième indicateur','Comptes par catégorie'])
  await page.getByRole('button',{name:'Déplacer Comptes par catégorie',exact:true}).press('ArrowUp')
  await expect(page.locator('.dashboard-widget > header > h3')).toHaveText(['Comptes par catégorie','Deuxième indicateur'])
  const handle=page.getByRole('button',{name:'Déplacer Comptes par catégorie',exact:true})
  await handle.scrollIntoViewIfNeeded()
  const from=await handle.boundingBox(),target=await page.getByRole('article',{name:'Deuxième indicateur',exact:true}).locator('header').boundingBox()
  expect(from&&target).toBeTruthy()
  await page.mouse.move(from!.x+from!.width/2,from!.y+from!.height/2);await page.mouse.down();await page.mouse.move(target!.x+target!.width/2,target!.y+target!.height/2,{steps:8});await page.mouse.up()
  await expect(page.locator('.dashboard-widget > header > h3')).toHaveText(['Deuxième indicateur','Comptes par catégorie'])
  await page.getByRole('button',{name:'Redimensionner Comptes par catégorie',exact:true}).press('ArrowRight')
  await page.getByRole('button',{name:'Redimensionner Comptes par catégorie',exact:true}).press('ArrowDown')
  await expect(page.getByRole('article',{name:'Comptes par catégorie',exact:true})).toHaveCSS('grid-column-start','span 12')
  await expect(page.getByRole('article',{name:'Comptes par catégorie',exact:true})).toHaveCSS('grid-row-start','span 6')
  const resize=page.getByRole('button',{name:'Redimensionner Comptes par catégorie',exact:true})
  await resize.scrollIntoViewIfNeeded()
  const resizeBox=await resize.boundingBox(),gridWidth=await page.locator('.dashboard-grid').evaluate(element=>element.getBoundingClientRect().width)
  expect(resizeBox).toBeTruthy()
  await page.mouse.move(resizeBox!.x+resizeBox!.width/2,resizeBox!.y+resizeBox!.height/2);await page.mouse.down();await page.mouse.move(resizeBox!.x+resizeBox!.width/2-gridWidth/3,resizeBox!.y+resizeBox!.height/2+80,{steps:8});await page.mouse.up()
  await expect(page.getByRole('article',{name:'Comptes par catégorie',exact:true})).toHaveCSS('grid-column-start','span 6')
  await expect(page.getByRole('article',{name:'Comptes par catégorie',exact:true})).toHaveCSS('grid-row-start','span 7')
  await page.getByRole('button',{name:'Ajouter un filtre interactif',exact:true}).click()
  await page.getByLabel('Nom du filtre 1',{exact:true}).fill('Groupes')
  await page.getByLabel('Catégories autorisées du filtre 1',{exact:false}).fill('A\nB')
  for(const name of ['Comptes par catégorie','Deuxième indicateur']){
    await page.getByLabel('Colonne pour Groupes → '+name,{exact:true}).selectOption(columnId('category'))
    await page.getByRole('button',{name:'Mapper '+name,exact:true}).click()
  }
  await Promise.all([page.waitForEvent('dialog').then(dialog=>dialog.dismiss()),page.getByRole('link',{name:'Mes analyses',exact:true}).click()])
  await expect(page).toHaveURL(/\/tableaux\/nouveau\?analysis=/)
  let logouts=0
  page.on('request',request=>{if(request.url().endsWith('/platform-api/auth/logout'))logouts++})
  await Promise.all([page.waitForEvent('dialog').then(dialog=>dialog.dismiss()),page.getByRole('button',{name:'Se déconnecter',exact:true}).click()])
  await expect(page.getByLabel('Titre du tableau de bord',{exact:true})).toHaveValue('Mon tableau pharmaceutique');expect(logouts).toBe(0)
  let releaseSave!:()=>void;const gate=new Promise<void>(resolve=>{releaseSave=resolve})
  await page.route('**/platform-api/dashboards',async route=>{if(route.request().method()!=='POST'){await route.continue();return}const response=await route.fetch();await gate;await route.fulfill({response})})
  await page.getByRole('button',{name:'Enregistrer les modifications',exact:true}).click()
  try{await expect(page.getByLabel('Titre du tableau de bord',{exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'Ajouter un widget vide',exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'Descendre Deuxième indicateur',exact:true})).toBeDisabled()}finally{releaseSave()}
  await expect(page).toHaveURL(/\/tableaux\/[a-f0-9-]{36}$/);await page.unroute('**/platform-api/dashboards')
  const savedUrl=page.url(),body=page.getByRole('region',{name:'Contenu de Comptes par catégorie',exact:true})
  await expect(body).toContainText('4 lignes après filtrage')
  await page.getByLabel('Groupes',{exact:true}).selectOption(['A'])
  await expect(body).toContainText('2 lignes après filtrage')
  await page.getByRole('button',{name:'Réinitialiser les filtres du lecteur',exact:true}).click();await expect(body).toContainText('4 lignes après filtrage')
  await page.reload();await expect(body).toContainText('4 lignes après filtrage')
  await page.getByRole('button',{name:'Se déconnecter',exact:true}).click();await expect(page).toHaveURL(/\/connexion$/)
  await page.goto(savedUrl);await expect(page).toHaveURL(/\/connexion$/)
  await page.getByLabel('Adresse e-mail',{exact:true}).fill('dashboards-builder@example.test');await page.getByLabel('Mot de passe',{exact:true}).fill('dashboards-browser-password');await page.getByRole('button',{name:'Se connecter',exact:true}).click();await expect(page).toHaveURL(savedUrl);await expect(body).toContainText('4 lignes après filtrage')
  await expect(page.locator('.dashboard-widget > header > h3')).toHaveText(['Deuxième indicateur','Comptes par catégorie'])
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('dashboard-desktop.png'),fullPage:true})
  await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('dashboard-mobile.png'),fullPage:true});await page.setViewportSize({width:1280,height:900})
  const unrelated=await importCsv(page,fixture,'Autre dataset avec les mêmes noms')
  await page.getByRole('button',{name:'Modifier le tableau de bord',exact:true}).click()
  await page.getByRole('button',{name:'Configurer Comptes par catégorie',exact:true}).click()
  await page.getByLabel('Jeu de données (Source du widget)',{exact:true}).selectOption(unrelated.datasetId)
  await page.getByLabel('Version (Source du widget)',{exact:true}).selectOption(unrelated.versionId)
  await expect(page.getByRole('button',{name:'Retirer la correspondance Comptes par catégorie '+columnId('category'),exact:true})).toHaveCount(0)
  await expect(page.getByRole('button',{name:'Retirer la correspondance Deuxième indicateur '+columnId('category'),exact:true})).toBeVisible()
  await page.getByLabel('Titre du tableau de bord',{exact:true}).fill('Brouillon abandonné')
  await Promise.all([page.waitForEvent('dialog').then(dialog=>dialog.accept()),page.getByRole('button',{name:'Abandonner les modifications',exact:true}).click()]);await expect(page.getByRole('heading',{level:1})).toHaveText('Mon tableau pharmaceutique')
  await page.goto(savedUrl);await page.getByRole('button',{name:'Supprimer ce tableau de bord',exact:true}).click();await page.getByRole('button',{name:'Confirmer la suppression du tableau',exact:true}).click();await expect(page).toHaveURL(/\/tableaux$/)
})

test('three-account dataset/result sharing, original-owner approval and revocation are enforced',async({page,context},info)=>{
  await register(page,'dashboards-owner@example.test')
  const source=await importCsv(page,fixture,'Source partagée')
  const analystContext=await context.browser()!.newContext(),readerContext=await context.browser()!.newContext(),analyst=await analystContext.newPage(),reader=await readerContext.newPage()
  try{
    await register(analyst,'dashboards-analyst@example.test');await register(reader,'dashboards-reader@example.test')
    await page.goto('/donnees/'+source.datasetId);await openSharing(page);await share(page,'dashboards-analyst@example.test')
    await analyst.goto('/donnees/'+source.datasetId);await expect(analyst.getByText('Dataset partagé en lecture seule.',{exact:false})).toBeVisible();await expect(analyst.getByRole('button',{name:'Enregistrer les métadonnées',exact:true})).toHaveCount(0)
    await analyst.getByRole('button',{name:'Données',exact:true}).click();await expect(analyst.getByRole('region',{name:'Table des données',exact:true})).toContainText('private-alpha')
    const analysis=await seedAnalysis(analyst,source,'Analyse de la source reçue')
    await analyst.goto('/tableaux/nouveau?analysis='+analysis.id);await analyst.getByLabel('Titre du tableau de bord',{exact:true}).fill('Diffusion autorisée');await analyst.getByRole('button',{name:'Ajouter cette analyse au tableau',exact:true}).click();await analyst.getByRole('button',{name:'Enregistrer les modifications',exact:true}).click();await expect(analyst).toHaveURL(/\/tableaux\/[a-f0-9-]{36}$/)
    const savedUrl=analyst.url(),dashboardId=savedUrl.split('/').at(-1)!
    await openSharing(analyst);await expect(analyst.getByText('autorisation du propriétaire original requise pour cette révision',{exact:false})).toBeVisible();await expect(analyst.getByRole('button',{name:'Accorder un accès en lecture',exact:true})).toBeDisabled()
    await page.reload();await openSharing(page);await page.getByRole('button',{name:'Autoriser la diffusion de Diffusion autorisée',exact:true}).click();await page.getByRole('button',{name:'Confirmer l’autorisation de diffusion',exact:true}).click();await expect(page.getByRole('button',{name:'Révoquer la diffusion de Diffusion autorisée',exact:true})).toBeVisible()
    await analyst.reload();await openSharing(analyst);await share(analyst,'dashboards-reader@example.test')
    await reader.goto(savedUrl);await expect(reader.getByRole('region',{name:'Contenu de Analyse de la source reçue',exact:true})).toContainText('6 lignes après filtrage');await expect(reader.getByRole('button',{name:'Modifier le tableau de bord',exact:true})).toHaveCount(0)
    expect((await reader.request.get('/platform-api/datasets/'+source.datasetId)).status()).toBe(404)
    const tampered=await mutation(reader,`/dashboards/${dashboardId}/widgets/${(await (await analyst.request.get('/platform-api/dashboards/'+dashboardId)).json()).dashboard.configuration.widgets[0].id}/execute`,{revision:1,definition:{kind:'aggregate',source,measures:[{operation:'rows'}]}});expect(tampered.status()).toBe(422)
    await reader.getByLabel('Titre de la copie',{exact:true}).fill('Copie sans droit dataset');await reader.getByRole('button',{name:'Créer une copie privée',exact:true}).click();await expect(reader.getByRole('alert')).toContainText('introuvable')
    await reader.screenshot({path:info.outputPath('dashboard-shared-denied-copy.png'),fullPage:true})
    await page.getByRole('button',{name:'Révoquer la diffusion de Diffusion autorisée',exact:true}).click();await page.getByRole('button',{name:'Confirmer la révocation de diffusion',exact:true}).click()
    await reader.reload();await expect(reader.getByRole('alert')).toContainText('propriétaire original')
    await page.getByRole('button',{name:'Autoriser la diffusion de Diffusion autorisée',exact:true}).click();await page.getByRole('button',{name:'Confirmer l’autorisation de diffusion',exact:true}).click()
    await reader.reload();await expect(reader.getByRole('region',{name:'Contenu de Analyse de la source reçue',exact:true})).toContainText('6 lignes après filtrage')
    await page.getByRole('button',{name:'Révoquer l’accès de dashboards-analyst@example.test',exact:true}).click();await page.getByRole('button',{name:'Confirmer la révocation',exact:true}).click()
    await reader.reload();await expect(reader.getByRole('alert')).toContainText('révoqué');await analyst.goto('/donnees/'+source.datasetId);await expect(analyst.getByRole('alert')).toContainText('introuvable')
  }finally{await analystContext.close();await readerContext.close()}
})

test('new widgets, date/numeric/presence filters, error recovery and shared analysis copies',async({page,context},info)=>{
  await register(page,'dashboards-controls@example.test')
  const source=await importCsv(page,fixture,'Controlled source')
  await page.goto('/tableaux/nouveau');await page.getByLabel('Titre du tableau de bord',{exact:true}).fill('Distribution contrôlée');await page.getByRole('button',{name:'Ajouter un widget vide',exact:true}).click()
  await page.getByLabel('Titre du widget',{exact:true}).fill('Montants')
  await page.getByLabel('Jeu de données (Source du widget)',{exact:true}).selectOption(source.datasetId);await page.getByLabel('Version (Source du widget)',{exact:true}).selectOption(source.versionId)
  await page.getByLabel('Type de widget',{exact:true}).selectOption('histogram');await page.getByLabel('Colonne numérique',{exact:true}).selectOption(columnId('amount'));await page.getByLabel('Nombre d’intervalles',{exact:true}).fill('3')
  await page.getByRole('button',{name:'Prévisualiser ce widget',exact:true}).click();await expect(page.getByRole('region',{name:'Contenu de Montants',exact:true})).toContainText('6 valeurs présentes')
  await page.getByLabel('Type de widget',{exact:true}).selectOption('aggregate');await page.getByLabel('Groupe 1',{exact:true}).selectOption(columnId('category'));await page.getByLabel('Visualisation',{exact:true}).selectOption('pie');await page.getByLabel('Style circulaire',{exact:true}).selectOption('donut')
  await page.getByRole('button',{name:'Prévisualiser ce widget',exact:true}).click();await expect(page.getByRole('region',{name:'Contenu de Montants',exact:true}).locator('svg circle[fill="white"]')).toHaveCount(1)
  await page.getByLabel('Type de widget',{exact:true}).selectOption('histogram');await page.getByLabel('Colonne numérique',{exact:true}).selectOption(columnId('amount'));await page.getByLabel('Nombre d’intervalles',{exact:true}).fill('3')
  for(const [index,name,kind,column] of [[1,'Montant autorisé','numeric','amount'],[2,'Période autorisée','date','day'],[3,'Présence','presence','amount']] as const){
    await page.getByRole('button',{name:'Ajouter un filtre interactif',exact:true}).click();await page.getByLabel('Nom du filtre '+index,{exact:true}).fill(name);await page.getByLabel('Type du filtre '+index,{exact:true}).selectOption(kind)
    if(kind==='numeric'){await page.getByLabel('Borne autorisée minimum du filtre 1',{exact:true}).fill('2');await page.getByLabel('Borne autorisée maximum du filtre 1',{exact:true}).fill('5')}
    await page.getByLabel('Colonne pour '+name+' → Montants',{exact:true}).selectOption(columnId(column));await page.getByRole('button',{name:'Mapper Montants',exact:true}).nth(index-1).click()
  }
  await page.getByRole('button',{name:'Enregistrer les modifications',exact:true}).click();await expect(page).toHaveURL(/\/tableaux\/[a-f0-9-]{36}$/)
  const body=page.getByRole('region',{name:'Contenu de Montants',exact:true});await expect(body).toContainText('4 valeurs présentes')
  let releaseResult!:()=>void;const gate=new Promise<void>(resolve=>{releaseResult=resolve})
  await page.route('**/platform-api/dashboards/*/widgets/*/execute',async route=>{const response=await route.fetch();await gate;await route.fulfill({response})})
  await page.getByLabel('Montant autorisé · minimum',{exact:true}).fill('3');await page.getByLabel('Montant autorisé · maximum',{exact:true}).fill('4')
  try{await expect(body).toContainText('Calcul du widget en cours');await expect(body).not.toContainText('4 valeurs présentes')}finally{releaseResult()}
  await expect(body).toContainText('2 valeurs présentes');await page.unroute('**/platform-api/dashboards/*/widgets/*/execute')
  await page.getByLabel('Période autorisée · minimum',{exact:true}).fill('2026-01-02');await page.getByLabel('Période autorisée · maximum',{exact:true}).fill('2026-02-01');await expect(body).toContainText('1 valeurs présentes')
  await page.getByLabel('Présence',{exact:true}).selectOption('missing');await expect(body).toContainText('Aucune valeur présente à représenter')
  await page.getByRole('button',{name:'Réinitialiser les filtres du lecteur',exact:true}).click();await expect(body).toContainText('4 valeurs présentes')
  await page.route('**/platform-api/dashboards/*/widgets/*/execute',route=>route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({error:{code:'test_unavailable',message:'Erreur de calcul simulée'}})}))
  await page.getByLabel('Montant autorisé · minimum',{exact:true}).fill('3');await expect(body.getByRole('alert')).toContainText('Erreur de calcul simulée');await expect(body).not.toContainText('4 valeurs présentes')
  await page.unroute('**/platform-api/dashboards/*/widgets/*/execute');await body.getByRole('button',{name:'Réessayer le widget',exact:true}).click();await expect(body).toContainText('3 valeurs présentes')
  await page.screenshot({path:info.outputPath('dashboard-numeric-date-filters.png'),fullPage:true})
  const recipientContext=await context.browser()!.newContext(),recipient=await recipientContext.newPage()
  try{
    await register(recipient,'dashboards-summary-reader@example.test')
    const response=await mutation(page,'/analyses',{title:'Résumé de complétude partagé',definition:{kind:'missing',source,columns:[columnId('amount')]}});expect(response.status()).toBe(201);const analysis=(await response.json()).analysis
    await page.goto('/analyses/'+analysis.id);await openSharing(page);await share(page,'dashboards-summary-reader@example.test')
    await recipient.goto('/analyses/'+analysis.id);await recipient.getByRole('button',{name:'Calculer les résultats partagés',exact:true}).click();await expect(recipient.getByText('Accès aux résultats enregistrés uniquement',{exact:false})).toBeVisible();await expect(recipient.getByRole('region',{name:'Lignes affectées · valeurs interprétées et originales',exact:true})).toHaveCount(0)
    await recipient.getByLabel('Titre de la copie d’analyse',{exact:true}).fill('Copie personnelle de complétude');await recipient.getByRole('button',{name:'Copier cette analyse en privé',exact:true}).click();await expect(recipient.getByRole('alert')).toContainText('introuvable')
    await page.goto('/donnees/'+source.datasetId);await openSharing(page);await share(page,'dashboards-summary-reader@example.test')
    await recipient.getByRole('button',{name:'Copier cette analyse en privé',exact:true}).click();await expect(recipient).toHaveURL(/\/analyses\/[a-f0-9-]{36}$/);await expect(recipient.getByRole('heading',{level:1})).toContainText('Configurer l’analyse : Copie personnelle de complétude')
    await recipient.getByRole('button',{name:'Calculer l’analyse',exact:true}).click();await expect(recipient.getByRole('region',{name:'Lignes affectées · valeurs interprétées et originales',exact:true})).toBeVisible()
    await page.getByRole('button',{name:'Révoquer l’accès de dashboards-summary-reader@example.test',exact:true}).click();await page.getByRole('button',{name:'Confirmer la révocation',exact:true}).click()
    await recipient.getByRole('button',{name:'Calculer l’analyse',exact:true}).click();await expect(recipient.getByRole('alert').first()).toContainText('révoqué');await expect(recipient.getByRole('heading',{name:'Résultats de l’analyse',exact:true})).toHaveCount(0)
  }finally{await recipientContext.close()}
})
