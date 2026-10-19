"""Evaluation integrity: budgets, no gold injection, and failed-output denominators."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pharmacy_assistant.config import Settings
from pharmacy_assistant.config import ROOT
from pharmacy_assistant.evaluate_development import AuditedGroqClient, development_jobs, run
from pharmacy_assistant.evaluation_dataset import load_examples
from pharmacy_assistant.nlu_models import InferenceError, InterpretationResponse
from pharmacy_assistant.report_live_evaluation import analyze
from pharmacy_assistant.merge_development_rechecks import merge


class DevelopmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_budget_resume_and_all_40_outcomes_use_only_captured_live_predictions(self):
        cases = load_examples('development')
        jobs = development_jobs(cases)
        self.assertEqual(len(jobs), 48)
        self.assertTrue(all(j['case_id'].startswith('dev-') for j in jobs))
        annotations = {c.text: c.interpretation for c in cases}
        annotations.update({t.text: t.interpretation for c in cases for t in c.context})
        calls = []
        def factory(settings, *, control):
            class Offline:
                async def interpret(self, request):
                    await control.before_attempt()
                    calls.append(request.text)
                    parsed = annotations[request.text].model_copy(deep=True)
                    # Production extraction is intentionally raw/current-message-only.
                    if request.text == 'La boîte de 30, merci.':
                        parsed.intents = ['medication_information']
                    return InterpretationResponse.model_validate({
                        'interpretation': parsed.model_dump(),
                        'metadata': {'provider': settings.inference_provider, 'model': settings.inference_model,
                                     'requested_model': settings.inference_model, 'prompt_version': 'offline-test',
                                     'latency_ms': 1, 'attempts': 1, 'completion_id': None,
                                     'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}}})
                async def close(self): pass
            return Offline()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            settings = Settings(inference_provider='groq', groq_api_key='offline-key', inference_quota_db=Path(d)/'quota.db')
            output = Path(d)/'report.json'
            first = await run(settings, output, max_requests=4, factory=factory)
            self.assertEqual(first['summary']['completed_inference_jobs'], 4)
            second = await run(settings, output, max_requests=44, resume=True, factory=factory)
            self.assertEqual(len(calls), 48)
            self.assertEqual(second['summary']['passed_outcomes'], 40)
            self.assertEqual(second['summary']['raw_single_turn_extraction']['completed_cases'], 32)
            self.assertEqual(second['summary']['effective_dialogue_extraction']['completed_cases'], 40)
            self.assertEqual(second['summary']['effective_dialogue_extraction']['intent_micro']['f1'], 1)
            final = analyze(output, Path(d)/'metrics.json')
            self.assertEqual(final['dialogue_intents_and_current_slots']['entity_slot_micro']['f1'], 1)
            self.assertEqual(final['dialogue_intents_and_current_slots']['intent_micro']['f1'], 1)
            self.assertEqual(final['backend']['passed'], 40)
            recheck = json.loads(json.dumps(second))
            row = recheck['predictions'][0]
            row.pop('response')
            row['error'] = {'code':'provider_invalid_response','message':'offline failure','retryable':False,'retry_after_seconds':None}
            recheck['predictions'] = [row]
            recheck['invocations'] = []
            recheck['errors'] = []
            target = Path(d)/'targeted.json'
            target.write_text(json.dumps(recheck),encoding='utf-8')
            combined = await merge(output,target,Path(d)/'combined.json')
            self.assertEqual(combined['summary']['passed_outcomes'],39)
            self.assertNotIn('response',combined['predictions'][0])
            await run(settings, output, max_requests=4, resume=True, factory=factory)
            self.assertEqual(len(calls), 48)
            changed = settings.model_copy(update={'groq_model':'changed'})
            with self.assertRaisesRegex(ValueError, 'configuration'):
                await run(changed, output, max_requests=1, resume=True, factory=factory)

    async def test_invalid_output_is_retained_as_failure_instead_of_retried_until_success(self):
        def factory(settings, *, control):
            class Invalid:
                async def interpret(self, request):
                    await control.before_attempt()
                    raise InferenceError('provider_invalid_response', 'Offline invalid output', 502)
                async def close(self): pass
            return Invalid()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            settings = Settings(inference_provider='groq', groq_api_key='offline-key', inference_quota_db=Path(d)/'quota.db')
            report = await run(settings, Path(d)/'report.json', max_requests=2, factory=factory)
            self.assertEqual(report['status'], 'paused_budget')
            self.assertEqual(len(report['predictions']), 2)
            self.assertEqual(report['summary']['completed_outcomes'], 2)
            self.assertEqual(report['summary']['passed_outcomes'], 0)
            self.assertEqual(report['summary']['accepted_inference_jobs'], 0)

    async def test_audit_separates_schema_failure_from_unsupported_entity_evidence(self):
        case = load_examples('development')[0]
        parsed = case.interpretation.model_copy(deep=True)
        parsed.entities.medications[0].name = 'Invented'
        contents = iter([parsed.model_dump_json(), '{not json}'])
        async def create(**kwargs):
            return SimpleNamespace(choices=[SimpleNamespace(finish_reason='stop', message=SimpleNamespace(content=next(contents)))],
                                   usage=None, model='offline-fixture')
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        audit = []
        wrapper = AuditedGroqClient(client, audit)
        wrapper.text = case.text
        await wrapper.create()
        await wrapper.create()
        self.assertTrue(audit[0]['schema_valid'])
        self.assertFalse(audit[0]['evidence_valid'])
        self.assertFalse(audit[1]['schema_valid'])
        self.assertIsNone(audit[1]['evidence_valid'])

    async def test_held_out_gate_runs_before_loading_examples_or_creating_a_provider(self):
        with patch('pharmacy_assistant.evaluation_freeze.verify_freeze',side_effect=ValueError('freeze mismatch')), \
             patch('pharmacy_assistant.evaluate_development.load_examples') as loader:
            with self.assertRaisesRegex(ValueError,'freeze mismatch'):
                await run(Settings(),Path('unused.json'),split='held_out',freeze=Path('invalid-freeze.json'))
            loader.assert_not_called()

    async def test_custom_seen_regressions_are_development_only_and_have_their_own_checksum(self):
        fixture=ROOT/'data/evaluation/matching_regressions_v1.json'
        with tempfile.TemporaryDirectory() as d, redirect_stdout(io.StringIO()):
            settings=Settings(inference_provider='groq',groq_api_key='offline-key',inference_quota_db=Path(d)/'quota.db')
            def no_calls(settings,*,control):
                class Offline:
                    async def interpret(self,request):
                        await control.before_attempt()
                        raise AssertionError('Zero request budget must prevent inference')
                    async def close(self): pass
                return Offline()
            report=await run(settings,Path(d)/'custom.json',max_requests=0,factory=no_calls,examples_path=fixture,
                             case_ids=['fresh-fr-unitless-strength'])
            self.assertEqual(report['summary']['cases'],1)
            self.assertEqual(report['summary']['inference_jobs'],2)
            self.assertEqual(report['invocations'][0]['attempts_reserved'],0)
            self.assertEqual(report['sources']['annotations_path'],str(fixture))
            with self.assertRaisesRegex(ValueError,'complete split'):
                await run(settings,Path(d)/'held.json',split='held_out',freeze=Path('unused-freeze.json'),examples_path=fixture)


if __name__ == '__main__':
    unittest.main()
