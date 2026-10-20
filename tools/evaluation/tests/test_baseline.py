from tests.support.ledger import OfflineEvaluationCase, OfflineEvaluationSyncCase, clear_fixture_ledger
import json
from pathlib import Path
import tempfile
import unittest
from pharmacy_core.medications.catalog import DATASET
from pharmacy_evaluation.runners.baseline import live_cases
from pharmacy_evaluation.datasets.baseline import DATA_DIRECTORY, load_examples, sha256, validate_dataset

class DatasetTests(OfflineEvaluationSyncCase):

    def test_balanced_splits_raw_spans_ids_and_freeze_validate(self):
        report = validate_dataset()
        self.assertEqual(report['examples'], 80)
        self.assertEqual(report['kinds'], {'single_turn': 64, 'conversation_turn': 16})
        manifest = json.loads((DATA_DIRECTORY / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(report['catalogue_matches_annotation_snapshot'], sha256(DATASET) == manifest['catalogue_sha256'])
        self.assertEqual(report['held_out_execution'], 'not_run')
        for split in ('development', 'held_out'):
            for case in load_examples(split):
                case.interpretation.validate_evidence(case.text)
                for turn in case.context:
                    turn.interpretation.validate_evidence(turn.text)

    def test_modified_frozen_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            for name in ('manifest.json', 'development.json'):
                (target / name).write_bytes((DATA_DIRECTORY / name).read_bytes())
            with (target / 'development.json').open('a', encoding='utf-8') as stream:
                stream.write(' ')
            with self.assertRaisesRegex(ValueError, 'Frozen annotations changed'):
                load_examples('development', target)

    def test_live_cases_exclude_all_context_and_held_out_examples(self):
        cases = live_cases()
        self.assertEqual(len(cases), 32)
        self.assertEqual([c['group'] for c in cases[:4]], ['fr', 'ar', 'darija', 'mixed'])
        self.assertTrue(all((c['id'].startswith('dev-') and (not c['baseline_example']['context']) for c in cases)))
        self.assertTrue(all((sum((c['group'] == g for c in cases)) == 8 for g in ('fr', 'ar', 'darija', 'mixed'))))
from pharmacy_evaluation.scoring.extraction import aggregate_extraction, score_extraction
from pharmacy_evaluation.datasets.baseline import load_examples

class MetricTests(OfflineEvaluationSyncCase):

    @classmethod
    def setUpClass(cls):
        cls.cases = {c.id: c for c in load_examples('development')}

    def test_order_of_multiple_medications_does_not_change_slot_f1(self):
        case = self.cases['dev-fr-05']
        actual = case.interpretation.model_copy(deep=True)
        actual.entities.medications.reverse()
        result = score_extraction(actual, case)
        self.assertTrue(result['entities_exact'])
        self.assertEqual(result['slot_counts']['f1'], 1)

    def test_duplicate_prediction_cannot_reuse_a_gold_mention(self):
        case = self.cases['dev-fr-01']
        actual = case.interpretation.model_copy(deep=True)
        actual.entities.medications.append(actual.entities.medications[0].model_copy())
        result = score_extraction(actual, case)
        self.assertEqual(result['slot_counts']['tp'], 1)
        self.assertEqual(result['slot_counts']['fp'], 1)
        self.assertEqual(result['slot_counts']['fn'], 0)
        self.assertAlmostEqual(result['slot_counts']['f1'], 2 / 3)

    def test_wrong_slot_counts_false_positive_and_false_negative(self):
        case = self.cases['dev-fr-01']
        actual = case.interpretation.model_copy(deep=True)
        actual.entities.medications[0].name = 'WrongMedicine'
        result = score_extraction(actual, case)
        self.assertEqual(result['slot_counts']['tp'], 0)
        self.assertEqual(result['slot_counts']['fp'], 1)
        self.assertEqual(result['slot_counts']['fn'], 1)
        self.assertEqual(result['slot_counts']['f1'], 0)

    def test_missing_mention_counts_all_its_non_null_slots(self):
        case = self.cases['dev-fr-05']
        actual = case.interpretation.model_copy(deep=True)
        actual.entities.medications.pop()
        result = score_extraction(actual, case)
        self.assertEqual(result['slot_counts']['fn'], 2)
        self.assertEqual(result['slot_counts']['fp'], 0)

    def test_alternate_evidenced_span_is_accepted(self):
        case = self.cases['dev-fr-06']
        actual = case.interpretation.model_copy(deep=True)
        actual.entities.pharmacy = 'Ibn Nafis'
        self.assertTrue(score_extraction(actual, case)['entities_exact'])

    def test_null_slots_do_not_artificially_inflate_entity_f1(self):
        case = self.cases['dev-mixed-07']
        result = score_extraction(case.interpretation, case)
        self.assertIsNone(result['slot_counts']['f1'])
        self.assertEqual(result['slot_counts']['tp'], 0)

    def test_wrong_intent_and_unobserved_language_groups_are_not_perfect(self):
        case = self.cases['dev-fr-01']
        actual = case.interpretation.model_copy(deep=True)
        actual.intents = ['price', 'availability']
        scored = score_extraction(actual, case)
        self.assertEqual(scored['intent_counts']['tp'], 1)
        self.assertEqual(scored['intent_counts']['fp'], 1)
        result = aggregate_extraction([{'id': case.id, 'group': case.group, **scored}], 32)
        self.assertFalse(result['passed'])
        self.assertIsNone(result['by_group']['ar']['intent_micro']['f1'])
from contextlib import redirect_stdout
import io
from unittest.mock import patch
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest
from tests.support.configuration import FixtureSettings as Settings
from pharmacy_evaluation.runners.baseline import AnnotationInterpreter, backend_baseline, baseline_summary, live_baseline, score_outcome
from pharmacy_core.pharmacies.directory import PharmacyDirectory

class BackendBaselineTests(OfflineEvaluationCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()
        cls.cases = {c.id: c for c in load_examples('development')}

    async def test_annotation_oracle_uses_no_live_factory_and_separates_conversation(self):
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()), patch('pharmacy_evaluation.runners.interpretation.create_interpreter') as factory:
            report = await backend_baseline(Path(directory) / 'backend.json')
        factory.assert_not_called()
        self.assertEqual(report['summary']['cases'], 40)
        self.assertEqual(report['summary']['single_turn']['cases'], 32)
        self.assertEqual(report['summary']['conversation']['cases'], 8)
        self.assertFalse(report['is_model_accuracy_measurement'])
        self.assertEqual(report['live_provider_requests'], 0)
        self.assertTrue(all((r['id'].startswith('dev-') for r in report['results'])))

    async def test_same_medication_with_wrong_price_record_is_not_a_correct_resolution(self):
        case = self.cases['dev-mixed-01']
        service = ChatService(self.catalog, AnnotationInterpreter(case), self.directory)
        body = await service.respond(ChatRequest(text=case.text))
        body.medications[0].medication = self.catalog.get('9080')
        result = score_outcome(body, case, self.catalog)
        self.assertTrue(any((f['code'] == 'incorrect_automatic_selection' for f in result['failures'])))

    async def test_failure_summary_distinguishes_error_counts_from_case_counts_without_live_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = {'summary': {'cases': 40}, 'results': [{'id': 'dev-fr-01', 'observed': {}, 'failures': [{'component': 'matching', 'code': 'first_issue'}, {'component': 'matching', 'code': 'second_issue'}]}]}
            (root / 'backend.json').write_text(json.dumps(backend), encoding='utf-8')
            with patch('pharmacy_evaluation.runners.interpretation.create_interpreter') as factory:
                report = baseline_summary(root / 'backend.json', root / 'missing_live.json', root / 'summary.json')
            factory.assert_not_called()
            self.assertEqual(len(report['backend_failures_by_component']['matching']), 1)
            self.assertEqual(report['live_extraction']['remaining_single_turn_cases'], 32)
            self.assertIsNone(report['live_extraction']['summary'])
            self.assertIsNone(report['live_extraction']['latency_ms'])
            self.assertEqual(report['held_out_execution'], 'not_run')

    async def test_budgeted_live_adapter_resumes_custom_metrics_with_mocked_inference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = Settings(gemini_api_key='offline-fixture', inference_min_interval_seconds=0)
            cases = {c.text: c for c in load_examples('development')}
            calls = []

            def factory(settings, *, control):

                class Offline:

                    async def interpret(self, request):
                        await control.before_attempt()
                        calls.append(request.text)
                        response = await AnnotationInterpreter(cases[request.text]).interpret(request)
                        response.metadata.requested_model = settings.inference_model
                        return response

                    async def close(self):
                        pass
                return Offline()
            with patch('pharmacy_evaluation.runners.interpretation.create_interpreter', side_effect=factory), redirect_stdout(io.StringIO()):
                first = await live_baseline(settings, root / 'live.json', max_requests=4)
                second = await live_baseline(settings, root / 'live.json', max_requests=1, resume=True)
            self.assertEqual(first['summary']['completed_cases'], 4)
            self.assertEqual(second['summary']['completed_cases'], 5)
            self.assertEqual(second['summary']['total_cases'], 32)
            self.assertEqual(second['summary']['intent_micro']['f1'], 1)
            self.assertFalse(second['summary']['passed'])
            self.assertEqual(len(set(calls)), 5)
