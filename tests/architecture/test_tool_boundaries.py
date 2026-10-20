"""Maintained tools/tests must remain usable without the retired application."""
import ast
from pathlib import Path
import subprocess
import sys
import unittest

from pharmacy_infrastructure.paths import ROOT


class ToolBoundaryTests(unittest.TestCase):
    def test_maintained_code_and_coverage_import_no_legacy_namespace_or_streamlit(self):
        folders = ['services', 'packages', 'tools/operations', 'tools/evaluation',
                   'tests/support', 'tests/architecture', 'tests/integration']
        for folder in folders:
            for path in (ROOT / folder).rglob('*.py'):
                for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
                    names = ([node.module or ''] if isinstance(node,ast.ImportFrom) else
                             [a.name for a in node.names] if isinstance(node,ast.Import) else [])
                    for name in names:
                        with self.subTest(path=path.relative_to(ROOT),name=name):
                            self.assertNotIn(name.split('.')[0], {'pharmacy_assistant','streamlit'})

    def test_installed_tool_imports_work_when_legacy_and_streamlit_are_blocked(self):
        script = '''
import sys
class BlockRetired:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'pharmacy_assistant', 'streamlit'}:
            raise AssertionError('Retired dependency imported: ' + fullname)
sys.meta_path.insert(0, BlockRetired())
import pharmacy_ops.database, pharmacy_ops.backup, pharmacy_ops.compose_verify, pharmacy_ops.fixtures
import pharmacy_evaluation.runners.baseline, pharmacy_evaluation.runners.development
import pharmacy_evaluation.reporting.freeze, pharmacy_evaluation.reporting.analysis
'''
        result = subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
