import unittest
from unittest.mock import AsyncMock
from pharmacy_core.conversation.errors import ChatError
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest
from pharmacy_evaluation.runners.baseline import AnnotationInterpreter, score_outcome
from pharmacy_evaluation.datasets.baseline import load_examples
from pharmacy_contracts.interpretation import InferenceError
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from tests.support.chat import mention, response

class ConversationTests(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()

    def service(self, *interpretations, **kwargs):
        interpreter = AsyncMock()
        interpreter.interpret.side_effect = list(interpretations)
        return ChatService(self.catalog, interpreter, self.directory, **kwargs)

    async def test_all_eight_development_contexts_resolve_identity_and_requested_totals(self):
        cases = [c for c in load_examples('development') if c.kind == 'conversation_turn']
        self.assertEqual(len(cases), 8)
        for case in cases:
            with self.subTest(case=case.id):
                service = ChatService(self.catalog, AnnotationInterpreter(case), self.directory)
                token = None
                for previous in case.context:
                    initial = await service.respond(ChatRequest(text=previous.text, session_id=token))
                    token = initial.session_id
                result = await service.respond(ChatRequest(text=case.text, session_id=token))
                result.interpretation.validate_evidence(case.text)
                self.assertIsNone(result.interpretation.entities.medications[0].name)
                self.assertEqual(result.medications[0].medication.source_record_id, case.expected.medications[0].record_ids[0])
                self.assertIn('medications.0.name', result.context.inherited_fields)
                checks = score_outcome(result, case, self.catalog)
                self.assertTrue(all((d['passed'] for d in checks['medication_decisions'])))
                self.assertFalse(checks['failures'])

    async def test_without_session_the_same_fragment_remains_incomplete(self):
        fragment = response([mention(None, presentation='boîte de 30')])
        service = self.service(response([mention('ABIP')]), response([mention('AIRCORT')]), fragment, fragment, response([], intents=['availability']))
        first = await service.respond(ChatRequest(text='Prix ABIP?'))
        second = await service.respond(ChatRequest(text='Prix AIRCORT?'))
        result = await service.respond(ChatRequest(text='La boîte de 30'))
        self.assertEqual(result.medications[0].status, 'missing_name')
        self.assertFalse(result.context.inherited_fields)
        abip = await service.respond(ChatRequest(text='La boîte de 30', session_id=first.session_id))
        aircort = await service.respond(ChatRequest(text='Disponible?', session_id=second.session_id))
        self.assertEqual(abip.medications[0].medication.source_record_id, '9080')
        self.assertEqual(aircort.medications[0].medication.source_record_id, '771')

    async def test_confirmed_choice_survives_quantity_and_availability_followups(self):
        service = self.service(response([mention('ABIP')]), response([mention(None, quantity='deux boîtes')]), response([], intents=['availability']))
        initial = await service.respond(ChatRequest(text='Prix ABIP?'))
        selected = await service.respond(ChatRequest(continuation_id=initial.continuation_id, selections=[{'mention_index': 0, 'record_id': '9080'}]))
        quantity = await service.respond(ChatRequest(text='Et deux boîtes?', session_id=selected.session_id))
        self.assertEqual(quantity.medications[0].medication.source_record_id, '9080')
        self.assertEqual(quantity.medications[0].mention.quantity, 'deux boîtes')
        available = await service.respond(ChatRequest(text='Disponible?', session_id=quantity.session_id))
        self.assertEqual(available.medications[0].medication.source_record_id, '9080')
        self.assertEqual(available.medications[0].stock_status, 'unknown')
        self.assertEqual(service.interpreter.interpret.await_count, 3)

    async def test_new_product_does_not_inherit_filters_quantity_or_previous_identity(self):
        service = self.service(response([mention('ABIP', strength='15mg', presentation='boîte de 30', quantity='deux')]), response([mention('AIRCORT')]))
        initial = await service.respond(ChatRequest(text='ABIP 15mg boîte de 30 deux'))
        result = await service.respond(ChatRequest(text='Et AIRCORT?', session_id=initial.session_id))
        self.assertEqual(result.medications[0].medication.source_record_id, '771')
        self.assertEqual(result.medications[0].mention, mention('AIRCORT'))
        self.assertFalse(result.context.inherited_fields)

    async def test_strength_form_and_presentation_changes_do_not_reuse_old_selection(self):
        for fragment in (mention(None, strength='5mg'), mention(None, form='sirop'), mention(None, presentation='boîte de 20')):
            service = self.service(response([mention('ABIP', strength='15mg', presentation='boîte de 30')]), response([fragment]))
            initial = await service.respond(ChatRequest(text='ABIP 15mg boîte de 30'))
            result = await service.respond(ChatRequest(text='Correction', session_id=initial.session_id))
            if fragment.presentation:
                self.assertEqual(result.medications[0].medication.source_record_id, '9079')
            else:
                self.assertIsNone(result.medications[0].medication)
                self.assertEqual(result.medications[0].status, 'filters_not_matched')
                self.assertIsNone(result.medications[0].mention.presentation)
                if fragment.form:
                    self.assertIsNone(result.medications[0].mention.strength)

    async def test_ambiguous_reference_needs_choice_and_choice_uses_no_inference(self):
        service = self.service(response([mention('ABIP'), mention('AIRCORT')]), response([mention(None, quantity='deux boîtes')]))
        initial = await service.respond(ChatRequest(text='Prix ABIP et AIRCORT'))
        fragment = await service.respond(ChatRequest(text='Et deux boîtes?', session_id=initial.session_id))
        self.assertTrue(fragment.context.needs_reference)
        self.assertEqual(fragment.status, 'needs_clarification')
        self.assertFalse(fragment.medications)
        self.assertFalse(fragment.sources)
        self.assertNotIn('83.00', fragment.answer)
        self.assertEqual(len(fragment.context.reference_options), 2)
        with self.assertRaises(ChatError):
            await service.respond(ChatRequest(session_id=fragment.session_id, reference_index=2))
        selected = await service.respond(ChatRequest(session_id=fragment.session_id, reference_index=1))
        self.assertEqual(selected.medications[0].medication.source_record_id, '771')
        self.assertEqual(selected.medications[0].mention.quantity, 'deux boîtes')
        self.assertIsNone(selected.interpretation.entities.medications[0].name)
        self.assertFalse(selected.inference_performed)
        self.assertEqual(service.interpreter.interpret.await_count, 2)

    async def test_named_followup_targets_only_matching_previous_medication(self):
        service = self.service(response([mention('ABIP', strength='15mg', presentation='boîte de 30'), mention('AIRCORT')]), response([mention('ABIP', quantity='deux boîtes')]))
        initial = await service.respond(ChatRequest(text='ABIP 15mg boîte de 30 et AIRCORT'))
        result = await service.respond(ChatRequest(text='Deux boîtes ABIP', session_id=initial.session_id))
        self.assertEqual(len(result.medications), 1)
        self.assertEqual(result.medications[0].medication.source_record_id, '9080')

    async def test_ordinal_selection_and_multimedication_ambiguity(self):
        for phrase in ('La deuxième, merci.', 'الثانية', 'taniya 3afak'):
            service = self.service(response([mention('ABIP')]), response([], intents=['unsupported']))
            initial = await service.respond(ChatRequest(text='Prix ABIP?'))
            expected = initial.medications[0].candidates[1].source_record_id
            result = await service.respond(ChatRequest(text=phrase, session_id=initial.session_id))
            self.assertEqual(result.medications[0].medication.source_record_id, expected)
            self.assertEqual(result.context.action, 'ordinal_selection')
        service = self.service(response([mention('ABIP'), mention('AIRCORT')]), response([], intents=['unsupported']))
        initial = await service.respond(ChatRequest(text='Prix ABIP et AIRCORT'))
        result = await service.respond(ChatRequest(text='La deuxième', session_id=initial.session_id))
        self.assertTrue(result.context.needs_reference)
        self.assertFalse(result.medications)

    async def test_fuzzy_identity_stays_unconfirmed_after_typed_filter(self):
        service = self.service(response([mention('airkort')]), response([mention(None, form='inhalation')]))
        initial = await service.respond(ChatRequest(text='Prix airkort?'))
        result = await service.respond(ChatRequest(text='inhalation', session_id=initial.session_id))
        self.assertEqual(result.medications[0].status, 'suggestions')
        self.assertIsNone(result.medications[0].medication)

    async def test_explicit_correction_is_remembered_instead_of_rejected_strength(self):
        service = self.service(response([mention('ABIP', strength='5mg')]), response([], intents=['price']))
        initial = await service.respond(ChatRequest(text='Prix ABIP 5mg'))
        selected = await service.respond(ChatRequest(continuation_id=initial.continuation_id, selections=[{'mention_index': 0, 'record_id': '9080'}]))
        result = await service.respond(ChatRequest(text='Et le prix?', session_id=selected.session_id))
        self.assertEqual(result.medications[0].medication.source_record_id, '9080')
        self.assertEqual(result.context.effective_interpretation.entities.medications[0].strength, '15 MG')

    async def test_unsupported_and_topic_switches_drop_old_medication(self):
        service = self.service(response([mention('AIRCORT')]), response([], intents=['unsupported']), response([], intents=['price']))
        initial = await service.respond(ChatRequest(text='Prix AIRCORT'))
        clinical = await service.respond(ChatRequest(text='Quel traitement pour ma douleur?', session_id=initial.session_id))
        self.assertFalse(clinical.medications)
        self.assertFalse(clinical.sources)
        result = await service.respond(ChatRequest(text='Et le prix?', session_id=clinical.session_id))
        self.assertFalse(result.medications)
        self.assertFalse(result.context.inherited_fields)

    async def test_pharmacy_context_and_city_switch_do_not_leak_filters(self):
        service = self.service(response([], intents=['pharmacy_search'], city='Rabat', pharmacy='Ibn Nafis', area='Agdal'), response([], intents=['pharmacy_contact']), response([], intents=['pharmacy_search'], city='Casablanca'))
        initial = await service.respond(ChatRequest(text='Pharmacie Ibn Nafis Agdal Rabat'))
        contact = await service.respond(ChatRequest(text='Et le téléphone?', session_id=initial.session_id))
        self.assertEqual(contact.context.effective_interpretation.entities.pharmacy, 'Ibn Nafis')
        self.assertIsNone(contact.interpretation.entities.pharmacy)
        changed = await service.respond(ChatRequest(text='Et à Casablanca?', session_id=contact.session_id))
        self.assertEqual(changed.pharmacy.status, 'outside_coverage')
        self.assertIsNone(changed.context.effective_interpretation.entities.pharmacy)
        self.assertIsNone(changed.context.effective_interpretation.entities.area)

    async def test_provider_failure_leaves_original_session_usable(self):
        service = self.service(response([mention('ABIP')]), InferenceError('provider_timeout', 'timeout', 504, True), response([mention(None, presentation='boîte de 30')]))
        initial = await service.respond(ChatRequest(text='Prix ABIP'))
        with self.assertRaises(InferenceError):
            await service.respond(ChatRequest(text='La boîte de 30', session_id=initial.session_id))
        result = await service.respond(ChatRequest(text='La boîte de 30', session_id=initial.session_id))
        self.assertEqual(result.medications[0].medication.source_record_id, '9080')

    async def test_long_source_packaging_never_breaks_session_creation_or_pinning(self):
        record = next((r for r in self.catalog.records if len(r.presentation) > 200))
        service = self.service(response([mention(record.brand_name)]), response([], intents=['price']))
        initial = await service.respond(ChatRequest(text=record.brand_name))
        if initial.medications[0].status != 'resolved':
            snapshot = service.sessions[initial.session_id]
            from pharmacy_core.conversation.models import MedicationResult
            from pharmacy_core.conversation.state import anchors_for
            snapshot.results = [MedicationResult(mention_index=0, mention=mention(record.brand_name), status='resolved', medication=record)]
            snapshot.anchors = anchors_for(snapshot.results)
        final = await service.respond(ChatRequest(text='Et le prix?', session_id=initial.session_id))
        self.assertEqual(final.medications[0].medication.source_record_id, record.source_record_id)
        self.assertEqual(final.medications[0].medication.presentation, record.presentation)

    async def test_fragment_information_intent_inherits_previous_price_intent(self):
        service = self.service(response([mention('ABIP')]), response([mention(None, presentation='boîte de 30')], intents=['medication_information']))
        initial = await service.respond(ChatRequest(text='Prix ABIP'))
        final = await service.respond(ChatRequest(text='La boîte de 30', session_id=initial.session_id))
        self.assertEqual(final.interpretation.intents, ['medication_information'])
        self.assertEqual(final.context.effective_interpretation.intents, ['price'])
        self.assertIn('intents', final.context.inherited_fields)
        self.assertEqual(final.medications[0].medication.source_record_id, '9080')
