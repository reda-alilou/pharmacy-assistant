import { test, expect } from '@playwright/test'
import { fileURLToPath } from 'node:url'

test.skip(!process.env.DEPLOYMENT_ORIGIN, 'Run through the explicitly controlled isolated Compose verification utility')
test.use({ baseURL: process.env.DEPLOYMENT_ORIGIN, trace: 'off', screenshot: 'off' })

test('real web/core/PostgreSQL: restore, quota error, inference-free choice, refresh, and reset', async ({ page, request }) => {
  const token = process.env.DEPLOYMENT_TOKEN!
  await page.addInitScript(({ token }) => sessionStorage.setItem('pharmacy.active-conversation.v1',
    JSON.stringify({ token, expiresAt: new Date(Date.now() + 1_800_000).toISOString() })), { token })
  await page.goto('/')
  await expect(page.getByRole('button', { name: /Choisir ABIP.*BOITE DE 30/ }).last()).toBeEnabled()
  await page.getByRole('textbox', { name: 'Votre question' }).fill('Et deux boîtes ?')
  await page.getByRole('button', { name: 'Envoyer la question' }).click()
  await expect(page.getByRole('alert')).toContainText('La limite de demandes est atteinte')
  await expect(page.getByRole('button', { name: 'Réessayer la question' })).toBeDisabled()
  await page.getByRole('button', { name: /Choisir ABIP.*BOITE DE 30/ }).last().click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  await page.reload()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  await expect(page.getByText('Et deux boîtes ?', { exact: true })).toBeVisible()
  await page.screenshot({ path: fileURLToPath(new URL('../../reports/checkpoint5-real-compose.png', import.meta.url)), fullPage: true })
  await page.getByRole('button', { name: 'Nouvelle conversation' }).click()
  await page.getByRole('alertdialog').getByRole('button', { name: 'Nouvelle conversation' }).click()
  await expect(page.getByRole('heading', { name: /Une question sur/ })).toBeVisible()
  expect((await request.get('/api/conversation', { headers: { Authorization: `Bearer ${token}` } })).status()).toBe(410)
})
