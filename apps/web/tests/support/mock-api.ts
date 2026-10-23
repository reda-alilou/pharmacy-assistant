import type { Page, Route } from '@playwright/test'
import raw from '../fixtures/responses.json' with { type: 'json' }

export const TOKEN = 'test_session_token_long_enough_1234567890'
export const CONTINUATION = 'test_continuation_long_enough_1234567890'
export type MockOptions = { delay?: number; expired?: boolean; pending?: boolean; failure?: string; cooldown?: number; invalid?: boolean }

export async function mockApi(page: Page, options: MockOptions = {}) {
  let responseGate: Promise<void> | null = null
  let releaseResponse: (() => void) | null = null
  const calls: Record<string, unknown>[] = []
  const messages: Record<string, unknown>[] = []
  let current: Record<string, unknown> | null = null
  let expires = new Date(Date.now() + 1_800_000).toISOString()
  let restoreFailure = false
  let resetFailure = false
  let chatFailure = options.failure
  let pending = options.pending ?? false
  let deleted = false
  let lostAfterCompletion = false
  const prepare = (source: unknown) => ({ ...structuredClone(source as Record<string, unknown>), session_id: TOKEN,
    continuation_id: (source as Record<string, unknown>).status === 'needs_clarification' ? CONTINUATION : null,
    session_expires_at_utc: expires, continuation_expires_at_utc: expires })
  const view = () => ({ session_id: TOKEN, expires_at_utc: expires, messages, response: current })
  const user = (text: string | null, outcome: string, payload: unknown = null) => messages.push({
    sequence: messages.length, role: 'user', outcome, text, created_at_utc: new Date().toISOString(), payload })
  const answer = (source: unknown) => {
    current = prepare(source)
    const payload = { ...current }; delete payload.session_id; delete payload.continuation_id
    messages.push({ sequence: messages.length, role: 'assistant', outcome: 'answered', text: current.answer,
      created_at_utc: new Date().toISOString(), payload })
  }
  async function fulfill(route: Route, status: number, body: unknown, headers = {}) {
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body), headers })
  }
  await page.route(url => url.pathname.startsWith('/api/'), async route => {
    const request = route.request(), path = new URL(request.url()).pathname
    if (path === '/api/conversation') {
      if (request.method() === 'POST') { deleted = false; return fulfill(route, 200, view()) }
      if (request.method() === 'DELETE') {
        if (resetFailure) return fulfill(route, 503, { detail: { code: 'storage_unavailable', retryable: true } })
        deleted = true; current = null; messages.length = 0; return route.fulfill({ status: 204 })
      }
      if (options.expired || deleted) return fulfill(route, 410, { detail: { code: 'session_expired' } })
      if (restoreFailure) return fulfill(route, 503, { detail: { code: 'storage_unavailable', retryable: true } })
      return fulfill(route, 200, view())
    }
    if (path === '/api/chat') {
      const body = request.postDataJSON() as Record<string, unknown>; calls.push(body)
      const typed = typeof body.text === 'string'
      const failure = typed ? chatFailure : undefined
      user(typed ? body.text as string : null, pending && typed ? 'pending' : failure ? 'failed' : 'answered',
        failure ? { error_code: failure } : { action: { ...body } })
      if (options.delay) await new Promise(resolve => setTimeout(resolve, options.delay))
      if (responseGate) await responseGate
      if (pending && typed) return route.abort('connectionreset')
      if (failure) return fulfill(route, options.cooldown ? 429 : 503,
        { detail: { code: failure, retryable: true, retry_after_seconds: options.cooldown ?? null, message: 'PRIVATE PROVIDER BODY' } },
        options.cooldown ? { 'Retry-After': String(options.cooldown) } : {})
      expires = new Date(Date.now() + 1_800_000).toISOString()
      answer(body.selections ? raw.selected : typeof body.text === 'string' && body.text.includes('deux') ? raw.two
        : typeof body.text === 'string' && body.text.includes('Agdal') ? raw.pharmacy : raw.initial)
      if (lostAfterCompletion) return route.abort('connectionreset')
      if (options.invalid) return fulfill(route, 200, { answer: 'UNTRUSTED UNVALIDATED PRICE 999999' })
      return fulfill(route, 200, current)
    }
    return fulfill(route, 404, {})
  })
  return { calls, messages, view, prepare,
    holdResponse: () => { responseGate = new Promise<void>(resolve => { releaseResponse = resolve }) },
    releaseResponse: () => { releaseResponse?.(); responseGate = null; releaseResponse = null },
    failChat: (code: string | undefined) => { chatFailure = code }, failRestore: (value: boolean) => { restoreFailure = value },
    failReset: (value: boolean) => { resetFailure = value }, loseResponse: () => { lostAfterCompletion = true },
    finishPending: () => { pending = false; const last = messages.at(-1)!; last.outcome = 'answered'; answer(raw.initial) },
    expire: () => { options.expired = true },
    seed: (kind: keyof typeof raw = 'initial') => { messages.length = 0; user('Quel est le prix de ABIP 15mg ?', 'answered'); answer(raw[kind]) },
    seedCustom: (source: unknown) => { messages.length = 0; user('Une question de démonstration', 'answered'); answer(source) },
  }
}
export { raw }
