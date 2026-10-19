"""Development-only matching, safe recovery and functional refinement checks."""

import asyncio
from pathlib import Path
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from pharmacy_assistant.api import create_app
from pharmacy_assistant.catalog import MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.demo_client import DemoClient
from pharmacy_assistant.medication_normalization import CONFIRMATION_ALIASES, NAME_ALIASES, form_matches, presentation_matches, strength_key
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.resolution import resolve
from test_chat import mention, response
import test_demo


class NormalizationTests(unittest.TestCase):
    def test_explicit_unit_equivalence_and_ordered_combination_strengths(self):
        for first, second in (("٠٫٥ غرام", "500 mg"), ("250 µg / dose", "0.25 mg/dose"),
                              ("25mg/5ml", "5 mg / ml"), ("1g/0.1l", "10mg/ml"),
                              ("1g/125mg", "1000mg/125mg"), ("250 ميكروغرام / جرعة", "250ug/dose")):
            self.assertEqual(strength_key(first), strength_key(second), (first, second))
        for first, second in (("15", "15mg"), ("5mg", "15mg"), ("1g/125mg", "8mg/1mg"),
                              ("100mg/5ml", "100mg/ml"), ("5ug", "5mg"), ("1mg+2mg", "2mg+1mg")):
            self.assertNotEqual(strength_key(first), strength_key(second), (first, second))

    def test_form_synonyms_keep_qualifiers_and_negative_words_significant(self):
        self.assertTrue(form_matches("SUSPENSION POUR INHALATION", "الاستنشاق"))
        self.assertTrue(form_matches("COMPRIMES PELLICULES", "أقراص"))
        self.assertTrue(form_matches("COMPRIME EFFERVESCENT", "comprimés effervescents"))
        self.assertTrue(form_matches("INHALATION", "l'inhalation"))
        self.assertFalse(form_matches("COMPRIME SECABLE", "comprimé effervescent"))
        self.assertFalse(form_matches("COMPRIME EFFERVESCENT", "comprimé non effervescent"))
        self.assertFalse(form_matches("COMPRIME", "sirop"))
        self.assertFalse(form_matches("COMPRIME", "?"))

    def test_packaging_numbers_volumes_container_and_form_are_not_conflated(self):
        self.assertTrue(presentation_matches("FLACON DE 100ML", "flacon de 0,1 l"))
        self.assertTrue(presentation_matches("BOITE DE 30", "lboita dyal ٣٠"))
        self.assertTrue(presentation_matches("BOITE DE 20", "20 أقراص", "COMPRIME"))
        self.assertFalse(presentation_matches("BOITE DE 200", "boîte de 20"))
        self.assertFalse(presentation_matches("FLACON DE 20 ML", "flacon de 20 g"))
        self.assertFalse(presentation_matches("FLACON DE 20 ML", "boîte de 20 ml"))
        self.assertFalse(presentation_matches("BOITE DE 20", "20 gélules", "COMPRIME"))
        self.assertFalse(presentation_matches("BOITE DE 2 FLACONS DE 50ML", "flacon de 50 ml"))
        self.assertFalse(presentation_matches("FLACON MULTIDOSE DE 15ML", "flacon monodose 15ml"))
        self.assertFalse(presentation_matches("BOITE DE 20", "?"))


class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = MedicationCatalog.from_path()

    def test_reviewed_alias_targets_exist_in_the_real_catalogue(self):
        from pharmacy_assistant.catalog import normalize
        for target in {*NAME_ALIASES.values(), *CONFIRMATION_ALIASES.values()}:
            self.assertTrue(any((field, normalize(target)) in self.catalog.name_index
                                for field in ("brand_name", "active_substance")), target)

    def test_arabic_substance_and_form_are_matched_without_rewriting_raw_mentions(self):
        raw = mention("أموكسيسيلين")
        result = resolve(self.catalog, raw, 0)
        self.assertEqual(result.status, "ambiguous")
        self.assertEqual(result.mention.name, "أموكسيسيلين")
        self.assertEqual(result.name_alias, "AMOXICILLINE")
        self.assertEqual(result.candidate_count, 148)
        self.assertEqual(result.clarification.field, "strength")
        self.assertTrue(all(r.active_substance == "AMOXICILLINE" for r in result.candidates))
        inhaler = resolve(self.catalog, mention("AIRCORT", form="الاستنشاق"), 0)
        self.assertEqual(inhaler.medication.source_record_id, "771")

    def test_known_brand_wrong_strength_never_auto_selects_and_retains_choices(self):
        result = resolve(self.catalog, mention("ABIP", strength="5mg"), 0)
        self.assertEqual(result.status, "filters_not_matched")
        self.assertIsNone(result.medication)
        self.assertEqual({r.source_record_id for r in result.candidates}, {"9079", "9080"})
        self.assertEqual(result.conflicting_filters, ["strength"])
        self.assertEqual(result.clarification.kind, "correct_filters")
        self.assertEqual({v.value for v in result.clarification.options}, {"15 MG"})
        self.assertEqual(result.mention.strength, "5mg")

    def test_arabizi_partial_and_fuzzy_proposals_require_record_confirmation(self):
        for name in ("airkort", "AIRCOR", "AIRCORTT"):
            result = resolve(self.catalog, mention(name), 0)
            self.assertEqual(result.status, "suggestions")
            self.assertIsNone(result.medication)
            self.assertEqual(result.candidates[0].source_record_id, "771")

    def test_fuzzy_ranking_survives_sorting_and_brand_collisions_stay_separate(self):
        original = self.catalog.get("771")
        catalog = MedicationCatalog([
            original.model_copy(update={"source_record_id": "1", "brand_name": "AIRCORT"}),
            original.model_copy(update={"source_record_id": "2", "brand_name": "AIRCORA"}),
        ], "ranking-fixture")
        result = resolve(catalog, mention("AIRCORTT"), 0)
        self.assertEqual(result.candidates[0].brand_name, "AIRCORT")
        self.assertEqual({r.brand_name for r in resolve(self.catalog, mention("ABIP"), 0).candidates}, {"ABIP"})


class RefinementTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()

    def service(self, mentions):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response(mentions)
        return ChatService(self.catalog, interpreter, self.directory)

    async def test_narrowing_large_substance_search_preserves_scope_without_new_inference(self):
        service = self.service([mention("أموكسيسيلين")])
        result = await service.respond(ChatRequest(text="معلومات أموكسيسيلين"))
        target = self.catalog.get("3842")
        seen_counts = []
        from pharmacy_assistant.resolution import field_key, field_value
        while result.medications[0].candidate_count > 5:
            med = result.medications[0]
            question = med.clarification
            option = next(o for o in question.options if field_key(o.value, question.field) ==
                          field_key(field_value(target, question.field), question.field))
            seen_counts.append(med.candidate_count)
            result = await service.respond(ChatRequest(continuation_id=result.continuation_id,
                refinements=[{"mention_index": 0, "field": question.field, "value": option.value}]))
            self.assertFalse(result.inference_performed)
            if result.medications[0].status == "resolved": break
        med = result.medications[0]
        if med.status != "resolved":
            self.assertIn("3842", {r.source_record_id for r in med.candidates})
            result = await service.respond(ChatRequest(continuation_id=result.continuation_id,
                selections=[{"mention_index": 0, "record_id": "3842"}]))
        self.assertEqual(result.medications[0].medication.source_record_id, "3842")
        self.assertEqual(result.interpretation.entities.medications[0].name, "أموكسيسيلين")
        self.assertTrue(all(a > b for a, b in zip(seen_counts, seen_counts[1:])))
        service.interpreter.interpret.assert_awaited_once()

    async def test_explicit_strength_correction_preserves_original_extraction_and_prices(self):
        service = self.service([mention("ABIP", strength="5mg")])
        initial = await service.respond(ChatRequest(text="Prix ABIP 5mg"))
        corrected = await service.respond(ChatRequest(continuation_id=initial.continuation_id,
            refinements=[{"mention_index": 0, "field": "strength", "value": "15 MG"}]))
        self.assertEqual(corrected.medications[0].status, "ambiguous")
        self.assertEqual(corrected.interpretation.entities.medications[0].strength, "5mg")
        final = await service.respond(ChatRequest(continuation_id=corrected.continuation_id,
            selections=[{"mention_index": 0, "record_id": "9080"}]))
        self.assertIn("372.00 MAD", final.answer)
        self.assertEqual(final.medications[0].applied_refinements, {"strength": "15 MG"})
        self.assertEqual(final.medications[0].conflicting_filters, ["strength"])
        self.assertIn("Vous avez confirmé", final.answer)
        self.assertFalse(final.inference_performed)
        service.interpreter.interpret.assert_awaited_once()

    async def test_unoffered_fields_values_and_cross_mention_choices_are_rejected(self):
        service = self.service([mention("AMOXICILLINE"), mention("ABIP")])
        initial = await service.respond(ChatRequest(text="AMOXICILLINE et ABIP"))
        for refinement in ({"mention_index": 0, "field": "strength", "value": "9999 MG"},
                           {"mention_index": 0, "field": "brand_name", "value": "ABIP"},
                           {"mention_index": 1, "field": "strength", "value": "1 G"},
                           {"mention_index": 9, "field": "strength", "value": "1 G"}):
            with self.assertRaises(HTTPException) as caught:
                await service.respond(ChatRequest(continuation_id=initial.continuation_id, refinements=[refinement]))
            self.assertEqual(caught.exception.status_code, 422)
        hidden = next(identifier for identifier in service.pending[initial.continuation_id].resolution_states[0].candidate_ids
                      if identifier not in {r.source_record_id for r in initial.medications[0].candidates})
        with self.assertRaises(HTTPException):
            await service.respond(ChatRequest(continuation_id=initial.continuation_id,
                selections=[{"mention_index": 0, "record_id": hidden}]))
        service.interpreter.interpret.assert_awaited_once()

    async def test_next_page_is_validated_and_only_offered_records_can_be_selected(self):
        service = self.service([mention("PAGINGTEST")])
        record = self.catalog.get("771")
        service.catalog = MedicationCatalog([record.model_copy(update={"source_record_id": str(100 + i),
            "brand_name": "PAGINGTEST"}) for i in range(8)], "paging-fixture")
        initial = await service.respond(ChatRequest(text="PAGINGTEST"))
        self.assertEqual(len(initial.medications[0].candidates), 5)
        with self.assertRaises(HTTPException):
            await service.respond(ChatRequest(continuation_id=initial.continuation_id,
                refinements=[{"mention_index": 0, "field": "page", "value": "6"}]))
        page = await service.respond(ChatRequest(continuation_id=initial.continuation_id,
            refinements=[{"mention_index": 0, "field": "page", "value": "5"}]))
        self.assertEqual(len(page.medications[0].candidates), 3)
        self.assertIsNone(page.medications[0].next_candidate_offset)
        selected = await service.respond(ChatRequest(continuation_id=page.continuation_id,
            selections=[{"mention_index": 0, "record_id": page.medications[0].candidates[0].source_record_id}]))
        self.assertEqual(selected.status, "answered")
        service.interpreter.interpret.assert_awaited_once()


class RefinementApiAndUiTests(unittest.TestCase):
    def test_http_refinement_validation_and_existing_presentation_selection(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response([mention("ABIP", strength="5mg")])
        with patch("pharmacy_assistant.api.create_interpreter", return_value=interpreter), \
             TestClient(create_app(settings=Settings())) as client:
            initial = client.post("/chat", json={"text": "ABIP 5mg"}).json()
            token = initial["continuation_id"]
            self.assertEqual(client.post("/chat", json={"continuation_id": token,
                "refinements": [{"mention_index": 0, "field": "quantity", "value": "2"}]}).status_code, 422)
            self.assertEqual(client.post("/chat", json={"continuation_id": token,
                "refinements": [{"mention_index": 0, "field": "strength", "value": "5 MG"}]}).status_code, 422)
            corrected = client.post("/chat", json={"continuation_id": token,
                "refinements": [{"mention_index": 0, "field": "strength", "value": "15 MG"}]})
            self.assertEqual(corrected.status_code, 200)
            final = client.post("/chat", json={"continuation_id": corrected.json()["continuation_id"],
                "selections": [{"mention_index": 0, "record_id": "9079"}]}).json()
            self.assertIn("268.00 MAD", final["answer"])
        interpreter.interpret.assert_awaited_once()

    def test_streamlit_refinement_menu_sends_the_real_continuation_payload(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response([mention("PARACETAMOL")])
        service = ChatService(MedicationCatalog.from_path(), interpreter, PharmacyDirectory.from_path())
        initial = asyncio.run(service.respond(ChatRequest(text="Prix PARACETAMOL?")))
        option = initial.medications[0].clarification.options[0].value
        narrowed = asyncio.run(service.respond(ChatRequest(continuation_id=initial.continuation_id,
            refinements=[{"mention_index": 0, "field": "strength", "value": option}])))
        test_demo.StreamlitTests.setUpClass()
        with patch.object(DemoClient, "health", return_value=test_demo.StreamlitTests.health), \
             patch.object(DemoClient, "chat", side_effect=[initial, narrowed]) as chat:
            app = AppTest.from_file(str(ROOT / "src/pharmacy_assistant/demo.py"), default_timeout=15).run()
            app.chat_input[0].set_value("Prix PARACETAMOL?").run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.selectbox), 1)
            self.assertFalse(any("BOITE DE" in button.label for button in app.button))
            app.selectbox[0].select(option).run()
            next(button for button in app.button if button.label == "Affiner").click().run()
            self.assertFalse(app.exception)
            self.assertEqual(chat.call_args.args[0], {"continuation_id": initial.continuation_id,
                "refinements": [{"mention_index": 0, "field": "strength", "value": option}]})
            self.assertEqual(chat.call_count, 2)
        interpreter.interpret.assert_awaited_once()


if __name__ == "__main__": unittest.main()
