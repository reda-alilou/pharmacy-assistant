"""Explicit real PG17 transport check; never runs container lifecycle commands.

Run separately with unittest discover -p compose_backup_postgres.py after the user
has started the dedicated localhost:55433 test cluster. Docker guards are unit
tested; here the same pg_dump/restore/psql stream is supplied by local PG17 clients.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

import psycopg
from psycopg import sql

from pharmacy_infrastructure.paths import ROOT
from pharmacy_ops.backup import tool
from pharmacy_ops.compose_backup import ComposeBackup

CLUSTER = 'postgresql://platform_test_admin:isolated-test-only-password@127.0.0.1:55433/platform_checkpoint1_test'


class RealComposeBackupTransport(unittest.TestCase):
    def test_pg17_binary_stream_fingerprints_exclusions_and_temporary_restore_cleanup(self):
        name = 'platform_cp6_' + uuid.uuid4().hex
        with psycopg.connect(CLUSTER, autocommit=True) as cluster:
            self.assertEqual(cluster.execute('SELECT current_user,current_database()').fetchone(),
                             ('platform_test_admin','platform_checkpoint1_test'))
            self.assertRegex(name,r'^platform_cp6_[a-f0-9]{32}$')
            cluster.execute(sql.SQL('CREATE DATABASE {} TEMPLATE template0').format(sql.Identifier(name)))
            try:
                with psycopg.connect(CLUSTER.replace('/platform_checkpoint1_test','/'+name), autocommit=True) as source:
                    source.execute("""CREATE SCHEMA core; CREATE SCHEMA language; CREATE SCHEMA platform;
                        CREATE TABLE core.facts(id text PRIMARY KEY, amount numeric, observed timestamptz, original jsonb);
                        INSERT INTO core.facts VALUES ('001',0,'2026-10-24 00:00:00.123456+00','{"text":"é"}'),('002',NULL,NULL,'{"text":"002"}');
                        CREATE TABLE language.quota(scope text PRIMARY KEY, attempts integer);
                        INSERT INTO language.quota VALUES('synthetic',3);
                        CREATE TABLE platform.users(id integer PRIMARY KEY, role text,active boolean,password_hash text);
                        INSERT INTO platform.users VALUES(1,'admin',true,'synthetic-private-hash');
                        CREATE TABLE platform.schema_migrations(version text PRIMARY KEY);
                        INSERT INTO platform.schema_migrations VALUES('0005_administration.sql');
                        CREATE TABLE core.conversations(id text); INSERT INTO core.conversations VALUES('synthetic-temporary');
                        CREATE TABLE platform.sessions(token_hash text); INSERT INTO platform.sessions VALUES('synthetic-session');
                        CREATE TABLE platform.auth_throttles(key_hash text); INSERT INTO platform.auth_throttles VALUES('synthetic-throttle');
                        CREATE TABLE platform.import_uploads(content bytea); INSERT INTO platform.import_uploads VALUES('synthetic-staging');""")
                operation=ComposeBackup.__new__(ComposeBackup)
                operation.database=name
                def pg(program,args=(),*,database=None,input=None,stdin=None,stdout=None):
                    command=[tool(program),'--host','127.0.0.1','--port','55433','--username','platform_test_admin','--dbname',database or name,*args]
                    environment={**os.environ,'PGPASSWORD':'isolated-test-only-password','PGCONNECT_TIMEOUT':'5',
                                 'PGOPTIONS':'-c timezone=UTC -c datestyle=ISO -c statement_timeout=60000 -c lock_timeout=3000'}
                    result=subprocess.run(command,input=input,stdin=stdin,stdout=stdout or subprocess.PIPE,
                                          stderr=subprocess.PIPE,env=environment,timeout=30)
                    if result.returncode:
                        raise ValueError('Synthetic database transport failed; diagnostics withheld.')
                    return result.stdout
                with tempfile.TemporaryDirectory(prefix='compose-backup-pg-',dir=ROOT/'.runtime') as directory:
                    self.assertEqual(Path(directory).resolve().parent,(ROOT/'.runtime').resolve())
                    self.assertTrue(Path(directory).name.startswith('compose-backup-pg-'))
                    path=Path(directory)/'synthetic.dump'
                    with patch.object(operation,'idle'),patch.object(operation,'pg',side_effect=pg):
                        status=operation.status()
                        self.assertTrue(status['platform_installed'])
                        self.assertEqual(status['active_administrators'],1)
                        self.assertEqual(status['platform_migrations'],['0005_administration.sql'])
                        operation.backup(path)
                        self.assertEqual(path.read_bytes()[:5],b'PGDMP')
                        manifest=json.loads(Path(str(path)+'.manifest.json').read_text(encoding='utf-8'))
                        self.assertEqual(manifest['fingerprints']['core.facts']['rows'],'2')
                        result=operation.verify(path)
                        self.assertTrue(result['restore_verified'])
                        self.assertTrue(result['source_database_unchanged'])
                        self.assertTrue(result['temporary_history_sessions_and_staging_absent'])
                        self.assertTrue(result['temporary_restore_database_removed'])
                        # A changed persistent source invalidates current verification.
                        with psycopg.connect(CLUSTER.replace('/platform_checkpoint1_test','/'+name),autocommit=True) as source:
                            source.execute('UPDATE language.quota SET attempts=4')
                        with self.assertRaisesRegex(ValueError,'Source changed since backup'):
                            operation.verify(path)
                self.assertEqual(cluster.execute('SELECT count(*) FROM pg_database WHERE datname LIKE %s',('pharmacy_backup_verify_%',)).fetchone()[0],0)
            finally:
                assert re.fullmatch(r'platform_cp6_[a-f0-9]{32}',name)
                cluster.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
