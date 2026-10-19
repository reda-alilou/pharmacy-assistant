"""Step 1 acceptance checks; no API key or third-party test runner required."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

from pydantic import ValidationError

from pharmacy_assistant.api import create_app
from pharmacy_assistant.catalog import (
    DATASET,
    MedicationCatalog,
    contains_presentation,
    contains_strength,
)
from pharmacy_assistant.models import BASIC_SOURCE, DETAILED_SOURCE, MedicationSearchRequest
from pharmacy_assistant.quality_ammps import validate_records
from pharmacy_assistant.search_medications import search_medications


def expected_snapshot():
    """Compare published data against its independently collected source count."""
    first = json.loads(DATASET.read_text(encoding="utf-8").splitlines()[0])
    if not first.get("source_fetched_at_utc"):
        return 2640, 132, 312, {"basic", "detailed"}
    directory = DATASET.parents[1] / "raw/ammps_snapshot"
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    missing = 0
    for page in range(1, manifest["expected_pages"] + 1):
        payload = json.loads((directory / f"page_{page}.json").read_text(encoding="utf-8"))
        raw_prices = ["".join(r["details"]["PPV"].upper().split()).removesuffix("DH")
                      for r in payload["records"]]
        missing += sum("SANSPPV" in value or value in {"NA", "N/A"} for value in raw_prices)
    return manifest["advertised_total"], manifest["expected_pages"], missing, {"detailed"}


EXPECTED_RECORDS, EXPECTED_PAGES, EXPECTED_MISSING_PPV, EXPECTED_LISTINGS = expected_snapshot()


async def http_get(app, path, parameters=None):
    """Exercise the actual ASGI routing, validation and serialization stack."""
    events = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(event):
        events.append(event)

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": urlencode(parameters or {}).encode(),
        "headers": [], "client": ("127.0.0.1", 1), "server": ("test", 80),
        "root_path": "",
    }
    await app(scope, receive, send)
    status = next(e["status"] for e in events if e["type"] == "http.response.start")
    body = b"".join(e.get("body", b"") for e in events if e["type"] == "http.response.body")
    return status, json.loads(body)


class CatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()

    def search(self, query, **filters):
        return self.catalog.search(MedicationSearchRequest(query=query, **filters))

    def test_enriched_only_product_is_searchable(self):
        self.assertEqual(len(self.catalog.records), EXPECTED_RECORDS)
        self.assertEqual(len(self.catalog.by_id), EXPECTED_RECORDS)
        result = self.search("AIRCORT")
        self.assertGreater(result.result_count, 0)
        self.assertTrue(all(r.brand_name == "AIRCORT" for r in result.medications))

    def test_abip_presentations_retain_prices_and_enrichment(self):
        result = self.search("  aBiP  ", strength="15mg")
        self.assertEqual(result.result_count, 2)
        self.assertEqual({r.ppv_price_mad for r in result.medications}, {268.0, 372.0})
        self.assertEqual(len({r.source_record_id for r in result.medications}), 2)
        self.assertTrue(all(r.authorization_status for r in result.medications))

    def test_filters_select_one_presentation_without_merging(self):
        result = self.search("ABIP", strength="15 mg", form="comprimé", presentation="20")
        self.assertEqual(result.result_count, 1)
        self.assertEqual(result.medications[0].ppv_price_mad, 268.0)
        self.assertEqual(self.search("ABIP", strength="5 mg").result_count, 0)
        self.assertEqual(self.search("ABIP", form="sirop").result_count, 0)
        self.assertEqual(self.search("ABIP", presentation="200").result_count, 0)

    def test_active_substance_and_case_search(self):
        result = self.search("  aRiPiPrAzOlE ")
        self.assertGreaterEqual(result.result_count, 4)
        self.assertTrue(all("ARIPIPRAZOLE" in r.active_substance for r in result.medications))

    def test_spelling_suggestions_never_become_results(self):
        result = self.search("ABPI", strength="15 mg")
        self.assertEqual(result.status, "suggestions")
        self.assertEqual(result.result_count, 0)
        self.assertEqual(result.medications, [])
        abip = next(s for s in result.suggestions if s.term == "ABIP")
        self.assertEqual(set(abip.medication_ids), {"9079", "9080"})

    def test_unknown_and_filter_misses_are_not_nonexistence_claims(self):
        for result in (self.search("zzzz_unmatched"), self.search("ABIP", strength="999 mg")):
            self.assertEqual(result.status, "not_found")
            self.assertEqual(result.suggestions, [])
            self.assertIn("partial catalogue", result.message)
            self.assertIn("does not establish", result.message)

    def test_strength_units_and_numeric_boundaries(self):
        for value, query, expected in [
            ("15 MG", "15mg", True), ("1,50 MG", "1.50 mg", True),
            ("15 MG", "5 mg", False), ("1.5 MG", "5 mg", False),
            ("5 MCG", "5 mg", False), ("100 MG / 5 ML", "100mg/5ml", True),
            ("15 MG/ML", "15 mg", True),
        ]:
            with self.subTest(value=value, query=query):
                self.assertEqual(contains_strength(value, query), expected)
        self.assertFalse(contains_presentation("BOITE DE 200", "20"))
        self.assertTrue(contains_presentation("BOITE DE 20", "20"))

    def test_whitespace_input_rejected_for_query_and_filters(self):
        for fields in (
            {"query": "   "}, {"query": "\u0301"},
            {"query": "ABIP", "strength": "  "},
        ):
            with self.assertRaises(ValidationError):
                MedicationSearchRequest(**fields)

    def test_python_search_interface_remains_list_of_dicts(self):
        records = search_medications("ABIP", presentation="30")
        self.assertIsInstance(records, list)
        self.assertEqual(records[0]["ppv_price_mad"], 372.0)

    def test_startup_rejects_empty_duplicate_and_invalid_data(self):
        record = self.catalog.records[0].model_dump(mode="json")
        cases = [[], [record, record], [{**record, "ppv_price_mad": -1}]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.jsonl"
            for rows in cases:
                with self.subTest(rows=len(rows)):
                    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        MedicationCatalog.from_path(path)


class QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]

    def test_full_enriched_dataset_passes_with_unknown_prices(self):
        report = validate_records(self.records)
        self.assertTrue(report["passed"], report["errors"])
        self.assertEqual(report["total_records"], EXPECTED_RECORDS)
        self.assertEqual(report["missing_ppv"], EXPECTED_MISSING_PPV)
        self.assertEqual(report["detailed_source_pages"], list(range(1, EXPECTED_PAGES + 1)))
        self.assertEqual(set(report["pages_by_listing"]), EXPECTED_LISTINGS)

    def test_invalid_prices_schema_and_provenance_fail(self):
        original = self.records[0]
        invalid = [
            {**original, "ppv_price_mad": price}
            for price in (-1, True, float("inf"), float("nan"), "268")
        ] + [
            {**original, "source_url": original["source_url"] + "0"},
            {**original, "detailed_source_url": "https://example.org/?page=1"},
            {**original, "source_page": True},
            {**original, "source_record_id": "not-an-id"},
            {key: value for key, value in original.items() if key != "pfht_price_mad"},
        ]
        for record in invalid:
            with self.subTest(record=record):
                self.assertFalse(validate_records([record])["passed"])

    def test_empty_duplicate_and_nonobject_data_fail(self):
        for rows in ([], [self.records[0], self.records[0]], [None]):
            self.assertFalse(validate_records(rows)["passed"])

    def test_basic_and_detailed_page_numbers_can_differ(self):
        record = {**self.records[0], "detailed_source_url": f"{DETAILED_SOURCE}?page=2",
                  "source_url": f"{BASIC_SOURCE}?page={self.records[0]['source_page']}"}
        self.assertTrue(validate_records([record])["passed"])
        record["source_url"] = f"{DETAILED_SOURCE}?page={record['source_page']}"
        self.assertFalse(validate_records([record])["passed"])


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = create_app()
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()

    async def asyncTearDown(self):
        await self.lifespan.__aexit__(None, None, None)

    async def test_health_and_search_need_no_further_file_reads(self):
        with patch.object(Path, "open", side_effect=AssertionError("Unexpected file read")):
            status, health = await http_get(self.app, "/health")
            self.assertEqual(status, 200)
            self.assertEqual(health["catalog_record_count"], EXPECTED_RECORDS)
            for query in ("ABIP", "AIRCORT"):
                status, result = await http_get(self.app, "/medications/search", {"query": query})
                self.assertEqual(status, 200)
                self.assertGreater(result["result_count"], 0)

    async def test_original_search_fields_and_new_filters(self):
        status, result = await http_get(self.app, "/medications/search", {
            "query": "ABIP", "strength": "15mg", "form": "comprimé", "presentation": "20",
        })
        self.assertEqual(status, 200)
        self.assertTrue({"query", "result_count", "medications", "catalog_scope"} <= result.keys())
        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["medications"][0]["ppv_price_mad"], 268.0)

    async def test_invalid_queries_return_422_instead_of_500(self):
        for parameters in ({}, {"query": ""}, {"query": "   "}, {"query": "x" * 201},
                           {"query": "\u0301"}, {"query": "ABIP", "strength": "  "}):
            status, _ = await http_get(self.app, "/medications/search", parameters)
            self.assertEqual(status, 422)

    async def test_lookup_and_partial_catalogue_404(self):
        status, medication = await http_get(self.app, "/medications/9079")
        self.assertEqual(status, 200)
        self.assertEqual(medication["brand_name"], "ABIP")
        self.assertEqual(medication["ppv_price_mad"], 268.0)
        status, error = await http_get(self.app, "/medications/999999999")
        self.assertEqual(status, 404)
        self.assertIn("partial catalogue", error["detail"])

    async def test_fuzzy_api_response_requires_review(self):
        status, result = await http_get(self.app, "/medications/search", {"query": "ABPI"})
        self.assertEqual(status, 200)
        self.assertEqual(result["medications"], [])
        self.assertEqual(result["status"], "suggestions")
        self.assertTrue(result["suggestions"])


if __name__ == "__main__":
    unittest.main()
