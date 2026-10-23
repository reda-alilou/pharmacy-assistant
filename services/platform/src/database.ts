import pg, { type PoolClient } from 'pg'

export function createPool(url: string) {
  const pool = new pg.Pool({ connectionString: url.replace(/^postgresql\+psycopg:/, 'postgresql:'), max: 8,
    connectionTimeoutMillis: 5000, idleTimeoutMillis: 30000,
    options: '-c statement_timeout=10000 -c lock_timeout=3000 -c timezone=UTC -c search_path=platform,pg_catalog' })
  // Never log error objects: connection strings or SQL values may contain secrets.
  pool.on('error', () => process.stderr.write('Platform database connection unavailable.\n'))
  return pool
}
export async function transaction<T>(pool: pg.Pool, action: (db: PoolClient) => Promise<T>): Promise<T> {
  const db = await pool.connect()
  try {
    await db.query('BEGIN')
    const result = await action(db)
    await db.query('COMMIT')
    return result
  } catch (error) {
    await db.query('ROLLBACK')
    throw error
  } finally { db.release() }
}
