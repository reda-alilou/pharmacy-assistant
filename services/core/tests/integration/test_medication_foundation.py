import json
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode
from tests.support.runtime import core_app as create_app
from pharmacy_core.medications.catalog import DATASET

def expected_snapshot():
    from tests.support.catalogue import profile
    p = profile()
    return p["records"], p["source_pages"], p["missing_public_prices"], set(p["source_listings"])
EXPECTED_RECORDS, EXPECTED_PAGES, EXPECTED_MISSING_PPV, EXPECTED_LISTINGS = expected_snapshot()

async def http_get(app, path, parameters=None):
    """Exercise the actual ASGI routing, validation and serialization stack."""
    events = []

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    async def send(event):
        events.append(event)
    scope = {'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': 'GET', 'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': urlencode(parameters or {}).encode(), 'headers': [], 'client': ('127.0.0.1', 1), 'server': ('test', 80), 'root_path': ''}
    await app(scope, receive, send)
    status = next((e['status'] for e in events if e['type'] == 'http.response.start'))
    body = b''.join((e.get('body', b'') for e in events if e['type'] == 'http.response.body'))
    return (status, json.loads(body))

class ApiTests(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        self.app = create_app()
        self.lifespan = self.app.router.lifespan_context(self.app)
        await self.lifespan.__aenter__()

    async def asyncTearDown(self):
        await self.lifespan.__aexit__(None, None, None)

    async def test_health_and_search_need_no_further_file_reads(self):
        with patch.object(Path, 'open', side_effect=AssertionError('Unexpected file read')):
            status, health = await http_get(self.app, '/health')
            self.assertEqual(status, 200)
            self.assertEqual(health['catalog_record_count'], EXPECTED_RECORDS)
            for query in ('ABIP', 'AIRCORT'):
                status, result = await http_get(self.app, '/medications/search', {'query': query})
                self.assertEqual(status, 200)
                self.assertGreater(result['result_count'], 0)

    async def test_original_search_fields_and_new_filters(self):
        status, result = await http_get(self.app, '/medications/search', {'query': 'ABIP', 'strength': '15mg', 'form': 'comprimé', 'presentation': '20'})
        self.assertEqual(status, 200)
        self.assertTrue({'query', 'result_count', 'medications', 'catalog_scope'} <= result.keys())
        self.assertEqual(result['result_count'], 1)
        self.assertEqual(result['medications'][0]['ppv_price_mad'], 268.0)

    async def test_invalid_queries_return_422_instead_of_500(self):
        for parameters in ({}, {'query': ''}, {'query': '   '}, {'query': 'x' * 201}, {'query': '́'}, {'query': 'ABIP', 'strength': '  '}):
            status, _ = await http_get(self.app, '/medications/search', parameters)
            self.assertEqual(status, 422)

    async def test_lookup_and_partial_catalogue_404(self):
        status, medication = await http_get(self.app, '/medications/9079')
        self.assertEqual(status, 200)
        self.assertEqual(medication['brand_name'], 'ABIP')
        self.assertEqual(medication['ppv_price_mad'], 268.0)
        status, error = await http_get(self.app, '/medications/999999999')
        self.assertEqual(status, 404)
        self.assertIn('partial catalogue', error['detail'])

    async def test_fuzzy_api_response_requires_review(self):
        status, result = await http_get(self.app, '/medications/search', {'query': 'ABPI'})
        self.assertEqual(status, 200)
        self.assertEqual(result['medications'], [])
        self.assertEqual(result['status'], 'suggestions')
        self.assertTrue(result['suggestions'])
