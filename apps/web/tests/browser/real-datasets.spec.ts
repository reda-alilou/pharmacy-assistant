import { test,expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { randomUUID } from 'node:crypto'
import type { Server } from 'node:http'
import { createApp } from '../../../../services/platform/src/app'
import { createPool } from '../../../../services/platform/src/database'
import { migrate,grantRuntime } from '../../../../services/platform/src/migrations'
import { PostgresStore } from '../../../../services/platform/src/store'
import { DatasetService } from '../../../../services/platform/src/datasets/service'

const cluster=createPool('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database='platform_cp2_'+randomUUID().replaceAll('-','')
let admin:ReturnType<typeof createPool>|undefined,runtime:ReturnType<typeof createPool>|undefined,server:Server|undefined,created=false
test.beforeAll(async()=>{
  if(process.env.DEPLOYMENT_ORIGIN)return
  expect((await cluster.query('SELECT current_user,current_database()')).rows[0]).toEqual({current_user:'platform_test_admin',current_database:'platform_checkpoint1_test'})
  if(!/^platform_cp2_[a-f0-9]{32}$/.test(database))throw new Error('Invalid test identity')
  await cluster.query(`CREATE DATABASE "${database}"`);created=true
  admin=createPool(`postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/${database}`)
  await migrate(admin);await grantRuntime(admin,'platform-test-runtime-password-at-least-32-characters')
  runtime=createPool(`postgresql://pharmacy_platform:platform-test-runtime-password-at-least-32-characters@127.0.0.1:55433/${database}`)
  const app=createApp(new PostgresStore(runtime),{origin:'http://127.0.0.1:5179',secureCookie:false,trustProxy:false},new DatasetService(runtime))
  server=await new Promise((resolve,reject)=>{const listening=app.listen(3003,'127.0.0.1',()=>resolve(listening));listening.on('error',reject)})
})
test.afterAll(async()=>{
  if(server){server.closeAllConnections()}
  if(server)await new Promise<void>((resolve,reject)=>server!.close(error=>error?reject(error):resolve()))
  await runtime?.end();await admin?.end();if(created)await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`);await cluster.end()
})
async function register(page:import('@playwright/test').Page,email:string){
  await page.goto('/inscription');await page.getByLabel('Nom affiché').fill('Analyste CSV');await page.getByLabel('Adresse e-mail').fill(email);await page.getByLabel('Mot de passe',{exact:true}).fill('dataset-browser-password');await page.getByRole('button',{name:'Créer mon compte'}).click();await expect(page).toHaveURL(/\/espace$/)
}
async function upload(page:import('@playwright/test').Page,csv:string,name='test.csv'){
  await page.getByLabel('Fichier CSV').setInputFiles({name,mimeType:'text/csv',buffer:Buffer.from(csv)})
  await page.getByRole('button',{name:'Préparer l’aperçu'}).click();await expect(page.getByRole('heading',{name:'Configuration du fichier'})).toBeVisible()
}
test('CSV wizard → private dataset → exploration/version/archive/delete; accessible desktop/mobile',async({page,context},info)=>{
  await register(page,'dataset-browser@example.test')
  await page.getByRole('link',{name:'Ouvrir mes données'}).click()
  await expect(page.getByRole('heading',{name:'Aucun jeu de données'})).toBeVisible()
  await page.getByRole('link',{name:'Importer un CSV',exact:true}).click()
  await upload(page,'code;amount;label;day;active\n001;10,50;Alpha;01/02/2026;false\n002;0;Beta;03/04/2026;true\n003;;NA;05/06/2026;false\n','pharma.csv')
  await page.getByLabel('Séparateur décimal',{exact:true}).selectOption(',')
  // Hold a real response so editing cannot race the refreshed inferred types.
  let releasePreview!:()=>void
  const previewGate=new Promise<void>(resolve=>{releasePreview=resolve})
  await page.route('**/platform-api/imports/*/preview',async route=>{
    const response=await route.fetch();await previewGate;await route.fulfill({response})
  })
  await page.getByRole('button',{name:'Actualiser l’aperçu et proposer les types'}).click()
  await expect(page.getByLabel('Type de amount',{exact:true})).toBeDisabled()
  await expect(page.getByLabel('Séparateur décimal',{exact:true})).toBeDisabled()
  releasePreview()
  await expect(page.getByLabel('Type de amount',{exact:true})).toBeEnabled()
  await page.getByLabel('Type de amount',{exact:true}).selectOption('decimal')
  await page.getByLabel('Type de day',{exact:true}).selectOption('date')
  await page.getByLabel('Format de day',{exact:true}).selectOption('dmy')
  await page.getByLabel('Titre',{exact:true}).fill('Essai pharmaceutique')
  await page.getByLabel('Source',{exact:true}).fill('Synthetic browser fixture')
  await page.getByRole('button',{name:'Valider tout le fichier'}).click()
  await expect(page.getByText('Validation réussie : 3 lignes, 5 colonnes.')).toBeVisible()
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('wizard-desktop.png'),fullPage:true})
  await page.getByRole('button',{name:'Importer et créer le jeu de données'}).click()
  await expect(page.getByRole('heading',{name:'Essai pharmaceutique',exact:true})).toBeVisible()
  const url=page.url()
  await page.getByRole('button',{name:'Données',exact:true}).click()
  await expect(page.getByRole('status')).toContainText('3 ligne(s) correspondent')
  await page.getByLabel('Trier par',{exact:true}).selectOption({label:'amount'})
  const table=page.getByRole('region',{name:'Table des données'})
  await expect(table.locator('tbody tr').first()).toContainText('002')
  await expect(table.locator('tbody tr').last()).toContainText('Manquant')
  await page.getByLabel('Colonne du filtre').selectOption({label:'amount (Décimal)'})
  await page.getByLabel('Opération',{exact:true}).selectOption('missing')
  await page.getByRole('button',{name:'Ajouter le filtre',exact:true}).click()
  await expect(page.getByRole('status')).toContainText('1 ligne(s) correspondent')
  await expect(table).toContainText('NA')
  await page.getByRole('button',{name:'Effacer tous les filtres et la recherche'}).click()
  await expect(page.getByRole('status')).toContainText('3 ligne(s) correspondent')
  await page.setViewportSize({width:390,height:844})
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
  expect((await new AxeBuilder({page}).analyze()).violations).toEqual([])
  await page.screenshot({path:info.outputPath('exploration-mobile.png'),fullPage:true})
  await page.setViewportSize({width:1280,height:900})
  await page.reload();await expect(page.getByRole('status')).toContainText('3 ligne(s) correspondent')
  await page.getByRole('link',{name:'Ajouter une version CSV'}).click()
  await upload(page,'code,amount,label\n009,77,New version\n','version2.csv')
  await page.getByRole('button',{name:'Valider tout le fichier'}).click();await expect(page.getByText('Validation réussie : 1 lignes, 3 colonnes.')).toBeVisible()
  await page.getByRole('button',{name:'Publier la nouvelle version'}).click()
  await page.getByRole('button',{name:'Versions',exact:true}).click();await expect(page.getByRole('heading',{name:'Version 1',exact:true})).toBeVisible();await expect(page.getByRole('heading',{name:'Version 2',exact:true})).toBeVisible()
  await page.getByRole('button',{name:'Consulter la version 1'}).click();await expect(page.getByRole('status')).toContainText('3 ligne(s) correspondent')
  const second=await context.browser()!.newContext(),other=await second.newPage()
  await register(other,'other-dataset-browser@example.test');await other.goto(url);await expect(other.getByRole('alert')).toContainText('introuvable');await second.close()
  await page.getByRole('button',{name:'Vue d’ensemble',exact:true}).click()
  let releaseSave!:()=>void
  const saveGate=new Promise<void>(resolve=>{releaseSave=resolve})
  await page.route('**/platform-api/datasets/*',async route=>{
    if(route.request().method()!=='PATCH'){await route.continue();return}
    const response=await route.fetch();await saveGate;await route.fulfill({response})
  })
  await page.getByRole('textbox',{name:'Description',exact:true}).fill('Métadonnées enregistrées explicitement')
  await page.getByRole('button',{name:'Enregistrer les métadonnées'}).click()
  try{
    await expect(page.getByLabel('Titre',{exact:true})).toBeDisabled()
    await expect(page.getByRole('textbox',{name:'Description',exact:true})).toBeDisabled()
    await expect(page.getByRole('button',{name:'Annuler les modifications des métadonnées'})).toBeDisabled()
  }finally{releaseSave()}
  await expect(page.getByRole('textbox',{name:'Description',exact:true})).toBeEnabled()
  await page.unroute('**/platform-api/datasets/*')
  await page.reload()
  await expect(page.getByRole('textbox',{name:'Description',exact:true})).toHaveValue('Métadonnées enregistrées explicitement')
  await page.getByRole('button',{name:'Archiver le jeu de données',exact:true}).click();await expect(page.getByRole('button',{name:'Restaurer le jeu de données'})).toBeVisible()
  await page.getByRole('link',{name:'Mes données',exact:true}).click();await expect(page.getByRole('heading',{name:'Aucun jeu de données'})).toBeVisible();await page.getByLabel('Afficher les archives').check();await page.getByRole('link',{name:'Essai pharmaceutique',exact:true}).click()
  await page.getByRole('button',{name:'Vérifier les dépendances avant suppression'}).click();await expect(page.getByText(/2 version\(s\) seront supprimées/)).toBeVisible()
  await page.getByLabel('Recopiez le titre pour confirmer').fill('Essai pharmaceutique');await page.getByRole('button',{name:'Supprimer définitivement toutes les versions'}).click();await expect(page).toHaveURL(/\/donnees$/)
})
test('invalid numeric/date input stays unpublished; user downloads report, corrects types and resumes after refresh',async({page})=>{
  await register(page,'invalid-browser@example.test');await page.goto('/donnees/importer')
  await upload(page,'id,amount,day\n001,12,31/02/2026\n002,bad,01/02/2026\n','invalid.csv')
  await page.getByLabel('Type de amount',{exact:true}).selectOption('decimal');await page.getByLabel('Type de day',{exact:true}).selectOption('date');await page.getByLabel('Format de day').selectOption('dmy')
  await page.getByRole('button',{name:'Valider tout le fichier'}).click();await expect(page.getByText('Validation refusée : 2 erreur(s). Corrigez la configuration ou le fichier.')).toBeVisible()
  await expect(page.getByRole('button',{name:'Importer et créer le jeu de données'})).toBeDisabled()
  const download=page.waitForEvent('download');await page.getByRole('link',{name:'Télécharger le rapport de validation CSV'}).click();expect((await download).suggestedFilename()).toBe('validation.csv')
  await page.reload();await expect(page.getByText('Validation refusée : 2 erreur(s). Corrigez la configuration ou le fichier.')).toBeVisible()
  await page.getByLabel('Type de amount',{exact:true}).selectOption('text');await page.getByLabel('Type de day',{exact:true}).selectOption('text');await page.getByRole('button',{name:'Valider tout le fichier'}).click();await expect(page.getByText('Validation réussie : 2 lignes, 3 colonnes.')).toBeVisible()
  await page.getByRole('button',{name:'Annuler cet import temporaire'}).click();await expect(page).toHaveURL(/\/donnees$/);await expect(page.getByRole('heading',{name:'Aucun jeu de données'})).toBeVisible()
})
