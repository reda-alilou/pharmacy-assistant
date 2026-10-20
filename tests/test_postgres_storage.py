"""Opt-in real PostgreSQL checks, isolated from the application database.

Set PHARMACY_PG_TEST_ENV to the generated database env-file path. Tests create and
drop only a uniquely named pharmacy_checkpoint2_test_* database on that server.
They never start/stop PostgreSQL, call hosted inference, or change source files.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
import uuid

import groq
import httpx

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import Settings
from pharmacy_assistant.contracts.nlu_models import InferenceError
from pharmacy_assistant.core.chat import ChatService
from pharmacy_assistant.core.chat_models import ChatRequest
from pharmacy_assistant.core.errors import ChatError
from pharmacy_assistant.core.storage import models as m
from pharmacy_assistant.core.storage.catalogue import import_catalogue, load_catalogue
from pharmacy_assistant.core.storage.conversations import ConversationStore
from pharmacy_assistant.core.storage.state_codec import encode_state, encode_choice
from pharmacy_assistant.database import create_database_engine
from pharmacy_assistant.database_setup import configuration, grant, verify
from pharmacy_assistant.language.storage.quota import PostgresQuotaStore
from pharmacy_assistant.language.quota import QuotaStore
from pharmacy_assistant.paths import ROOT
from test_chat import response
from test_interpretation import completion, extraction
from service_harness import connected_apps
from pharmacy_assistant.config import LanguageSettings
from pharmacy_assistant.language.nlu import GroqInterpreter
from pharmacy_assistant.language.quota import AttemptControl


@unittest.skipUnless(os.environ.get("PHARMACY_PG_TEST_ENV"), "Real PostgreSQL not explicitly configured")
class PostgresStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.values = configuration(Path(os.environ["PHARMACY_PG_TEST_ENV"]))
        cls.name = "pharmacy_checkpoint2_test_" + uuid.uuid4().hex
        cls.admin = create_database_engine(make_url(cls.values["MIGRATION_DATABASE_URL"]).set(database="postgres").render_as_string(hide_password=False))
        cls.created = False
        cls.addClassCleanup(cls.drop_database)
        with cls.admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
            db.execute(text(f'CREATE DATABASE "{cls.name}"'))
        cls.created = True
        cls.values = {key: make_url(value).set(database=cls.name).render_as_string(hide_password=False)
                      if key.endswith("DATABASE_URL") else value for key, value in cls.values.items()}
        for schema in ("core", "language"):
            config = Config(str(ROOT / "alembic.ini"), ini_section=schema)
            config.attributes["database_url"] = cls.values["MIGRATION_DATABASE_URL"]
            command.upgrade(config, "head")
            command.upgrade(config, "head")  # Migrations themselves are repeatable.
        grant(cls.values)
        cls.engine = create_database_engine(cls.values["MIGRATION_DATABASE_URL"])
        cls.core = create_database_engine(cls.values["CORE_DATABASE_URL"])
        cls.language = create_database_engine(cls.values["LANGUAGE_DATABASE_URL"])
        cls.medications = ROOT / "data/processed/ammps_medications_enriched.jsonl"
        cls.pharmacies = ROOT / "data/processed/pharmacies_rabat.jsonl"
        cls.counts = import_catalogue(cls.engine, cls.medications, cls.pharmacies)
        cls.catalog, cls.directory = load_catalogue(cls.core)

    @classmethod
    def drop_database(cls):
        for name in ("engine", "core", "language"):
            engine = getattr(cls, name, None)
            if engine is not None:
                engine.dispose()
        if cls.created:
            assert cls.name.startswith("pharmacy_checkpoint2_test_") and cls.name.replace("_", "").isalnum()
            with cls.admin.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
                db.execute(text(f'DROP DATABASE "{cls.name}" WITH (FORCE)'))
        cls.admin.dispose()

    def test_full_round_trip_repeat_import_and_permissions(self):
        self.assertEqual(self.counts["presentations"], 9936)
        self.assertEqual(self.counts["medications"], 7302)
        self.assertEqual(self.counts["source_observations"], 3128)
        self.assertEqual(self.counts["data_conflicts"], 1260)
        self.assertTrue(import_catalogue(self.engine, self.medications, self.pharmacies)["repeated"])
        self.assertTrue(verify(self.values, self.medications, self.pharmacies)["cross_service_access_denied"])
        with self.core.connect() as db:
            missing = db.scalar(select(func.count()).select_from(m.presentation_prices).where(
                m.presentation_prices.c.kind == "ppv", m.presentation_prices.c.amount.is_(None)))
            self.assertEqual(missing, 1126)

    def test_backup_restore_preserves_facts_and_quotas_without_temporary_history(self):
        from pharmacy_assistant.database_backup import backup, verify_backup
        store = ConversationStore(self.core)
        view = store.create()
        store.begin(ChatRequest(text="Temporary transcript must stay out of backups", session_id=view["session_id"]))
        quota = PostgresQuotaStore(self.language)
        quota.reserve("backup-" + uuid.uuid4().hex, 0)
        quota.new_budget(uuid.uuid4().hex, uuid.uuid4().hex, 1)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "test.dump"
            self.assertTrue(backup(self.values, output)["temporary_conversations_excluded"])
            self.assertTrue(verify_backup(self.values, output)["restore_verified"])

    def test_foreign_keys_and_exact_price_constraints(self):
        with self.assertRaises(IntegrityError), self.core.begin() as db:
            db.execute(insert(m.presentation_prices).values(presentation_id="999999999", kind="ppv", amount=1))
        with self.assertRaises(IntegrityError), self.core.begin() as db:
            db.execute(update(m.presentation_prices).where(m.presentation_prices.c.presentation_id == "9080",
                m.presentation_prices.c.kind == "ppv").values(amount=-1))

    def test_conversation_api_restart_restore_idempotency_and_reset(self):
        fake = AsyncMock()
        fake.interpret.return_value = response()
        settings = Settings(storage_backend="postgres", core_database_url=self.values["CORE_DATABASE_URL"],
                            language_database_url=self.values["LANGUAGE_DATABASE_URL"])
        with patch("pharmacy_assistant.api.create_interpreter", return_value=fake):
            with TestClient(create_app(settings=settings)) as client:
                self.assertEqual(client.get("/health").json()["storage_backend"], "postgres")
                self.assertEqual(client.get("/ready").status_code, 200)
                self.assertEqual(client.get("/conversation").status_code, 401)
                initial = client.post("/conversation").json()
                payload = dict(text="Prix ABIP?", session_id=initial["session_id"], request_id=uuid.uuid4().hex)
                first = client.post("/chat", json=payload)
                self.assertEqual(first.status_code, 200, first.text)
                repeated = client.post("/chat", json=payload)
                self.assertEqual(repeated.status_code, 200, repeated.text)
                self.assertFalse(repeated.json()["inference_performed"])
                fake.interpret.assert_awaited_once()
                token = repeated.json()["session_id"]
        # A new app instance has no process-local conversation dictionaries.
        with patch("pharmacy_assistant.api.create_interpreter", return_value=fake):
            with TestClient(create_app(settings=settings)) as client:
                restored = client.get("/conversation", headers={"Authorization": f"Bearer {token}"})
                self.assertEqual(restored.status_code, 200, restored.text)
                self.assertEqual(len(restored.json()["messages"]), 2)
                choice = client.post("/chat", json={"continuation_id": restored.json()["response"]["continuation_id"],
                    "selections": [{"mention_index": 0, "record_id": "9080"}]})
                self.assertEqual(choice.status_code, 200, choice.text)
                self.assertEqual(choice.json()["medications"][0]["medication"]["source_record_id"], "9080")
                fake.interpret.assert_awaited_once()
                token = choice.json()["session_id"]
                self.assertEqual(client.delete("/conversation", headers={"Authorization": f"Bearer {token}"}).status_code, 204)
                self.assertEqual(client.get("/conversation", headers={"Authorization": f"Bearer {token}"}).status_code, 410)

    def test_http_extraction_outage_restore_choices_and_postgres_quotas(self):
        settings = Settings(storage_backend="postgres", core_database_url=self.values["CORE_DATABASE_URL"],
            language_database_url=self.values["LANGUAGE_DATABASE_URL"], inference_provider="groq",
            groq_api_key="offline-test-key", inference_quota_scope="http-" + uuid.uuid4().hex)
        calls, mode = [], ["ok"]
        def hosted(request):
            calls.append(request)
            if mode[0] == "quota":
                return httpx.Response(429, headers={"retry-after": "120"}, json={"error": {"message": "private-body"}})
            data = extraction()
            if mode[0] == "quantity":
                data["intents"] = ["price"]
                data["entities"]["medications"] = [{"name": None, "strength": None,
                    "quantity": "deux boîtes", "form": None, "presentation": None}]
            return httpx.Response(200, json=completion(data))
        language_settings = LanguageSettings.for_app(settings)
        control = AttemptControl.from_settings(language_settings)
        sdk = groq.AsyncGroq(api_key="offline-test-key", max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(hosted)))
        provider = GroqInterpreter(language_settings, client=sdk, control=control)
        transport_state = {"available": True}
        with connected_apps(settings, provider, transport_state) as client:
            self.assertEqual(client.get("/health").json()["language_service_status"], "available")
            initial = client.post("/conversation").json()
            first = client.post("/chat", json={"text": "Wach kayn ABIP 15mg w bch7al?",
                "session_id": initial["session_id"], "request_id": uuid.uuid4().hex})
            self.assertEqual(first.status_code, 200, first.text)
            body = first.json()
            transport_state["available"] = False
            failure = client.post("/chat", json={"text": "Et deux boîtes ?", "session_id": body["session_id"],
                "request_id": uuid.uuid4().hex})
            self.assertEqual(failure.status_code, 503, failure.text)
            self.assertEqual(failure.json()["detail"]["code"], "language_unavailable")
            restored = client.get("/conversation", headers={"Authorization": f"Bearer {body['session_id']}"}).json()
            self.assertEqual(restored["messages"][-1]["text"], "Et deux boîtes ?")
            self.assertEqual(restored["messages"][-1]["outcome"], "failed")
            selected = client.post("/chat", json={"continuation_id": restored["response"]["continuation_id"],
                "selections": [{"mention_index": 0, "record_id": "9080"}]})
            self.assertEqual(selected.status_code, 200, selected.text)
            self.assertIn("372.00 MAD", selected.json()["answer"])
            self.assertFalse(selected.json()["inference_performed"])
            self.assertEqual(len(calls), 1)
            transport_state["available"], mode[0] = True, "quantity"
            recovered = client.post("/chat", json={"text": "Et deux boîtes ?",
                "session_id": selected.json()["session_id"], "request_id": uuid.uuid4().hex})
            self.assertEqual(recovered.status_code, 200, recovered.text)
            self.assertIn("744.00 MAD", recovered.json()["answer"])
            mode[0] = "quota"
            for _ in range(2):
                limited = client.post("/interpret", json={"text": "ABIP"})
                self.assertEqual(limited.status_code, 429, limited.text)
                self.assertEqual(limited.json()["detail"]["code"], "provider_rate_limited")
                self.assertGreater(int(limited.headers["retry-after"]), 0)
            self.assertEqual(len(calls), 3)  # Original + recovered + one provider 429.
            self.assertEqual(control.store.status(control.scope)["local_attempts_reserved"], 3)
            self.assertEqual(client.delete("/conversation", headers={
                "Authorization": f"Bearer {recovered.json()['session_id']}"}).status_code, 204)

    def test_expired_context_rejected_before_cleanup_and_children_deleted(self):
        store = ConversationStore(self.core)
        view = store.create()
        with self.core.begin() as db:
            db.execute(update(m.conversations).where(m.conversations.c.id.in_(
                select(m.conversation_states.c.conversation_id).where(m.conversation_states.c.token_hash ==
                    hashlib.sha256(view["session_id"].encode()).hexdigest()))).values(
                created_at=func.clock_timestamp() - text("interval '31 minutes'"),
                expires_at=func.clock_timestamp() - text("interval '1 second'")))
        with self.assertRaises(ChatError):
            store.restore(view["session_id"])
        self.assertGreaterEqual(store.cleanup(), 1)

    def test_concurrent_updates_cannot_overwrite_successful_context(self):
        store = ConversationStore(self.core)
        initial = store.create()
        request = ChatRequest(text="Prix ABIP?", session_id=initial["session_id"])
        one, two = store.begin(request), store.begin(request)
        fake = AsyncMock()
        fake.interpret.return_value = response()
        service = ChatService(self.catalog, fake, self.directory)
        result = asyncio.run(service.respond(ChatRequest(text="Prix ABIP?")))
        state = encode_state(service.sessions[result.session_id])
        choice = encode_choice(service.pending[result.continuation_id])
        stored = store.complete(one, result, state, choice)
        with self.assertRaises(ChatError) as caught:
            store.complete(two, result, state, choice)
        self.assertEqual(caught.exception.code, "conversation_conflict")
        store.fail(two, "conversation_conflict")
        self.assertEqual(store.restore(stored.session_id)["response"]["answer"], result.answer)

    def test_refresh_and_failed_messages_do_not_extend_expiry(self):
        store = ConversationStore(self.core)
        initial = store.create()
        restored = store.restore(initial["session_id"])
        self.assertEqual(restored["expires_at_utc"], initial["expires_at_utc"])
        request = ChatRequest(text="Mon message conservé", session_id=restored["session_id"])
        turn = store.begin(request)
        store.fail(turn, "provider_unavailable")
        after = store.restore(restored["session_id"])
        self.assertEqual(after["expires_at_utc"], initial["expires_at_utc"])
        self.assertEqual(after["messages"][0]["text"], request.text)
        self.assertEqual(after["messages"][0]["outcome"], "failed")
        self.assertIsNone(after["response"])

    def test_concurrent_quota_reservations_and_budget_limits(self):
        store = PostgresQuotaStore(self.language, clock=lambda: 1000)
        scope = uuid.uuid4().hex
        def reserve(_):
            try:
                store.reserve(scope, 30)
                return "sent"
            except InferenceError as error:
                return error.detail.code
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(reserve, range(12)))
        self.assertEqual(results.count("sent"), 1)
        self.assertEqual(results.count("local_rate_limited"), 11)
        budget, evaluation = uuid.uuid4().hex, uuid.uuid4().hex
        store.new_budget(budget, evaluation, 1)
        store.reserve(uuid.uuid4().hex, 0, budget)
        with self.assertRaises(InferenceError):
            store.reserve(uuid.uuid4().hex, 0, budget)
        self.assertEqual(store.budget_counts(budget, evaluation)["attempts_reserved"], 1)

    def test_legacy_quota_import_preserves_cooldowns_without_modifying_ledger(self):
        store = PostgresQuotaStore(self.language, clock=lambda: 1000)
        with tempfile.TemporaryDirectory() as directory:
            path, scope = Path(directory) / "quota.sqlite3", uuid.uuid4().hex
            legacy = QuotaStore(path, clock=lambda: 1000)
            legacy.reserve(scope, 0)
            legacy.cooldown(scope, 120, "provider_rate_limited")
            store.import_sqlite(path)
            self.assertTrue(store.import_sqlite(path)["repeated"])
            self.assertEqual(store.status(scope)["cooldown_remaining_seconds"], 120)
            self.assertEqual(legacy.status(scope)["local_attempts_reserved"], 1)
            store.cooldown(scope, 240, "provider_rate_limited")
            store.import_sqlite(path)
            self.assertEqual(store.status(scope)["cooldown_remaining_seconds"], 240)


if __name__ == "__main__":
    unittest.main()
