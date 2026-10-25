"""Backup/restore checks through the existing normal PostgreSQL container only.

No container lifecycle, host ports, credential changes or original-database restore.
Docker exec runs PostgreSQL's own clients with credentials kept inside the container.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import uuid

from sqlalchemy.engine import make_url

from pharmacy_infrastructure.paths import ROOT
from pharmacy_ops.backup import TEMPORARY_TABLES
from pharmacy_ops.database import configuration

PROJECT = 'pharmacy-assistant-architecture'
VOLUME = PROJECT + '_postgres_data'
SCHEMAS = ('core', 'language', 'platform')
TABLES_SQL = """SELECT coalesce(json_agg(json_build_object('schema',n.nspname,'table',c.relname)
ORDER BY n.nspname,c.relname),'[]')::text FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind IN ('r','p') AND n.nspname IN ('core','language','platform')"""


def identifier(value):
    return '"' + value.replace('"', '""') + '"'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


class ComposeBackup:
    def __init__(self, env_file):
        self.env_file = Path(env_file).resolve()
        values = configuration(self.env_file)
        url = make_url(values.get('MIGRATION_DATABASE_URL', ''))
        if (url.drivername != 'postgresql+psycopg' or url.host != 'postgres' or url.port != 5432
                or url.database != values.get('POSTGRES_DB') or url.username != values.get('POSTGRES_USER')
                or not url.password or url.password != values.get('POSTGRES_PASSWORD')):
            raise ValueError('Use the unchanged normal Compose configuration.')
        self.database, self.user = url.database, url.username
        self.command = ['docker', 'compose', '-p', PROJECT, '--env-file', str(self.env_file),
                        '-f', str(ROOT / 'deploy/compose.yaml')]
        container = self.run(self.command + ['ps', '--all', '--quiet', 'postgres']).decode().strip()
        if not re.fullmatch(r'[a-f0-9]{12,64}', container):
            raise ValueError('The user must start only the normal PostgreSQL service first.')
        self.container = container
        raw = self.run(['docker', 'inspect', '--format', '{{json .}}', container])
        inspected = json.loads(raw)
        # Never print inspect output: it includes environment values. Validate in memory.
        labels = inspected.get('Config', {}).get('Labels', {})
        mounts = [m for m in inspected.get('Mounts', []) if m.get('Destination') == '/var/lib/postgresql/data']
        if (labels.get('com.docker.compose.project') != PROJECT
                or labels.get('com.docker.compose.service') != 'postgres'
                or inspected.get('State', {}).get('Running') is not True
                or len(mounts) != 1 or mounts[0].get('Type') != 'volume'
                or mounts[0].get('Name') != VOLUME):
            raise ValueError('Refusing a different PostgreSQL project or data volume.')
        identity = self.sql("SELECT json_build_object('database',current_database(),'user',current_user,'major',current_setting('server_version_num')::int/10000)::text")
        if identity != {'database': self.database, 'user': self.user, 'major': 17}:
            raise ValueError('Database identity/version does not match the configured installation.')

    @staticmethod
    def run(arguments, *, input=None, stdin=None, stdout=None):
        completed = subprocess.run(arguments, input=input, stdin=stdin, stdout=stdout or subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=180, cwd=ROOT)
        if completed.returncode:
            raise ValueError('Container database operation failed; credentials and diagnostics withheld.')
        return completed.stdout

    def pg(self, program, args=(), *, database=None, input=None, stdin=None, stdout=None):
        # Fixed shell source only; user-controlled values are argv, never shell code.
        command = ['docker', 'exec', '-i', self.container, 'sh', '-c',
                   'PGPASSWORD="$POSTGRES_PASSWORD" PGCONNECT_TIMEOUT=5 PGOPTIONS="-c timezone=UTC -c datestyle=ISO -c statement_timeout=60000 -c lock_timeout=3000" exec "$@"',
                   '--', program, '--host', '127.0.0.1', '--port', '5432', '--username', self.user,
                   '--dbname', database or self.database, *args]
        return self.run(command, input=input, stdin=stdin, stdout=stdout)

    def sql(self, query, database=None):
        raw = self.pg('psql', ['-X', '--quiet', '--no-align', '--tuples-only', '--set', 'ON_ERROR_STOP=1'],
                      database=database, input=query.encode('utf-8'))
        return json.loads(raw.decode('utf-8').strip())

    def execute(self, query, database='postgres'):
        self.pg('psql', ['-X', '--quiet', '--set', 'ON_ERROR_STOP=1'], database=database,
                input=query.encode('utf-8'))

    def idle(self):
        running = self.run(self.command + ['ps', '--services', '--status', 'running']).decode().split()
        if set(running) != {'postgres'}:
            raise ValueError('Keep application writers stopped while backing up and verifying; the user controls lifecycle.')

    def fingerprint(self, database=None):
        tables = self.sql(TABLES_SQL, database)
        if not any(t['schema'] == 'core' for t in tables) or not any(t['schema'] == 'language' for t in tables):
            raise ValueError('Expected existing assistant schemas; refusing an empty or unrelated installation.')
        result = {}
        for table in tables:
            if table['schema'] not in SCHEMAS or not isinstance(table['table'], str):
                raise ValueError('Unexpected database namespace.')
            key = table['schema'] + '.' + table['table']
            if key in TEMPORARY_TABLES:
                continue
            name = identifier(table['schema']) + '.' + identifier(table['table'])
            result[key] = self.sql(f"SELECT json_build_object('rows',count(*)::text,'digest',encode(sha256(convert_to(coalesce(string_agg(row_digest,'' ORDER BY row_digest),''),'UTF8')),'hex'))::text FROM (SELECT encode(sha256(convert_to(row_to_json(t)::text,'UTF8')),'hex') row_digest FROM {name} t) fingerprints", database)
        return tables, result

    def status(self):
        tables = self.sql(TABLES_SQL)
        present = {'platform.users', 'platform.schema_migrations'}.issubset({t['schema']+'.'+t['table'] for t in tables})
        active_admins = self.sql("SELECT count(*)::int FROM platform.users WHERE active AND role='admin'") if present else 0
        revisions = self.sql("SELECT coalesce(json_agg(version ORDER BY version),'[]')::text FROM platform.schema_migrations") if present else []
        role = self.sql("SELECT to_json(EXISTS(SELECT 1 FROM pg_roles WHERE rolname='pharmacy_platform'))::text")
        return {'project': PROJECT, 'volume': VOLUME, 'postgres_major': 17, 'platform_installed': present,
                'platform_runtime_role_exists': role, 'platform_migrations': revisions,
                'active_administrators': active_admins, 'credentials_printed': False,
                'container_lifecycle_performed': False}

    def backup(self, path):
        self.idle()
        path = Path(path).resolve()
        manifest = Path(str(path) + '.manifest.json')
        if path.exists() or manifest.exists():
            raise ValueError('Choose a new backup path; existing files are preserved.')
        path.parent.mkdir(parents=True, exist_ok=True)
        tables, before = self.fingerprint()
        owned_manifest = owned_dump = False
        try:
            with manifest.open('x', encoding='utf-8') as metadata:
                owned_manifest = True
                with path.open('xb') as dump:
                    owned_dump = True
                    self.pg('pg_dump', ['--format=custom', '--no-owner', '--no-privileges',
                            *('--exclude-table-data='+t for t in TEMPORARY_TABLES)], stdout=dump)
                if not path.stat().st_size:
                    raise ValueError('Backup returned an empty file.')
                if self.fingerprint() != (tables, before):
                    raise ValueError('Database writes occurred during backup; keep writers idle and retry.')
                json.dump({'format': 1, 'project': PROJECT, 'volume': VOLUME, 'sha256': sha256(path),
                           'tables': tables, 'fingerprints': before}, metadata)
        except Exception:
            if owned_dump:
                path.unlink(missing_ok=True)
            if owned_manifest:
                manifest.unlink(missing_ok=True)
            raise
        return {'backup': str(path), 'manifest': str(manifest), 'backup_created': True,
                'temporary_history_sessions_and_staging_excluded': True, 'restore_verified': False,
                'container_lifecycle_performed': False}

    def verify(self, path):
        self.idle()
        path = Path(path).resolve()
        manifest = json.loads(Path(str(path)+'.manifest.json').read_text(encoding='utf-8'))
        if (manifest.get('format') != 1 or manifest.get('project') != PROJECT or manifest.get('volume') != VOLUME
                or manifest.get('sha256') != sha256(path)):
            raise ValueError('Backup identity/checksum mismatch; no database was restored.')
        baseline = self.fingerprint()
        if baseline != (manifest['tables'], manifest['fingerprints']):
            raise ValueError('Source changed since backup; do not use this verification as current evidence.')
        name = 'pharmacy_backup_verify_' + uuid.uuid4().hex
        if not re.fullmatch(r'pharmacy_backup_verify_[a-f0-9]{32}', name) or name == self.database:
            raise ValueError('Invalid temporary restore identity.')
        created = False
        try:
            self.execute(f'CREATE DATABASE {identifier(name)} TEMPLATE template0'); created = True
            with path.open('rb') as dump:
                self.pg('pg_restore', ['--exit-on-error', '--no-owner', '--no-privileges'], database=name, stdin=dump)
            if self.fingerprint(name) != baseline:
                raise ValueError('Restored persistent table values differ from the original.')
            restored_tables = {t['schema']+'.'+t['table'] for t in baseline[0]}
            for table in TEMPORARY_TABLES:
                if table in restored_tables:
                    schema, relation = table.split('.')
                    if self.sql(f'SELECT count(*)::int FROM {identifier(schema)}.{identifier(relation)}', name) != 0:
                        raise ValueError('Backup retained excluded temporary state.')
            if self.fingerprint() != baseline:
                raise ValueError('Source changed during restore verification; keep writers idle and retry.')
        finally:
            if created:
                assert re.fullmatch(r'pharmacy_backup_verify_[a-f0-9]{32}', name) and name != self.database
                self.execute(f'DROP DATABASE {identifier(name)} WITH (FORCE)')
        return {'restore_verified': True, 'verified_persistent_tables': len(baseline[1]),
                'temporary_history_sessions_and_staging_absent': True, 'source_database_unchanged': True,
                'temporary_restore_database_removed': True, 'application_volume': VOLUME,
                'container_lifecycle_performed': False}
