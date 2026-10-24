import type { Page } from '@playwright/test'

export async function mockAccounts(page: Page, options: { unavailable?: boolean; admin?: boolean } = {}) {
  const user = { id: '090c80aa-b1a3-4ba3-8421-660b4ca48f73', email: 'analyst@example.test', displayName: 'Analyste', role: options.admin ? 'admin' : 'analyst', createdAt: '2026-10-23T12:00:00.000Z' }
  let authenticated = false
  const session = () => ({ user: authenticated ? user : null, csrfToken: 'test-csrf', expiresAt: new Date(Date.now() + 1800000).toISOString() })
  const calls: string[] = []
  await page.route('**/platform-api/**', async route => {
    const path = new URL(route.request().url()).pathname.replace('/platform-api', '')
    calls.push(path)
    if (options.unavailable) return route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'Le service de comptes est indisponible.' } } })
    if (path === '/auth/session') return route.fulfill({ json: session() })
    if (route.request().method() !== 'GET' && route.request().headers()['x-csrf-token'] !== 'test-csrf') return route.fulfill({ status: 403 })
    if (path === '/auth/register' || path === '/auth/login') {
      authenticated = true
      const body = route.request().postDataJSON()
      user.email = body.email
      if (body.displayName) user.displayName = body.displayName
      return route.fulfill({ status: path === '/auth/register' ? 201 : 200, json: session() })
    }
    if (path === '/auth/logout') { authenticated = false; return route.fulfill({ status: 204 }) }
    if (path.startsWith('/users/')) { user.displayName = route.request().postDataJSON().displayName; return route.fulfill({ json: { user } }) }
    if (path === '/admin/access') return route.fulfill({ json: { role: 'admin', administrationAvailable: true } })
    if (path === '/admin/overview') return route.fulfill({json:{totals:{users:1,active_users:1,active_admins:1,datasets:0,suspended_datasets:0,versions:0,imported_rows:'0',analyses:0,dashboards:0,failures_last_week:0},recentImports:[],recentFailures:[]}})
    return route.fulfill({ status: 404 })
  })
  return { calls, expire: () => { authenticated = false } }
}
