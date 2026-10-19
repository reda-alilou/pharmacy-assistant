"""Held-out gate refuses changed code/configuration and incomplete development."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pharmacy_assistant.config import Settings
from pharmacy_assistant.evaluation_dataset import sha256
from pharmacy_assistant.evaluation_freeze import create_freeze, verify_freeze
from pharmacy_assistant.nlu import PROMPT_VERSION


class FreezeTests(unittest.TestCase):
    def test_freeze_and_reverify_refuse_changed_code_model_or_development_evidence(self):
        settings = Settings(inference_provider='groq', groq_api_key='secret-never-saved')
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root/'predictions.json'
            source.write_text(json.dumps({'predictions':[{'response':{'metadata':{'prompt_version':PROMPT_VERSION}}}]}))
            development = root/'metrics.json'
            development.write_text(json.dumps({
                'split':'development', 'status':'complete', 'dialogue_intents_and_current_slots':{'passed':True},
                'raw_standalone':{'passed':True}, 'backend':{'passed':40},
                'provider':settings.inference_provider, 'model':settings.inference_model, 'output_mode':settings.inference_output_mode,
                'sources':{'backend_sha256':{'chat.py':'unchanged'}},
                'source_report':str(source), 'source_report_sha256':sha256(source)}))
            output = root/'freeze.json'
            with patch('pharmacy_assistant.evaluation_freeze.snapshot',return_value={'src/pharmacy_assistant/chat.py':'unchanged'}):
                create_freeze(settings, development, output)
                verify_freeze(settings, output)
                self.assertNotIn('secret-never-saved',output.read_text())
                with self.assertRaisesRegex(ValueError,'settings changed'):
                    verify_freeze(settings.model_copy(update={'groq_model':'other-model'}),output)
                with patch('pharmacy_assistant.evaluation_freeze.snapshot',return_value={'src/pharmacy_assistant/chat.py':'changed'}):
                    with self.assertRaisesRegex(ValueError,'changed'):
                        verify_freeze(settings,output)
                development.write_text('{}')
                with self.assertRaisesRegex(ValueError,'development report changed'):
                    verify_freeze(settings,output)

    def test_incomplete_development_cannot_be_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            report=root/'metrics.json'
            report.write_text(json.dumps({'split':'development','status':'paused_provider',
                                          'dialogue_intents_and_current_slots':{'passed':False}}))
            with self.assertRaisesRegex(ValueError,'Complete passing development'):
                create_freeze(Settings(),report,root/'freeze.json')
            self.assertFalse((root/'freeze.json').exists())


if __name__ == '__main__':
    unittest.main()
