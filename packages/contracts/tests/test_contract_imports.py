"""Contracts are usable without importing a service or provider."""
import subprocess
import sys
import unittest


class ContractImportTests(unittest.TestCase):
    def test_contract_import_does_not_load_frameworks_storage_or_services(self):
        script = """
import pharmacy_contracts.interpretation
import pharmacy_contracts.language
import pharmacy_contracts.interpreter
import pharmacy_contracts.errors
import sys
for prefix in ('pharmacy_core', 'pharmacy_language', 'pharmacy_assistant', 'fastapi', 'httpx', 'groq', 'sqlalchemy'):
    assert not any(n == prefix or n.startswith(prefix + '.') for n in sys.modules), prefix
"""
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
