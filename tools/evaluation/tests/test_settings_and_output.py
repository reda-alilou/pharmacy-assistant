import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from pharmacy_evaluation.config import EvaluationSettings
from pharmacy_evaluation.reporting.io import write_report
from pharmacy_evaluation.reporting.state import report_lock
from pharmacy_infrastructure.paths import ROOT


class EvaluationBoundaryTests(unittest.TestCase):
    def test_live_settings_require_postgres_without_combined_secrets_or_sqlite(self):
        with self.assertRaises(ValidationError):
            EvaluationSettings()
        config=EvaluationSettings(language_database_url='postgresql+psycopg://language:private@host/database')
        self.assertFalse(hasattr(config,'core_database_url'))
        self.assertFalse(hasattr(config,'inference_quota_db'))
        self.assertNotIn('private',repr(config))

    def test_reports_and_locks_cannot_overwrite_historical_evidence_or_data(self):
        for directory in ('data','reports','archive'):
            with self.subTest(directory=directory), self.assertRaisesRegex(ValueError,'read-only'), \
                 patch.object(Path,'mkdir',side_effect=AssertionError('Unexpected write')):
                with report_lock(ROOT/directory/'do-not-create.json'):
                    self.fail('Protected path accepted')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.json'
            write_report(path,{'status':'fixture'})
            self.assertIn('fixture',path.read_text())
