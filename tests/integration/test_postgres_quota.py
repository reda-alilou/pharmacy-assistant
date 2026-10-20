"""Real PostgreSQL counterparts of the former SQLite runtime-ledger scenarios."""
from concurrent.futures import ThreadPoolExecutor
import os
import subprocess
import sys
import unittest
import uuid

from pharmacy_contracts.interpretation import InferenceError
from pharmacy_infrastructure.database import create_database_engine
from pharmacy_language.storage.postgres.quota import PostgresQuotaStore
from tests.support.postgres import TemporaryPostgresCase


@unittest.skipUnless(os.environ.get('PHARMACY_PG_TEST_ENV') and os.environ.get('PHARMACY_ISOLATED_TEST_PROJECT'),
                     'Run through the explicit isolated verification stack')
class PostgresQuotaTests(TemporaryPostgresCase):
    load_catalogue = False

    def test_concurrent_connections_allow_only_one_reservation(self):
        store, scope = PostgresQuotaStore(self.language, clock=lambda:1000), uuid.uuid4().hex
        def reserve(_):
            try:
                store.reserve(scope,30)
                return 'reserved'
            except InferenceError as error:
                return error.detail.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes=list(pool.map(reserve,range(12)))
        self.assertEqual(outcomes.count('reserved'),1)
        self.assertEqual(outcomes.count('local_rate_limited'),11)
        self.assertEqual(store.status(scope)['local_attempts_reserved'],1)

    def test_another_python_process_uses_the_same_ledger(self):
        scope=uuid.uuid4().hex
        script='''
import os
from pharmacy_contracts.interpretation import InferenceError
from pharmacy_infrastructure.database import create_database_engine
from pharmacy_language.storage.postgres.quota import PostgresQuotaStore
engine=create_database_engine(os.environ['PG_QUOTA_TEST_URL'])
try:
    try:
        PostgresQuotaStore(engine,clock=lambda:1000).reserve(os.environ['PG_QUOTA_TEST_SCOPE'],30)
        print('reserved')
    except InferenceError as error:
        print(error.detail.code)
finally:
    engine.dispose()
'''
        env=dict(os.environ,PG_QUOTA_TEST_URL=self.values['LANGUAGE_DATABASE_URL'],PG_QUOTA_TEST_SCOPE=scope)
        outcomes=[]
        for _ in range(2):
            result=subprocess.run([sys.executable,'-c',script],env=env,text=True,capture_output=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stderr)
            outcomes.append(result.stdout.strip())
        self.assertEqual(outcomes,['reserved','local_rate_limited'])

    def test_cooldown_persists_and_cannot_be_shortened_by_another_caller(self):
        scope=uuid.uuid4().hex
        store=PostgresQuotaStore(self.language,clock=lambda:1000)
        store.cooldown(scope,120,'provider_rate_limited')
        engine=create_database_engine(self.values['LANGUAGE_DATABASE_URL'])
        try:
            other=PostgresQuotaStore(engine,clock=lambda:1000)
            other.cooldown(scope,30,'provider_rate_limited')
            self.assertEqual(other.status(scope)['cooldown_remaining_seconds'],120)
            with self.assertRaises(InferenceError) as caught:
                other.reserve(scope,0)
            self.assertEqual(caught.exception.detail.code,'provider_rate_limited')
            self.assertEqual(other.status(scope)['local_attempts_reserved'],0)
        finally:
            engine.dispose()

    def test_budget_counts_reservations_not_rejected_local_requests(self):
        store=PostgresQuotaStore(self.language,clock=lambda:1000)
        scope,budget,evaluation=(uuid.uuid4().hex for _ in range(3))
        store.new_budget(budget,evaluation,2)
        store.reserve(scope,30,budget)
        with self.assertRaises(InferenceError) as caught:
            store.reserve(scope,30,budget)
        self.assertEqual(caught.exception.detail.code,'local_rate_limited')
        self.assertEqual(store.budget_counts(budget,evaluation)['attempts_reserved'],1)
        store.reserve(scope,0,budget)
        with self.assertRaises(InferenceError) as caught:
            store.reserve(uuid.uuid4().hex,0,budget)
        self.assertEqual(caught.exception.detail.code,'evaluation_budget_exhausted')
        self.assertEqual(store.budget_counts(budget,evaluation)['attempts_reserved'],2)
        self.assertIsInstance(store.budget_counts(budget,evaluation)['total_attempts_reserved'],int)

    def test_unavailable_ledger_fails_closed_without_exposing_credentials(self):
        engine=create_database_engine('postgresql+psycopg://fixture:private-ledger-password@127.0.0.1:1/fixture')
        try:
            with self.assertRaises(InferenceError) as caught:
                PostgresQuotaStore(engine).reserve(uuid.uuid4().hex,0)
            self.assertEqual(caught.exception.detail.code,'quota_state_unavailable')
            self.assertNotIn('private-ledger-password',str(caught.exception))
        finally:
            engine.dispose()
