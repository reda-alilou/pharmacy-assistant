import { test, expect, type Page } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mkdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { editingApi, A, B, D, I, V } from '../support/editing-api'
import { mockApi } from '../support/mock-api'
const dialog = (page: Page) => page.getByRole('dialog', { name: 'Abandonner les modifications ?' })
const title = (page: Page) => page.getByLabel('Titre de l’analyse', { exact: true })
async function stay(page: Page) { await expect(dialog(page)).toBeVisible(); await page.getByRole('button', { name: 'Rester', exact: true }).click(); await expect(dialog(page)).not.toBeVisible() }
async function discard(page: Page) { await expect(dialog(page)).toBeVisible(); await page.getByRole('button', { name: 'Abandonner et continuer', exact: true }).click() }

test('analysis links, safe focus, Escape and discard preserve or deliberately lose input', async ({ page }) => {
  await editingApi(page); await page.goto('/analyses/' + A)
  await title(page).fill('Saisie non enregistrée')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Rester', exact: true })).toBeFocused()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  mkdirSync(resolve('../../artifacts/redesign/phase-1/screenshots'), { recursive: true })
  await page.screenshot({ path: '../../artifacts/redesign/phase-1/screenshots/analysis-warning-desktop.png' })
  await stay(page); await expect(title(page)).toHaveValue('Saisie non enregistrée')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await expect(dialog(page)).toBeVisible(); await page.keyboard.press('Escape'); await expect(dialog(page)).not.toBeVisible()
  await expect(title(page)).toHaveValue('Saisie non enregistrée')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await discard(page)
  await expect(page).toHaveURL(/\/donnees$/)
  await page.getByRole('link', { name: 'Mes analyses', exact: true }).click(); await page.getByRole('link', { name: 'TEST CP6 moyenne', exact: true }).click()
  await expect(title(page)).toHaveValue('TEST CP6 moyenne')
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []])
})

test('Back and Forward are guarded once and never restore discarded inputs', async ({ page }) => {
  await editingApi(page); await page.goto('/analyses')
  await page.getByRole('link', { name: 'TEST CP6 moyenne', exact: true }).click()
  await title(page).fill('Retour protégé'); await page.evaluate(() => history.back()); await stay(page)
  await expect(title(page)).toHaveValue('Retour protégé')
  await page.evaluate(() => history.back()); await discard(page); await expect(page).toHaveURL(/\/analyses$/)
  await page.evaluate(() => history.forward()); await expect(title(page)).toHaveValue('TEST CP6 moyenne')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click()
  await page.evaluate(() => history.back()); await expect(title(page)).toBeVisible()
  await title(page).fill('Avance protégée'); await page.evaluate(() => history.forward()); await stay(page)
  await expect(title(page)).toHaveValue('Avance protégée')
  await page.evaluate(() => history.forward()); await discard(page); await expect(page).toHaveURL(/\/donnees$/)
})

test('dataset local tabs and explicit reset warn; save feedback survives and clears on edit', async ({ page }) => {
  await editingApi(page); await page.goto('/donnees/' + D)
  const field = page.getByRole('textbox', { name: 'Description', exact: true })
  await field.fill('Métadonnées conservées'); await page.getByRole('button', { name: 'Données', exact: true }).click(); await stay(page)
  await expect(field).toHaveValue('Métadonnées conservées')
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(field).toHaveValue('Métadonnées conservées')
  await page.getByRole('button', { name: 'Annuler les modifications des métadonnées' }).click(); await stay(page)
  await page.getByRole('button', { name: 'Enregistrer les métadonnées' }).click()
  await expect(page.getByText('Modifications enregistrées.', { exact: true })).toBeVisible()
  await expect(field).toHaveValue('Métadonnées conservées')
  await page.getByRole('button', { name: 'Données', exact: true }).click(); await expect(dialog(page)).not.toBeVisible()
  await page.getByRole('button', { name: 'Vue d’ensemble', exact: true }).click(); await field.fill('À abandonner')
  await page.getByRole('button', { name: 'Données', exact: true }).click(); await discard(page)
  await page.getByRole('button', { name: 'Vue d’ensemble', exact: true }).click(); await expect(field).toHaveValue('Métadonnées conservées')
})

for (const status of [503, 409, 0]) test(`failed or uncertain metadata save ${status} retains input without replay`, async ({ page }) => {
  const api = await editingApi(page); await page.goto('/donnees/' + D)
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Valeur après échec')
  api.fail = status; api.abort = status === 0
  await page.getByRole('button', { name: 'Enregistrer les métadonnées' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  if (status === 409) await expect(page.getByRole('alert')).toContainText('révision')
  if (status === 0) await expect(page.getByRole('alert')).toContainText('incertain')
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Valeur après échec')
  await expect(page.getByRole('link', { name: 'Vérifier l’état enregistré dans un autre onglet' })).toHaveAttribute('target', '_blank')
  expect(api.calls.filter(call => call.method === 'PATCH')).toHaveLength(1)
  await page.getByRole('button', { name: 'Qualité', exact: true }).click(); await stay(page)
})

test('import metadata remains unsaved after accepted validation; publication is explicit', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/donnees/imports/' + I)
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Description privée non publiée')
  await page.getByLabel('Séparateur décimal', { exact: true }).selectOption(',')
  await page.getByRole('button', { name: 'Valider tout le fichier' }).click()
  await expect(page.getByText(/Validation réussie/)).toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Description privée non publiée')
  expect(api.calls.filter(call => call.path.endsWith('/publish'))).toHaveLength(0)
  await page.getByRole('button', { name: 'Importer et créer le jeu de données' }).click()
  await expect(page).toHaveURL(new RegExp('/donnees/' + D))
  await expect(page.getByText('Version publiée. Les données et leur interprétation ont été enregistrées.')).toBeVisible()
  await expect(dialog(page)).not.toBeVisible()
  expect(api.calls.filter(call => call.path.endsWith('/publish'))).toHaveLength(1)
})

test('CSV selection is guarded and successful upload hands off without a false warning', async ({ page }) => {
  await editingApi(page); await page.goto('/donnees/importer')
  await page.getByLabel('Fichier CSV').setInputFiles('tests/fixtures/functional-review/cp6-v1.csv')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  await page.getByRole('button', { name: 'Préparer l’aperçu' }).click()
  await expect(page).toHaveURL(new RegExp('/donnees/imports/' + I)); await expect(dialog(page)).not.toBeVisible()
})

test('dashboard save and discard respect dirty state; new resource success survives redirect', async ({ page }) => {
  await editingApi(page); await page.goto('/tableaux/' + B)
  await page.getByRole('button', { name: 'Modifier le tableau de bord', exact: true }).click()
  const field = page.getByLabel('Titre du tableau de bord', { exact: true })
  await field.fill('Disposition non enregistrée')
  await page.getByRole('button', { name: 'Abandonner les modifications', exact: true }).click(); await stay(page)
  await expect(field).toHaveValue('Disposition non enregistrée')
  await page.getByRole('button', { name: 'Enregistrer les modifications', exact: true }).click()
  await expect(page.getByText(/Tableau de bord enregistré/)).toBeVisible()
  await page.getByRole('link', { name: 'Mes tableaux de bord', exact: true }).click()
  await page.getByRole('link', { name: 'Créer un tableau de bord', exact: true }).click()
  await page.getByLabel('Titre du tableau de bord', { exact: true }).fill('Nouveau tableau sauvegardé')
  await page.getByRole('button', { name: 'Enregistrer les modifications', exact: true }).click()
  await expect(page).toHaveURL(new RegExp('/tableaux/' + B + '$'))
  await expect(page.getByText('Tableau de bord enregistré. Les sources restent épinglées.', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Modifier le tableau de bord', exact: true }).click()
  await page.getByLabel('Titre du tableau de bord', { exact: true }).fill('Encore modifié')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
})

test('Calculate is not Save; a confirmed analysis create retains success and guards later edits', async ({ page }) => {
  await editingApi(page); await page.goto('/analyses/' + A)
  await title(page).fill('Nouvelle configuration')
  await page.getByRole('button', { name: 'Calculer l’analyse', exact: true }).click()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  await page.getByRole('button', { name: 'Enregistrer l’analyse', exact: true }).click()
  await expect(page.getByText('Analyse enregistrée. Les versions et les règles restent épinglées.', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await expect(page).toHaveURL(/\/donnees$/)
})

test('logout waits for discard and failed logout keeps the editor and guard', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/analyses/' + A); await title(page).fill('Travail avant déconnexion')
  await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click(); await stay(page)
  expect(api.calls.filter(call => call.path === '/auth/logout')).toHaveLength(0)
  api.fail = 503; await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click(); await discard(page)
  await expect(page.getByRole('alert')).toContainText('indisponible'); await expect(title(page)).toHaveValue('Travail avant déconnexion')
  api.fail = 0; await page.getByRole('button', { name: 'Se déconnecter', exact: true }).click(); await discard(page)
  await expect(page).toHaveURL(/\/connexion$/)
  expect(api.calls.filter(call => call.path === '/auth/logout')).toHaveLength(2)
})

test('pending mutation warns and its late completion never hijacks discarded navigation', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/tableaux/nouveau')
  await page.getByLabel('Titre du tableau de bord', { exact: true }).fill('Création en attente')
  let release!: () => void; api.pending = new Promise<void>(resolve => { release = resolve })
  await page.getByRole('button', { name: 'Enregistrer les modifications', exact: true }).click()
  try {
    await page.getByRole('link', { name: 'Mes données', exact: true }).click()
    await expect(dialog(page)).toContainText('Quitter ne l’annule pas')
    await stay(page); await expect(page.getByLabel('Titre du tableau de bord', { exact: true })).toBeDisabled()
    await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await discard(page); await expect(page).toHaveURL(/\/donnees$/)
  } finally { release() }
  await expect.poll(() => api.calls.filter(call => call.path === '/dashboards' && call.method === 'POST').length).toBe(1)
  await page.getByRole('link', { name: 'Mes tableaux de bord', exact: true }).click()
  await expect(page.getByRole('link', { name: 'Création en attente', exact: true })).toBeVisible()
  await expect(page).toHaveURL(/\/tableaux$/)
})

test('profile name and password inputs survive failure and guard independently', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/profil')
  await page.getByLabel('Nom affiché').fill('Nom non enregistré')
  await page.getByLabel('Mot de passe actuel', { exact: true }).fill('synthetic-password')
  await page.getByLabel('Nouveau mot de passe', { exact: true }).fill('synthetic-new-password')
  api.fail = 503; await page.getByRole('button', { name: 'Enregistrer le profil', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('indisponible')
  await expect(page.getByLabel('Nom affiché')).toHaveValue('Nom non enregistré')
  api.fail = 0; await page.getByRole('button', { name: 'Enregistrer le profil', exact: true }).click()
  await expect(page.getByText('Profil enregistré.', { exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  await expect(page.getByLabel('Nouveau mot de passe', { exact: true })).toHaveValue('synthetic-new-password')
  await page.getByRole('button', { name: 'Changer le mot de passe', exact: true }).click(); await expect(page).toHaveURL(/\/connexion$/)
  await expect(page.getByText('Mot de passe modifié. Reconnectez-vous avec le nouveau mot de passe.', { exact: true })).toBeVisible()
})

test('forced authentication expiry follows security rather than retaining protected editing access', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/analyses/' + A); await title(page).fill('Saisie avant expiration')
  api.authenticated = false; await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page).toHaveURL(/\/connexion$/); await expect(dialog(page)).not.toBeVisible()
  await expect(title(page)).not.toBeVisible()
})

test('native reload warning cancels or accepts loss without a recovery store', async ({ page }) => {
  await editingApi(page); await page.goto('/analyses/' + A); await title(page).fill('Saisie avant rechargement')
  const first = page.waitForEvent('dialog'); const canceled = page.reload({ timeout: 2500 }).catch(() => null)
  const warning = await first; expect(warning.type()).toBe('beforeunload'); await warning.dismiss(); await canceled
  await expect(title(page)).toHaveValue('Saisie avant rechargement')
  const next = page.waitForEvent('dialog'); const reloaded = page.reload()
  await (await next).accept(); await reloaded
  await expect(title(page)).toHaveValue('TEST CP6 moyenne')
  expect(await page.evaluate(() => [Object.keys(localStorage), Object.keys(sessionStorage)])).toEqual([[], []])
})

test('mobile assistant unsent question has a readable warning and remains independent of accounts', async ({ page }) => {
  await editingApi(page); await mockApi(page); await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/assistant')
  await page.getByRole('textbox', { name: 'Votre question' }).fill('Question non envoyée')
  await page.getByRole('link', { name: 'Mon espace', exact: true }).click()
  await expect(dialog(page)).toBeVisible(); await page.screenshot({ path: '../../artifacts/redesign/phase-1/screenshots/assistant-warning-mobile.png' })
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await stay(page); await expect(page.getByRole('textbox', { name: 'Votre question' })).toHaveValue('Question non envoyée')
  await page.getByRole('link', { name: 'Mon espace', exact: true }).click(); await discard(page); await expect(page).toHaveURL(/\/espace$/)
})

test('new analysis saves once with pinned sources and carries success across its redirect', async ({ page }) => {
  const api = await editingApi(page); await page.goto(`/analyses/nouvelle?dataset=${D}&version=${V}`)
  await title(page).fill('Création explicite CP6')
  await page.getByRole('button', { name: 'Calculer l’analyse', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Enregistrer l’analyse', exact: true })).toBeEnabled()
  await page.getByRole('button', { name: 'Enregistrer l’analyse', exact: true }).click()
  await expect(page).toHaveURL(new RegExp('/analyses/' + A + '$'))
  await expect(page.getByText('Analyse enregistrée. Les versions et les règles restent épinglées.', { exact: true })).toBeVisible()
  const saves = api.calls.filter(call => call.path === '/analyses' && call.method === 'POST')
  expect(saves).toHaveLength(1)
  expect(saves[0].body).toMatchObject({ title: 'Création explicite CP6', definition: { source: { datasetId: D, versionId: V } } })
  await title(page).fill('Nouvelle modification'); await expect(page.getByText('Analyse enregistrée. Les versions et les règles restent épinglées.', { exact: true })).not.toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
})

test('discarding a dataset tab change stays safe through a session refresh', async ({ page }) => {
  await editingApi(page); await page.goto('/donnees/' + D)
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Saisie avant changement de vue')
  await page.getByRole('button', { name: 'Données', exact: true }).click(); await stay(page)
  const refreshed = page.waitForResponse(response => response.url().endsWith('/platform-api/auth/session'))
  await page.evaluate(() => window.dispatchEvent(new Event('focus'))); await refreshed
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Saisie avant changement de vue')
  await expect(page).not.toHaveURL(/tab=data/)
})

test('shared results remain read-only while an unsent private-copy title is guarded', async ({ page }) => {
  const api = await editingApi(page); api.shared = true; await page.goto('/analyses/' + A)
  await expect(page.getByLabel('Titre de l’analyse', { exact: true })).not.toBeVisible()
  await page.getByLabel('Titre de la copie d’analyse', { exact: true }).fill('Copie non créée')
  api.fail = 403; await page.getByRole('button', { name: 'Copier cette analyse en privé', exact: true }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByLabel('Titre de la copie d’analyse', { exact: true })).toHaveValue('Copie non créée')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  expect(api.calls.some(call => call.method === 'PATCH')).toBe(false)
})

test('a changed account cannot inherit the previous account’s profile input', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/profil'); await page.getByLabel('Nom affiché').fill('Saisie du premier compte')
  await page.getByLabel('Nouveau mot de passe', { exact: true }).fill('synthetic-unsaved-password')
  api.user.id = '99999999-9999-4999-8999-999999999999'; api.user.displayName = 'Autre compte de test'
  const refreshed = page.waitForResponse(response => response.url().endsWith('/platform-api/auth/session'))
  await page.evaluate(() => window.dispatchEvent(new Event('focus'))); await refreshed
  await expect(page.getByLabel('Nom affiché')).toHaveValue('Autre compte de test')
  await expect(page.getByLabel('Nouveau mot de passe', { exact: true })).toHaveValue('')
})

test('warning fits 320px and enlarged text with keyboard access and focus return', async ({ page }) => {
  await editingApi(page); await page.setViewportSize({ width: 320, height: 720 }); await page.goto('/donnees/' + D)
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Saisie sur petit écran')
  const trigger = page.getByRole('button', { name: 'Données', exact: true }); await trigger.click()
  await expect(dialog(page)).toBeVisible()
  let bounds = await dialog(page).boundingBox(); expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(320)
  await page.screenshot({ path: '../../artifacts/redesign/phase-1/screenshots/metadata-warning-320.png' })
  await page.keyboard.press('Escape'); await expect(dialog(page)).not.toBeVisible(); await expect(trigger).toBeFocused()
  await page.evaluate(() => document.documentElement.style.fontSize = '200%')
  await trigger.click(); await expect(dialog(page)).toBeVisible()
  bounds = await dialog(page).boundingBox(); expect(bounds!.height).toBeLessThanOrEqual(720)
  await page.getByRole('button', { name: 'Rester', exact: true }).scrollIntoViewIfNeeded(); await page.keyboard.press('Enter')
  await expect(dialog(page)).not.toBeVisible(); await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Saisie sur petit écran')
})

test('a late profile response cannot restore a session after authentication expires', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/profil'); await page.getByLabel('Nom affiché').fill('Nom pendant sauvegarde')
  let release!: () => void; api.pending = new Promise<void>(resolve => { release = resolve })
  await page.getByRole('button', { name: 'Enregistrer le profil', exact: true }).click()
  try {
    api.authenticated = false; await page.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect(page).toHaveURL(/\/connexion$/)
  } finally { release() }
  await expect.poll(() => api.calls.filter(call => call.path === '/auth/session').length).toBeGreaterThanOrEqual(3)
  await expect(page.getByRole('button', { name: 'Se connecter', exact: true })).toBeVisible()
  expect(api.calls.filter(call => call.method === 'PATCH')).toHaveLength(1)
})

test('a save finishing while confirmation is open updates the message without inventing unsaved work', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/tableaux/' + B)
  await page.getByRole('button', { name: 'Modifier le tableau de bord', exact: true }).click()
  await page.getByLabel('Titre du tableau de bord', { exact: true }).fill('Titre sauvegardé pendant la confirmation')
  let release!: () => void; api.pending = new Promise<void>(resolve => { release = resolve })
  await page.getByRole('button', { name: 'Enregistrer les modifications', exact: true }).click()
  try { await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await expect(dialog(page)).toBeVisible() } finally { release() }
  await expect(page.getByRole('dialog', { name: 'Continuer la navigation ?', exact: true })).toContainText('L’opération est terminée')
  await page.getByRole('button', { name: 'Rester', exact: true }).click()
  await expect(page.getByText(/Tableau de bord enregistré/)).toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await expect(page).toHaveURL(/\/donnees$/)
})

test('failed analysis save preserves the result, definition and title until explicit discard', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/analyses/' + A); await title(page).fill('Analyse à préserver')
  await page.getByRole('button', { name: 'Calculer l’analyse', exact: true }).click()
  api.fail = 503; await page.getByRole('button', { name: 'Enregistrer l’analyse', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('indisponible')
  await expect(title(page)).toHaveValue('Analyse à préserver')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  expect(api.calls.filter(call => call.path === '/analyses/' + A && call.method === 'PATCH')).toHaveLength(1)
})

test('dashboard conflict retains the current edit without overwriting or retrying', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/tableaux/' + B)
  await page.getByRole('button', { name: 'Modifier le tableau de bord', exact: true }).click()
  await page.getByLabel('Titre du tableau de bord', { exact: true }).fill('Tableau en conflit')
  api.fail = 409; await page.getByRole('button', { name: 'Enregistrer les modifications', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('révision')
  await expect(page.getByLabel('Titre du tableau de bord', { exact: true })).toHaveValue('Tableau en conflit')
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await stay(page)
  expect(api.calls.filter(call => call.path === '/dashboards/' + B && call.method === 'PATCH')).toHaveLength(1)
})

test('failed import validation retains options and metadata; cancellation waits for discard', async ({ page }) => {
  const api = await editingApi(page); await page.goto('/donnees/imports/' + I)
  await page.getByLabel('Séparateur décimal', { exact: true }).selectOption(',')
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Import à préserver')
  api.fail = 503; await page.getByRole('button', { name: 'Valider tout le fichier' }).click()
  await expect(page.getByRole('alert')).toContainText('indisponible')
  await expect(page.getByLabel('Séparateur décimal', { exact: true })).toHaveValue(',')
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Import à préserver')
  await page.getByRole('button', { name: 'Annuler cet import temporaire', exact: true }).click(); await stay(page)
  expect(api.calls.filter(call => call.method === 'DELETE')).toHaveLength(0)
  api.fail = 0; await page.getByRole('button', { name: 'Annuler cet import temporaire', exact: true }).click(); await discard(page)
  await expect(page).toHaveURL(/\/donnees$/); expect(api.calls.filter(call => call.method === 'DELETE')).toHaveLength(1)
})

test('saving a rebuilt analysis definition adopts the accepted baseline without a false warning', async ({ page }) => {
  await editingApi(page); await page.goto('/analyses/' + A)
  await expect(page.getByLabel('Type d’analyse', { exact: true })).toBeEnabled()
  await page.getByLabel('Type d’analyse', { exact: true }).selectOption('histogram')
  await page.getByLabel('Type d’analyse', { exact: true }).selectOption('aggregate')
  await page.getByLabel('Description de l’analyse', { exact: true }).fill('Configuration reconstruite puis enregistrée')
  await page.getByRole('button', { name: 'Calculer l’analyse', exact: true }).click()
  await page.getByRole('button', { name: 'Enregistrer l’analyse', exact: true }).click()
  await expect(page.getByText('Analyse enregistrée. Les versions et les règles restent épinglées.', { exact: true })).toBeVisible()
  await expect(page.getByText(/Modifications non enregistrées\. Calculez/)).not.toBeVisible()
  await page.getByRole('link', { name: 'Mes données', exact: true }).click(); await expect(page).toHaveURL(/\/donnees$/)
})
