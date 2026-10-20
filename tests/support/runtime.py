"""Explicit offline API dependencies; never imported or selected by service startup."""
import threading
import time
from pharmacy_contracts.interpretation import InferenceError
from pharmacy_core.api import app as core_api
from pharmacy_core.api.resources import CoreResources
from pharmacy_core.config import CoreSettings
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from pharmacy_language.api import app as language_api
from pharmacy_language.config import LanguageSettings
from pharmacy_language.quota.control import AttemptControl
CORE_URL = 'postgresql+psycopg://fixture_core:offline@127.0.0.1:1/fixture'
LANGUAGE_URL = 'postgresql+psycopg://fixture_language:offline@127.0.0.1:1/fixture'

def core_settings(settings=None, **overrides):
    values = {name: getattr(settings, name) for name in CoreSettings.model_fields if name not in {'storage_backend', 'core_database_url'} and hasattr(settings, name)}
    return CoreSettings(core_database_url=CORE_URL, **values | overrides)

def language_settings(settings=None, **overrides):
    values = {name: getattr(settings, name) for name in LanguageSettings.model_fields if name not in {'storage_backend', 'language_database_url'} and hasattr(settings, name)}
    return LanguageSettings(language_database_url=LANGUAGE_URL, **values | overrides)

class MemoryQuotaStore:
    """A per-test quota fixture, never a service backend or durable ledger."""

    def __init__(self):
        self.rows, self.lock = ({}, threading.Lock())

    def reserve(self, scope, interval, budget_id=None):
        if budget_id is not None:
            raise AssertionError('Budgeted tooling must inject its explicit test ledger')
        with self.lock:
            row = self.rows.setdefault(scope, dict(next_at=0, blocked_until=0, code=None, attempts=0))
            now = time.time()
            if row['blocked_until'] > now:
                raise InferenceError(row['code'], 'Fixture cooldown', 429, True, row['blocked_until'] - now)
            if interval and row['next_at'] > now:
                raise InferenceError('local_rate_limited', 'Fixture spacing', 429, True, row['next_at'] - now)
            row.update(next_at=now + interval, attempts=row['attempts'] + 1)

    def cooldown(self, scope, seconds, code):
        with self.lock:
            row = self.rows.setdefault(scope, dict(next_at=0, blocked_until=0, code=None, attempts=0))
            deadline = time.time() + seconds
            if deadline >= row['blocked_until']:
                row.update(blocked_until=deadline, code=code)

    def status(self, scope):
        with self.lock:
            row = self.rows.get(scope, dict(next_at=0, blocked_until=0, code=None, attempts=0))
            now = time.time()
            return dict(scope=scope, local_attempts_reserved=row['attempts'], spacing_remaining_seconds=max(0, row['next_at'] - now), cooldown_remaining_seconds=max(0, row['blocked_until'] - now), cooldown_code=row['code'] if row['blocked_until'] > now else None)

def core_app(settings=None, *, interpreter=None):
    config = core_settings(settings)
    interpreter = interpreter if interpreter is not None else core_api.create_interpreter(config)
    catalog, directory = (MedicationCatalog.from_path(), PharmacyDirectory.from_path())
    resources = CoreResources(catalog, directory, interpreter, ChatService(catalog, interpreter, directory))
    return core_api.create_app(settings=config, resources=resources)

def language_app(settings=None, *, interpreter=None, store=None):
    config = language_settings(settings)
    if interpreter is None:
        store = store if store is not None else MemoryQuotaStore()
        control = AttemptControl(store, f'{config.inference_quota_scope}:{config.inference_provider}:{config.inference_model}', config.inference_min_interval_seconds)
        interpreter = language_api.create_interpreter(config, control=control)
    return language_api.create_app(config, interpreter=interpreter)
