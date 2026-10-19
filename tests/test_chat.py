"""Step 3 checks: real retrieval and API, mocked inference, no network."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from pharmacy_assistant.api import create_app
from pharmacy_assistant.catalog import MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.config import Settings
from pharmacy_assistant.nlu_models import InterpretationResponse, MedicationMention
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.resolution import resolve, strength_key


def mention(name="ABIP", **kwargs):
    return MedicationMention(name=name, strength=kwargs.get("strength"), quantity=kwargs.get("quantity"),
                             form=kwargs.get("form"), presentation=kwargs.get("presentation"))


def response(medications=None, intents=None, language="fr", script="latin", **context):
    return InterpretationResponse.model_validate({
        "interpretation": {
            "language": language, "reply_language": language, "reply_script": script,
            "intents": intents or ["price"],
            "entities": {"medications": [m.model_dump() for m in (medications if medications is not None else [mention()])],
                         **{key: context.get(key) for key in ("pharmacy", "city", "area", "date", "time", "symptom")}},
        },
        "metadata": {"requested_model": "offline", "model": "offline", "prompt_version": "test",
                     "latency_ms": 1, "attempts": 1, "completion_id": None,
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
    })


class ResolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()

    def test_exact_brand_excludes_substring_collision_and_keeps_presentations(self):
        result = resolve(self.catalog, mention(), 0)
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual({r.source_record_id for r in result.candidates}, {"9079", "9080"})
        self.assertEqual({r.ppv_price_mad for r in result.candidates}, {268, 372})
        self.assertTrue(all(r.brand_name == "ABIP" for r in result.candidates))

    def test_strength_form_and_package_are_independent_and_quantity_is_not_package(self):
        result = resolve(self.catalog, mention(strength="15mg", form="comprimés", presentation="boîte de 20"), 0)
        self.assertEqual(result.medication.source_record_id, "9079")
        self.assertEqual(resolve(self.catalog, mention(quantity="20 boîtes"), 0).status, "ambiguous")
        for fields in ({"strength": "5mg"}, {"strength": "15"}, {"form": "sirop"}, {"presentation": "200"}):
            self.assertEqual(resolve(self.catalog, mention(**fields), 0).status, "filters_not_matched")

    def test_arabic_alias_units_and_form(self):
        result = resolve(self.catalog, mention("أبيب", strength="١٥ ملغ", form="أقراص", presentation="علبة ٢٠"), 0)
        self.assertEqual(result.medication.source_record_id, "9079")
        self.assertEqual(strength_key("1 g"), strength_key("1000 mg"))
        self.assertEqual(strength_key("250 µg / dose"), strength_key("250 mcg / dose"))
        self.assertNotEqual(strength_key("5mg"), strength_key("15mg"))

    def test_fuzzy_and_partial_names_never_resolve_automatically(self):
        for name in ("AIRCOR", "AIRCORTT"):
            result = resolve(self.catalog, mention(name), 0)
            self.assertEqual(result.status, "suggestions")
            self.assertIsNone(result.medication)
            self.assertIn("AIRCORT", [r.brand_name for r in result.candidates])

    def test_unknown_missing_and_large_substance_ambiguity(self):
        self.assertEqual(resolve(self.catalog, mention("XYZZZ999999"), 0).status, "not_found")
        self.assertEqual(resolve(self.catalog, mention(None), 0).status, "missing_name")
        result = resolve(self.catalog, mention("PARACETAMOL"), 0)
        self.assertEqual(result.status, "ambiguous")
        self.assertTrue(result.candidates_truncated)
        self.assertLessEqual(len(result.candidates), 5)
        self.assertEqual(result.clarification.kind, "refine_search")
        self.assertEqual(result.clarification.field, "strength")
        self.assertGreater(result.candidate_count, 20)


class ChatServiceTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()

    def service(self, result, **options):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = result
        return ChatService(self.catalog, interpreter, self.directory, **options)

    async def test_selection_uses_only_offered_records_without_new_inference(self):
        service = self.service(response())
        initial = await service.respond(ChatRequest(text="Prix ABIP?"))
        self.assertEqual(initial.status, "needs_clarification")
        selected = await service.respond(ChatRequest(continuation_id=initial.continuation_id,
                                                    selections=[{"mention_index": 0, "record_id": "9080"}]))
        self.assertEqual(selected.status, "answered")
        self.assertFalse(selected.inference_performed)
        self.assertIn("372.00 MAD", selected.answer)
        self.assertIsNone(selected.continuation_id)
        service.interpreter.interpret.assert_awaited_once()
        for selection in ({"mention_index": 0, "record_id": "771"}, {"mention_index": 9, "record_id": "9080"}):
            with self.assertRaises(HTTPException) as caught:
                await service.respond(ChatRequest(continuation_id=initial.continuation_id, selections=[selection]))
            self.assertEqual(caught.exception.status_code, 422)

    async def test_selections_are_bound_to_each_mention_and_partial_selection_is_supported(self):
        service = self.service(response([mention(), mention("DOLIPRANE")]))
        initial = await service.respond(ChatRequest(text="ABIP et DOLIPRANE"))
        doliprane_id = initial.medications[1].candidates[0].source_record_id
        with self.assertRaises(HTTPException):
            await service.respond(ChatRequest(continuation_id=initial.continuation_id,
                                              selections=[{"mention_index": 0, "record_id": doliprane_id}]))
        partial = await service.respond(ChatRequest(continuation_id=initial.continuation_id,
                                                   selections=[{"mention_index": 0, "record_id": "9079"}]))
        self.assertEqual(partial.medications[0].status, "resolved")
        self.assertTrue(partial.continuation_id)
        final = await service.respond(ChatRequest(continuation_id=partial.continuation_id,
                                                 selections=[{"mention_index": 1, "record_id": doliprane_id}]))
        self.assertEqual(final.status, "answered")
        self.assertEqual(final.medications[0].medication.source_record_id, "9079")

    async def test_expired_unknown_and_evicted_continuations(self):
        service = self.service(response(), capacity=1)
        first = await service.respond(ChatRequest(text="ABIP"))
        second = await service.respond(ChatRequest(text="ABIP"))
        for token in (first.continuation_id, "x" * 32):
            with self.assertRaises(HTTPException) as caught:
                await service.respond(ChatRequest(continuation_id=token, selections=[{"mention_index": 0, "record_id": "9079"}]))
            self.assertEqual(caught.exception.status_code, 410)
        service.pending[second.continuation_id].expires = 0
        with self.assertRaises(HTTPException):
            await service.respond(ChatRequest(continuation_id=second.continuation_id,
                                              selections=[{"mention_index": 0, "record_id": "9079"}]))
        self.assertEqual(len(service.pending), 0)

    async def test_record_facts_missing_price_stock_and_sources(self):
        for language, script in (("fr", "latin"), ("ar", "arabic"), ("darija", "latin"), ("darija", "arabic")):
            service = self.service(response([mention("AIRCORT", quantity="deux boîtes")],
                                            ["price", "availability", "medication_information"], language, script))
            result = await service.respond(ChatRequest(text="AIRCORT"))
            self.assertIn("83.00 MAD", result.answer)
            self.assertIn(result.medications[0].medication.active_substance, result.answer)
            self.assertEqual(result.medications[0].stock_status, "unknown")
            self.assertEqual(result.sources[0].source, "AMMPS")
            self.assertIn("771", result.sources[0].record_ids)
        service = self.service(response([mention("18F PSMA RIM", presentation="BOITE D'UN FLACON MONODOSE DE 15 ML")]))
        result = await service.respond(ChatRequest(text="18F PSMA RIM"))
        self.assertIsNone(result.medications[0].medication.ppv_price_mad)
        self.assertIn("non renseigné", result.answer)
        self.assertNotIn("0.00 MAD", result.answer)

    async def test_source_conflicts_do_not_replace_official_prices(self):
        record = self.catalog.get("2128")
        service = self.service(response([mention(record.brand_name, strength=record.dosage, presentation=record.presentation)]))
        result = await service.respond(ChatRequest(text=record.brand_name))
        self.assertIn("164.50 MAD", result.answer)
        self.assertNotIn("184.50 MAD", result.answer)
        self.assertIn("divergent", result.answer)
        self.assertTrue(result.medications[0].medication.data_conflicts)
        self.assertIn("saydalia.ma", {s.source for s in result.sources})

    async def test_answer_follows_retrieved_values_instead_of_fixed_example_prices(self):
        service = self.service(response([mention("AIRCORT")]))
        changed = self.catalog.get("771").model_copy(update={"ppv_price_mad": 123.45})
        service.catalog = MedicationCatalog([changed], "synthetic-price-test")
        result = await service.respond(ChatRequest(text="Prix AIRCORT?"))
        self.assertIn("123.45 MAD", result.answer)
        self.assertNotIn("83.00 MAD", result.answer)

    async def test_unknown_incomplete_and_unsupported_requests(self):
        for data, phrase in ((response([]), "Quel médicament"),
                             (response([mention("XYZZZ999999")]), "catalogue partiel"),
                             (response([], ["unsupported"]), "ni diagnostic")):
            result = await self.service(data).respond(ChatRequest(text="test"))
            self.assertIn(phrase, result.answer)
            self.assertEqual(result.sources, [])

    async def test_unsupported_named_medication_does_not_trigger_unrequested_lookup(self):
        service = self.service(response([mention("ABIP")], ["unsupported"], symptom="douleur"))
        result = await service.respond(ChatRequest(text="ABIP pour ma douleur?"))
        self.assertEqual(result.status, "answered")
        self.assertEqual(result.medications, [])
        self.assertIsNone(result.continuation_id)
        self.assertIn("ni diagnostic", result.answer)
        self.assertEqual(result.interpretation.entities.medications[0].name, "ABIP")

    async def test_rabat_contacts_area_and_unverified_hours_duty(self):
        service = self.service(response([], ["pharmacy_search", "pharmacy_on_duty", "opening_hours"], city="الرباط"))
        result = await service.respond(ChatRequest(text="صيدلية الحراسة بالرباط"))
        self.assertEqual(result.pharmacy.result_count, len(self.directory.records))
        self.assertEqual(result.pharmacy.duty_status, "unverified")
        self.assertEqual(result.pharmacy.opening_hours_status, "unknown")
        self.assertIn("ne désignent pas", result.answer)
        self.assertTrue(all(r.phone in result.answer for r in result.pharmacy.pharmacies))
        service = self.service(response([], ["pharmacy_contact"], pharmacy="Pharmacie Ibn Nafis", city="Rabat"))
        exact = await service.respond(ChatRequest(text="Pharmacie Ibn Nafis Rabat"))
        self.assertEqual(exact.pharmacy.result_count, 1)
        self.assertIn("0537720657", exact.answer)
        service = self.service(response([], ["pharmacy_search"], area="اكدال"))
        area = await service.respond(ChatRequest(text="اكدال"))
        self.assertTrue(area.pharmacy.city_defaulted)
        self.assertGreater(area.pharmacy.result_count, 0)

    async def test_outside_coverage_and_missing_pharmacy_have_no_fallback_results(self):
        for context, status in (({"city": "Casablanca"}, "outside_coverage"),
                                ({"city": "Rabat", "pharmacy": "XYZZZ999999"}, "not_found"),
                                ({"city": "Rabat", "area": "XYZZZ999999"}, "not_found")):
            service = self.service(response([], ["pharmacy_search"], **context))
            result = await service.respond(ChatRequest(text="test"))
            self.assertEqual(result.pharmacy.status, status)
            self.assertEqual(result.pharmacy.pharmacies, [])


class ChatApiTests(unittest.TestCase):
    def test_http_clarification_serialization_and_selection_validation(self):
        fake = AsyncMock()
        fake.interpret.return_value = response()
        with patch("pharmacy_assistant.api.create_interpreter", return_value=fake):
            with TestClient(create_app(settings=Settings())) as client:
                initial = client.post("/chat", json={"text": "Prix ABIP?"})
                self.assertEqual(initial.status_code, 200)
                body = initial.json()
                self.assertEqual(body["status"], "needs_clarification")
                invalid = client.post("/chat", json={"continuation_id": body["continuation_id"],
                                                    "selections": [{"mention_index": 0, "record_id": "771"}]})
                self.assertEqual(invalid.status_code, 422)
                selected = client.post("/chat", json={"continuation_id": body["continuation_id"],
                                                     "selections": [{"mention_index": 0, "record_id": "9079"}]})
                self.assertEqual(selected.status_code, 200)
                self.assertIn("268.00 MAD", selected.json()["answer"])
                self.assertFalse(selected.json()["inference_performed"])
                for payload in ({}, {"text": " "}, {"text": "x", "selections": [{"mention_index": 0, "record_id": "9079"}]},
                                {"continuation_id": "x" * 32}, {"text": "x", "continuation_id": "x" * 32},
                                {"text": "x", "unexpected": True}):
                    self.assertEqual(client.post("/chat", json=payload).status_code, 422)
                fake.interpret.assert_awaited_once()

    def test_provider_error_is_visible_and_lookup_still_works(self):
        with TestClient(create_app(settings=Settings())) as client:
            failed = client.post("/chat", json={"text": "Prix ABIP?"})
            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed.json()["detail"]["code"], "model_not_configured")
            self.assertEqual(client.get("/medications/9079").status_code, 200)


if __name__ == "__main__":
    unittest.main()
