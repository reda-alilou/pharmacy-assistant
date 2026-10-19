"""UI interactions and HTTP errors, with all inference mocked offline."""

import asyncio
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import requests
from streamlit.testing.v1 import AppTest

from pharmacy_assistant.catalog import MedicationCatalog
from pharmacy_assistant.chat import ChatService
from pharmacy_assistant.chat_models import ChatRequest
from pharmacy_assistant.demo_client import DemoClient, DemoError, api_url
from pharmacy_assistant.models import HealthResponse
from pharmacy_assistant.pharmacy_directory import PharmacyDirectory
from pharmacy_assistant.run_demo import main as launch_demo
from test_chat import response


SCRIPT = Path(__file__).resolve().parents[1] / "src/pharmacy_assistant/demo.py"


def http_response(status, body, headers=None):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    result.headers.update(headers or {})
    return result


class DemoClientTests(unittest.TestCase):
    def test_api_url_cannot_contain_credentials_or_query_secrets(self):
        self.assertEqual(api_url("http://127.0.0.1:8000/"), "http://127.0.0.1:8000")
        for url in ("file:///tmp/key", "http://key:secret@localhost:8000", "http://localhost?key=secret", "http://localhost/other"):
            with self.assertRaises(ValueError):
                api_url(url)

    def test_provider_errors_are_redacted_and_cooldown_is_preserved(self):
        with patch("pharmacy_assistant.demo_client.requests.Session") as session:
            request = session.return_value.__enter__.return_value.request
            request.return_value = http_response(429, {"detail": {
                "code": "provider_rate_limited", "message": "SECRET_KEY_AND_PATIENT_TEXT", "retryable": True,
            }}, {"Retry-After": "30"})
            with self.assertRaises(DemoError) as caught:
                DemoClient().chat({"text": "ABIP"})
            error = caught.exception
            self.assertEqual(error.retry_after_seconds, 30)
            self.assertNotIn("SECRET", error.message)
            request.assert_called_once()
            self.assertNotIn("Authorization", request.call_args.kwargs)
            request.return_value = http_response(503, {"detail": {"code": "provider_authentication_failed", "retryable": False}})
            with self.assertRaises(DemoError) as caught:
                DemoClient().chat({"text": "ABIP"})
            self.assertFalse(caught.exception.retryable)

    def test_connection_timeout_malformed_response_and_input_errors(self):
        with patch("pharmacy_assistant.demo_client.requests.Session") as session:
            request = session.return_value.__enter__.return_value.request
            for exception, code in ((requests.ConnectionError(), "api_unreachable"), (requests.Timeout(), "api_timeout")):
                request.side_effect = exception
                with self.assertRaises(DemoError) as caught:
                    DemoClient().chat({"text": "ABIP"})
                self.assertEqual(caught.exception.code, code)
            request.side_effect = None
            request.return_value = http_response(200, {"answer": "unvalidated reply"})
            with self.assertRaises(DemoError) as caught:
                DemoClient().chat({"text": "ABIP"})
            self.assertEqual(caught.exception.code, "invalid_api_response")
            request.reset_mock()
            with self.assertRaises(DemoError):
                DemoClient().chat({"text": "  "})
            request.assert_not_called()


class StreamlitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = MedicationCatalog.from_path()
        from unittest.mock import AsyncMock
        interpreter = MagicMock()
        interpreter.interpret = AsyncMock(return_value=response())
        service = ChatService(catalog, interpreter, PharmacyDirectory.from_path())
        cls.initial = asyncio.run(service.respond(ChatRequest(text="Prix ABIP?")))
        cls.selected = asyncio.run(service.respond(ChatRequest(continuation_id=cls.initial.continuation_id,
                                                               selections=[{"mention_index": 0, "record_id": "9080"}])))
        cls.health = HealthResponse(catalog_dataset="offline-fixture", catalog_record_count=9936,
                                    catalog_brand_count=4087, interpretation_configured=True)

    def start_app(self):
        return AppTest.from_file(str(SCRIPT), default_timeout=10).run()

    def test_real_choice_payload_and_no_api_call_on_display_reruns(self):
        with patch.object(DemoClient, "health", return_value=self.health), patch.object(DemoClient, "chat", side_effect=[self.initial, self.selected]) as chat:
            app = self.start_app()
            self.assertEqual(len(app.exception), 0)
            chat.assert_not_called()
            app.chat_input[0].set_value("Prix ABIP?").run()
            self.assertEqual(len(app.exception), 0)
            choices = [button for button in app.button if "BOITE DE 30" in button.label]
            self.assertEqual(len(choices), 1)
            app.run()
            self.assertEqual(chat.call_count, 1)
            choices = [button for button in app.button if "BOITE DE 30" in button.label]
            choices[0].click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(chat.call_args.args[0], {"continuation_id": self.initial.continuation_id,
                                                    "selections": [{"mention_index": 0, "record_id": "9080"}]})
            self.assertTrue(any("372.00 MAD" in item.value for item in app.markdown))
            self.assertTrue(all(button.disabled for button in app.button if "BOITE DE" in button.label))

    def test_example_error_and_explicit_retry_preserve_the_original_payload(self):
        with patch.object(DemoClient, "health", return_value=self.health), patch.object(DemoClient, "chat", side_effect=[DemoError("provider_timeout", 504, True), self.initial]) as chat:
            app = self.start_app()
            next(button for button in app.button if button.label == "Français").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(app.error)
            self.assertFalse(app.session_state["turns"][0]["response"])
            app.run()
            self.assertEqual(chat.call_count, 1)
            next(button for button in app.button if button.label == "Réessayer").click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(chat.call_args_list[0], chat.call_args_list[1])
            self.assertEqual(len(app.session_state["turns"]), 1)
            next(button for button in app.button if button.label == "Nouvelle conversation").click().run()
            self.assertEqual(len(app.session_state["turns"]), 0)
            self.assertEqual(chat.call_count, 2)

    def test_expired_selection_restarts_text_and_never_replays_the_expired_token(self):
        with patch.object(DemoClient, "health", return_value=self.health), patch.object(DemoClient, "chat", side_effect=[self.initial, DemoError("clarification_expired", 410), self.initial]) as chat:
            app = self.start_app()
            app.chat_input[0].set_value("Prix ABIP?").run()
            next(button for button in app.button if "BOITE DE 20" in button.label).click().run()
            self.assertTrue(app.error)
            next(button for button in app.button if button.label == "Relancer la question initiale").click().run()
            self.assertEqual(chat.call_args.args[0], {"text": "Prix ABIP?"})
            self.assertEqual(len(app.exception), 0)

    def test_arabic_input_is_escaped_and_no_health_connection_has_recovery(self):
        with patch.object(DemoClient, "health", side_effect=DemoError("api_unreachable")), patch.object(DemoClient, "chat", side_effect=DemoError("api_unreachable", retryable=True)) as chat:
            app = self.start_app()
            app.chat_input[0].set_value("ما ثمن <script>alert(1)</script>؟").run()
            self.assertEqual(len(app.exception), 0)
            self.assertTrue(any("&lt;script&gt;" in item.value for item in app.markdown))
            self.assertFalse(any("<script>" in item.value for item in app.markdown))
            chat.assert_called_once()

    def test_cooldown_click_does_not_send_an_early_retry(self):
        with patch.object(DemoClient, "health", return_value=self.health), patch.object(DemoClient, "chat", side_effect=DemoError("provider_rate_limited", 429, True, 60)) as chat:
            app = self.start_app()
            app.chat_input[0].set_value("Prix ABIP?").run()
            next(button for button in app.button if button.label == "Réessayer").click().run()
            self.assertEqual(chat.call_count, 1)
            self.assertTrue(app.info)


class LauncherTests(unittest.TestCase):
    def test_reused_backend_is_never_stopped_by_the_launcher(self):
        child = MagicMock()
        child.poll.return_value = None
        with patch("sys.argv", ["run_demo"]), patch("pharmacy_assistant.run_demo.port_available", side_effect=[True, False]), \
             patch("pharmacy_assistant.run_demo.DemoClient") as client, \
             patch("pharmacy_assistant.run_demo.subprocess.Popen", return_value=child) as spawn, \
             patch("pharmacy_assistant.run_demo.time.sleep", side_effect=KeyboardInterrupt):
            self.assertEqual(launch_demo(), 0)
            self.assertEqual(spawn.call_count, 1)
            self.assertIn("streamlit", spawn.call_args.args[0])
            child.terminate.assert_called_once()
            client.return_value.health.assert_called_once()

    def test_owned_backend_and_ui_are_stopped_on_interrupt(self):
        backend, frontend = MagicMock(), MagicMock()
        backend.poll.return_value = frontend.poll.return_value = None
        with patch("sys.argv", ["run_demo"]), patch("pharmacy_assistant.run_demo.port_available", return_value=True), \
             patch("pharmacy_assistant.run_demo.DemoClient"), \
             patch("pharmacy_assistant.run_demo.subprocess.Popen", side_effect=[backend, frontend]), \
             patch("pharmacy_assistant.run_demo.time.sleep", side_effect=KeyboardInterrupt):
            self.assertEqual(launch_demo(), 0)
            backend.terminate.assert_called_once()
            frontend.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
