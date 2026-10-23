import { test, expect } from '@playwright/test'
import { mockAccounts } from '../support/account-api'

test('metadata cannot be edited or reset while saving; success persists and failure retains the draft', async ({ page }) => {
  await mockAccounts(page)
  let dataset = {
    id: '776a5195-8bb7-4a9a-80ad-33592d46e997', ownerId: '090c80aa-b1a3-4ba3-8421-660b4ca48f73', ownerName: 'Analyste',
    title: 'Données de test', description: '', category: '', source: '', observationDate: null,
    archived: false, revision: 1, versionCount: 0, createdAt: '2026-10-23T12:00:00Z', updatedAt: '2026-10-23T12:00:00Z',
  }
  let releaseSave!: () => void
  const saveGate = new Promise<void>(resolve => { releaseSave = resolve })
  let saves = 0
  await page.route('**/platform-api/datasets/*', async route => {
    if (route.request().method() === 'PATCH') {
      if (++saves === 2) return route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'Enregistrement indisponible.' } } })
      dataset = { ...dataset, ...route.request().postDataJSON(), revision: dataset.revision + 1 }
      await saveGate
    }
    await route.fulfill({ json: { dataset, versions: [] } })
  })
  await page.goto('/connexion')
  await page.getByLabel('Adresse e-mail').fill('analyst@example.test')
  await page.getByLabel('Mot de passe', { exact: true }).fill('metadata-test-password')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await expect(page).toHaveURL(/\/espace$/)
  await page.goto('/donnees/' + dataset.id)
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Description conservée')
  await page.getByRole('button', { name: 'Enregistrer les métadonnées' }).click()
  try {
    for (const label of ['Titre', 'Description', 'Catégorie', 'Source', 'Date d’observation (facultative)']) {
      const field = label === 'Description' ? page.getByRole('textbox', { name: label, exact: true }) : page.getByLabel(label, { exact: true })
      await expect(field).toBeDisabled()
    }
    await expect(page.getByRole('button', { name: 'Annuler les modifications des métadonnées' })).toBeDisabled()
  } finally { releaseSave() }
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toBeEnabled()
  await page.reload()
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Description conservée')
  await page.getByRole('textbox', { name: 'Description', exact: true }).fill('Brouillon après erreur')
  await page.getByRole('button', { name: 'Enregistrer les métadonnées' }).click()
  await expect(page.getByRole('alert')).toContainText('Enregistrement indisponible.')
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toBeEnabled()
  await expect(page.getByRole('textbox', { name: 'Description', exact: true })).toHaveValue('Brouillon après erreur')
})
