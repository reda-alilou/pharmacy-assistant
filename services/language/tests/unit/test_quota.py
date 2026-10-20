from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from pharmacy_language.quota.control import daily_reset_delay
from tests.support.ledger import MemoryLedger

class QuotaTests(unittest.TestCase):

    def test_pacific_midnight_handles_summer_winter_and_dst(self):
        for stamp, expected in (('2026-07-10T06:30:00+00:00', 1800), ('2026-12-10T07:30:00+00:00', 1800), ('2026-03-08T08:00:00+00:00', 23 * 3600), ('2026-11-01T07:00:00+00:00', 25 * 3600)):
            self.assertEqual(daily_reset_delay(datetime.fromisoformat(stamp).timestamp()), expected)
from unittest.mock import AsyncMock, patch
import httpx
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_language.providers.gemini import GeminiInterpreter, status_error
from pharmacy_contracts.interpretation import InferenceError, InterpretationRequest
from pharmacy_language.quota.control import AttemptControl
from tests.support.ledger import MemoryLedger
from tests.support.gemini import TEXT

class QuotaAdapterTests(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.store = MemoryLedger()

    async def test_retries_cannot_exceed_one_wire_request_budget(self):
        self.store.new_budget('budget', 'run', 1)
        control = AttemptControl(self.store, 'shared', 0, budget_id='budget')
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(503)
        interpreter = GeminiInterpreter(Settings(gemini_api_key='offline'), httpx.AsyncClient(transport=httpx.MockTransport(handler)), control=control)
        try:
            with patch('pharmacy_language.providers.gemini.asyncio.sleep', new_callable=AsyncMock):
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.detail.code, 'evaluation_budget_exhausted')
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.budget_counts('budget', 'run')['attempts_reserved'], 1)

    async def test_waiting_evaluator_respects_spacing_without_real_sleep(self):
        now = [1000.0]
        self.store.clock = lambda: now[0]
        self.store.reserve('shared', 30)

        async def advance(seconds):
            now[0] += seconds
        control = AttemptControl(self.store, 'shared', 30, wait=True, sleep=advance)
        await control.before_attempt()
        self.assertEqual(now[0], 1030)
        self.assertEqual(self.store.status('shared')['local_attempts_reserved'], 2)

    async def test_known_daily_429_stops_without_retry_and_blocks_a_new_interpreter(self):
        calls = []

        def handler(request):
            calls.append(request)
            return httpx.Response(429, json={'error': {'message': 'PRIVATE', 'details': [{'@type': 'type.googleapis.com/google.rpc.QuotaFailure', 'violations': [{'quotaId': 'GenerateRequestsPerDayPerProjectPerModel-FreeTier'}]}]}})
        for _ in range(2):
            control = AttemptControl(self.store, 'shared', 0)
            interpreter = GeminiInterpreter(Settings(gemini_api_key='offline'), httpx.AsyncClient(transport=httpx.MockTransport(handler)), control=control)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, 'provider_daily_quota_exhausted')
            self.assertFalse(caught.exception.detail.retryable)
            self.assertGreater(caught.exception.detail.retry_after_seconds, 0)
            self.assertNotIn('PRIVATE', str(caught.exception))
        self.assertEqual(len(calls), 1)

    async def test_unspecified_429_gets_a_shared_default_cooldown(self):
        control = AttemptControl(self.store, 'shared', 0)
        error = control.failed(status_error(httpx.Response(429)))
        self.assertEqual(error.detail.retry_after_seconds, 60)
        with self.assertRaises(InferenceError) as caught:
            await control.before_attempt()
        self.assertEqual(caught.exception.detail.code, 'provider_rate_limited')
