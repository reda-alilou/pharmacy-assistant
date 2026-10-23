import { randomBytes, randomUUID } from 'node:crypto'
import { readFile, writeFile } from 'node:fs/promises'
import { emitKeypressEvents } from 'node:readline'
import { parseArgs } from 'node:util'
import { parse } from 'dotenv'
import { z } from 'zod'
import { displayName, email, password as passwordSchema } from './contracts.js'
import { createPool, transaction } from './database.js'
import { grantRuntime, migrate } from './migrations.js'
import { hashPassword } from './security.js'

async function hiddenPassword(): Promise<string> {
  if (!process.stdin.isTTY) throw new Error('Interactive terminal or --password-file required')
  process.stdout.write('New password (12–128 characters; hidden): ')
  emitKeypressEvents(process.stdin)
  process.stdin.setRawMode(true)
  process.stdin.resume()
  return new Promise((resolve, reject) => {
    let value = ''
    const finish = () => { process.stdin.setRawMode(false); process.stdin.pause(); process.stdin.off('keypress', listener); process.stdout.write('\n') }
    const listener = (text: string | undefined, key: { name?: string; ctrl?: boolean }) => {
      if (key.ctrl && key.name === 'c') { finish(); reject(new Error('Cancelled')); return }
      if (key.name === 'return') { finish(); resolve(value); return }
      if (key.name === 'backspace') value = [...value].slice(0, -1).join('')
      else if (text && !key.ctrl) value += text
    }
    process.stdin.on('keypress', listener)
  })
}
export async function configure(source: string, output: string) {
  const values = parse(await readFile(source))
  const raw = values.MIGRATION_DATABASE_URL
  if (!raw) throw new Error('Existing Compose migration URL required')
  const original = new URL(raw.replace(/^postgresql\+psycopg:/, 'postgresql:'))
  const runtimePassword = randomBytes(32).toString('base64url')
  original.username = 'pharmacy_platform'
  original.password = runtimePassword
  original.search = ''
  await writeFile(output, `# Private platform configuration. Existing credentials are unchanged.\nPLATFORM_DATABASE_URL='${original.href}'\nPLATFORM_DB_PASSWORD='${runtimePassword}'\nPLATFORM_ORIGIN='http://127.0.0.1:8080'\nPLATFORM_COOKIE_SECURE='false'\n`, { flag: 'wx', mode: 0o600 })
}
export async function provision(pool: ReturnType<typeof createPool>, address: string, name: string, secret: string) {
  const encoded = await hashPassword(secret)
  await transaction(pool, async db => {
    await db.query('SELECT pg_advisory_xact_lock(72419021)')
    // New account only: never silently elevate or replace an existing account.
    const id = randomUUID()
    await db.query("INSERT INTO platform.users(id,email,display_name,password_hash,role) VALUES ($1,$2,$3,$4,'admin')", [id, address, name, encoded])
    await db.query("INSERT INTO platform.activity(actor_id,action,resource_id,details) VALUES ($1,'account.provisioned',$1,'{\"via\":\"explicit_cli\"}')", [id])
  })
}
export async function permissions(pool: ReturnType<typeof createPool>, address: string, role: 'analyst' | 'admin', active: boolean) {
  await transaction(pool, async db => {
    await db.query('SELECT pg_advisory_xact_lock(72419021)')
    const before = await db.query('SELECT id,role,active FROM platform.users WHERE email=$1 FOR UPDATE', [address])
    if (!before.rowCount) throw new Error('Account not found')
    await db.query('UPDATE platform.users SET role=$2,active=$3,updated_at=now() WHERE email=$1', [address, role, active])
    await db.query(`INSERT INTO platform.activity(action,resource_id,details) VALUES ('account.permissions_changed',$1,$2)`,
      [before.rows[0].id, JSON.stringify({ via: 'explicit_cli', before: { role: before.rows[0].role, active: before.rows[0].active }, after: { role, active } })])
  })
}
export async function main() {
  const { positionals, values } = parseArgs({ allowPositionals: true, options: {
    'env-file': { type: 'string' }, source: { type: 'string' }, output: { type: 'string' },
    email: { type: 'string' }, name: { type: 'string' }, 'password-file': { type: 'string' },
    role: { type: 'string' }, active: { type: 'string' }, confirm: { type: 'boolean' }, help: { type: 'boolean' },
  } })
  const action = positionals[0]
  if (values.help || !action) {
    process.stdout.write('Actions: configure --source <existing compose.env> --output <new platform.env>; migrate; grant; provision-admin --email <email> --name <name> [--password-file <private file>]; set-account --email <email> --role analyst|admin --active true|false --confirm. Database actions accept --env-file <private env>. Passwords are never command-line arguments.\n')
    return
  }
  if (action === 'configure') {
    if (!values.source || !values.output) throw new Error('Source and output required')
    await configure(values.source, values.output)
  } else {
    const environment = { ...(values['env-file'] ? parse(await readFile(values['env-file'])) : {}), ...process.env }
    const url = z.string().min(1).parse(environment.MIGRATION_DATABASE_URL)
    const pool = createPool(url)
    try {
      if (action === 'migrate') await migrate(pool)
      else if (action === 'grant') await grantRuntime(pool, z.string().parse(environment.PLATFORM_DB_PASSWORD))
      else if (action === 'provision-admin') {
        const secret = values['password-file'] ? (await readFile(values['password-file'], 'utf8')).replace(/\r?\n$/, '') : await hiddenPassword()
        await provision(pool, email.parse(values.email), displayName.parse(values.name), passwordSchema.parse(secret))
      } else if (action === 'set-account') {
        if (!values.confirm) throw new Error('Explicit --confirm is required: permissions change immediately; disabled owners retain resources and explicit shares')
        await permissions(pool, email.parse(values.email), z.enum(['analyst', 'admin']).parse(values.role), z.enum(['true', 'false']).parse(values.active) === 'true')
      } else throw new Error('Unknown action')
    } finally { await pool.end() }
  }
  process.stdout.write('Platform operation completed; secrets withheld.\n')
}
