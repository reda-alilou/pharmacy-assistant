import unittest
from pharmacy_core.medications.pricing import parse_quantity

class QuantityParserTests(unittest.TestCase):

    def test_reviewed_number_words_digits_and_duals_in_four_language_groups(self):
        for text, count in (('une boîte', 1), ('deux boîtes', 2), ('trois présentations', 3), ('dix-sept boîtes', 17), ('2 boîtes', 2), ('٢ علب', 2), ('۲ عبوات', 2), ('علبتين', 2), ('علبتان', 2), ('ثلاث علب', 3), ('علبة واحدة', 1), ('جوج علب', 2), ('jouj l3lab', 2), ('jooj boites', 2), ('wa7ed lboita', 1), ('tlata dyal l3lab', 3), ('جوج ديال العلب', 2), ('1000 présentations', 1000), ('2flacons', 2), ('قارورتين', 2), ('trois tubes', 3)):
            with self.subTest(text=text):
                self.assertEqual(parse_quantity(text)[0], count)

    def test_unclear_fractional_negative_range_or_physical_units_never_become_packages(self):
        for text in (None, '', 'deux', '2', '0 boîtes', '-2 boîtes', '1.5 boîtes', '2,0 boîtes', 'une demi boîte', '2 ou 3 boîtes', 'deux à trois boîtes', '2 boîtes de 30', 'boîte de 30', '30 comprimés', '2 doses', '200 ml', '15 mg', 'deux fois par jour', '1001 boîtes', '3lab', 'plusieurs boîtes', 'deux boîtes et trois boîtes'):
            with self.subTest(text=text):
                self.assertIsNone(parse_quantity(text))
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.medications.pricing import apply_pricing
from pharmacy_core.medications.matching import resolve
from tests.support.chat import mention, response

class PricingGroundingTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()

    def result(self, name='AIRCORT', **slots):
        return resolve(self.catalog, mention(name, **slots), 0)

    def test_box_size_is_not_purchase_quantity_and_missing_quantity_stays_unknown(self):
        result = self.result('ABIP', presentation='boîte de 30')
        total = apply_pricing([result])
        self.assertEqual(result.medication.source_record_id, '9080')
        self.assertEqual(result.pricing.status, 'not_requested')
        self.assertIsNone(result.pricing.presentation_count)
        self.assertIsNone(total.total_price_mad)

    def test_real_prices_and_presentation_identity_determine_the_total(self):
        for presentation, expected in (('boîte de 20', '536.00'), ('boîte de 30', '744.00')):
            result = self.result('ABIP', quantity='deux boîtes', presentation=presentation)
            total = apply_pricing([result])
            self.assertEqual(result.pricing.total_price_mad, expected)
            self.assertEqual(total.total_price_mad, expected)
            self.assertEqual(result.pricing.basis, 'per_catalogue_presentation')

    def test_money_uses_decimal_cents_and_changed_source_price(self):
        result = self.result(quantity='trois boîtes')
        result.medication = result.medication.model_copy(update={'ppv_price_mad': 0.29})
        apply_pricing([result])
        self.assertEqual(result.pricing.total_price_mad, '0.87')
        result.medication = result.medication.model_copy(update={'ppv_price_mad': 123.45})
        apply_pricing([result])
        self.assertEqual(result.pricing.total_price_mad, '370.35')
        result.medication = result.medication.model_copy(update={'ppv_price_mad': 1.005})
        apply_pricing([result])
        self.assertEqual(result.pricing.unit_price_mad, '1.01')
        self.assertEqual(result.pricing.total_price_mad, '3.03')
        from pharmacy_core.conversation.answers import render_answer
        answer = render_answer(response().interpretation, [result], None)
        self.assertIn('Prix public enregistré: 1.01 MAD', answer)

    def test_missing_price_never_becomes_zero_but_stored_zero_is_preserved(self):
        result = self.result(quantity='deux boîtes')
        result.medication = result.medication.model_copy(update={'ppv_price_mad': None})
        self.assertEqual(apply_pricing([result]).status, 'incomplete')
        self.assertEqual(result.pricing.status, 'price_unavailable')
        self.assertIsNone(result.pricing.total_price_mad)
        result.medication = result.medication.model_copy(update={'ppv_price_mad': 0.0})
        self.assertEqual(apply_pricing([result]).total_price_mad, '0.00')

    def test_spelling_and_presentation_ambiguity_prevent_totals(self):
        for name in ('ABIP', 'airkort', 'XYZZZ999999'):
            result = self.result(name, quantity='deux boîtes')
            apply_pricing([result])
            self.assertEqual(result.pricing.status, 'awaiting_medication')
            self.assertIsNone(result.pricing.total_price_mad)

    def test_specific_containers_must_be_the_selected_retail_presentation(self):
        result = self.result(quantity='deux flacons')
        apply_pricing([result])
        self.assertEqual(result.pricing.total_price_mad, '166.00')
        for packaging in ('BOITE DE 2 FLACONS DE 50ML', "BOITE D'UN FLACON", '2 FLACONS', 'FLACONS DE 50ML'):
            result.medication = result.medication.model_copy(update={'presentation': packaging})
            apply_pricing([result])
            self.assertEqual(result.pricing.status, 'needs_quantity_clarification')
            self.assertEqual(result.pricing.clarification_reason, 'container_mismatch')
        result = self.result('ABIP', presentation='boîte de 30', quantity='deux flacons')
        apply_pricing([result])
        self.assertIsNone(result.pricing.total_price_mad)

    def test_multimedication_order_has_no_partial_or_implicit_quantity_total(self):
        first = self.result('ABIP', presentation='boîte de 20', quantity='une boîte')
        second = self.result(quantity='deux boîtes')
        second.mention_index = 1
        self.assertEqual(apply_pricing([first, second]).total_price_mad, '434.00')
        second.mention.quantity = None
        self.assertEqual(apply_pricing([first, second]).status, 'incomplete')
        self.assertIsNone(apply_pricing([first, second]).total_price_mad)
        second.mention.quantity = 'deux boîtes'
        second.medication = None
        self.assertEqual(apply_pricing([first, second]).status, 'incomplete')
from unittest.mock import AsyncMock
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest
from pharmacy_core.pharmacies.directory import PharmacyDirectory

class PricingChatTests(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()

    def service(self, *values):
        interpreter = AsyncMock()
        interpreter.interpret.side_effect = list(values)
        return ChatService(self.catalog, interpreter, self.directory)

    async def test_ambiguous_abip_selection_calculates_without_another_model_call(self):
        service = self.service(response([mention('ABIP', quantity='deux boîtes')]))
        initial = await service.respond(ChatRequest(text='Prix deux boîtes ABIP'))
        self.assertIsNone(initial.order_pricing.total_price_mad)
        selected = await service.respond(ChatRequest(continuation_id=initial.continuation_id, selections=[{'mention_index': 0, 'record_id': '9080'}]))
        self.assertIn('2 × 372.00 MAD = 744.00 MAD', selected.answer)
        self.assertEqual(selected.order_pricing.total_price_mad, '744.00')
        self.assertFalse(selected.inference_performed)
        service.interpreter.interpret.assert_awaited_once()

    async def test_quantity_followups_replace_previous_quantity_and_keep_presentation(self):
        service = self.service(response([mention('ABIP', presentation='boîte de 30')]), response([mention(None, quantity='deux boîtes')]), response([mention(None, quantity='trois boîtes')]))
        initial = await service.respond(ChatRequest(text='Prix ABIP boîte de 30'))
        two = await service.respond(ChatRequest(text='Et deux boîtes?', session_id=initial.session_id))
        three = await service.respond(ChatRequest(text='Et trois boîtes?', session_id=two.session_id))
        self.assertEqual(two.order_pricing.total_price_mad, '744.00')
        self.assertEqual(three.order_pricing.total_price_mad, '1116.00')
        self.assertIsNone(two.interpretation.entities.medications[0].name)
        self.assertEqual(three.medications[0].medication.source_record_id, '9080')

    async def test_unclear_quantity_asks_for_packages_then_a_clear_followup_works(self):
        service = self.service(response([mention('ABIP', presentation='boîte de 30', quantity='30 comprimés')]), response([mention(None, quantity='deux boîtes')]))
        unclear = await service.respond(ChatRequest(text='30 comprimés ABIP boîte de 30'))
        self.assertEqual(unclear.status, 'needs_clarification')
        self.assertEqual(unclear.medications[0].pricing.status, 'needs_quantity_clarification')
        self.assertIsNone(unclear.order_pricing.total_price_mad)
        self.assertIn('Combien', unclear.answer)
        clear = await service.respond(ChatRequest(text='deux boîtes', session_id=unclear.session_id))
        self.assertEqual(clear.order_pricing.total_price_mad, '744.00')

    async def test_multilingual_answers_have_identical_math_and_keep_stock_unknown(self):
        for language, script, quantity in (('fr', 'latin', 'deux boîtes'), ('ar', 'arabic', 'علبتين'), ('darija', 'latin', 'jouj l3lab'), ('darija', 'arabic', 'جوج علب')):
            service = self.service(response([mention('ABIP', presentation='boîte de 30', quantity=quantity)], intents=['price', 'availability'], language=language, script=script))
            result = await service.respond(ChatRequest(text='synthetic multilingual example'))
            self.assertIn('2 × 372.00 MAD = 744.00 MAD', result.answer)
            self.assertEqual(result.medications[0].stock_status, 'unknown')

    async def test_source_conflicts_keep_official_price_in_arithmetic(self):
        record = self.catalog.get('2128')
        service = self.service(response([mention(record.brand_name, strength=record.dosage, presentation=record.presentation, quantity='deux boîtes')]))
        result = await service.respond(ChatRequest(text='source-conflict fixture'))
        self.assertEqual(result.order_pricing.total_price_mad, '329.00')
        self.assertNotIn('369.00 MAD', result.answer)
        self.assertTrue(result.medications[0].medication.data_conflicts)
