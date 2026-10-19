"""Parser, provenance and conservative joining checks for the data checkpoint."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pharmacy_assistant.build_reference_data import (
    dose_key, link_secondary, matching_key, presentation_key, snapshot_records,
)
from pharmacy_assistant.catalog import DATASET
from pharmacy_assistant.collect_ammps_snapshot import advertised_total
from pharmacy_assistant.collect_rabat_pharmacies import normalize_pharmacies
from pharmacy_assistant.collection_http import SourceClient, redact_url
from pharmacy_assistant.supplementary_sources import (
    parse_medicament_detail, parse_saydalia_listing, source_price,
)
from pharmacy_assistant.process_ammps import normalize_price


ROOT = Path(__file__).resolve().parents[1]
DISCOVERY = ROOT / "data/raw/source_discovery"
FETCHED = "2026-10-18T16:00:00+00:00"
MED_URL = "https://medicament.ma/medicament/abip-15-mg-comprime-pellicule-2/"


class SecondaryParserTests(unittest.TestCase):
    def test_medicament_extracts_actual_details_and_publication_date(self):
        html = (DISCOVERY / "medicament_detail_2.html").read_text(encoding="utf-8")
        record = parse_medicament_detail(html, MED_URL, FETCHED)
        self.assertEqual(record["brand_name"], "ABIP")
        self.assertEqual(record["dosage"], "15 MG")
        self.assertEqual(record["presentation"], "Boite de 30")
        self.assertEqual(record["ppv_price_mad"], 372.0)
        self.assertEqual(record["atc_code"], "N05AX12")
        self.assertIn("2025", record["source_updated_at_raw"])
        self.assertIsNone(record["reimbursement_raw"])

    def test_missing_presentation_is_preserved_without_guessing(self):
        html = ('<h1 class="main-title">TEST, Gel</h1><div class="medicine-details">'
                '<div class="detail-item"><div class="detail-header">Composition</div>'
                '<div class="detail-content">Example</div></div></div>')
        record = parse_medicament_detail(html, MED_URL, FETCHED)
        self.assertIsNone(record["presentation"])
        self.assertIsNone(matching_key(record))
        with self.assertRaises(ValueError):
            parse_medicament_detail("<html>Unavailable</html>", MED_URL, FETCHED)

    def test_saydalia_repeated_attributes_do_not_duplicate_products(self):
        html = (DISCOVERY / "saydalia_medications.html").read_text(encoding="utf-8")
        records = parse_saydalia_listing(html, FETCHED)
        self.assertEqual(len(records), 12)
        self.assertEqual(len({r["source_record_id"] for r in records}), 12)
        self.assertEqual(records[0]["ppv_price_mad"], 10411.0)
        self.assertEqual(records[0]["reimbursement_raw"], "Oui")
        # Preserve the site's incomplete code as observed; never fabricate a digit.
        self.assertEqual(records[0]["atc_code"], "L02BX0")

    def test_secondary_prices_and_package_boundaries(self):
        for value, expected in [("10.411,00 MAD", 10411.0), ("10.70 dhs", 10.7),
                                ("1.678,00 MAD", 1678.0), (None, None)]:
            self.assertEqual(source_price(value), expected)
        with self.assertRaises(ValueError):
            source_price("approximately 20")
        self.assertNotEqual(presentation_key("Boite de 20"), presentation_key("Boite de 30"))
        self.assertNotEqual(presentation_key("Flacon de 20 ml"), presentation_key("Flacon de 20 g"))
        self.assertEqual(dose_key("0,50 MG"), dose_key("0.5mg"))
        self.assertEqual(dose_key("100 µG"), dose_key("100 mcg"))
        self.assertIsNone(dose_key("-"))
        self.assertIsNone(normalize_price("NA DH"))
        self.assertIsNone(normalize_price("N/A DH"))


class MatchingTests(unittest.TestCase):
    def setUp(self):
        records = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
        self.primary = copy.deepcopy(next(r for r in records if r["source_record_id"] == "9080"))
        self.primary.update(source_observations=[], data_conflicts=[], atc_code=None, reimbursement_status=None)
        html = (DISCOVERY / "medicament_detail_2.html").read_text(encoding="utf-8")
        self.observed = parse_medicament_detail(html, MED_URL, FETCHED)

    def test_unique_presentation_enrichment_preserves_official_prices(self):
        self.observed["ppv_price_mad"] = 999.0
        original_price = self.primary["ppv_price_mad"]
        report = link_secondary([self.primary], [self.observed])
        self.assertEqual(len(report["matched_observations"]), 1)
        self.assertEqual(self.primary["ppv_price_mad"], original_price)
        self.assertEqual(self.primary["atc_code"], "N05AX12")
        self.assertEqual(self.primary["source_observations"][0]["ppv_price_mad"], 999.0)
        self.assertTrue(any(c["field"] == "ppv_price_mad" for c in report["conflicts"]))

    def test_ambiguous_and_wrong_strength_never_auto_merge(self):
        duplicate = copy.deepcopy(self.primary)
        duplicate["source_record_id"] = "test-other-id"
        report = link_secondary([self.primary, duplicate], [self.observed])
        self.assertEqual(len(report["ambiguous_observations"]), 1)
        self.assertEqual(self.primary["source_observations"], [])
        self.observed["dosage"] = "5 MG"
        report = link_secondary([self.primary], [self.observed])
        self.assertEqual(len(report["unmatched_observations"]), 1)

    def test_secondary_disagreements_leave_canonical_fields_unknown(self):
        other = {**self.observed, "source": "saydalia.ma", "atc_code": "N05AX13",
                 "reimbursement_raw": "Non", "source_url": "https://saydalia.ma/fr/produit/example/"}
        self.observed["reimbursement_raw"] = "Oui"
        report = link_secondary([self.primary], [self.observed, other])
        self.assertIsNone(self.primary["atc_code"])
        self.assertIsNone(self.primary["reimbursement_status"])
        self.assertTrue(any(c["field"] == "atc_code" for c in report["conflicts"]))

    def test_invalid_atc_and_nonmedication_products_are_not_promoted(self):
        self.observed["atc_code"] = "N05AX1"
        link_secondary([self.primary], [self.observed])
        self.assertIsNone(self.primary["atc_code"])
        self.primary["source_observations"] = []
        self.observed["product_nature"] = "Complément alimentaire"
        report = link_secondary([self.primary], [self.observed])
        self.assertEqual(report["matched_observations"], [])


class PharmacyAndCollectionTests(unittest.TestCase):
    def test_only_rabat_records_and_no_undated_duty_claim(self):
        raw = [{"id": "123", "title": "Example", "Ville": "Rabat", "Phone": "0537000000",
                "address": "Source-provided address", "lat": 34.0, "lng": -6.8, "garde": "2"},
               {"id": "456", "title": "Other city", "Ville": "Témara", "lat": 33.9, "lng": -6.8}]
        records, duties = normalize_pharmacies(raw, {"source_url": "https://saydalia.ma/api/siteweb_api.php",
                                                    "fetched_at_utc": FETCHED})
        self.assertEqual(len(records), 1)
        self.assertIsNone(records[0]["opening_information"])
        self.assertFalse(duties[0]["duty_verified"])
        self.assertIsNone(duties[0]["valid_until"])
        self.assertEqual(duties[0]["observed_garde_raw"], "2")

    def test_source_cache_verifies_hash_and_redacts_browser_tokens(self):
        with tempfile.TemporaryDirectory() as directory:
            response = Mock(content=b"[]", status_code=200)
            response.url = "https://saydalia.ma/api/siteweb_api.php?origin=34,-6&api_key=TEST_BROWSER_TOKEN"
            with SourceClient("https://saydalia.ma", Path(directory)) as client:
                with patch.object(client.session, "get", return_value=response) as request:
                    params = {"origin": "34,-6", "api_key": "TEST_BROWSER_TOKEN"}
                    _, meta = client.get("https://saydalia.ma/api/siteweb_api.php", "sample", params=params)
                    client.get("https://saydalia.ma/api/siteweb_api.php", "sample", params=params)
                    self.assertEqual(request.call_count, 1)
                self.assertNotIn("TEST_BROWSER_TOKEN", json.dumps(meta))
                Path(directory, "sample.html").write_text("tampered", encoding="utf-8")
                with self.assertRaises(ValueError):
                    client.get("https://saydalia.ma/api/siteweb_api.php", "sample", params=params)
                with self.assertRaises(ValueError):
                    client.get("https://other.example/", "sample")
        self.assertNotIn("api_key", redact_url(response.url))

    def test_incomplete_snapshot_cannot_replace_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "manifest.json").write_text('{"complete":false}', encoding="utf-8")
            with self.assertRaises(ValueError):
                snapshot_records(path)
        html = (DISCOVERY / "ammps_live_1.html").read_text(encoding="utf-8")
        self.assertEqual(advertised_total(html), 9936)


if __name__ == "__main__":
    unittest.main()
