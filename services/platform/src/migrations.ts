import { createHash } from 'node:crypto'
import { readFile, readdir } from 'node:fs/promises'
import type pg from 'pg'
import { transaction } from './database.js'

const directory = new URL('../migrations/', import.meta.url)
export async function migrate(pool: pg.Pool) {
  await transaction(pool, async db => {
    await db.query('SELECT pg_advisory_xact_lock(72419020)')
    await db.query('CREATE SCHEMA IF NOT EXISTS platform; REVOKE ALL ON SCHEMA platform FROM PUBLIC')
    await db.query(`CREATE TABLE IF NOT EXISTS platform.schema_migrations (
      version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())`)
    const files = (await readdir(directory)).filter(name => /^\d{4}_[a-z_]+\.sql$/.test(name)).sort()
    const known = await db.query('SELECT version, checksum FROM platform.schema_migrations ORDER BY version')
    if (known.rows.some(row => !files.includes(row.version))) throw new Error('Unknown platform migration')
    for (const version of files) {
      const sql = await readFile(new URL(version, directory), 'utf8')
      const checksum = createHash('sha256').update(sql).digest('hex')
      const applied = known.rows.find(row => row.version === version)
      if (applied) {
        if (applied.checksum !== checksum) throw new Error('Applied migration checksum mismatch')
        continue
      }
      await db.query(sql)
      await db.query('INSERT INTO platform.schema_migrations(version,checksum) VALUES ($1,$2)', [version, checksum])
    }
  })
}

export async function grantRuntime(pool: pg.Pool, password: string) {
  if (!/^[A-Za-z0-9_-]{32,128}$/.test(password)) throw new Error('Use a new random URL-safe platform password (32–128 characters)')
  await transaction(pool, async db => {
    await db.query('SELECT pg_advisory_xact_lock(72419020)')
    const existing = await db.query("SELECT rolname,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls FROM pg_roles WHERE rolname='pharmacy_platform'")
    if (existing.rows.some(role => role.rolsuper || role.rolcreatedb || role.rolcreaterole || role.rolreplication || role.rolbypassrls))
      throw new Error('Refusing privileged preexisting runtime role')
    // Password has a deliberately restricted alphabet; never accept arbitrary SQL here.
    if (!existing.rowCount) await db.query(`CREATE ROLE pharmacy_platform LOGIN PASSWORD '${password}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`)
    const memberships = await db.query("SELECT 1 FROM pg_auth_members WHERE member = 'pharmacy_platform'::regrole")
    if (memberships.rowCount) throw new Error('Runtime role must not have role memberships')
    const peers = await db.query("SELECT nspname FROM pg_namespace WHERE nspname IN ('core','language') AND has_schema_privilege('pharmacy_platform',oid,'USAGE')")
    if (peers.rowCount) throw new Error('Runtime role has unexpected peer-schema access')
    // Existing role credentials are never changed by repeated grants.
    await db.query('REVOKE ALL ON SCHEMA platform FROM PUBLIC; GRANT USAGE ON SCHEMA platform TO pharmacy_platform')
    await db.query('REVOKE ALL ON ALL TABLES IN SCHEMA platform FROM pharmacy_platform')
    await db.query('GRANT SELECT, INSERT, UPDATE, DELETE ON platform.users, platform.sessions, platform.auth_throttles TO pharmacy_platform')
    await db.query('GRANT SELECT, INSERT ON platform.activity TO pharmacy_platform; GRANT USAGE, SELECT ON SEQUENCE platform.activity_id_seq TO pharmacy_platform')
    await db.query('REVOKE ALL ON FUNCTION platform.guard_admin() FROM PUBLIC; GRANT EXECUTE ON FUNCTION platform.guard_admin() TO pharmacy_platform')
    if((await db.query("SELECT to_regclass('platform.datasets') IS NOT NULL present")).rows[0].present){
      await db.query('GRANT SELECT, INSERT, UPDATE, DELETE ON platform.datasets,platform.import_receipts,platform.import_uploads TO pharmacy_platform')
      await db.query('GRANT SELECT, INSERT ON platform.dataset_versions,platform.dataset_columns,platform.dataset_rows TO pharmacy_platform')
      await db.query('GRANT SELECT ON platform.dataset_dependencies TO pharmacy_platform')
    }
    if((await db.query("SELECT to_regclass('platform.analyses') IS NOT NULL present")).rows[0].present){
      await db.query('GRANT SELECT, INSERT, UPDATE, DELETE ON platform.analyses,platform.analysis_sources,platform.dataset_dependencies TO pharmacy_platform')
    }
    // No DDL, migration history writes, peer-schema grants or administrative credentials.
  })
}
