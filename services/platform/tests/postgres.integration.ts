import assert from 'node:assert/strict'
import { randomUUID } from 'node:crypto'
import { execFile } from 'node:child_process'
import { mkdtemp, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { promisify } from 'node:util'
import test from 'node:test'
import request from 'supertest'
import { createApp } from '../src/app.js'
import { createPool } from '../src/database.js'
import { grantRuntime, migrate } from '../src/migrations.js'
import { provision, permissions } from '../src/administration.js'
import { digest, hashPassword, newToken } from '../src/security.js'
import { PostgresStore } from '../src/store.js'

// Hard-coded disposable cluster identity prevents accepting an application URL.
const clusterUrl = new URL('postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test')
const database = `platform_cp1_${randomUUID().replaceAll('-', '')}`
const runtimePassword = 'platform-test-runtime-password-at-least-32-characters'
const origin = 'http://127.0.0.1:5177'

test('real PostgreSQL Checkpoint 1 (dedicated user-started test cluster only)', async t => {
  const cluster = createPool(clusterUrl.href)
  let created = false
  let pool: ReturnType<typeof createPool> | undefined
  let runtime: ReturnType<typeof createPool> | undefined
  try {
    const identity = await cluster.query('SELECT current_user, current_database()')
    assert.equal(identity.rows[0].current_user, 'platform_test_admin')
    assert.equal(identity.rows[0].current_database, 'platform_checkpoint1_test')
    assert.match(database, /^platform_cp1_[a-f0-9]{32}$/)
    await cluster.query(`CREATE DATABASE "${database}"`)
    created = true
    const url = new URL(clusterUrl); url.pathname = `/${database}`
    pool = createPool(url.href)
    const admin = pool
    await t.test('atomic, repeatable, checksummed migration and restricted runtime grants', async () => {
      await admin.query(`CREATE SCHEMA core; CREATE SCHEMA language;
        REVOKE ALL ON SCHEMA core,language FROM PUBLIC;
        CREATE TABLE core.private_data(secret text); CREATE TABLE language.private_data(secret text)`)
      await migrate(admin); await migrate(admin)
      assert.equal((await admin.query('SELECT count(*)::int n FROM platform.schema_migrations')).rows[0].n, 3)
      const before = await admin.query("SELECT checksum FROM platform.schema_migrations WHERE version='0001_accounts.sql'")
      await admin.query("UPDATE platform.schema_migrations SET checksum='changed' WHERE version='0001_accounts.sql'")
      await assert.rejects(migrate(admin), /checksum/)
      await admin.query("UPDATE platform.schema_migrations SET checksum=$1 WHERE version='0001_accounts.sql'", [before.rows[0].checksum])
      await grantRuntime(admin, runtimePassword); await grantRuntime(admin, runtimePassword)
      url.username = 'pharmacy_platform'; url.password = runtimePassword
      runtime = createPool(url.href)
      await runtime.query('SELECT * FROM platform.users')
      for (const sql of ['SELECT * FROM core.private_data', 'SELECT * FROM language.private_data',
        'CREATE TABLE platform.forbidden(id int)', "UPDATE platform.schema_migrations SET checksum='bad'", 'DELETE FROM platform.activity'])
        await assert.rejects(runtime.query(sql), { code: '42501' })
      const privileges = await admin.query(`SELECT has_schema_privilege('pharmacy_platform','platform','CREATE') ddl,
        has_table_privilege('pharmacy_platform','platform.schema_migrations','UPDATE') migrations`)
      assert.deepEqual(privileges.rows[0], { ddl: false, migrations: false })
      for (const role of ['cp1_core_probe', 'cp1_language_probe']) {
        if (!(await admin.query('SELECT 1 FROM pg_roles WHERE rolname=$1', [role])).rowCount) await admin.query(`CREATE ROLE ${role}`)
        const connection = await admin.connect()
        try {
          await connection.query(`SET ROLE ${role}`)
          await assert.rejects(connection.query('SELECT * FROM platform.users'), { code: '42501' })
        } finally { await connection.query('RESET ROLE'); connection.release() }
      }
    })
    if (!runtime) throw new Error('Runtime grant gate failed')
    const store = new PostgresStore(runtime)
    await store.ready()
    await assert.rejects(new PostgresStore(admin).ready(), /runtime permissions/)
    const app = createApp(store, { origin, secureCookie: false, trustProxy: false })
    type Browser = { cookie: string; csrf: string }
    const fresh = async (): Promise<Browser> => {
      const response = await request(app).get('/auth/session').expect(200)
      return { cookie: response.headers['set-cookie'][0].split(';')[0]!, csrf: response.body.csrfToken }
    }
    const post = (browser: Browser, path: string, body = {}) => request(app).post(path).set('Origin', origin).set('Cookie', browser.cookie).set('X-CSRF-Token', browser.csrf).send(body)
    const login = async (email: string, password = 'analyst-password-123'): Promise<Browser> => {
      const response = await post(await fresh(), '/auth/login', { email, password }).expect(200)
      return { cookie: response.headers['set-cookie'][0].split(';')[0]!, csrf: response.body.csrfToken }
    }
    let analyst: Browser, userId: string
    await t.test('registration, login rotation, CSRF, profile ownership, logout and persistence', async () => {
      const anon = await fresh()
      await post(anon, '/auth/register', { email: 'one@example.test', displayName: 'One', password: 'analyst-password-123', role: 'admin' }).expect(422)
      const registered = await post(anon, '/auth/register', { email: ' ONE@EXAMPLE.TEST ', displayName: 'One', password: 'analyst-password-123' }).expect(201)
      userId = registered.body.user.id
      analyst = { cookie: registered.headers['set-cookie'][0].split(';')[0]!, csrf: registered.body.csrfToken }
      assert.equal(registered.body.user.role, 'analyst')
      assert.notEqual(analyst.cookie, anon.cookie)
      assert.equal(await store.session(anon.cookie.split('=')[1]!), null)
      const rows = await admin.query('SELECT token_hash FROM platform.sessions WHERE user_id=$1', [userId])
      assert.equal(rows.rows[0].token_hash, digest(analyst.cookie.split('=')[1]!))
      assert.doesNotMatch(JSON.stringify(registered.body), /password_hash|scrypt|token_hash/)
      await request(app).get(`/users/${userId}`).set('Cookie', analyst.cookie).expect(200)
      await request(app).get(`/users/${randomUUID()}`).set('Cookie', analyst.cookie).expect(403)
      await request(app).get('/admin/access').set('Cookie', analyst.cookie).expect(403)
      await request(app).patch(`/users/${userId}`).set('Origin', origin).set('Cookie', analyst.cookie).send({ displayName: 'Hacked' }).expect(403)
      await request(app).patch(`/users/${userId}`).set('Origin', 'https://evil.test').set('Cookie', analyst.cookie).set('X-CSRF-Token', analyst.csrf).send({ displayName: 'Hacked' }).expect(403)
      await request(app).patch(`/users/${userId}`).set('Origin', origin).set('Cookie', analyst.cookie).set('X-CSRF-Token', analyst.csrf).send({ displayName: 'Edited', role: 'admin' }).expect(422)
      await request(app).patch(`/users/${userId}`).set('Origin', origin).set('Cookie', analyst.cookie).set('X-CSRF-Token', analyst.csrf).send({ displayName: 'Edited' }).expect(200)
      const replacementStore = new PostgresStore(runtime!)
      assert.equal((await replacementStore.session(analyst.cookie.split('=')[1]!))?.user?.displayName, 'Edited')
      await post(analyst, '/auth/logout').expect(204)
      await request(app).get(`/users/${userId}`).set('Cookie', analyst.cookie).expect(401)
      const unknown = await post(await fresh(), '/auth/login', { email: 'absent@example.test', password: 'wrong' }).expect(401)
      const wrong = await post(await fresh(), '/auth/login', { email: 'one@example.test', password: 'wrong' }).expect(401)
      assert.deepEqual(unknown.body, wrong.body)
      analyst = await login('one@example.test')
      const duplicate = await post(await fresh(), '/auth/register', { email: 'one@example.test', displayName: 'Duplicate', password: 'analyst-password-123' }).expect(409)
      assert.equal(duplicate.body.error.code, 'registration_unavailable')
    })
    await t.test('expiry (idle and absolute), cleanup and cross-process throttling', async () => {
      const token = newToken(); await store.issue(token, userId!)
      await admin.query("UPDATE platform.sessions SET expires_at=now()-interval '1 second' WHERE token_hash=$1", [digest(token)])
      assert.equal(await store.session(token), null)
      const absolute = newToken(); await store.issue(absolute, userId!)
      await admin.query("UPDATE platform.sessions SET created_at=now()-interval '1 day',expires_at=now()-interval '1 second',absolute_expires_at=now()-interval '1 second' WHERE token_hash=$1", [digest(absolute)])
      assert.equal(await store.session(absolute), null)
      await store.cleanup()
      assert.equal((await admin.query('SELECT count(*)::int n FROM platform.sessions WHERE token_hash IN ($1,$2)', [digest(token), digest(absolute)])).rows[0].n, 0)
      const otherStore = new PostgresStore(runtime!)
      const attempts = await Promise.allSettled(Array.from({ length: 12 }, (_, index) => (index % 2 ? store : otherStore).throttle('concurrent-probe', 4)))
      assert.equal(attempts.filter(result => result.status === 'fulfilled').length, 4)
      assert.equal(attempts.filter(result => result.status === 'rejected').length, 8)
      for (let index = 0; index < 11; index++) {
        const response = await post(await fresh(), '/auth/login', { email: 'throttle@example.test', password: 'wrong' })
        assert.equal(response.status, index < 10 ? 401 : 429)
        if (index === 10) assert.ok(Number(response.headers['retry-after']) > 0)
      }
    })
    await t.test('password change revokes all sessions and requires the current password', async () => {
      const second = await login('one@example.test')
      await post(analyst!, '/auth/password', { currentPassword: 'wrong', password: 'replacement-password-123' }).expect(401)
      await post(analyst!, '/auth/password', { currentPassword: 'analyst-password-123', password: 'replacement-password-123' }).expect(204)
      for (const browser of [analyst!, second]) await request(app).get(`/users/${userId!}`).set('Cookie', browser.cookie).expect(401)
      analyst = await login('one@example.test', 'replacement-password-123')
      assert.equal((await admin.query('SELECT count(*)::int n FROM platform.activity WHERE action=$1', ['account.password_changed'])).rows[0].n, 1)
    })
    await t.test('explicit provisioning, last-admin safeguard, role/disable changes immediately revoke access', async () => {
      await provision(admin, 'admin@example.test', 'Administrator', 'admin-password-123')
      await assert.rejects(provision(admin, 'one@example.test', 'Never elevate', 'another-password-123'), { code: '23505' })
      const administrator = await login('admin@example.test', 'admin-password-123')
      await request(app).get('/admin/access').set('Cookie', administrator.cookie).expect(200)
      await assert.rejects(permissions(admin, 'admin@example.test', 'analyst', true), { code: '23514' })
      await assert.rejects(permissions(admin, 'admin@example.test', 'admin', false), { code: '23514' })
      await permissions(admin, 'one@example.test', 'admin', true)
      await request(app).get(`/users/${userId!}`).set('Cookie', analyst!.cookie).expect(401)
      const promoted = await login('one@example.test', 'replacement-password-123')
      await request(app).get('/admin/access').set('Cookie', promoted.cookie).expect(200)
      await permissions(admin, 'one@example.test', 'analyst', true)
      await request(app).get('/admin/access').set('Cookie', promoted.cookie).expect(401)
      const active = await login('one@example.test', 'replacement-password-123')
      await permissions(admin, 'one@example.test', 'analyst', false)
      await request(app).get(`/users/${userId!}`).set('Cookie', active.cookie).expect(401)
      const disabled = await post(await fresh(), '/auth/login', { email: 'one@example.test', password: 'replacement-password-123' }).expect(401)
      assert.equal(disabled.body.error.code, 'invalid_credentials')
      await permissions(admin, 'one@example.test', 'analyst', true)
      // Two concurrent demotions cannot remove both active administrators.
      await provision(admin, 'other-admin@example.test', 'Second admin', 'another-admin-password')
      const changes = await Promise.allSettled([
        permissions(admin, 'admin@example.test', 'analyst', true),
        permissions(admin, 'other-admin@example.test', 'analyst', true),
      ])
      assert.equal(changes.filter(result => result.status === 'fulfilled').length, 1)
      assert.equal((await admin.query("SELECT count(*)::int n FROM platform.users WHERE role='admin' AND active")).rows[0].n, 1)
      const activity = await admin.query('SELECT details FROM platform.activity')
      assert.doesNotMatch(JSON.stringify(activity.rows), /password|session|csrf|analyst-password/)
    })
    await t.test('duplicate accounts cannot race; failed writes are atomic', async () => {
      const encoded = await hashPassword('unique-account-password')
      const outcomes = await Promise.allSettled([store.register('race@example.test', 'Race A', encoded), store.register('race@example.test', 'Race B', encoded)])
      assert.equal(outcomes.filter(outcome => outcome.status === 'fulfilled').length, 1)
      const count = await admin.query("SELECT count(*)::int n FROM platform.activity a JOIN platform.users u ON u.id=a.resource_id WHERE u.email='race@example.test'")
      assert.equal(count.rows[0].n, 1)
    })
    await t.test('maintained backup preserves platform accounts/activity and excludes live authentication state', async () => {
      const directory = await mkdtemp(join(tmpdir(), 'platform-cp1-backup-'))
      const restoreName = `platform_cp1_${randomUUID().replaceAll('-', '')}`
      let restoreCreated = false
      let restored: ReturnType<typeof createPool> | undefined
      try {
        const root = fileURLToPath(new URL('../../../', import.meta.url))
        const python = join(root, process.platform === 'win32' ? '.venv/Scripts/python.exe' : '.venv/bin/python')
        const dump = join(directory, 'platform.dump')
        const sourceUrl = new URL(clusterUrl); sourceUrl.pathname = `/${database}`
        await promisify(execFile)(python, ['-c', 'import os,sys; from pharmacy_ops.backup import backup; backup({"MIGRATION_DATABASE_URL":os.environ["CP1_BACKUP_DATABASE_URL"]},sys.argv[1])', dump], {
          cwd: root, env: { ...process.env, CP1_BACKUP_DATABASE_URL: sourceUrl.href.replace('postgresql:', 'postgresql+psycopg:') }, timeout: 30000,
        })
        await cluster.query(`CREATE DATABASE "${restoreName}"`); restoreCreated = true
        const restoreUrl = new URL(clusterUrl); restoreUrl.pathname = `/${restoreName}`
        const tool = process.platform === 'win32' ? join(process.env.ProgramFiles ?? 'C:/Program Files', 'PostgreSQL/17/bin/pg_restore.exe') : 'pg_restore'
        await promisify(execFile)(tool, ['--host', '127.0.0.1', '--port', '55433', '--username', 'platform_test_admin', '--dbname', restoreName, '--exit-on-error', '--no-owner', '--no-privileges', dump], {
          env: { ...process.env, PGPASSWORD: clusterUrl.password }, timeout: 30000,
        })
        restored = createPool(restoreUrl.href)
        for (const table of ['users', 'activity', 'schema_migrations']) {
          const sql = `SELECT row_to_json(t)::text data FROM platform.${table} t ORDER BY row_to_json(t)::text`
          assert.deepEqual((await restored.query(sql)).rows, (await admin.query(sql)).rows)
        }
        for (const table of ['sessions', 'auth_throttles']) assert.equal((await restored.query(`SELECT count(*)::int n FROM platform.${table}`)).rows[0].n, 0)
      } finally {
        await restored?.end()
        if (restoreCreated) await cluster.query(`DROP DATABASE "${restoreName}" WITH (FORCE)`)
        await rm(directory, { recursive: true, force: true })
      }
    })
  } finally {
    await runtime?.end(); await pool?.end()
    if (created) await cluster.query(`DROP DATABASE "${database}" WITH (FORCE)`)
    await cluster.end()
  }
})
