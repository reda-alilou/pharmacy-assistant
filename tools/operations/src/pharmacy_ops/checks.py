"""Run owned unittest suites in isolated Python processes from the workspace."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from pharmacy_infrastructure.paths import ROOT

SUITES = {
    'core': 'services/core/tests', 'language': 'services/language/tests',
    'contracts': 'packages/contracts/tests', 'infrastructure': 'packages/infrastructure/tests',
    'operations': 'tools/operations/tests', 'evaluation': 'tools/evaluation/tests',
    'architecture': 'tests/architecture', 'integration': 'tests/integration',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', action='append', choices=list(SUITES))
    parser.add_argument('--list', action='store_true', help='List suite locations without running code')
    args = parser.parse_args()
    groups = args.group or list(SUITES)
    if args.list:
        for group in groups:
            print(f'{group}: {SUITES[group]}')
        return
    environment = dict(os.environ, PYTHONPATH=str(ROOT))
    failed = []
    for group in groups:
        directory = ROOT / SUITES[group]
        if not directory.is_dir():
            parser.error(f'Missing test suite: {SUITES[group]} (run from a full workspace checkout)')
        print(f'Running {group}: {SUITES[group]}', flush=True)
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', str(directory), '-v'], cwd=ROOT, env=environment)
        if result.returncode:
            failed.append(group)
    if failed:
        parser.exit(1, 'Failed suites: ' + ', '.join(failed) + '\n')


if __name__ == '__main__':
    main()
