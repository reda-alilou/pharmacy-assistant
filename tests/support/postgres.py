"""Disposable databases inside the user-controlled isolated verification cluster."""
import os
from pathlib import Path
import unittest
import uuid

from sqlalchemy import text
from sqlalchemy.engine import make_url
from pharmacy_infrastructure.database import create_database_engine
from pharmacy_infrastructure.paths import ROOT
from pharmacy_ops.database import configuration, grant
from pharmacy_ops.migrations import migrate_schemas
from pharmacy_core.storage.postgres.catalogue import import_catalogue, load_catalogue


class TemporaryPostgresCase(unittest.TestCase):
    load_catalogue = True

    @classmethod
    def setUpClass(cls):
        project = os.environ.get('PHARMACY_ISOLATED_TEST_PROJECT', '')
        path = os.environ.get('PHARMACY_PG_TEST_ENV')
        if not path or not project.startswith('pharmacy-checkpoint4-test-') or len(project) != 58:
            raise unittest.SkipTest('Run PostgreSQL checks through pharmacy-compose-verify --run-isolated')
        expected = (ROOT / '.runtime' / (project+'-host.env')).resolve()
        if Path(path).resolve() != expected:
            raise ValueError('PostgreSQL tests require the isolated verification environment')
        cls.values = configuration(expected)
        if make_url(cls.values['MIGRATION_DATABASE_URL']).username != 'verification_admin':
            raise ValueError('Refusing to use an application database administrator for tests')
        cls.name = 'pharmacy_r5_test_' + uuid.uuid4().hex
        cls.admin = create_database_engine(make_url(cls.values['MIGRATION_DATABASE_URL']).set(database='postgres').render_as_string(hide_password=False))
        cls.created = False
        cls.addClassCleanup(cls.drop_database)
        with cls.admin.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
            db.execute(text(f'CREATE DATABASE "{cls.name}"'))
        cls.created = True
        cls.values = {key:make_url(value).set(database=cls.name).render_as_string(hide_password=False)
                      if key.endswith('DATABASE_URL') else value for key,value in cls.values.items()}
        migrate_schemas(cls.values['MIGRATION_DATABASE_URL'])
        migrate_schemas(cls.values['MIGRATION_DATABASE_URL'])
        grant(cls.values)
        cls.engine = create_database_engine(cls.values['MIGRATION_DATABASE_URL'])
        cls.core = create_database_engine(cls.values['CORE_DATABASE_URL'])
        cls.language = create_database_engine(cls.values['LANGUAGE_DATABASE_URL'])
        if cls.load_catalogue:
            cls.medications = ROOT / 'data/imports/ammps_medications_enriched.jsonl'
            cls.pharmacies = ROOT / 'data/imports/pharmacies_rabat.jsonl'
            cls.counts = import_catalogue(cls.engine,cls.medications,cls.pharmacies)
            cls.catalog,cls.directory = load_catalogue(cls.core)

    @classmethod
    def drop_database(cls):
        for name in ('engine','core','language'):
            engine = getattr(cls,name,None)
            if engine is not None:
                engine.dispose()
        try:
            if cls.created:
                assert cls.name.startswith('pharmacy_r5_test_') and cls.name.replace('_','').isalnum()
                with cls.admin.connect().execution_options(isolation_level='AUTOCOMMIT') as db:
                    db.execute(text(f'DROP DATABASE "{cls.name}" WITH (FORCE)'))
        finally:
            cls.admin.dispose()
