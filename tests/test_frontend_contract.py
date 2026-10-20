"""Keep the browser's checked-in contract and offline fixtures aligned with core."""

import json
import unittest
from unittest.mock import patch

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import CoreSettings
from pharmacy_assistant.core.chat_models import ChatResponse
from pharmacy_assistant.paths import ROOT


class FrontendContractTests(unittest.TestCase):
    def test_openapi_snapshot_matches_core_without_runtime_configuration(self):
        with patch.object(CoreSettings, "from_env", side_effect=AssertionError("Runtime settings read")):
            actual = create_app().openapi()
        snapshot = json.loads((ROOT / "frontend/contracts/core.openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(snapshot, actual)

    def test_browser_factual_fixtures_validate_against_core_response(self):
        fixtures = json.loads((ROOT / "frontend/tests/fixtures/responses.json").read_text(encoding="utf-8"))
        for name, value in fixtures.items():
            with self.subTest(fixture=name):
                ChatResponse.model_validate(value)


if __name__ == "__main__":
    unittest.main()
