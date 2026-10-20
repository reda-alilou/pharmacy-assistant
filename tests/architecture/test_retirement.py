"""Keep retired modules and dependencies out of the maintained project."""
import importlib.util
from pathlib import Path
import tomllib
import unittest

from pharmacy_infrastructure.paths import ROOT


class RetirementTests(unittest.TestCase):
    def test_old_source_and_root_tests_are_retired_after_coverage_migration(self):
        self.assertEqual(list((ROOT/'src').rglob('*.py')),[])
        self.assertEqual(sorted(p.name for p in (ROOT/'tests').glob('*.py')),['__init__.py'])
        for name in ('alembic.ini','deploy/verification_seed.py','deploy/compose.database.yaml','.streamlit/config.toml'):
            self.assertFalse((ROOT/name).exists())
        self.assertIsNone(importlib.util.find_spec('pharmacy_assistant'))
        self.assertIsNone(importlib.util.find_spec('streamlit'))

    def test_root_is_a_virtual_coordinator_and_retained_dependencies_own_their_manifests(self):
        manifest=tomllib.loads((ROOT/'pyproject.toml').read_text(encoding='utf-8'))
        self.assertFalse(manifest['tool']['uv']['package'])
        self.assertNotIn('build-system',manifest)
        self.assertNotIn('scripts',manifest['project'])
        self.assertNotIn('dependency-groups',manifest)
        self.assertEqual(len(manifest['tool']['uv']['workspace']['members']),6)
        locked={p['name'] for p in tomllib.loads((ROOT/'uv.lock').read_text())['package']}
        self.assertTrue({'streamlit','beautifulsoup4','requests','pydeck','altair','soupsieve'}.isdisjoint(locked))
