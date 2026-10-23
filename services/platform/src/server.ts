import { z } from 'zod'
import { createApp } from './app.js'
import { createPool } from './database.js'
import { PostgresStore } from './store.js'
import { DatasetService } from './datasets/service.js'

async function main() {
  const config = z.object({ PLATFORM_DATABASE_URL: z.string().min(1), PLATFORM_ORIGIN: z.url(),
    PLATFORM_COOKIE_SECURE: z.enum(['true', 'false']).default('true'),
    PLATFORM_TRUST_PROXY: z.enum(['true', 'false']).default('false'),
    PORT: z.coerce.number().int().min(1).max(65535).default(3000) }).parse(process.env)
  const origin = new URL(config.PLATFORM_ORIGIN)
  if (origin.origin !== config.PLATFORM_ORIGIN || (config.PLATFORM_COOKIE_SECURE === 'false' &&
    !['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname))) throw new Error('Invalid origin/cookie configuration')
  const pool = createPool(config.PLATFORM_DATABASE_URL)
  const store = new PostgresStore(pool)
  const datasets=new DatasetService(pool)
  try { await store.ready();await datasets.ready() } catch { await pool.end(); throw new Error('Database not ready') }
  const app = createApp(store, { origin: origin.origin, secureCookie: config.PLATFORM_COOKIE_SECURE === 'true', trustProxy: config.PLATFORM_TRUST_PROXY === 'true' },datasets)
  const server = app.listen(config.PORT, '0.0.0.0', () => process.stdout.write('Platform listening.\n'))
  const cleanup = () => Promise.all([store.cleanup(),datasets.cleanup()]).catch(() => process.stderr.write('Platform expiry cleanup unavailable.\n'))
  const timer = setInterval(cleanup, 60_000).unref()
  void cleanup()
  let closing = false
  const close = () => {
    if (closing) return
    closing = true
    clearInterval(timer)
    server.close(() => { void pool.end() })
    setTimeout(() => process.exit(1), 15000).unref()
  }
  process.on('SIGTERM', close)
  process.on('SIGINT', close)
}
main().catch(() => { process.stderr.write('Platform startup failed. Check configuration and explicit migrations; details withheld.\n'); process.exitCode = 1 })
