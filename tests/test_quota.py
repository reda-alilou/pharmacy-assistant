"""No live inference: shared gates, wire-attempt budgets and restart behaviour."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from pydantic import ValidationError

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import Settings
from pharmacy_assistant.gemini_nlu import GeminiInterpreter, status_error
from pharmacy_assistant.inference import create_interpreter
from pharmacy_assistant.nlu_models import InferenceError, InterpretationRequest
from pharmacy_assistant.quota import AttemptControl, QuotaStore, daily_reset_delay
from test_gemini import TEXT, completion


class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "quota.sqlite3"
        self.now = 1000.0
        self.store = QuotaStore(self.path, clock=lambda: self.now)

    def test_concurrent_connections_allow_only_one_reservation(self):
        def reserve(_):
            try:
                QuotaStore(self.path, clock=lambda: 1000).reserve("shared", 30)
                return "sent"
            except InferenceError as error:
                return error.detail.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(12)))
        self.assertEqual(results.count("sent"), 1)
        self.assertEqual(results.count("local_rate_limited"), 11)
        self.assertEqual(self.store.status("shared")["local_attempts_reserved"], 1)

    def test_another_python_process_uses_the_same_ledger(self):
        self.store.reserve("shared", 30)
        script = """from pathlib import Path
import sys
from pharmacy_assistant.quota import QuotaStore
from pharmacy_assistant.nlu_models import InferenceError
try:
 QuotaStore(Path(sys.argv[1]),clock=lambda:1000).reserve('shared',30)
 print('unexpected send')
except InferenceError as e:print(e.detail.code)
"""
        result = subprocess.run([sys.executable, "-c", script, str(self.path)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "local_rate_limited")

    def test_cooldown_persists_and_cannot_be_shortened_by_another_caller(self):
        self.store.cooldown("shared", 120, "provider_daily_quota_exhausted")
        another = QuotaStore(self.path, clock=lambda: self.now)
        another.cooldown("shared", 2, "provider_rate_limited")
        with self.assertRaises(InferenceError) as caught:
            another.reserve("shared", 0)
        self.assertEqual(caught.exception.detail.code, "provider_daily_quota_exhausted")
        self.assertFalse(caught.exception.detail.retryable)
        self.assertEqual(caught.exception.detail.retry_after_seconds, 120)
        self.now += 121
        another.reserve("shared", 0)
        self.assertEqual(another.status("shared")["local_attempts_reserved"], 1)

    def test_budget_counts_reservations_not_rejected_local_requests(self):
        self.store.new_budget("one", "evaluation", 2)
        self.store.reserve("shared", 30, "one")
        with self.assertRaises(InferenceError):
            self.store.reserve("shared", 30, "one")
        self.assertEqual(self.store.budget_counts("one", "evaluation")["attempts_reserved"], 1)
        self.now += 30
        self.store.reserve("shared", 30, "one")
        with self.assertRaises(InferenceError) as caught:
            self.store.reserve("shared", 0, "one")
        self.assertEqual(caught.exception.detail.code, "evaluation_budget_exhausted")
        self.store.new_budget("two", "evaluation", 1)
        self.now += 30
        self.store.reserve("shared", 0, "two")
        self.assertEqual(self.store.budget_counts("two", "evaluation")["total_attempts_reserved"], 3)

    def test_unavailable_ledger_fails_closed_and_settings_are_validated(self):
        self.path.write_text("not a database", encoding="utf-8")
        with self.assertRaises(InferenceError) as caught:
            self.store.reserve("shared", 0)
        self.assertEqual(caught.exception.detail.code, "quota_state_unavailable")
        for kwargs in ({"inference_min_interval_seconds": -1}, {"inference_min_interval_seconds": float("nan")},
                       {"inference_quota_scope": "key?secret"}):
            with self.assertRaises(ValidationError):
                Settings(**kwargs)

    def test_pacific_midnight_handles_summer_winter_and_dst(self):
        for stamp, expected in (("2026-07-10T06:30:00+00:00", 1800),
                                ("2026-12-10T07:30:00+00:00", 1800),
                                ("2026-03-08T08:00:00+00:00", 23 * 3600),
                                ("2026-11-01T07:00:00+00:00", 25 * 3600)):
            self.assertEqual(daily_reset_delay(datetime.fromisoformat(stamp).timestamp()), expected)


class QuotaAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = QuotaStore(Path(self.temp.name) / "quota.sqlite3")

    async def test_retries_cannot_exceed_one_wire_request_budget(self):
        self.store.new_budget("budget", "run", 1)
        control = AttemptControl(self.store, "shared", 0, budget_id="budget")
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(503)
        interpreter = GeminiInterpreter(Settings(gemini_api_key="offline"),
            httpx.AsyncClient(transport=httpx.MockTransport(handler)), control=control)
        try:
            with patch("pharmacy_assistant.gemini_nlu.asyncio.sleep", new_callable=AsyncMock):
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
        finally:
            await interpreter.close()
        self.assertEqual(caught.exception.detail.code, "evaluation_budget_exhausted")
        self.assertEqual(len(calls), 1)
        self.assertEqual(self.store.budget_counts("budget", "run")["attempts_reserved"], 1)

    async def test_waiting_evaluator_respects_spacing_without_real_sleep(self):
        now = [1000.0]
        self.store.clock = lambda: now[0]
        self.store.reserve("shared", 30)
        async def advance(seconds):
            now[0] += seconds
        control = AttemptControl(self.store, "shared", 30, wait=True, sleep=advance)
        await control.before_attempt()
        self.assertEqual(now[0], 1030)
        self.assertEqual(self.store.status("shared")["local_attempts_reserved"], 2)

    async def test_known_daily_429_stops_without_retry_and_blocks_a_new_interpreter(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(429, json={"error": {"message": "PRIVATE", "details": [{
                "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
            }]}})
        for _ in range(2):
            control = AttemptControl(QuotaStore(self.store.path), "shared", 0)
            interpreter = GeminiInterpreter(Settings(gemini_api_key="offline"),
                httpx.AsyncClient(transport=httpx.MockTransport(handler)), control=control)
            try:
                with self.assertRaises(InferenceError) as caught:
                    await interpreter.interpret(InterpretationRequest(text=TEXT))
            finally:
                await interpreter.close()
            self.assertEqual(caught.exception.detail.code, "provider_daily_quota_exhausted")
            self.assertFalse(caught.exception.detail.retryable)
            self.assertGreater(caught.exception.detail.retry_after_seconds, 0)
            self.assertNotIn("PRIVATE", str(caught.exception))
        self.assertEqual(len(calls), 1)

    async def test_unspecified_429_gets_a_shared_default_cooldown(self):
        control = AttemptControl(self.store, "shared", 0)
        error = control.failed(status_error(httpx.Response(429)))
        self.assertEqual(error.detail.retry_after_seconds, 60)
        with self.assertRaises(InferenceError) as caught:
            await control.before_attempt()
        self.assertEqual(caught.exception.detail.code, "provider_rate_limited")


class QuotaApiTests(unittest.TestCase):
    def test_factory_api_spacing_preserves_lookup_and_retry_after_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(gemini_api_key="offline-key", inference_min_interval_seconds=30,
                                inference_quota_db=Path(directory) / "quota.db")
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=completion())
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch("pharmacy_assistant.gemini_nlu.httpx.AsyncClient", return_value=http_client), \
                 TestClient(create_app(settings=settings)) as client:
                self.assertEqual(client.post("/interpret", json={"text": TEXT}).status_code, 200)
                result = client.post("/interpret", json={"text": TEXT})
                self.assertEqual(result.status_code, 429)
                self.assertEqual(result.json()["detail"]["code"], "local_rate_limited")
                self.assertGreater(int(result.headers["retry-after"]), 0)
                self.assertNotIn("offline-key", result.text)
                self.assertEqual(client.get("/medications/9079").status_code, 200)
            self.assertEqual(len(calls), 1)

    def test_default_allows_back_to_back_requests_and_ignores_old_spacing(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(gemini_api_key="offline-key", inference_quota_db=Path(directory) / "quota.db")
            self.assertEqual(settings.inference_min_interval_seconds, 0)
            control = AttemptControl.from_settings(settings)
            control.store.reserve(control.scope, 30)  # Old application policy.
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(200, json=completion())
            http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
            with patch("pharmacy_assistant.gemini_nlu.httpx.AsyncClient", return_value=http_client), \
                 TestClient(create_app(settings=settings)) as client:
                for _ in range(2):
                    result = client.post("/interpret", json={"text": TEXT})
                    self.assertEqual(result.status_code, 200, result.text)
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
