import json
import unittest
from pydantic import ValidationError
from pharmacy_core.medications.catalog import DATASET, MedicationCatalog, contains_presentation, contains_strength
from pharmacy_core.medications.models import MedicationSearchRequest

def expected_snapshot():
    from tests.support.catalogue import profile
    p = profile()
    return p["records"], p["source_pages"], p["missing_public_prices"], set(p["source_listings"])
EXPECTED_RECORDS, EXPECTED_PAGES, EXPECTED_MISSING_PPV, EXPECTED_LISTINGS = expected_snapshot()

class CatalogueTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()

    def search(self, query, **filters):
        return self.catalog.search(MedicationSearchRequest(query=query, **filters))

    def test_enriched_only_product_is_searchable(self):
        self.assertEqual(len(self.catalog.records), EXPECTED_RECORDS)
        self.assertEqual(len(self.catalog.by_id), EXPECTED_RECORDS)
        result = self.search('AIRCORT')
        self.assertGreater(result.result_count, 0)
        self.assertTrue(all((r.brand_name == 'AIRCORT' for r in result.medications)))

    def test_abip_presentations_retain_prices_and_enrichment(self):
        result = self.search('  aBiP  ', strength='15mg')
        self.assertEqual(result.result_count, 2)
        self.assertEqual({r.ppv_price_mad for r in result.medications}, {268.0, 372.0})
        self.assertEqual(len({r.source_record_id for r in result.medications}), 2)
        self.assertTrue(all((r.authorization_status for r in result.medications)))

    def test_filters_select_one_presentation_without_merging(self):
        result = self.search('ABIP', strength='15 mg', form='comprimé', presentation='20')
        self.assertEqual(result.result_count, 1)
        self.assertEqual(result.medications[0].ppv_price_mad, 268.0)
        self.assertEqual(self.search('ABIP', strength='5 mg').result_count, 0)
        self.assertEqual(self.search('ABIP', form='sirop').result_count, 0)
        self.assertEqual(self.search('ABIP', presentation='200').result_count, 0)

    def test_active_substance_and_case_search(self):
        result = self.search('  aRiPiPrAzOlE ')
        self.assertGreaterEqual(result.result_count, 4)
        self.assertTrue(all(('ARIPIPRAZOLE' in r.active_substance for r in result.medications)))

    def test_spelling_suggestions_never_become_results(self):
        result = self.search('ABPI', strength='15 mg')
        self.assertEqual(result.status, 'suggestions')
        self.assertEqual(result.result_count, 0)
        self.assertEqual(result.medications, [])
        abip = next((s for s in result.suggestions if s.term == 'ABIP'))
        self.assertEqual(set(abip.medication_ids), {'9079', '9080'})

    def test_unknown_and_filter_misses_are_not_nonexistence_claims(self):
        for result in (self.search('zzzz_unmatched'), self.search('ABIP', strength='999 mg')):
            self.assertEqual(result.status, 'not_found')
            self.assertEqual(result.suggestions, [])
            self.assertIn('partial catalogue', result.message)
            self.assertIn('does not establish', result.message)

    def test_strength_units_and_numeric_boundaries(self):
        for value, query, expected in [('15 MG', '15mg', True), ('1,50 MG', '1.50 mg', True), ('15 MG', '5 mg', False), ('1.5 MG', '5 mg', False), ('5 MCG', '5 mg', False), ('100 MG / 5 ML', '100mg/5ml', True), ('15 MG/ML', '15 mg', True)]:
            with self.subTest(value=value, query=query):
                self.assertEqual(contains_strength(value, query), expected)
        self.assertFalse(contains_presentation('BOITE DE 200', '20'))
        self.assertTrue(contains_presentation('BOITE DE 20', '20'))

    def test_whitespace_input_rejected_for_query_and_filters(self):
        for fields in ({'query': '   '}, {'query': '́'}, {'query': 'ABIP', 'strength': '  '}):
            with self.assertRaises(ValidationError):
                MedicationSearchRequest(**fields)
