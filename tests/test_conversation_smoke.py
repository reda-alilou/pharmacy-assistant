"""Live-check orchestration is tested against a mocked provider and real budget."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from pharmacy_assistant.config import Settings
from pharmacy_assistant.evaluate_conversation_smoke import run_smoke
from pharmacy_assistant.nlu_models import InferenceError
from test_chat import mention, response


class ConversationSmokeTests(unittest.IsolatedAsyncioTestCase):
    async def check(self, root, maximum, *, failure=False):
        calls = []
        def factory(settings, *, control):
            interpreter = AsyncMock()
            async def interpret(request):
                await control.before_attempt()
                calls.append(request.text)
                if failure:
                    raise InferenceError('provider_rate_limited', 'fixture', 429, True, 60)
                if len(calls) == 3:
                    return response([mention(None, quantity='deux boîtes')])
                return response([mention('ABIP')]) if len(calls) == 1 else response(
                    [mention(None, presentation='Lboita dyal 30')], intents=['medication_information'], language='darija')
            interpreter.interpret.side_effect = interpret
            return interpreter
        settings = Settings(inference_min_interval_seconds=0, inference_quota_db=root / 'quota.db')
        with patch('pharmacy_assistant.evaluate_conversation_smoke.create_interpreter', side_effect=factory), redirect_stdout(io.StringIO()):
            report = await run_smoke(settings, root / 'smoke.json', max_requests=maximum, quantity_check=maximum == 3)
        return report, calls

    async def test_two_turns_share_context_and_zero_budget_sends_nothing(self):
        for maximum in (0, 2, 3):
            with tempfile.TemporaryDirectory() as directory:
                report, calls = await self.check(Path(directory), maximum)
            self.assertEqual(len(calls), maximum)
            self.assertEqual(report['budget']['attempts_reserved'], maximum)
            self.assertEqual(report['status'], 'passed' if maximum else 'stopped_provider_error')
            if maximum:
                self.assertEqual(report['turns'][1]['response']['medications'][0]['medication']['source_record_id'], '9080')
            if maximum == 3:
                self.assertEqual(report['turns'][2]['response']['order_pricing']['total_price_mad'], '744.00')

    async def test_provider_failure_stops_and_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, calls = await self.check(root, 2, failure=True)
            self.assertEqual(len(calls), 1)
            self.assertEqual(report['error']['code'], 'provider_rate_limited')
            self.assertFalse(report['turns'])
            with self.assertRaises(ValueError), patch('pharmacy_assistant.evaluate_conversation_smoke.create_interpreter') as factory:
                await run_smoke(Settings(), root / 'smoke.json')
            factory.assert_not_called()


if __name__ == '__main__': unittest.main()
