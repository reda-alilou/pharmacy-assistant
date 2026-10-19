"""Browser-style three-turn conversation through the actual HTTP API contract."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from streamlit.testing.v1 import AppTest

from pharmacy_assistant.api import create_app
from pharmacy_assistant.chat_models import ChatResponse
from pharmacy_assistant.config import ROOT, Settings
from pharmacy_assistant.demo_client import DemoClient, DemoError
from test_chat import mention, response
import test_demo


class DemoConversationChainTests(unittest.TestCase):
    def test_screenshot_sequence_uses_the_latest_response_session_even_after_retry(self):
        for rate_limited in (False, True):
            with self.subTest(rate_limited=rate_limited):
                interpreter = AsyncMock()
                interpreter.interpret.side_effect = [
                    response([mention('abip')]),
                    response([mention(None, presentation='30')], intents=['medication_information'], language='darija'),
                    response([mention(None, quantity='deux boites')]),
                ]
                test_demo.StreamlitTests.setUpClass()
                with patch('pharmacy_assistant.api.create_interpreter', return_value=interpreter), \
                     TestClient(create_app(settings=Settings())) as api:
                    payloads, responses = [], []
                    def chat(payload):
                        payloads.append(payload)
                        if rate_limited and len(payloads) == 3:
                            raise DemoError('local_rate_limited', 429, True, 0)
                        http = api.post('/chat', json=payload)
                        self.assertEqual(http.status_code, 200, http.text)
                        body = ChatResponse.model_validate(http.json())
                        responses.append(body)
                        return body
                    with patch.object(DemoClient, 'health', return_value=test_demo.StreamlitTests.health), \
                         patch.object(DemoClient, 'chat', side_effect=chat):
                        app = AppTest.from_file(str(ROOT/'src/pharmacy_assistant/demo.py'), default_timeout=15).run()
                        app.chat_input[0].set_value('quel est le prix de abip').run()
                        app.chat_input[0].set_value('l boita dyal 303afak').run()
                        self.assertFalse(app.exception)
                        self.assertEqual(responses[1].medications[0].medication.source_record_id, '9080')
                        # Reproduce the stale cached-token state implied by the
                        # supplied raw/effective JSON: the cache still points to
                        # the original ambiguous ABIP reply, while history shows
                        # the later resolved 30-tablet presentation.
                        app.session_state['session_id'] = responses[0].session_id
                        app.chat_input[0].set_value('et pour deux boites ?').run()
                        if rate_limited:
                            next(b for b in app.button if b.label == 'Réessayer').click().run()
                            self.assertEqual(payloads[-2], payloads[-1])
                        self.assertFalse(app.exception)
                        self.assertEqual(payloads[-1]['session_id'], responses[1].session_id)
                        self.assertEqual(responses[2].medications[0].medication.source_record_id, '9080')
                        self.assertEqual(responses[2].order_pricing.total_price_mad, '744.00')
                        self.assertTrue(any(m.value == '744.00 MAD' for m in app.metric))
                self.assertEqual(interpreter.interpret.await_count, 3)


if __name__ == '__main__': unittest.main()
