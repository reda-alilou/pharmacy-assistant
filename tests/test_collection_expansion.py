"""Collection contracts: pagination, interruption, provenance and honest coverage."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from pharmacy_assistant.collection_http import CollectionBudgetReached, SourceClient, atomic_replace
from pharmacy_assistant.expand_medications import (
    collect as collect_medications, medicament_listing, saydalia_page_count,
)
from pharmacy_assistant.expand_pharmacies import (
    collect as collect_pharmacies, directory_quality, grid_points, phone_key, refinement_origins,
)
from pharmacy_assistant.review_collection_expansion import pharmacy_audit, ROOT
from pharmacy_assistant.run_collection_expansion import review_ready


def listing(identifier, page_count=2):
    return (f'<article class="w-grid-item product" data-id="{identifier}">'
            f'<div class="post_title"><a href="https://saydalia.ma/fr/produit/item-{identifier}/">'
            'TEST 10 MG, Comprimé</a></div></article>'
            f'<a class="page-numbers" href="https://saydalia.ma/fr/medicaments/page/{page_count}/">'
            f'{page_count}</a>')


def response(body, url, status=200):
    from requests import Response
    result = Response()
    result.status_code, result.url = status, url
    result._content = body.encode("utf-8")
    result.encoding = "utf-8"
    return result


class MedicationExpansionTests(unittest.TestCase):
    def test_pipeline_never_marks_partial_or_failed_audit_ready(self):
        good = {"all_collections_finished": True, "offline_integrity_passed": True,
                "pharmacies": {"retrieval_checks": [{"passed": True}]}}
        self.assertTrue(review_ready(good, {"medicament": 0, "saydalia": 0, "rabat": 0}, 0))
        self.assertFalse(review_ready(good, {"medicament": 2}, 0))
        self.assertFalse(review_ready(good, {"medicament": 0}, 1))
        self.assertFalse(review_ready({**good, "all_collections_finished": False}, {"medicament": 0}, 0))
        self.assertFalse(review_ready({**good, "offline_integrity_passed": False}, {"medicament": 0}, 0))
        self.assertFalse(review_ready({**good, "pharmacies": {"retrieval_checks": [{"passed": False}]}},
                                      {"medicament": 0}, 0))

    def test_windows_checkpoint_rename_retries_and_preserves_previous_file_on_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            old, new = directory / "old.json", directory / "new.tmp"
            old.write_text("old")
            new.write_text("new")
            locked = PermissionError("sharing violation")
            locked.winerror = 32
            replace = Path.replace
            calls = []
            def temporarily_locked(path, target):
                calls.append(1)
                if len(calls) < 3:
                    raise locked
                return replace(path, target)
            with patch.object(Path, "replace", temporarily_locked):
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    atomic_replace(new, old)
            self.assertEqual(old.read_text(), "new")
            new.write_text("later")
            with patch.object(Path, "replace", side_effect=locked) as rename:
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    with self.assertRaises(PermissionError):
                        atomic_replace(new, old)
            self.assertEqual(rename.call_count, 12)
            self.assertEqual(old.read_text(), "new")
            self.assertEqual(new.read_text(), "later")

    def test_all_letters_discovery_resumes_before_details_and_ignores_stale_sitemap_urls(self):
        def get(_, url, **kwargs):
            if url.endswith("/wp-sitemap.xml"):
                body = '<sitemapindex><sitemap><loc>https://medicament.ma/wp-sitemap-posts-medicament-1.xml</loc></sitemap></sitemapindex>'
            elif url.endswith(".xml"):
                body = '<urlset><url><loc>https://medicament.ma/medicament/stale/</loc></url></urlset>'
            elif "/listing-des-medicaments/" in url:
                letter = parse_qs(urlparse(url).query)["lettre"][0]
                body = ('<h3>1 résultat</h3><li class="listing-item"><a href="https://medicament.ma/medicament/'
                        + letter.lower() + '/">Item</a></li>') if letter in "AB" else '<h3>0 résultats</h3>'
            else:
                self.assertNotIn("stale", url)
                body = ('<h1 class="main-title">TEST 10 MG, Comprimé</h1><div class="medicine-details">'
                        '<div class="detail-item"><div class="detail-header">Dosage</div>'
                        '<div class="detail-content">10 MG</div></div></div>')
            return response(body, url)
        with tempfile.TemporaryDirectory() as temporary:
            with patch("requests.Session.get", autospec=True, side_effect=get) as request:
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    first = collect_medications("medicament", Path(temporary), max_requests=28)
                    self.assertTrue(first["discovery_complete"])
                    self.assertFalse(first["collection_complete"])
                    self.assertEqual(len(first["listing_letters"]), 26)
                    final = collect_medications("medicament", Path(temporary), max_requests=2)
                    self.assertTrue(final["collection_complete"])
                    self.assertTrue(final["advertised_counts_reconciled"])
                    self.assertEqual(final["record_count"], 2)
                    self.assertEqual(request.call_count, 30)
                    replay = collect_medications("medicament", Path(temporary), max_requests=0)
                    self.assertTrue(replay["collection_complete"])
                    self.assertEqual(request.call_count, 30)

    def test_page_discovery_is_not_capped_at_old_sample(self):
        self.assertEqual(saydalia_page_count(listing("1", 442)), 442)
        with self.assertRaises(ValueError):
            saydalia_page_count("<h1>Service unavailable</h1>")
        with self.assertRaises(ValueError):
            saydalia_page_count(listing("1").replace("https://saydalia.ma/fr/medicaments/page/2/",
                                                   "https://other.example/fr/medicaments/page/2/"))

    def test_zero_letter_and_duplicate_listing_links(self):
        self.assertEqual(medicament_listing("<h3>0 résultats</h3>", ""), ([], 0))
        card = ('<li class="listing-item"><a href="https://medicament.ma/medicament/test/">'
                'Test</a></li>')
        with self.assertRaises(ValueError):
            medicament_listing("<h3>2 résultats</h3>" + card * 2, "")

    def test_budget_resume_preserves_stage_and_reuses_verified_cache(self):
        def get(_session, url, **kwargs):
            return response(listing("2" if "/page/2/" in url else "1"), url)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with patch("requests.Session.get", autospec=True, side_effect=get) as request:
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    first = collect_medications("saydalia", directory, max_requests=1)
                    self.assertFalse(first["collection_complete"])
                    self.assertEqual(first["record_count"], 1)
                    zero = collect_medications("saydalia", directory, max_requests=0)
                    self.assertEqual(zero["record_count"], 1)
                    final = collect_medications("saydalia", directory, max_requests=1)
                    self.assertTrue(final["collection_complete"])
                    self.assertEqual(final["record_count"], 2)
                    self.assertEqual(request.call_count, 2)
                    replay = collect_medications("saydalia", directory, max_requests=0)
                    self.assertTrue(replay["collection_complete"])
                    self.assertEqual(request.call_count, 2)
            self.assertFalse((directory / "processed").exists())

    def test_repeated_listing_page_is_coverage_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch("requests.Session.get", autospec=True,
                       side_effect=lambda _, url, **kw: response(listing("1"), url)):
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    state = collect_medications("saydalia", Path(temporary))
        self.assertFalse(state["collection_complete"])
        self.assertEqual(state["record_count"], 1)
        self.assertEqual(len(state["errors"]), 1)

    def test_provider_rejection_stops_without_serializing_error_secrets(self):
        def get(_, url, **kwargs):
            return response(listing("1"), url) if "/page/2/" not in url else response(
                "blocked", url + "?api_key=DO_NOT_STORE", 403)
        with tempfile.TemporaryDirectory() as temporary:
            with patch("requests.Session.get", autospec=True, side_effect=get):
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    state = collect_medications("saydalia", Path(temporary))
        self.assertEqual(state["stop_reason"], "source_rejected_requests")
        self.assertNotIn("DO_NOT_STORE", json.dumps(state))

    def test_retry_attempts_count_against_budget(self):
        with tempfile.TemporaryDirectory() as temporary:
            with SourceClient("https://example.com", Path(temporary), max_requests=1) as client:
                with patch.object(client.session, "get", return_value=response("retry", "https://example.com/", 503)) as request:
                    with patch("pharmacy_assistant.collection_http.time.sleep"):
                        with self.assertRaises(CollectionBudgetReached):
                            client.get("https://example.com/", "first")
                self.assertEqual(request.call_count, 1)


class PharmacyExpansionTests(unittest.TestCase):
    def test_offline_retrieval_audit_uses_full_entity_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "pharmacies.jsonl").write_bytes(
                (ROOT / "data/processed/pharmacies_rabat.jsonl").read_bytes())
            (directory / "manifest.json").write_text(json.dumps({
                "configuration": {"bounds": [33.91, 34.06, -6.94, -6.77]}}))
            report = pharmacy_audit(directory)
            self.assertEqual(report["missing_baseline_ids"], [])
            self.assertTrue(report["ibn_nafis_phone_unchanged"])
            self.assertEqual(len(report["retrieval_checks"]), 8)
            self.assertTrue(all(check["passed"] for check in report["retrieval_checks"]))

    def test_grid_covers_bounds_and_phone_normalization_preserves_unknowns(self):
        points = grid_points([33.91, 34.06, -6.94, -6.77], 0.015)
        self.assertIn((33.91, -6.94), points)
        self.assertIn((34.06, -6.77), points)
        self.assertEqual(len(points), len(set(points)))
        self.assertEqual(phone_key("+212 537 72 06 57"), "0537720657")
        self.assertIsNone(phone_key("unknown"))
        self.assertEqual(len(refinement_origins((34.015, -6.835), 0.015,
                                              [33.91, 34.06, -6.94, -6.77])), 4)
        self.assertEqual(len(refinement_origins((34.03, -6.77), 0.015,
                                              [33.91, 34.06, -6.94, -6.77])), 2)
        with self.assertRaises(ValueError):
            grid_points([34, 33, -7, -6], 0.01)

    def test_generic_city_run_is_staged_capped_and_resumable(self):
        raw = [{"id": "1", "title": "Example", "Ville": "Other city", "Phone": "+212537000001",
                "address": "Source address", "lat": 34.0, "lng": -6.8, "garde": "yes"},
               {"id": "2", "title": "Neighbour", "Ville": "Rabat", "lat": 34.0, "lng": -6.8}]
        def get(_, url, **kwargs):
            body = ('<script>var nearestSaydaliaData = {"api_key":"PUBLIC_BROWSER_TOKEN"};</script>'
                    if url.endswith("/fr/") else json.dumps(raw))
            return response(body, url)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            config = directory / "cities.json"
            config.write_text(json.dumps({"other": {"city": "Other city", "bounds": [34, 34.01, -6.9, -6.89],
                "grid_step_degrees": 0.02, "requested_limit": 2, "observed_result_cap": 2}}))
            with patch("requests.Session.get", autospec=True, side_effect=get) as request:
                with patch("pharmacy_assistant.collection_http.time.sleep"):
                    first = collect_pharmacies("other", directory, config, max_requests=2)
                    self.assertEqual(first["record_count"], 1)
                    final = collect_pharmacies("other", directory, config)
                    self.assertTrue(final["collection_complete"])
                    self.assertEqual(final["search_points_completed"], 4)
                    self.assertEqual(final["possibly_truncated_points"], 4)
                    self.assertFalse(final["complete_city_directory"])
                    self.assertEqual(final["quality"]["records"], 1)
                    self.assertEqual(request.call_count, 5)
                    replay = collect_pharmacies("other", directory, config, max_requests=0)
                    self.assertTrue(replay["collection_complete"])
                    self.assertEqual(request.call_count, 5)
            self.assertNotIn("PUBLIC_BROWSER_TOKEN", json.dumps(final))
            duties = (directory / "other/duty_observations.jsonl").read_text()
            self.assertFalse(json.loads(duties)["duty_verified"])
            self.assertIsNone(json.loads(duties)["valid_until"])

    def test_duplicate_names_are_reviewed_not_automatically_merged(self):
        records = [{"pharmacy_id": str(i), "name": "Pharmacie Étoile", "phone": "0537000000",
                    "address": None} for i in range(2)]
        report = directory_quality(records)
        self.assertEqual(report["records"], 2)
        self.assertEqual(report["possible_duplicate_id_groups"], [["0", "1"]])


if __name__ == "__main__":
    unittest.main()
