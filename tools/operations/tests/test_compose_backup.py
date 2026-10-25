"""Normal-volume backup safety and binary transport without Docker lifecycle."""
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pharmacy_ops.compose_backup import ComposeBackup, PROJECT, VOLUME
from pharmacy_ops.backup import main


class ComposeBackupTests(unittest.TestCase):
    def operation(self):
        operation = ComposeBackup.__new__(ComposeBackup)
        operation.database = 'pharmacy_assistant'
        operation.user = 'synthetic_admin'
        operation.container = 'a' * 64
        operation.command = ['docker', 'compose', '-p', PROJECT]
        return operation

    def snapshot(self):
        tables = [{'schema': 'core', 'table': 'facts'}, {'schema': 'language', 'table': 'quota'},
                  {'schema': 'platform', 'table': 'users'}, {'schema': 'platform', 'table': 'sessions'}]
        fingerprints = {t['schema']+'.'+t['table']: {'rows': '2', 'digest': 'synthetic'} for t in tables[:-1]}
        return tables, fingerprints

    def test_only_expected_normal_volume_and_container_identity_are_accepted(self):
        values = dict(POSTGRES_DB='pharmacy_assistant', POSTGRES_USER='synthetic_admin', POSTGRES_PASSWORD='private-fixture',
                      MIGRATION_DATABASE_URL='postgresql+psycopg://synthetic_admin:private-fixture@postgres:5432/pharmacy_assistant')
        inspected = {'Config': {'Labels': {'com.docker.compose.project': PROJECT, 'com.docker.compose.service': 'postgres'},
                                'Env': ['POSTGRES_PASSWORD=must-not-be-printed']}, 'State': {'Running': True},
                     'Mounts': [{'Destination': '/var/lib/postgresql/data', 'Type': 'volume', 'Name': VOLUME}]}
        for valid in (True, False):
            inspected['Mounts'][0]['Name'] = VOLUME if valid else 'unrelated_data'
            with self.subTest(valid=valid), patch('pharmacy_ops.compose_backup.configuration', return_value=values), \
                 patch.object(ComposeBackup, 'run', side_effect=[b'a'*64, json.dumps(inspected).encode()]), \
                 patch.object(ComposeBackup, 'sql', return_value={'database':'pharmacy_assistant','user':'synthetic_admin','major':17}):
                if valid:
                    self.assertEqual(ComposeBackup(Path('unused.env')).container, 'a'*64)
                else:
                    with self.assertRaisesRegex(ValueError, 'different PostgreSQL'):
                        ComposeBackup(Path('unused.env'))

    def test_live_application_writers_are_refused_without_stopping_them(self):
        operation = self.operation()
        with patch.object(operation, 'run', return_value=b'postgres\nplatform\n') as run:
            with self.assertRaisesRegex(ValueError, 'writers stopped'):
                operation.idle()
            self.assertEqual(run.call_args.args[0][-4:], ['ps','--services','--status','running'])

    def test_dump_is_binary_exclusive_and_verification_restores_only_new_database(self):
        operation = self.operation()
        binary = b'PGDMP\x00\xff\xfe\r\n\x80'
        statements, calls = [], []
        def pg(program, args=(), **kwargs):
            calls.append((program, args, kwargs.get('database')))
            if program == 'pg_dump':
                kwargs['stdout'].write(binary)
            elif program == 'pg_restore':
                self.assertEqual(kwargs['stdin'].read(), binary)
                self.assertRegex(kwargs['database'], r'^pharmacy_backup_verify_[a-f0-9]{32}$')
                self.assertNotEqual(kwargs['database'], operation.database)
        with tempfile.TemporaryDirectory(prefix='compose-backup-test-') as directory:
            path = Path(directory)/'normal.dump'
            with patch.object(operation, 'idle'), patch.object(operation, 'fingerprint', return_value=self.snapshot()), \
                 patch.object(operation, 'pg', side_effect=pg), patch.object(operation, 'execute', side_effect=lambda sql:statements.append(sql)), \
                 patch.object(operation, 'sql', return_value=0):
                self.assertFalse(operation.backup(path)['restore_verified'])
                self.assertEqual(path.read_bytes(), binary)
                with self.assertRaisesRegex(ValueError,'new backup path'):
                    operation.backup(path)
                result = operation.verify(path)
                self.assertTrue(result['restore_verified'])
                self.assertTrue(result['temporary_restore_database_removed'])
                self.assertEqual(len(statements),2)
                self.assertTrue(statements[0].startswith('CREATE DATABASE "pharmacy_backup_verify_'))
                self.assertTrue(statements[1].startswith('DROP DATABASE "pharmacy_backup_verify_'))
                self.assertTrue(any('--exclude-table-data=platform.sessions' in args for _,args,_ in calls))
                self.assertTrue(any('--exclude-table-data=core.conversation_messages' in args for _,args,_ in calls))
                self.assertTrue(any('--exclude-table-data=platform.import_uploads' in args for _,args,_ in calls))

    def test_failed_restore_still_removes_only_its_temporary_database(self):
        operation = self.operation()
        statements = []
        with tempfile.TemporaryDirectory(prefix='compose-backup-test-') as directory:
            path=Path(directory)/'normal.dump'
            def dump(program,args=(),**kwargs):
                if program=='pg_dump':kwargs['stdout'].write(b'PGDMP-binary')
                else:raise ValueError('Synthetic restore failure')
            with patch.object(operation,'idle'), patch.object(operation,'fingerprint',return_value=self.snapshot()), \
                 patch.object(operation,'pg',side_effect=dump),patch.object(operation,'execute',side_effect=lambda sql:statements.append(sql)):
                operation.backup(path)
                with self.assertRaisesRegex(ValueError,'Synthetic restore failure'):
                    operation.verify(path)
                self.assertEqual(len(statements),2)
                self.assertIn('DROP DATABASE "pharmacy_backup_verify_',statements[-1])
                self.assertNotIn('DROP DATABASE "pharmacy_assistant"', statements[-1])

    def test_changed_source_or_tampered_dump_is_rejected_before_restore(self):
        operation=self.operation()
        with tempfile.TemporaryDirectory(prefix='compose-backup-test-') as directory:
            path=Path(directory)/'normal.dump'
            with patch.object(operation,'idle'),patch.object(operation,'fingerprint',return_value=self.snapshot()), \
                 patch.object(operation,'pg',side_effect=lambda _,args=(),**kwargs:kwargs['stdout'].write(b'original')):
                operation.backup(path)
            path.write_bytes(b'changed')
            with patch.object(operation,'idle'),patch.object(operation,'execute') as execute:
                with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                    operation.verify(path)
                execute.assert_not_called()

    def test_exec_uses_fixed_shell_and_no_host_password_argument_or_lifecycle(self):
        operation=self.operation()
        with patch.object(operation,'run',return_value=b'{}') as run:
            operation.pg('psql',['-X'],input=b'SELECT 1;')
            command=run.call_args.args[0]
            self.assertEqual(command[:4],['docker','exec','-i','a'*64])
            self.assertIn('$POSTGRES_PASSWORD', command[6])
            self.assertNotIn('private-fixture',' '.join(command))
            self.assertNotIn('up',command)
            self.assertNotIn('down',command)
        with patch('pharmacy_ops.compose_backup.subprocess.run',return_value=subprocess.CompletedProcess([],1,b'',b'private credentials')):
            with self.assertRaisesRegex(ValueError,'diagnostics withheld') as caught:
                operation.run(['docker','inspect'])
            self.assertNotIn('private credentials',str(caught.exception))

    def test_help_reads_no_credentials_and_runs_no_container_commands(self):
        with patch('sys.argv',['pharmacy-backup','--help']),patch('pharmacy_ops.backup.configuration',side_effect=AssertionError('No settings on help')), \
             patch('subprocess.run',side_effect=AssertionError('No process on help')),patch('sys.stdout',new_callable=io.StringIO):
            with self.assertRaises(SystemExit) as caught:
                main()
            self.assertEqual(caught.exception.code,0)
