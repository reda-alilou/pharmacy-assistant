import { randomUUID } from 'node:crypto'
import type pg from 'pg'
import { transaction } from './database.js'
import { ApiError, type User, userSchema } from './contracts.js'
import { digest } from './security.js'

export const IDLE_MS = 30 * 60_000
export const ABSOLUTE_MS = 12 * 60 * 60_000
export type Session = { user: User | null; expiresAt: string }
type Account = { user: User; passwordHash: string; active: boolean }
export interface AccountStore {
  ready(): Promise<void>
  session(token: string): Promise<Session | null>
  issue(token: string, userId: string | null, oldToken?: string, expectedPasswordHash?: string): Promise<Session>
  revoke(token: string): Promise<void>
  throttle(key: string, maximum: number): Promise<void>
  account(email: string): Promise<Account | null>
  register(email: string, displayName: string, passwordHash: string): Promise<User>
  profile(id: string, displayName: string): Promise<User>
  password(id: string, expected: string, replacement: string): Promise<void>
  cleanup(): Promise<void>
}
function user(row: Record<string, unknown>): User {
  return userSchema.parse({ id: row.id, email: row.email, displayName: row.display_name,
    role: row.role, createdAt: (row.created_at as Date).toISOString() })
}
export class PostgresStore implements AccountStore {
  constructor(public pool: pg.Pool) {}
  async ready() {
    const boundary = await this.pool.query(`SELECT current_user = 'pharmacy_platform' AS owned,
      has_schema_privilege(current_user,'platform','CREATE') AS ddl,
      EXISTS (SELECT 1 FROM pg_namespace WHERE nspname IN ('core','language') AND has_schema_privilege(current_user,oid,'USAGE')) AS peers`)
    if (!boundary.rows[0].owned || boundary.rows[0].ddl || boundary.rows[0].peers) throw new Error('Invalid platform runtime permissions')
    await this.pool.query('SELECT id FROM platform.users LIMIT 0')
    await this.pool.query('SELECT token_hash FROM platform.sessions LIMIT 0')
  }
  async session(token: string): Promise<Session | null> {
    const result = await this.pool.query(`UPDATE platform.sessions s SET last_seen_at = now(),
      expires_at = LEAST(now() + interval '30 minutes', absolute_expires_at)
      WHERE token_hash = $1 AND expires_at > now() AND absolute_expires_at > now()
      AND (user_id IS NULL OR EXISTS (SELECT 1 FROM platform.users u WHERE u.id = s.user_id AND u.active))
      RETURNING s.user_id, s.expires_at`, [digest(token)])
    const row = result.rows[0]
    if (!row) return null
    if (!row.user_id) return { user: null, expiresAt: row.expires_at.toISOString() }
    const account = await this.pool.query('SELECT * FROM platform.users WHERE id = $1 AND active', [row.user_id])
    if (!account.rows[0]) return null
    return { user: user(account.rows[0]), expiresAt: row.expires_at.toISOString() }
  }
  async issue(token: string, userId: string | null, oldToken?: string, expectedPasswordHash?: string): Promise<Session> {
    return transaction(this.pool, async db => {
      let currentUser: User | null = null
      if (userId) {
        const result = await db.query('SELECT * FROM platform.users WHERE id = $1 AND active FOR SHARE', [userId])
        if (!result.rows[0] || (expectedPasswordHash && result.rows[0].password_hash !== expectedPasswordHash))
          throw new ApiError(401, 'invalid_credentials', 'Adresse ou mot de passe incorrect.')
        currentUser = user(result.rows[0])
      }
      if (oldToken) await db.query('DELETE FROM platform.sessions WHERE token_hash = $1', [digest(oldToken)])
      const result = await db.query(`INSERT INTO platform.sessions(token_hash,user_id,expires_at,absolute_expires_at)
        VALUES ($1,$2,now()+interval '30 minutes',now()+interval '12 hours') RETURNING expires_at`, [digest(token), userId])
      return { user: currentUser, expiresAt: result.rows[0].expires_at.toISOString() }
    })
  }
  async revoke(token: string) { await this.pool.query('DELETE FROM platform.sessions WHERE token_hash = $1', [digest(token)]) }
  async throttle(key: string, maximum: number) {
    const result = await this.pool.query(`INSERT INTO platform.auth_throttles(key_hash,attempts,expires_at)
      VALUES ($1,1,now()+interval '15 minutes') ON CONFLICT(key_hash) DO UPDATE SET
      attempts = CASE WHEN auth_throttles.expires_at <= now() THEN 1 ELSE auth_throttles.attempts+1 END,
      expires_at = CASE WHEN auth_throttles.expires_at <= now() THEN now()+interval '15 minutes' ELSE auth_throttles.expires_at END
      RETURNING attempts, GREATEST(1,ceil(extract(epoch FROM (expires_at-now()))))::integer AS retry`, [digest(key)])
    if (result.rows[0].attempts > maximum) throw new ApiError(429, 'rate_limited', 'Trop de tentatives. Réessayez plus tard.', result.rows[0].retry)
  }
  async account(email: string): Promise<Account | null> {
    const result = await this.pool.query('SELECT * FROM platform.users WHERE email = $1', [email])
    const row = result.rows[0]
    return row ? { user: user(row), passwordHash: row.password_hash, active: row.active } : null
  }
  async register(email: string, displayName: string, passwordHash: string) {
    return transaction(this.pool, async db => {
      const result = await db.query(`INSERT INTO platform.users(id,email,display_name,password_hash)
        VALUES ($1,$2,$3,$4) RETURNING *`, [randomUUID(), email, displayName, passwordHash])
      const registered = user(result.rows[0])
      await db.query(`INSERT INTO platform.activity(actor_id,action,resource_id) VALUES ($1,'account.registered',$1)`, [registered.id])
      return registered
    })
  }
  async profile(id: string, displayName: string) {
    return transaction(this.pool, async db => {
      const result = await db.query('UPDATE platform.users SET display_name = $2, updated_at = now() WHERE id = $1 AND active RETURNING *', [id, displayName])
      if (!result.rows[0]) throw new ApiError(401, 'authentication_required', 'Connectez-vous pour continuer.')
      await db.query(`INSERT INTO platform.activity(actor_id,action,resource_id) VALUES ($1,'account.updated',$1)`, [id])
      return user(result.rows[0])
    })
  }
  async password(id: string, expected: string, replacement: string) {
    await transaction(this.pool, async db => {
      const result = await db.query('UPDATE platform.users SET password_hash = $3, updated_at = now() WHERE id = $1 AND password_hash = $2 AND active', [id, expected, replacement])
      if (!result.rowCount) throw new ApiError(409, 'account_changed', 'Le compte a changé. Reconnectez-vous.')
      await db.query(`INSERT INTO platform.activity(actor_id,action,resource_id) VALUES ($1,'account.password_changed',$1)`, [id])
    })
  }
  async cleanup() {
    await this.pool.query('DELETE FROM platform.sessions WHERE expires_at <= now() OR absolute_expires_at <= now()')
    await this.pool.query('DELETE FROM platform.auth_throttles WHERE expires_at <= now()')
  }
}
