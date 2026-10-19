import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from pharmacy_assistant.catalog import DATASET
from pharmacy_assistant.prepare_demo_enrichment import (
    ROOT, build_candidate, merge_observations, rows, verify_collected,
)
from pharmacy_assistant.supplementary_sources import parse_medicament_detail

URL = "https://medicament.ma/medicament/abip-15-mg-comprime-pellicule-2/"
FETCHED = "2026-10-19T18:00:00+00:00"


class FrozenEnrichmentTests(unittest.TestCase):
    def test_latest_whole_observation_and_earlier_unrefreshed_ids_are_preserved(self):
        old = {"source": "medicament.ma", "source_record_id": "one", "source_url": URL,
               "fetched_at_utc": "2026-10-18T16:00:00+00:00", "atc_code": "N05AX12"}
        retained = {**old, "source_record_id": "two"}
        new = {**old, "fetched_at_utc": FETCHED, "atc_code": None}
        selected, stats = merge_observations([old, retained], [new], "medicament.ma")
        self.assertEqual(selected, [new, retained])
        self.assertIsNone(selected[0]["atc_code"])
        self.assertEqual(stats["retained_previous_only"], 1)

    def test_conflicting_same_timestamp_and_duplicate_source_ids_are_rejected(self):
        row = {"source": "medicament.ma", "source_record_id": "one", "source_url": URL,
               "fetched_at_utc": FETCHED, "atc_code": None}
        with self.assertRaises(ValueError):
            merge_observations([row], [{**row, "atc_code": "N05AX12"}], "medicament.ma")
        with self.assertRaises(ValueError):
            merge_observations([], [row, row], "medicament.ma")

    def test_freeze_reparses_raw_content_and_rejects_tampered_parsed_prices(self):
        body = (ROOT / "data/raw/source_discovery/medicament_detail_2.html").read_bytes()
        observed = parse_medicament_detail(body.decode("utf-8-sig"), URL, FETCHED)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "raw").mkdir()
            (directory / "parsed").mkdir()
            (directory / "raw/detail.html").write_bytes(body)
            (directory / "raw/detail.meta.json").write_text(json.dumps({
                "sha256": hashlib.sha256(body).hexdigest(), "status_code": 200,
                "requested_url": URL, "source_url": URL, "fetched_at_utc": FETCHED}))
            parsed_path = directory / "parsed/detail.json"
            parsed_path.write_text(json.dumps([observed]))
            records, evidence = verify_collected(directory, "medicament.ma")
            self.assertEqual(records, [observed])
            self.assertIn(observed["source_record_id"], evidence)
            parsed_path.write_text(json.dumps([{**observed, "ppv_price_mad": 999.0}]))
            with self.assertRaises(ValueError):
                verify_collected(directory, "medicament.ma")

    def test_candidate_enrichment_preserves_official_facts_and_original_input(self):
        primary = next(r for r in rows(DATASET) if r["source_record_id"] == "9080")
        before = copy.deepcopy(primary)
        observed = parse_medicament_detail(
            (ROOT / "data/raw/source_discovery/medicament_detail_2.html").read_text(encoding="utf-8"), URL, FETCHED)
        observed["ppv_price_mad"] = 999.0
        candidate, matching, quality = build_candidate([primary], [observed])
        self.assertEqual(primary, before)
        self.assertTrue(quality["passed"])
        self.assertEqual(candidate[0]["ppv_price_mad"], before["ppv_price_mad"])
        self.assertEqual(candidate[0]["atc_code"], "N05AX12")
        self.assertTrue(any(c["field"] == "ppv_price_mad" for c in matching["conflicts"]))


if __name__ == "__main__":
    unittest.main()
