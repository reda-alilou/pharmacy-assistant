"""R6 immutable archive and historical scoring checks; no inference."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pharmacy_infrastructure.paths import ROOT
from pharmacy_infrastructure.evidence import resolve_input, verify_archive
from pharmacy_evaluation.reporting.analysis import analyze
from pharmacy_evaluation.reporting.freeze import verify_freeze
from pharmacy_evaluation.config import EvaluationSettings


class ArchivedEvidenceTests(unittest.TestCase):
    def test_complete_inventory_archive_and_active_inputs_preserve_R1_bytes(self):
        manifest=json.loads((ROOT/'archive/manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['entries']),1002)
        self.assertEqual(len(manifest['active_relocations']),2)
        self.assertEqual(verify_archive()['verified_files'],1004)
        inventory=json.loads((ROOT/'docs/validation/cleanup-r1-inventory.json').read_text(encoding='utf-8'))
        original={r['path']:r for r in inventory['entries']}
        for row in manifest['entries']+manifest['active_relocations']:
            self.assertEqual(row['sha256'],original[row['original_path']]['working_tree_sha256_at_capture'])
            self.assertFalse((ROOT/row['original_path']).is_file())

    def test_historical_heldout_and_correction_predictions_can_be_scored_without_rewriting_sources(self):
        for name,split,metrics in [('held_out_qwen_frozen_v1.json','held_out','held_out_qwen_frozen_metrics.json'),
                                   ('matching_package_live_v2.json','development','matching_package_metrics_complete.json')]:
            source=ROOT/'reports'/name
            actual=resolve_input(source)
            before=hashlib.sha256(actual.read_bytes()).hexdigest()
            with self.subTest(report=name),tempfile.TemporaryDirectory() as directory:
                report=analyze(source,Path(directory)/'metrics.json',split=split)
                recorded=json.loads(resolve_input(ROOT/'reports'/metrics).read_text(encoding='utf-8'))
                for key in ('backend','raw_standalone','dialogue_intents_and_current_slots','schema','attempts_reserved'):
                    self.assertEqual(report[key],recorded[key],key)
                self.assertEqual(hashlib.sha256(actual.read_bytes()).hexdigest(),before)
                self.assertFalse(source.exists())

    def test_archived_freeze_cannot_authorize_current_heldout_execution(self):
        settings=EvaluationSettings(language_database_url='postgresql+psycopg://fixture:fixture@127.0.0.1:1/offline')
        with self.assertRaisesRegex(ValueError,'Frozen code, data or model settings changed'), \
             patch('pharmacy_evaluation.reporting.freeze.Settings.from_env',side_effect=AssertionError('Private configuration read')):
            verify_freeze(settings,ROOT/'reports/qwen_evaluation_freeze.json')
