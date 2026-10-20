"""Offline two-API harness. Serialize real HTTP contracts, mock hosted inference only."""

from contextlib import contextmanager, nullcontext
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient

from pharmacy_assistant.api import create_app
from pharmacy_assistant.config import CoreSettings
from pharmacy_assistant.language.api import create_app as language_app
from pharmacy_assistant.transport.language import HttpInterpreter


@contextmanager
def connected_apps(settings, interpreter=None, transport_state=None):
    provider = patch("pharmacy_assistant.language.api.create_interpreter", return_value=interpreter) if interpreter is not None else nullcontext()
    with provider, TestClient(language_app(settings=settings)) as language:
        def dispatch(request):
            if transport_state is not None and not transport_state["available"]:
                raise httpx.ConnectError("offline-test-outage", request=request)
            result = language.request(request.method, request.url.path, content=request.content,
                                      headers={"content-type": "application/json"})
            return httpx.Response(result.status_code, content=result.content, headers=result.headers)
        core_settings = CoreSettings.for_app(settings)
        remote = HttpInterpreter(core_settings, httpx.AsyncClient(transport=httpx.MockTransport(dispatch)))
        with patch("pharmacy_assistant.api.create_interpreter", return_value=remote), TestClient(create_app(settings=core_settings)) as core:
            yield core
