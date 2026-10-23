"""Exercise verifier orchestration without starting containers or making requests."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import httpx

from pharmacy_ops import compose_verify


class ComposeVerifierTests(unittest.TestCase):
    def test_analytics_dashboard_probes_preserve_report_and_cleanup_after_later_failure(self):
        commands = []
        real_client = httpx.Client
        granted = False

        def command(arguments, **kwargs):
            commands.append(arguments)
            if 'exec' in arguments:
                raise RuntimeError('Controlled failure after analytics checks')
            stdout = '127.0.0.1:8080' if 'port' in arguments else ''
            return subprocess.CompletedProcess(arguments, 0, stdout, '')

        def response(request):
            nonlocal granted
            path = request.url.path
            status, body = 200, {}
            reader = 'fixture-reader' in request.headers.get('Cookie', '')
            if path == '/api/health':
                body = dict(catalog_record_count=9936, storage_backend='postgres', language_service_status='available')
            elif path == '/api/docs':
                return httpx.Response(200, text='/api/openapi.json')
            elif path == '/api/openapi.json':
                body = {'servers': [{'url': '/api'}]}
            elif path.endswith('/auth/session'):
                body = {'user': None, 'csrfToken': 'fixture-csrf'}
            elif path.endswith('/auth/register'):
                registered_reader = json.loads(request.content)['email'] == 'isolated-dashboard-reader@example.test'
                return httpx.Response(201, json={'user': {'id': 'reader' if registered_reader else 'owner', 'role': 'analyst'}, 'csrfToken': 'fixture-csrf'},
                    headers={'Set-Cookie': 'platform_session=' + ('fixture-reader' if registered_reader else 'fixture-owner') + '; Path=/'})
            elif path.endswith(('/admin/access', '/auth/logout')):
                status = 403
            elif path == '/platform-api/imports':
                status, body = 201, {'id': 'staged'}
            elif path == '/platform-api/imports/staged':
                body = {'rowCount': 1000, 'revision': 0, 'configuration': {
                    'columns': [{'id': name, 'originalName': name} for name in ('code', 'amount', 'label', 'observed_at')]}}
            elif path.endswith('/validate'):
                body = {'revision': 1, 'validation': {'valid': True}}
            elif path.endswith('/publish'):
                status, body = 201, {'datasetId': 'dataset', 'versionId': 'version'}
            elif path.endswith('/rows'):
                body = {'total': 1000, 'rows': [{'values': {'observed_at': '2026-10-18T16:17:23.815325Z'}} for _ in range(25)]}
            elif path.endswith('/analytics/execute'):
                if reader:
                    return httpx.Response(404, json={})
                kind = json.loads(request.content)['definition']['kind']
                body = {'kind': kind}
                if kind == 'aggregate':
                    body['rows'] = [{'metrics': [{'value': value} for value in ('499500', '499.5', '499.5', '249.75', '749.25')]}]
            elif path == '/platform-api/analyses':
                status, body = 201, {'analysis': {'id': 'saved'}}
            elif path.endswith('/dependencies'):
                body = {'canDelete': False}
            elif path == '/platform-api/dashboards':
                status, body = 201, {'dashboard': {'id': 'dashboard'}}
            elif path == '/platform-api/dashboards/dashboard/shares':
                granted = True
                status, body = 201, {'id': 'grant'}
            elif path == '/platform-api/dashboards/dashboard/shares/grant':
                granted = False
                status = 204
            elif path.startswith('/platform-api/dashboards/dashboard/widgets/'):
                payload = json.loads(request.content)
                if not granted:
                    status = 404
                elif 'definition' in payload or payload['values'][0]['values'] == ['0', '999']:
                    status = 422
                else:
                    body = {'result': {'rows': [{'metrics': [{'value': '124.5'}]}]}, 'columns': [{'id': 'amount'}]}
            elif path in ('/platform-api/datasets/dataset', '/platform-api/dashboards/dashboard/copy'):
                status = 404
            elif path not in ('/', '/healthz', '/platform-api/ready', '/platform-api/users/owner'):
                raise AssertionError('Unexpected mocked request: ' + path)
            return httpx.Response(status, json=body)

        with tempfile.TemporaryDirectory(prefix='cp3-verifier-') as directory:
            root = Path(directory).resolve()
            self.assertEqual(root.parent, Path(tempfile.gettempdir()).resolve())
            self.assertTrue(root.name.startswith('cp3-verifier-'))
            with patch.object(compose_verify, 'ROOT', root), \
                 patch.object(compose_verify.subprocess, 'run', side_effect=command), \
                 patch.object(compose_verify.httpx, 'Client', side_effect=lambda **kwargs: real_client(
                     **kwargs, transport=httpx.MockTransport(response))), \
                 patch('builtins.print'):
                exit_code = compose_verify.verify(output=Path('report.json'))
            report = json.loads((root / 'report.json').read_text(encoding='utf-8'))
            self.assertEqual(exit_code, 1)
            self.assertFalse(report['passed'])
            self.assertEqual(report['error_type'], 'RuntimeError')
            self.assertEqual(report['failed_stage'], 'platform dashboard filtering and read-only sharing')
            self.assertEqual(len(report['checks']), 7)
            self.assertTrue(report['checks']['platform_analytics_exact_statistics_four_features_and_saved_dependencies'])
            self.assertTrue(report['checks']['platform_dashboard_filters_result_only_sharing_revocation_and_copy_boundary'])
            self.assertTrue(report['isolated_resources_removed'])
            self.assertTrue(any('down' in args and '--volumes' in args for args in commands))
            self.assertEqual([item.suffix for item in (root / '.runtime').iterdir()], ['.log'])
