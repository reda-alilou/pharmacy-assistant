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
    def test_analytics_probe_preserves_report_and_cleanup_after_later_failure(self):
        commands = []
        real_client = httpx.Client

        def command(arguments, **kwargs):
            commands.append(arguments)
            if 'exec' in arguments:
                raise RuntimeError('Controlled failure after analytics checks')
            stdout = '127.0.0.1:8080' if 'port' in arguments else ''
            return subprocess.CompletedProcess(arguments, 0, stdout, '')

        def response(request):
            path = request.url.path
            status, body = 200, {}
            if path == '/api/health':
                body = dict(catalog_record_count=9936, storage_backend='postgres', language_service_status='available')
            elif path == '/api/docs':
                return httpx.Response(200, text='/api/openapi.json')
            elif path == '/api/openapi.json':
                body = {'servers': [{'url': '/api'}]}
            elif path.endswith('/auth/session'):
                body = {'user': None, 'csrfToken': 'fixture-csrf'}
            elif path.endswith('/auth/register'):
                status, body = 201, {'user': {'id': 'owner', 'role': 'analyst'}, 'csrfToken': 'fixture-csrf'}
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
                kind = json.loads(request.content)['definition']['kind']
                body = {'kind': kind}
                if kind == 'aggregate':
                    body['rows'] = [{'metrics': [{'value': value} for value in ('499500', '499.5', '499.5', '249.75', '749.25')]}]
            elif path == '/platform-api/analyses':
                status, body = 201, {'analysis': {'id': 'saved'}}
            elif path.endswith('/dependencies'):
                body = {'canDelete': False}
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
            self.assertEqual(report['failed_stage'], 'platform analytics correctness and saved configuration')
            self.assertEqual(len(report['checks']), 6)
            self.assertTrue(report['checks']['platform_analytics_exact_statistics_four_features_and_saved_dependencies'])
            self.assertTrue(report['isolated_resources_removed'])
            self.assertTrue(any('down' in args and '--volumes' in args for args in commands))
            self.assertEqual([item.suffix for item in (root / '.runtime').iterdir()], ['.log'])
