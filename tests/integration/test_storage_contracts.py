import ast
import unittest
from pharmacy_core.storage.postgres.catalogue import alias_rows, amount
from pharmacy_infrastructure.paths import ROOT

class StorageValueTests(unittest.TestCase):

    def test_frozen_initial_migrations_match_the_relational_models(self):
        from sqlalchemy.schema import CreateTable, CreateIndex
        from sqlalchemy.dialects.postgresql import dialect
        from pharmacy_core.storage.postgres.models import metadata as core
        from pharmacy_language.storage.postgres.models import metadata as language
        for schema, metadata in (('core', core), ('language', language)):
            path = ROOT / 'services' / schema / 'migrations/versions/0001_initial.py'
            tree = ast.parse(path.read_text(encoding='utf-8'))
            stored = next((ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any((isinstance(target, ast.Name) and target.id == 'STATEMENTS' for target in node.targets))))
            generated = []
            for table in metadata.sorted_tables:
                generated.append(str(CreateTable(table).compile(dialect=dialect())))
                generated.extend((str(CreateIndex(index).compile(dialect=dialect())) for index in sorted(table.indexes, key=lambda row: row.name)))
            self.assertEqual([' '.join(s.split()) for s in stored], [' '.join(s.split()) for s in generated])

    def test_prices_preserve_missing_zero_and_exact_precision(self):
        self.assertIsNone(amount(None))
        self.assertEqual(str(amount(0)), '0')
        self.assertEqual(str(amount(18.3)), '18.3')
        for value in (True, -1, '1.001', 'NaN', 'Infinity', '10000000000'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                amount(value)

    def test_alias_spellings_and_confirmation_policies_remain_distinct(self):
        rows = alias_rows()
        self.assertEqual(len(rows), 22)
        self.assertEqual(len({r['normalized_key'] for r in rows}), 17)
        self.assertTrue(next((r for r in rows if r['spelling'] == 'airkort'))['requires_confirmation'])
        self.assertFalse(next((r for r in rows if r['target'] == 'VENTOLINE'))['requires_confirmation'])
import json
from unittest.mock import AsyncMock
from pydantic import ValidationError
from pharmacy_core.medications.catalog import MedicationCatalog
from pharmacy_core.conversation.service import ChatService
from pharmacy_core.conversation.models import ChatRequest
from pharmacy_core.pharmacies.directory import PharmacyDirectory
from pharmacy_core.storage.postgres.conversations import public_payload
from pharmacy_core.storage.postgres.state_codec import encode_choice, decode_choice, encode_state, decode_state
from tests.support.chat import mention, response

class StateCodecTests(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalog = MedicationCatalog.from_path()
        cls.directory = PharmacyDirectory.from_path()

    async def test_json_round_trip_restores_clarification_then_pricing_context(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response()
        service = ChatService(self.catalog, interpreter, self.directory)
        initial = await service.respond(ChatRequest(text='Prix ABIP?'))
        choice_json = json.loads(json.dumps(encode_choice(service.pending[initial.continuation_id])))
        snapshot_json = json.loads(json.dumps(encode_state(service.sessions[initial.session_id])))
        restarted = ChatService(self.catalog, interpreter, self.directory)
        restarted.pending[initial.continuation_id] = decode_choice(choice_json)
        restarted.sessions[initial.session_id] = decode_state(snapshot_json)
        selected = await restarted.respond(ChatRequest(continuation_id=initial.continuation_id, selections=[{'mention_index': 0, 'record_id': '9080'}]))
        self.assertFalse(selected.inference_performed)
        self.assertEqual(selected.medications[0].medication.source_record_id, '9080')
        interpreter.interpret.assert_awaited_once()
        stored = json.loads(json.dumps(encode_state(restarted.sessions[selected.session_id])))
        next_service = ChatService(self.catalog, interpreter, self.directory)
        next_service.sessions[selected.session_id] = decode_state(stored)
        interpreter.interpret.return_value = response([mention(None, quantity='deux boîtes')])
        final = await next_service.respond(ChatRequest(text='Et pour deux boîtes?', session_id=selected.session_id))
        self.assertEqual(final.order_pricing.total_price_mad, '744.00')

    async def test_transcript_payload_does_not_persist_bearer_tokens(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response()
        service = ChatService(self.catalog, interpreter, self.directory)
        initial = await service.respond(ChatRequest(text='Prix ABIP?'))
        stored = json.dumps(public_payload(initial))
        self.assertNotIn(initial.session_id, stored)
        self.assertNotIn(initial.continuation_id, stored)
        self.assertIn('AMMPS', stored)

    def test_unrecognized_snapshot_version_is_rejected(self):
        with self.assertRaises(ValidationError):
            decode_state({'version': 2})
        with self.assertRaises(ValidationError):
            decode_choice({'version': 2})
