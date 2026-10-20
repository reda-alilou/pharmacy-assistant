"""Upgrade owned histories explicitly; startup never performs migrations."""
from alembic import command
from alembic.config import Config
from pharmacy_infrastructure.paths import ROOT


def migrate_schemas(database_url):
    for owner in ('core', 'language'):
        config = Config(str(ROOT / 'services' / owner / 'alembic.ini'))
        config.attributes['database_url'] = database_url
        command.upgrade(config, 'head')
    return {'migrated': ['core', 'language']}
