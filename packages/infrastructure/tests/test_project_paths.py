"""Root resolution must survive package relocation and wheel installation."""
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pharmacy_infrastructure.paths import project_root


class ProjectRootTests(unittest.TestCase):
    def test_explicit_root_is_independent_of_source_depth(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"PHARMACY_PROJECT_ROOT": directory}):
                self.assertEqual(project_root(), Path(directory).resolve())

    def test_invalid_explicit_root_fails_without_exposing_its_value(self):
        with patch.dict(os.environ, {"PHARMACY_PROJECT_ROOT": "relative-private-path"}):
            with self.assertRaises(ValueError) as caught:
                project_root()
        self.assertNotIn("relative-private-path", str(caught.exception))

    def test_workspace_is_discovered_from_nested_working_directory(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text('[project]\nname="pharmacy-assistant"\n', encoding="utf-8")
            nested = root / "deep" / "nested"
            nested.mkdir(parents=True)
            try:
                os.chdir(nested)
                with patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(project_root(), root.resolve())
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
