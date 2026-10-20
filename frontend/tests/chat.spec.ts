import { test, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { mockApi, TOKEN, raw } from './mock-api'

const question = 'Quel est le prix de ABIP 15mg ?'
const input = (page: import('@playwright/test').Page) => page.getByRole('textbox', { name: 'Votre question' })
const choose30 = (page: import('@playwright/test').Page) => page.getByRole('button', { name: /Choisir ABIP.*BOITE DE 30/ }).last()
async function send(page: import('@playwright/test').Page, text = question) {
  await input(page).fill(text); await page.getByRole('button', { name: 'Envoyer la question' }).click()
}
async function saveToken(page: import('@playwright/test').Page) {
  await page.addInitScript(({ token }) => sessionStorage.setItem('pharmacy.active-conversation.v1', JSON.stringify({ token, expiresAt: new Date(Date.now() + 1_800_000).toISOString() })), { token: TOKEN })
}

test('French empty state, examples prepare without sending, keyboard focus and no overflow', async ({ page }) => {
  const api = await mockApi(page)
  await page.goto('/')
  await expect(page).toHaveTitle('Assistant pharmacie')
  await expect(page.getByRole('heading', { name: /Une question sur/ })).toBeVisible()
  await page.getByRole('button', { name: /Le prix d’un médicament/ }).click()
  await expect(input(page)).toHaveValue('Quel est le prix de ABIP ?')
  await expect(input(page)).toBeFocused()
  await expect(page.getByRole('button', { name: 'Envoyer la question' })).toBeEnabled()
  expect(api.calls).toHaveLength(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../reports/checkpoint5-desktop-empty.png', fullPage: true })
})

test('chat, explicit presentation, two packages and refresh restoration without inference', async ({ page }) => {
  const api = await mockApi(page)
  await page.goto('/'); await send(page)
  await expect(choose30(page)).toBeEnabled()
  await choose30(page).click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  expect(api.calls).toHaveLength(2)
  expect(api.calls[1]).not.toHaveProperty('text')
  expect(api.calls[1]).toMatchObject({ continuation_id: expect.any(String), selections: [{ mention_index: 0, record_id: '9080' }] })
  await send(page, 'Et pour deux boîtes ?')
  await expect(page.getByText('744,00 MAD', { exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByText('744,00 MAD', { exact: true })).toBeVisible()
  await expect(page.getByText('Et pour deux boîtes ?', { exact: true })).toBeVisible()
  expect(api.calls).toHaveLength(3)
  expect(api.calls[2]).toHaveProperty('session_id')
  expect(new Set(api.calls.map(call => call.request_id)).size).toBe(3)
  await expect(page.getByText(/Extraction JSON|prompt_version|inherited_fields|browser-test-fixture/)).toHaveCount(0)
  await page.getByRole('button', { name: 'Sources et détails' }).last().click()
  await expect(page.getByText(/Ces informations correspondent aux dates/).last()).toBeVisible()
  await page.screenshot({ path: '../reports/checkpoint5-desktop-conversation.png', fullPage: true })
})

test('typed chat and selections work without the HTTPS-only randomUUID API', async ({ page }) => {
  await page.addInitScript(() => {
    Object.defineProperty(Crypto.prototype, 'randomUUID', { configurable: true, value: undefined })
  })
  const api = await mockApi(page)
  await page.goto('/'); await send(page)
  await expect(choose30(page)).toBeEnabled()
  await choose30(page).click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  expect(api.calls).toHaveLength(2)
  for (const call of api.calls) expect(call.request_id).toMatch(/^[a-f0-9]{32}$/)
  expect(api.calls[0].request_id).not.toBe(api.calls[1].request_id)
  await page.reload()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  expect(api.calls).toHaveLength(2)
})

test('busy requests block duplicate submissions and historical choices stay inactive', async ({ page }) => {
  const api = await mockApi(page, { delay: 250 })
  await page.goto('/'); await send(page)
  await expect(page.getByRole('button', { name: 'Envoyer la question' })).toBeDisabled()
  await expect(input(page)).toBeDisabled()
  await expect(choose30(page)).toBeEnabled(); await choose30(page).click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  await expect(choose30(page)).toBeDisabled()
  expect(api.calls).toHaveLength(2)
})

test('cooldowns preserve failed text and allow inference-free choices, never automatic retry', async ({ page }) => {
  const api = await mockApi(page, { cooldown: 120 })
  await page.goto('/'); await send(page); await expect(choose30(page)).toBeEnabled()
  api.failChat('provider_rate_limited')
  await send(page, 'Et deux boîtes ?')
  await expect(page.getByRole('alert')).toContainText('La limite de demandes est atteinte')
  await expect(page.getByRole('button', { name: 'Réessayer la question' })).toBeDisabled()
  await expect(page.getByText('Et deux boîtes ?', { exact: true })).toBeVisible()
  await expect(choose30(page)).toBeEnabled(); await choose30(page).click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  expect(api.calls).toHaveLength(3)
  await expect(page.getByText('PRIVATE PROVIDER BODY')).toHaveCount(0)
})

test('lost successful response is recovered by GET without repeating the POST', async ({ page }) => {
  const api = await mockApi(page); api.loseResponse()
  await page.goto('/'); await send(page)
  await expect(choose30(page)).toBeEnabled()
  await expect(page.getByRole('alert')).toHaveCount(0)
  expect(api.calls).toHaveLength(1)
})

test('uncertain pending request survives refresh and requires explicit status verification', async ({ page }) => {
  const api = await mockApi(page, { pending: true })
  await page.goto('/'); await send(page)
  await expect(page.getByRole('button', { name: 'Vérifier la conversation' })).toBeEnabled()
  await page.reload()
  await expect(page.getByText(question, { exact: true })).toBeVisible()
  await input(page).fill('Autre question')
  await expect(page.getByRole('button', { name: 'Envoyer la question' })).toBeDisabled()
  api.finishPending()
  await page.getByRole('button', { name: 'Vérifier la conversation' }).click()
  await expect(choose30(page)).toBeEnabled()
  expect(api.calls).toHaveLength(1)
})

test('manual retry uses a fresh request id and preserves the original failed message', async ({ page }) => {
  const api = await mockApi(page, { failure: 'language_unavailable' })
  await page.goto('/'); await send(page)
  await expect(page.getByRole('button', { name: 'Réessayer la question' })).toBeEnabled()
  api.failChat(undefined)
  await page.getByRole('button', { name: 'Réessayer la question' }).click()
  await expect(choose30(page)).toBeEnabled()
  expect(api.calls).toHaveLength(2)
  expect(api.calls[0].request_id).not.toBe(api.calls[1].request_id)
  await expect(page.getByText('Demande non aboutie', { exact: true })).toBeVisible()
})

test('new conversation waits for server invalidation; failed reset preserves messages', async ({ page }) => {
  const api = await mockApi(page); await page.goto('/'); await send(page); await expect(choose30(page)).toBeEnabled()
  await page.getByRole('button', { name: 'Nouvelle conversation' }).click()
  const dialog = page.getByRole('alertdialog')
  await expect(dialog).toBeVisible()
  api.failReset(true)
  await dialog.getByRole('button', { name: 'Nouvelle conversation' }).click()
  await expect(dialog.getByRole('alert')).toBeVisible()
  await expect(page.getByText(question, { exact: true })).toBeVisible()
  api.failReset(false)
  await dialog.getByRole('button', { name: 'Nouvelle conversation' }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByRole('heading', { name: /Une question sur/ })).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('pharmacy.active-conversation.v1'))).toBeNull()
  await page.reload()
  await expect(page.getByText(question, { exact: true })).toHaveCount(0)
})

test('server expiry clears the temporary transcript and does not resend the question', async ({ page }) => {
  const api = await mockApi(page); api.seed(); await saveToken(page)
  await page.goto('/'); await expect(choose30(page)).toBeEnabled()
  api.expire(); await page.reload()
  await expect(page.getByText(/Cette conversation a expiré/)).toBeVisible()
  await expect(page.getByText(question, { exact: true })).toHaveCount(0)
  expect(api.calls).toHaveLength(0)
})

test('elapsed local expiry clears messages and browser token', async ({ page }) => {
  const api = await mockApi(page); api.seed(); await saveToken(page)
  await page.clock.install()
  await page.goto('/'); await expect(choose30(page)).toBeEnabled()
  await page.clock.fastForward(1_801_000)
  await expect(page.getByText(/Cette conversation a expiré/)).toBeVisible()
  expect(await page.evaluate(() => sessionStorage.getItem('pharmacy.active-conversation.v1'))).toBeNull()
})

test('pharmacy cards expose readable provenance and safe contact links without stock claims', async ({ page }) => {
  const api = await mockApi(page); api.seed('pharmacy'); await saveToken(page)
  await page.goto('/')
  await expect(page.getByRole('region', { name: 'Pharmacies trouvées' })).toBeVisible()
  await expect(page.getByText(/Horaires inconnus · Garde non vérifiée/)).toBeVisible()
  await expect(page.locator('.pharmacy-card').first()).toContainText('Collecté le')
  expect(api.calls).toHaveLength(0)
})

test('missing recorded price is explicit and never displayed as zero', async ({ page }) => {
  const api = await mockApi(page); api.seed('missing'); await saveToken(page)
  await page.goto('/')
  await expect(page.getByText('Prix non renseigné', { exact: true })).toBeVisible()
  await expect(page.getByText('0,00 MAD', { exact: true })).toHaveCount(0)
})

test('invalid extraction response never renders an unvalidated factual answer', async ({ page }) => {
  const api = await mockApi(page, { invalid: true })
  await page.goto('/'); await send(page)
  await expect(choose30(page)).toBeEnabled() // Canonical validated recovery, no replay.
  await expect(page.getByText(/UNTRUSTED UNVALIDATED PRICE/)).toHaveCount(0)
  expect(api.calls).toHaveLength(1)
})

test('browser storage failure stays usable and explains refresh limitation', async ({ page }) => {
  await page.addInitScript(() => { Storage.prototype.setItem = () => { throw new Error('blocked') } })
  const api = await mockApi(page); await page.goto('/'); await send(page)
  await expect(choose30(page)).toBeEnabled()
  await expect(page.getByText(/La reprise après actualisation n’est pas disponible/)).toBeVisible()
  expect(api.calls).toHaveLength(1)
})

test('input limits, whitespace and IME composition never issue unintended requests', async ({ page }) => {
  const api = await mockApi(page); await page.goto('/')
  await input(page).fill('   '); await expect(page.getByRole('button', { name: 'Envoyer la question' })).toBeDisabled()
  await input(page).fill('a'.repeat(2001)); await expect(page.getByRole('button', { name: 'Envoyer la question' })).toBeDisabled()
  await input(page).fill('ما ثمن ABIP؟')
  await input(page).dispatchEvent('keydown', { key: 'Enter', code: 'Enter', isComposing: true })
  expect(api.calls).toHaveLength(0)
  await input(page).press('Shift+Enter'); expect(api.calls).toHaveLength(0)
})

test('mobile layout and accessible empty/chat/reset states', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await mockApi(page); await page.goto('/')
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: '../reports/checkpoint5-mobile-empty.png', fullPage: true })
  await send(page); await expect(choose30(page)).toBeEnabled(); await choose30(page).click()
  await expect(page.getByText('372,00 MAD', { exact: true }).last()).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await expect(input(page)).toBeEnabled()
  await input(page).evaluate(element => element.focus({ preventScroll: true }))
  await page.screenshot({ path: '../reports/checkpoint5-mobile-conversation.png', fullPage: true })
  await page.getByRole('button', { name: 'Nouvelle conversation' }).click()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})

test('multiple medication cards use server line totals and hide an incomplete order total', async ({ page }) => {
  const api = await mockApi(page); api.seed('multi'); await saveToken(page); await page.goto('/')
  await expect(page.locator('.medication-card')).toHaveCount(2)
  await expect(page.locator('.order-total')).toContainText(raw.multi.order_pricing.total_price_mad!.replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '\u202f'))
  const incomplete = structuredClone(raw.multi)
  incomplete.order_pricing.status = 'incomplete'; incomplete.order_pricing.total_price_mad = null
  api.seedCustom(incomplete); await page.reload()
  await expect(page.locator('.order-total')).toHaveCount(0)
  await expect(page.getByText(/Le total de la sélection ne peut pas encore/)).toBeVisible()
})

test('offered facet, pagination and reference actions send exact API values without text', async ({ page }) => {
  const api = await mockApi(page)
  const facet = structuredClone(raw.initial)
  facet.medications[0].candidate_count = 10
  facet.medications[0].clarification = { kind: 'refine_search', field: 'strength', options: [{ value: '15 MG', candidate_count: 2 }] }
  api.seedCustom(facet); await saveToken(page); await page.goto('/')
  await page.getByRole('combobox', { name: 'Dosage pour ABIP' }).selectOption('15 MG')
  await page.getByRole('button', { name: 'Préciser', exact: true }).click()
  await expect(choose30(page)).toBeEnabled()
  expect(api.calls[0]).toMatchObject({ refinements: [{ mention_index: 0, field: 'strength', value: '15 MG' }] })
  const paged = structuredClone(raw.initial); paged.medications[0].next_candidate_offset = 5
  api.seedCustom(paged); await page.reload(); await page.getByRole('button', { name: 'Présentations suivantes' }).click()
  expect(api.calls[1]).toMatchObject({ refinements: [{ mention_index: 0, field: 'page', value: '5' }] })
  await expect(choose30(page)).toBeEnabled()
  const reference = structuredClone(raw.initial)
  reference.context!.needs_reference = true
  reference.context!.reference_options = [{ mention_index: 0, medication: { name: 'ABIP', strength: null, quantity: null, form: null, presentation: null } }]
  api.seedCustom(reference); await page.reload(); await page.getByRole('button', { name: 'À propos de ABIP' }).click()
  expect(api.calls[2]).toMatchObject({ session_id: TOKEN, reference_index: 0 })
  expect(api.calls.every(call => !('text' in call))).toBe(true)
})

test('user markup is text and unsafe source URLs never become links', async ({ page }) => {
  const api = await mockApi(page); await page.goto('/')
  await send(page, '<script>window.unsafe = true</script> ABIP')
  await expect(page.getByText('<script>window.unsafe = true</script> ABIP', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => 'unsafe' in window)).toBe(false)
  const unsafe = structuredClone(raw.selected)
  unsafe.sources[0].url = 'javascript:alert(1)'
  unsafe.medications[0].medication!.source_url = 'https://user:password@example.com/private'
  api.seedCustom(unsafe); await page.reload()
  await page.getByRole('button', { name: 'Sources et détails' }).click()
  await expect(page.locator('a[href^="javascript:"], a[href*="user:password"]')).toHaveCount(0)
})
