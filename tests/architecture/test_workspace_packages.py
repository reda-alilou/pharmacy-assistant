"""R2 ownership and integrity guards target canonical packages, not old shims."""
import ast
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pharmacy_infrastructure.paths import ROOT
from pharmacy_evaluation.runners.development import provenance
from pharmacy_evaluation.datasets.baseline import sha256
from pharmacy_evaluation.reporting.freeze import snapshot

class WorkspaceBoundaryTests(unittest.TestCase):

    def test_canonical_imports_respect_package_and_feature_ownership(self):
        roots = {'pharmacy_core': ROOT / 'services/core/src/pharmacy_core', 'pharmacy_language': ROOT / 'services/language/src/pharmacy_language', 'pharmacy_contracts': ROOT / 'packages/contracts/src/pharmacy_contracts', 'pharmacy_infrastructure': ROOT / 'packages/infrastructure/src/pharmacy_infrastructure'}
        allowed = {'pharmacy_core': {'pharmacy_core', 'pharmacy_contracts', 'pharmacy_infrastructure'}, 'pharmacy_language': {'pharmacy_language', 'pharmacy_contracts', 'pharmacy_infrastructure'}, 'pharmacy_contracts': {'pharmacy_contracts'}, 'pharmacy_infrastructure': {'pharmacy_infrastructure'}}
        for owner, root in roots.items():
            for path in root.rglob('*.py'):
                tree = ast.parse(path.read_text(encoding='utf-8'))
                for node in ast.walk(tree):
                    modules = [node.module or ''] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
                    for module in modules:
                        prefix = module.split('.')[0]
                        with self.subTest(path=path.relative_to(ROOT), module=module):
                            if prefix.startswith('pharmacy_'):
                                self.assertIn(prefix, allowed[owner])
                            if owner == 'pharmacy_contracts' or (owner == 'pharmacy_core' and path.relative_to(root).parts[0] in {'conversation', 'medications', 'pharmacies'}):
                                self.assertNotIn(prefix, {'fastapi', 'starlette', 'httpx', 'requests', 'groq', 'sqlalchemy'})

    def test_api_imports_need_no_legacy_package_or_peer_implementation(self):
        for module, banned in (('pharmacy_core.api.app', ('pharmacy_assistant', 'pharmacy_language', 'groq')), ('pharmacy_language.api.app', ('pharmacy_assistant', 'pharmacy_core'))):
            script = f"import {module}\nimport sys\nfor p in {banned!r}: assert not any(n == p or n.startswith(p+'.') for n in sys.modules), p"
            with tempfile.TemporaryDirectory() as directory:
                result = subprocess.run([sys.executable, '-c', script], cwd=directory, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_evaluation_detects_changes_in_canonical_implementations(self):
        files = ('services/core/src/pharmacy_core/conversation/service.py', 'services/language/src/pharmacy_language/extraction/prompt.py', 'packages/contracts/src/pharmacy_contracts/interpretation.py', 'tools/operations/src/pharmacy_ops/export_contract.py', 'tools/evaluation/src/pharmacy_evaluation/scoring/extraction.py')
        hashes = provenance()['backend_sha256']
        frozen = snapshot()
        for name in files:
            path = ROOT / name
            self.assertEqual(hashes[name], sha256(path))
            self.assertEqual(frozen[name], hashes[name])

            def changed(candidate):
                return 'changed' if candidate == path else sha256(candidate)
            with patch('pharmacy_evaluation.runners.development.sha256', side_effect=changed):
                self.assertNotEqual(provenance()['backend_sha256'][name], hashes[name])
            with patch('pharmacy_evaluation.reporting.freeze.sha256', side_effect=changed):
                self.assertNotEqual(snapshot(), frozen)

    def test_initial_migration_bytes_are_preserved_at_service_locations(self):
        inventory = json.loads((ROOT / 'docs/validation/cleanup-r1-inventory.json').read_text(encoding='utf-8'))
        for row in inventory['entries']:
            if row['path'].startswith('migrations/') and '/versions/' in row['path']:
                self.assertEqual(sha256(ROOT / row['destinations'][0]), row['working_tree_sha256_at_capture'])
if __name__ == '__main__':
    unittest.main()
