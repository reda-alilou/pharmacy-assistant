"""Identity aliases retain filters; package follow-ups retain the real session."""

import unittest
from unittest.mock import AsyncMock

from pharmacy_assistant.catalog import MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.resolution import resolve
from pharmacy_assistant.pricing import parse_quantity
from pharmacy_assistant.evaluate_baseline import score_outcome
from pharmacy_assistant.evaluation_dataset import EvaluationExample
from pharmacy_assistant.config import ROOT
import json
from test_chat import mention, response


class AliasRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.catalog = MedicationCatalog.from_path()

    def test_arabic_brand_variants_diacritics_and_units_preserve_raw_mentions(self):
        for name in ('فنتولين', 'فينتولين', 'ڤنتولين', 'ڤينتولين', 'فِينْتُولِين'):
            with self.subTest(name=name):
                raw=mention(name,strength='١٠٠ ميكروغرام / جرعة')
                result=resolve(self.catalog,raw,0)
                self.assertEqual(result.medication.source_record_id,'1972')
                self.assertEqual(result.mention,raw)
                self.assertEqual(result.name_alias,'VENTOLINE')
        for name in ('أوغمنتين','أوجمنتين','اوجمنتين','أُوغْمَنْتِين'):
            for count,identifier in (('12','1790'),('16','1791'),('24','1792')):
                raw=mention(name,strength='1 g / 125 mg',presentation='علبة '+count)
                self.assertEqual(resolve(self.catalog,raw,0).medication.source_record_id,identifier)

    def test_alias_alone_does_not_pick_a_strength_or_presentation(self):
        for name,expected in (('فنتولين',{'1971','1972','1973','1974','1975'}),('أوجمنتين',{'1790','1791','1792'})):
            result=resolve(self.catalog,mention(name),0)
            self.assertEqual(result.status,'ambiguous')
            self.assertIsNone(result.medication)
            self.assertEqual({r.source_record_id for r in result.candidates},expected)

    def test_alias_does_not_relax_wrong_filters_or_accept_nearby_spellings(self):
        for fields in ({'strength':'2 g / 125 mg'},{'presentation':'علبة 240'},{'form':'sirop'}):
            result=resolve(self.catalog,mention('أوغمنتين',**fields),0)
            self.assertEqual(result.status,'filters_not_matched')
            self.assertIsNone(result.medication)
        for name in ('أوغمنتين فورت','أوجمنتيني','Ventolinne'):
            self.assertIsNone(resolve(self.catalog,mention(name),0).medication)

    def test_arabic_indefinite_singular_is_explicit_but_missing_or_definite_quantities_are_not_one(self):
        self.assertEqual(parse_quantity('علبة'),(1,'package'))
        self.assertEqual(parse_quantity('قنينة'),(1,'flacon'))
        for raw in (None,'lboita','la boîte','العلبة','علب','boîtes'):
            self.assertIsNone(parse_quantity(raw))


class PackageSessionTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=MedicationCatalog.from_path();cls.directory=PharmacyDirectory.from_path()

    async def test_package_selection_then_requested_quantity_remain_separate(self):
        for brand,package,form,identifier,total in (
            ('VENTOLINE','lboita dyal 40','l9ras','1974','37.40'),
            ('ABIP','lboita dyal 20','l9ras','9079','536.00'),
            ('ABIP','30','comprimés','9080','744.00')):
            interpreter=AsyncMock()
            interpreter.interpret.side_effect=[response([mention(brand)]),
                response([mention(None,form=form,presentation=package)],intents=['medication_information']),
                response([mention(None,quantity='deux boîtes')])]
            service=ChatService(self.catalog,interpreter,self.directory)
            initial=await service.respond(ChatRequest(text='Prix '+brand+' ?'))
            selected=await service.respond(ChatRequest(text=package+' '+form,session_id=initial.session_id))
            self.assertEqual(selected.medications[0].medication.source_record_id,identifier)
            self.assertEqual(selected.context.effective_interpretation.intents,['price'])
            self.assertIsNone(selected.interpretation.entities.medications[0].strength)
            self.assertIsNone(selected.interpretation.entities.medications[0].quantity)
            result=await service.respond(ChatRequest(text='Et deux boîtes ?',session_id=selected.session_id))
            self.assertEqual(result.medications[0].medication.source_record_id,identifier)
            self.assertEqual(result.order_pricing.total_price_mad,total)

    async def test_explicit_unitless_or_wrong_strength_is_not_silently_replaced_by_box_size(self):
        interpreter=AsyncMock()
        interpreter.interpret.side_effect=[response([mention('VENTOLINE')]),
            response([mention(None,strength='40')],intents=['medication_information'])]
        service=ChatService(self.catalog,interpreter,self.directory)
        initial=await service.respond(ChatRequest(text='Prix VENTOLINE ?'))
        result=await service.respond(ChatRequest(text='dosage 40',session_id=initial.session_id))
        self.assertIsNone(result.medications[0].medication)
        self.assertEqual(result.medications[0].status,'filters_not_matched')
        self.assertEqual(result.medications[0].mention.strength,'40')

    async def test_arabic_and_latin_name_identity_share_only_confirmed_record(self):
        interpreter=AsyncMock()
        interpreter.interpret.side_effect=[response([mention('فنتولين',strength='2mg',presentation='boîte de 40')]),
            response([mention('VENTOLINE',quantity='deux boîtes')])]
        service=ChatService(self.catalog,interpreter,self.directory)
        initial=await service.respond(ChatRequest(text='فنتولين 2mg boîte de 40'))
        result=await service.respond(ChatRequest(text='Deux boîtes VENTOLINE',session_id=initial.session_id))
        self.assertEqual(result.medications[0].medication.source_record_id,'1974')
        self.assertEqual(result.order_pricing.total_price_mad,'37.40')

    async def test_definite_container_reference_is_corrected_only_in_effective_followup(self):
        for quantity in ('lboita','l3elba','la boîte','le flacon','العلبة','القارورة','القنينة'):
            interpreter=AsyncMock()
            interpreter.interpret.side_effect=[response([mention('VENTOLINE')]),
                response([mention(None,quantity=quantity,presentation='40')],intents=['medication_request'])]
            service=ChatService(self.catalog,interpreter,self.directory)
            initial=await service.respond(ChatRequest(text='Prix VENTOLINE ?'))
            result=await service.respond(ChatRequest(text=quantity+' 40',session_id=initial.session_id))
            self.assertEqual(result.status,'answered')
            self.assertEqual(result.medications[0].medication.source_record_id,'1974')
            self.assertEqual(result.interpretation.entities.medications[0].quantity,quantity)
            self.assertEqual(result.interpretation.intents,['medication_request'])
            self.assertIsNone(result.context.effective_interpretation.entities.medications[0].quantity)
            self.assertEqual(result.context.effective_interpretation.intents,['price'])
            self.assertEqual(result.context.normalized_fields,['medications.0.quantity','intents'])
            self.assertEqual(result.medications[0].pricing.status,'not_requested')

    async def test_explicit_purchase_counts_and_ambiguous_counts_are_never_dropped(self):
        for quantity in ('deux boîtes','une boîte','علبة','plusieurs boîtes'):
            interpreter=AsyncMock()
            interpreter.interpret.side_effect=[response([mention('VENTOLINE')]),
                response([mention(None,quantity=quantity,presentation='40')],intents=['medication_request'])]
            service=ChatService(self.catalog,interpreter,self.directory)
            initial=await service.respond(ChatRequest(text='Prix VENTOLINE ?'))
            result=await service.respond(ChatRequest(text=quantity+' de 40',session_id=initial.session_id))
            self.assertEqual(result.context.effective_interpretation.entities.medications[0].quantity,quantity)
            self.assertFalse(result.context.normalized_fields)
            self.assertEqual(result.status,'needs_clarification' if quantity=='plusieurs boîtes' else 'answered')

    async def test_outcome_metric_rejects_unnecessary_quantity_clarification(self):
        data=json.loads((ROOT/'data/evaluation/matching_regressions_v1.json').read_text(encoding='utf-8'))
        case=EvaluationExample.model_validate(next(c for c in data if c['id']=='fresh-fr-diacritics'))
        interpreter=AsyncMock()
        interpreter.interpret.return_value=response([mention('VENTOLINE',strength='2 mg',presentation='boîte de 40',quantity='lboita')])
        service=ChatService(self.catalog,interpreter,self.directory)
        result=await service.respond(ChatRequest(text='VENTOLINE 2 mg boîte de 40 lboita'))
        self.assertEqual(result.status,'needs_clarification')
        self.assertEqual(result.medications[0].medication.source_record_id,'1974')
        self.assertIn('unexpected_clarification',[f['code'] for f in score_outcome(result,case,self.catalog)['failures']])


if __name__ == '__main__': unittest.main()
