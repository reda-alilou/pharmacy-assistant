import ast
import subprocess
import sys
import unittest
from unittest.mock import patch
from pharmacy_infrastructure.paths import ENV_FILE
from pharmacy_core.medications.catalog import DATASET
from pharmacy_core.pharmacies.directory import PHARMACIES
from pharmacy_evaluation.runners.development import provenance
from pharmacy_evaluation.datasets.baseline import sha256
from pharmacy_evaluation.reporting.freeze import snapshot
from pharmacy_infrastructure.paths import ROOT

class OwnershipTests(unittest.TestCase):

    def test_core_import_needs_no_http_framework_provider_or_collector(self):
        script = "\nimport sys\nfrom pharmacy_core.conversation.service import ChatService\nfrom pharmacy_core.medications.catalog import MedicationCatalog\nfrom pharmacy_core.pharmacies.directory import PharmacyDirectory\nfor prefix in ('fastapi', 'groq', 'httpx', 'pharmacy_assistant.language',\n               'pharmacy_assistant.collection_http',\n               'pharmacy_assistant.collect_rabat_pharmacies'):\n    assert not any(name == prefix or name.startswith(prefix + '.') for name in sys.modules), prefix\n"
        result = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


    def test_data_and_environment_paths_still_resolve_from_repository_root(self):
        self.assertEqual(ENV_FILE, ROOT / '.env')
        self.assertEqual(DATASET, ROOT / 'data/imports/ammps_medications_enriched.jsonl')
        self.assertEqual(PHARMACIES, ROOT / 'data/imports/pharmacies_rabat.jsonl')
        self.assertTrue(DATASET.is_file())
        self.assertTrue(PHARMACIES.is_file())
