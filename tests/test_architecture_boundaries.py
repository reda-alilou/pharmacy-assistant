"""Checkpoint 1: ownership, transport isolation, and compatibility contracts."""

import ast
import importlib
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import ENV_FILE, Settings
from pharmacy_assistant.core.catalog import DATASET
from pharmacy_assistant.core.errors import ChatError
from pharmacy_assistant.contracts.storage import StorageUnavailable
from pharmacy_assistant.core.storage.conversations import ConversationStore
from pharmacy_assistant.core.pharmacy_directory import PHARMACIES
from pharmacy_assistant.evaluate_development import provenance
from pharmacy_assistant.evaluation_dataset import sha256
from pharmacy_assistant.evaluation_freeze import snapshot
from pharmacy_assistant.paths import ROOT


PACKAGE = ROOT / "src/pharmacy_assistant"


class OwnershipTests(unittest.TestCase):
    def test_core_import_needs_no_http_framework_provider_or_collector(self):
        script = """
import sys
from pharmacy_assistant.core.chat import ChatService
from pharmacy_assistant.core.catalog import MedicationCatalog
from pharmacy_assistant.core.pharmacy_directory import PharmacyDirectory
for prefix in ('fastapi', 'groq', 'httpx', 'pharmacy_assistant.language',
               'pharmacy_assistant.collection_http',
               'pharmacy_assistant.collect_rabat_pharmacies'):
    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix
"""
        result = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_service_imports_respect_ownership(self):
        allowed = {
            "core": ("pharmacy_assistant.core", "pharmacy_assistant.contracts", "pharmacy_assistant.paths"),
            "language": ("pharmacy_assistant.language", "pharmacy_assistant.contracts",
                         "pharmacy_assistant.config", "pharmacy_assistant.paths", "pharmacy_assistant.database"),
            "contracts": ("pharmacy_assistant.contracts",),
        }
        for package, prefixes in allowed.items():
            for path in (PACKAGE / package).rglob("*.py"):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    modules = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                               else [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
                    for module in modules:
                        with self.subTest(path=path.name, module=module):
                            if module.startswith("pharmacy_assistant"):
                                self.assertTrue(any(module == p or module.startswith(p + ".") for p in prefixes))
                            if package in {"core", "contracts"}:
                                self.assertNotIn(module.split(".")[0], {"fastapi", "starlette", "groq", "httpx", "requests"})

    def test_legacy_imports_share_the_canonical_modules(self):
        groups = {
            "core": ("chat", "chat_models", "conversation", "catalog", "models", "resolution",
                     "medication_normalization", "pharmacy_directory", "pharmacy_normalization",
                     "pricing", "answer_templates"),
            "language": ("inference", "nlu", "gemini_nlu", "opencode_nlu", "quota"),
            "contracts": ("nlu_models",),
        }
        for package, names in groups.items():
            for name in names:
                with self.subTest(module=name):
                    self.assertIs(importlib.import_module(f"pharmacy_assistant.{name}"),
                                  importlib.import_module(f"pharmacy_assistant.{package}.{name}"))
        from pharmacy_assistant.collect_rabat_pharmacies import PharmacyRecord as legacy_record
        from pharmacy_assistant.core.pharmacy_models import PharmacyRecord
        self.assertIs(legacy_record, PharmacyRecord)

    def test_data_and_environment_paths_still_resolve_from_repository_root(self):
        self.assertEqual(ENV_FILE, ROOT / ".env")
        self.assertEqual(DATASET, ROOT / "data/processed/ammps_medications_enriched.jsonl")
        self.assertEqual(PHARMACIES, ROOT / "data/processed/pharmacies_rabat.jsonl")
        self.assertTrue(DATASET.is_file())
        self.assertTrue(PHARMACIES.is_file())

    def test_evaluation_guards_include_changes_in_nested_implementation(self):
        targets = ("core/chat.py", "language/nlu.py", "contracts/nlu_models.py")
        initial = provenance()["backend_sha256"]
        frozen = snapshot()
        for target in targets:
            with self.subTest(target=target):
                self.assertEqual(initial[target], sha256(PACKAGE / target))
                self.assertEqual(frozen[f"src/pharmacy_assistant/{target}"], initial[target])
                def changed_hash(path):
                    return "changed" if path == PACKAGE / target else sha256(path)
                with patch("pharmacy_assistant.evaluate_development.sha256", side_effect=changed_hash):
                    self.assertNotEqual(provenance()["backend_sha256"][target], initial[target])
                with patch("pharmacy_assistant.evaluation_freeze.sha256", side_effect=changed_hash):
                    self.assertNotEqual(snapshot(), frozen)


class ChatErrorApiTests(unittest.TestCase):
    def test_application_errors_keep_the_existing_http_contract(self):
        errors = {
            "session_expired": 410, "clarification_expired": 410,
            "invalid_reference": 422, "invalid_selection": 422, "invalid_refinement": 422,
            "conversation_conflict": 409, "request_in_progress": 409, "request_conflict": 409,
        }
        interpreter = AsyncMock()
        with patch("pharmacy_assistant.api.create_interpreter", return_value=interpreter):
            with TestClient(create_app(settings=Settings())) as client:
                for code, status in errors.items():
                    with self.subTest(code=code):
                        failure = ChatError(code, "Safe application message")
                        with patch.object(client.app.state.chat, "respond", side_effect=failure):
                            result = client.post("/chat", json={"text": "Prix ABIP?"})
                        self.assertEqual(result.status_code, status)
                        self.assertEqual(result.json(), {"detail": {"code": code, "message": failure.message}})
                interpreter.interpret.assert_not_awaited()
        interpreter.close.assert_awaited_once()

    def test_database_failures_are_sanitized_before_the_http_boundary(self):
        from sqlalchemy.exc import OperationalError
        engine = Mock()
        engine.begin.side_effect = OperationalError("private SQL", {}, Exception("private-password"))
        with self.assertRaises(StorageUnavailable) as caught:
            ConversationStore(engine).create()
        self.assertNotIn("private-password", str(caught.exception))
        interpreter = AsyncMock()
        with patch("pharmacy_assistant.api.create_interpreter", return_value=interpreter):
            with TestClient(create_app(settings=Settings())) as client:
                with patch.object(client.app.state.chat, "respond", side_effect=caught.exception):
                    result = client.post("/chat", json={"text": "Prix ABIP?"})
                self.assertEqual(result.status_code, 503)
                self.assertEqual(result.json()["detail"]["code"], "storage_unavailable")
                self.assertNotIn("private-password", result.text)
                interpreter.interpret.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
