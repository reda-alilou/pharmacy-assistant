import { test, expect } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import type { Server } from 'node:http'
import { createApp } from '../../../../services/platform/src/app'
import { createPool } from '../../../../services/platform/src/database'
import { migrate, grantRuntime } from '../../../../services/platform/src/migrations'
import { permissions, provision } from '../../../../services/platform/src/administration'
import { PostgresStore } from '../../../../services/platform/src/store'

const cluster = createPool('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database = `platform_cp1_${randomUUID().replaceAll('-', '')}`
let admin: ReturnType<typeof createPool> | undefined
let runtime: ReturnType<typeof createPool> | undefined
let server: Server | undefined
let created = false
test.beforeAll(async () => {
  const identity = await cluster.query('SELECT current_user,current_database()')
  expect(identity.rows[0]).toEqual({ current_user: 'platform_test_admin', current_database: 'platform_checkpoint1_test' })
  if (!/^platform_cp1_[a-f0-9]{32}$/.test(database)) throw new Error('Invalid test database name')
  await cluster.query(`CREATE DATABASE "${database}"`); created = true
  admin = createPool(`postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/${database}`)
  await migrate(admin)
  await grantRuntime(admin, 'platform-test-runtime-password-at-least-32-characters')
  await provision(admin, 'browser-admin@example.test', 'Administrateur test', 'browser-admin-password')
  runtime = createPool(`postgresql://pharmacy_platform:platform-test-runtime-password-at-least-32-characters@127.0.0.1:55433/${database}`)
  const app = createApp(new PostgresStore(runtime), { origin: 'http://127.0.0.1:5178', secureCookie: false, trustProxy: false })
  server = await new Promise<Server>((resolve, reject) => {
    const listening = app.listen(3002, '127.0.0.1', () => resolve(listening))
    listening.on('error', reject)
  })
})
test.afterAll(async () => {
  if (server) server.closeAllConnections()
  if (server) await new Promise<void>((resolve, reject) => server!.close(error => error ? reject(error) : resolve()))
  await runtime?.end(); await admin?.end()
  if (created) await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`)
  await cluster.end()
})
test('real React → Express → PostgreSQL account lifecycle and immediate authorization', async ({ page, context }) => {
  await page.goto('/profil')
  await expect(page).toHaveURL(/\/connexion$/)
  await page.getByRole('link', { name: 'Créer un compte', exact: true }).last().click()
  await page.getByLabel('Nom affiché').fill('Analyste navigateur')
  await page.getByLabel('Adresse e-mail').fill('browser@example.test')
  await page.getByLabel('Mot de passe', { exact: true }).fill('browser-analyst-password')
  await page.getByRole('button', { name: 'Créer mon compte' }).click()
  await expect(page.getByRole('heading', { name: 'Bonjour, Analyste navigateur' })).toBeVisible()
  const cookie = (await context.cookies()).find(cookie => cookie.name === 'platform_session')
  expect(cookie?.httpOnly).toBe(true)
  expect(cookie?.sameSite).toBe('Lax')
  expect(await page.evaluate(() => document.cookie.includes('platform_session'))).toBe(false)
  expect(await page.evaluate(() => localStorage.length)).toBe(0)
  const account = (await admin!.query("SELECT id FROM platform.users WHERE email='browser@example.test'")).rows[0]
  expect((await context.request.get('/platform-api/admin/access')).status()).toBe(403)
  expect((await context.request.get(`/platform-api/users/${randomUUID()}`)).status()).toBe(403)
  await page.getByRole('link', { name: 'Mon profil', exact: true }).click()
  await page.getByLabel('Nom affiché').fill('Nom enregistré')
  await page.getByRole('button', { name: 'Enregistrer le profil' }).click()
  await expect(page.getByRole('status')).toHaveText('Profil enregistré.')
  await page.reload()
  await expect(page.getByLabel('Nom affiché')).toHaveValue('Nom enregistré')
  await page.getByLabel('Mot de passe actuel').fill('browser-analyst-password')
  await page.getByLabel('Nouveau mot de passe').fill('browser-replacement-password')
  await page.getByRole('button', { name: 'Changer le mot de passe', exact: true }).click()
  await expect(page).toHaveURL(/\/connexion$/)
  await expect(page.getByRole('status')).toContainText('Mot de passe modifié')
  expect((await context.request.get(`/platform-api/users/${account.id}`)).status()).toBe(401)
  await page.getByLabel('Adresse e-mail').fill('browser@example.test')
  await page.getByLabel('Mot de passe', { exact: true }).fill('incorrect-password')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await expect(page.getByRole('alert')).toHaveText('Adresse ou mot de passe incorrect.')
  await page.getByLabel('Mot de passe', { exact: true }).fill('browser-replacement-password')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await expect(page).toHaveURL(/\/espace$/)
  await permissions(admin!, 'browser@example.test', 'analyst', false)
  expect((await context.request.get(`/platform-api/users/${account.id}`)).status()).toBe(401)
  await page.reload()
  await expect(page).toHaveURL(/\/connexion$/)
  await page.getByLabel('Adresse e-mail').fill('browser-admin@example.test')
  await page.getByLabel('Mot de passe', { exact: true }).fill('browser-admin-password')
  await page.getByRole('button', { name: 'Se connecter' }).click()
  await page.getByRole('link', { name: 'Administration · à venir' }).click()
  await expect(page.getByRole('heading', { name: 'Administration · à venir' })).toBeVisible()
  expect((await context.request.get('/platform-api/admin/access')).status()).toBe(200)
  await page.getByRole('button', { name: 'Se déconnecter' }).click()
  await expect(page).toHaveURL(/\/connexion$/)
  expect((await context.request.get('/platform-api/admin/access')).status()).toBe(401)
})
