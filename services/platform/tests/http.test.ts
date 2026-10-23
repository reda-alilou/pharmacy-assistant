import assert from 'node:assert/strict'
import test from 'node:test'
import request from 'supertest'
import { createApp } from '../src/app.js'
import type { AccountStore } from '../src/store.js'

// These are boundary/failure checks; real persistence is exercised separately.
const store = (): AccountStore => ({
  ready: async () => {}, session: async () => null,
  issue: async () => ({ user: null, expiresAt: new Date(Date.now() + 60000).toISOString() }),
  revoke: async () => {}, throttle: async () => {}, account: async () => null,
  register: async () => { throw new Error('unexpected') }, profile: async () => { throw new Error('unexpected') },
  password: async () => {}, cleanup: async () => {},
})
test('pre-auth CSRF, origin, content type, cookie flags and safe failures', async () => {
  const persistence = store()
  const app = createApp(persistence, { origin: 'https://example.test', secureCookie: true, trustProxy: false })
  const bootstrap = await request(app).get('/auth/session').expect(200)
  assert.match(bootstrap.headers['set-cookie'][0], /HttpOnly/)
  assert.match(bootstrap.headers['set-cookie'][0], /Secure/)
  assert.match(bootstrap.headers['set-cookie'][0], /SameSite=Lax/)
  assert.match(bootstrap.headers['set-cookie'][0], /Path=\/platform-api/)
  assert.equal(bootstrap.headers['cache-control'], 'no-store')
  assert.equal(bootstrap.body.user, null)
  await request(app).post('/auth/login').set('Origin', 'https://evil.test').send({}).expect(403)
  await request(app).post('/auth/login').set('Origin', 'https://example.test').send({}).expect(403)
  await request(app).post('/auth/login').set('Origin', 'https://example.test').type('form').send('x=y').expect(415)
  await request(app).get('/admin/access').expect(401)
  await request(app).get('/users/other').expect(401)
  const malformed = await request(app).post('/auth/login').set('Content-Type', 'application/json').send('{').expect(400)
  assert.equal(malformed.body.error.code, 'invalid_json')
  persistence.ready = async () => { throw new Error('private password and SQL') }
  const failure = await request(app).get('/ready').expect(503)
  assert.doesNotMatch(JSON.stringify(failure.body), /password|SQL/)
  assert.equal(failure.headers['cache-control'], 'no-store')
})
