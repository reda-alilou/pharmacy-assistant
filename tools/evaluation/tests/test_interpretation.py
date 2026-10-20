from tests.support.ledger import OfflineEvaluationCase, OfflineEvaluationSyncCase, clear_fixture_ledger
import json
import unittest
from collections import Counter
from pharmacy_evaluation.runners.interpretation import CASES, compare_entities, summarize
from pharmacy_contracts.interpretation import Interpretation

def extraction():
    return {'language': 'darija', 'reply_language': 'darija', 'reply_script': 'latin', 'intents': ['price', 'availability'], 'entities': {'medications': [{'name': 'ABIP', 'strength': '15mg', 'quantity': None, 'form': None, 'presentation': None}], 'pharmacy': None, 'city': None, 'area': None, 'date': None, 'time': None, 'symptom': None}}

class SmokeEvaluationTests(OfflineEvaluationSyncCase):

    def test_fixture_has_twelve_balanced_cases_and_only_message_spans(self):
        cases = json.loads(CASES.read_text(encoding='utf-8'))
        self.assertEqual(Counter((c['group'] for c in cases)), {'fr': 3, 'ar': 3, 'darija': 3, 'mixed': 3})
        for case in cases:
            fields = list(case['expected_context'].values())
            fields.extend((v for m in case['expected_medications'] for v in m.values()))
            for allowed in fields:
                for value in allowed:
                    if value is not None:
                        self.assertIn(value, case['text'])

    def test_incomplete_or_failed_run_cannot_pass(self):
        self.assertFalse(summarize([], 12)['passed'])
        self.assertFalse(summarize([{'intents_correct': True}], 12)['passed'])
        valid = {'response': {}, 'intents_correct': True, 'entities_exact': True}
        self.assertTrue(summarize([valid] * 12, 12)['passed'])
        missing = {**valid, 'entities_exact': False}
        self.assertFalse(summarize([missing] * 12, 12)['passed'])
        bad = {**valid, 'incorrect_nonnull_entities': ['city']}
        self.assertFalse(summarize([valid] * 11 + [bad], 12)['passed'])

    def test_entity_comparison_distinguishes_missing_from_wrong(self):
        cases = json.loads(CASES.read_text(encoding='utf-8'))
        case = next((c for c in cases if c['id'] == 'darija-price'))
        actual = Interpretation.model_validate(extraction())
        self.assertTrue(compare_entities(actual, case)['entities_exact'])
        actual.entities.medications[0].quantity = 'two boxes'
        self.assertIn('medications[0].quantity', compare_entities(actual, case)['incorrect_nonnull_entities'])
