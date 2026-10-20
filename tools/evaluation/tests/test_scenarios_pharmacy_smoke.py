from tests.support.ledger import OfflineEvaluationCase, OfflineEvaluationSyncCase, clear_fixture_ledger
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_evaluation.runners.baseline import AnnotationInterpreter
from pharmacy_evaluation.runners.scenarios.pharmacy import run_pharmacy_smoke, smoke_cases, score_pharmacy, summarize_pharmacy
from pharmacy_evaluation.datasets.baseline import load_examples

class PharmacySmokeTests(OfflineEvaluationCase):

    async def test_budgeted_partial_run_resumes_only_remaining_cases(self):
        by_text = {c.text: c for c in load_examples('development')}
        calls = []

        def factory(settings, *, control):

            class Offline:

                async def interpret(self, request):
                    await control.before_attempt()
                    calls.append(request.text)
                    result = await AnnotationInterpreter(by_text[request.text]).interpret(request)
                    result.metadata.requested_model = settings.inference_model
                    return result

                async def close(self):
                    pass
            return Offline()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(gemini_api_key='offline-fixture', inference_min_interval_seconds=0)
            with patch('pharmacy_evaluation.runners.interpretation.create_interpreter', side_effect=factory), redirect_stdout(io.StringIO()):
                first = await run_pharmacy_smoke(settings, root / 'live.json', max_requests=2)
                self.assertFalse(first['summary']['passed'])
                second = await run_pharmacy_smoke(settings, root / 'live.json', max_requests=2, resume=True)
            self.assertTrue(second['summary']['passed'])
            self.assertEqual(second['summary']['pharmacy_resolutions_correct'], 4)
            self.assertEqual(len(set(calls)), 4)
            self.assertEqual(sum((i['attempts_reserved'] for i in second['invocations'])), 4)
            self.assertTrue(all(('0537720657' in row['grounded_answer'] for row in second['results'])))

    async def test_incorrect_resolution_and_incomplete_coverage_cannot_pass(self):
        cases = smoke_cases()
        self.assertEqual({c['group'] for c in cases}, {'fr', 'ar', 'darija', 'mixed'})
        self.assertTrue(all((c['id'].startswith('dev-') for c in cases)))
        from pharmacy_evaluation.datasets.baseline import EvaluationExample
        case = EvaluationExample.model_validate(cases[0]['baseline_example'])
        from pharmacy_contracts.interpretation import InterpretationRequest
        result = await AnnotationInterpreter(case).interpret(InterpretationRequest(text=case.text))
        result.interpretation.entities.pharmacy = 'XYZZZ999999'
        scored = score_pharmacy(result, cases[0])
        self.assertFalse(scored['pharmacy_resolution_correct'])
        summary = summarize_pharmacy([{'id': cases[0]['id'], 'group': 'fr', **scored}], 4)
        self.assertFalse(summary['passed'])
        self.assertEqual(summary['pharmacy_resolutions_correct'], 0)
