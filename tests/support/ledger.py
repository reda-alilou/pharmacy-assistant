"""Deterministic offline ledger fixtures; actual durability is checked on PostgreSQL."""
from contextlib import contextmanager
import threading
import time
import unittest
from unittest.mock import patch

from pharmacy_contracts.interpretation import InferenceError
from pharmacy_evaluation import ledger
from pharmacy_language.quota.control import AttemptControl


class MemoryLedger:
    def __init__(self, *args, clock=time.time):
        self.clock, self.rows, self.budgets, self.lock = clock, {}, {}, threading.RLock()

    def new_budget(self, identifier, evaluation_id, maximum):
        if maximum < 0:
            raise ValueError('Request budget must be non-negative')
        with self.lock:
            if identifier in self.budgets:
                raise ValueError('Duplicate fixture budget')
            self.budgets[identifier] = [evaluation_id, maximum, 0]

    def budget_counts(self, identifier, evaluation_id):
        with self.lock:
            row = self.budgets.get(identifier)
            if row is None or row[0] != evaluation_id:
                raise InferenceError('quota_state_unavailable', 'Fixture ledger missing', 503)
            return dict(max_requests=row[1], attempts_reserved=row[2],
                        total_attempts_reserved=sum(r[2] for r in self.budgets.values() if r[0] == evaluation_id))

    def reserve(self, scope, interval, budget_id=None):
        with self.lock:
            budget = self.budgets.get(budget_id) if budget_id is not None else None
            if budget_id is not None and budget is None:
                raise InferenceError('quota_state_unavailable', 'Fixture budget missing', 503)
            if budget is not None and budget[2] >= budget[1]:
                raise InferenceError('evaluation_budget_exhausted', 'Fixture attempt budget reached', 429)
            now = self.clock()
            row = self.rows.setdefault(scope, [0, 0, None, 0])
            if row[1] > now:
                raise InferenceError(row[2] or 'provider_rate_limited', 'Fixture cooldown', 429,
                                     row[2] != 'provider_daily_quota_exhausted', row[1]-now)
            if interval and row[0] > now:
                raise InferenceError('local_rate_limited', 'Fixture spacing', 429, True, row[0]-now)
            row[0], row[3] = now+interval, row[3]+1
            if budget is not None:
                budget[2] += 1

    def cooldown(self, scope, seconds, code):
        with self.lock:
            row = self.rows.setdefault(scope, [0, 0, None, 0])
            deadline = self.clock()+seconds
            if deadline >= row[1]:
                row[1], row[2] = deadline, code

    def status(self, scope):
        with self.lock:
            row, now = self.rows.get(scope, [0, 0, None, 0]), self.clock()
            return dict(scope=scope, local_attempts_reserved=row[3],
                        spacing_remaining_seconds=round(max(0,row[0]-now),2),
                        cooldown_remaining_seconds=round(max(0,row[1]-now),2),
                        cooldown_code=row[2] if row[1]>now else None)


def fixture_store(settings):
    return ledger.create_control(settings).store


def clear_fixture_ledger(settings):
    store = fixture_store(settings)
    store.rows.clear()
    store.budgets.clear()


class OfflineLedgerMixin:
    def run(self, result=None):
        stores = {}
        def factory(settings, **kwargs):
            store = stores.setdefault(settings.inference_quota_scope, MemoryLedger())
            return AttemptControl(store,
                f'{settings.inference_quota_scope}:{settings.inference_provider}:{settings.inference_model}',
                settings.inference_min_interval_seconds, **kwargs)
        with patch('pharmacy_evaluation.ledger.create_control', side_effect=factory):
            return super().run(result)


class OfflineEvaluationCase(OfflineLedgerMixin, unittest.IsolatedAsyncioTestCase):
    pass


class OfflineEvaluationSyncCase(OfflineLedgerMixin, unittest.TestCase):
    pass
