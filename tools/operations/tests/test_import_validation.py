import json
import unittest
from pharmacy_core.medications.catalog import DATASET
from pharmacy_ops.import_validation import validate_records

def expected_snapshot():
    from tests.support.catalogue import profile
    p = profile()
    return p["records"], p["source_pages"], p["missing_public_prices"], set(p["source_listings"])
EXPECTED_RECORDS, EXPECTED_PAGES, EXPECTED_MISSING_PPV, EXPECTED_LISTINGS = expected_snapshot()

class QualityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in DATASET.read_text(encoding='utf-8').splitlines()]

    def test_full_enriched_dataset_passes_with_unknown_prices(self):
        report = validate_records(self.records)
        self.assertTrue(report['passed'], report['errors'])
        self.assertEqual(report['total_records'], EXPECTED_RECORDS)
        self.assertEqual(report['missing_ppv'], EXPECTED_MISSING_PPV)
        self.assertEqual(report['detailed_source_pages'], list(range(1, EXPECTED_PAGES + 1)))
        self.assertEqual(set(report['pages_by_listing']), EXPECTED_LISTINGS)

    def test_invalid_prices_schema_and_provenance_fail(self):
        original = self.records[0]
        invalid = [{**original, 'ppv_price_mad': price} for price in (-1, True, float('inf'), float('nan'), '268')] + [{**original, 'source_url': original['source_url'] + '0'}, {**original, 'detailed_source_url': 'https://example.org/?page=1'}, {**original, 'source_page': True}, {**original, 'source_record_id': 'not-an-id'}, {key: value for key, value in original.items() if key != 'pfht_price_mad'}]
        for record in invalid:
            with self.subTest(record=record):
                self.assertFalse(validate_records([record])['passed'])

    def test_empty_duplicate_and_nonobject_data_fail(self):
        for rows in ([], [self.records[0], self.records[0]], [None]):
            self.assertFalse(validate_records(rows)['passed'])
