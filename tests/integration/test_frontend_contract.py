import json
import unittest
from unittest.mock import patch
from pharmacy_core.api.app import create_app
from pharmacy_core.config import CoreSettings
from pharmacy_core.conversation.models import ChatResponse
from pharmacy_infrastructure.paths import ROOT

class FrontendContractTests(unittest.TestCase):

    def test_openapi_snapshot_matches_core_without_runtime_configuration(self):
        with patch.object(CoreSettings, 'from_env', side_effect=AssertionError('Runtime settings read')):
            actual = create_app().openapi()
        snapshot = json.loads((ROOT / 'apps/web/contracts/core.openapi.json').read_text(encoding='utf-8'))
        self.assertEqual(snapshot, actual)

    def test_browser_factual_fixtures_validate_against_core_response(self):
        fixtures = json.loads((ROOT / 'apps/web/tests/fixtures/responses.json').read_text(encoding='utf-8'))
        for name, value in fixtures.items():
            with self.subTest(fixture=name):
                ChatResponse.model_validate(value)
