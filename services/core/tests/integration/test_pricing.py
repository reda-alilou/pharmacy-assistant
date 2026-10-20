import unittest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from tests.support.runtime import core_app as create_app
from tests.support.configuration import FixtureSettings as Settings
from tests.support.chat import mention, response

class PricingApiAndUiTests(unittest.TestCase):

    def test_real_api_returns_exact_string_amounts_and_rejects_injected_prices(self):
        interpreter = AsyncMock()
        interpreter.interpret.return_value = response([mention('ABIP', presentation='boîte de 30', quantity='deux boîtes')])
        with patch('pharmacy_core.api.app.create_interpreter', return_value=interpreter), TestClient(create_app(settings=Settings())) as client:
            result = client.post('/chat', json={'text': 'Prix deux boîtes ABIP boîte de 30'})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json()['order_pricing']['total_price_mad'], '744.00')
            self.assertEqual(result.json()['medications'][0]['pricing']['unit_price_mad'], '372.00')
            self.assertEqual(client.post('/chat', json={'text': 'ABIP', 'unit_price_mad': '0.01'}).status_code, 422)
        interpreter.interpret.assert_awaited_once()
