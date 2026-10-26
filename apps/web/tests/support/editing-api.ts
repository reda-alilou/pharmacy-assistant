import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

export const D = '11111111-1111-4111-8111-111111111111', V = '22222222-2222-4222-8222-222222222222'
export const A = '33333333-3333-4333-8333-333333333333', B = '44444444-4444-4444-8444-444444444444'
export const I = '88888888-8888-4888-8888-888888888888'
const U = '66666666-6666-4666-8666-666666666666', now = '2026-10-25T12:00:00.000Z'

/** All requests terminate here. No test backend, private data or inference. */
export async function editingApi(page: Page) {
  const raw = readFileSync(new URL('../fixtures/functional-review/cp6-v1.csv', import.meta.url), 'utf8').trim().split(/\r?\n/).map(row => row.split(','))
  const headers = raw.shift()!
  const columns = headers.map(name => ({ id: name, name, originalName: name, type: name === 'ppv_price_mad' ? 'decimal' : name === 'quantity' ? 'integer' : name === 'observation_date' ? 'date' : 'text', dateFormat: 'iso', booleanFormat: 'true-false' }))
  const configuration = { delimiter: ',', encoding: 'utf-8', trim: false, decimalSeparator: '.', missingMarkers: [''], columns }
  const user = { id: U, email: 'synthetic@example.test', displayName: 'Analyste de test', role: 'analyst', createdAt: now }
  let dataset = { id: D, ownerId: U, ownerName: user.displayName, title: 'TEST CP6', description: '', category: 'Test', source: 'SYNTHETIC_CP6_REVIEW', observationDate: '2026-01-01', archived: false, suspended: false, revision: 1, versionCount: 1, createdAt: now, updatedAt: now }
  const version = { id: V, datasetId: D, number: 1, rowCount: 9, columnCount: 8, filename: 'cp6-v1.csv', sourceSha256: 'a'.repeat(64), configuration, createdAt: now }
  const source = { datasetId: D, versionId: V, search: '', filters: [] }
  const definition = { algorithm: 'cp3-v1', source, kind: 'aggregate', measures: [{ operation: 'mean', column: 'ppv_price_mad', label: 'Prix moyen' }], groupBy: [{ column: 'group', interval: 'value' }], order: { by: 'measure', index: 0, direction: 'desc' }, limit: 20, chart: 'bar', style: { xLabel: 'Groupe', yLabel: 'Prix moyen', unit: 'MAD', precision: 2, legend: true } }
  let analysis = { id: A, ownerId: U, title: 'TEST CP6 moyenne', description: '', definition, revision: 1, createdAt: now, updatedAt: now, access: 'owner' }
  let dashboard = { id: B, ownerId: U, title: 'TEST CP6 tableau', description: '', configuration: { algorithm: 'cp4-v1', widgets: [], filters: [] }, revision: 1, createdAt: now, updatedAt: now, access: 'owner' }
  let receipt = { id: I, revision: 1, filename: 'cp6-v1.csv', status: 'staged', expiresAt: '2099-01-01T00:00:00.000Z', configuration, rowCount: 9, columnCount: 8, sample: raw, warnings: [], structure: { valid: true, issueCount: 0, issues: [], truncated: false }, validation: null as null | { valid: boolean; issueCount: number; issues: never[]; truncated: boolean; rowCount: number; columnCount: number } }
  const state = { user, authenticated: true, shared: false, fail: 0, abort: false, pending: null as Promise<void> | null, calls: [] as { path: string; method: string; body?: unknown }[] }
  await page.route(url => url.pathname.startsWith('/api/'), route => route.abort())
  await page.route('**/platform-api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname.replace('/platform-api', ''), method = request.method()
    const body = request.postData() && request.headers()['content-type']?.includes('application/json') ? request.postDataJSON() : undefined
    state.calls.push({ path, method, body })
    const send = (json: unknown) => route.fulfill({ json })
    if (method !== 'GET' && path !== '/analytics/templates') {
      if (state.pending) await state.pending
      if (state.abort) return route.abort('failed')
      if (state.fail) return route.fulfill({ status: state.fail, json: { error: { code: state.fail === 409 ? 'revision_conflict' : 'unavailable', message: state.fail === 409 ? 'La révision a changé.' : 'Enregistrement indisponible.' } } })
    }
    if (path === '/auth/session') return send({ user: state.authenticated ? user : null, csrfToken: 'synthetic-csrf', expiresAt: '2099-01-01T00:00:00.000Z' })
    if (path === '/auth/logout' || path === '/auth/password') { state.authenticated = false; return route.fulfill({ status: 204 }) }
    if (path === '/users/' + U) { user.displayName = body.displayName; return send({ user }) }
    if (path === '/datasets') return send({ datasets: [dataset], page: 1, hasMore: false })
    if (path === '/datasets/' + D) { if (method === 'PATCH') dataset = { ...dataset, ...body, revision: dataset.revision + 1 }; return send({ dataset, versions: [version] }) }
    if (path === `/datasets/${D}/versions`) return send({ versions: [version], total: 1, page: 1 })
    if (path === `/datasets/${D}/versions/${V}`) return send({ version, columns: columns.map(definition => ({ definition, profile: { total: 9, present: 8, missing: 1, distinct: 8, minimum: null, maximum: null } })) })
    if (path.endsWith('/rows')) return send({ versionId: V, total: 0, page: 1, pageSize: 25, rows: [] })
    if (path === '/analytics/templates') return send({ templates: [] })
    if (path === '/analytics/execute') return send(body.definition.groupBy?.length ? { algorithm: 'cp3-v1', definition: body.definition, sources: [{ datasetId: D, versionId: V, title: dataset.title, versionNumber: 1, importedRows: 9 }], conventions: { precision: 'Exact decimal values' }, kind: 'aggregate', filteredRows: 9, groupsTotal: 2, omittedGroups: 0, rows: [{ groups: ['B'], rowCount: 5, share: '55.555555555555555555', metrics: [{ value: '87.5', present: 4, missing: 1 }] }, { groups: ['A'], rowCount: 4, share: '44.444444444444444444', metrics: [{ value: '15', present: 4, missing: 0 }] }], plot: { zero: '0', positions: ['1', '0.1714285714'] } } : { algorithm: 'cp3-v1', definition: body.definition, sources: [{ datasetId: D, versionId: V, title: dataset.title, versionNumber: 1, importedRows: 9 }], conventions: { precision: 'Exact decimal values' }, kind: 'aggregate', filteredRows: 9, groupsTotal: 1, omittedGroups: 0, rows: [{ groups: [], rowCount: 9, share: '100', metrics: [{ value: '9', present: 9, missing: 0 }] }], plot: { zero: '0', positions: ['1'] } })
    if (path === '/analyses' && method === 'GET') return send({ analyses: [analysis], page: 1, hasMore: false })
    if (path === '/analyses' || path === '/analyses/' + A) { if (method === 'POST' || method === 'PATCH') analysis = { ...analysis, ...body, revision: analysis.revision + 1 }; return send({ analysis: { ...analysis, access: state.shared ? 'shared' : 'owner' } }) }
    if (path === '/dashboards' && method === 'GET') return send({ dashboards: [{ ...dashboard, widgetCount: 0 }], page: 1, hasMore: false })
    if (path === '/dashboards' || path === '/dashboards/' + B) { if (method === 'POST' || method === 'PATCH') dashboard = { ...dashboard, ...body, revision: dashboard.revision + 1 }; return send({ dashboard: { ...dashboard, access: state.shared ? 'shared' : 'owner' } }) }
    if (path === '/imports' && method === 'POST') return send({ id: I, filename: 'cp6-v1.csv', revision: 1, status: 'staged', expiresAt: receipt.expiresAt })
    if (path === '/imports/' + I && method === 'GET') return send(receipt)
    if (path === `/imports/${I}/validate` || path === `/imports/${I}/preview`) { receipt = { ...receipt, revision: receipt.revision + 1, configuration: { ...receipt.configuration, ...body.options, columns: body.columns ?? receipt.configuration.columns }, validation: path.endsWith('validate') ? { valid: true, issueCount: 0, issues: [], truncated: false, rowCount: 9, columnCount: 8 } : null }; return send(receipt) }
    if (path === `/imports/${I}/publish`) return send({ datasetId: D, versionId: V })
    if (path === '/imports/' + I && method === 'DELETE') return route.fulfill({ status: 204 })
    if (path.endsWith('/shares')) return send({ grants: [], authorizations: [], page: 1, hasMore: false })
    return route.fulfill({ status: 404, json: { error: { code: 'unhandled_fixture', message: 'Route non simulée.' } } })
  })
  return state
}
