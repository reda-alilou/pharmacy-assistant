import assert from 'node:assert/strict'
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { parse } from 'dotenv'
import { configure } from '../src/administration.js'

test('new platform configuration preserves existing credentials and refuses overwrite', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'platform-config-test-'))
  try {
    const source = join(directory, 'existing.env'), output = join(directory, 'platform.env')
    const existing = "MIGRATION_DATABASE_URL='postgresql+psycopg://original_admin:synthetic-admin-secret@postgres:5432/pharmacy_assistant'\nGROQ_API_KEY='synthetic-provider-secret'\n"
    await writeFile(source, existing)
    await configure(source, output)
    const written = await readFile(output, 'utf8')
    const values = parse(written)
    const url = new URL(values.PLATFORM_DATABASE_URL!)
    assert.equal(url.username, 'pharmacy_platform')
    assert.equal(url.hostname, 'postgres')
    assert.equal(url.pathname, '/pharmacy_assistant')
    assert.match(url.password, /^[A-Za-z0-9_-]{43}$/)
    assert.equal(url.password, values.PLATFORM_DB_PASSWORD)
    assert.doesNotMatch(written, /original_admin|synthetic-admin-secret|synthetic-provider-secret/)
    await assert.rejects(configure(source, output), { code: 'EEXIST' })
    assert.equal(await readFile(source, 'utf8'), existing)
    assert.equal(await readFile(output, 'utf8'), written)
  } finally { await rm(directory, { recursive: true, force: true }) }
})
test('configuration fails without an existing migration URL', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'platform-config-test-'))
  try {
    const source = join(directory, 'missing.env'), output = join(directory, 'platform.env')
    await writeFile(source, 'OTHER=value\n')
    await assert.rejects(configure(source, output), /migration URL/)
    await assert.rejects(readFile(output), { code: 'ENOENT' })
  } finally { await rm(directory, { recursive: true, force: true }) }
})
