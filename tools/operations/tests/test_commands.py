from contextlib import redirect_stdout
import importlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pharmacy_core.api.app import create_app
from pharmacy_ops.export_contract import main as export_contract


class CommandBoundaryTests(unittest.TestCase):
    def test_help_never_reads_configuration_or_starts_services(self):
        for name in ('database','backup','compose_setup','compose_verify','export_contract','fixtures','quota','checks','archive'):
            module=importlib.import_module('pharmacy_ops.'+name)
            with self.subTest(command=name),patch('sys.argv',[name,'--help']), \
                 patch('pharmacy_infrastructure.environment.dotenv_values',side_effect=AssertionError('Settings read')), \
                 patch('subprocess.run',side_effect=AssertionError('Process started')), \
                 redirect_stdout(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    module.main()
                self.assertEqual(caught.exception.code,0)

    def test_contract_export_accepts_a_new_output_without_runtime_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'contract.json'
            with patch('sys.argv',['pharmacy-export-contract','--output',str(target)]), \
                 patch('pharmacy_infrastructure.environment.dotenv_values',side_effect=AssertionError('Settings read')), \
                 redirect_stdout(io.StringIO()):
                export_contract()
            self.assertEqual(json.loads(target.read_text(encoding='utf-8')),create_app().openapi())
