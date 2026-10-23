import assert from 'node:assert/strict'
import test from 'node:test'
import { csrfFor, digest, hashPassword, newToken, verifyPassword } from '../src/security.js'
import { registerBody, requireOwner, requireRole, type User } from '../src/contracts.js'

test('scrypt uses random salts and verifies only the correct password', async () => {
  const first = await hashPassword('test-password-123')
  const second = await hashPassword('test-password-123')
  assert.notEqual(first, second)
  assert.equal(await verifyPassword('test-password-123', first), true)
  assert.equal(await verifyPassword('wrong-password', first), false)
  assert.equal(await verifyPassword('test-password-123', 'corrupt'), false)
})
test('opaque identifiers and independent CSRF values; strict registration and authorization', () => {
  const token = newToken()
  assert.equal(token.length, 43)
  assert.notEqual(digest(token), token)
  assert.notEqual(csrfFor(token), token)
  assert.notEqual(csrfFor(newToken()), csrfFor(token))
  const user: User = { id: '090c80aa-b1a3-4ba3-8421-660b4ca48f73', email: 'a@example.com', displayName: 'A', role: 'analyst', createdAt: new Date().toISOString() }
  assert.throws(() => requireOwner(null, user.id), { status: 401 })
  assert.throws(() => requireOwner(user, 'another-id'), { status: 403 })
  assert.throws(() => requireRole(user, 'admin'), { status: 403 })
  assert.equal(requireOwner(user, user.id), user)
  assert.equal(registerBody.parse({ email: ' A@EXAMPLE.COM ', displayName: ' A ', password: 'long-password-123' }).email, 'a@example.com')
  assert.equal(registerBody.safeParse({ email: 'a@example.com', displayName: 'A', password: 'long-password-123', role: 'admin' }).success, false)
})
