"""Offline two-API harness. Serialize real HTTP contracts, mock hosted inference only."""
from contextlib import contextmanager, nullcontext
from unittest.mock import patch
import httpx
from fastapi.testclient import TestClient
from pharmacy_core.api.app import create_app
from pharmacy_core.config import CoreSettings
from pharmacy_language.config import LanguageSettings
from pharmacy_language.api.app import create_app as language_app
from pharmacy_core.clients.language import HttpInterpreter
from tests.support.runtime import core_app as offline_core, language_app as offline_language, core_settings

@contextmanager
def connected_apps(settings, interpreter=None, transport_state=None, *, persistent=False, language_config=None):
    provider = patch('pharmacy_language.api.app.create_interpreter', return_value=interpreter) if interpreter is not None else nullcontext()
    language_factory = language_app if persistent else offline_language
    language_config = language_config if persistent else settings
    with provider, TestClient(language_factory(settings=language_config)) as language:

        def dispatch(request):
            if transport_state is not None and (not transport_state['available']):
                raise httpx.ConnectError('offline-test-outage', request=request)
            result = language.request(request.method, request.url.path, content=request.content, headers={'content-type': 'application/json'})
            return httpx.Response(result.status_code, content=result.content, headers=result.headers)
        config = CoreSettings.for_app(settings) if persistent else core_settings(settings)
        remote = HttpInterpreter(config, httpx.AsyncClient(transport=httpx.MockTransport(dispatch)))
        factory = create_app if persistent else offline_core
        with patch('pharmacy_core.api.app.create_interpreter', return_value=remote), TestClient(factory(settings=config)) as core:
            yield core
