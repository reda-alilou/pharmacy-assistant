from tests.support.ledger import OfflineEvaluationCase, OfflineEvaluationSyncCase, clear_fixture_ledger
import asyncio
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_evaluation.runners.interpretation import CASES, run_smoke
from pharmacy_evaluation.reporting.state import report_lock
from pharmacy_contracts.interpretation import InferenceError, InterpretationResponse
CASES_BY_TEXT = {case['text']: case for case in json.loads(CASES.read_text(encoding='utf-8'))}

def annotated_response(text, settings):
    case = CASES_BY_TEXT[text]
    group = case['group']
    return InterpretationResponse.model_validate({'interpretation': {'language': group, 'reply_language': 'fr' if group == 'mixed' else group, 'reply_script': 'arabic' if group == 'ar' else 'latin', 'intents': case['expected_intents'], 'entities': {'medications': [{k: v[0] for k, v in med.items()} for med in case['expected_medications']], **{k: v[0] for k, v in case['expected_context'].items()}}}, 'metadata': {'provider': settings.inference_provider, 'requested_model': settings.inference_model, 'model': 'offline-fixture', 'prompt_version': 'test', 'latency_ms': 1, 'attempts': 1, 'completion_id': None, 'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}})

class ResumeTests(OfflineEvaluationCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'run.json'
        self.settings = Settings(gemini_api_key='offline-key', inference_min_interval_seconds=0)
        self.calls, self.closed = ([], [])
        self.failure = None

        def factory(settings, *, control):
            outer = self

            class OfflineInterpreter:

                async def interpret(self, request):
                    await control.before_attempt()
                    outer.calls.append(request.text)
                    if outer.failure:
                        failure = outer.failure
                        outer.failure = None
                        if isinstance(failure, InferenceError):
                            raise control.failed(failure)
                        raise failure
                    return annotated_response(request.text, settings)

                async def close(self):
                    outer.closed.append(True)
            return OfflineInterpreter()
        self.factory = self.enterContext(patch('pharmacy_evaluation.runners.interpretation.create_interpreter', side_effect=factory))
        self.enterContext(redirect_stdout(io.StringIO()))

    async def run_check(self, **kwargs):
        return await run_smoke(self.settings, self.path, 0, **kwargs)

    async def test_zero_budget_sends_nothing_and_is_resumable(self):
        report = await self.run_check(max_requests=0)
        self.assertEqual(report['status'], 'paused_budget')
        self.assertEqual(self.calls, [])
        self.assertEqual(report['invocations'][-1]['attempts_reserved'], 0)
        resumed = await self.run_check(max_requests=1, resume=True)
        self.assertEqual(len(resumed['results']), 1)
        self.assertEqual(len(self.calls), 1)

    async def test_three_invocations_complete_without_repeating_saved_cases(self):
        for index in range(3):
            report = await self.run_check(max_requests=4, resume=index > 0)
            self.assertEqual(len(report['results']), (index + 1) * 4)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(len(self.calls), 12)
        self.assertEqual(len(set(self.calls)), 12)
        self.assertEqual(report['invocations'][-1]['total_attempts_reserved'], 12)
        self.factory.reset_mock()
        finished = await self.run_check(max_requests=4, resume=True)
        self.factory.assert_not_called()
        self.assertTrue(finished['summary']['passed'])

    async def test_existing_evidence_is_never_overwritten_by_accident(self):
        await self.run_check(max_requests=1)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            await self.run_check(max_requests=1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(len(self.calls), 1)

    async def test_changed_model_prompt_or_labels_reject_resume_before_any_call(self):
        await self.run_check(max_requests=1)
        with patch('pharmacy_evaluation.reporting.state.SYSTEM_PROMPT', 'Changed extraction instructions'):
            with self.assertRaisesRegex(ValueError, 'Cannot resume'):
                await self.run_check(max_requests=1, resume=True)
        self.settings = self.settings.model_copy(update={'gemini_model': 'gemini-other-model'})
        with self.assertRaisesRegex(ValueError, 'Cannot resume'):
            await self.run_check(max_requests=1, resume=True)
        self.assertEqual(len(self.calls), 1)

    async def test_provider_failure_stays_pending_and_resume_retries_only_that_case(self):
        self.failure = InferenceError('provider_unavailable', 'Offline provider unavailable', 503, True)
        report = await self.run_check(max_requests=1)
        self.assertEqual(report['status'], 'stopped_provider_error')
        self.assertFalse(report['results'])
        self.assertEqual(report['invocations'][-1]['attempts_reserved'], 1)
        resumed = await self.run_check(max_requests=1, resume=True)
        self.assertEqual(len(resumed['results']), 1)
        self.assertEqual(resumed['invocations'][-1]['total_attempts_reserved'], 2)
        self.assertEqual(self.calls[0], self.calls[1])

    async def test_quota_resume_does_not_probe_during_shared_cooldown(self):
        self.failure = InferenceError('provider_rate_limited', 'Offline quota exhausted', 429, True, 120)
        first = await self.run_check(max_requests=3)
        self.assertEqual(first['status'], 'paused_quota')
        resumed = await self.run_check(max_requests=3, resume=True)
        self.assertEqual(resumed['status'], 'paused_quota')
        self.assertEqual(resumed['invocations'][-1]['attempts_reserved'], 0)
        self.assertEqual(len(self.calls), 1)

    async def test_interruption_preserves_saved_cases_and_counts_uncertain_attempts(self):
        await self.run_check(max_requests=1)
        self.failure = asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):
            await self.run_check(max_requests=2, resume=True)
        interrupted = json.loads(self.path.read_text(encoding='utf-8'))
        self.assertEqual(interrupted['status'], 'interrupted')
        self.assertEqual(len(interrupted['results']), 1)
        self.assertEqual(interrupted['invocations'][-1]['attempts_reserved'], 1)
        resumed = await self.run_check(max_requests=1, resume=True)
        self.assertEqual(len(resumed['results']), 2)
        self.assertEqual(resumed['invocations'][-1]['total_attempts_reserved'], 3)
        self.assertEqual(len(self.closed), 3)

    async def test_report_lock_blocks_concurrent_evaluators_and_releases_cleanly(self):
        with report_lock(self.path):
            with self.assertRaisesRegex(ValueError, 'already in use'):
                await self.run_check(max_requests=1)
        report = await self.run_check(max_requests=1)
        self.assertEqual(len(report['results']), 1)

    async def test_missing_report_key_and_invalid_budget_do_not_consume_requests(self):
        with self.assertRaisesRegex(ValueError, 'no report'):
            await self.run_check(max_requests=1, resume=True)
        with self.assertRaises(ValueError):
            await self.run_check(max_requests=-1)
        self.settings = self.settings.model_copy(update={'gemini_api_key': None})
        report = await self.run_check(max_requests=3)
        self.assertEqual(report['status'], 'not_run_missing_key')
        self.factory.assert_not_called()
        self.assertFalse(self.calls)

    async def test_duplicate_saved_results_are_rejected(self):
        report = await self.run_check(max_requests=1)
        report['results'].append(report['results'][0])
        self.path.write_text(json.dumps(report), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            await self.run_check(max_requests=1, resume=True)
        self.assertEqual(len(self.calls), 1)

    async def test_missing_request_ledger_rejects_resume_without_resetting_counts(self):
        await self.run_check(max_requests=1)
        clear_fixture_ledger(self.settings)
        with self.assertRaises(InferenceError) as caught:
            await self.run_check(max_requests=1, resume=True)
        self.assertEqual(caught.exception.detail.code, 'quota_state_unavailable')
        self.assertEqual(len(self.calls), 1)
